"""Student, parent and owner views built from the DB + cached batch state (artifact-shaped JSON)."""
from __future__ import annotations

import datetime as dt
import json

import numpy as np
import pandas as pd
import psycopg2.extras

from .. import config
from ..db import pg
from . import analytics
from .analytics import env, qdf, topics


class NotFound(Exception):
    pass


def student_row(conn, sid: str) -> dict:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT s.id::text, s.batch_id::text, s.roll_no, s.name, s.dob, s.join_date, s.status, s.institute_id::text, "
                    "b.exam, b.class_level, b.name AS batch_name FROM students s JOIN batches b ON b.id=s.batch_id WHERE s.id=%s", (sid,))
        r = cur.fetchone()
    if not r:
        raise NotFound(sid)
    return dict(r)


def _band_headline(trend: str):
    return {"improving": ("You are improving. Keep going", "आप सुधार कर रहे हैं, ऐसे ही चलते रहें"),
            "steady": ("Steady progress this month", "इस महीने स्थिर प्रगति रही"),
            "declining": ("Let us look at a few topics together", "आइए कुछ विषय साथ मिलकर देखें")}[trend]


def student_facts(conn, institute_id: str, sid: str, asof: str | None = None) -> dict:
    """Everything the student/parent/report views need for one student (uses the cached batch state)."""
    sr = student_row(conn, sid)
    res = analytics.state(conn, institute_id, sr["batch_id"], asof)
    ts = res["as_of"]
    T = topics()
    c = res["cells"]
    c = c[c.student_id == sid].copy()
    c["subject"] = c.topic_id.map(lambda t: T.get(t, {}).get("subject", ""))
    rr = qdf(conn, "SELECT r.is_correct::int AS y, ts.test_date, q.subject FROM responses r JOIN tests ts ON ts.id=r.test_id "
                   "JOIN questions q ON q.id=r.question_id JOIN question_topics qt ON qt.question_id=r.question_id "
                   "WHERE r.student_id=%s AND r.status='answered' AND ts.test_date <= %s", (sid, ts.date()))
    if len(rr):
        rr["test_date"] = pd.to_datetime(rr.test_date)
    subj = []
    for sj, g in c[c.n >= 3].groupby("subject"):
        rs = rr[rr.subject == sj].sort_values("test_date") if len(rr) else rr
        ch = np.array_split(rs.y.values, 4) if len(rs) >= 8 else []
        subj.append({"subject": sj.lower(), "theta": round(float(g.theta.mean()), 2),
                     "trend": [round(float(x.mean()), 2) for x in ch if len(x)]})
    cc = c[c.n >= 5].sort_values("theta")
    weak, strong = cc.head(3), cc.tail(3)
    t_s = res["tt"][(res["tt"].student_id == sid)].sort_values("test_date").tail(3)
    att_all = qdf(conn, "SELECT attendance_date, present_flag::int AS flag FROM attendance WHERE student_id=%s AND attendance_date <= %s", (sid, ts.date()))
    att_pct, streak = 0.0, 0
    if len(att_all):
        att_all["attendance_date"] = pd.to_datetime(att_all.attendance_date)
        a30 = att_all[att_all.attendance_date > ts - pd.Timedelta(days=30)]
        att_pct = round(float(a30.flag.mean() * 100), 1) if len(a30) else 0.0
        wk = att_all.set_index("attendance_date").flag.resample("W").mean()
        for v in wk.values[::-1]:
            if v >= 0.6:
                streak += 1
            else:
                break
    trend = "steady"
    if len(t_s) >= 2:
        d_ = t_s.pct.iloc[-1] - t_s.pct.iloc[0]
        trend = "improving" if d_ > 0.03 else ("declining" if d_ < -0.03 else "steady")
    pr = res["prange"].loc[sid] if sid in res["prange"].index else None
    return {"sr": sr, "res": res, "cells": c, "weak": weak, "strong": strong, "subj": subj, "scores": t_s,
            "att_pct": att_pct, "streak": streak, "trend": trend, "prange": pr, "asof": ts,
            "tests_taken": int(((res["tt"].student_id == sid) & (res["tt"].test_date <= ts)).sum())}


def student_profile(conn, institute_id: str, slug: str, sid: str, asof: str | None = None) -> dict:
    f = student_facts(conn, institute_id, sid, asof)
    sr, T = f["sr"], topics()
    ts = f["asof"]
    age_class = "adult" if (ts - pd.Timestamp(sr["dob"])).days / 365.25 >= 18 else "minor"
    item = lambda r_: {"topic_id": r_.topic_id, "name_en": T.get(r_.topic_id, {}).get("name_en", r_.topic_id),
                       "name_hi": T.get(r_.topic_id, {}).get("name_hi", r_.topic_id)}
    plan = []
    for d_, w in zip(["Mon", "Wed", "Fri"], f["weak"].itertuples()):
        tn = T.get(w.topic_id, {})
        plan.append({"day": d_, "task_en": f"20 questions on {tn.get('name_en', w.topic_id)}",
                     "task_hi": f"{tn.get('name_hi', w.topic_id)} के 20 प्रश्न", "minutes": 40})
    head = _band_headline(f["trend"])
    pr = f["prange"]
    prange = ({"low": float(pr.low), "mid": float(pr.mid), "high": float(pr.high), "assumption": True} if pr is not None else None)
    streak = f["streak"]
    return {"student_id": sid, "display_name": sr["name"].split()[0], "roll_no": sr["roll_no"], "age_class": age_class,
            "exam": sr["exam"], "language_pref": "hi", "streak_weeks": streak,
            "headline": {"text_en": head[0], "text_hi": head[1]}, "mastery_by_subject": f["subj"],
            "strengths": [item(r_) for r_ in f["strong"].itertuples()],
            "focus_topics": [{**item(r_), "why_en": "Lower accuracy than your other topics", "est_minutes": 40} for r_ in f["weak"].itertuples()],
            "study_plan": plan,
            "score_trend": [{"test": r_.test_name[:6], "marks": float(r_.raw_score)} for r_ in f["scores"].itertuples()],
            "percentile_range": prange,
            "milestones": ([{"id": "m1", "text_en": f"{streak} weeks of regular attendance", "text_hi": f"{streak} सप्ताह नियमित उपस्थिति"}] if streak >= 2 else []),
            "support_contact": {"counsellor_available": True, "text_en": "Talk to your counsellor any time", "text_hi": "कभी भी काउंसलर से बात करें"},
            "trend_note": "trend values are share of correct answers in four time chunks"}


def student_envelope(conn, institute_id, slug, sid, asof=None) -> dict:
    return {**env("student/1", slug, "model"), "students": [student_profile(conn, institute_id, slug, sid, asof)]}


def parent_view(conn, institute_id: str, slug: str, sid: str, asof: str | None = None) -> dict:
    from . import reports

    f = student_facts(conn, institute_id, sid, asof)
    ts = f["asof"]
    T = topics()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT name, lang_pref FROM guardians WHERE student_id=%s ORDER BY created_at LIMIT 1", (sid,))
        g = cur.fetchone()
        cur.execute("SELECT verification_method, verified_at, revoked_at FROM consents WHERE student_id=%s ORDER BY verified_at LIMIT 1", (sid,))
        c = cur.fetchone()
        cur.execute("SELECT due_date, amount_paise FROM fees WHERE student_id=%s AND due_date > %s ORDER BY due_date LIMIT 1", (sid, ts.date()))
        fee = cur.fetchone()
    fee_ = ({"next_due_date": str(fee["due_date"]), "amount_inr": float(fee["amount_paise"]) / 100, "status": "on_track"}
            if fee else {"next_due_date": None, "amount_inr": None, "status": "none_due"})
    rep = {lg: reports.generate(conn, institute_id, slug, sid, lg, use_llm=False) for lg in ("hi", "en")}
    sc = [float(x) for x in f["scores"].raw_score]
    msgs = [{"id": "w1", "type": "monthly_report", "sent_at": f"{ts.date()}T09:00:00Z", "status": "read",
             "body_hi": rep["hi"]["body"], "body_en": rep["en"]["body"], "has_pdf": True, "verified": True}]
    if fee_["next_due_date"]:
        msgs.append({"id": "w2", "type": "fee_reminder", "sent_at": f"{ts.date()}T09:30:00Z", "status": "delivered",
                     "body_hi": f"अगली किस्त {fee_['next_due_date']} को देय है।",
                     "body_en": f"The next instalment is due on {fee_['next_due_date']}.", "has_pdf": False, "verified": True})
    pdata = {"student_id": sid, "guardian_display": g["name"] if g else "Guardian", "language": g["lang_pref"] if g else "hi",
             "channel": "whatsapp",
             "consent": {"verified": bool(c and c["verified_at"] and not c["revoked_at"]),
                         "method": c["verification_method"] if c else "unknown",
                         "date": str(c["verified_at"])[:10] if c and c["verified_at"] else None},
             "monthly_summary": {"month": ts.strftime("%Y-%m"), "attendance_pct": f["att_pct"], "tests_taken": f["tests_taken"],
                                 "marks_trend": sc,
                                 "strongest_topic": T.get(f["strong"].topic_id.iloc[-1], {}).get("name_en") if len(f["strong"]) else None,
                                 "focus_topic": T.get(f["weak"].topic_id.iloc[0], {}).get("name_en") if len(f["weak"]) else None,
                                 "fee": fee_,
                                 "what_you_can_do": [{"text_en": "Ask your child to explain one solved question", "text_hi": "बच्चे से एक हल किया प्रश्न समझाने को कहें"}],
                                 "next_meeting": None},
             "whatsapp_messages": msgs,
             "notification_prefs": {"monthly_report": True, "fee_reminder": True, "meeting_invite": True, "quiet_hours": "21:00-08:00"},
             "faq": [{"q_en": "How is my child doing compared with others?",
                      "a_en": "We do not compare children. Reports show your child's own progress.",
                      "a_hi": "हम बच्चों की तुलना नहीं करते। रिपोर्ट आपके बच्चे की अपनी प्रगति दिखाती है।"}]}
    return {**env("parent/1", slug, "model"), "parents": [pdata]}


# ---------------------------------------------------------------- owner
def owner_dashboard(conn, institute_id: str, slug: str, asof: str | None = None) -> dict:
    ts = analytics.asof_ts(asof)
    rng = np.random.default_rng(42)
    tt = analytics.qdf(conn, "SELECT s.batch_id::text AS batch_id, t.student_id::text AS student_id, t.raw_score / ts.max_marks AS pct "
                             "FROM test_totals t JOIN tests ts ON ts.id=t.test_id JOIN students s ON s.id=t.student_id "
                             "WHERE NOT t.absent_flag AND t.raw_score IS NOT NULL AND ts.test_date <= %s", (ts.date(),))
    bc = []
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT id::text, name, published_capacity, mentor_capacity_per_week FROM batches WHERE academic_year=%s ORDER BY name", (config.CURRENT_YEAR,))
        batches = cur.fetchall()
        cur.execute("SELECT date_trunc('month', left_date)::date AS m, count(*) AS n FROM students WHERE left_date IS NOT NULL AND left_date <= %s GROUP BY 1 ORDER BY 1", (ts.date(),))
        monthly = cur.fetchall()
        cur.execute("SELECT count(*) AS n FROM students")
        enrolled = cur.fetchone()["n"]
        cur.execute("SELECT count(*) AS n FROM tests WHERE day_after_off_warning")
        off_warn = cur.fetchone()["n"]
        cur.execute("SELECT count(*) AS n FROM students WHERE join_date < (dob + interval '16 years')")
        under16 = cur.fetchone()["n"]
        cur.execute("SELECT purpose, count(*) FILTER (WHERE revoked_at IS NULL) AS active, count(*) FILTER (WHERE revoked_at IS NOT NULL) AS revoked FROM consents GROUP BY purpose ORDER BY purpose")
        cons = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT minor_ml_risk_enabled, active_feature_tier FROM legal_settings LIMIT 1")
        legal = dict(cur.fetchone())
    for B in batches:
        x = tt[tt.batch_id == B["id"]].groupby("student_id").pct.mean().values
        if len(x) >= 3:
            s = [np.mean(x[rng.integers(0, len(x), len(x))]) for _ in range(300)]
            lo, hi = float(np.percentile(s, 2.5)), float(np.percentile(s, 97.5))
        else:
            lo = hi = float("nan")
        bc.append({"batch_id": B["id"], "metric": "mean_test_score_pct", "value": float(np.mean(x)) if len(x) else None,
                   "ci_low": None if lo != lo else lo, "ci_high": None if hi != hi else hi, "n": int(len(x)), "enough_data": bool(len(x) >= 30)})
    by_reason = {}
    p = config.ARTIFACTS / slug / "owner.json"
    if p.exists():
        by_reason = json.loads(p.read_text(encoding="utf-8")).get("retention", {}).get("by_reason", {})
    roi = {"fees_protected_inr": None, "staff_hours": None, "cost_inr": None, "ratio_low": 0.35, "ratio_base": 0.55,
           "ratio_high": 1.7, "origin": "assumption",
           "note": "low = fees only, base = fees + staff time, high = all benefits; from financial model v1.1 (not recomputed here)"}
    return {**env("owner/1", slug, "synthetic"), "batch_compare": bc,
            "faculty_compare": [], "faculty_note": "Faculty is not in the data schema; comparison is by batch only.",
            "retention": {"monthly": [{"month": str(m["m"])[:7], "enrolled": int(enrolled), "dropped": int(m["n"])} for m in monthly],
                          "by_reason": by_reason,
                          "by_reason_note": "reasons come from the synthetic ground-truth file; they are not stored in the application database"},
            "roi": roi,
            "compliance": {"tests_day_after_weekly_off": int(off_warn), "students_enrolled_under_16": int(under16),
                           "consents_by_purpose": cons, "legal": legal,
                           "batches_over_published_capacity": [b["name"] for b in batches
                                                               if len(tt[tt.batch_id == b["id"]].student_id.unique()) > b["published_capacity"]]},
            "as_of": str(ts.date())}
