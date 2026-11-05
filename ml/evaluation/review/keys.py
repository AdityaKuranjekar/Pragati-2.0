"""Answer keys for E4 and E6 [SIM]. Written to keys/ (git-ignored). Never shown to raters, never read by sheets.py.

E4 root cause (definition, not an expert label): among the goal chain (goal and its ancestors), the unmastered
concepts whose prerequisites are all truly mastered (the frontier), the root is the frontier concept with the
lowest latent mastery (ties by id). For an unmastered goal the frontier is never empty (the earliest unmastered
concept in the chain has only mastered prerequisites, or it would not be earliest).
"""
from __future__ import annotations

import json
from pathlib import Path

from .cases import Case


def ancestors(prereqs: dict, c: str) -> set:
    out, stack = set(), list(prereqs[c])
    while stack:
        p = stack.pop()
        if p not in out:
            out.add(p)
            stack.extend(prereqs[p])
    return out


def descendants(prereqs: dict, c: str) -> set:
    return {d for d in prereqs if c in ancestors(prereqs, d)}


def root_cause(case: Case) -> str:
    chain = ancestors(case.prereqs, case.goal) | {case.goal}
    frontier = [c for c in chain if not case.M[c] and all(case.M[p] for p in case.prereqs[c])]
    if not frontier:
        raise ValueError(f"{case.case_id}: no frontier (goal mastered?)")
    return min(frontier, key=lambda c: (case.m[c], c))


def e4_key(cases: list[Case]) -> dict:
    out = {}
    for c in cases:
        root = root_cause(c)
        out[c.case_id] = {"root_cause": root, "goal": c.goal, "course": c.course,
                          "root_descendants": sorted(descendants(c.prereqs, root)),
                          "truth_m": {k: round(v, 4) for k, v in c.m.items()},
                          "truth_M": {k: int(v) for k, v in c.M.items()}}
    return out


def e6_key(meta: list[dict]) -> dict:
    """meta: one dict per presentation row, with the policy that produced it (never shown)."""
    return {r["row_id"]: {k: r[k] for k in ("profile_id", "slot", "rank", "policy", "recommended_concept")}
            for r in meta}


def write_key(data: dict, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()
