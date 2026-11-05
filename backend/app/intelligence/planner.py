"""Planner: composes concept choice, item selection, challenge ladder, revision and budget.

An in-memory session for one learner and one goal. No database, no LLM, no clock, no timing data.
Day number and remaining budget are explicit inputs. The flags in PlannerConfig exist so that each
component can be switched off for the ablation runs in ml/evaluation/sim; production uses the defaults.

Step kinds:
  recheck   a due revision item on a mastered concept
  practice  an item on the concept the policy picked
  none      nothing to do now (goal mastered by estimate and no recheck due, or no item available)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from .events import AttemptEvent
from .graph import Graph
from .mastery import ConceptState, learner_state
from .policy import Recommendation, recommend_with_budget
from .revision import DEFAULT_POLICY, RevisionPolicy, Schedule, apply_lapses, due, on_recheck, refresh
from .selection import BankItem, Selection, select_item


@dataclass(frozen=True)
class PlannerConfig:
    target: str = "medium"
    use_graph: bool = True          # False: pick the unmastered concept with the lowest estimate
    use_challenge: bool = True      # False: the band stays at the guided-entry level, no raise or lower
    use_revision: bool = True
    use_budget: bool = True
    allow_unapproved_demo: bool = False
    revision: RevisionPolicy = DEFAULT_POLICY


@dataclass(frozen=True)
class Step:
    kind: str
    concept_id: str | None
    item_id: str | None
    reason: str
    selection: Selection | None = None
    recommendation: Recommendation | None = None
    trace: dict = field(default_factory=dict)


class AdaptiveSession:
    def __init__(self, learner_id: str, graph: Graph, goal: str, bank: Sequence[BankItem],
                 config: PlannerConfig = PlannerConfig(), names: Mapping[str, str] | None = None):
        if goal not in graph.nodes:
            raise ValueError(f"unknown goal {goal}")
        self.learner_id, self.graph, self.goal = learner_id, graph, goal
        self.bank, self.config, self.names = list(bank), config, names
        self.events: list[AttemptEvent] = []
        self.schedules: dict[str, Schedule] = {}
        self._entry_p: dict[str, float] = {}

    # -- reads -------------------------------------------------------------------------------
    def states(self) -> dict[str, ConceptState]:
        return learner_state(self.events, self.graph.nodes)

    def _history(self, concept_id: str) -> list[tuple[str, bool]]:
        return [(e.item_id, e.correct) for e in self.events if e.concept_id == concept_id]

    def _select(self, concept_id: str, st: ConceptState) -> Selection:
        hist = self._history(concept_id)
        entry = self._entry_p.setdefault(concept_id, st.p_known)
        # use_challenge=False pins the ladder to its entry band: k above any reachable run.
        k, m = (3, 2) if self.config.use_challenge else (10**9, 10**9)
        return select_item(self.bank, concept_id, st.p_known, hist, self.config.target,
                           entry_p_known=entry, allow_unapproved_demo=self.config.allow_unapproved_demo,
                           k=k, m=m)

    # -- decision ----------------------------------------------------------------------------
    def next_step(self, day: int, budget_remaining: int) -> Step:
        cfg = self.config
        states = self.states()
        if cfg.use_revision:
            self.schedules = refresh(self.schedules, states, day, cfg.revision)
            states = apply_lapses(states, self.schedules)

        if cfg.use_graph:
            rec = recommend_with_budget(self.graph, self.goal, states, budget_remaining, self.names)
            short = bool(rec.trace["budget"]["short"]) and cfg.use_budget
            concept = None if rec.action == "goal_mastered" else rec.concept_id
        else:
            rec = None
            open_ = [c for c in self.graph.nodes if states[c].band != "mastered"]
            concept = min(open_, key=lambda c: (states[c].p_known, c)) if open_ else None
            short = False

        if cfg.use_revision and not short:
            ready = due(self.schedules, day)
            if ready:
                s = ready[0]
                sel = self._select(s.concept_id, states[s.concept_id])
                if sel.item_id is not None:
                    why = (f"Recheck of {s.concept_id}: it was judged mastered earlier and the recheck "
                           f"was due on day {s.due_day} (interval {s.interval} days, "
                           f"{s.successes} correct rechecks so far).")
                    return Step("recheck", s.concept_id, sel.item_id, why + " " + sel.reason, sel, rec,
                                {"due_day": s.due_day, "interval": s.interval, "day": day})

        if concept is None:
            return Step("none", None, None, "Goal mastered on current evidence; no recheck is due.",
                        None, rec, {"day": day})
        sel = self._select(concept, states[concept])
        if sel.item_id is None:
            return Step("none", concept, None, sel.reason, sel, rec, {"day": day})
        why = (rec.reason + " " if rec is not None else
               f"Lowest estimate among unmastered concepts: {concept} ({states[concept].p_known:.0%}). ")
        return Step("practice", concept, sel.item_id, why + sel.reason, sel, rec,
                    {"day": day, "budget_short": short})

    # -- write -------------------------------------------------------------------------------
    def record(self, step: Step, correct: bool, day: int) -> AttemptEvent:
        if step.item_id is None or step.concept_id is None:
            raise ValueError("cannot record an answer for a step without an item")
        seq = len(self.events)
        ev = AttemptEvent(f"{self.learner_id}-{seq}", self.learner_id, step.concept_id,
                          step.item_id, bool(correct), seq)
        self.events.append(ev)
        if step.kind == "recheck" and self.config.use_revision:
            self.schedules[step.concept_id] = on_recheck(self.schedules[step.concept_id], day,
                                                         bool(correct), self.config.revision)
        return ev
