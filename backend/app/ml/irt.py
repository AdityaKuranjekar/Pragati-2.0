"""Runtime Rasch mastery (MAP ability per student and topic) and wrong-key detection.

Same maths as ml/build_artifacts.py (Rasch, item difficulty from pass rates, Newton with an N(0, 1.5^2) prior),
split into a training half (`item_difficulty`) and an inference half (`fit_cells`) so a batch recompute never
re-estimates item difficulty. The hierarchical 2PL with a guessing prior is NOT implemented (README says so).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PRIOR_VAR = 2.25
MIN_N_FOR_BAND = 5
MAX_SE_FOR_BAND = 0.9
WRONG_KEY_PB = 0.05


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def logit_difficulty(p_correct: pd.Series | np.ndarray):
    p = np.clip(p_correct, 0.03, 0.97)
    return -np.log(p / (1 - p))


def item_difficulty(resp: pd.DataFrame) -> pd.DataFrame:
    """resp: question_id, y (answered rows only). Returns b, n, se_b per question."""
    g = resp.groupby("question_id").y.agg(["mean", "count"])
    b = logit_difficulty(g["mean"].values)
    p = np.clip(g["mean"].values, 0.03, 0.97)
    se = 1 / np.sqrt(np.maximum(g["count"].values, 1) * p * (1 - p))
    return pd.DataFrame({"question_id": g.index, "b": b, "n": g["count"].values, "se_b": se, "p_correct": g["mean"].values})


def fit_cells(resp: pd.DataFrame, b_by_question: dict | pd.Series, iters: int = 10) -> pd.DataFrame:
    """resp: student_id, topic_id, question_id, y (answered rows). Returns one row per (student, topic):
    theta, se, n, raw_pct. Questions without a stored difficulty are skipped."""
    if len(resp) == 0:
        return pd.DataFrame(columns=["student_id", "topic_id", "theta", "se", "n", "raw_pct"])
    r = resp.copy()
    r["b"] = r.question_id.map(b_by_question)
    r = r[r.b.notna()]
    key = r.student_id.astype(str) + "|" + r.topic_id.astype(str)
    codes, uniq = pd.factorize(key)
    y = r.y.values.astype(float)
    b = r.b.values.astype(float)
    n_cell = np.bincount(codes)
    k_cell = np.bincount(codes, weights=y)
    th = np.zeros(len(uniq))
    for _ in range(iters):
        p = sigmoid(th[codes] - b)
        g = np.bincount(codes, weights=y - p) - th / PRIOR_VAR
        h = np.bincount(codes, weights=p * (1 - p)) + 1 / PRIOR_VAR
        th += g / h
    p = sigmoid(th[codes] - b)
    se = 1 / np.sqrt(np.bincount(codes, weights=p * (1 - p)) + 1 / PRIOR_VAR)
    sid, tid = zip(*(u.split("|", 1) for u in uniq)) if len(uniq) else ([], [])
    return pd.DataFrame({"student_id": list(sid), "topic_id": list(tid), "theta": th, "se": se,
                         "n": n_cell, "raw_pct": k_cell / n_cell})


def band_of(theta: float, se: float, n: int) -> str:
    if n < MIN_N_FOR_BAND or se > MAX_SE_FOR_BAND:
        return "not_enough_data"
    return "strong" if theta > 0.5 else ("steady" if theta > -0.3 else "needs_support")


def add_bands(cells: pd.DataFrame) -> pd.DataFrame:
    if len(cells) == 0:
        return cells.assign(band=[])
    c = cells.copy()
    c["band"] = [band_of(t, s, n) for t, s, n in zip(c.theta, c.se, c.n)]
    return c


def point_biserial(resp: pd.DataFrame) -> pd.Series:
    """Per-question point-biserial of correctness against the student's mean correctness (answered rows)."""
    tot = resp.groupby("student_id").y.mean()
    r = resp.assign(tot=resp.student_id.map(tot))

    def pb(d):
        return np.corrcoef(d.y, d.tot)[0, 1] if d.y.std() > 0 and d.tot.std() > 0 else 0.0

    return r.groupby("question_id").apply(pb)


def flag_wrong_keys(resp: pd.DataFrame, threshold: float = WRONG_KEY_PB, min_n: int = 20) -> pd.DataFrame:
    """Questions whose point-biserial is below the threshold. Returns question_id, point_biserial, n."""
    if len(resp) == 0:
        return pd.DataFrame(columns=["question_id", "point_biserial", "n"])
    pb = point_biserial(resp)
    n = resp.groupby("question_id").size()
    out = pd.DataFrame({"point_biserial": pb, "n": n}).reset_index()
    return out[(out.point_biserial < threshold) & (out.n >= min_n)].sort_values("point_biserial")


# ---------------------------------------------------------------- scoring (re-score after a key change)
def _norm_set(val) -> set[str]:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return set()
    return {x.strip().upper() for x in str(val).replace(",", "|").split("|") if x.strip()}


def score_response(response, status: str, accepted: list[str], tolerance: float, dropped: bool,
                   q_type: str, scheme: dict) -> tuple[bool, float]:
    """Return (is_correct, marks) for one response under the marking scheme. Mirrors marking_schemes.yaml."""
    if dropped:
        return True, float(scheme["correct"])  # dropped_rule full_marks_all
    if status != "answered":
        return False, float(scheme["blank"])
    if q_type == "numeric":
        try:
            ok = any(abs(float(response) - float(a)) <= tolerance + 1e-9 for a in accepted)
        except (TypeError, ValueError):
            ok = False
    else:
        got, acc = _norm_set(response), {a.strip().upper() for a in accepted}
        ok = bool(got) and got <= acc
    return ok, float(scheme["correct"] if ok else scheme["wrong"])
