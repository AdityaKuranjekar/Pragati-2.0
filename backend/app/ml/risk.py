"""Runtime early-warning: feature snapshot, saved LightGBM models, purpose/age routing, reasons.

Routing comes from contracts/routing_policy.yaml: a minor is never scored on a track that uses attendance,
fees or engagement (tiers B, C, D) unless the institute's legal flag `minor_ml_risk_enabled` is on, and even then
engagement (tier D) is never used for a minor (DPDP s.9(3)).
"""
from __future__ import annotations

import functools
import threading

import lightgbm as lgb
import numpy as np
import pandas as pd
import yaml

from .. import config

ACAD = ["score3", "score_delta", "n_tests"]
TIER_FEATURES = {
    "A": ACAD,
    "B": ["att30", "att_delta"],
    "C": ["fee_late_days", "fee_unpaid"],
    "D": ["doubts30", "hw30"],
}
# model name -> ordered feature list. "full" keeps the column order used by ml/build_artifacts.py.
MODEL_FEATURES = {
    "A": ACAD,
    "AB": ACAD + ["att30", "att_delta"],
    "ABC": ACAD + ["att30", "att_delta", "fee_late_days", "fee_unpaid"],
    "ABCD": ACAD + ["att30", "att_delta", "doubts30", "hw30", "fee_late_days", "fee_unpaid"],
}
TIER_ORDER = "ABCD"

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

LGB_PARAMS = dict(n_estimators=250, learning_rate=0.04, num_leaves=15, min_child_samples=40, subsample=0.8,
                  colsample_bytree=0.8, subsample_freq=1, random_state=42, verbose=-1)


# ---------------------------------------------------------------- features
def snapshot_features(asof: pd.Timestamp, ids: pd.Index | list, att: pd.DataFrame, tt: pd.DataFrame,
                      fees: pd.DataFrame, eng: pd.DataFrame) -> pd.DataFrame:
    """Per-student features as of a date. Inputs are plain frames:
    att[student_id, attendance_date, flag]; tt[student_id, test_date, pct]; fees[student_id, due_date, paid_date];
    eng[student_id, activity_date, doubts_asked, homework_submitted]."""
    a = att[(att.attendance_date <= asof) & (att.attendance_date > asof - pd.Timedelta(days=60))]
    a30 = a[a.attendance_date > asof - pd.Timedelta(days=30)].groupby("student_id").flag.mean().rename("att30")
    ap = a[a.attendance_date <= asof - pd.Timedelta(days=30)].groupby("student_id").flag.mean().rename("att_prev30")
    t = tt[tt.test_date <= asof].sort_values("test_date")
    last3 = t.groupby("student_id").tail(3).groupby("student_id").pct.mean().rename("score3")
    first = t.groupby("student_id").head(3).groupby("student_id").pct.mean().rename("score_first3")
    ntests = t.groupby("student_id").size().rename("n_tests")
    f = fees[fees.due_date <= asof].copy()
    f["late"] = ((f.paid_date.fillna(asof).clip(upper=asof) - f.due_date).dt.days).clip(lower=0)
    f["unpaid"] = f.paid_date.isna() | (f.paid_date > asof)
    fee_late = f.groupby("student_id").late.max().rename("fee_late_days")
    fee_unpaid = f.groupby("student_id").unpaid.sum().rename("fee_unpaid")
    e = eng[(eng.activity_date <= asof) & (eng.activity_date > asof - pd.Timedelta(days=30))].groupby("student_id").agg(
        doubts30=("doubts_asked", "sum"), hw30=("homework_submitted", "mean"))
    X = pd.DataFrame({"student_id": list(ids)}).set_index("student_id")
    X = X.join([a30, ap, last3, first, ntests, fee_late, fee_unpaid, e])
    X["att_delta"] = X.att30 - X.att_prev30
    X["score_delta"] = X.score3 - X.score_first3
    return X


# ---------------------------------------------------------------- models
_lock = threading.Lock()


def load_model_file(path) -> lgb.Booster:
    """Load a saved LightGBM model; tolerates CRLF line endings that Windows git autocrlf can introduce."""
    txt = open(path, "r", encoding="utf-8", newline="").read().replace(chr(13) + chr(10), chr(10))
    return lgb.Booster(model_str=txt)


@functools.lru_cache(maxsize=None)
def load_booster(name: str) -> lgb.Booster:
    return load_model_file(config.MODELS_DIR / f"risk_{name}.txt")


def models_available() -> bool:
    return all((config.MODELS_DIR / f"risk_{n}.txt").exists() for n in MODEL_FEATURES)


@functools.lru_cache(maxsize=1)
def routing_policy() -> dict:
    return yaml.safe_load(open(config.CONTRACTS / "routing_policy.yaml", encoding="utf-8"))


def route(is_minor: bool, minor_ml_risk_enabled: bool, target: str) -> dict:
    """Look up the routing row for (is_minor, flag, target)."""
    for row in routing_policy()["routing_matrix"]:
        if (row["is_minor"] == is_minor and row["minor_ml_risk_enabled"] == minor_ml_risk_enabled
                and row["target"] == target):
            return row
    raise KeyError((is_minor, minor_ml_risk_enabled, target))


def model_for(is_minor: bool, minor_flag: bool, active_tier: str, has_engagement_consent: bool = True) -> str:
    """Pick the model (feature set) a student may be scored with.

    Support-list track: minors -> `academic_support` routing (tier A only unless the legal flag allows retention ML);
    adults -> `retention` routing (tiers A-D). The institute's active tier caps the features; tier D additionally
    needs the student's own engagement consent and is never used for minors."""
    if is_minor:
        row = route(True, minor_flag, "retention") if minor_flag else route(True, minor_flag, "academic_support")
    else:
        row = route(False, minor_flag, "retention")
    allowed = set(row["allowed_tiers"])
    if is_minor:
        allowed.discard("D")
    if not has_engagement_consent:
        allowed.discard("D")
    cap = set(TIER_ORDER[: TIER_ORDER.index(active_tier) + 1])
    use = "".join(t for t in TIER_ORDER if t in allowed and t in cap)
    return use if use in MODEL_FEATURES else _closest_model(use)


def _closest_model(tiers: str) -> str:
    """Tier sets without a trained model (for example A+C) fall back to the largest trained subset."""
    for name in ("ABC", "AB", "A"):
        if set(name) <= set(tiers):
            return name
    return "A"


def score_students(X: pd.DataFrame, model_names: pd.Series) -> pd.DataFrame:
    """Probability and per-feature contributions for each student under their own model. X indexed by student_id."""
    out = []
    for name, idx in model_names.groupby(model_names).groups.items():
        cols = MODEL_FEATURES[name]
        b = load_booster(name)
        sub = X.loc[idx, cols]
        p = b.predict(sub)
        contrib = b.predict(sub, pred_contrib=True)
        for i, sid in enumerate(idx):
            out.append((sid, name, float(p[i]), dict(zip(cols, contrib[i][:-1]))))
    df = pd.DataFrame(out, columns=["student_id", "model", "p", "contrib"]).set_index("student_id")
    return df


def reasons_for(contrib: dict, top: int = 3) -> tuple[list[dict], dict]:
    order = sorted(contrib.items(), key=lambda kv: -kv[1])[:top]
    reasons = [{"code": c, "text_en": REASON[c][0], "text_hi": REASON[c][1], "weight": round(float(w), 3)}
               for c, w in order if w > 0]
    code = REASON[reasons[0]["code"]][2] if reasons else "mentor_chat"
    action = {"code": code, "text_en": ACTION[code][0], "text_hi": ACTION[code][1]}
    return reasons, action
