"""Revision scheduling (USP row 5). Pure Python, deterministic, no wall-clock.

Time is an explicit input: a non-negative integer day number supplied by the caller. The module never
reads a clock, so replaying the same inputs gives the same schedule.

Policy (configurable, NOT a claim about forgetting curves):
  * When a concept is first judged mastered on day d, schedule a recheck at d + base_interval.
  * A correct recheck multiplies the interval by `growth` (capped at `max_interval`) and schedules the
    next recheck that far ahead.
  * A wrong recheck marks the concept `lapsed`, multiplies the interval by `error_factor` (floored at
    `min_interval`) and schedules the next recheck sooner. A lapsed concept is treated as not
    mastered by the planner until a later recheck is answered correctly.
  * Intervals are whole days.

The defaults (2 days, x2, cap 30, x0.5 after an error, floor 1) are a conventional expanding-interval
shape chosen for being simple and explainable. They are not fitted to any data and are not evidence of
how JEE aspirants forget. Calibrate only against retention data from a pilot.

The `day` values here are study-calendar days chosen by the caller. They are not response times and are
not part of the attempt event (ADR-003 stays unchanged); persisting a day number needs its own ADR.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Mapping

from .mastery import ConceptState


@dataclass(frozen=True)
class RevisionPolicy:
    base_interval: int = 2
    growth: float = 2.0
    max_interval: int = 30
    error_factor: float = 0.5
    min_interval: int = 1

    def __post_init__(self):
        if self.min_interval < 1 or self.base_interval < self.min_interval:
            raise ValueError("need 1 <= min_interval <= base_interval")
        if self.max_interval < self.base_interval:
            raise ValueError("max_interval must be >= base_interval")
        if self.growth <= 1.0:
            raise ValueError("growth must be > 1 so intervals grow with success")
        if not 0.0 < self.error_factor < 1.0:
            raise ValueError("error_factor must be in (0, 1) so intervals shorten after an error")


DEFAULT_POLICY = RevisionPolicy()


@dataclass(frozen=True)
class Schedule:
    concept_id: str
    interval: int          # days until the next recheck, from the last event
    due_day: int
    last_day: int
    successes: int         # correct rechecks in a row
    lapses: int            # wrong rechecks, ever
    lapsed: bool           # last recheck was wrong and no correct recheck has followed


def _check_day(day: int) -> None:
    if not isinstance(day, int) or isinstance(day, bool) or day < 0:
        raise ValueError("day must be a non-negative integer day number")


def on_mastered(concept_id: str, day: int, policy: RevisionPolicy = DEFAULT_POLICY) -> Schedule:
    _check_day(day)
    return Schedule(concept_id, policy.base_interval, day + policy.base_interval, day, 0, 0, False)


def on_recheck(s: Schedule, day: int, correct: bool, policy: RevisionPolicy = DEFAULT_POLICY) -> Schedule:
    _check_day(day)
    if day < s.last_day:
        raise ValueError("recheck day is before the last event for this concept")
    if correct:
        # Grows from the current interval; after a lapse that is the shortened interval.
        interval = min(policy.max_interval, max(policy.min_interval, int(round(s.interval * policy.growth))))
        return replace(s, interval=interval, due_day=day + interval, last_day=day,
                       successes=s.successes + 1, lapsed=False)
    interval = max(policy.min_interval, int(s.interval * policy.error_factor))
    return replace(s, interval=interval, due_day=day + interval, last_day=day,
                   successes=0, lapses=s.lapses + 1, lapsed=True)


def refresh(schedules: Mapping[str, Schedule], states: Mapping[str, ConceptState], day: int,
            policy: RevisionPolicy = DEFAULT_POLICY) -> dict[str, Schedule]:
    """Create a schedule for every concept newly judged mastered. Existing schedules are untouched."""
    _check_day(day)
    out = dict(schedules)
    for cid in sorted(states):
        if states[cid].band == "mastered" and cid not in out:
            out[cid] = on_mastered(cid, day, policy)
    return out


def due(schedules: Mapping[str, Schedule], day: int) -> list[Schedule]:
    """Schedules due on or before `day`, most overdue first, ties by concept id."""
    _check_day(day)
    rows = [s for s in schedules.values() if s.due_day <= day]
    return sorted(rows, key=lambda s: (s.due_day, s.concept_id))


def apply_lapses(states: Mapping[str, ConceptState], schedules: Mapping[str, Schedule]) -> dict[str, ConceptState]:
    """A lapsed concept is not treated as mastered. Its estimate and count are kept; only the band
    changes to 'uncertain' so the policy practises it again."""
    out = dict(states)
    for cid, s in schedules.items():
        st = out.get(cid)
        if s.lapsed and st is not None and st.band == "mastered":
            out[cid] = ConceptState(st.concept_id, st.p_known, st.n, "uncertain")
    return out


def replay(events: Iterable[tuple[str, int, str]], policy: RevisionPolicy = DEFAULT_POLICY) -> dict[str, Schedule]:
    """Fold rows of (concept_id, day, kind) in the order given; kind is 'mastered', 'pass' or 'fail'.
    Same rows in, same schedules out."""
    out: dict[str, Schedule] = {}
    for concept_id, day, kind in events:
        if kind == "mastered":
            if concept_id not in out:
                out[concept_id] = on_mastered(concept_id, day, policy)
        elif kind in ("pass", "fail"):
            if concept_id not in out:
                raise ValueError(f"recheck for {concept_id} before it was mastered")
            out[concept_id] = on_recheck(out[concept_id], day, kind == "pass", policy)
        else:
            raise ValueError(f"unknown revision row kind {kind!r}")
    return out
