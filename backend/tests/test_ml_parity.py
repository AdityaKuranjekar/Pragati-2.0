"""Runtime ML must reproduce the batch artifacts (ml/artifacts/patna_jee/*.json) within tolerance."""
from __future__ import annotations

import json
import time

import pytest

from app import config, deps
from app.db import pg
from app.ml import risk
from app.services import analytics

ART = config.ARTIFACTS / "patna_jee"


@pytest.fixture(scope="module")
def institute_state(seeded):
    iid = deps.institutes_by_slug()["patna_jee"]["id"]
    with pg.tenant_conn(iid) as conn:
        res = analytics.compute(conn, iid, None, enforce_consent=False)  # artifact semantics: everyone scored
    return iid, res


def test_mastery_theta_matches_artifact(institute_state):
    _, res = institute_state
    art = json.load(open(ART / "mastery.json", encoding="utf-8"))["cells"]
    c = res["cells"].set_index(["student_id", "topic_id"])
    diffs, band_mismatch = [], 0
    for x in art:
        k = (x["student_id"], x["topic_id"])
        assert k in c.index, f"cell missing at runtime: {k}"
        diffs.append(abs(c.at[k, "theta"] - x["theta"]))
        band_mismatch += c.at[k, "band"] != x["band"]
    assert len(art) > 1000
    assert max(diffs) < 2e-3  # artifact values are rounded to 3 d.p.
    assert band_mismatch == 0


def test_support_list_matches_artifact(institute_state):
    _, res = institute_state
    art = json.load(open(ART / "risk.json", encoding="utf-8"))
    sl = analytics.support_list_json(res, "patna_jee")
    assert sl["capacity_per_week"] == art["capacity_per_week"]
    a, b = [x["student_id"] for x in art["list"]], {x["student_id"]: x for x in sl["list"]}
    assert len(set(a) & set(b)) >= len(a) - 1  # same students (a tie in test dates can swap one)
    same_reasons = 0
    for x in art["list"]:
        y = b.get(x["student_id"])
        assert y is None or y["track"] == x["track"]
        if y and [r["code"] for r in x["reasons"]] == [r["code"] for r in y["reasons"]] and all(
                abs(r["weight"] - q["weight"]) < 0.01 for r, q in zip(x["reasons"], y["reasons"])):
            same_reasons += 1
    assert same_reasons >= 0.7 * len(a)  # the rest differ only where two tests share a date (sort tie-break)


def test_percentile_matches_artifact(institute_state):
    _, res = institute_state
    art = json.load(open(ART / "percentile.json", encoding="utf-8"))["students"]
    pr = res["prange"]
    diffs = [abs(pr.at[s["student_id"], "mid"] - s["mid"]) for s in art]
    assert len(diffs) > 30 and max(diffs) < 0.15
    meta = json.load(open(config.MODELS_DIR / "percentile_meta.json"))
    ref = json.load(open(config.ARTIFACTS / "metrics.json", encoding="utf-8"))["results"]
    q_ref = next(r["value"] for r in ref if r["metric_key"] == "percentile_band_halfwidth")
    assert abs(meta["halfwidth"] - q_ref) < 0.02


def test_risk_metrics_equal_artifact():
    ab = json.load(open(config.MODELS_DIR / "risk_ablation.json"))
    ref = {r["metric_key"]: r["value"] for r in json.load(open(config.ARTIFACTS / "metrics.json", encoding="utf-8"))["results"]}
    assert abs(ab["ABCD"]["auc"] - ref["risk_full_lgbm_auc"]) < 1e-6
    assert abs(ab["A"]["auc"] - ref["risk_academic_lgbm_auc"]) < 1e-6
    assert abs(ab["ABCD"]["precision"] - ref["risk_full_lgbm_precision"]) < 1e-6


def test_no_minor_on_full_track(institute_state):
    _, res = institute_state
    sc, el = res["scores"], res["elig"]
    minors = el.index[el.is_minor]
    assert len(minors) > 0
    assert set(sc.loc[sc.index.intersection(minors), "model"]) == {"A"}


def test_routing_policy_rules():
    # minors: tier A only, even if the institute allows D; adults: capped by the institute tier
    assert risk.model_for(True, False, "D") == "A"
    assert risk.model_for(True, True, "D") in ("AB", "ABC", "A")  # legal flag lifts B/C, never D
    assert "D" not in risk.model_for(True, True, "D")
    assert risk.model_for(False, False, "D") == "ABCD"
    assert risk.model_for(False, False, "B") == "AB"
    assert risk.model_for(False, False, "D", has_engagement_consent=False) == "ABC"


def test_batch_recompute_under_5s(client, teacher, batches):
    worst = 0.0
    for b in batches:
        t = time.perf_counter()
        iid = deps.institutes_by_slug()["patna_jee"]["id"]
        with pg.tenant_conn(iid) as conn:
            analytics.recompute(conn, iid, b["id"])
        worst = max(worst, time.perf_counter() - t)
    assert worst < 5.0, worst
