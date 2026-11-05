"""Concept state as a fixed-parameter Bayesian Knowledge Tracing fold (v0).

Parameters are fixed, documented defaults, NOT fitted. They are a baseline to be replaced only after
E1 shows a fitted model beats them on held-out learners. The 'uncertainty' value is a simple
heuristic (1 / sqrt(n + 1)), not a calibrated interval; the UI must say so.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .events import AttemptEvent

POLICY_VERSION = "policy-v0.1"


@dataclass(frozen=True)
class BKTParams:
    p_init: float = 0.10     # P(L0)
    p_transit: float = 0.20  # P(T) learning per opportunity
    p_guess: float = 0.25    # 4-option MCQ chance rate
    p_slip: float = 0.10


DEFAULT_PARAMS = BKTParams()
MIN_EVIDENCE = 3           # below this, no band is shown
MIN_MASTERY_EVIDENCE = 5   # 'mastered' needs this many answers: guards against a lucky run of guesses
MASTERED_AT = 0.85
UNMASTERED_BELOW = 0.50


@dataclass(frozen=True)
class ConceptState:
    concept_id: str
    p_known: float
    n: int
    band: str              # insufficient | mastered | uncertain | unmastered

    @property
    def uncertainty(self) -> float:
        return 1.0 / (self.n + 1) ** 0.5


def bkt_update(p: float, correct: bool, params: BKTParams = DEFAULT_PARAMS) -> float:
    g, s = params.p_guess, params.p_slip
    if correct:
        post = p * (1 - s) / (p * (1 - s) + (1 - p) * g)
    else:
        post = p * s / (p * s + (1 - p) * (1 - g))
    return post + (1 - post) * params.p_transit


def band_for(p: float, n: int) -> str:
    if n < MIN_EVIDENCE:
        return "insufficient"
    if p >= MASTERED_AT and n >= MIN_MASTERY_EVIDENCE:
        return "mastered"
    if p < UNMASTERED_BELOW:
        return "unmastered"
    return "uncertain"


def fold_concept(events: Iterable[AttemptEvent], concept_id: str,
                 params: BKTParams = DEFAULT_PARAMS) -> ConceptState:
    """Replay one concept's events in seq order. Duplicate event_ids are ignored if identical;
    a conflicting duplicate raises (ADR-003 idempotency)."""
    seen: dict[str, AttemptEvent] = {}
    mine = []
    for ev in events:
        if ev.concept_id != concept_id:
            continue
        prior = seen.get(ev.event_id)
        if prior is not None:
            if prior != ev:
                raise ValueError(f"conflicting duplicate event_id {ev.event_id}")
            continue
        seen[ev.event_id] = ev
        mine.append(ev)
    seqs = [e.seq for e in mine]
    if len(seqs) != len(set(seqs)):
        raise ValueError("duplicate seq for one learner and concept")
    p = params.p_init
    for ev in sorted(mine, key=lambda e: e.seq):
        p = bkt_update(p, ev.correct, params)
    n = len(mine)
    return ConceptState(concept_id, round(p, 4), n, band_for(p, n))


def learner_state(events: Iterable[AttemptEvent], concepts: Iterable[str],
                  params: BKTParams = DEFAULT_PARAMS) -> dict[str, ConceptState]:
    events = list(events)
    return {c: fold_concept(events, c, params) for c in concepts}
