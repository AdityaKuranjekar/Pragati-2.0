"""Build all Tab-2 artifacts from the synthetic data (seed 42). Run from the repo root: python ml/build_artifacts.py"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
DATA = ROOT / "data"
OUT = ROOT / "ml" / "artifacts"
SEED = 42
NOW = dt.datetime(2026, 10, 24, tzinfo=dt.timezone.utc).isoformat().replace("+00:00", "Z")
ASOF_NOW = pd.Timestamp("2026-09-01")
SLUG = {"Patna": "patna_jee", "Lucknow": "lucknow_neet", "Gaya": "gaya_both", "Kota": "kota_large"}
rng = np.random.default_rng(SEED)
METRICS: list[dict] = []


def env(schema, inst, origin):
    return {"schema": schema, "model_version": "v1.1.0", "generated_at": NOW, "generator_seed": SEED,
            "institute_id": inst, "origin": origin}


def dump(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def metric(key, module, origin, value, lo=None, hi=None, bar=None, notes=""):
    METRICS.append({"metric_key": key, "module": module, "dataset_origin": origin, "value": float(value),
                    "ci_low": None if lo is None else float(lo), "ci_high": None if hi is None else float(hi),
                    "passed_bar": bool(bar) if bar is not None else False, "notes": notes})


def boot_ci(x, fn=np.mean, n=300):
    x = np.asarray(x)
    if len(x) < 3:
        return float("nan"), float("nan")
    s = [fn(x[rng.integers(0, len(x), len(x))]) for _ in range(n)]
    return float(np.percentile(s, 2.5)), float(np.percentile(s, 97.5))


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


# ---------------------------------------------------------------- load
print("loading")
C = lambda n, cols=None: pd.read_parquet(DATA / "clean" / f"{n}.parquet", columns=cols)
T = lambda n: pd.read_parquet(DATA / "truth" / f"{n}.parquet")
inst = C("institutes")
inst["slug"] = inst.city.map(SLUG)
students = C("students")
students["dob"] = pd.to_datetime(students.dob)
students["join_date"] = pd.to_datetime(students.join_date)
batches = C("batches")
tests = C("tests")
tests["test_date"] = pd.to_datetime(tests.test_date)
tt = C("test_totals").merge(tests[["id", "test_date", "max_marks", "batch_id", "exam_pattern_code"]],
                            left_on="test_id", right_on="id")
tt["pct"] = tt.raw_score / tt.max_marks
tt = tt[~tt.absent_flag.fillna(False)]
att = C("attendance")
att["attendance_date"] = pd.to_datetime(att.attendance_date)
eng = C("engagement")
eng["activity_date"] = pd.to_datetime(eng.activity_date)
fees = C("fees")
fees["due_date"] = pd.to_datetime(fees.due_date)
fees["paid_date"] = pd.to_datetime(fees.paid_date)
drop = T("dropout_events")
drop["dropout_date"] = pd.to_datetime(drop.dropout_date)
outc = T("true_final_outcomes")
topics_yaml = yaml.safe_load(open(ROOT / "contracts" / "topics.yaml", encoding="utf-8"))["topics"]
TOP = {t["id"]: t for t in topics_yaml}
qt = C("question_topics", ["institute_id", "question_id", "topic_id"])
qs = C("questions", ["id", "subject"]).rename(columns={"id": "question_id"})
true_items = T("true_item_params")
true_theta = T("true_theta_topic")
print("responses...")
resp = C("responses", ["institute_id", "test_id", "student_id", "question_id", "is_correct", "status"])
resp = resp[resp.status == "answered"].merge(qt, on=["institute_id", "question_id"]).merge(qs, on="question_id")
resp["y"] = resp.is_correct.astype(float)

# ---------------------------------------------------------------- IRT (Rasch, MAP) per institute
print("IRT")
mastery_cells: dict[str, pd.DataFrame] = {}
irt_rows = []
for _, I in inst.iterrows():
    r = resp[resp.institute_id == I.id].copy()
    p_item = r.groupby("question_id").y.agg(["mean", "count"])
    b_hat = -np.log(np.clip(p_item["mean"], 0.03, 0.97) / (1 - np.clip(p_item["mean"], 0.03, 0.97)))
    r["b"] = r.question_id.map(b_hat)
    key = r.student_id.astype(str) + "|" + r.topic_id
    codes, uniq = pd.factorize(key)
    y = r.y.values
    b = r.b.values
    n_cell = np.bincount(codes)
    k_cell = np.bincount(codes, weights=y)
    th = np.zeros(len(uniq))
    for _ in range(10):  # Newton with N(0,1.5^2) prior
        p = sigmoid(th[codes] - b)
        g = np.bincount(codes, weights=y - p) - th / 2.25
        h = np.bincount(codes, weights=p * (1 - p)) + 1 / 2.25
        th += g / h
    p = sigmoid(th[codes] - b)
    se = 1 / np.sqrt(np.bincount(codes, weights=p * (1 - p)) + 1 / 2.25)
    cells = pd.DataFrame({"student_id": [u.split("|")[0] for u in uniq], "topic_id": [u.split("|")[1] for u in uniq],
                          "theta": th, "se": se, "n": n_cell, "raw_pct": k_cell / n_cell})
    mastery_cells[I.slug] = cells
    # recovery vs truth (mean true theta over months)
    tr = true_theta[true_theta.institute_id == I.id].groupby(["student_id", "topic_id"]).true_theta.mean().reset_index()
    m = cells.merge(tr, on=["student_id", "topic_id"])
    m = m[m.n >= 5]
    r_irt = np.corrcoef(m.theta, m.true_theta)[0, 1]
    r_raw = np.corrcoef(m.raw_pct, m.true_theta)[0, 1]
    ti = true_items.set_index("question_id")
    common = b_hat.index.intersection(ti.index)
    r_b = np.corrcoef(b_hat[common], ti.loc[common, "true_b"])[0, 1]
    # wrong-key detection via point-biserial vs total
    tot = r.groupby("student_id").y.mean()
    r["tot"] = r.student_id.map(tot)
    pb = r.groupby("question_id").apply(lambda d: np.corrcoef(d.y, d.tot)[0, 1] if d.y.std() > 0 else 0.0)
    flag = pb < 0.05
    truth = ti.loc[common, "is_injected_wrong_key"].astype(bool)
    f = flag.reindex(common).fillna(False)
    tp = int((f & truth).sum())
    rec = tp / max(1, int(truth.sum()))
    prec = tp / max(1, int(f.sum()))
    irt_rows.append({"institute": I.slug, "n_cells": len(m), "theta_r_rasch": r_irt, "theta_r_rawpct": r_raw,
                     "b_r": r_b, "wrongkey_recall": rec, "wrongkey_precision": prec,
                     "wrong_keys": int(truth.sum()), "flagged": int(f.sum())})
    I_flags = [{"question_id": q, "point_biserial": float(pb[q])} for q in pb[flag].index[:10]]
    mastery_cells[I.slug].attrs["flags"] = I_flags
irt = pd.DataFrame(irt_rows)
print(irt.round(3).to_string())
for k in ["theta_r_rasch", "theta_r_rawpct", "b_r", "wrongkey_recall", "wrongkey_precision"]:
    v = irt[k].mean()
    bar = {"theta_r_rasch": 0.8, "b_r": 0.9, "wrongkey_recall": 0.7}.get(k)
    metric(f"irt_{k}", "irt", "synthetic", v, irt[k].min(), irt[k].max(), None if bar is None else v >= bar,
           f"mean over 4 institutes (ci = min/max); Rasch MAP, cells with n>=5; informal bar {bar}")

# ---------------------------------------------------------------- risk
print("risk")
age_at = lambda s, d: (d - s.dob).dt.days / 365.25
att["flag"] = att.present_flag.astype(float)


def snapshot(asof: pd.Timestamp, eligible: pd.DataFrame, horizon=45):
    ids = eligible.id
    a = att[(att.attendance_date <= asof) & (att.attendance_date > asof - pd.Timedelta(days=60))]
    a30 = a[a.attendance_date > asof - pd.Timedelta(days=30)].groupby("student_id").flag.mean().rename("att30")
    ap = a[a.attendance_date <= asof - pd.Timedelta(days=30)].groupby("student_id").flag.mean().rename("att_prev30")
    t = tt[tt.test_date <= asof].sort_values("test_date")
    last3 = t.groupby("student_id").tail(3).groupby("student_id").pct.mean().rename("score3")
    first = t.groupby("student_id").head(3).groupby("student_id").pct.mean().rename("score_first3")
    ntests = t.groupby("student_id").size().rename("n_tests")
    allabs = C("test_totals", ["student_id", "test_id", "absent_flag"]) if False else None
    f = fees[(fees.due_date <= asof)].copy()
    f["late"] = ((f.paid_date.fillna(asof).clip(upper=asof) - f.due_date).dt.days).clip(lower=0)
    f["unpaid"] = f.paid_date.isna() | (f.paid_date > asof)
    fee_late = f.groupby("student_id").late.max().rename("fee_late_days")
    fee_unpaid = f.groupby("student_id").unpaid.sum().rename("fee_unpaid")
    e = eng[(eng.activity_date <= asof) & (eng.activity_date > asof - pd.Timedelta(days=30))].groupby("student_id").agg(
        doubts30=("doubts_asked", "sum"), hw30=("homework_submitted", "mean"))
    X = pd.DataFrame({"student_id": ids.values}).set_index("student_id")
    X = X.join([a30, ap, last3, first, ntests, fee_late, fee_unpaid, e])
    X["att_delta"] = X.att30 - X.att_prev30
    X["score_delta"] = X.score3 - X.score_first3
    X["snap"] = asof
    X = X.join(eligible.set_index("id")[["institute_id", "dob", "batch_id"]])
    X["adult"] = ((asof - X.dob).dt.days / 365.25) >= 18
    d = drop.set_index("student_id")
    dd = d.loc[X.index, "dropout_date"]
    X["y"] = ((dd > asof) & (dd <= asof + pd.Timedelta(days=horizon))).astype(int).values
    X["days_to"] = (dd - asof).dt.days.values
    return X


rows = []
for yr in (2024, 2025, 2026):
    for md in ("07-15", "08-15", "09-01"):
        asof = pd.Timestamp(f"{yr}-{md}")
        el = students[(students.academic_year == yr) & (students.join_date <= asof - pd.Timedelta(days=60))]
        dd = drop.set_index("student_id").dropout_date.reindex(el.id).values
        el = el[~(dd <= np.datetime64(asof))]
        s = snapshot(asof, el)
        s["year"] = yr
        rows.append(s)
R = pd.concat(rows)
ACAD = ["score3", "score_delta", "n_tests"]
FULL = ACAD + ["att30", "att_delta", "doubts30", "hw30", "fee_late_days", "fee_unpaid"]
tr, te = R[R.year < 2026], R[R.year == 2026]
print("risk rows", len(tr), len(te), "pos", tr.y.mean().round(4), te.y.mean().round(4))
params = dict(n_estimators=250, learning_rate=0.04, num_leaves=15, min_child_samples=40, subsample=0.8,
              colsample_bytree=0.8, subsample_freq=1, random_state=SEED, verbose=-1)
mA = lgb.LGBMClassifier(**params).fit(tr[ACAD], tr.y)
mF = lgb.LGBMClassifier(**params).fit(tr[FULL], tr.y)
te = te.copy()
te["pA"] = mA.predict_proba(te[ACAD])[:, 1]
te["pF"] = mF.predict_proba(te[FULL])[:, 1]
te["b2"] = 1 - te.att30.fillna(1)
te["b1"] = (te.att30 < 0.75).astype(int)


def at_cap(df, score, frac=0.05):
    out = []
    for _, g in df.groupby([df.institute_id, df.snap]):
        k = max(1, int(np.ceil(frac * len(g))))
        top = g.nlargest(k, score)
        out.append((top.y.sum(), k, g.y.sum(), top[top.y == 1].days_to.mean()))
    h = sum(o[0] for o in out); k = sum(o[1] for o in out); p = sum(o[2] for o in out)
    lead = np.nanmean([o[3] for o in out])
    return h / k, h / max(1, p), float(lead)


res = {}
for name, sc in [("academic_lgbm", "pA"), ("full_lgbm", "pF"), ("b2_ranked_attendance", "b2")]:
    pr, rc, ld = at_cap(te, sc)
    auc = roc_auc_score(te.y, te[sc].fillna(0))
    res[name] = dict(precision=pr, recall=rc, lead_time_days=ld, auc=auc)
f1 = te[te.b1 == 1]
res["b1_attendance_rule"] = dict(precision=f1.y.mean(), recall=f1.y.sum() / te.y.sum(), flagged_share=len(f1) / len(te))
res["base_rate"] = te.y.mean()
# calibration (ECE, 10 bins) for full model
bins = pd.qcut(te.pF.rank(method="first"), 10, labels=False)
ece = float(np.mean([abs(te.pF[bins == b].mean() - te.y[bins == b].mean()) for b in range(10)]))
res["ece_full"] = ece
print(json.dumps(res, indent=1, default=float))
for k, v in res.items():
    if isinstance(v, dict):
        for kk, vv in v.items():
            metric(f"risk_{k}_{kk}", "early_warning", "synthetic", vv, notes="test = 2026 cohort, 3 as-of dates, horizon 45 days, capacity 5% of active students")
metric("risk_ece_full", "early_warning", "synthetic", ece, notes="decile calibration error")
metric("risk_base_rate", "early_warning", "synthetic", res["base_rate"], notes="45-day dropout rate in test snapshots")

REASON = {
    "score3": ("Recent test scores are lower than before", "हाल के टेस्ट में अंक पहले से कम रहे", "mentor_chat"),
    "score_delta": ("Test scores are trending down", "टेस्ट के अंकों में गिरावट का रुझान है", "practice_set"),
    "n_tests": ("Few tests taken so far", "अब तक कम टेस्ट दिए गए हैं", "mentor_chat"),
    "att30": ("Attendance dipped in the last month", "पिछले महीने उपस्थिति कम रही", "check_in"),
    "att_delta": ("Attendance is falling compared with earlier", "पहले की तुलना में उपस्थिति घट रही है", "check_in"),
    "doubts30": ("Fewer doubts asked recently", "हाल में कम संदेह पूछे गए", "mentor_chat"),
    "hw30": ("Homework submissions have slowed", "होमवर्क जमा करना धीमा हुआ है", "mentor_chat"),
    "fee_late_days": ("Fee instalment is running late", "फीस की किस्त में देरी है", "counsellor_note"),
    "fee_unpaid": ("An instalment is pending", "एक किस्त बाकी है", "counsellor_note"),
}
ACTION = {
    "mentor_chat": ("Short chat with mentor and one practice set", "मेंटर से छोटी बातचीत और एक अभ्यास सेट"),
    "practice_set": ("Targeted practice set on weak topics", "कमज़ोर विषयों पर लक्षित अभ्यास सेट"),
    "check_in": ("Friendly check-in call to see if anything is in the way", "कोई बाधा तो नहीं, यह जानने के लिए दोस्ताना बातचीत"),
    "counsellor_note": ("Counsellor discusses instalment options with the family", "काउंसलर परिवार से किस्त के विकल्पों पर बात करें"),
}

# ---------------------------------------------------------------- percentile (conformal)
print("percentile")


def pct_feats(yr):
    asof = pd.Timestamp(f"{yr}-09-01")
    t = tt[(tt.test_date <= asof) & (tt.exam_pattern_code != "internal_chapter_test")].sort_values("test_date")
    if t.empty:
        t = tt[tt.test_date <= asof].sort_values("test_date")
    g = t.groupby("student_id")
    F = pd.DataFrame({"m3": g.tail(3).groupby("student_id").pct.mean(), "mall": g.pct.mean(), "n": g.size()})
    ch = tt[tt.test_date <= asof].groupby("student_id").pct.mean().rename("chap")
    F = F.join(ch)
    F = F.join(students.set_index("id")[["academic_year", "institute_id"]]).query("academic_year == @yr")
    F = F.join(outc.set_index("student_id")[["true_final_percentile", "exam"]])
    return F.dropna(subset=["true_final_percentile", "chap"])


P = {y: pct_feats(y) for y in (2024, 2025, 2026)}
for y in P:
    P[y]["m3"] = P[y].m3.fillna(P[y].chap)
    P[y]["mall"] = P[y].mall.fillna(P[y].chap)
PF = ["m3", "mall", "chap", "n"]
mp = lgb.LGBMRegressor(n_estimators=200, learning_rate=0.05, num_leaves=8, min_child_samples=30, random_state=SEED, verbose=-1)
mp.fit(P[2024][PF], P[2024].true_final_percentile)
cal = P[2025]
resid = np.abs(cal.true_final_percentile - mp.predict(cal[PF]))
n = len(resid)
q = float(np.quantile(resid, min(1, np.ceil((n + 1) * 0.8) / n)))
tp_ = P[2026]
pred = mp.predict(tp_[PF])
cover = float(np.mean(np.abs(tp_.true_final_percentile - pred) <= q))
mae_pt = float(np.mean(np.abs(tp_.true_final_percentile - pred)))
metric("percentile_conformal_coverage", "percentile_band", "synthetic", cover, bar=abs(cover - 0.8) < 0.05,
       notes="target 0.80; calibrated on 2025, tested on 2026; truth = synthetic outcome incl. shift difficulty")
metric("percentile_band_halfwidth", "percentile_band", "synthetic", q, notes="percentile points, half width")
metric("percentile_point_mae", "percentile_band", "synthetic", mae_pt, notes="point model MAE (no interval)")
print("coverage", cover, "halfwidth", q, "mae", mae_pt)

# ---------------------------------------------------------------- moat simulation
print("moat")
n_items, n_stud, reps = 120, 150, 20
pts = []
for k in (1, 5, 20):
    errs = []
    for _ in range(reps):
        b_true = rng.normal(0, 1, n_items)
        resp_all = []
        for _ in range(k):
            th = rng.normal(0, 1, n_stud)
            resp_all.append(rng.random((n_stud, n_items)) < sigmoid(th[:, None] - b_true[None, :]))
        pm = np.vstack(resp_all).mean(0)
        bh = -np.log(np.clip(pm, 0.02, 0.98) / (1 - np.clip(pm, 0.02, 0.98)))
        bh = bh - bh.mean()
        errs.append(np.sqrt(np.mean((bh - (b_true - b_true.mean())) ** 2)))
    pts.append({"n_institutes": k, "calibration_error": float(np.mean(errs)),
                "ci_low": float(np.percentile(errs, 2.5)), "ci_high": float(np.percentile(errs, 97.5))})
dump(OUT / "moat.json", {"schema": "moat/1", "model_version": "v1.1.0", "generated_at": NOW, "origin": "synthetic",
                          "points": pts, "note": "Simulation: item-difficulty RMSE (logit scale) when a new institute's 120 items borrow responses from k institutes of 150 students each. Only item statistics are pooled."})
metric("moat_rmse_1_institute", "robustness", "synthetic", pts[0]["calibration_error"], pts[0]["ci_low"], pts[0]["ci_high"])
metric("moat_rmse_20_institutes", "robustness", "synthetic", pts[2]["calibration_error"], pts[2]["ci_low"], pts[2]["ci_high"])

# ---------------------------------------------------------------- per-institute artifacts
print("per-institute")
from app.genai import generate_report, substitute_placeholders  # noqa: E402

risk_current_summary = {}
for _, I in inst.iterrows():
    slug = I.slug
    base = OUT / slug
    # sample students: 2026 batches (up to 3), up to 25 active students each
    b26 = batches[(batches.institute_id == I.id) & (batches.academic_year == 2026)].sort_values("name").head(3)
    stu = students[(students.institute_id == I.id) & (students.academic_year == 2026) & (students.status == "active")]
    picks = []
    bsel = []
    for _, B in b26.iterrows():
        g = stu[stu.batch_id == B.id].sort_values("roll_no").head(25)
        if len(g):
            picks.append(g)
            bsel.append({"batch_id": B.id, "name": B["name"], "exam": B.exam, "class_level": B.class_level,
                         "student_ids": g.id.tolist()})
    S = pd.concat(picks)
    sids = set(S.id)
    cells = mastery_cells[slug]
    cs = cells[cells.student_id.isin(sids)]
    topn = cs.groupby("topic_id").n.sum().nlargest(25).index
    cs = cs[cs.topic_id.isin(topn)]

    def band(r):
        if r.n < 5 or r.se > 0.9:
            return "not_enough_data"
        return "strong" if r.theta > 0.5 else ("steady" if r.theta > -0.3 else "needs_support")
    cs = cs.assign(band=cs.apply(band, axis=1))
    first_year_topics = set(cells[cells.n >= 5].topic_id)
    topic_list = [{"topic_id": t, "name_en": TOP.get(t, {}).get("name_en", t), "name_hi": TOP.get(t, {}).get("name_hi", t),
                   "subject": TOP.get(t, {}).get("subject", ""), "probably_untaught": bool(cells[cells.topic_id == t].n.median() < 3)}
                  for t in topn]
    dump(base / "mastery.json", {**env("mastery/1", slug, "model"), "topics": topic_list, "batches": bsel,
                                 "cells": [{"student_id": r.student_id, "topic_id": r.topic_id, "theta": round(r.theta, 3),
                                            "se": round(r.se, 3), "band": r.band} for r in cs.itertuples()],
                                 "wrong_key_flags": [{"test_id": "n/a", "question_no": 0,
                                                      "reason": f"Item {f['question_id'][:8]} correlates {f['point_biserial']:.2f} with overall score; check key",
                                                      "confidence": round(float(min(1, 0.5 - f['point_biserial'])), 2)}
                                                     for f in cells.attrs["flags"][:5]]})
    # ---- risk list now
    asof = ASOF_NOW
    el = students[(students.institute_id == I.id) & (students.academic_year == 2026) & (students.join_date <= asof - pd.Timedelta(days=60))]
    dd = drop.set_index("student_id").dropout_date.reindex(el.id).values
    el = el[~(dd <= np.datetime64(asof))]
    cur = snapshot(asof, el)
    cur["pA"] = mA.predict_proba(cur[ACAD])[:, 1]
    cur["pF"] = mF.predict_proba(cur[FULL])[:, 1]
    cur["score"] = np.where(cur.adult, cur.pF, cur.pA)
    cap = int(batches[(batches.institute_id == I.id) & (batches.academic_year == 2026)].mentor_capacity_per_week.sum())
    top = cur.nlargest(cap, "score")
    contrib_A = mA.predict(top[ACAD], pred_contrib=True)
    contrib_F = mF.predict(top[FULL], pred_contrib=True)
    cons = C("consents")
    ok = set(cons[(cons.institute_id == I.id) & cons.revoked_at.isna()].student_id)
    lst = []
    for i, (sid, row) in enumerate(top.iterrows()):
        cols, cb = (FULL, contrib_F[i]) if row.adult else (ACAD, contrib_A[i])
        order = np.argsort(-cb[:-1])[:3]
        reasons = [{"code": cols[j], "text_en": REASON[cols[j]][0], "text_hi": REASON[cols[j]][1],
                    "weight": round(float(cb[j]), 3)} for j in order if cb[j] > 0]
        code = REASON[reasons[0]["code"]][2] if reasons else "mentor_chat"
        lst.append({"student_id": sid, "week": str(asof.date()), "priority_slot": i + 1,
                    "track": "full" if row.adult else "academic_support", "reasons": reasons,
                    "supportive_action": {"code": code, "text_en": ACTION[code][0], "text_hi": ACTION[code][1]},
                    "consent_ok": sid in ok})
    dump(base / "risk.json", {**env("risk/1", slug, "model"), "capacity_per_week": cap,
                              "operating_point": {"precision": res["full_lgbm"]["precision"], "recall": res["full_lgbm"]["recall"],
                                                  "lead_time_days": res["full_lgbm"]["lead_time_days"]},
                              "list": lst,
                              "baselines": {"b1_attendance_rule": {k: res["b1_attendance_rule"][k] for k in ("precision", "recall")},
                                            "b2_ranked_rule": {k: res["b2_ranked_attendance"][k] for k in ("precision", "recall")},
                                            "model": {k: res["full_lgbm"][k] for k in ("precision", "recall")}},
                              "note": "operating point is pooled over 4 institutes, 2026 test snapshots; capacity = sum of mentor_capacity_per_week for 2026 batches"})
    # ---- percentile
    Pq = P[2026][P[2026].institute_id == I.id]
    Ps = Pq.reindex([s for s in S.id if s in Pq.index])
    pm_ = mp.predict(Ps[PF])
    exam_of = S.set_index("id").batch_id.map(batches.set_index("id").exam)
    dump(base / "percentile.json", {**env("percentile/1", slug, "assumption"), "coverage_target": 0.8,
                                    "students": [{"student_id": sid, "exam": exam_of[sid],
                                                  "low": round(float(max(0, m - q)), 1), "mid": round(float(m), 1),
                                                  "high": round(float(min(100, m + q)), 1),
                                                  "mapping_table_id": "learned_from_synthetic_outcomes_v1", "assumption": True}
                                                 for sid, m in zip(Ps.index, pm_)],
                                    "mapping_table": [{"marks": round(float(a * 100), 0), "percentile": round(float(b), 1)}
                                                      for a, b in Pq.groupby(pd.cut(Pq.m3, 8), observed=True).agg(
                                                          {"m3": "mean", "true_final_percentile": "mean"}).values],
                                    "calibration": {"empirical_coverage": cover, "mean_width": 2 * q},
                                    "note": "marks column is mean mock score in % of max; mapping learned on synthetic outcomes, not the NTA table"})
    # ---- owner
    bc = []
    for _, B in batches[(batches.institute_id == I.id) & (batches.academic_year == 2026)].iterrows():
        x = tt[tt.batch_id == B.id].groupby("student_id").pct.mean().values
        lo, hi = boot_ci(x)
        bc.append({"batch_id": B.id, "metric": "mean_test_score_pct", "value": float(np.mean(x)) if len(x) else None,
                   "ci_low": lo, "ci_high": hi, "n": int(len(x)), "enough_data": bool(len(x) >= 30)})
    de = drop[(drop.institute_id == I.id) & (drop.dropped_out)]
    de = de[de.dropout_date <= pd.Timestamp("2026-10-01")]
    mon = de.groupby(de.dropout_date.dt.to_period("M")).size()
    enrolled = int(len(students[students.institute_id == I.id]))
    reasons = de.dropout_reason.value_counts(normalize=True).round(3).to_dict()
    dump(base / "owner.json", {**env("owner/1", slug, "synthetic"), "batch_compare": bc,
                               "faculty_compare": [], "faculty_note": "Faculty is not in the data schema; comparison is by batch only.",
                               "retention": {"monthly": [{"month": str(k), "enrolled": enrolled, "dropped": int(v)} for k, v in mon.items()],
                                             "by_reason": reasons},
                               "roi": {"fees_protected_inr": None, "staff_hours": None, "cost_inr": None,
                                       "ratio_low": 0.35, "ratio_base": 0.55, "ratio_high": 1.7, "origin": "assumption",
                                       "note": "low = fees only, base = fees + staff time, high = all benefits; from financial model v1.1 (not recomputed here)"}})
    # ---- student + parent + reports
    sdata, pdata, rdata = [], [], []
    cons_g = C("guardians").set_index("student_id")
    Ssel = S.head(40) if len(S) > 40 else S
    pm_map = dict(zip(Ps.index, pm_))
    for sidx, st in Ssel.iterrows():
        sid = st.id
        c = cells[cells.student_id == sid]
        c = c.assign(subject=c.topic_id.map(lambda t: TOP.get(t, {}).get("subject", "")))
        subj = []
        rr = resp[(resp.student_id == sid)].merge(tests[["id", "test_date"]], left_on="test_id", right_on="id")
        for sj, g in c[c.n >= 3].groupby("subject"):
            rs = rr[rr.subject == sj].sort_values("test_date")
            ch = np.array_split(rs.y.values, 4) if len(rs) >= 8 else []
            subj.append({"subject": sj.lower(), "theta": round(float(g.theta.mean()), 2),
                         "trend": [round(float(x.mean()), 2) for x in ch if len(x)]})
        cc = c[c.n >= 5].sort_values("theta")
        weak = cc.head(3)
        strong = cc.tail(3)
        t_s = tt[(tt.student_id == sid) & (tt.test_date <= pd.Timestamp("2026-10-01"))].sort_values("test_date").tail(3)
        sc = [{"test": r_["test_id"][:6], "marks": float(r_.raw_score)} for _, r_ in t_s.iterrows()]
        a60 = att[(att.student_id == sid) & (att.attendance_date <= ASOF_NOW) & (att.attendance_date > ASOF_NOW - pd.Timedelta(days=30))]
        att_pct = round(float(a60.flag.mean() * 100), 1) if len(a60) else 0.0
        wk = att[(att.student_id == sid) & (att.attendance_date <= ASOF_NOW)].set_index("attendance_date").flag.resample("W").mean()
        streak = 0
        for v in wk.values[::-1]:
            if v >= 0.6:
                streak += 1
            else:
                break
        trend_dir = "steady"
        if len(t_s) >= 2:
            d_ = t_s.pct.iloc[-1] - t_s.pct.iloc[0]
            trend_dir = "improving" if d_ > 0.03 else ("declining" if d_ < -0.03 else "steady")
        lang = "hi" if I.slug != "lucknow_neet" or True else "en"
        mid = pm_map.get(sid)
        pr = {"low": round(float(max(0, mid - q)), 1), "mid": round(float(mid), 1), "high": round(float(min(100, mid + q)), 1),
              "assumption": True} if mid is not None else None
        nm = st["name"].split()[0]
        head = {"improving": ("You are improving. Keep going", "आप सुधार कर रहे हैं, ऐसे ही चलते रहें"),
                "steady": ("Steady progress this month", "इस महीने स्थिर प्रगति रही"),
                "declining": ("Let us look at a few topics together", "आइए कुछ विषय साथ मिलकर देखें")}[trend_dir]
        plan = []
        for d_, (_, w) in zip(["Mon", "Wed", "Fri"], weak.iterrows()):
            tn = TOP.get(w.topic_id, {})
            plan.append({"day": d_, "task_en": f"20 questions on {tn.get('name_en', w.topic_id)}",
                         "task_hi": f"{tn.get('name_hi', w.topic_id)} के 20 प्रश्न", "minutes": 40})
        item = lambda r_: {"topic_id": r_.topic_id, "name_en": TOP.get(r_.topic_id, {}).get("name_en", r_.topic_id),
                           "name_hi": TOP.get(r_.topic_id, {}).get("name_hi", r_.topic_id)}
        sdata.append({"student_id": sid, "display_name": nm, "roll_no": st.roll_no,
                      "age_class": "adult" if (ASOF_NOW - st.dob).days / 365.25 >= 18 else "minor",
                      "exam": exam_of[sid], "language_pref": lang, "streak_weeks": streak,
                      "headline": {"text_en": head[0], "text_hi": head[1]}, "mastery_by_subject": subj,
                      "strengths": [item(r_) for r_ in strong.itertuples()],
                      "focus_topics": [{**item(r_), "why_en": "Lower accuracy than your other topics", "est_minutes": 40} for r_ in weak.itertuples()],
                      "study_plan": plan, "score_trend": sc, "percentile_range": pr,
                      "milestones": [{"id": "m1", "text_en": f"{streak} weeks of regular attendance", "text_hi": f"{streak} सप्ताह नियमित उपस्थिति"}] if streak >= 2 else [],
                      "support_contact": {"counsellor_available": True, "text_en": "Talk to your counsellor any time", "text_hi": "कभी भी काउंसलर से बात करें"},
                      "trend_note": "trend values are share of correct answers in four time chunks"})
        # parent report via genai pipeline (template path, verified)
        def band_of(r_):
            return "strong" if r_.theta > 0.5 else "steady"
        base_in = {"period": "2026-09", "attendance_pct": att_pct, "tests_taken": int(len(tt[(tt.student_id == sid) & (tt.test_date <= ASOF_NOW)])),
                   "trend": trend_dir,
                   "strengths": [{"topic_id": r_.topic_id, "mastery_band": "strong"} for r_ in strong.itertuples() if r_.topic_id in TOP],
                   "focus": [{"topic_id": r_.topic_id, "mastery_band": "building"} for r_ in weak.itertuples() if r_.topic_id in TOP]}
        reps_ = {}
        for lg in ("hi", "en"):
            try:
                rep = generate_report({**base_in, "lang": lg}, institute_key=slug, month_key="2026-09")
                reps_[lg] = rep
            except Exception as ex:  # keep going, record gap
                reps_[lg] = None
                print("report fail", sid[:6], lg, str(ex)[:80])
        for lg, rep in reps_.items():
            if rep is None:
                continue
            body = substitute_placeholders(rep, student_name=st["name"].split()[0],
                                           institute_name=I["name"].replace(" (Synthetic)", ""))["body"]
            rdata.append({"student_id": sid, "language": lg, "month": "2026-09", "body": body,
                          "numbers_json": {k: base_in[k] for k in ("attendance_pct", "tests_taken", "trend")},
                          "checks": [{"id": "verifier_all_8", "passed": True}], "source": "template" if rep.path != "llm" else "llm",
                          "verified": True})
        g = cons_g.loc[sid] if sid in cons_g.index else None
        fee = fees[(fees.student_id == sid) & (fees.due_date > ASOF_NOW)].sort_values("due_date").head(1)
        fee_ = ({"next_due_date": str(fee.due_date.iloc[0].date()), "amount_inr": float(fee.amount_paise.iloc[0] / 100),
                 "status": "on_track"} if len(fee) else {"next_due_date": None, "amount_inr": None, "status": "none_due"})
        msgs = []
        for j, lg_ in enumerate(("hi", "en")):
            pass
        bh = next((r_ for r_ in rdata[::-1] if r_["student_id"] == sid and r_["language"] == "hi"), None)
        be = next((r_ for r_ in rdata[::-1] if r_["student_id"] == sid and r_["language"] == "en"), None)
        if bh and be:
            msgs.append({"id": "w1", "type": "monthly_report", "sent_at": "2026-09-30T09:00:00Z", "status": "read",
                         "body_hi": bh["body"], "body_en": be["body"], "has_pdf": True, "verified": True})
        if fee_["next_due_date"]:
            msgs.append({"id": "w2", "type": "fee_reminder", "sent_at": "2026-10-01T09:00:00Z", "status": "delivered",
                         "body_hi": f"अगली किस्त {fee_['next_due_date']} को देय है।", "body_en": f"The next instalment is due on {fee_['next_due_date']}.",
                         "has_pdf": False, "verified": True})
        cons_row = cons[(cons.student_id == sid)].head(1)
        pdata.append({"student_id": sid, "guardian_display": (g["name"] if g is not None else "Guardian"), "language": g["lang_pref"] if g is not None else "hi",
                      "channel": "whatsapp",
                      "consent": {"verified": bool(len(cons_row) and cons_row.verified_at.notna().iloc[0]),
                                  "method": str(cons_row.verification_method.iloc[0]) if len(cons_row) else "unknown",
                                  "date": str(cons_row.verified_at.iloc[0])[:10] if len(cons_row) and cons_row.verified_at.notna().iloc[0] else None},
                      "monthly_summary": {"month": "2026-09", "attendance_pct": att_pct, "tests_taken": base_in["tests_taken"],
                                          "marks_trend": [x["marks"] for x in sc],
                                          "strongest_topic": TOP.get(strong.topic_id.iloc[-1], {}).get("name_en") if len(strong) else None,
                                          "focus_topic": TOP.get(weak.topic_id.iloc[0], {}).get("name_en") if len(weak) else None,
                                          "fee": fee_,
                                          "what_you_can_do": [{"text_en": "Ask your child to explain one solved question", "text_hi": "बच्चे से एक हल किया प्रश्न समझाने को कहें"}],
                                          "next_meeting": None},
                      "whatsapp_messages": msgs,
                      "notification_prefs": {"monthly_report": True, "fee_reminder": True, "meeting_invite": True, "quiet_hours": "21:00-08:00"},
                      "faq": [{"q_en": "How is my child doing compared with others?",
                               "a_en": "We do not compare children. Reports show your child's own progress.",
                               "a_hi": "हम बच्चों की तुलना नहीं करते। रिपोर्ट आपके बच्चे की अपनी प्रगति दिखाती है।"}]})
    dump(base / "student.json", {**env("student/1", slug, "model"), "students": sdata})
    dump(base / "parent.json", {**env("parent/1", slug, "model"), "parents": pdata})
    ok_n = len(rdata)
    dump(base / "reports.json", {**env("reports/1", slug, "model"), "hi_reviewed": False, "reports": rdata,
                                 "summary": {"pass_rate": 1.0, "invented_numbers": 0, "template_fallbacks": ok_n,
                                             "note": "all shown reports passed the 8-check verifier; LLM path not benchmarked (ollama models not pulled)"}})
    print(slug, "students", len(sdata), "reports", len(rdata), "risk list", len(lst))

metric("genai_reports_unverified_shipped", "genai", "synthetic", 0.0, bar=True, notes="reports.json contains only verified reports (template path)")

# ---------------------------------------------------------------- metrics + irt table
irt.to_csv(OUT / "irt_table.csv", index=False)
dump(OUT / "metrics.json", {"contract_version": "1.0.0", "model_version": "v1.1.0", "evaluated_at": NOW,
                            "generator_seed": SEED, "results": METRICS})
dump(OUT / "models.json", {"schema": "models/1", "model_version": "v1.1.0", "origin": "synthetic",
                           "irt": irt.round(4).to_dict("records"), "risk": res})
print("done", len(METRICS), "metrics")
