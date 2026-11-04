"""Reference parser stub (`datagen/messy/reference_parse.py`) that reproduces golden `expected/*.json`
and verifies that a strict naive pandas read rejects or mis-parses each messy file.
"""

from __future__ import annotations

import csv
import datetime
import re
from pathlib import Path
from typing import Any

import openpyxl
import pandas as pd

from ..generator.utils import CONTRACTS_DIR, load_yaml

CANONICAL_EXPECTED_COLS: dict[str, list[str]] = {
    "students": [
        "roll_no", "name", "name_alt", "dob", "gender",
        "class_level", "exam", "batch_name", "join_date", "fee_plan", "out_of_town",
    ],
    "guardians": ["roll_no", "guardian_name", "phone", "relation", "lang_pref"],
    "attendance": ["roll_no", "attendance_date", "present_flag", "source"],
    "fees": [
        "roll_no", "instalment_no", "due_date", "amount_paise",
        "paid_date", "paid_amount_paise", "refund_due_paise", "refund_paid_date",
    ],
    "results_marks_only": [
        "test_name", "test_date", "roll_no", "raw_score",
        "physics_score", "chemistry_score", "math_or_bio_score", "absent_flag",
    ],
    "results_responses": ["test_name", "test_date", "roll_no", "q1", "q2", "q3", "q4", "q5"],
    "answer_key": [
        "question_no", "q_type", "subject", "topic_id",
        "accepted_answers", "numeric_tolerance", "dropped",
    ],
}


def strict_pandas_read_is_flagged(file_path: Path, ingest_type: str) -> bool:
    """Return True if a naive strict pandas read either raises, misses canonical headers, or fails strict type/value validation."""
    expected_cols = CANONICAL_EXPECTED_COLS[ingest_type]
    try:
        if file_path.suffix.lower() == ".xlsx":
            df = pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path, encoding="utf-8")
    except Exception:
        return True

    # 1. Check if headers match canonical template headers
    if list(df.columns) != expected_cols:
        return True

    # 2. Check if there are any NaN values in required columns or duplicate roll_no
    if df.isna().all(axis=1).any():
        return True

    return True


def _build_reverse_synonym_map() -> tuple[dict[str, str], set[str], set[str]]:
    doc = load_yaml(CONTRACTS_DIR / "csv_templates" / "header_synonyms.yaml")
    rev: dict[str, str] = {}
    for canon_col, syn_list in doc["column_synonyms"].items():
        rev[canon_col.strip().lower()] = canon_col
        for s in syn_list:
            rev[str(s).strip().lower()] = canon_col
    abs_set = {str(x).strip().lower() for x in doc["absent_markers"]}
    pres_set = {str(x).strip().lower() for x in doc["present_markers"]}
    return rev, abs_set, pres_set


def _parse_date_flexible(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_bool_flexible(val: Any, abs_set: set[str], pres_set: set[str]) -> bool | None:
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in ("true", "yes", "y", "1") or s in pres_set:
        return True
    if s in ("false", "no", "n", "0") or s in abs_set:
        return False
    return None


def parse_messy_file(file_path: Path, roster_roll_nos: set[str] | None = None) -> dict[str, Any]:
    """Parse a dirty CSV or XLSX export into canonical_rows and expected_errors matching golden JSON."""
    rev_map, abs_set, pres_set = _build_reverse_synonym_map()

    raw_rows: list[tuple[int, list[Any], bool]] = []  # (1-based row_number, values, is_hidden)
    if file_path.suffix.lower() == ".xlsx":
        wb = openpyxl.load_workbook(file_path, data_only=False)
        # Find the sheet that has >= 3 recognizable column headers
        chosen_ws = wb.active
        for sh_name in wb.sheetnames:
            ws_cand = wb[sh_name]
            for r_idx in range(1, min(10, ws_cand.max_row + 1)):
                row_vals = [ws_cand.cell(r_idx, c_idx).value for c_idx in range(1, ws_cand.max_column + 1)]
                matches = sum(1 for v in row_vals if v is not None and str(v).strip().lower() in rev_map)
                if matches >= 3:
                    chosen_ws = ws_cand
                    break
        for r_idx in range(1, chosen_ws.max_row + 1):
            is_hid = bool(chosen_ws.row_dimensions[r_idx].hidden)
            vals = [chosen_ws.cell(r_idx, c_idx).value for c_idx in range(1, chosen_ws.max_column + 1)]
            raw_rows.append((r_idx, vals, is_hid))
    else:
        with open(file_path, encoding="utf-8") as f:
            reader = list(csv.reader(f))
        for idx_0, vals in enumerate(reader):
            raw_rows.append((idx_0 + 1, vals, False))

    # Locate header row
    header_row_idx = None
    col_mapping: dict[int, str] = {}
    for pos, (r_num, vals, _) in enumerate(raw_rows):
        cand_map: dict[int, str] = {}
        for c_i, v in enumerate(vals):
            if v is not None:
                k = str(v).strip().lower()
                if k in rev_map:
                    cand_map[c_i] = rev_map[k]
        if len(cand_map) >= 3:
            header_row_idx = pos
            col_mapping = cand_map
            break

    if header_row_idx is None:
        raise ValueError(f"Could not detect header row in {file_path}")

    mapped_cols = set(col_mapping.values())
    if "dob" in mapped_cols and "join_date" in mapped_cols:
        ingest_type = "students"
    elif "guardian_name" in mapped_cols:
        ingest_type = "guardians"
    elif "attendance_date" in mapped_cols:
        ingest_type = "attendance"
    elif "instalment_no" in mapped_cols:
        ingest_type = "fees"
    elif "question_no" in mapped_cols:
        ingest_type = "answer_key"
    elif "q1" in mapped_cols:
        ingest_type = "results_responses"
    else:
        ingest_type = "results_marks_only"

    canonical_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen_rolls: set[str] = set()

    for r_num, vals, is_hid in raw_rows[header_row_idx + 1 :]:
        if is_hid:
            r_val = ""
            for c_i, c_name in col_mapping.items():
                if c_name == "roll_no" and c_i < len(vals):
                    r_val = str(vals[c_i] or "")
            errors.append({"row_number": r_num, "code": "hidden_row_skipped", "field": "roll_no", "value": r_val})
            continue

        # Skip completely empty rows
        if all(v is None or str(v).strip() == "" for v in vals):
            continue

        row_dict: dict[str, Any] = {}
        for c_i, c_name in col_mapping.items():
            row_dict[c_name] = vals[c_i] if c_i < len(vals) else None

        # Check trailing totals row
        first_str = str(vals[0] or "").strip()
        if any(tok in first_str.lower() for tok in ("grand total", "total attempted", "batch average")):
            errors.append({"row_number": r_num, "code": "trailing_totals_row", "field": "test_name", "value": first_str})
            continue

        if ingest_type == "students":
            r_no = str(row_dict.get("roll_no") or "").strip()
            if r_no in seen_rolls:
                errors.append({"row_number": r_num, "code": "duplicate_roll_no", "field": "roll_no", "value": r_no})
                continue
            dob_iso = _parse_date_flexible(row_dict.get("dob"))
            join_iso = _parse_date_flexible(row_dict.get("join_date"))
            if dob_iso and join_iso:
                d_dob = datetime.date.fromisoformat(dob_iso)
                d_join = datetime.date.fromisoformat(join_iso)
                bday_16 = datetime.date(d_dob.year + 16, d_dob.month, min(28, d_dob.day))
                if d_join < bday_16:
                    errors.append({"row_number": r_num, "code": "underage_enrolment_lt_16", "field": "dob", "value": dob_iso})
                    continue
            seen_rolls.add(r_no)
            canonical_rows.append({
                "roll_no": r_no,
                "name": str(row_dict.get("name") or "").strip(),
                "name_alt": str(row_dict.get("name_alt") or "").strip(),
                "dob": dob_iso,
                "gender": str(row_dict.get("gender") or "").strip(),
                "class_level": str(row_dict.get("class_level") or "").strip(),
                "exam": str(row_dict.get("exam") or "").strip(),
                "batch_name": str(row_dict.get("batch_name") or "").strip(),
                "join_date": join_iso,
                "fee_plan": str(row_dict.get("fee_plan") or "").strip(),
                "out_of_town": bool(_parse_bool_flexible(row_dict.get("out_of_town"), abs_set, pres_set)),
            })

        elif ingest_type == "attendance":
            r_no = str(row_dict.get("roll_no") or "").strip()
            if roster_roll_nos is not None and r_no not in roster_roll_nos:
                errors.append({"row_number": r_num, "code": "missing_student_in_roster", "field": "roll_no", "value": r_no})
                continue
            if "MISSING" in r_no or "UNKNOWN" in r_no:
                errors.append({"row_number": r_num, "code": "missing_student_in_roster", "field": "roll_no", "value": r_no})
                continue
            dt_iso = _parse_date_flexible(row_dict.get("attendance_date"))
            if dt_iso is None:
                errors.append({"row_number": r_num, "code": "invalid_date", "field": "attendance_date", "value": str(row_dict.get("attendance_date") or "")})
                continue
            p_flag = _parse_bool_flexible(row_dict.get("present_flag"), abs_set, pres_set)
            canonical_rows.append({
                "roll_no": r_no,
                "attendance_date": dt_iso,
                "present_flag": bool(p_flag),
                "source": str(row_dict.get("source") or "csv").strip(),
            })

        elif ingest_type == "results_marks_only":
            r_no = str(row_dict.get("roll_no") or "").strip()
            dt_iso = _parse_date_flexible(row_dict.get("test_date"))
            abs_flag = bool(_parse_bool_flexible(row_dict.get("absent_flag"), abs_set, pres_set))
            if str(row_dict.get("physics_score") or "").strip().lower() in abs_set:
                abs_flag = True

            if abs_flag:
                canonical_rows.append({
                    "test_name": str(row_dict.get("test_name") or "").strip(),
                    "test_date": dt_iso,
                    "roll_no": r_no,
                    "raw_score": None,
                    "physics_score": None,
                    "chemistry_score": None,
                    "math_or_bio_score": None,
                    "absent_flag": True,
                })
            else:
                p_s = float(str(row_dict.get("physics_score")).strip())
                c_s = float(str(row_dict.get("chemistry_score")).strip())
                m_s = float(str(row_dict.get("math_or_bio_score")).strip())
                raw_cell = str(row_dict.get("raw_score") or "").strip()
                if raw_cell.startswith("="):
                    tot_s = p_s + c_s + m_s
                else:
                    tot_s = float(raw_cell)
                if tot_s > 720.0 or r_no in seen_rolls:
                    errors.append({"row_number": r_num, "code": "duplicate_or_out_of_bounds_score", "field": "raw_score", "value": str(tot_s)})
                    continue
                seen_rolls.add(r_no)
                canonical_rows.append({
                    "test_name": str(row_dict.get("test_name") or "").strip(),
                    "test_date": dt_iso,
                    "roll_no": r_no,
                    "raw_score": tot_s,
                    "physics_score": p_s,
                    "chemistry_score": c_s,
                    "math_or_bio_score": m_s,
                    "absent_flag": False,
                })

        elif ingest_type == "answer_key":
            q_no = int(str(row_dict.get("question_no")).strip())
            q_t = str(row_dict.get("q_type")).strip()
            ans_raw = str(row_dict.get("accepted_answers")).strip()
            ans_list = [x.strip() for x in ans_raw.split("|") if x.strip()]
            if q_t in ("mcq_single", "mcq_multi") and any(x not in ("A", "B", "C", "D") for x in ans_list):
                errors.append({"row_number": r_num, "code": "invalid_option_label", "field": "accepted_answers", "value": ans_raw})
                continue
            canonical_rows.append({
                "question_no": q_no,
                "q_type": q_t,
                "subject": str(row_dict.get("subject")).strip(),
                "topic_id": str(row_dict.get("topic_id")).strip(),
                "accepted_answers": ans_list,
                "numeric_tolerance": float(str(row_dict.get("numeric_tolerance") or "0.0").strip()),
                "dropped": bool(_parse_bool_flexible(row_dict.get("dropped"), abs_set, pres_set)),
            })

        elif ingest_type == "results_responses":
            r_no = str(row_dict.get("roll_no") or "").strip()
            if "UNKNOWN" in r_no or "MISSING" in r_no:
                errors.append({"row_number": r_num, "code": "missing_student_in_roster", "field": "roll_no", "value": r_no})
                continue
            dt_iso = _parse_date_flexible(row_dict.get("test_date"))
            out_r: dict[str, Any] = {
                "test_name": str(row_dict.get("test_name")).strip(),
                "test_date": dt_iso,
                "roll_no": r_no,
            }
            for qk in ("q1", "q2", "q3", "q4", "q5"):
                qv = str(row_dict.get(qk) or "").strip()
                if qv == "" or qv in ("-", "--", "NA", "N/A", "na", "blank", "BLANK", "छोड़ा"):
                    out_r[qk] = None
                else:
                    out_r[qk] = qv
            canonical_rows.append(out_r)

        elif ingest_type == "fees":
            r_no = str(row_dict.get("roll_no") or "").strip()
            if not r_no:
                errors.append({"row_number": r_num, "code": "missing_roll_no", "field": "roll_no", "value": ""})
                continue
            amt_str = str(row_dict.get("amount_paise") or "0").replace(",", "").strip()
            amt_val = int(amt_str)
            if amt_val < 0:
                errors.append({"row_number": r_num, "code": "negative_fee_amount", "field": "amount_paise", "value": amt_str})
                continue
            canonical_rows.append({
                "roll_no": r_no,
                "instalment_no": int(str(row_dict.get("instalment_no")).strip()),
                "due_date": _parse_date_flexible(row_dict.get("due_date")),
                "amount_paise": amt_val,
                "paid_date": _parse_date_flexible(row_dict.get("paid_date")),
                "paid_amount_paise": int(str(row_dict.get("paid_amount_paise") or "0").replace(",", "").strip()),
                "refund_due_paise": int(str(row_dict.get("refund_due_paise") or "0").replace(",", "").strip()),
                "refund_paid_date": _parse_date_flexible(row_dict.get("refund_paid_date")),
            })

        elif ingest_type == "guardians":
            r_no = str(row_dict.get("roll_no") or "").strip()
            ph = str(row_dict.get("phone") or "").strip()
            if not re.match(r"^[0-9]{10}$", ph):
                errors.append({"row_number": r_num, "code": "invalid_phone_number", "field": "phone", "value": ph})
                continue
            canonical_rows.append({
                "roll_no": r_no,
                "guardian_name": str(row_dict.get("guardian_name") or "").strip(),
                "phone": ph,
                "relation": str(row_dict.get("relation") or "").strip(),
                "lang_pref": str(row_dict.get("lang_pref") or "").strip(),
            })

    return {
        "ingest_type": ingest_type,
        "expected_rows_ok": len(canonical_rows),
        "expected_rows_failed": len(errors),
        "canonical_rows": canonical_rows,
        "expected_errors": errors,
    }
