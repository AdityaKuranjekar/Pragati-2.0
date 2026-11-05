"""E3 generator and metrics [SIM]. Independent of the estimator: this module must not import anything from
backend/app/intelligence (enforced by ml/evaluation/tests/test_recovery.py). The engine is run by
recovery_run.py, the harness, which is the only file in this package allowed to import it.

What it generates (see ml/evaluation/PREREGISTRATION.md, section "E3")
  * A layered prerequisite DAG: C concepts in D+1 contiguous layers; each concept in layer l >= 1 has one or
    two prerequisites in layer l-1. The longest chain therefore has D edges.
  * Concept difficulty b_c ~ N(0, 0.5) and learner ability theta ~ N(0, 1).
  * Latent continuous mastery m_c, in topological order: raw = sigmoid(2 (theta - b_c)); a concept with
    prerequisites is capped at the lowest prerequisite mastery plus PREREQ_SLACK. This is an ASSUMPTION about
    how prerequisites limit mastery.
  * Latent binary state M_c = (m_c >= MASTERED_AT). MASTERED_AT is the product threshold, copied as a number
    because the truth must not depend on the engine.
  * Responses: item j on concept c is correct when u_j < guess + (1 - guess - SLIP) * m_c. The uniforms u come
    from a per-(learner, concept) stream, so the first k items of a longer run equal a shorter run, and the
    same learners and uniforms are reused across guessing settings (paired comparison).

Every constant is an assumption of the simulation. Item difficulty is not modelled (stated limit).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

import numpy as np

SLIP = 0.10
MASTERY_LINK = 2.0        # slope of the logistic link from ability to raw mastery
PREREQ_SLACK = 0.10       # a dependent concept may sit this far above its weakest prerequisite
MASTERED_AT = 0.85        # the product threshold (truth side; the engine's constant is checked by a test)
MAX_ITEMS = 20
Z80 = 1.2815515655446004  # standard normal 90th percentile: half-width of a central 80% interval, in SD units


@dataclass(frozen=True)
class RecoveryDesign:
    n_concepts: int
    depth: int
    guess: float
    n_learners: int = 500
    seed: int = 2026110502
    max_items: int = MAX_ITEMS


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def concept_ids(n_concepts: int) -> tuple[str, ...]:
    return tuple(f"k{j:02d}" for j in range(n_concepts))


def layer_of(j: int, n_concepts: int, depth: int) -> int:
    return j * (depth + 1) // n_concepts


def make_graph(n_concepts: int, depth: int, seed: int) -> dict:
    """Returns {'prereqs': {concept: tuple}, 'difficulty': {concept: float}, 'goal': concept}.
    Concepts are numbered in topological order: every prerequisite has a smaller index."""
    if depth < 1 or n_concepts < depth + 1:
        raise ValueError("need depth >= 1 and at least depth + 1 concepts")
    rng = random.Random(f"{seed}:graph:{n_concepts}:{depth}")
    ids = concept_ids(n_concepts)
    prereqs: dict[str, tuple[str, ...]] = {}
    for j, c in enumerate(ids):
        lay = layer_of(j, n_concepts, depth)
        if lay == 0:
            prereqs[c] = ()
            continue
        pool = [ids[x] for x in range(n_concepts) if layer_of(x, n_concepts, depth) == lay - 1]
        k = 2 if (len(pool) >= 2 and rng.random() < 0.5) else 1
        prereqs[c] = tuple(sorted(rng.sample(pool, k)))
    difficulty = {c: rng.gauss(0.0, 0.5) for c in ids}
    return {"prereqs": prereqs, "difficulty": difficulty, "goal": ids[-1]}


def chain_depth(prereqs: dict) -> int:
    """Longest prerequisite chain, in edges (checked against the design in tests)."""
    memo: dict[str, int] = {}

    def d(c: str) -> int:
        if c not in memo:
            memo[c] = 0 if not prereqs[c] else 1 + max(d(p) for p in prereqs[c])
        return memo[c]

    return max(d(c) for c in prereqs)


def generate(design: RecoveryDesign) -> dict:
    """Learners' latent truth and uniforms. Shapes: m (N, C), M (N, C) bool, u (N, C, MAX_ITEMS)."""
    g = make_graph(design.n_concepts, design.depth, design.seed)
    ids = concept_ids(design.n_concepts)
    n, c_n = design.n_learners, design.n_concepts
    m = np.zeros((n, c_n))
    u = np.zeros((n, c_n, design.max_items))
    for i in range(n):
        theta = random.Random(f"{design.seed}:{i}:{c_n}:{design.depth}:init").gauss(0.0, 1.0)
        for j, c in enumerate(ids):
            raw = _sigmoid(MASTERY_LINK * (theta - g["difficulty"][c]))
            pre = g["prereqs"][c]
            val = raw if not pre else min(raw, min(m[i, ids.index(p)] for p in pre) + PREREQ_SLACK)
            m[i, j] = min(1.0, max(0.0, val))
            stream = random.Random(f"{design.seed}:{i}:{c_n}:{design.depth}:{c}:u")
            u[i, j] = [stream.random() for _ in range(design.max_items)]
    return {"m": m, "M": m >= MASTERED_AT, "u": u, "graph": g}


def responses(u: np.ndarray, m: np.ndarray, guess: float, k: int) -> np.ndarray:
    """Correctness of the first k items, shape (N, C, k)."""
    p = guess + (1.0 - guess - SLIP) * m
    return u[:, :, :k] < p[:, :, None]


def wilson(correct: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Raw share correct and its Wilson 80% interval (the baseline's interval)."""
    p = correct.sum(axis=2) / k
    z2 = Z80 ** 2
    centre = (p + z2 / (2 * k)) / (1 + z2 / k)
    half = Z80 * np.sqrt(p * (1 - p) / k + z2 / (4 * k * k)) / (1 + z2 / k)
    return p, np.clip(centre - half, 0, 1), np.clip(centre + half, 0, 1)


def average_ranks(a: np.ndarray) -> np.ndarray:
    order = np.argsort(a, kind="mergesort")
    _, inv, counts = np.unique(a[order], return_inverse=True, return_counts=True)
    end = np.cumsum(counts)
    avg = end - (counts - 1) / 2.0
    ranks = np.empty(len(a))
    ranks[order] = avg[inv]
    return ranks


def pearson(x: np.ndarray, y: np.ndarray) -> float:
    x, y = x - x.mean(), y - y.mean()
    den = math.sqrt(float((x * x).sum()) * float((y * y).sum()))
    return float((x * y).sum()) / den if den > 0 else float("nan")


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    return pearson(average_ranks(x), average_ranks(y))


def state_counts(pred: np.ndarray, truth: np.ndarray) -> tuple[float, float, float]:
    """Accuracy, precision (nan if nothing predicted mastered), recall (nan if nothing truly mastered)."""
    tp = float(np.sum(pred & truth))
    fp = float(np.sum(pred & ~truth))
    fn = float(np.sum(~pred & truth))
    acc = float(np.mean(pred == truth))
    prec = tp / (tp + fp) if tp + fp > 0 else float("nan")
    rec = tp / (tp + fn) if tp + fn > 0 else float("nan")
    return acc, prec, rec


def bundle(est: np.ndarray, lo: np.ndarray, hi: np.ndarray, m: np.ndarray, pred: np.ndarray, truth: np.ndarray) -> dict:
    """All pre-registered metrics for one estimator over a set of learner x concept rows (flattened)."""
    acc, prec, rec = state_counts(pred, truth)
    return {
        "pearson_r": pearson(est, m),
        "spearman_rho": spearman(est, m),
        "rmse": float(np.sqrt(np.mean((est - m) ** 2))),
        "coverage80": float(np.mean((m >= lo) & (m <= hi))),
        "state_accuracy": acc,
        "state_precision": prec,
        "state_recall": rec,
    }


def bootstrap_bundles(est, lo, hi, m, pred, truth, idx: np.ndarray) -> list[dict]:
    """The bundle for every learner resample. est, lo, hi, m, pred, truth have shape (N, C); idx is (B, N)."""
    out = []
    for row in idx:
        out.append(bundle(est[row].ravel(), lo[row].ravel(), hi[row].ravel(), m[row].ravel(),
                          pred[row].ravel(), truth[row].ravel()))
    return out
