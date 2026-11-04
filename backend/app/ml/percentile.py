"""Runtime percentile range: saved LightGBM point model + conformal half-width (80 % target).

The mapping from mock scores to percentile is learned from the generator's synthetic outcomes and is labelled
an assumption everywhere; the editable mapping table is returned as stored in models/percentile_mapping.json.
"""
from __future__ import annotations

import functools
import json

import lightgbm as lgb
import pandas as pd

from .. import config
from . import risk as risk_mod

PF = ["m3", "mall", "chap", "n"]


def features(tt: pd.DataFrame, asof: pd.Timestamp, strict: bool = False) -> pd.DataFrame:
    """tt[student_id, test_date, pct, exam_pattern_code]; one row per student with at least one test.
    strict=True (training) keeps only students with at least one non-internal test, as ml/build_artifacts.py did;
    at runtime students with only chapter tests still get a range (falling back to their chapter-test mean)."""
    t = tt[(tt.test_date <= asof) & (tt.exam_pattern_code != "internal_chapter_test")].sort_values("test_date")
    if t.empty:
        t = tt[tt.test_date <= asof].sort_values("test_date")
    g = t.groupby("student_id")
    F = pd.DataFrame({"m3": g.tail(3).groupby("student_id").pct.mean(), "mall": g.pct.mean(), "n": g.size()})
    ch = tt[tt.test_date <= asof].groupby("student_id").pct.mean().rename("chap")
    F = F.join(ch, how="left" if strict else "outer")
    F["m3"] = F.m3.fillna(F.chap)
    F["mall"] = F.mall.fillna(F.chap)
    F["n"] = F.n.fillna(0)
    return F.dropna(subset=["chap"])


@functools.lru_cache(maxsize=1)
def _model() -> lgb.Booster:
    return risk_mod.load_model_file(config.MODELS_DIR / "percentile_point.txt")


@functools.lru_cache(maxsize=1)
def meta() -> dict:
    return json.loads((config.MODELS_DIR / "percentile_meta.json").read_text(encoding="utf-8"))


def predict_range(F: pd.DataFrame) -> pd.DataFrame:
    if len(F) == 0:
        return pd.DataFrame(columns=["low", "mid", "high"])
    q = meta()["halfwidth"]
    mid = _model().predict(F[PF])
    return pd.DataFrame({"low": (mid - q).clip(min=0).round(1), "mid": mid.round(1),
                         "high": (mid + q).clip(max=100).round(1)}, index=F.index)
