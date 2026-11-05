"""E3 harness [SIM]: runs the engine's BKT fold on simulated attempts and scores it against latent mastery.

This file imports the engine because it has to run it. recovery.py (the generator) does not. The engine sees
only (learner, concept, item, correct, seq) events; it never sees m, M or the graph.

Run (from the repo root):
  python3 -m ml.evaluation.sim.recovery_run --suite prereg --n 500 --seed 2026110502 \
      --out ml/evaluation/results/e3_recovery_v1.json
Every number is [SIM]: simulated learners under stated assumptions, not evidence about real students.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from app.intelligence.events import AttemptEvent                 # noqa: E402
from app.intelligence.mastery import fold_concept                # noqa: E402

from . import recovery as gen                                    # noqa: E402

LABEL = "[SIM]"
TASK = "mastery recovery on simulated learners (latent continuous mastery and binary state at 0.85)"
CELLS_C = (10, 30)
CELLS_D = (1, 3)
GUESSES = (0.25, 0.40)
ITEMS = (3, 6, 10, 20)
N_BOOT = 2000
BOOT_SEED = 7
METRICS = ("pearson_r", "spearman_rho", "rmse", "coverage80", "state_accuracy", "state_precision", "state_recall")
PAIRED = ("pearson_r", "spearman_rho", "rmse", "coverage80", "state_accuracy")
Z = gen.Z80


def engine_estimates(correct: np.ndarray, concept_names: tuple[str, ...], learner_offset: int = 0):
    """Folds each (learner, concept) with the engine. Returns p, n, band (strings), uncertainty, shape (N, C)."""
    n_learn, n_con, k = correct.shape
    p = np.zeros((n_learn, n_con))
    unc = np.zeros((n_learn, n_con))
    band = np.empty((n_learn, n_con), dtype=object)
    for i in range(n_learn):
        for j, c in enumerate(concept_names):
            events = [AttemptEvent(event_id=f"{i + learner_offset}:{c}:{s}", learner_id=f"l{i + learner_offset}",
                                   concept_id=c, item_id=f"{c}:{s}", correct=bool(correct[i, j, s]), seq=s)
                      for s in range(k)]
            st = fold_concept(events, c)
            p[i, j], unc[i, j], band[i, j] = st.p_known, st.uncertainty, st.band
    return p, unc, band


def setting_key(c: int, d: int, g: float, k: int) -> str:
    return f"C{c}_D{d}_g{g:.2f}_k{k}"


def run_setting(design: gen.RecoveryDesign, k: int, truth: dict, boot_idx: np.ndarray) -> dict:
    ids = gen.concept_ids(design.n_concepts)
    m, M, u = truth["m"], truth["M"], truth["u"]
    correct = gen.responses(u, m, design.guess, k)
    p, unc, band = engine_estimates(correct, ids)
    lo_e = np.clip(p - Z * unc, 0, 1)
    hi_e = np.clip(p + Z * unc, 0, 1)
    pred_e = band == "mastered"
    share, lo_b, hi_b = gen.wilson(correct, k)
    pred_b = (share >= gen.MASTERED_AT) & (k >= 5)
    est_sets = {
        "estimator": dict(est=p, lo=lo_e, hi=hi_e, pred=pred_e),
        "baseline_share_correct": dict(est=share, lo=lo_b, hi=hi_b, pred=pred_b),
    }
    paths, boots = {}, {}
    for name, s in est_sets.items():
        point = gen.bundle(s["est"].ravel(), s["lo"].ravel(), s["hi"].ravel(), m.ravel(), s["pred"].ravel(), M.ravel())
        bs = gen.bootstrap_bundles(s["est"], s["lo"], s["hi"], m, s["pred"], M, boot_idx)
        boots[name] = bs
        paths[name] = {key: {"mean": point[key], "lo": _pct(bs, key, 2.5), "hi": _pct(bs, key, 97.5),
                             "undefined_in_boot": _undef(bs, key)} for key in METRICS}
    diffs = {key: {"mean": paths["estimator"][key]["mean"] - paths["baseline_share_correct"][key]["mean"],
                   "lo": _pct_diff(boots, key, 2.5), "hi": _pct_diff(boots, key, 97.5)} for key in PAIRED}
    return {
        "label": LABEL, "task": TASK,
        "config": {"n_concepts": design.n_concepts, "depth": design.depth, "guess": design.guess,
                   "items_per_concept": k, "n_learners": design.n_learners, "seed": design.seed,
                   "slip": gen.SLIP, "mastery_link": gen.MASTERY_LINK, "prereq_slack": gen.PREREQ_SLACK,
                   "mastered_at": gen.MASTERED_AT, "implied_interval_z": Z, "n_boot": N_BOOT, "boot_seed": BOOT_SEED},
        "n_rows": int(m.size),
        "prevalence": float(M.mean()),
        "share_shown_as_band": float(np.mean(band != "insufficient")),
        "paths": paths,
        "paired_differences": {"estimator_minus_baseline": diffs},
        "pass_bar": _pass_bar(k, paths, diffs),
    }


def _pct(bs: list[dict], key: str, q: float) -> float:
    vals = np.array([b[key] for b in bs], dtype=float)
    return float(np.nanpercentile(vals, q)) if np.isfinite(vals).any() else float("nan")


def _undef(bs: list[dict], key: str) -> float:
    return float(np.mean([not np.isfinite(b[key]) for b in bs]))


def _pct_diff(boots: dict, key: str, q: float) -> float:
    a = np.array([b[key] for b in boots["estimator"]], dtype=float)
    b_ = np.array([b[key] for b in boots["baseline_share_correct"]], dtype=float)
    d = a - b_
    return float(np.nanpercentile(d, q)) if np.isfinite(d).any() else float("nan")


def _pass_bar(k: int, paths: dict, diffs: dict) -> dict:
    """Pre-registered bar, applied only at k >= 10. Below 10 the bar is 'not enough evidence' and is checked separately."""
    if k < 10:
        return {"applies": False, "r_pass": None, "coverage_pass": None}
    r = paths["estimator"]["pearson_r"]
    cov = paths["estimator"]["coverage80"]
    return {"applies": True, "r_pass": bool(r["lo"] >= 0.80), "coverage_pass": bool(cov["lo"] >= 0.75 and cov["hi"] <= 0.85)}


def run_suite(n: int, seed: int) -> dict:
    res = {}
    boot_rng = np.random.default_rng(BOOT_SEED)
    for c in CELLS_C:
        for d in CELLS_D:
            design0 = gen.RecoveryDesign(n_concepts=c, depth=d, guess=GUESSES[0], n_learners=n, seed=seed)
            truth = gen.generate(design0)
            if gen.chain_depth(truth["graph"]["prereqs"]) != d:
                raise RuntimeError(f"generated graph depth {gen.chain_depth(truth['graph']['prereqs'])} != {d}")
            boot_idx = boot_rng.integers(0, n, size=(N_BOOT, n))   # shared by every setting in the cell
            for g in GUESSES:
                design = gen.RecoveryDesign(n_concepts=c, depth=d, guess=g, n_learners=n, seed=seed)
                for k in ITEMS:
                    res[setting_key(c, d, g, k)] = run_setting(design, k, truth, boot_idx)
    return res


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()
    except Exception:
        return "unknown"


def markdown(res: dict) -> str:
    lines = [f"# E3 mastery recovery {LABEL}", "", TASK + ". Every row is simulated; none is evidence about real students.", "",
             "| Setting | items | r (95% CI) | Spearman (95% CI) | RMSE | coverage80 (95% CI) | state acc | state precision | state recall | shows band | pass bar (k>=10) |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for key, r in res.items():
        if key.startswith("_"):
            continue
        e = r["paths"]["estimator"]
        cell = lambda m: f"{e[m]['mean']:.2f} [{e[m]['lo']:.2f}, {e[m]['hi']:.2f}]"  # noqa: E731
        pb = r["pass_bar"]
        verdict = "not applicable (<10)" if not pb["applies"] else f"r {'pass' if pb['r_pass'] else 'miss'}; coverage {'pass' if pb['coverage_pass'] else 'miss'}"
        lines.append(f"| {key} | {r['config']['items_per_concept']} | {cell('pearson_r')} | {cell('spearman_rho')} | "
                     f"{e['rmse']['mean']:.2f} | {cell('coverage80')} | {e['state_accuracy']['mean']:.2f} | "
                     f"{e['state_precision']['mean']:.2f} | {e['state_recall']['mean']:.2f} | {r['share_shown_as_band']:.2f} | {verdict} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="prereg", choices=["prereg"])
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--seed", type=int, default=2026110502)
    ap.add_argument("--out", default=str(ROOT / "ml/evaluation/results/e3_recovery_v1.json"))
    ap.add_argument("--note", default="", help="free text stored in provenance")
    a = ap.parse_args(argv)
    res = run_suite(a.n, a.seed)
    res["_provenance"] = {
        "label": LABEL, "task": TASK, "seed": a.seed, "n_learners_per_cell": a.n,
        "code_commit": _git("rev-parse", "HEAD"),
        "prereg_commit": _git("log", "-1", "--format=%H", "--", "ml/evaluation/PREREGISTRATION.md"),
        "generator_sha256": _sha256(Path(gen.__file__)),
        "harness_sha256": _sha256(Path(__file__)),
        "command": f"python3 -m ml.evaluation.sim.recovery_run --suite {a.suite} --n {a.n} --seed {a.seed}",
        "run_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": a.note,
    }
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, sort_keys=True) + "\n")
    out.with_suffix(".md").write_text(markdown(res))
    print(markdown(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
