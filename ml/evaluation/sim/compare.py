"""E9 harness [SIM]: fixed path vs adaptive path vs ablations at equal item budgets.

This is the only file in ml/evaluation/sim that imports the engine, because it has to run it. The
simulator (simulator.py) never sees the engine, and the engine never sees the simulator's latent state:
a path only observes the (concept, item, correct) it served.

Run (from the repo root):
  python3 -m ml.evaluation.sim.compare --suite prereg --out ml/evaluation/results/e9_sim_v1.json
Every number is [SIM]: simulated learners, not evidence of learning outcomes.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from app.intelligence.graph import Edge, Graph                              # noqa: E402
from app.intelligence.planner import AdaptiveSession, PlannerConfig         # noqa: E402
from app.intelligence.selection import DIFFICULTY_SCALE, bank_from_records  # noqa: E402

from .simulator import SIM_EDGES, SIM_GOAL, SIM_NODES, SimConfig, SimLearner, make_bank  # noqa: E402

TARGET = "medium"
PATHS = ("fixed", "adaptive", "no_graph", "no_challenge", "no_revision", "no_budget")
ABLATION_FLAGS = {
    "adaptive": {}, "no_graph": {"use_graph": False}, "no_challenge": {"use_challenge": False},
    "no_revision": {"use_revision": False}, "no_budget": {"use_budget": False},
}
METRICS = ("final_mastered", "items_to_goal", "reached_goal", "violations", "items_used", "rechecks")
LABEL = "[SIM]"


def engine_graph() -> Graph:
    return Graph(SIM_NODES, [Edge(p, d, "reviewed") for p, d in SIM_EDGES])


def run_fixed(learner: SimLearner, cfg: SimConfig, bank: list[dict]) -> dict:
    """Curriculum order, equal items per concept, always at the target band, no revision, no adaptation."""
    n = len(SIM_NODES)
    plan = []
    for i, c in enumerate(SIM_NODES):
        plan += [c] * (cfg.budget // n + (1 if i < cfg.budget % n else 0))
    ids = {c: sorted(b["item_id"] for b in bank if b["topic_id"] == c and b["difficulty_target"] == TARGET)
           for c in SIM_NODES}
    used = {c: 0 for c in SIM_NODES}
    return _loop(learner, cfg, lambda slot, day: (plan[slot], ids[plan[slot]][used[plan[slot]]],
                                                   DIFFICULTY_SCALE[TARGET], "practice"),
                 lambda step, ok: used.__setitem__(step[0], used[step[0]] + 1), None)


def run_adaptive(learner: SimLearner, cfg: SimConfig, bank: list[dict], flags: dict) -> dict:
    session = AdaptiveSession(f"sim-{learner.idx}", engine_graph(), SIM_GOAL, bank_from_records(bank),
                              PlannerConfig(target=TARGET, **flags))
    holder = {}

    def choose(slot: int, day: int):
        step = session.next_step(day, holder["remaining"])
        holder["step"] = step
        if step.kind == "none":
            return None
        return (step.concept_id, step.item_id, DIFFICULTY_SCALE[step.selection.served_level_name], step.kind)

    def after(step, ok):
        session.record(holder["step"], ok, holder["day"])

    return _loop(learner, cfg, choose, after, holder)


def _loop(learner: SimLearner, cfg: SimConfig, choose, after, holder) -> dict:
    served = violations = rechecks = 0
    items_to_goal = 0 if learner.goal_mastered else None
    for slot in range(cfg.budget):
        day = slot // cfg.items_per_day
        if slot and slot % cfg.items_per_day == 0:
            learner.end_day()
        if holder is not None:
            holder["day"], holder["remaining"] = day, cfg.budget - slot   # slots left; idle slots also pass time
        step = choose(slot, day)
        if step is None:
            continue
        concept, _item, band, kind = step
        violations += learner.violates(concept)
        ok = learner.respond(concept, band)
        after(step, ok)
        served += 1
        rechecks += kind == "recheck"
        if items_to_goal is None and learner.goal_mastered:
            items_to_goal = served
    return {"final_mastered": learner.mastered_count,
            "items_to_goal": items_to_goal if items_to_goal is not None else cfg.budget,
            "reached_goal": int(items_to_goal is not None), "violations": violations,
            "items_used": served, "rechecks": rechecks}


def simulate(cfg: SimConfig, paths=PATHS) -> dict[str, dict[str, np.ndarray]]:
    bank = make_bank(cfg.bank_per_level)
    out = {p: {m: np.zeros(cfg.n_learners) for m in METRICS} for p in paths}
    for i in range(cfg.n_learners):
        for p in paths:
            learner = SimLearner(i, cfg)           # fresh copy of the same learner for every path
            res = run_fixed(learner, cfg, bank) if p == "fixed" else run_adaptive(learner, cfg, bank, ABLATION_FLAGS[p])
            for m in METRICS:
                out[p][m][i] = res[m]
    return out


def boot_ci(x: np.ndarray, idx: np.ndarray) -> tuple[float, float, float]:
    means = x[idx].mean(axis=1)
    return float(x.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def summarise(data: dict, cfg: SimConfig, boot_seed: int = 7, n_boot: int = 2000) -> dict:
    rng = np.random.default_rng(boot_seed)
    idx = rng.integers(0, cfg.n_learners, size=(n_boot, cfg.n_learners))   # shared resamples: paired
    rows = {p: {m: dict(zip(("mean", "lo", "hi"), boot_ci(data[p][m], idx))) for m in METRICS} for p in data}
    diffs = {}
    for p in data:
        if p == "fixed":
            continue
        diffs[f"{p}_minus_fixed"] = {m: dict(zip(("mean", "lo", "hi"), boot_ci(data[p][m] - data["fixed"][m], idx)))
                                     for m in METRICS}
        if p != "adaptive" and "adaptive" in data:
            diffs[f"{p}_minus_adaptive"] = {m: dict(zip(("mean", "lo", "hi"), boot_ci(data[p][m] - data["adaptive"][m], idx)))
                                            for m in METRICS}
    return {"label": LABEL, "task": "simulated mastery under equal item budget", "config": cfg.__dict__ | {"readiness_probs": list(cfg.readiness_probs)},
            "n_boot": n_boot, "boot_seed": boot_seed, "paths": rows, "paired_differences": diffs}


SUITE = {   # pre-registered in ml/evaluation/PREREGISTRATION.md
    "P_primary_neutral": dict(),
    "S1_zone_learning": dict(learning_model="zone"),
    "S2_no_forgetting": dict(forget_per_day=0.0),
    "S3_short_budget": dict(budget=36),
}


def run_suite(n: int, seed: int) -> dict:
    res = {}
    for name, over in SUITE.items():
        cfg = SimConfig(n_learners=n, seed=seed, **over)
        res[name] = summarise(simulate(cfg), cfg)
    return res


def fmt(v: dict) -> str:
    return f"{v['mean']:.2f} [{v['lo']:.2f}, {v['hi']:.2f}]"


def markdown(res: dict) -> str:
    lines = []
    for name, r in res.items():
        if name.startswith("_"):
            continue
        c = r["config"]
        lines += [f"### {name} {LABEL}", f"learners={c['n_learners']} seed={c['seed']} budget={c['budget']} "
                  f"model={c['learning_model']} forget/day={c['forget_per_day']}", "",
                  "| Path | final mastered (of 8) | items to goal (censored at budget) | reached goal | violations | items used | rechecks |",
                  "|---|---|---|---|---|---|---|"]
        for p, m in r["paths"].items():
            lines.append(f"| {p} | " + " | ".join(fmt(m[k]) for k in
                         ("final_mastered", "items_to_goal", "reached_goal", "violations", "items_used", "rechecks")) + " |")
        lines += ["", "Paired difference, adaptive minus fixed:", "", "| Metric | mean [95% CI] |", "|---|---|"]
        for k, v in r["paired_differences"]["adaptive_minus_fixed"].items():
            lines.append(f"| {k} | {fmt(v)} |")
        lines.append("")
    return "\n".join(lines)


def _git(*args: str) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()
    except Exception:
        return "unknown"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="prereg", choices=["prereg"])
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--seed", type=int, default=2026110501)
    ap.add_argument("--out", default=str(ROOT / "ml/evaluation/results/e9_sim_v1.json"))
    ap.add_argument("--note", default="", help="free text stored in provenance, e.g. post_hoc")
    a = ap.parse_args(argv)
    res = run_suite(a.n, a.seed)
    res["_provenance"] = {"label": LABEL, "code_commit": _git("rev-parse", "HEAD"),
                          "prereg_commit": _git("log", "-1", "--format=%H", "--", "ml/evaluation/PREREGISTRATION.md"),
                          "command": f"python3 -m ml.evaluation.sim.compare --suite {a.suite} --n {a.n} --seed {a.seed}",
                          "note": a.note}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=2, sort_keys=True) + "\n")
    Path(a.out).with_suffix(".md").write_text(markdown(res) + "\n")
    print(markdown(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
