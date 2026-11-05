"""Recommendation policy v0. Deterministic. Every output carries a reason and the trace it used.

Rule (by construction, tested in E7): walk the goal's prerequisite chain in topological order and
recommend the FIRST concept that is not yet mastered. Every prerequisite of that concept is earlier
in the chain, so none of them is unmastered at that point.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .graph import Graph
from .mastery import (DEFAULT_PARAMS, MASTERED_AT, MIN_EVIDENCE, MIN_MASTERY_EVIDENCE, POLICY_VERSION,
                      BKTParams, ConceptState, bkt_update)


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


# ---------------------------------------------------------------------------------------------
# Time, goal and pace (USP row 6)
# ---------------------------------------------------------------------------------------------
SHORT_SLACK = 1.5   # policy parameter: the budget is "short" if it is under 1.5x the best-case need


def items_to_reach(p_known: float, n: int, goal_p: float = MASTERED_AT,
                   min_n: int = MIN_MASTERY_EVIDENCE, params: BKTParams = DEFAULT_PARAMS) -> int:
    """BEST-CASE number of further items to reach a 'mastered' label: every answer correct.
    A lower bound, not a forecast. Mastered needs p >= goal_p AND at least `min_n` answers."""
    k = 0
    while (p_known < goal_p or n < min_n) and k < 200:
        p_known = bkt_update(p_known, True, params)
        n += 1
        k += 1
    return k


def items_available(days_left: int, items_per_day: int) -> int:
    """Budget helper: items before the goal date from a planned study rate. Both are explicit inputs
    set by the learner or teacher. The engine never measures response time or pace from behaviour."""
    if days_left < 0 or items_per_day < 0:
        raise ValueError("days_left and items_per_day must be non-negative")
    return days_left * items_per_day


def recommend_with_budget(graph: Graph, goal: str, states: Mapping[str, ConceptState],
                          budget_items: int, names: Mapping[str, str] | None = None,
                          slack: float = SHORT_SLACK) -> Recommendation:
    """Same choice of concept as `recommend`, plus a budget check.

    budget_items: items the learner can still do before the goal date. If it is under `slack` times
    the best-case need for every unmastered concept on the goal chain, the budget is short: the trace
    carries the minimum-item plan and the reason says so. In that case optional work (revision
    rechecks) is deferred by the planner; the recommended concept is the same one `recommend` gives.
    """
    if not isinstance(budget_items, int) or isinstance(budget_items, bool) or budget_items < 0:
        raise ValueError("budget_items must be a non-negative integer")
    base = recommend(graph, goal, states, names)
    chain = goal_chain(graph, goal)
    plan = []
    for c in chain:
        st = states.get(c, ConceptState(c, DEFAULT_PARAMS.p_init, 0, "insufficient"))
        if st.band == "mastered":
            continue
        plan.append({"concept_id": c, "min_items": items_to_reach(st.p_known, st.n)})
    needed = sum(p["min_items"] for p in plan)
    short = needed > 0 and budget_items < int(-(-needed * slack // 1))
    unreachable = needed > budget_items
    budget = {"available": budget_items, "min_items_needed": needed, "plan": plan,
              "short": short, "goal_unreachable_in_budget": unreachable, "slack": slack,
              "needed_is": "best case, every answer correct"}
    if needed == 0:
        reason = base.reason + f" Budget: nothing left to practise; {budget_items} items remain."
    elif not short:
        reason = base.reason + (f" Budget: {budget_items} items remain and the chain needs at least "
                                f"{needed} even if every answer is correct, so there is room.")
    elif unreachable:
        reason = (f"Budget is short: {budget_items} items remain but the chain needs at least {needed} "
                  f"even if every answer is correct, so the goal estimate cannot be reached in time. "
                  f"Minimum-item path: {base.reason} Optional rechecks are deferred.")
    else:
        reason = (f"Budget is short: {budget_items} items remain against a best-case need of {needed}. "
                  f"Recommending the minimum-item path. {base.reason} Optional rechecks are deferred.")
    return Recommendation(base.action, base.concept_id, reason, {**base.trace, "budget": budget})
