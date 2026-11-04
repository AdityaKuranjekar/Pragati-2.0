"""Batch analytics: load a batch from the tenant DB, run the saved models, cache, persist, and shape the JSON
the front end uses (same shapes as ml/artifacts/<institute>/*.json).

Everything here is inference only. A cold batch recompute is one SQL pass plus Rasch Newton steps and three
LightGBM predicts; results are cached per (institute, batch, as_of) and the cache is dropped by any write.
"""
from __future__ import annotations

import datetime as dt
import functools
import io
import json
import threading
import time

import numpy as np
import pandas as pd
import psycopg2.extras
import yaml

from .. import config
from ..ml import irt, percentile, risk

_cache: dict[tuple, dict] = {}
_cache_lock = threading.Lock()
_versions: dict[str, int] = {}


def bump(institute_id: str) -> None:
    """Called by every write path: invalidates cached results of this institute."""
    with _cache_lock:
        _versions[institute_id] = _versions.get(institute_id, 0) + 1
        for k in [k for k in _cache if k[0] == institute_id]:
            _cache.pop(k, None)


# ---------------------------------------------------------------- helpers
def qdf(conn, sql: str, params: tuple = ()) -> pd.DataFrame:
    """Fast query to DataFrame through COPY (3-5x quicker than fetchall for 100k+ rows)."""
    with conn.cursor() as cur:
        q = cur.mogrify(sql, params).decode()
        buf = io.StringIO()
        cur.copy_expert(f"COPY ({q}) TO STDOUT WITH (FORMAT csv, HEADER true)", buf)
    buf.seek(0)
    return pd.read_csv(buf, dtype_backend="numpy_nullable", true_values=["t"], false_values=["f"]) if buf.getvalue() else pd.DataFrame()


@functools.lru_cache(maxsize=1)
def topics() -> dict[str, dict]:
    y = yaml.safe_load(open(config.CONTRACTS / "topics.yaml", encoding="utf-8"))["topics"]
    return {t["id"]: t for t in y}


def asof_ts(asof: str | None = None) -> pd.Timestamp:
    return pd.Timestamp(asof or config.ASOF_NOW)


def _age_years(dob: pd.Series, asof: pd.Timestamp) -> pd.Series:
    return (asof - dob).dt.days / 365.25


# ---------------------------------------------------------------- data load
def load(conn, institute_id: str, batch_id: str | None, asof: pd.Timestamp) -> dict:
    where = "s.batch_id = %s" if batch_id else "TRUE"
    args: tuple = (batch_id,) if batch_id else ()
    st = qdf(conn, f"SELECT s.id::text AS id, s.roll_no, s.name, s.dob, s.join_date, s.left_date, s.status, s.batch_id::text AS batch_id "
                   f"FROM students s WHERE {where}", args)
    for c in ("dob", "join_date", "left_date"):
        st[c] = pd.to_datetime(st[c])
    a0 = (asof - pd.Timedelta(days=60)).date()
    att = qdf(conn, f"SELECT a.student_id::text AS student_id, a.attendance_date, a.present_flag::int AS flag FROM attendance a "
                    f"JOIN students s ON s.id=a.student_id WHERE {where} AND a.attendance_date <= %s AND a.attendance_date > %s",
              args + (asof.date(), a0))
    att["attendance_date"] = pd.to_datetime(att.attendance_date)
    tt = qdf(conn, f"SELECT t.student_id::text AS student_id, ts.test_date, ts.exam_pattern_code, ts.name AS test_name, t.test_id::text AS test_id, "
                   f"t.raw_score / ts.max_marks AS pct, t.raw_score FROM test_totals t JOIN tests ts ON ts.id=t.test_id "
                   f"JOIN students s ON s.id=t.student_id WHERE {where} AND NOT t.absent_flag AND t.raw_score IS NOT NULL", args)
    tt["test_date"] = pd.to_datetime(tt.test_date)
    fees = qdf(conn, f"SELECT f.student_id::text AS student_id, f.due_date, f.paid_date, f.amount_paise FROM fees f "
                     f"JOIN students s ON s.id=f.student_id WHERE {where}", args)
    for c in ("due_date", "paid_date"):
        fees[c] = pd.to_datetime(fees[c])
    eng = qdf(conn, f"SELECT e.student_id::text AS student_id, e.activity_date, e.doubts_asked, e.homework_submitted::int AS homework_submitted "
                    f"FROM engagement e JOIN students s ON s.id=e.student_id WHERE {where} AND e.activity_date <= %s AND e.activity_date > %s",
              args + (asof.date(), (asof - pd.Timedelta(days=30)).date()))
    eng["activity_date"] = pd.to_datetime(eng.activity_date)
    resp = qdf(conn, f"SELECT r.student_id::text AS student_id, r.question_id::text AS question_id, qt.topic_id, r.is_correct::int AS y "
                     f"FROM responses r JOIN students s ON s.id=r.student_id JOIN question_topics qt ON qt.question_id=r.question_id "
                     f"WHERE {where} AND r.status='answered'", args)
    items = qdf(conn, "SELECT question_id::text AS question_id, b FROM item_params")
    cons = qdf(conn, f"SELECT c.student_id::text AS student_id, c.purpose FROM consents c JOIN students s ON s.id=c.student_id "
                     f"WHERE {where} AND c.revoked_at IS NULL", args)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT minor_ml_risk_enabled, active_feature_tier FROM legal_settings LIMIT 1")
        legal = cur.fetchone() or {"minor_ml_risk_enabled": False, "active_feature_tier": "D"}
        if batch_id:
            cur.execute("SELECT id::text, name, exam, class_level, mentor_capacity_per_week, published_capacity FROM batches WHERE id=%s", (batch_id,))
        else:
            cur.execute("SELECT id::text, name, exam, class_level, mentor_capacity_per_week, published_capacity FROM batches WHERE academic_year=%s", (config.CURRENT_YEAR,))
        batches = [dict(r) for r in cur.fetchall()]
    return {"students": st, "att": att, "tt": tt, "fees": fees, "eng": eng, "resp": resp,
            "b": dict(zip(items.question_id, items.b)), "consents": cons, "legal": dict(legal), "batches": batches}


# ---------------------------------------------------------------- compute
def compute(conn, institute_id: str, batch_id: str | None, asof: str | None = None,
            enforce_consent: bool = True, tier_override: str | None = None) -> dict:
    t0 = time.perf_counter()
    ts = asof_ts(asof)
    D = load(conn, institute_id, batch_id, ts)
    t_load = time.perf_counter() - t0
    st = D["students"]
    legal = D["legal"]
    tier = tier_override or legal["active_feature_tier"]

    # ---- mastery
    cells = irt.add_bands(irt.fit_cells(D["resp"], D["b"]))

    # ---- risk
    elig = st[(st.join_date <= ts - pd.Timedelta(days=60)) & ~(st.left_date <= ts)].copy()
    att, tt = D["att"], D["tt"]
    X = risk.snapshot_features(ts, elig.id.values, att, tt, D["fees"], D["eng"])
    elig = elig.set_index("id")
    elig["is_minor"] = _age_years(elig.dob, ts) < 18
    cons = D["consents"]
    ok_core = set(cons[cons.purpose == "analytics"].student_id) & set(cons[cons.purpose == "risk_alerts"].student_id)
    ok_eng = set(cons[cons.purpose == "engagement_tracking"].student_id)
    elig["consent_ok"] = [sid in ok_core for sid in elig.index] if enforce_consent else True
    elig["eng_ok"] = [sid in ok_eng for sid in elig.index] if enforce_consent else True
    scored_ids = elig.index[elig.consent_ok]
    models = pd.Series({sid: risk.model_for(bool(elig.at[sid, "is_minor"]), bool(legal["minor_ml_risk_enabled"]), tier,
                                            bool(elig.at[sid, "eng_ok"])) for sid in scored_ids}, dtype=object)
    scores = risk.score_students(X, models) if len(models) else pd.DataFrame(columns=["model", "p", "contrib"])

    # ---- percentile
    F = percentile.features(tt, ts)
    F = F[F.index.isin(set(st.id))]
    prange = percentile.predict_range(F)

    return {"as_of": ts, "students": st, "elig": elig, "X": X, "scores": scores, "cells": cells, "prange": prange,
            "legal": legal, "tier": tier, "batches": D["batches"], "tt": tt, "att": att, "fees": D["fees"],
            "resp_rows": len(D["resp"]), "seconds_load": round(t_load, 3),
            "seconds": round(time.perf_counter() - t0, 3), "excluded_no_consent": int((~elig.consent_ok).sum())}


def state(conn, institute_id: str, batch_id: str | None, asof: str | None = None, **kw) -> dict:
    key = (institute_id, batch_id, asof or config.ASOF_NOW, tuple(sorted(kw.items())))
    with _cache_lock:
        hit = _cache.get(key)
        ver = _versions.get(institute_id, 0)
    if hit is not None:
        return hit
    res = compute(conn, institute_id, batch_id, asof, **kw)
    with _cache_lock:
        if _versions.get(institute_id, 0) == ver:
            _cache[key] = res
    return res


def recompute(conn, institute_id: str, batch_id: str, asof: str | None = None) -> dict:
    """Invalidate, recompute synchronously, persist results to mastery_snapshots / risk_scores / predictions."""
    bump(institute_id)
    res = state(conn, institute_id, batch_id, asof)
    t0 = time.perf_counter()
    persist(conn, institute_id, res)
    res["seconds_persist"] = round(time.perf_counter() - t0, 3)
    return res


def persist(conn, institute_id: str, res: dict) -> None:
    sids = list(res["students"].id)
    if not sids:
        return
    asof = res["as_of"].date()
    now = dt.datetime.now(dt.timezone.utc)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM mastery_snapshots WHERE student_id = ANY(%s::uuid[])", (sids,))
        cur.execute("DELETE FROM risk_scores WHERE student_id = ANY(%s::uuid[]) AND as_of=%s", (sids, asof))
        cur.execute("DELETE FROM predictions WHERE student_id = ANY(%s::uuid[]) AND as_of=%s", (sids, asof))
        c = res["cells"]
        if len(c):
            rows = [(institute_id, r.student_id, r.topic_id, float(r.theta), float(r.se),
                     "building" if r.band == "needs_support" else r.band, int(r.n), now, config.MODEL_VERSION)
                    for r in c.itertuples() if r.topic_id in topics()]
            psycopg2.extras.execute_values(cur, "INSERT INTO mastery_snapshots (institute_id, student_id, topic_id, theta, se, band, n_items, computed_at, model_version) VALUES %s", rows, page_size=5000)
        sc = res["scores"]
        if len(sc):
            ranked = sc.p.rank(ascending=False, method="first")
            cap = max(1, sum(b["mentor_capacity_per_week"] for b in res["batches"]))
            rows = []
            for sid, r in sc.iterrows():
                rk = ranked[sid]
                band = "needs_support" if rk <= cap else ("watch" if rk <= 2 * cap else "low")
                reasons, _ = risk.reasons_for(r.contrib)
                rows.append((institute_id, sid, asof, "academic_support" if r.model == "A" else "retention", "ml", float(r.p), band,
                             json.dumps(reasons, ensure_ascii=False), r.model[-1], config.MODEL_VERSION))
            psycopg2.extras.execute_values(cur, "INSERT INTO risk_scores (institute_id, student_id, as_of, target, routing_method, p, band, reasons, feature_tier, model_version) VALUES %s", rows, page_size=2000)
        pr = res["prange"]
        if len(pr):
            rows = [(institute_id, sid, asof, float(r.low), float(r.mid), float(r.high), float(r.low), float(r.high), 0.8, config.MODEL_VERSION)
                    for sid, r in pr.iterrows()]
            psycopg2.extras.execute_values(cur, "INSERT INTO predictions (institute_id, student_id, as_of, q10, q50, q90, mapped_low, mapped_high, coverage_level, model_version) VALUES %s", rows, page_size=2000)


# ---------------------------------------------------------------- JSON shapes
def env(schema: str, slug: str, origin: str) -> dict:
    return {"schema": schema, "model_version": config.MODEL_VERSION,
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
            "generator_seed": 42, "institute_id": slug, "origin": origin}


@functools.lru_cache(maxsize=1)
def ablation() -> dict:
    return json.loads((config.MODELS_DIR / "risk_ablation.json").read_text(encoding="utf-8"))


def heatmap_json(res: dict, slug: str, batch_id: str, top_topics: int = 25, flags: list | None = None) -> dict:
    cells = res["cells"]
    st = res["students"]
    b = res["batches"][0] if res["batches"] else {}
    T = topics()
    topn = cells.groupby("topic_id").n.sum().nlargest(top_topics).index if len(cells) else []
    cs = cells[cells.topic_id.isin(set(topn))]
    med = cells.groupby("topic_id").n.median() if len(cells) else {}
    tl = [{"topic_id": t, "name_en": T.get(t, {}).get("name_en", t), "name_hi": T.get(t, {}).get("name_hi", t),
           "subject": T.get(t, {}).get("subject", ""), "probably_untaught": bool(med[t] < 3)} for t in topn]
    active = st[st.status == "active"].sort_values("roll_no")
    return {**env("mastery/1", slug, "model"), "topics": tl,
            "batches": [{"batch_id": batch_id, "name": b.get("name"), "exam": b.get("exam"), "class_level": b.get("class_level"),
                         "student_ids": active.id.tolist()}],
            "students": [{"student_id": r.id, "roll_no": r.roll_no, "name": r.name} for r in active.itertuples()],
            "cells": [{"student_id": r.student_id, "topic_id": r.topic_id, "theta": round(float(r.theta), 3),
                       "se": round(float(r.se), 3), "band": r.band} for r in cs.itertuples()],
            "wrong_key_flags": flags or [], "as_of": str(res["as_of"].date()), "recompute_seconds": res["seconds"]}


def _track(model: str, is_minor: bool) -> str:
    """academic_support: tier A only. full: adults with more than tier A. retention_minor_opt_in: a minor, only when the institute
    recorded a legal opinion (never includes engagement)."""
    if model == "A":
        return "academic_support"
    return "retention_minor_opt_in" if is_minor else "full"


def support_list_json(res: dict, slug: str, capacity: int | None = None) -> dict:
    sc = res["scores"]
    elig = res["elig"]
    cap = capacity or max(1, sum(b["mentor_capacity_per_week"] for b in res["batches"]))
    top = sc.sort_values("p", ascending=False).head(cap) if len(sc) else sc
    lst = []
    for i, (sid, r) in enumerate(top.iterrows()):
        reasons, action = risk.reasons_for(r.contrib)
        lst.append({"student_id": sid, "week": str(res["as_of"].date()), "priority_slot": i + 1,
                    "track": _track(r.model, bool(elig.at[sid, "is_minor"])), "reasons": reasons,
                    "supportive_action": action, "consent_ok": bool(elig.at[sid, "consent_ok"]),
                    "p": round(float(r.p), 4), "model": r.model, "roll_no": None})
    names = res["students"].set_index("id")
    for it in lst:
        it["roll_no"] = names.at[it["student_id"], "roll_no"]
        it["name"] = names.at[it["student_id"], "name"]
    ab = ablation()
    best = ab["ABCD"]
    return {**env("risk/1", slug, "model"), "capacity_per_week": cap,
            "operating_point": {k: best[k] for k in ("precision", "recall", "lead_time_days")},
            "list": lst,
            "baselines": {"b2_ranked_rule": {k: ab["B2_ranked_attendance"][k] for k in ("precision", "recall")},
                          "model": {k: best[k] for k in ("precision", "recall")},
                          "b1_attendance_rule": ab.get("B1_attendance_rule", {"precision": None, "recall": None})},
            "as_of": str(res["as_of"].date()), "feature_tier_active": res["tier"],
            "excluded_no_consent": res["excluded_no_consent"], "scored": int(len(sc)),
            "minors_on_full_track": int(sum(1 for it in lst if it["track"] == "full" and elig.at[it["student_id"], "is_minor"])),
            "recompute_seconds": res["seconds"],
            "note": "operating point is pooled over 4 institutes, 2026 test snapshots; list is capped at the batch's mentor capacity"}


def percentile_json(res: dict, slug: str, batch: dict | None) -> dict:
    meta = percentile.meta()
    mp = json.loads((config.MODELS_DIR / "percentile_mapping.json").read_text(encoding="utf-8"))
    pr = res["prange"]
    exam = (batch or {}).get("exam", "jee_main")
    return {**env("percentile/1", slug, "assumption"), "coverage_target": 0.8,
            "students": [{"student_id": sid, "exam": exam, "low": float(r.low), "mid": float(r.mid), "high": float(r.high),
                          "mapping_table_id": mp["id"], "assumption": True} for sid, r in pr.iterrows()],
            "mapping_table": mp["table"],
            "calibration": {"empirical_coverage": meta["empirical_coverage_2026"], "mean_width": 2 * meta["halfwidth"]},
            "note": "marks column is mean mock score in % of max; mapping learned on synthetic outcomes, not the NTA table",
            "as_of": str(res["as_of"].date())}
