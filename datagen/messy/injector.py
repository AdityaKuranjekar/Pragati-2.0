"""Messy-data injector (`datagen/messy/`) producing realistic dirty Excel/CSV exports and golden expected JSONs."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np
import openpyxl
from openpyxl.utils import get_column_letter
import pandas as pd

from ..generator.utils import CONTRACTS_DIR, load_yaml


def generate_messy_exports(
    clean_tables: dict[str, pd.DataFrame],
    dirty_dir: Path,
    rng: np.random.Generator,
) -> list[Path]:
    """Generate >= 12 messy CSV and XLSX files across >= 3 institutes with golden `expected/<file>.json`."""
    dirty_dir.mkdir(parents=True, exist_ok=True)
    expected_dir = dirty_dir / "expected"
    expected_dir.mkdir(parents=True, exist_ok=True)

    synonyms_doc = load_yaml(CONTRACTS_DIR / "csv_templates" / "header_synonyms.yaml")
    col_syn = synonyms_doc["column_synonyms"]
    absent_markers = synonyms_doc["absent_markers"]
    present_markers = synonyms_doc["present_markers"]

    institutes_df = clean_tables["institutes"]
    students_df = clean_tables["students"]
    batches_df = clean_tables["batches"]
    guardians_df = clean_tables["guardians"]
    attendance_df = clean_tables["attendance"]
    fees_df = clean_tables["fees"]
    tests_df = clean_tables["tests"]
    test_totals_df = clean_tables["test_totals"]

    inst_ids = institutes_df["id"].tolist()
    # Ensure we span >= 3 institutes (if preset == tiny with 1 institute, cycle over its ID and synthetic sub-labels)
    inst_pool = [inst_ids[i % len(inst_ids)] for i in range(4)]
    batch_name_map = dict(zip(batches_df["id"], batches_df["name"]))
    batch_class_map = dict(zip(batches_df["id"], batches_df["class_level"]))
    batch_exam_map = dict(zip(batches_df["id"], batches_df["exam"]))

    created_files: list[Path] = []

    def _write_golden(fname: str, ingest_type: str, inst_id: str, canonical_rows: list[dict[str, Any]], errors: list[dict[str, Any]], anomalies: list[str]) -> None:
        golden_path = expected_dir / f"{fname}.json"
        payload = {
            "file_name": fname,
            "institute_id": inst_id,
            "ingest_type": ingest_type,
            "anomalies_injected": anomalies,
            "expected_rows_ok": len(canonical_rows),
            "expected_rows_failed": len(errors),
            "canonical_rows": canonical_rows,
            "expected_errors": errors,
        }
        with open(golden_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)

    # Helper to grab sample students for an institute
    def _sample_students(inst_id: str, n: int = 12) -> pd.DataFrame:
        sub = students_df[students_df["institute_id"] == inst_id]
        if len(sub) == 0:
            sub = students_df
        return sub.head(n).reset_index(drop=True)

    # -----------------------------------------------------------------------
    # File 1: patna_students_row3_merged.xlsx
    # Anomalies: Title banner in row 1 (merged A1:K1), blank row 2, headers in row 3 using Hindi/Hinglish synonyms,
    # DD/MM/YYYY dates, Devanagari names, 1 duplicate roll_no row, 1 under-age (<16) student row error.
    # -----------------------------------------------------------------------
    f1_name = "01_patna_students_row3_merged.xlsx"
    f1_path = dirty_dir / f1_name
    inst_0 = inst_pool[0]
    s_sub = _sample_students(inst_0, 10)

    wb1 = openpyxl.Workbook()
    ws1 = wb1.active
    ws1.title = "Admission_Register_2026"
    ws1.merge_cells("A1:K1")
    ws1["A1"] = "PATNA COACHING CENTRE — ADMISSION REGISTER (SESSION 2026-27)"
    # Row 2 blank
    headers_f1 = [
        col_syn["roll_no"][0],       # "Roll No."
        col_syn["name"][4],          # "Bacche Ka Naam"
        col_syn["name_alt"][4],      # "हिंदी नाम"
        col_syn["dob"][5],           # "जन्म तिथि"
        col_syn["gender"][2],        # "M/F"
        col_syn["class_level"][4],   # "Kaksha"
        col_syn["exam"][4],          # "JEE/NEET"
        col_syn["batch_name"][0],    # "Batch"
        col_syn["join_date"][4],     # "DOJ"
        col_syn["fee_plan"][4],      # "Kist Plan"
        col_syn["out_of_town"][1],   # "Hosteller"
    ]
    ws1.append([])  # row 2
    ws1.append(headers_f1)  # row 3

    f1_canon: list[dict[str, Any]] = []
    f1_errors: list[dict[str, Any]] = []

    for idx, r in s_sub.iterrows():
        dob_str = r["dob"].strftime("%d/%m/%Y")  # DD/MM/YYYY format
        join_str = r["join_date"].strftime("%d/%m/%Y")
        b_name = batch_name_map.get(r["batch_id"], "JEE-11-A")
        b_cls = batch_class_map.get(r["batch_id"], "class_11")
        b_exm = batch_exam_map.get(r["batch_id"], "jee_main")
        ws1.append([
            r["roll_no"],
            r["name"],
            r["name_alt"] or "",
            dob_str,
            r["gender"],
            b_cls,
            b_exm,
            b_name,
            join_str,
            r["fee_plan"],
            "Yes" if r["out_of_town"] else "No",
        ])
        f1_canon.append({
            "roll_no": str(r["roll_no"]),
            "name": str(r["name"]),
            "name_alt": str(r["name_alt"] or ""),
            "dob": r["dob"].isoformat(),
            "gender": str(r["gender"]),
            "class_level": str(b_cls),
            "exam": str(b_exm),
            "batch_name": b_name,
            "join_date": r["join_date"].isoformat(),
            "fee_plan": str(r["fee_plan"]),
            "out_of_town": bool(r["out_of_town"]),
        })

    # Inject duplicate roll_no row (row 14)
    dup_r = s_sub.iloc[0]
    ws1.append([
        dup_r["roll_no"], dup_r["name"], dup_r["name_alt"] or "",
        dup_r["dob"].strftime("%d/%m/%Y"), dup_r["gender"], batch_class_map.get(dup_r["batch_id"], "class_11"),
        batch_exam_map.get(dup_r["batch_id"], "jee_main"), batch_name_map.get(dup_r["batch_id"], "JEE-11-A"),
        dup_r["join_date"].strftime("%d/%m/%Y"), dup_r["fee_plan"], "No",
    ])
    f1_errors.append({"row_number": 14, "code": "duplicate_roll_no", "field": "roll_no", "value": str(dup_r["roll_no"])})

    # Inject underage student (< 16 at join_date, MoE 2024 warning/error, row 15)
    ws1.append([
        "PAT26-9999", "Chotu Synth", "छोटू सिंथ",
        "10/08/2012", "male", "class_11", "jee_main", "JEE-11-A",
        "15/04/2026", "standard_3_instalment", "No",
    ])
    f1_errors.append({"row_number": 15, "code": "underage_enrolment_lt_16", "field": "dob", "value": "2012-08-10"})

    wb1.save(f1_path)
    _write_golden(f1_name, "students", inst_0, f1_canon, f1_errors, ["header_in_row_3", "merged_cells", "dd_mm_yyyy_dates", "duplicate_roll_no", "underage_lt_16", "devanagari_headers"])
    created_files.append(f1_path)

    # -----------------------------------------------------------------------
    # File 2: 02_lucknow_attendance_markers_mix.csv
    # Anomalies: Comment banner rows, Devanagari + Hinglish headers, mixed absent/present markers
    # (AB, A, -, अनुपस्थित, P, 1, उपस्थित, blank), DD-MM-YYYY and MM/DD/YYYY mixed dates, unknown roll_no row.
    # -----------------------------------------------------------------------
    f2_name = "02_lucknow_attendance_markers_mix.csv"
    f2_path = dirty_dir / f2_name
    inst_1 = inst_pool[1]
    s_sub2 = _sample_students(inst_1, 10)

    f2_canon: list[dict[str, Any]] = []
    f2_errors: list[dict[str, Any]] = []
    f2_rows: list[list[str]] = [
        ["# Lucknow NEET Academy Daily Attendance Export", "", "", ""],
        ["", "", "", ""],
        [col_syn["roll_no"][7], col_syn["attendance_date"][4], col_syn["present_flag"][4], col_syn["source"][4]],  # रोल नंबर, Tarikh, Haziri, Madhyam
    ]
    for idx, r in s_sub2.iterrows():
        is_pres = (idx % 3 != 0)
        marker = present_markers[idx % len(present_markers)] if is_pres else absent_markers[idx % len(absent_markers)]
        date_str = "04/05/2026" if idx % 2 == 0 else "2026-05-04"  # 4 May 2026
        f2_rows.append([str(r["roll_no"]), date_str, marker, "csv"])
        f2_canon.append({
            "roll_no": str(r["roll_no"]),
            "attendance_date": "2026-05-04",
            "present_flag": bool(is_pres),
            "source": "csv",
        })
    # Blank present_flag row -> treated as error or missing
    f2_rows.append(["LUC99-MISSING", "04/05/2026", "", "csv"])
    f2_errors.append({"row_number": 14, "code": "missing_student_in_roster", "field": "roll_no", "value": "LUC99-MISSING"})

    with open(f2_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(f2_rows)
    _write_golden(f2_name, "attendance", inst_1, f2_canon, f2_errors, ["header_in_row_3", "absent_present_marker_mix", "devanagari_markers", "missing_roster_student"])
    created_files.append(f2_path)

    # -----------------------------------------------------------------------
    # File 3: 03_kota_results_formulas_and_totals.xlsx
    # Anomalies: Multiple sheets (first sheet is "Instructions", second sheet is "Marks_Sheet"),
    # hidden row, Excel =SUM(D4:F4) formulas for raw_score, trailing "Batch Average / Grand Total" row,
    # numbers stored as text, absent student with 'AB'.
    # -----------------------------------------------------------------------
    f3_name = "03_kota_results_formulas_and_totals.xlsx"
    f3_path = dirty_dir / f3_name
    inst_3 = inst_pool[3]
    s_sub3 = _sample_students(inst_3, 10)

    wb3 = openpyxl.Workbook()
    ws_inst = wb3.active
    ws_inst.title = "Readme_Cover"
    ws_inst["A1"] = "Please see sheet 2 (Marks_Sheet) for test results."

    ws3 = wb3.create_sheet("Marks_Sheet")
    ws3.merge_cells("A1:H1")
    ws3["A1"] = "KOTA LARGE JEE — FORTNIGHTLY TEST 01 MARKS"
    ws3.append([])  # row 2 blank
    ws3.append([
        col_syn["test_name"][0],
        col_syn["test_date"][0],
        col_syn["roll_no"][2],        # R.No
        col_syn["physics_score"][1],  # Phy Marks
        col_syn["chemistry_score"][1],# Chem Marks
        col_syn["math_or_bio_score"][1], # Maths Marks
        col_syn["raw_score"][0],      # Total Marks (Formula!)
        col_syn["absent_flag"][0],    # Absent?
    ])

    f3_canon: list[dict[str, Any]] = []
    f3_errors: list[dict[str, Any]] = []

    for idx, r in s_sub3.iterrows():
        excel_row = idx + 4
        if idx == 8:
            # Absent student with 'AB' in score columns
            ws3.append(["FT-01-JEE", "03/05/2026", r["roll_no"], "AB", "AB", "AB", "AB", "Yes"])
            f3_canon.append({
                "test_name": "FT-01-JEE",
                "test_date": "2026-05-03",
                "roll_no": str(r["roll_no"]),
                "raw_score": None,
                "physics_score": None,
                "chemistry_score": None,
                "math_or_bio_score": None,
                "absent_flag": True,
            })
        else:
            p_m = float(40 + idx * 3)
            c_m = float(35 + idx * 2)
            m_m = float(45 + idx * 2)
            tot_m = p_m + c_m + m_m
            # Store numbers as text strings for odd rows, and Excel formula for Total Marks
            ws3.append([
                "FT-01-JEE",
                "03/05/2026",
                r["roll_no"],
                str(int(p_m)) if idx % 2 == 1 else p_m,
                str(int(c_m)) if idx % 2 == 1 else c_m,
                str(int(m_m)) if idx % 2 == 1 else m_m,
                f"=SUM(D{excel_row}:F{excel_row})",
                "false",
            ])
            f3_canon.append({
                "test_name": "FT-01-JEE",
                "test_date": "2026-05-03",
                "roll_no": str(r["roll_no"]),
                "raw_score": tot_m,
                "physics_score": p_m,
                "chemistry_score": c_m,
                "math_or_bio_score": m_m,
                "absent_flag": False,
            })

    # Inject a hidden dummy row (row 14) and a trailing totals row (row 15)
    ws3.append(["FT-01-JEE", "03/05/2026", "HIDDEN-ROW", 0, 0, 0, 0, "false"])
    ws3.row_dimensions[14].hidden = True
    f3_errors.append({"row_number": 14, "code": "hidden_row_skipped", "field": "roll_no", "value": "HIDDEN-ROW"})

    ws3.append(["Grand Total", "", "", "=SUM(D4:D12)", "=SUM(E4:E12)", "=SUM(F4:F12)", "=SUM(G4:G12)", ""])
    f3_errors.append({"row_number": 15, "code": "trailing_totals_row", "field": "test_name", "value": "Grand Total"})

    wb3.save(f3_path)
    _write_golden(f3_name, "results_marks_only", inst_3, f3_canon, f3_errors, ["multiple_sheets", "hidden_rows", "excel_formulas", "trailing_totals_row", "numbers_as_text", "marks_only_export"])
    created_files.append(f3_path)

    # -----------------------------------------------------------------------
    # File 4: 04_gaya_marks_only_export.csv
    # Anomalies: Marks-only CSV export with Hindi headers, extra blank rows, and 1 absurd score > max_marks error.
    # -----------------------------------------------------------------------
    f4_name = "04_gaya_marks_only_export.csv"
    f4_path = dirty_dir / f4_name
    inst_2 = inst_pool[2]
    s_sub4 = _sample_students(inst_2, 8)

    f4_canon: list[dict[str, Any]] = []
    f4_errors: list[dict[str, Any]] = []
    f4_rows: list[list[str]] = [
        [
            col_syn["test_name"][5],       # टेस्ट का नाम
            col_syn["test_date"][5],       # परीक्षा तिथि
            col_syn["roll_no"][7],         # रोल नंबर
            col_syn["raw_score"][5],       # कुल अंक
            col_syn["physics_score"][5],   # भौतिकी अंक
            col_syn["chemistry_score"][5], # रसायन अंक
            col_syn["math_or_bio_score"][5], # गणित / जीव विज्ञान
            col_syn["absent_flag"][5],     # अनुपस्थिति
        ],
        ["", "", "", "", "", "", "", ""],  # Extra blank row
    ]
    for idx, r in s_sub4.iterrows():
        p_s, c_s, m_s = 50.0 + idx, 48.0 + idx, 52.0 + idx
        tot_s = p_s + c_s + m_s
        f4_rows.append(["CT-01-MIX", "2026-05-10", str(r["roll_no"]), str(tot_s), str(p_s), str(c_s), str(m_s), "false"])
        f4_canon.append({
            "test_name": "CT-01-MIX",
            "test_date": "2026-05-10",
            "roll_no": str(r["roll_no"]),
            "raw_score": tot_s,
            "physics_score": p_s,
            "chemistry_score": c_s,
            "math_or_bio_score": m_s,
            "absent_flag": False,
        })
    # Absurd score row (row 11)
    f4_rows.append(["CT-01-MIX", "2026-05-10", str(s_sub4.iloc[0]["roll_no"]), "9999.0", "400.0", "400.0", "400.0", "false"])
    f4_errors.append({"row_number": 11, "code": "duplicate_or_out_of_bounds_score", "field": "raw_score", "value": "9999.0"})

    with open(f4_path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(f4_rows)
    _write_golden(f4_name, "results_marks_only", inst_2, f4_canon, f4_errors, ["marks_only_export", "extra_blank_rows", "devanagari_headers", "out_of_bounds_score"])
    created_files.append(f4_path)

    # -----------------------------------------------------------------------
    # File 5: 05_patna_answer_key_wrong_and_bonus.csv
    # Anomalies: Contains 1 injected wrong answer key (question 4) and 1 dropped/bonus question (question 5).
    # -----------------------------------------------------------------------
    f5_name = "05_patna_answer_key_wrong_and_bonus.csv"
    f5_path = dirty_dir / f5_name
    f5_rows = [
        [
            col_syn["question_no"][1],      # Q.No.
            col_syn["q_type"][0],           # Question Type
            col_syn["subject"][4],          # Vishay
            col_syn["topic_id"][1],         # Topic Code
            col_syn["accepted_answers"][1], # Answer Key
            col_syn["numeric_tolerance"][0],# Tolerance
            col_syn["dropped"][1],          # Is Bonus
        ],
        ["1", "mcq_single", "Physics", "jee.phy.kinematics.projectile", "A", "0.0", "false"],
        ["2", "mcq_multi", "Chemistry", "jee.chem.atomic_structure.bohr_model", "A|C", "0.0", "false"],
        ["3", "numeric", "Mathematics", "jee.math.quadratic_equations.roots_nature", "42.5", "0.1", "false"],
        ["4", "mcq_single", "Physics", "jee.phy.laws_of_motion.friction", "D", "0.0", "false"],  # Wrong key (true=B)
        ["5", "mcq_single", "Chemistry", "jee.chem.chemical_bonding.vsepr_theory", "B", "0.0", "true"],  # Bonus / dropped
        ["6", "mcq_single", "Mathematics", "jee.math.circles.tangent_normal_circle", "INVALID_OPT", "0.0", "false"],
    ]
    f5_canon = [
        {"question_no": 1, "q_type": "mcq_single", "subject": "Physics", "topic_id": "jee.phy.kinematics.projectile", "accepted_answers": ["A"], "numeric_tolerance": 0.0, "dropped": False},
        {"question_no": 2, "q_type": "mcq_multi", "subject": "Chemistry", "topic_id": "jee.chem.atomic_structure.bohr_model", "accepted_answers": ["A", "C"], "numeric_tolerance": 0.0, "dropped": False},
        {"question_no": 3, "q_type": "numeric", "subject": "Mathematics", "topic_id": "jee.math.quadratic_equations.roots_nature", "accepted_answers": ["42.5"], "numeric_tolerance": 0.1, "dropped": False},
        {"question_no": 4, "q_type": "mcq_single", "subject": "Physics", "topic_id": "jee.phy.laws_of_motion.friction", "accepted_answers": ["D"], "numeric_tolerance": 0.0, "dropped": False},
        {"question_no": 5, "q_type": "mcq_single", "subject": "Chemistry", "topic_id": "jee.chem.chemical_bonding.vsepr_theory", "accepted_answers": ["B"], "numeric_tolerance": 0.0, "dropped": True},
    ]
    f5_errors = [{"row_number": 7, "code": "invalid_option_label", "field": "accepted_answers", "value": "INVALID_OPT"}]
    with open(f5_path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(f5_rows)
    _write_golden(f5_name, "answer_key", inst_0, f5_canon, f5_errors, ["wrong_answer_key", "bonus_cancelled_question", "invalid_option_error"])
    created_files.append(f5_path)

    # -----------------------------------------------------------------------
    # File 6: 06_lucknow_responses_wide_messy.csv
    # Anomalies: Wide responses with "-" and "NA" for blanks, 1 student missing from roster,
    # 1 test scheduled on Monday (day after Sunday weekly off -> schedule compliance warning).
    # -----------------------------------------------------------------------
    f6_name = "06_lucknow_responses_wide_messy.csv"
    f6_path = dirty_dir / f6_name
    s_sub6 = _sample_students(inst_1, 8)
    f6_rows = [
        [
            col_syn["test_name"][2], # Mock Test
            col_syn["test_date"][4], # Pariksha Tithi
            col_syn["roll_no"][1],   # Roll No
            col_syn["q1"][1],        # Q.1
            col_syn["q2"][2],        # Ques 2
            col_syn["q3"][4],        # प्र. 3
            col_syn["q4"][0],        # Q4
            col_syn["q5"][0],        # Q5
        ]
    ]
    f6_canon = []
    for idx, r in s_sub6.iterrows():
        q3_val = "-" if idx % 2 == 0 else "C"
        f6_rows.append(["FT-02-NEET", "04/05/2026", str(r["roll_no"]), "A", "A|C", q3_val, "B", "42.5"])
        f6_canon.append({
            "test_name": "FT-02-NEET",
            "test_date": "2026-05-04",
            "roll_no": str(r["roll_no"]),
            "q1": "A",
            "q2": "A|C",
            "q3": None if q3_val == "-" else "C",
            "q4": "B",
            "q5": "42.5",
        })
    f6_rows.append(["FT-02-NEET", "04/05/2026", "UNKNOWN-ROLL-77", "A", "B", "C", "D", "10"])
    f6_errors = [{"row_number": 10, "code": "missing_student_in_roster", "field": "roll_no", "value": "UNKNOWN-ROLL-77"}]
    with open(f6_path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(f6_rows)
    _write_golden(f6_name, "results_responses", inst_1, f6_canon, f6_errors, ["blank_markers_dash", "missing_student_in_roster", "day_after_weekly_off_test"])
    created_files.append(f6_path)

    # -----------------------------------------------------------------------
    # File 7: 07_kota_fees_negative_and_text_numbers.xlsx
    # Anomalies: Numbers stored as text with commas/spaces, negative fee amount error, trailing summary row.
    # -----------------------------------------------------------------------
    f7_name = "07_kota_fees_negative_and_text_numbers.xlsx"
    f7_path = dirty_dir / f7_name
    s_sub7 = _sample_students(inst_3, 8)
    wb7 = openpyxl.Workbook()
    ws7 = wb7.active
    ws7.title = "Fee_Ledger"
    ws7.append(["KOTA FEE REGISTER", "", "", "", "", "", "", ""])
    ws7.append(["", "", "", "", "", "", "", ""])
    ws7.append([
        col_syn["roll_no"][0],
        col_syn["instalment_no"][2],     # Kist No
        col_syn["due_date"][4],          # Jama Tarikh
        col_syn["amount_paise"][4],      # Kul Rashi
        col_syn["paid_date"][4],         # Bhugtan Tithi
        col_syn["paid_amount_paise"][3], # Jama Rashi
        col_syn["refund_due_paise"][3],  # Wapasi Rashi
        col_syn["refund_paid_date"][3],  # Wapasi Tithi
    ])
    f7_canon = []
    for idx, r in s_sub7.iterrows():
        ws7.append([
            str(r["roll_no"]),
            "1",
            "15/04/2026",
            "2500000",
            "15/04/2026",
            "2500000",
            "0",
            "",
        ])
        f7_canon.append({
            "roll_no": str(r["roll_no"]),
            "instalment_no": 1,
            "due_date": "2026-04-15",
            "amount_paise": 2500000,
            "paid_date": "2026-04-15",
            "paid_amount_paise": 2500000,
            "refund_due_paise": 0,
            "refund_paid_date": None,
        })
    # Negative fee amount error (row 12)
    ws7.append([str(s_sub7.iloc[0]["roll_no"]), "2", "15/07/2026", "-500000", "", "0", "0", ""])
    f7_errors = [{"row_number": 12, "code": "negative_fee_amount", "field": "amount_paise", "value": "-500000"}]
    wb7.save(f7_path)
    _write_golden(f7_name, "fees", inst_3, f7_canon, f7_errors, ["header_in_row_3", "numbers_as_text", "negative_fee_error"])
    created_files.append(f7_path)

    # -----------------------------------------------------------------------
    # File 8: 08_gaya_guardians_shared_phone_devanagari.csv
    # Anomalies: Shared sibling phone numbers, Devanagari headers, invalid 8-digit phone number row.
    # -----------------------------------------------------------------------
    f8_name = "08_gaya_guardians_shared_phone_devanagari.csv"
    f8_path = dirty_dir / f8_name
    s_sub8 = _sample_students(inst_2, 8)
    f8_rows = [
        [
            col_syn["roll_no"][7],       # रोल नंबर
            col_syn["guardian_name"][5], # अभिभावक का नाम
            col_syn["phone"][5],         # मोबाइल नंबर
            col_syn["relation"][4],      # संबंध
            col_syn["lang_pref"][5],     # भाषा
        ]
    ]
    f8_canon = []
    for idx, r in s_sub8.iterrows():
        ph = "9999900101" if idx < 2 else f"99999001{idx:02d}"
        f8_rows.append([str(r["roll_no"]), f"Rajesh Synth", ph, "father", "hi"])
        f8_canon.append({
            "roll_no": str(r["roll_no"]),
            "guardian_name": "Rajesh Synth",
            "phone": ph,
            "relation": "father",
            "lang_pref": "hi",
        })
    f8_rows.append([str(s_sub8.iloc[0]["roll_no"]), "Bad Phone Parent", "12345", "father", "hi"])
    f8_errors = [{"row_number": 10, "code": "invalid_phone_number", "field": "phone", "value": "12345"}]
    with open(f8_path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(f8_rows)
    _write_golden(f8_name, "guardians", inst_2, f8_canon, f8_errors, ["shared_sibling_phone", "devanagari_headers", "invalid_phone_error"])
    created_files.append(f8_path)

    # -----------------------------------------------------------------------
    # File 9: 09_patna_reused_roll_numbers_across_years.csv
    # Anomalies: Reused roll_no PAT-R001 duplicated in the same upload file + MM/DD/YYYY vs DD/MM/YYYY date mix.
    # -----------------------------------------------------------------------
    f9_name = "09_patna_reused_roll_numbers_across_years.csv"
    f9_path = dirty_dir / f9_name
    s_sub9 = _sample_students(inst_0, 6)
    f9_rows = [
        [
            col_syn["roll_no"][3],     # Roll Number
            col_syn["name"][0],        # Student Name
            col_syn["name_alt"][0],    # Hindi Name
            col_syn["dob"][1],         # DOB
            col_syn["gender"][0],      # Gender
            col_syn["class_level"][0], # Class
            col_syn["exam"][0],        # Target Exam
            col_syn["batch_name"][1],  # Batch Name
            col_syn["join_date"][0],   # Admission Date
            col_syn["fee_plan"][0],    # Fee Plan
            col_syn["out_of_town"][0], # Outstation
        ]
    ]
    f9_canon = []
    for idx, r in s_sub9.iterrows():
        b_name = batch_name_map.get(r["batch_id"], "JEE-11-A")
        b_cls = batch_class_map.get(r["batch_id"], "class_11")
        b_exm = batch_exam_map.get(r["batch_id"], "jee_main")
        f9_rows.append([
            str(r["roll_no"]), str(r["name"]), str(r["name_alt"] or ""),
            r["dob"].strftime("%d-%m-%Y"), str(r["gender"]), str(b_cls),
            str(b_exm), b_name, r["join_date"].strftime("%d-%m-%Y"),
            str(r["fee_plan"]), "true" if r["out_of_town"] else "false",
        ])
        f9_canon.append({
            "roll_no": str(r["roll_no"]),
            "name": str(r["name"]),
            "name_alt": str(r["name_alt"] or ""),
            "dob": r["dob"].isoformat(),
            "gender": str(r["gender"]),
            "class_level": str(b_cls),
            "exam": str(b_exm),
            "batch_name": b_name,
            "join_date": r["join_date"].isoformat(),
            "fee_plan": str(r["fee_plan"]),
            "out_of_town": bool(r["out_of_town"]),
        })
    # Reused roll_no collision within file
    r0 = s_sub9.iloc[0]
    f9_rows.append([
        str(r0["roll_no"]), "Collision Student Synth", "टकराव सिंथ",
        "14-05-2008", "male", "class_12", "jee_main", "JEE-12-A",
        "15-04-2026", "upfront_full", "false",
    ])
    f9_errors = [{"row_number": 8, "code": "duplicate_roll_no", "field": "roll_no", "value": str(r0["roll_no"])}]
    with open(f9_path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(f9_rows)
    _write_golden(f9_name, "students", inst_0, f9_canon, f9_errors, ["reused_roll_no_collision", "dd_mm_yyyy_dash_dates"])
    created_files.append(f9_path)

    # -----------------------------------------------------------------------
    # File 10: 10_lucknow_attendance_absurd_date.xlsx
    # Anomalies: Merged title cells, header in row 3, 0/1 numeric attendance flags, invalid date "32/13/2026".
    # -----------------------------------------------------------------------
    f10_name = "10_lucknow_attendance_absurd_date.xlsx"
    f10_path = dirty_dir / f10_name
    wb10 = openpyxl.Workbook()
    ws10 = wb10.active
    ws10.title = "May_Attendance"
    ws10.merge_cells("A1:D1")
    ws10["A1"] = "LUCKNOW BIOMETRIC EXPORT"
    ws10.append([])
    ws10.append([col_syn["roll_no"][4], col_syn["attendance_date"][0], col_syn["present_flag"][2], col_syn["source"][2]])
    f10_canon = []
    for idx, r in s_sub2.head(6).iterrows():
        flag_str = "1" if idx % 2 == 0 else "AB"
        ws10.append([str(r["roll_no"]), "06/05/2026", flag_str, "biometric"])
        f10_canon.append({
            "roll_no": str(r["roll_no"]),
            "attendance_date": "2026-05-06",
            "present_flag": (idx % 2 == 0),
            "source": "biometric",
        })
    ws10.append([str(s_sub2.iloc[0]["roll_no"]), "32/13/2026", "1", "biometric"])
    f10_errors = [{"row_number": 10, "code": "invalid_date", "field": "attendance_date", "value": "32/13/2026"}]
    wb10.save(f10_path)
    _write_golden(f10_name, "attendance", inst_1, f10_canon, f10_errors, ["header_in_row_3", "merged_cells", "invalid_date_error"])
    created_files.append(f10_path)

    # -----------------------------------------------------------------------
    # File 11: 11_kota_responses_multi_sheet_and_extra_blanks.xlsx
    # Anomalies: Two sheets ("Summary_Ignore", "Responses_Data"), extra blank rows in middle, trailing total row.
    # -----------------------------------------------------------------------
    f11_name = "11_kota_responses_multi_sheet_and_extra_blanks.xlsx"
    f11_path = dirty_dir / f11_name
    wb11 = openpyxl.Workbook()
    ws11_cov = wb11.active
    ws11_cov.title = "Summary_Ignore"
    ws11_cov["A1"] = "Ignore this summary tab"
    ws11 = wb11.create_sheet("Responses_Data")
    ws11.append([
        col_syn["test_name"][0], col_syn["test_date"][0], col_syn["roll_no"][0],
        col_syn["q1"][0], col_syn["q2"][0], col_syn["q3"][0], col_syn["q4"][0], col_syn["q5"][0],
    ])
    f11_canon = []
    for idx, r in s_sub3.head(6).iterrows():
        if idx == 3:
            ws11.append(["", "", "", "", "", "", "", ""])  # blank separator row
        ws11.append(["FT-03-JEE", "17/05/2026", str(r["roll_no"]), "B", "D", "--", "A", "12"])
        f11_canon.append({
            "test_name": "FT-03-JEE",
            "test_date": "2026-05-17",
            "roll_no": str(r["roll_no"]),
            "q1": "B",
            "q2": "D",
            "q3": None,
            "q4": "A",
            "q5": "12",
        })
    ws11.append(["Total Attempted", "", "6", "6", "6", "0", "6", "6"])
    f11_errors = [{"row_number": 9, "code": "trailing_totals_row", "field": "test_name", "value": "Total Attempted"}]
    wb11.save(f11_path)
    _write_golden(f11_name, "results_responses", inst_3, f11_canon, f11_errors, ["multiple_sheets", "extra_blank_rows", "trailing_totals_row"])
    created_files.append(f11_path)

    # -----------------------------------------------------------------------
    # File 12: 12_gaya_fees_pro_rata_refund_and_missing_roll.csv
    # Anomalies: Pro-rata refund rows, Hinglish headers, 1 row with missing roll_no.
    # -----------------------------------------------------------------------
    f12_name = "12_gaya_fees_pro_rata_refund_and_missing_roll.csv"
    f12_path = dirty_dir / f12_name
    f12_rows = [
        [
            col_syn["roll_no"][5],           # Enrolment ID
            col_syn["instalment_no"][1],     # Installment #
            col_syn["due_date"][1],          # Instalment Date
            col_syn["amount_paise"][1],      # Due Amount
            col_syn["paid_date"][1],         # Receipt Date
            col_syn["paid_amount_paise"][1], # Amount Received
            col_syn["refund_due_paise"][1],  # Pro-Rata Refund
            col_syn["refund_paid_date"][1],  # Refund Paid On
        ]
    ]
    f12_canon = []
    for idx, r in s_sub4.head(6).iterrows():
        ref_paise = 400000 if idx == 5 else 0
        ref_date = "2026-08-20" if idx == 5 else ""
        f12_rows.append([
            str(r["roll_no"]), "1", "2026-04-15", "2000000", "2026-04-15", "2000000", str(ref_paise), ref_date
        ])
        f12_canon.append({
            "roll_no": str(r["roll_no"]),
            "instalment_no": 1,
            "due_date": "2026-04-15",
            "amount_paise": 2000000,
            "paid_date": "2026-04-15",
            "paid_amount_paise": 2000000,
            "refund_due_paise": ref_paise,
            "refund_paid_date": ref_date if ref_date else None,
        })
    f12_rows.append(["", "1", "2026-04-15", "2000000", "2026-04-15", "2000000", "0", ""])
    f12_errors = [{"row_number": 8, "code": "missing_roll_no", "field": "roll_no", "value": ""}]
    with open(f12_path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(f12_rows)
    _write_golden(f12_name, "fees", inst_2, f12_canon, f12_errors, ["pro_rata_refund_row", "missing_roll_no_error", "hinglish_headers"])
    created_files.append(f12_path)

    return created_files
