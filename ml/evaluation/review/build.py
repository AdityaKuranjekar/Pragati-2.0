"""Builds the E4 and E6 sheets and keys [SIM]. Run from the repo root:

  python3 -m ml.evaluation.review.build

Writes (sheets, committed):  ml/evaluation/review/e4_root_cause_sheet.csv, e6_relevance_sheet.csv, manifest.json
Writes (keys, git-ignored):  ml/evaluation/review/keys/e4_key.json, e6_key.json
Only this file runs the engine (E6 adaptive policy). Sheets are written before keys, and sheets.py never reads keys.
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from app.intelligence.graph import Edge, Graph                          # noqa: E402
from app.intelligence.mastery import ConceptState                       # noqa: E402
from app.intelligence.policy import goal_chain, recommend               # noqa: E402

from ..sim.recovery_run import engine_estimates                         # noqa: E402
from . import cases as cs                                               # noqa: E402
from . import keys as ks                                                # noqa: E402
from . import sheets as sh                                              # noqa: E402

HERE = Path(__file__).resolve().parent
KEYS = HERE / "keys"
POLICIES = ("adaptive", "fixed", "random")


def top3(first: list, order, band: dict) -> list:
    """First the given concepts, then unmastered (by the estimate) in order, then anything in order. Always three."""
    out = []
    for c in first:
        if c and c not in out:
            out.append(c)
    for c in order:
        if len(out) == 3:
            break
        if c not in out and band[c] != "mastered":
            out.append(c)
    for c in order:
        if len(out) == 3:
            break
        if c not in out:
            out.append(c)
    return out[:3]


def policy_lists(case: cs.Case) -> dict:
    graph = Graph(case.concepts, [Edge(p, d, "reviewed") for d, ps in case.prereqs.items() for p in ps])
    p_known, _unc, band = engine_estimates(_bool_array(case), case.concepts)
    states = {c: ConceptState(c, float(p_known[0, j]), len(case.seq[c]), str(band[0, j]))
              for j, c in enumerate(case.concepts)}
    band_of = {c: states[c].band for c in case.concepts}
    rec = recommend(graph, case.goal, states)
    chain = list(goal_chain(graph, case.goal))
    rest = [c for c in case.concepts if c not in chain]
    rng = random.Random(f"{cs.E6_SEED}:{case.case_id}:random")
    pool = [c for c in case.concepts if band_of[c] != "mastered"]
    rand = rng.sample(pool, 3) if len(pool) >= 3 else top3(pool, case.concepts, band_of)
    return {"adaptive": top3([rec.concept_id] if rec.concept_id else [], chain + rest, band_of),
            "fixed": top3([], case.concepts, band_of),
            "random": rand}


def _bool_array(case: cs.Case):
    import numpy as np
    return np.array([[list(case.seq[c]) for c in case.concepts]], dtype=bool)


def e6_rows(cases: list) -> tuple[list, list]:
    rng = random.Random(f"{cs.E6_SEED}:presentation")
    rows, meta = [], []
    for case in cases:
        lists = policy_lists(case)
        slots = list(rng.sample(POLICIES, 3))
        ev = sh.evidence_text(case.concepts, case.correct, cs.ITEMS_PER_CONCEPT)
        gt = sh.graph_text(case.prereqs)
        for slot_name, policy in zip("ABC", slots):
            for rank, concept in enumerate(lists[policy], start=1):
                rid = f"{case.case_id}-{slot_name}-{rank}"
                rows.append({"row_id": rid, "profile_id": case.case_id, "goal_concept": case.goal,
                             "prerequisite_graph": gt, "attempts_and_correct": ev, "rank": rank,
                             "recommended_concept": concept,
                             "reason_shown": f"Listed next for this learner. Evidence on {concept}: "
                                             f"{case.correct[concept]} of {cs.ITEMS_PER_CONCEPT} correct."})
                meta.append({"row_id": rid, "profile_id": case.case_id, "slot": slot_name, "rank": rank,
                             "policy": policy, "recommended_concept": concept})
    rng.shuffle(rows)                       # presentation order carries no policy information
    return rows, meta


def main() -> int:
    e4 = cs.e4_cases()
    e6 = cs.e6_cases()
    # Sheets: visible views only, shuffled with a seed so the order carries no truth.
    e4_visible = [cs.visible_view(c) for c in e4]
    random.Random(f"{cs.E4_SEED}:order").shuffle(e4_visible)
    h4 = sh.export_e4(e4_visible, HERE / "e4_root_cause_sheet.csv")
    e6_pres, e6_meta = e6_rows(e6)
    h6 = sh.export_e6(e6_pres, HERE / "e6_relevance_sheet.csv")
    sheet_hashes = {n: hashlib.sha256((HERE / n).read_bytes()).hexdigest()
                    for n in ("e4_root_cause_sheet.csv", "e6_relevance_sheet.csv")}
    # Keys: written after the sheets, from truth and policy labels.
    k4 = ks.write_key(ks.e4_key(e4), KEYS / "e4_key.json")
    k6 = ks.write_key(ks.e6_key(e6_meta), KEYS / "e6_key.json")
    manifest = {
        "label": "[SIM]", "purpose": "E4 root-cause and E6 relevance review material; no rating or expert label is recorded",
        "e4": {"seed": cs.E4_SEED, "cases": h4, "items_per_concept": cs.ITEMS_PER_CONCEPT,
               "courses": {"D1": sum(c.course == "D1" for c in e4), "D3": sum(c.course == "D3" for c in e4)}},
        "e6": {"seed": cs.E6_SEED, "profiles": len(e6), "rows": h6, "policies": list(POLICIES),
               "slots_per_profile": 3, "ranks_per_slot": 3},
        "sheet_sha256": sheet_hashes,
        "key_files_gitignored": {"keys/e4_key.json_sha256": k4, "keys/e6_key.json_sha256": k6},
    }
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"E4 sheet rows: {h4}; E6 sheet rows: {h6} for {len(e6)} profiles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
