"""Consent ledger. Accepts both the original body (student_id, purpose, verification_method) and the front end's
(roll_no, guardian_name, method); the list returns both `consents` (every purpose) and `items` + `summary` (one row per student)."""
from __future__ import annotations

import datetime as dt
import time
from typing import Literal

import pandas as pd
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import deps
from ..services import analytics, profiles
from .read import _check_student, audit

router = APIRouter(prefix="/api/v1")
MANAGE = deps.require(*deps.MANAGERS)


def _rc(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def _standing(res: dict, sid: str) -> dict:
    sc = res["scores"]
    if sid not in sc.index:
        return {"scored": False, "p": None, "rank": None, "on_support_list": False}
    ranked = sc.p.rank(ascending=False, method="first")
    cap = max(1, sum(b["mentor_capacity_per_week"] for b in res["batches"]))
    return {"scored": True, "p": round(float(sc.at[sid, "p"]), 4), "rank": int(ranked[sid]), "on_support_list": bool(ranked[sid] <= cap), "model": sc.at[sid, "model"]}


class ConsentIn(BaseModel):
    student_id: str | None = None
    roll_no: str | None = None
    guardian_name: str | None = None
    purpose: Literal["analytics", "risk_alerts", "parent_reports", "benchmarking", "engagement_tracking"] | None = None
    verification_method: Literal["in_person_id_check", "otp_known_parent", "digilocker_token", "self_adult"] | None = None
    method: Literal["in_person_id_check", "otp_known_parent", "digilocker_token", "digilocker", "self_adult"] | None = None
    notice_lang: Literal["en", "hi"] = "hi"


def _row(r: dict, guardian: str | None) -> dict:
    return {"consent_id": r["id"], "student_id": r["student_id"], "roll_no": r["roll_no"], "guardian_display": guardian or "Self (adult)",
            "kind": "self" if r["verification_method"] == "self_adult" else "parental", "method": r["verification_method"],
            "date": str(r["verified_at"])[:10], "status": "withdrawn" if r["revoked_at"] else "active"}


@router.get("/consents")
def list_consents(student_id: str | None = None, purpose: str | None = None, active_only: bool = False, q: str | None = None,
                  p=Depends(deps.current_principal), conn=Depends(deps.tenant)):
    if p.is_family:
        student_id = p.student_id
    elif p.role == "mentor":
        raise HTTPException(403, "role 'mentor' may not view the consent ledger")
    sql = ("SELECT c.id::text, c.student_id::text, c.purpose, c.verification_method, c.verified_at, c.revoked_at, c.notice_version, c.notice_lang, s.roll_no, "
           "(SELECT g.name FROM guardians g WHERE g.student_id=c.student_id ORDER BY g.created_at LIMIT 1) AS guardian "
           "FROM consents c JOIN students s ON s.id=c.student_id WHERE TRUE")
    args: list = []
    if student_id:
        sql += " AND c.student_id=%s"
        args.append(student_id)
    if purpose:
        sql += " AND c.purpose=%s"
        args.append(purpose)
    if active_only:
        sql += " AND c.revoked_at IS NULL"
    if q:
        sql += " AND (s.roll_no ILIKE %s OR s.name ILIKE %s)"
        args += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY c.verified_at DESC LIMIT 1000"
    try:
        with _rc(conn) as cur:
            cur.execute(sql, args)
            raw = cur.fetchall()
    except psycopg2.errors.InvalidTextRepresentation:
        conn.rollback()
        raise HTTPException(422, "student id is not a valid uuid")
    rows = [{k: v for k, v in dict(r).items() if k != "guardian"} | {"verified_at": r["verified_at"].isoformat(),
            "revoked_at": r["revoked_at"].isoformat() if r["revoked_at"] else None} for r in raw]
    items = [_row(r, r["guardian"]) for r in raw if r["purpose"] == "analytics"][:200]
    return {"consents": rows, "count": len(rows), "items": items,
            "summary": {"total": len(items), "active": sum(i["status"] == "active" for i in items), "withdrawn": sum(i["status"] == "withdrawn" for i in items)}}


@router.post("/consents", status_code=201)
def grant_consent(body: ConsentIn, p=Depends(MANAGE), conn=Depends(deps.tenant)):
    t0 = time.perf_counter()
    method = {"digilocker": "digilocker_token"}.get(body.method or "", body.method) or body.verification_method
    sid = body.student_id
    front = body.roll_no is not None
    if front:
        with _rc(conn) as cur:
            cur.execute("SELECT id::text FROM students WHERE roll_no=%s ORDER BY academic_year DESC LIMIT 1", (body.roll_no,))
            r = cur.fetchone()
        if not r:
            raise HTTPException(404, f"roll number {body.roll_no} not found")
        sid = r["id"]
    if not sid or not method:
        raise HTTPException(422, "give student_id (or roll_no) and the verification method")
    purposes = [body.purpose] if body.purpose else ["analytics", "risk_alerts", "parent_reports"]
    sr = _check_student(p, conn, sid)
    minor = (analytics.asof_ts() - pd.Timestamp(sr["dob"])).days / 365.25 < 18
    if minor and method == "self_adult":
        raise HTTPException(422, "a minor cannot consent for themselves; use a parental verification method")
    if not minor and method != "self_adult":
        if not front:
            raise HTTPException(422, "an adult student gives their own consent: use verification_method self_adult")
        method = "self_adult"
    if minor and "engagement_tracking" in purposes:
        raise HTTPException(422, "engagement tracking is never used for minors (DPDP s.9(3)); consent cannot be recorded")
    with _rc(conn) as cur:
        if front:
            cur.execute("SELECT 1 FROM consents WHERE student_id=%s AND purpose='analytics' AND revoked_at IS NULL", (sid,))
            if cur.fetchone():
                raise HTTPException(409, "an active consent already exists for this student")
        gid = None
        if minor:
            cur.execute("SELECT id::text FROM guardians WHERE student_id=%s ORDER BY created_at LIMIT 1", (sid,))
            g = cur.fetchone()
            if not g and body.guardian_name:
                cur.execute("INSERT INTO guardians (institute_id, student_id, name, phone, relation, lang_pref) VALUES (%s,%s,%s,'0000000000','legal_guardian','hi') RETURNING id::text",
                            (p.institute_id, sid, body.guardian_name))
                g = cur.fetchone()
            if not g:
                raise HTTPException(422, "no guardian on record for this minor; add the guardian first")
            gid = g["id"]
        first = None
        for purpose in purposes:
            cur.execute("UPDATE consents SET revoked_at=now() WHERE student_id=%s AND purpose=%s AND revoked_at IS NULL", (sid, purpose))
            cur.execute("INSERT INTO consents (institute_id, student_id, guardian_id, purpose, verification_method, verified_by_user_id, notice_version, notice_lang) "
                        "VALUES (%s,%s,%s,%s,%s,%s,'v1',%s) RETURNING id::text, verified_at", (p.institute_id, sid, gid, purpose, method, p.user_id, body.notice_lang))
            row = cur.fetchone()
            first = first or row
            audit(conn, p, "grant_consent", "consent", row["id"])
        cur.execute("SELECT name FROM guardians WHERE student_id=%s ORDER BY created_at LIMIT 1", (sid,))
        gn = (cur.fetchone() or {}).get("name")
    res = analytics.recompute(conn, p.institute_id, sr["batch_id"])
    out = {"id": first["id"], "student_id": sid, "purpose": purposes[0], "status": "active", "standing": _standing(res, sid),
           "recompute_seconds": round(time.perf_counter() - t0, 3)}
    out.update(_row({"id": first["id"], "student_id": sid, "roll_no": sr["roll_no"], "verification_method": method, "verified_at": first["verified_at"], "revoked_at": None}, gn))
    return out


@router.delete("/consents/{consent_id}")
def withdraw_consent(consent_id: str, p=Depends(deps.current_principal), conn=Depends(deps.tenant)):
    """Withdrawal halts processing at once: derived scores are purged and the student leaves every list."""
    t0 = time.perf_counter()
    try:
        with _rc(conn) as cur:
            cur.execute("SELECT c.id::text, c.student_id::text, c.purpose, c.revoked_at, c.verification_method, c.verified_at FROM consents c WHERE c.id=%s", (consent_id,))
            c = cur.fetchone()
    except psycopg2.errors.InvalidTextRepresentation:
        conn.rollback()
        raise HTTPException(422, "consent id is not a valid uuid")
    if not c:
        raise HTTPException(404, "consent not found")
    if p.is_family:
        deps.guard_student(p, c["student_id"])
    elif p.role == "mentor":
        raise HTTPException(403, "role 'mentor' may not change consents")
    if c["revoked_at"]:
        return {"id": consent_id, "status": "already_revoked", "effect": "Already withdrawn.", "consent_id": consent_id}
    sr = profiles.student_row(conn, c["student_id"])
    purged = []
    with _rc(conn) as cur:
        cur.execute("UPDATE consents SET revoked_at=now() WHERE id=%s", (consent_id,))
        if c["purpose"] in ("analytics", "risk_alerts"):
            for tbl in ("mastery_snapshots", "risk_scores", "predictions"):
                cur.execute(f"DELETE FROM {tbl} WHERE student_id=%s", (c["student_id"],))
                purged.append(tbl)
        cur.execute("SELECT name FROM guardians WHERE student_id=%s ORDER BY created_at LIMIT 1", (c["student_id"],))
        gn = (cur.fetchone() or {}).get("name")
    audit(conn, p, "revoke_consent", "consent", consent_id)
    res = analytics.recompute(conn, p.institute_id, sr["batch_id"])
    effect = {"analytics": "Processing stopped: scores for this student were deleted and they no longer appear in any list.",
              "risk_alerts": "Risk alerts stopped: scores for this student were deleted and they no longer appear on the support list.",
              "parent_reports": "Parent reports will no longer be generated for this student."}.get(c["purpose"], "Consent withdrawn.")
    row = _row({"id": consent_id, "student_id": c["student_id"], "roll_no": sr["roll_no"], "verification_method": c["verification_method"],
                "verified_at": c["verified_at"], "revoked_at": True}, gn)
    return {**row, "effect": effect, "id": consent_id, "purpose": c["purpose"], "status": "revoked",
            "halted": {"risk_scoring": c["purpose"] in ("analytics", "risk_alerts"), "parent_reports": c["purpose"] == "parent_reports"},
            "derived_rows_purged_from": purged, "standing": _standing(res, c["student_id"]), "recompute_seconds": round(time.perf_counter() - t0, 3)}
