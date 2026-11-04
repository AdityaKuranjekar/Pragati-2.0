"""One-command offline training. Writes ml/artifacts/models/* with a manifest of hashes. Never called per request.

    python -m app.ml.train            (run from backend)

Reads all years of data/clean + data/truth (the truth tables supply only the labels: dropout events and final
percentile). Models: four LightGBM risk models (feature tiers A, A+B, A+B+C, A+B+C+D), a LightGBM percentile
point model with a conformal half-width, and stored Rasch item difficulties.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import time

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from .. import config
from . import irt, percentile, risk

SEED = 42


def _clean(name, columns=None):
    return pd.read_parquet(config.DATA_DIR / "clean" / f"{name}.parquet", columns=columns)


def _truth(name):
    return pd.read_parquet(config.DATA_DIR / "truth" / f"{name}.parquet")


def load_item_difficulty() -> pd.DataFrame:
    p = config.MODELS_DIR / "item_difficulty.csv"
    if not p.exists():
        train()
    return pd.read_csv(p)


def _sha(path) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]


def train() -> dict:
    t0 = time.time()
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    students = _clean("students")
    students["dob"] = pd.to_datetime(students.dob)
    students["join_date"] = pd.to_datetime(students.join_date)
    tests = _clean("tests")
    tests["test_date"] = pd.to_datetime(tests.test_date)
    tt = _clean("test_totals").merge(tests[["id", "test_date", "max_marks", "batch_id", "exam_pattern_code"]],
                                     left_on="test_id", right_on="id")
    tt["pct"] = tt.raw_score / tt.max_marks
    tt = tt[~tt.absent_flag.fillna(False)]
    att = _clean("attendance")
    att["attendance_date"] = pd.to_datetime(att.attendance_date)
    att["flag"] = att.present_flag.astype(float)
    eng = _clean("engagement")
    eng["activity_date"] = pd.to_datetime(eng.activity_date)
    fees = _clean("fees")
    fees["due_date"] = pd.to_datetime(fees.due_date)
    fees["paid_date"] = pd.to_datetime(fees.paid_date)
    drop = _truth("dropout_events")
    drop["dropout_date"] = pd.to_datetime(drop.dropout_date)
    outc = _truth("true_final_outcomes")
    dd_by = drop.set_index("student_id").dropout_date

    # ---------------------------------------------------------- item difficulty (per institute)
    resp = _clean("responses", ["institute_id", "test_id", "student_id", "question_id", "is_correct", "status"])
    resp = resp[resp.status == "answered"]
    qt = _clean("question_topics", ["institute_id", "question_id", "topic_id"])
    resp = resp.merge(qt, on=["institute_id", "question_id"])
    resp["y"] = resp.is_correct.astype(float)
    diffs = []
    for iid, r in resp.groupby("institute_id"):
        d = irt.item_difficulty(r)
        flags = set(irt.flag_wrong_keys(r, min_n=1).question_id)
        d["institute_id"] = iid
        d["fit_flag"] = np.where(d.question_id.isin(flags), "suspect_wrong_key",
                                 np.where(d.n < 30, "too_few_responses", "ok"))
        diffs.append(d)
    diff = pd.concat(diffs)
    diff = diff.assign(a=1.0, g=0.0, n_responses=diff.n.astype(int))[
        ["institute_id", "question_id", "a", "b", "g", "se_b", "n_responses", "fit_flag"]]
    diff.to_csv(config.MODELS_DIR / "item_difficulty.csv", index=False)
    del resp

    # ---------------------------------------------------------- risk snapshots 2024-26
    rows = []
    for yr in (2024, 2025, 2026):
        for md in ("07-15", "08-15", "09-01"):
            asof = pd.Timestamp(f"{yr}-{md}")
            el = students[(students.academic_year == yr) & (students.join_date <= asof - pd.Timedelta(days=60))]
            dd = dd_by.reindex(el.id).values
            el = el[~(dd <= np.datetime64(asof))]
            X = risk.snapshot_features(asof, el.id.values, att, tt, fees, eng)
            X = X.join(el.set_index("id")[["institute_id", "dob", "batch_id"]])
            X["snap"] = asof
            X["adult"] = ((asof - X.dob).dt.days / 365.25) >= 18
            d_ = dd_by.loc[X.index]
            X["y"] = ((d_ > asof) & (d_ <= asof + pd.Timedelta(days=45))).astype(int).values
            X["days_to"] = (d_ - asof).dt.days.values
            X["year"] = yr
            rows.append(X)
    R = pd.concat(rows)
    tr, te = R[R.year < 2026], R[R.year == 2026].copy()
    ablation = {}
    for name, cols in risk.MODEL_FEATURES.items():
        m = lgb.LGBMClassifier(**risk.LGB_PARAMS).fit(tr[cols], tr.y)
        m.booster_.save_model(str(config.MODELS_DIR / f"risk_{name}.txt"))
        te["p"] = m.predict_proba(te[cols])[:, 1]
        pr, rc, ld = _at_cap(te, "p")
        ablation[name] = {"auc": float(roc_auc_score(te.y, te.p)), "precision": pr, "recall": rc, "lead_time_days": ld,
                          "features": cols}
    te["b2"] = 1 - te.att30.fillna(1)
    pr, rc, ld = _at_cap(te, "b2")
    ablation["B2_ranked_attendance"] = {"auc": float(roc_auc_score(te.y, te.b2.fillna(0))), "precision": pr,
                                        "recall": rc, "lead_time_days": ld, "features": ["att30"]}
    f1 = te[te.att30 < 0.75]
    ablation["B1_attendance_rule"] = {"precision": float(f1.y.mean()), "recall": float(f1.y.sum() / te.y.sum()),
                                      "flagged_share": float(len(f1) / len(te)), "features": ["att30"]}
    (config.MODELS_DIR / "risk_ablation.json").write_text(json.dumps(ablation, indent=1), encoding="utf-8")

    # ---------------------------------------------------------- percentile
    P = {}
    for yr in (2024, 2025, 2026):
        asof = pd.Timestamp(f"{yr}-09-01")
        stu = students[students.academic_year == yr].set_index("id")
        F = percentile.features(tt[tt.student_id.isin(stu.index)], asof, strict=True)
        F = F.join(outc.set_index("student_id")[["true_final_percentile", "exam"]]).dropna(subset=["true_final_percentile"])
        F["institute_id"] = stu.institute_id.reindex(F.index).values
        P[yr] = F
    mp = lgb.LGBMRegressor(n_estimators=200, learning_rate=0.05, num_leaves=8, min_child_samples=30,
                           random_state=SEED, verbose=-1)
    mp.fit(P[2024][percentile.PF], P[2024].true_final_percentile)
    mp.booster_.save_model(str(config.MODELS_DIR / "percentile_point.txt"))
    cal = P[2025]
    resid = np.abs(cal.true_final_percentile - mp.predict(cal[percentile.PF]))
    n = len(resid)
    q = float(np.quantile(resid, min(1, np.ceil((n + 1) * 0.8) / n)))
    tp_ = P[2026]
    pred = mp.predict(tp_[percentile.PF])
    cover = float(np.mean(np.abs(tp_.true_final_percentile - pred) <= q))
    mapping = [{"marks": round(float(a * 100), 0), "percentile": round(float(b), 1)}
               for a, b in tp_.groupby(pd.cut(tp_.m3, 8), observed=True).agg({"m3": "mean", "true_final_percentile": "mean"}).values]
    (config.MODELS_DIR / "percentile_meta.json").write_text(json.dumps(
        {"halfwidth": q, "coverage_target": 0.8, "empirical_coverage_2026": cover,
         "mae_2026": float(np.mean(np.abs(tp_.true_final_percentile - pred))), "calibrated_on": 2025, "tested_on": 2026},
        indent=1), encoding="utf-8")
    (config.MODELS_DIR / "percentile_mapping.json").write_text(json.dumps(
        {"id": "learned_from_synthetic_outcomes_v1", "assumption": True, "table": mapping}, indent=1), encoding="utf-8")

    manifest = {
        "model_version": config.MODEL_VERSION, "trained_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "seed": SEED, "data": "synthetic, seed 42", "seconds": round(time.time() - t0, 1),
        "files": {p.name: _sha(p) for p in sorted(config.MODELS_DIR.glob("*")) if p.name != "manifest.json"},
        "ablation": {k: {kk: vv for kk, vv in v.items() if kk != "features"} for k, v in ablation.items()},
        "percentile": json.loads((config.MODELS_DIR / "percentile_meta.json").read_text(encoding="utf-8")),
    }
    (config.MODELS_DIR / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def _at_cap(df, score, frac=0.05):
    out = []
    for _, g in df.groupby([df.institute_id, df.snap]):
        k = max(1, int(np.ceil(frac * len(g))))
        top = g.nlargest(k, score)
        out.append((top.y.sum(), k, g.y.sum(), top[top.y == 1].days_to.mean()))
    h = sum(o[0] for o in out)
    k = sum(o[1] for o in out)
    p = sum(o[2] for o in out)
    return float(h / k), float(h / max(1, p)), float(np.nanmean([o[3] for o in out]))


if __name__ == "__main__":
    m = train()
    print(json.dumps({k: m[k] for k in ("model_version", "seconds", "ablation", "percentile")}, indent=1))
