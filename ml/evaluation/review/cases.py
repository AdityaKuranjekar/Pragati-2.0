"""Simulated case profiles for E4 (root cause) and E6 (recommendation relevance). [SIM].

Profiles come from the E3 generator (ml/evaluation/sim/recovery.py), which does not import the engine.
Each Case holds both what a rater may see (ids, prerequisite graph, attempts and correct counts) and the
truth (latent mastery, binary state). Only the visible view is ever passed to a sheet.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from ..sim import recovery as gen

E4_SEED = 2026110504
E6_SEED = 2026110505
ITEMS_PER_CONCEPT = 6
GUESS = 0.25
POOL = 200     # learners simulated per course before filtering


@dataclass(frozen=True)
class Case:
    case_id: str
    course: str             # "D1" or "D3": the prerequisite depth of the course
    concepts: tuple         # ids in curriculum (topological) order
    prereqs: dict           # visible: concept -> tuple of prerequisites
    goal: str               # visible
    correct: dict           # visible: concept -> correct answers out of ITEMS_PER_CONCEPT
    seq: dict               # engine input only: concept -> tuple of item outcomes in order (not shown to raters)
    m: dict                 # TRUTH: latent continuous mastery
    M: dict                 # TRUTH: binary state (m >= 0.85)


def case_id(seed: int, tag: str, index: int) -> str:
    return "C-" + hashlib.sha256(f"{seed}:{tag}:{index}".encode()).hexdigest()[:8]


def build_course(seed: int, depth: int, n_concepts: int = 10) -> tuple[gen.RecoveryDesign, dict]:
    design = gen.RecoveryDesign(n_concepts=n_concepts, depth=depth, guess=GUESS, n_learners=POOL, seed=seed)
    truth = gen.generate(design)
    return design, truth


def visible_view(case: Case) -> dict:
    """Everything a rater may see. Nothing from the truth."""
    return {"case_id": case.case_id, "concepts": list(case.concepts),
            "prereqs": {c: list(p) for c, p in case.prereqs.items()}, "goal": case.goal,
            "correct": dict(case.correct), "attempts": ITEMS_PER_CONCEPT}


def _cases_from(truth: dict, design: gen.RecoveryDesign, course: str, tag: str, indices, seed: int) -> list[Case]:
    ids = gen.concept_ids(design.n_concepts)
    resp = gen.responses(truth["u"], truth["m"], GUESS, ITEMS_PER_CONCEPT)
    out = []
    for i in indices:
        out.append(Case(
            case_id=case_id(seed, tag, i), course=course, concepts=ids,
            prereqs=truth["graph"]["prereqs"], goal=truth["graph"]["goal"],
            correct={c: int(resp[i, j].sum()) for j, c in enumerate(ids)},
            seq={c: tuple(bool(x) for x in resp[i, j]) for j, c in enumerate(ids)},
            m={c: float(truth["m"][i, j]) for j, c in enumerate(ids)},
            M={c: bool(truth["M"][i, j]) for j, c in enumerate(ids)}))
    return out


def e4_cases(seed: int = E4_SEED, per_course: int = 20) -> list[Case]:
    """Cases whose goal is unmastered: each has a root cause (see keys.root_cause). Two courses, depth 1 and 3."""
    out = []
    for depth in (1, 3):
        design, truth = build_course(seed, depth)
        goal_idx = design.n_concepts - 1
        wanted = [i for i in range(POOL) if not truth["M"][i, goal_idx]][:per_course]
        if len(wanted) < per_course:
            raise RuntimeError(f"only {len(wanted)} unmastered-goal learners at depth {depth}")
        out += _cases_from(truth, design, f"D{depth}", f"e4-d{depth}", wanted, seed)
    return out


def e6_cases(seed: int = E6_SEED, per_course: int = 25) -> list[Case]:
    """First learners of each course, with no filter on mastery: raters judge every profile."""
    out = []
    for depth in (1, 3):
        design, truth = build_course(seed, depth)
        out += _cases_from(truth, design, f"D{depth}", f"e6-d{depth}", range(per_course), seed)
    return out
