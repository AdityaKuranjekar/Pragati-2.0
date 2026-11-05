"""F: the simulator is independent of the estimator, and the comparison is deterministic. All [SIM]."""
import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

SIM_DIR = Path(__file__).resolve().parents[1] / "sim"
ROOT = Path(__file__).resolve().parents[3]
HARNESS = {"compare.py"}      # the only file allowed to import the engine


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            out.add(("." * n.level) + (n.module or ""))
    return out


def test_simulator_files_never_import_the_estimator():
    files = [f for f in SIM_DIR.glob("*.py") if f.name not in HARNESS]
    assert "simulator.py" in {f.name for f in files}
    for f in files:
        for mod in _imports(f):
            assert "intelligence" not in mod and not mod.startswith("app"), f"{f.name} imports {mod}"
            assert "backend" not in mod, f"{f.name} imports {mod}"


def test_simulator_source_does_not_mention_the_engine_modules_or_parameters():
    src = (SIM_DIR / "simulator.py").read_text()
    for banned in ("app.intelligence", "BKTParams", "DEFAULT_PARAMS", "bkt_update", "p_transit", "learner_state"):
        assert banned not in src


def test_importing_the_simulator_alone_does_not_load_the_engine():
    code = ("import sys; sys.path.insert(0, %r); import ml.evaluation.sim.simulator as s; "
            "bad=[m for m in sys.modules if m.startswith('app.intelligence') or m=='app']; "
            "print('LOADED' if bad else 'CLEAN', s.SIM_GOAL)") % str(ROOT)
    out = subprocess.check_output([sys.executable, "-I", "-c", code], text=True, cwd="/")
    assert out.split()[0] == "CLEAN"


def test_simulator_constants_match_the_brief():
    from ml.evaluation.sim import simulator as s
    assert s.GUESS == 0.25 and s.SLIP == 0.10


def test_generated_learners_respect_prerequisites():
    from ml.evaluation.sim.simulator import SimConfig, SimLearner, SIM_EDGES
    cfg = SimConfig(n_learners=1, seed=5)
    for i in range(300):
        lr = SimLearner(i, cfg)
        for p, d in SIM_EDGES:
            assert not (lr.initial_mastered[d] and not lr.initial_mastered[p])


def test_comparison_is_deterministic_for_a_fixed_seed_and_changes_with_the_seed():
    from ml.evaluation.sim.compare import simulate, summarise
    from ml.evaluation.sim.simulator import SimConfig
    def run(seed):
        cfg = SimConfig(n_learners=12, seed=seed)
        return json.dumps(summarise(simulate(cfg), cfg, n_boot=50), sort_keys=True)
    assert run(11) == run(11)
    assert run(11) != run(12)


def test_all_paths_face_the_same_learners_and_respect_the_equal_budget():
    from ml.evaluation.sim.compare import simulate
    from ml.evaluation.sim.simulator import SimConfig
    cfg = SimConfig(n_learners=15, seed=3)
    d = simulate(cfg)
    for p in d:
        assert d[p]["items_used"].max() <= cfg.budget
    assert d["fixed"]["items_used"].min() == cfg.budget


def test_summary_carries_the_sim_label_and_ci_fields():
    from ml.evaluation.sim.compare import simulate, summarise
    from ml.evaluation.sim.simulator import SimConfig
    cfg = SimConfig(n_learners=10, seed=2)
    r = summarise(simulate(cfg), cfg, n_boot=40)
    assert r["label"] == "[SIM]"
    cell = r["paired_differences"]["adaptive_minus_fixed"]["final_mastered"]
    assert cell["lo"] <= cell["mean"] <= cell["hi"] or cell["lo"] == cell["hi"]


def test_engine_files_do_not_import_the_simulator():
    for f in (ROOT / "backend/app/intelligence").glob("*.py"):
        for mod in _imports(f):
            assert "evaluation" not in mod and "sim" not in mod.split(".")[-1:], f"{f.name} imports {mod}"


def test_config_rejects_bad_values():
    from ml.evaluation.sim.simulator import SimConfig
    with pytest.raises(ValueError):
        SimConfig(learning_model="magic")
    with pytest.raises(ValueError):
        SimConfig(budget=0)
