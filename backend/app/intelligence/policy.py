"""Recommendation policy v0. Deterministic. Every output carries a reason and the trace it used.

Rule (by construction, tested in E7): walk the goal's prerequisite chain in topological order and
recommend the FIRST concept that is not yet mastered. Every prerequisite of that concept is earlier
in the chain, so none of them is unmastered at that point.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .graph import Graph
from .mastery import POLICY_VERSION, ConceptState, MIN_EVIDENCE


@dataclass(frozen=True)
class Recommendation:
    action: str            # diagnostic | gather_evidence | review_prerequisite | practice_target | goal_mastered
    concept_id: str | None
    reason: str
    trace: dict = field(default_factory=dict)
    policy_version: str = POLICY_VERSION


def goal_chain(graph: Graph, goal: str) -> list[str]:
    members = graph.ancestors(goal) | {goal}
    return [n for n in graph.topo_order() if n in members]


def _name(names: Mapping[str, str] | None, cid: str) -> str:
    return (names or {}).get(cid, cid)


def recommend(graph: Graph, goal: str, states: Mapping[str, ConceptState],
              names: Mapping[str, str] | None = None) -> Recommendation:
    if goal not in graph.nodes:
        raise ValueError(f"unknown goal concept {goal}")
    chain = goal_chain(graph, goal)
    empty = ConceptState("", 0.1, 0, "insufficient")
    st = {c: states.get(c, ConceptState(c, empty.p_known, 0, "insufficient")) for c in chain}
    trace = {
        "chain": chain,
        "bands": {c: st[c].band for c in chain},
        "p_known": {c: st[c].p_known for c in chain},
        "n": {c: st[c].n for c in chain},
        "policy_version": POLICY_VERSION,
    }

    if all(st[c].n == 0 for c in chain):
        c = chain[0]
        return Recommendation(
            "diagnostic", c,
            f"No answers yet on this chain. Start with a short diagnostic on {_name(names, c)}.",
            {**trace, "rule": "cold_start"})

    for c in chain:
        band = st[c].band
        if band == "mastered":
            continue
        if band == "insufficient":
            return Recommendation(
                "gather_evidence", c,
                f"Only {st[c].n} of {MIN_EVIDENCE} answers on {_name(names, c)} so far, "
                f"so its state is not yet judged. A few more answers here come first.",
                {**trace, "rule": "insufficient_evidence_first"})
        if c == goal:
            action = "practice_target"
            reason = (f"Prerequisites are in place. Practise {_name(names, goal)} next; "
                      f"current estimate {st[c].p_known:.0%} ({band}).")
            return Recommendation(action, c, reason, {**trace, "rule": "goal_not_mastered"})
        dependent = next(d for d in chain if c in graph.prereqs(d))
        edge = graph.edge(c, dependent)
        note = ""
        if edge.review_status != "reviewed":
            note = " This prerequisite link is proposed and not yet teacher-reviewed."
        reason = (f"{_name(names, c)} is not yet mastered ({st[c].p_known:.0%}, {band}), "
                  f"and it is needed for {_name(names, dependent)}. Review it first.{note}")
        return Recommendation(
            "review_prerequisite", c, reason,
            {**trace, "rule": "first_unmastered_in_chain", "blocks": dependent,
             "edge_review_status": edge.review_status})

    return Recommendation("goal_mastered", goal,
                          f"{_name(names, goal)} is mastered on current evidence.",
                          {**trace, "rule": "all_mastered"})


def cohort_bottlenecks(graph: Graph, learners: Mapping[str, Mapping[str, ConceptState]]) -> list[dict]:
    """Teacher view: concepts that are unmastered for many learners and block downstream concepts.
    Score = learners for whom the concept is unmastered (below threshold) and at least one dependent
    is not mastered, counted per concept. A simple count, not PageRank (deferred)."""
    rows = []
    for c in graph.topo_order():
        deps = graph.dependents(c)
        if not deps:
            continue
        blocked_for = 0
        for states in learners.values():
            if states.get(c) and states[c].band in ("unmastered", "uncertain") and \
               any(states.get(d) is None or states[d].band != "mastered" for d in deps):
                blocked_for += 1
        if blocked_for:
            rows.append({"concept_id": c, "learners_blocked": blocked_for,
                         "dependents": sorted(deps), "edge_review": [graph.edge(c, d).review_status for d in sorted(deps)]})
    return sorted(rows, key=lambda r: (-r["learners_blocked"], r["concept_id"]))
