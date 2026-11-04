"""OMR upload, review and confirm (front-end contract). The reader is app/omr/reader.py; scoring uses the test's stored answer key
through the same path as CSV responses, then the batch is recomputed."""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path

import psycopg2.extras
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from .. import deps
from ..omr import read_sheet
from ..services import analytics, ingest as svc

router = APIRouter(prefix="/api/v1/ingest/omr")
WRITE = deps.require(*deps.MANAGERS)
MAX_IMAGE = 15 * 1024 * 1024


def _rc(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def _path(job_id: str) -> Path:
    return svc._payload_path("omr_" + job_id)


def _view(job_id: str, st: dict) -> dict:
    return {"job_id": job_id, "status": st["status"], "filename": st["filename"], "result": st["result"], "test_id": st.get("test_id"),
            "roll_no": st["result"].get("roll_no"), "scored": st.get("scored")}


def _load(conn, job_id: str) -> dict:
    p = _path(job_id)
    with _rc(conn) as cur:
        try:
            cur.execute("SELECT 1 FROM ingest_jobs WHERE id=%s AND type='omr_photos'", (job_id,))
        except psycopg2.errors.InvalidTextRepresentation:
            conn.rollback()
            raise HTTPException(422, "job id is not a valid uuid")
        if not cur.fetchone() or not p.exists():
            raise HTTPException(404, "OMR job not found")
    return json.loads(p.read_text(encoding="utf-8"))


def _resolve_test(conn, form_test_id: str | None, result: dict) -> tuple[str | None, str | None]:
    """(test_id, student_id): explicit form value, else a UUID in the QR payload, else the latest keyed test of the student's batch."""
    cand = form_test_id
    if not cand and result.get("test_id"):
        for part in str(result["test_id"]).replace("|", " ").split():
            try:
                cand = str(uuid.UUID(part))
                break
            except ValueError:
                continue
    with _rc(conn) as cur:
        sid = None
        if result.get("roll_no"):
            cur.execute("SELECT id::text, batch_id::text FROM students WHERE roll_no=%s ORDER BY academic_year DESC LIMIT 1", (result["roll_no"],))
            r = cur.fetchone()
            sid, batch = (r["id"], r["batch_id"]) if r else (None, None)
        if cand:
            try:
                cur.execute("SELECT id::text FROM tests WHERE id=%s", (cand,))
            except psycopg2.errors.InvalidTextRepresentation:
                conn.rollback()
                raise HTTPException(422, "test_id is not a valid uuid")
            if cur.fetchone():
                return cand, sid
            if form_test_id:
                raise HTTPException(404, "test not found")
        if sid:
            cur.execute("SELECT t.id::text FROM tests t WHERE t.batch_id=%s AND EXISTS (SELECT 1 FROM answer_keys k WHERE k.test_id=t.id) ORDER BY t.test_date DESC LIMIT 1", (batch,))
            r = cur.fetchone()
            if r:
                return r["id"], sid
    return None, sid


@router.post("", status_code=201)
async def upload_omr(file: UploadFile = File(...), test_id: str | None = Form(None), p=Depends(WRITE), conn=Depends(deps.tenant)):
    data = await file.read()
    if not data:
        raise HTTPException(422, "empty file")
    if len(data) > MAX_IMAGE:
        raise HTTPException(413, "image larger than 15 MB")
    h = hashlib.sha256(data + (test_id or "").encode()).hexdigest()
    with _rc(conn) as cur:
        cur.execute("SELECT id::text FROM ingest_jobs WHERE file_hash=%s AND type='omr_photos'", (h,))
        dup = cur.fetchone()
    if dup and _path(dup["id"]).exists():
        return _view(dup["id"], json.loads(_path(dup["id"]).read_text(encoding="utf-8")))
    t0 = time.perf_counter()
    try:
        d = read_sheet(data, None).to_dict()
    except Exception as ex:  # undecodable file: ask for a retake instead of failing
        d = {"layout_name": None, "test_id": None, "qr_payload": None, "roll_no": None, "roll_confidence": 0.0, "questions": {}, "uncertain": [], "elapsed_ms": 0.0,
             "quality": {"ok": False, "retake": True, "reason": f"the file is not a readable photo ({type(ex).__name__}); take the photo again", "notes": []}}
    status = "retake" if d["quality"]["retake"] else "review"
    tid, sid = (None, None) if status == "retake" else _resolve_test(conn, test_id, d)
    job_id = str(uuid.uuid4())
    st = {"status": status, "filename": file.filename or "sheet.jpg", "result": d, "test_id": tid, "student_id": sid, "read_seconds": round(time.perf_counter() - t0, 2)}
    _path(job_id).write_text(json.dumps(st, ensure_ascii=False, default=str), encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute("INSERT INTO ingest_jobs (id, institute_id, file_hash, type, status, mapping, errors, rows_ok, rows_failed) VALUES (%s,%s,%s,'omr_photos',%s,%s,'[]',%s,0)",
                    (job_id, p.institute_id, h, "awaiting_review" if status == "review" else "failed", json.dumps({"layout": d["layout_name"]}), len(d["questions"])))
    return _view(job_id, st)


@router.get("/{job_id}")
def get_omr(job_id: str, p=Depends(WRITE), conn=Depends(deps.tenant)):
    return _view(job_id, _load(conn, job_id))


class ConfirmIn(BaseModel):
    corrections: dict[str, str] = {}
    roll_no: str | None = None
    test_id: str | None = None


@router.post("/{job_id}/confirm")
def confirm_omr(job_id: str, body: ConfirmIn, p=Depends(WRITE), conn=Depends(deps.tenant)):
    st = _load(conn, job_id)
    if st["status"] == "done":
        return {"status": "done", "roll_no": st["result"]["roll_no"], "scored": st["scored"], "redirect": "/teacher", "idempotent": True}
    if st["status"] == "retake":
        raise HTTPException(422, "this photo needs a retake: " + str(st["result"]["quality"].get("reason") or "unreadable"))
    d = st["result"]
    need = {u["question_no"] for u in d["uncertain"] if u["question_no"] is not None}
    got = set()
    for k, v in body.corrections.items():
        if not k.isdigit() or str(v).upper() not in ("A", "B", "C", "D") and not _is_number(v):
            raise HTTPException(422, f"correction for question {k} must be A, B, C or D")
        got.add(int(k))
    missing = sorted(need - got)
    if missing:
        raise HTTPException(422, "Confirm or correct these questions first: " + ", ".join(map(str, missing)))
    roll = body.roll_no or d["roll_no"]
    if not roll:
        raise HTTPException(422, "the roll number could not be read; send roll_no with the confirmation")
    tid, sid = _resolve_test(conn, body.test_id or st.get("test_id"), {**d, "roll_no": roll})
    if not tid:
        raise HTTPException(422, "no test with an answer key found for this student; pass test_id")
    if not sid:
        raise HTTPException(404, f"roll number {roll} is not in this institute's roster")
    items = []
    for qk, q in d["questions"].items():
        qn = int(qk)
        ans = body.corrections.get(str(qn), q["answer"])
        items.append((sid, qn, str(ans).upper() if ans and not _is_number(ans) else ans))
    out = svc._score_and_store(conn, p.institute_id, {tid: items})
    with _rc(conn) as cur:
        cur.execute("SELECT count(*) FILTER (WHERE is_correct) AS correct, count(*) FILTER (WHERE NOT is_correct AND status<>'blank' AND status<>'unreadable' AND marks_awarded<>0 OR (NOT is_correct AND status='multi_marked')) AS wrong, "
                    "count(*) FILTER (WHERE status IN ('blank','unreadable')) AS blank, coalesce(sum(marks_awarded),0) AS marks FROM responses WHERE test_id=%s AND student_id=%s", (tid, sid))
        sc = dict(cur.fetchone())
        cur.execute("SELECT max_marks FROM tests WHERE id=%s", (tid,))
        sc["max_marks"] = cur.fetchone()["max_marks"]
        cur.execute("UPDATE ingest_jobs SET status='confirmed' WHERE id=%s", (job_id,))
    rec = {}
    for b in out["_batches"]:
        r = analytics.recompute(conn, p.institute_id, b)
        rec[b] = r["seconds"]
    scored = {k: float(v) for k, v in sc.items()}
    st.update({"status": "done", "scored": scored, "roll_no": roll, "test_id": tid})
    _path(job_id).write_text(json.dumps(st, ensure_ascii=False, default=str), encoding="utf-8")
    return {"status": "done", "roll_no": roll, "scored": scored, "redirect": "/teacher", "test_id": tid, "student_id": sid,
            "recompute_seconds": rec}


def _is_number(v) -> bool:
    try:
        float(str(v))
        return True
    except ValueError:
        return False
