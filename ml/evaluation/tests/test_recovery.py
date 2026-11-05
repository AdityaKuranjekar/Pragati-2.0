"""E3 [SIM]: the generator is independent of the engine, is deterministic for a fixed seed, respects the design,
and the committed E3 result file has the shape and provenance the evaluation page reads."""
import ast
import json
import math
from pathlib import Path

import numpy as np
import pytest

from ml.evaluation.sim import recovery as gen

ROOT = Path(__file__).resolve().parents[3]
RESULT = ROOT / "ml/evaluation/results/e3_recovery_v1.json"


def _imports(path: Path) -> set[str]:
    out = set()
    for n in ast.walk(ast.parse(path.read_text())):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            out.add(("." * n.level) + (n.module or ""))
    return out


def test_generator_never_imports_or_names_the_engine():
    src = Path(gen.__file__).read_text()
    for mod in _imports(Path(gen.__file__)):
        assert "intelligence" not in mod and not mod.startswith("app") and "backend" not in mod, mod
    for banned in ("app.intelligence", "fold_concept", "band_for", "BKTParams", "DEFAULT_PARAMS"):
        assert banned not in src


def test_generator_truth_threshold_matches_the_product_threshold():
    import sys
    sys.path.insert(0, str(ROOT / "backend"))
    from app.intelligence.mastery import MASTERED_AT          # test side only; the generator copies the number
    assert gen.MASTERED_AT == MASTERED_AT == 0.85


def test_same_seed_gives_identical_truth_and_responses():
    d = gen.RecoveryDesign(n_concepts=10, depth=3, guess=0.25, n_learners=40, seed=77)
    a, b = gen.generate(d), gen.generate(d)
    assert np.array_equal(a["m"], b["m"]) and np.array_equal(a["u"], b["u"])
    assert np.array_equal(gen.responses(a["u"], a["m"], 0.25, 6), gen.responses(b["u"], b["m"], 0.25, 6))
    other = gen.generate(gen.RecoveryDesign(n_concepts=10, depth=3, guess=0.25, n_learners=40, seed=78))
    assert not np.array_equal(a["m"], other["m"])


@pytest.mark.parametrize("c,d", [(10, 1), (10, 3), (30, 1), (30, 3)])
def test_graph_matches_the_design(c, d):
    g = gen.make_graph(c, d, seed=5)
    assert gen.chain_depth(g["prereqs"]) == d
    ids = gen.concept_ids(c)
    for j, x in enumerate(ids):
        for p in g["prereqs"][x]:
            assert ids.index(p) < j                  # topological order by construction
    assert g["goal"] == ids[-1]


def test_latent_mastery_respects_prerequisite_cap():
    d = gen.RecoveryDesign(n_concepts=30, depth=3, guess=0.25, n_learners=120, seed=9)
    t = gen.generate(d)
    ids = gen.concept_ids(30)
    pre = t["graph"]["prereqs"]
    for i in range(120):
        for j, c in enumerate(ids):
            if pre[c]:
                floor = min(t["m"][i, ids.index(p)] for p in pre[c])
                assert t["m"][i, j] <= floor + gen.PREREQ_SLACK + 1e-12
            assert 0.0 <= t["m"][i, j] <= 1.0
            assert bool(t["M"][i, j]) == (t["m"][i, j] >= 0.85)


def test_guessing_raises_correctness_at_zero_mastery_and_prefixes_are_consistent():
    m = np.zeros((1, 1)); u = np.random.default_rng(1).random((1, 1, 20))
    lo = gen.responses(u, m, 0.25, 20).mean()
    hi = gen.responses(u, m, 0.40, 20).mean()
    assert hi > lo
    full = gen.responses(u, np.full((1, 1), 0.6), 0.25, 20)
    short = gen.responses(u, np.full((1, 1), 0.6), 0.25, 6)
    assert np.array_equal(full[:, :, :6], short)


def test_metric_helpers_on_known_values():
    x = np.array([1.0, 2.0, 3.0, 4.0]); y = np.array([2.0, 4.0, 6.0, 8.0])
    assert gen.pearson(x, y) == pytest.approx(1.0)
    assert gen.spearman(x, -y) == pytest.approx(-1.0)
    assert gen.average_ranks(np.array([1, 1, 3])).tolist() == [1.5, 1.5, 3.0]
    acc, prec, rec = gen.state_counts(np.array([False, False]), np.array([True, False]))
    assert acc == 0.5 and math.isnan(prec) and rec == 0.0


def test_wilson_interval_contains_the_share():
    correct = np.array([[[1, 1, 1, 0, 0, 0]]], dtype=bool)
    share, lo, hi = gen.wilson(correct, 6)
    assert share[0, 0] == pytest.approx(0.5)
    assert lo[0, 0] < 0.5 < hi[0, 0]


def test_committed_result_has_the_registered_shape_and_provenance():
    res = json.loads(RESULT.read_text().replace("NaN", "null"))   # the file keeps Python's NaN for undefined cells
    prov = res["_provenance"]
    assert prov["label"] == "[SIM]" and prov["seed"] == 2026110502 and prov["n_learners_per_cell"] == 500
    assert len(prov["code_commit"]) == 40 and len(prov["prereg_commit"]) == 40
    keys = [k for k in res if not k.startswith("_")]
    assert len(keys) == 32
    assert {res[k]["config"]["n_concepts"] for k in keys} == {10, 30}
    assert {res[k]["config"]["depth"] for k in keys} == {1, 3}
    assert {res[k]["config"]["guess"] for k in keys} == {0.25, 0.40}
    assert {res[k]["config"]["items_per_concept"] for k in keys} == {3, 6, 10, 20}
    for k in keys:
        assert res[k]["label"] == "[SIM]"
        assert set(res[k]["paths"]) == {"estimator", "baseline_share_correct"}
        assert set(res[k]["paired_differences"]["estimator_minus_baseline"]) >= {"pearson_r", "coverage80"}


def test_committed_result_reports_the_negative_findings():
    """The results were written before any reader existed; these assertions pin what the registered run showed."""
    res = json.loads(RESULT.read_text().replace("NaN", "null"))
    for k, s in res.items():
        if k.startswith("_"):
            continue
        k_items = s["config"]["items_per_concept"]
        if k_items >= 10:
            assert s["paths"]["estimator"]["pearson_r"]["lo"] < 0.80        # r bar missed everywhere
        if k_items == 3:
            assert s["paths"]["estimator"]["state_recall"]["mean"] == 0.0   # engine needs 5 answers to say mastered
            assert s["share_shown_as_band"] == 1.0                           # a band is shown below 10 items
        diff = s["paired_differences"]["estimator_minus_baseline"]["pearson_r"]
        if k_items >= 10:
            assert diff["hi"] < 0                                          # engine worse than raw share at 10 and 20
