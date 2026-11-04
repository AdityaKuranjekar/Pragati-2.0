"""P5 live what-if edits, consents, privacy tier, interventions; P6 report generation.

Every edit that can change a result runs the batch recompute synchronously and returns the new numbers, so the
screen can refresh in one round trip. Validation errors are 422 with a human-readable message, never a 500.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import time
from typing import Literal

import pandas as pd
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

from .. import config, deps
from ..db import pg
from ..services import analytics, profiles, reports, scoring
from .read import audit, batch_or_404, flagged_for_test, _check_student

router = APIRouter(prefix="/api/v1")
MANAGE = deps.require(*deps.MANAGERS)
OWNER = deps.require("owner", "admin")


def _rc(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def _standing(res: dict, sid: str) -> dict:
    sc = res["scores"]
    if sid not in sc.index:
        return {"scored": False, "p": None, "rank": None, "on_support_list": False}
    ranked = sc.p.rank(ascending=False, method="first")
    cap = max(1, sum(b["mentor_capacity_per_week"] for b in res["batches"]))
    return {"scored": True, "p": round(float(sc.at[sid, "p"]), 4), "rank": int(ranked[sid]), "on_support_list": bool(ranked[sid] <= cap),
            "model": sc.at[sid, "model"]}


def _after_edit(conn, p, sr: dict, before: dict, t0: float, extra: dict) -> dict:
    res = analytics.recompute(conn, p.institute_id, sr["batch_id"])
    slug = deps.slug_of(p.institute_id)
    b = batch_or_404(conn, sr["batch_id"])
    sl = analytics.support_list_json(res, slug, capacity=b["mentor_capacity_per_week"])
    after = _standing(res, sr["id"])
    note = None
    if after.get("model") == "A":
        note = "this student is scored on test results only (tier A: under 18 or institute tier A), so attendance and fee edits do not change the score"
    sc = res["scores"]
    track = analytics._track(after["model"], bool(res["elig"].at[sr["id"], "is_minor"])) if after.get("scored") else "none"
    minor = sr["id"] in res["elig"].index and bool(res["elig"].at[sr["id"], "is_minor"])
    effect = "rule_only" if minor else ("model" if after.get("model") not in (None, "A") else "none")
    en = {"model": "The model used the new attendance and recomputed the support list.",
          "rule_only": "Under 18: attendance is not used by the model; only the transparent attendance rule applies.",
          "none": "Attendance does not change this student's score at the current privacy tier."}[effect]
    hi = {"model": "मॉडल ने नई उपस्थिति से सहायता सूची दोबारा बनाई।",
          "rule_only": "18 वर्ष से कम: मॉडल उपस्थिति का उपयोग नहीं करता; केवल पारदर्शी नियम लागू है।",
          "none": "वर्तमान गोपनीयता स्तर पर उपस्थिति इस विद्यार्थी का स्कोर नहीं बदलती।"}[effect]
    ms = round((time.perf_counter() - t0) * 1000)
    return {"student_id": sr["id"], **extra, "before": before, "after": after, "note": note, "support_list": sl,
            "attendance_pct": extra.get("edited", {}).get("attendance_pct_now"), "track": track, "effect": effect,
            "on_support_list": after["on_support_list"], "recompute_ms": ms, "message_en": en, "message_hi": hi,
            "recompute_seconds": round(time.perf_counter() - t0, 3)}


# ---------------------------------------------------------------- attendance
class AttendanceEdit(BaseModel):
    attendance_pct: float | None = Field(None, description="set the attendance share of the last window_days days to this percentage")
    window_days: int = Field(30, ge=1, le=90)
    date: dt.date | None = None
    present: bool | None = None
    as_of: str | None = None

    @field_validator("attendance_pct")
    @classmethod
    def _pct(cls, v):
        if v is not None and not (0 <= v <= 100):
            raise ValueError("attendance percentage must be between 0 and 100")
        return v

    @model_validator(mode="after")
    def _one_of(self):
        single = self.date is not None or self.present is not None
        if self.attendance_pct is None and not single:
            raise ValueError("give attendance_pct (window edit) or date + present (single day)")
        if self.attendance_pct is not None and single:
            raise ValueError("give either attendance_pct or date + present, not both")
        if single and (self.date is None or self.present is None):
            raise ValueError("a single-day edit needs both date and present")
        if self.date is not None and not (dt.date(2015, 1, 1) <= self.date <= dt.date(2100, 1, 1)):
            raise ValueError("date is outside the plausible range")
        return self


@router.patch("/students/{student_id}/attendance")
def patch_attendance(student_id: str, body: AttendanceEdit, p=Depends(MANAGE), conn=Depends(deps.tenant)):
    t0 = time.perf_counter()
    sr = _check_student(p, conn, student_id)
    asof = analytics.asof_ts(body.as_of)
    before = _standing(analytics.state(conn, p.institute_id, sr["batch_id"], body.as_of), student_id)
    with _rc(conn) as cur:
        if body.date is not None:
            cur.execute("INSERT INTO attendance (institute_id, student_id, attendance_date, present_flag, source) VALUES (%s,%s,%s,%s,'manual') "
                        "ON CONFLICT (student_id, attendance_date) DO UPDATE SET present_flag=EXCLUDED.present_flag, source='manual'",
                        (p.institute_id, student_id, body.date, body.present))
            extra = {"edited": {"date": str(body.date), "present": body.present}}
        else:
            cur.execute("SELECT weekly_off_day FROM institutes LIMIT 1")
            off = scoring.WEEKDAYS.index(cur.fetchone()["weekly_off_day"])
            lo = (asof - pd.Timedelta(days=body.window_days)).date()
            cur.execute("SELECT attendance_date FROM attendance WHERE student_id=%s AND attendance_date > %s AND attendance_date <= %s ORDER BY attendance_date",
                        (student_id, lo, asof.date()))
            days = [r["attendance_date"] for r in cur.fetchall()]
            if not days:  # no register rows in the window yet: create one per working day
                days = [lo + dt.timedelta(days=i + 1) for i in range(body.window_days) if (lo + dt.timedelta(days=i + 1)).weekday() != off]
            n = len(days)
            k = round(body.attendance_pct / 100 * n)
            vals = [(p.institute_id, student_id, d, ((i + 1) * k) // n > (i * k) // n, "manual") for i, d in enumerate(days)]
            psycopg2.extras.execute_values(cur, "INSERT INTO attendance (institute_id, student_id, attendance_date, present_flag, source) VALUES %s "
                                                "ON CONFLICT (student_id, attendance_date) DO UPDATE SET present_flag=EXCLUDED.present_flag, source='manual'", vals)
            extra = {"edited": {"window_days": body.window_days, "days": n, "present_days": k, "attendance_pct_now": round(100 * k / n, 1)}}
    return _after_edit(conn, p, sr, before, t0, extra)


# ---------------------------------------------------------------- fees
class FeeEdit(BaseModel):
    instalment_no: int = Field(..., ge=1, le=12)
    paid: bool | None = None
    paid_date: dt.date | None = None
    delay_days: int | None = Field(None, ge=0, le=365, description="mark paid this many days after the due date")
    amount_inr: float | None = Field(None, ge=0, description="scheduled instalment amount in rupees (cannot be negative)")
    paid_amount_inr: float | None = Field(None, ge=0)
    as_of: str | None = None

    @model_validator(mode="after")
    def _any(self):
        if all(v is None for v in (self.paid, self.paid_date, self.delay_days, self.amount_inr, self.paid_amount_inr)):
            raise ValueError("nothing to change: give paid, paid_date, delay_days, amount_inr or paid_amount_inr")
        return self


@router.patch("/students/{student_id}/fees")
def patch_fees(student_id: str, body: FeeEdit, p=Depends(MANAGE), conn=Depends(deps.tenant)):
    t0 = time.perf_counter()
    sr = _check_student(p, conn, student_id)
    asof = analytics.asof_ts(body.as_of)
    before = _standing(analytics.state(conn, p.institute_id, sr["batch_id"], body.as_of), student_id)
    with _rc(conn) as cur:
        cur.execute("SELECT id::text, due_date, amount_paise, paid_date, paid_amount_paise FROM fees WHERE student_id=%s AND instalment_no=%s", (student_id, body.instalment_no))
        f = cur.fetchone()
        if not f:
            raise HTTPException(404, f"instalment {body.instalment_no} does not exist for this student")
        amount = round(body.amount_inr * 100) if body.amount_inr is not None else f["amount_paise"]
        paid_date, paid_amt = f["paid_date"], f["paid_amount_paise"]
        if body.paid is False:
            paid_date, paid_amt = None, 0
        if body.delay_days is not None:
            paid_date = f["due_date"] + dt.timedelta(days=body.delay_days)
            paid_amt = amount if body.paid_amount_inr is None else paid_amt
        if body.paid is True and paid_date is None and body.paid_date is None:
            paid_date = min(asof.date(), f["due_date"])
        if body.paid_date is not None:
            paid_date = body.paid_date
            paid_amt = amount if paid_amt == 0 else paid_amt
        if body.paid_amount_inr is not None:
            paid_amt = round(body.paid_amount_inr * 100)
        if paid_amt > amount:
            raise HTTPException(422, "paid amount cannot exceed the instalment amount")
        if paid_date is not None and paid_amt == 0:
            raise HTTPException(422, "a paid date needs a paid amount above zero")
        cur.execute("UPDATE fees SET amount_paise=%s, paid_date=%s, paid_amount_paise=%s WHERE id=%s", (amount, paid_date, paid_amt, f["id"]))
    extra = {"edited": {"instalment_no": body.instalment_no, "amount_inr": amount / 100, "paid_date": str(paid_date) if paid_date else None,
                        "paid_amount_inr": paid_amt / 100}}
    return _after_edit(conn, p, sr, before, t0, extra)


# ---------------------------------------------------------------- answer key
class KeyEdit(BaseModel):
    key: str | None = Field(None, description="front-end form: 'A' or 'A|C'")
    accepted_answers: list[str] = Field(default_factory=list)
    numeric_tolerance: float = Field(0.0, ge=0)
    dropped: bool = False


@router.post("/answer-keys/{test_id}/{question_no}")
def fix_answer_key(test_id: str, question_no: int, body: KeyEdit, p=Depends(MANAGE), conn=Depends(deps.tenant)):
    t0 = time.perf_counter()
    if question_no < 1:
        raise HTTPException(422, "question number starts at 1")
    try:
        keys = scoring.latest_keys(conn, test_id)
    except psycopg2.errors.InvalidTextRepresentation:
        conn.rollback()
        raise HTTPException(422, "test id is not a valid uuid")
    if not len(keys):
        raise HTTPException(404, "test has no answer key (or does not exist)")
    row = keys[keys.position == question_no]
    if not len(row):
        raise HTTPException(404, f"question {question_no} is not in this test (1 to {int(keys.position.max())})")
    k = row.iloc[0]
    acc = [a.strip() for a in (body.accepted_answers or (body.key or "").split("|")) if a.strip()]
    if not body.dropped:
        if not acc:
            raise HTTPException(422, "give at least one accepted answer (or set dropped=true)")
        if k.q_type == "numeric":
            try:
                [float(a) for a in acc]
            except ValueError:
                raise HTTPException(422, "numeric question: accepted answers must be numbers")
        elif any(a.upper() not in ("A", "B", "C", "D") for a in acc):
            raise HTTPException(422, "option answers must be A, B, C or D")
        elif k.q_type == "mcq_single" and len(acc) > 1:
            raise HTTPException(422, "single-answer question: give exactly one option")
        acc = [a.upper() for a in acc] if k.q_type != "numeric" else acc
    before_flags = {f["question_id"] for f in flagged_for_test(conn, test_id) if f["status"] == "open"}
    with _rc(conn) as cur:
        cur.execute("SELECT batch_id::text, institute_id::text FROM tests WHERE id=%s", (test_id,))
        t = cur.fetchone()
        cur.execute("SELECT avg(raw_score) AS m FROM test_totals WHERE test_id=%s AND NOT absent_flag", (test_id,))
        mean_before = cur.fetchone()["m"]
        cur.execute("INSERT INTO answer_keys (institute_id, test_id, question_id, accepted_answers, numeric_tolerance, dropped, version, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (p.institute_id, test_id, k.question_id, acc, body.numeric_tolerance, body.dropped, int(k.version) + 1, p.user_id))
    rs = scoring.rescore_test(conn, test_id, [k.question_id])
    scoring.refresh_item_difficulty(conn, [k.question_id], config.MODEL_VERSION)
    with _rc(conn) as cur:
        cur.execute("SELECT avg(raw_score) AS m FROM test_totals WHERE test_id=%s AND NOT absent_flag", (test_id,))
        mean_after = cur.fetchone()["m"]
    audit(conn, p, "update_answer_key", "test_question", f"{test_id}:{question_no}")
    res = analytics.recompute(conn, p.institute_id, t["batch_id"])
    after_all = flagged_for_test(conn, test_id)
    after_flags = {f["question_id"] for f in after_all if f["status"] == "open"}
    return {"test_id": test_id, "question_no": question_no, "version": int(k.version) + 1, "previous_key": k.accepted, "new_key": acc,
            "rescore": rs, "mean_score_before": None if mean_before is None else round(float(mean_before), 2),
            "mean_score_after": None if mean_after is None else round(float(mean_after), 2),
            "flagged_before": k.question_id in before_flags, "flagged_after": k.question_id in after_flags,
            "recompute_seconds": round(time.perf_counter() - t0, 3), "batch_recompute_seconds": res["seconds"],
            "key": "|".join(acc), "rescored_students": rs["students_changed"], "recompute_ms": round((time.perf_counter() - t0) * 1000), "flagged": after_all}


# ---------------------------------------------------------------- privacy tier
TIERS = {"A": ("Test results only", "A"), "B": ("Tests + attendance", "AB"), "C": ("Tests + attendance + fees", "ABC"),
         "D": ("Tests + attendance + fees + engagement (adults with their own consent only)", "ABCD")}


class TierIn(BaseModel):
    tier: Literal["A", "B", "C", "D", "full", "academic_only"]
    minor_ml_risk_enabled: bool | None = None
    legal_opinion_ref: str | None = Field(None, max_length=200)
    batch_id: str | None = None


def _letter(t: str) -> str:
    return {"full": "D", "academic_only": "A"}.get(t, t)


def _tier_view(conn, p, res=None) -> dict:
    with _rc(conn) as cur:
        cur.execute("SELECT minor_ml_risk_enabled, active_feature_tier, legal_opinion_ref FROM legal_settings LIMIT 1")
        ls = dict(cur.fetchone())
    ab = analytics.ablation()
    with _rc(conn) as cur:
        cur.execute("SELECT COALESCE(sum(mentor_capacity_per_week),0) AS c FROM batches WHERE academic_year=%s", (config.CURRENT_YEAR,))
        cap = int(cur.fetchone()["c"]) or None
    fe = "academic_only" if ls["active_feature_tier"] == "A" else "full"
    lst = None
    try:
        r_ = analytics.state(conn, p.institute_id, None)
        lst = int(min(cap or 0, len(r_["scores"]))) if cap else int(len(r_["scores"]))
    except Exception:
        pass
    mt = lambda k: {m: round(ab[k][m], 4) for m in ("auc", "precision", "recall", "lead_time_days")}
    fe_extra = {"tier": fe, "minors_always_academic": not ls["minor_ml_risk_enabled"], "list_size": lst, "capacity_per_week": cap, "origin": "synthetic",
                "options": [{"tier": "full", "label_en": "Full: tests, attendance, fees, engagement (adults with own consent)", "label_hi": "पूर्ण: टेस्ट, उपस्थिति, फ़ीस, सहभागिता (सहमति वाले वयस्क)", "metrics": mt("ABCD")},
                            {"tier": "academic_only", "label_en": "Academic only: test results", "label_hi": "केवल शैक्षणिक: टेस्ट परिणाम", "metrics": mt("A")}]}
    return {**fe_extra, "active_tier": ls["active_feature_tier"], "minor_ml_risk_enabled": ls["minor_ml_risk_enabled"], "legal_opinion_ref": ls["legal_opinion_ref"],
            "tiers": {k: {"label": v[0], "model": v[1], **{m: round(ab[v[1]][m], 4) for m in ("auc", "precision", "recall", "lead_time_days")}} for k, v in TIERS.items()},
            "baselines": {"b2_ranked_attendance": {m: round(ab["B2_ranked_attendance"][m], 4) for m in ("auc", "precision", "recall")}},
            "ablation_note": "numbers are measured once, offline, on the 2026 synthetic test snapshots (capacity 5 % per institute); the list below is recomputed live",
            "rules": ["under-18 students: tier A only unless the institute records a legal opinion and enables minor risk ML; engagement (D) is never used for minors",
                      "adults: tiers up to the institute's active tier; D also needs the student's engagement_tracking consent"]}


@router.get("/settings/privacy-tier")
def get_tier(p=Depends(OWNER), conn=Depends(deps.tenant)):
    return _tier_view(conn, p)


@router.put("/settings/privacy-tier")
def put_tier(body: TierIn, p=Depends(OWNER), conn=Depends(deps.tenant)):
    t0 = time.perf_counter()
    if body.minor_ml_risk_enabled and not (body.legal_opinion_ref or "").strip():
        raise HTTPException(422, "enabling risk ML for minors requires legal_opinion_ref (document reference of the legal opinion)")
    with _rc(conn) as cur:
        cur.execute("SELECT minor_ml_risk_enabled, active_feature_tier FROM legal_settings LIMIT 1")
        old = dict(cur.fetchone())
        new_flag = old["minor_ml_risk_enabled"] if body.minor_ml_risk_enabled is None else body.minor_ml_risk_enabled
        cur.execute("UPDATE legal_settings SET active_feature_tier=%s, minor_ml_risk_enabled=%s, legal_opinion_ref=COALESCE(%s, legal_opinion_ref), updated_by=%s, updated_at=now()",
                    (_letter(body.tier), new_flag, body.legal_opinion_ref, p.user_id))
    audit(conn, p, "update_privacy_tier", "legal_settings", p.institute_id)
    analytics.bump(p.institute_id)
    out = _tier_view(conn, p)
    out["changed_from"] = old
    if body.batch_id:
        b = batch_or_404(conn, body.batch_id)
        res = analytics.recompute(conn, p.institute_id, body.batch_id)
        sl = analytics.support_list_json(res, deps.slug_of(p.institute_id), capacity=b["mentor_capacity_per_week"])
        out["support_list"] = sl
        sc = res["scores"]
        out["students_by_model"] = sc.model.value_counts().to_dict() if len(sc) else {}
    out["recompute_seconds"] = round(time.perf_counter() - t0, 3)
    return out


# ---------------------------------------------------------------- reports (P6)
class ReportIn(BaseModel):
    lang: Literal["hi", "en"] | None = None
    language: Literal["hi", "en"] | None = None
    use_llm: bool | None = Field(None, description="null: use the local model only if Ollama runs and the model is pulled; false: template only")


@router.post("/students/{student_id}/reports", status_code=201)
def make_report(student_id: str, body: ReportIn, p=Depends(deps.current_principal), conn=Depends(deps.tenant)):
    if p.role in ("student",):
        raise HTTPException(403, "role 'student' may not generate parent reports")
    sr = _check_student(p, conn, student_id)
    with _rc(conn) as cur:
        cur.execute("SELECT 1 FROM consents WHERE student_id=%s AND purpose='parent_reports' AND revoked_at IS NULL", (student_id,))
        if not cur.fetchone():
            raise HTTPException(403, "no active parent_reports consent for this student: reports are not generated without it")
    lang = body.language or body.lang or "hi"
    out = reports.generate(conn, p.institute_id, deps.slug_of(p.institute_id), student_id, lang, use_llm=body.use_llm)
    out["llm_requested"] = bool(body.use_llm)
    out["llm_available"] = out["ollama_model_available"] is not None
    out["fallback_used"] = out["source"] != "llm" and bool(body.use_llm)
    out["fallback_reason"] = out["fallback_reason"] or (None if out["source"] == "llm" else ("model not installed or Ollama not running" if body.use_llm else None))
    with _rc(conn) as cur:
        cur.execute("INSERT INTO reports (institute_id, student_id, period, lang, numbers_json, content, verified, path, model_version, sent_via) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'none') RETURNING id::text",
                    (p.institute_id, student_id, out["month"], lang, json.dumps(out["numbers_json"]), out["body"], True, out["source"], config.MODEL_VERSION))
        out["id"] = cur.fetchone()["id"]
    audit(conn, p, "generate_report", "student", student_id)
    return out


# ---------------------------------------------------------------- interventions (supportive actions log)
class InterventionIn(BaseModel):
    type: Literal["mentoring", "counselling_referral", "remedial_session", "fee_plan_discussion", "parent_call"]
    due_date: dt.date
    outcome: Literal["pending", "completed_improved", "completed_no_change", "escalated_to_counsellor", "parent_unreachable", "declined"] = "pending"


@router.post("/students/{student_id}/interventions", status_code=201)
def add_intervention(student_id: str, body: InterventionIn, p=Depends(deps.require(*deps.STAFF)), conn=Depends(deps.tenant)):
    _check_student(p, conn, student_id)
    with _rc(conn) as cur:
        cur.execute("INSERT INTO interventions (institute_id, student_id, type, owner_user_id, due_date, outcome, done_at) VALUES (%s,%s,%s,%s,%s,%s, CASE WHEN %s='pending' THEN NULL ELSE now() END) RETURNING id::text",
                    (p.institute_id, student_id, body.type, p.user_id, body.due_date, body.outcome, body.outcome))
        iid = cur.fetchone()["id"]
    audit(conn, p, "create_intervention", "student", student_id)
    return {"id": iid, "student_id": student_id, **body.model_dump(mode="json")}


@router.get("/students/{student_id}/interventions")
def list_interventions(student_id: str, p=Depends(deps.require(*deps.STAFF)), conn=Depends(deps.tenant)):
    _check_student(p, conn, student_id)
    with _rc(conn) as cur:
        cur.execute("SELECT id::text, type, due_date, outcome, done_at, created_at FROM interventions WHERE student_id=%s ORDER BY created_at DESC", (student_id,))
        return {"interventions": [{**dict(r), "due_date": str(r["due_date"]), "done_at": r["done_at"].isoformat() if r["done_at"] else None,
                                   "created_at": r["created_at"].isoformat()} for r in cur.fetchall()]}
