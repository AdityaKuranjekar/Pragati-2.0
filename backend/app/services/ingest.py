"""Upload -> mapping preview + row errors -> commit -> batch recompute. Idempotent per (institute, file hash, options)."""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from pathlib import Path

import pandas as pd
import psycopg2.extras

from .. import config
from . import analytics, ingest_parse as ip, scoring
ref = ip.ref
from .analytics import qdf

CACHE_DIR = Path(config.PG_DATA_DIR).parent / ".ingest_cache"
MAX_FILE_BYTES = 25 * 1024 * 1024


class IngestError(Exception):
    def __init__(self, status: int, message: str, extra: dict | None = None):
        self.status, self.message, self.extra = status, message, extra or {}


def _payload_path(job_id: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{job_id}.json"


# ---------------------------------------------------------------- tenant lookups
def _rc(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def roster(conn) -> dict[str, dict]:
    """roll_no -> student (latest academic year wins when a roll number is reused across years)."""
    with _rc(conn) as cur:
        cur.execute("SELECT s.id::text, s.roll_no, s.batch_id::text, s.dob, s.academic_year, b.exam, b.name AS batch_name "
                    "FROM students s JOIN batches b ON b.id=s.batch_id ORDER BY s.academic_year")
        return {r["roll_no"]: dict(r) for r in cur.fetchall()}


def batch_lookup(conn) -> dict[str, dict]:
    with _rc(conn) as cur:
        cur.execute("SELECT id::text, name, exam, class_level, academic_year FROM batches ORDER BY academic_year")
        out = {}
        for r in cur.fetchall():
            out[r["name"].strip().lower()] = dict(r)
        return out


def weekly_off(conn) -> str:
    with _rc(conn) as cur:
        cur.execute("SELECT weekly_off_day FROM institutes LIMIT 1")
        return cur.fetchone()["weekly_off_day"]


def _tests_by_batch_name(conn) -> dict[tuple[str, str], list[dict]]:
    with _rc(conn) as cur:
        cur.execute("SELECT id::text, batch_id::text, name, test_date, max_marks FROM tests")
        out: dict = {}
        for r in cur.fetchall():
            out.setdefault((r["batch_id"], r["name"].strip().lower()), []).append(dict(r))
        return out


def _find_test(tests, batch_id, name, date):
    cands = tests.get((batch_id, str(name).strip().lower()), [])
    if date:
        m = [t for t in cands if str(t["test_date"]) == date]
        if m:
            return m[0]
    return cands[0] if cands else None


def _scheme_default(exam: str) -> tuple[str, float]:
    return ("neet_ug", 720.0) if exam == "neet_ug" else ("jee_main", 300.0)


# ---------------------------------------------------------------- preview
def preview(conn, institute_id: str, user_id: str, kind: str, filename: str, data: bytes, params: dict) -> dict:
    if len(data) > MAX_FILE_BYTES:
        raise IngestError(413, "file larger than 25 MB")
    if not data:
        raise IngestError(422, "empty file")
    opts = {k: v for k, v in sorted(params.items()) if v not in (None, "")}
    file_hash = hashlib.sha256(data + b"|" + kind.encode() + b"|" + json.dumps(opts, sort_keys=True).encode()).hexdigest()
    with _rc(conn) as cur:
        cur.execute("SELECT id::text, status FROM ingest_jobs WHERE file_hash=%s", (file_hash,))
        dup = cur.fetchone()
    if dup and _payload_path(dup["id"]).exists():
        out = get_job(conn, dup["id"])
        out["duplicate"] = True
        out["message"] = ("this exact file was already uploaded and committed; nothing was written again" if dup["status"] == "confirmed"
                          else "this exact file was already uploaded; returning the existing preview")
        return out

    try:
        itype, rows, errors, warnings, resolved, status, mapping = _analyze(conn, kind, filename, data, params)
    except IngestError:
        raise
    job_id = str(uuid.uuid4())
    payload = {"rows": rows, "resolved": resolved, "params": opts, "ingest_type": itype, "filename": filename, "kind": kind, "warnings": warnings}
    _payload_path(job_id).write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
    _payload_path(job_id).with_suffix(".bin").write_bytes(data)
    db_type = ip.DB_TYPE.get(itype, itype)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO ingest_jobs (id, institute_id, file_hash, type, status, mapping, errors, rows_ok, rows_failed) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (job_id, institute_id, file_hash, db_type, status, json.dumps(mapping), json.dumps(errors[:2000]), len(rows), len(errors)))
    return _job_view(job_id, status, itype, filename, mapping, errors, warnings, rows, resolved, params, committed=False, kind=kind)


def _analyze(conn, kind, filename, data, params):
    override = json.loads(params["mapping"]) if params.get("mapping") else None
    hint = float(params["max_marks"]) if params.get("max_marks") else None
    try:
        parsed = ip.parse(data, filename, override, hint, kind)
    except ip.ParseError as ex:
        raise IngestError(422, str(ex))
    except Exception as ex:  # corrupted xlsx, binary junk
        raise IngestError(422, f"could not read the file: {type(ex).__name__}: {str(ex)[:120]}")
    itype = parsed["ingest_type"]
    if itype not in ip.KIND_TO_TYPES[kind]:
        raise IngestError(422, f"this file looks like '{itype}' data, not '{kind}'; use the matching upload", {"detected_type": itype})
    errors, warnings = list(parsed["errors"]), []
    rows = parsed["canonical_rows"]
    resolved: dict = {}
    status = "preview_ready"
    if parsed["missing_required"]:
        status = "pending_mapping"
        warnings.append({"code": "missing_required_columns", "message": "pick the columns manually: missing " + ", ".join(parsed["missing_required"]),
                         "columns": parsed["missing_required"]})
    else:
        rows, errors, warnings, resolved = _validate(conn, itype, rows, errors, warnings, params)
    mapping = {"detected": parsed["mapping"], "unmapped": parsed["unmapped_columns"], "missing_required": parsed["missing_required"],
               "header_row": parsed["header_row"], "question_columns": len(parsed["question_columns"])}
    return itype, rows, errors, warnings, resolved, status, mapping


def remap(conn, job_id: str, mapping_in: dict) -> dict:
    """Re-run parsing and validation of the stored file with the user's column choices."""
    with _rc(conn) as cur:
        cur.execute("SELECT status FROM ingest_jobs WHERE id=%s FOR UPDATE", (job_id,))
        j = cur.fetchone()
    if not j:
        raise IngestError(404, "job not found")
    if j["status"] == "confirmed":
        raise IngestError(409, "this job was already committed")
    pp = _payload_path(job_id)
    if not pp.exists() or not pp.with_suffix(".bin").exists():
        raise IngestError(410, "the uploaded file is no longer cached; upload it again")
    old = json.loads(pp.read_text(encoding="utf-8"))
    params = dict(old["params"])
    params["mapping"] = json.dumps({k: v for k, v in mapping_in.items() if v})
    itype, rows, errors, warnings, resolved, status, mapping = _analyze(conn, old["kind"], old["filename"], pp.with_suffix(".bin").read_bytes(), params)
    payload = {**old, "rows": rows, "resolved": resolved, "params": params, "ingest_type": itype, "warnings": warnings}
    pp.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute("UPDATE ingest_jobs SET status=%s, mapping=%s, errors=%s, rows_ok=%s, rows_failed=%s, type=%s WHERE id=%s",
                    (status, json.dumps(mapping), json.dumps(errors[:2000]), len(rows), len(errors), ip.DB_TYPE.get(itype, itype), job_id))
    return _job_view(job_id, status, itype, old["filename"], mapping, errors, warnings, rows, resolved, params, committed=False, kind=old["kind"])


def _job_view(job_id, status, itype, filename, mapping, errors, warnings, rows, resolved, params, committed, result=None, kind=None):
    base = {"job_id": job_id, "status": status, "ingest_type": itype, "filename": filename, "mapping": mapping,
            "rows_ok": len(rows), "rows_failed": len(errors),
            "errors": [{**e, "message": e.get("message") or _MSG.get(e["code"], e["code"])} for e in errors[:500]],
            "errors_truncated": max(0, len(errors) - 500), "warnings": warnings,
            "preview_rows": [{k: v for k, v in r.items() if k != "_row"} for r in rows[:15]],
            "target": resolved.get("target"), "committed": committed, "duplicate": False, "result": result,
            "can_commit": status == "preview_ready" and len(rows) > 0}
    return {**base, **_contract(base, status, itype, kind, mapping, errors, warnings, rows)}


_WARN_CODES = {"hidden_row_skipped", "trailing_totals_row"}
_STATE: dict[str, dict] = {}


def _targets(itype: str, mapping: dict) -> list[dict]:
    cols = list(ref.CANONICAL_EXPECTED_COLS.get({"results_long": "results_marks_only"}.get(itype, itype), []))
    if itype == "results_responses":
        cols = ["test_name", "test_date", "roll_no"] + [f"q{i}" for i in range(1, max(mapping.get("question_columns", 5), 1) + 1)]
    if itype == "results_long":
        cols = ["test_name", "test_date", "roll_no", "question_no", "response"]
    req = set(ip.REQUIRED.get(itype, []))
    return [{"id": c, "required": c in req, "label_en": c.replace("_", " "), "label_hi": c.replace("_", " ")} for c in cols]


def _contract(base, status, itype, kind, mapping, errors, warnings, rows):
    from . import ingest_parse as _ip  # noqa: F401

    cstatus = {"confirmed": "done", "failed": "failed"}.get(status, "preview")
    detected = mapping.get("detected", [])
    cols = [{"source": d["column"], "target": d["canonical"], "confidence": d["confidence"], "alternatives": []} for d in detected]
    cols += [{"source": u, "target": None, "confidence": 0.0, "alternatives": []} for u in mapping.get("unmapped", [])]
    c2s = {d["canonical"]: d["column"] for d in detected}
    samples = [{c2s.get(k, k): ("" if v is None else str(v)) for k, v in r.items() if not k.startswith("_")} for r in rows[:8]]
    cerrors = [{"row_number": int(e.get("row_number") or 0), "field": str(e.get("field") or ""), "message": e.get("message") or _MSG.get(e["code"], e["code"]),
                "row": int(e.get("row_number") or 0), "column": str(e.get("field") or ""), "code": e["code"],
                "severity": "warning" if e["code"] in _WARN_CODES else "error", "value": str(e.get("value", "")),
                "message_en": e.get("message") or _MSG.get(e["code"], e["code"]), "message_hi": e.get("message") or _MSG.get(e["code"], e["code"])}
               for e in errors[:500]]
    cerrors += [{"row_number": 0, "field": "", "message": w["message"], "row": 0, "column": "", "code": w["code"], "severity": "warning", "value": "", "message_en": w["message"], "message_hi": w["message"]} for w in warnings]
    n_err = sum(1 for e in cerrors if e["severity"] == "error")
    st = _STATE.get(base["job_id"])
    return {"status": st["status"] if st else cstatus, "db_status": status, "kind": kind or "", "stage": st["stage"] if st else ("done" if cstatus == "done" else "reading"),
            "progress": st["progress"] if st else (1.0 if cstatus == "done" else 0.0), "row_count": len(rows) + len(errors), "accepted_count": len(rows),
            "error_count": n_err, "warning_count": len(cerrors) - n_err, "rejected_rows": len(errors), "columns": cols, "targets": _targets(itype, mapping),
            "missing_required": mapping.get("missing_required", []), "one_of": None, "one_of_missing": False,
            "errors": cerrors, "errors_truncated": len(errors) > 500, "sample_rows": samples,
            "redirect": "/teacher" if cstatus == "done" else None}


_MSG = {
    "missing_student_in_roster": "roll number is not in this institute's roster",
    "duplicate_roll_no": "roll number appears twice in the file; first row kept",
    "underage_enrolment_lt_16": "student is under 16 at joining; enrolment is not allowed (MoE 2024 guideline), row rejected",
    "invalid_date": "date could not be read",
    "negative_fee_amount": "fee amounts cannot be negative",
    "invalid_phone_number": "phone must be 10 digits",
    "invalid_option_label": "answer must be one of A, B, C, D (use | between options)",
    "hidden_row_skipped": "hidden spreadsheet row skipped",
    "trailing_totals_row": "totals row at the bottom skipped",
    "duplicate_or_out_of_bounds_score": "score is above the maximum marks or the student appears twice for this test",
    "missing_roll_no": "roll number is empty",
    "unknown_batch": "batch name does not exist; create the batch first",
    "no_answer_key_for_test": "the test has no answer key yet; upload the answer key first",
    "unknown_question_no": "question number is not in this test",
    "invalid_attendance_marker": "attendance marker not understood (use P/A, Present/Absent, 1/0)",
    "unreadable_value": "a value in this row could not be read as a number or date",
    "absurd_date": "date is outside the plausible range",
}


# ---------------------------------------------------------------- validation against the tenant
def _validate(conn, itype, rows, errors, warnings, params):
    ro = roster(conn)
    resolved: dict = {}
    keep = []
    off = weekly_off(conn)

    def err(r, code, field, value, msg=None):
        errors.append({"row_number": r.get("_row"), "code": code, "field": field, "value": str(value), **({"message": msg} if msg else {})})

    if itype == "students":
        bl = batch_lookup(conn)
        existing = 0
        minors = 0
        for r in rows:
            b = bl.get(r["batch_name"].strip().lower())
            if not b:
                err(r, "unknown_batch", "batch_name", r["batch_name"])
                continue
            r["_batch_id"] = b["id"]
            existing += r["roll_no"] in ro
            minors += (pd.Timestamp(config.ASOF_NOW) - pd.Timestamp(r["dob"])).days / 365.25 < 18
            keep.append(r)
        if existing:
            warnings.append({"code": "existing_students_updated", "message": f"{existing} students already exist and will be updated", "count": existing})
        if minors:
            warnings.append({"code": "minors_need_consent", "message": f"{minors} students are under 18: verified parental consent is required before analytics (DPDP s.9)", "count": minors})
        under16 = [e["row_number"] for e in errors if e["code"] == "underage_enrolment_lt_16"]
        if under16:
            warnings.append({"code": "underage_enrolment_lt_16", "message": f"{len(under16)} rows rejected: student under 16 at joining", "rows": under16})
        return keep, errors, warnings, resolved

    if itype in ("guardians", "attendance", "fees"):
        late = 0
        dmax = None
        for r in rows:
            s = ro.get(r["roll_no"])
            if not s:
                err(r, "missing_student_in_roster", "roll_no", r["roll_no"])
                continue
            r["_student_id"] = s["id"]
            d = r.get("attendance_date") or r.get("due_date")
            if d and itype == "attendance":
                if not ("2015-01-01" <= d <= "2100-01-01"):
                    err(r, "absurd_date", "attendance_date", d)
                    continue
                dmax = max(dmax or d, d)
                late += d > config.ASOF_NOW
            keep.append(r)
        if itype == "attendance" and late:
            warnings.append({"code": "after_demo_as_of", "message": f"{late} rows are dated after the as-of date {config.ASOF_NOW}; models use data up to the as-of date. "
                                                                    f"Pass as_of={dmax} on the read endpoints to include them", "count": late, "suggested_as_of": dmax})
        return keep, errors, warnings, resolved

    if itype in ("results_marks_only",):
        tests = _tests_by_batch_name(conn)
        new_tests: dict[tuple, dict] = {}
        flagged = set()
        for r in rows:
            s = ro.get(r["roll_no"])
            if not s:
                err(r, "missing_student_in_roster", "roll_no", r["roll_no"])
                continue
            t = _find_test(tests, s["batch_id"], r["test_name"], r["test_date"])
            _, dflt = _scheme_default(s["exam"])
            max_marks = float(params["max_marks"]) if params.get("max_marks") else (float(t["max_marks"]) if t else dflt)
            if r["raw_score"] is not None and (r["raw_score"] > max_marks or r["raw_score"] < -max_marks):
                err(r, "duplicate_or_out_of_bounds_score", "raw_score", r["raw_score"])
                continue
            r["_student_id"], r["_batch_id"] = s["id"], s["batch_id"]
            r["_test_id"] = t["id"] if t else None
            r["_max_marks"] = max_marks
            if not t:
                new_tests[(s["batch_id"], r["test_name"])] = {"date": r["test_date"]}
            d = r["test_date"] or (str(t["test_date"]) if t else None)
            if d and scoring.day_after_off(d, off):
                flagged.add((r["test_name"], d))
            keep.append(r)
        if new_tests:
            warnings.append({"code": "new_tests_will_be_created", "message": f"{len(new_tests)} test(s) are new for their batch and will be created from this file", "count": len(new_tests)})
        if flagged:
            warnings.append({"code": "test_day_after_weekly_off", "message": "test dated on the day after the weekly off (MoE 2024 cl. 10.1): " + ", ".join(f"{n} on {d}" for n, d in sorted(flagged)), "count": len(flagged)})
        resolved["target"] = {"new_tests": len(new_tests)}
        return keep, errors, warnings, resolved

    if itype in ("results_responses", "results_long"):
        tests = _tests_by_batch_name(conn)
        ctx: dict[str, dict] = {}
        flagged = set()
        for r in rows:
            s = ro.get(r["roll_no"])
            if not s:
                err(r, "missing_student_in_roster", "roll_no", r["roll_no"])
                continue
            t = _find_test(tests, s["batch_id"], r["test_name"], r["test_date"])
            if not t:
                err(r, "no_answer_key_for_test", "test_name", r["test_name"], "no test named like this exists for the student's batch; upload the answer key (it creates the test) first")
                continue
            if t["id"] not in ctx:
                with _rc(conn) as cur:
                    cur.execute("SELECT count(*) AS n FROM answer_keys WHERE test_id=%s", (t["id"],))
                    ctx[t["id"]] = {"keys": cur.fetchone()["n"], "date": str(t["test_date"])}
            if not ctx[t["id"]]["keys"]:
                err(r, "no_answer_key_for_test", "test_name", r["test_name"])
                continue
            r["_student_id"], r["_test_id"] = s["id"], t["id"]
            if scoring.day_after_off(ctx[t["id"]]["date"], off):
                flagged.add((r["test_name"], ctx[t["id"]]["date"]))
            keep.append(r)
        if flagged:
            warnings.append({"code": "test_day_after_weekly_off", "message": "test dated on the day after the weekly off (MoE 2024 cl. 10.1): " + ", ".join(f"{n} on {d}" for n, d in sorted(flagged)), "count": len(flagged)})
        resolved["target"] = {"tests": len(ctx)}
        return keep, errors, warnings, resolved

    if itype == "answer_key":
        target = _answer_key_target(conn, params)
        resolved["target"] = target
        qn = {r["question_no"] for r in rows}
        if target.get("test_ids"):
            with _rc(conn) as cur:
                cur.execute("SELECT max(position) AS n FROM test_questions WHERE test_id = ANY(%s::uuid[])", (target["test_ids"],))
                n = cur.fetchone()["n"] or 0
            for r in rows:
                if r["question_no"] > n:
                    err(r, "unknown_question_no", "question_no", r["question_no"])
                else:
                    keep.append(r)
            target["questions_in_test"] = n
        else:
            keep = rows
            warnings.append({"code": "new_test_will_be_created", "message": f"test '{target['test_name']}' does not exist; it will be created with {len(qn)} questions", "count": len(qn)})
        if target.get("test_date") and scoring.day_after_off(target["test_date"], off):
            warnings.append({"code": "test_day_after_weekly_off", "message": f"test dated {target['test_date']} is the day after the weekly off (MoE 2024 cl. 10.1)", "count": 1})
        return keep, errors, warnings, resolved
    raise IngestError(500, f"no validator for {itype}")


def _answer_key_target(conn, params) -> dict:
    with _rc(conn) as cur:
        if params.get("test_id"):
            cur.execute("SELECT id::text, name, batch_id::text, test_date FROM tests WHERE id=%s", (params["test_id"],))
            t = cur.fetchone()
            if not t:
                raise IngestError(404, "test_id not found")
            return {"test_ids": [t["id"]], "test_name": t["name"], "mode": "existing", "test_date": str(t["test_date"])}
        if not params.get("test_name"):
            raise IngestError(422, "give test_id (existing test) or test_name + batch_id (new test)")
        if params.get("batch_id"):
            cur.execute("SELECT id::text, name, batch_id::text, test_date FROM tests WHERE batch_id=%s AND lower(name)=lower(%s)", (params["batch_id"], params["test_name"]))
        else:
            cur.execute("SELECT id::text, name, batch_id::text, test_date FROM tests WHERE lower(name)=lower(%s)", (params["test_name"],))
        ts = cur.fetchall()
        if ts:
            return {"test_ids": [t["id"] for t in ts], "test_name": ts[0]["name"], "mode": "existing", "test_date": str(ts[0]["test_date"])}
        if not params.get("batch_id"):
            raise IngestError(422, "no test with this name exists; give batch_id to create it")
        cur.execute("SELECT id::text, exam FROM batches WHERE id=%s", (params["batch_id"],))
        b = cur.fetchone()
        if not b:
            raise IngestError(404, "batch_id not found")
        return {"test_ids": [], "test_name": params["test_name"], "mode": "create", "batch_id": b["id"],
                "test_date": params.get("test_date") or config.ASOF_NOW, "exam": b["exam"]}


# ---------------------------------------------------------------- jobs
def get_job(conn, job_id: str) -> dict:
    try:
        with _rc(conn) as cur:
            cur.execute("SELECT id::text, status, type, mapping, errors, rows_ok, rows_failed FROM ingest_jobs WHERE id=%s", (job_id,))
            j = cur.fetchone()
    except psycopg2.errors.InvalidTextRepresentation:
        conn.rollback()
        raise IngestError(422, "job id is not a valid uuid")
    if not j:
        raise IngestError(404, "job not found")
    p = _payload_path(job_id)
    payload = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"rows": [], "resolved": {}, "params": {}, "ingest_type": j["type"], "filename": ""}
    view = _job_view(job_id, j["status"], payload["ingest_type"], payload.get("filename", ""), j["mapping"], j["errors"], payload.get("warnings", []),
                     payload["rows"], payload.get("resolved", {}), payload.get("params", {}), committed=j["status"] == "confirmed", result=payload.get("result"), kind=payload.get("kind"))
    view["rows_ok"], view["rows_failed"] = j["rows_ok"], j["rows_failed"]
    return view


# ---------------------------------------------------------------- commit
def commit(conn, institute_id: str, job_id: str) -> dict:
    t0 = time.perf_counter()
    with _rc(conn) as cur:
        cur.execute("SELECT status FROM ingest_jobs WHERE id=%s FOR UPDATE", (job_id,))
        j = cur.fetchone()
    if not j:
        raise IngestError(404, "job not found")
    p = _payload_path(job_id)
    if not p.exists():
        raise IngestError(410, "the uploaded rows are no longer cached; upload the file again")
    payload = json.loads(p.read_text(encoding="utf-8"))
    if j["status"] == "confirmed":
        return {"job_id": job_id, "status": "confirmed", "idempotent": True, "message": "already committed", "result": payload.get("result")}
    if j["status"] != "preview_ready":
        raise IngestError(422, "Missing required columns: " + ", ".join(json.loads(json.dumps(payload.get("warnings", [{}])[0].get("columns", []))) or ["see mapping"]) if j["status"] == "pending_mapping" else f"job is '{j['status']}' and cannot be committed")
    itype, rows, params = payload["ingest_type"], payload["rows"], payload["params"]
    if not rows:
        raise IngestError(422, "no valid rows to commit")
    fn = {"students": _c_students, "guardians": _c_guardians, "attendance": _c_attendance, "fees": _c_fees,
          "results_marks_only": _c_marks, "results_responses": _c_responses, "results_long": _c_responses_long, "answer_key": _c_key}[itype]
    result = fn(conn, institute_id, rows, params)
    t_write = time.perf_counter() - t0
    batches = result.pop("_batches", [])
    rec = {}
    t1 = time.perf_counter()
    analytics.bump(institute_id)
    for b in batches:
        r = analytics.recompute(conn, institute_id, b)
        rec[b] = r["seconds"] + r.get("seconds_persist", 0)
    result["recompute"] = {"batches": len(batches), "seconds_total": round(time.perf_counter() - t1, 2), "seconds_per_batch": rec}
    result["write_seconds"] = round(t_write, 2)
    payload["result"] = result
    p.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute("UPDATE ingest_jobs SET status='confirmed' WHERE id=%s", (job_id,))
    return {"job_id": job_id, "status": "confirmed", "idempotent": False, "result": result}


def _execute_values(cur, sql, vals, template=None, page=2000):
    if vals:
        psycopg2.extras.execute_values(cur, sql, vals, template=template, page_size=page)


def _c_students(conn, iid, rows, params):
    with conn.cursor() as cur:
        cur.execute("SELECT id::text, academic_year, exam, class_level FROM batches")
        bmeta = {r[0]: r for r in cur.fetchall()}
        vals = []
        for r in rows:
            gender = r["gender"] if r["gender"] in ("female", "male", "other", "prefer_not_to_say") else "prefer_not_to_say"
            plan = r["fee_plan"] if r["fee_plan"] in ip.FEE_PLANS else "standard_3_instalment"
            vals.append((iid, r["_batch_id"], bmeta[r["_batch_id"]][1], r["roll_no"], r["name"], r["name_alt"] or None, r["dob"], gender, r["join_date"], plan, r["out_of_town"]))
        _execute_values(cur, "INSERT INTO students (institute_id, batch_id, academic_year, roll_no, name, name_alt, dob, gender, join_date, fee_plan, out_of_town) VALUES %s "
                             "ON CONFLICT (institute_id, academic_year, roll_no) DO UPDATE SET batch_id=EXCLUDED.batch_id, name=EXCLUDED.name, name_alt=EXCLUDED.name_alt, "
                             "dob=EXCLUDED.dob, gender=EXCLUDED.gender, join_date=EXCLUDED.join_date, fee_plan=EXCLUDED.fee_plan, out_of_town=EXCLUDED.out_of_town", vals)
    return {"students_written": len(vals), "_batches": sorted({r["_batch_id"] for r in rows}),
            "note": "new students have no consent yet: add consents before they appear on support lists"}


def _c_guardians(conn, iid, rows, params):
    n = 0
    with conn.cursor() as cur:
        for r in rows:
            rel = r["relation"] if r["relation"] in ("father", "mother", "legal_guardian", "self") else "legal_guardian"
            lang = r["lang_pref"] if r["lang_pref"] in ("en", "hi") else "hi"
            cur.execute("SELECT 1 FROM guardians WHERE student_id=%s AND phone=%s AND name=%s", (r["_student_id"], r["phone"], r["guardian_name"]))
            if cur.fetchone():
                continue
            cur.execute("INSERT INTO guardians (institute_id, student_id, name, phone, relation, lang_pref) VALUES (%s,%s,%s,%s,%s,%s)",
                        (iid, r["_student_id"], r["guardian_name"], r["phone"], rel, lang))
            n += 1
    return {"guardians_written": n, "already_present": len(rows) - n, "_batches": []}


def _students_batches(conn, student_ids) -> list[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT batch_id::text FROM students WHERE id = ANY(%s::uuid[])", (list(student_ids),))
        return [r[0] for r in cur.fetchall()]


def _c_attendance(conn, iid, rows, params):
    vals = [(iid, r["_student_id"], r["attendance_date"], r["present_flag"], r["source"] if r["source"] in ("csv", "manual", "biometric") else "csv") for r in rows]
    # last write wins when a file repeats a (student, date) pair
    vals = list({(v[1], v[2]): v for v in vals}.values())
    with conn.cursor() as cur:
        _execute_values(cur, "INSERT INTO attendance (institute_id, student_id, attendance_date, present_flag, source) VALUES %s "
                             "ON CONFLICT (student_id, attendance_date) DO UPDATE SET present_flag=EXCLUDED.present_flag, source=EXCLUDED.source", vals, page=5000)
    return {"attendance_rows_written": len(vals), "_batches": _students_batches(conn, {v[1] for v in vals})}


def _c_fees(conn, iid, rows, params):
    vals = list({(r["_student_id"], r["instalment_no"]): (iid, r["_student_id"], r["instalment_no"], r["due_date"], r["amount_paise"], r["paid_date"],
                                                          r["paid_amount_paise"], r["refund_due_paise"], r["refund_paid_date"]) for r in rows}.values())
    with conn.cursor() as cur:
        _execute_values(cur, "INSERT INTO fees (institute_id, student_id, instalment_no, due_date, amount_paise, paid_date, paid_amount_paise, refund_due_paise, refund_paid_date) VALUES %s "
                             "ON CONFLICT (student_id, instalment_no) DO UPDATE SET due_date=EXCLUDED.due_date, amount_paise=EXCLUDED.amount_paise, paid_date=EXCLUDED.paid_date, "
                             "paid_amount_paise=EXCLUDED.paid_amount_paise, refund_due_paise=EXCLUDED.refund_due_paise, refund_paid_date=EXCLUDED.refund_paid_date", vals)
    return {"fee_rows_written": len(vals), "_batches": _students_batches(conn, {v[1] for v in vals})}


def _create_test(conn, iid, batch_id, name, date, max_marks, source="csv") -> str:
    off_flag = False
    with conn.cursor() as cur:
        cur.execute("SELECT exam FROM batches WHERE id=%s", (batch_id,))
        exam = cur.fetchone()[0]
        cur.execute("SELECT weekly_off_day FROM institutes LIMIT 1")
        off_flag = scoring.day_after_off(date, cur.fetchone()[0])
        cur.execute("INSERT INTO tests (institute_id, batch_id, name, test_date, exam_pattern_code, marking_scheme_id, max_marks, source, day_after_off_warning) "
                    "VALUES (%s,%s,%s,%s,'internal_chapter_test',%s,%s,%s,%s) RETURNING id::text",
                    (iid, batch_id, name, date, _scheme_default(exam)[0], max_marks, source, off_flag))
        return cur.fetchone()[0]


def _c_marks(conn, iid, rows, params):
    tests = _tests_by_batch_name(conn)
    made: dict[tuple, str] = {}
    vals = []
    for r in rows:
        tid = r["_test_id"]
        if not tid:
            k = (r["_batch_id"], r["test_name"])
            if k not in made:
                made[k] = _create_test(conn, iid, r["_batch_id"], r["test_name"], r["test_date"] or config.ASOF_NOW, r["_max_marks"])
            tid = made[k]
        vals.append((iid, tid, r["_student_id"], r["raw_score"], r["physics_score"], r["chemistry_score"], r["math_or_bio_score"], bool(r["absent_flag"])))
    vals = list({(v[1], v[2]): v for v in vals}.values())
    with conn.cursor() as cur:
        _execute_values(cur, "INSERT INTO test_totals (institute_id, test_id, student_id, raw_score, physics_score, chemistry_score, math_or_bio_score, absent_flag) VALUES %s "
                             "ON CONFLICT (test_id, student_id) DO UPDATE SET raw_score=EXCLUDED.raw_score, physics_score=EXCLUDED.physics_score, "
                             "chemistry_score=EXCLUDED.chemistry_score, math_or_bio_score=EXCLUDED.math_or_bio_score, absent_flag=EXCLUDED.absent_flag", vals, page=5000)
    return {"score_rows_written": len(vals), "tests_created": len(made), "_batches": _students_batches(conn, {v[2] for v in vals}),
            "note": "marks-only data has no question-level responses, so topic mastery is not updated by this file"}


def _score_and_store(conn, iid, per_test: dict[str, list[tuple[str, int, str | None]]]) -> dict:
    """per_test: test_id -> [(student_id, question_no, response)]."""
    written, students = 0, set()
    for tid, items in per_test.items():
        keys = scoring.latest_keys(conn, tid)
        scheme = scoring.scheme_for(conn, tid)
        pos = dict(zip(keys.position, keys.question_id))
        recs = []
        for sid, qn, resp in items:
            q = pos.get(qn)
            if q is None:
                continue
            recs.append({"student_id": sid, "question_id": q, "response": resp, "status": "answered" if resp not in (None, "") else "blank"})
        if not recs:
            continue
        df = scoring.score_frame(pd.DataFrame(recs), keys, scheme)
        vals = [(iid, tid, r.student_id, r.question_id, r.response, bool(r.is_correct), float(r.marks), r.new_status, 1.0) for r in df.itertuples()]
        vals = list({(v[2], v[3]): v for v in vals}.values())
        with conn.cursor() as cur:
            _execute_values(cur, "INSERT INTO responses (institute_id, test_id, student_id, question_id, response, is_correct, marks_awarded, status, confidence) VALUES %s "
                                 "ON CONFLICT (test_id, student_id, question_id) DO UPDATE SET response=EXCLUDED.response, is_correct=EXCLUDED.is_correct, "
                                 "marks_awarded=EXCLUDED.marks_awarded, status=EXCLUDED.status", vals, page=5000)
        scoring.rebuild_totals(conn, tid)
        scoring.refresh_item_difficulty(conn, sorted({v[3] for v in vals}), config.MODEL_VERSION)
        written += len(vals)
        students |= {v[2] for v in vals}
    return {"response_rows_written": written, "students": len(students), "tests": len(per_test), "_batches": _students_batches(conn, students) if students else []}


def _c_responses(conn, iid, rows, params):
    per: dict[str, list] = {}
    for r in rows:
        for k, v in r.items():
            m = re.fullmatch(r"q(\d+)", k)
            if m:
                per.setdefault(r["_test_id"], []).append((r["_student_id"], int(m.group(1)), v))
    return _score_and_store(conn, iid, per)


def _c_responses_long(conn, iid, rows, params):
    per: dict[str, list] = {}
    for r in rows:
        per.setdefault(r["_test_id"], []).append((r["_student_id"], r["question_no"], r["response"]))
    return _score_and_store(conn, iid, per)


def _c_key(conn, iid, rows, params):
    target = _answer_key_target(conn, params)
    batches: set[str] = set()
    changed_total = 0
    with conn.cursor() as cur:
        if target["mode"] == "create":
            tid = _create_test(conn, iid, target["batch_id"], target["test_name"], target["test_date"], float(params.get("max_marks") or 4 * len(rows)), source="csv")
            test_ids = [tid]
            batches.add(target["batch_id"])
            for r in sorted(rows, key=lambda x: x["question_no"]):
                cur.execute("INSERT INTO questions (institute_id, subject, text_hash, q_type, options_n) VALUES (%s,%s,%s,%s,%s) RETURNING id::text",
                            (iid, r["subject"] or "General", hashlib.sha256(f"{tid}|{r['question_no']}".encode()).hexdigest(), r["q_type"], 0 if r["q_type"] == "numeric" else 4))
                qid = cur.fetchone()[0]
                if r["topic_id"]:
                    cur.execute("SELECT 1 FROM topics WHERE id=%s", (r["topic_id"],))
                    if cur.fetchone():
                        cur.execute("INSERT INTO question_topics (question_id, institute_id, topic_id, weight, tagged_by, confidence) VALUES (%s,%s,%s,1.0,'human',1.0)", (qid, iid, r["topic_id"]))
                cur.execute("INSERT INTO test_questions (institute_id, test_id, question_id, position, section) VALUES (%s,%s,%s,%s,'A')", (iid, tid, qid, r["question_no"]))
                cur.execute("INSERT INTO answer_keys (institute_id, test_id, question_id, accepted_answers, numeric_tolerance, dropped, version) VALUES (%s,%s,%s,%s,%s,%s,1)",
                            (iid, tid, qid, r["accepted_answers"], r["numeric_tolerance"], r["dropped"]))
            return {"test_created": True, "test_ids": test_ids, "questions": len(rows), "_batches": [], "note": "item difficulties start at 0 and update as responses arrive"}
        test_ids = target["test_ids"]
        rescored = []
        for tid in test_ids:
            keys = scoring.latest_keys(conn, tid)
            cur.execute("SELECT batch_id::text FROM tests WHERE id=%s", (tid,))
            batches.add(cur.fetchone()[0])
            kmap = keys.set_index("position") if len(keys) else None
            changed_q = []
            for r in rows:
                if kmap is None or r["question_no"] not in kmap.index:
                    continue
                cur_k = kmap.loc[r["question_no"]]
                if (sorted(cur_k.accepted) != sorted(r["accepted_answers"]) or bool(cur_k.dropped) != r["dropped"]
                        or abs(float(cur_k.tol or 0) - r["numeric_tolerance"]) > 1e-12):
                    cur.execute("INSERT INTO answer_keys (institute_id, test_id, question_id, accepted_answers, numeric_tolerance, dropped, version) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                                (iid, tid, cur_k.question_id, r["accepted_answers"], r["numeric_tolerance"], r["dropped"], int(cur_k.version) + 1))
                    changed_q.append(cur_k.question_id)
            if changed_q:
                rescored.append(scoring.rescore_test(conn, tid, changed_q))
                scoring.refresh_item_difficulty(conn, changed_q, config.MODEL_VERSION)
            changed_total += len(changed_q)
    return {"test_ids": test_ids, "keys_changed": changed_total, "rescored": rescored, "_batches": sorted(batches)}
