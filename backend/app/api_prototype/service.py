"""Pure helpers over stored data (no I/O, no clock, no LLM).

The day clock. The engine's revision module needs a non-negative integer day (see its docstring: a
study-calendar day chosen by the caller). In this API the server owns it: each learner has a counter
that starts at 0 and goes up by one per accepted attempt. It is an attempt-count clock, NOT a calendar
day and NOT a time measurement: "2 days" in the revision policy means 2 attempts. Attempt number n
(seq = n) is made on day n; after it the counter reads n + 1. Persisting a day number needs its own
ADR (the engine docs say so); this is a prototype choice awaiting that decision.
"""
from __future__ import annotations

from typing import Iterable, Mapping

from app.intelligence.events import AttemptEvent
from app.intelligence.mastery import fold_concept
from app.intelligence.revision import Schedule, replay


def revision_rows(events: Iterable[AttemptEvent], kind_by_item: Mapping[str, str]) -> list[tuple[str, int, str]]:
    """Rebuild (concept, day, kind) rows for engine.revision.replay from the stored history.

    * A concept is 'mastered' on the day the counter read after the event that first made its band
      'mastered' (seq + 1), which is the day the planner would first observe it.
    * An attempt on an item that was served as a 'recheck' is a 'pass' or 'fail' on day seq.
    Deterministic: same events and serve kinds in, same rows out."""
    rows: list[tuple[str, int, str]] = []
    scheduled: set[str] = set()
    per_concept: dict[str, list[AttemptEvent]] = {}
    for ev in sorted(events, key=lambda e: e.seq):
        per_concept.setdefault(ev.concept_id, []).append(ev)
        if kind_by_item.get(ev.item_id) == "recheck" and ev.concept_id in scheduled:
            rows.append((ev.concept_id, ev.seq, "pass" if ev.correct else "fail"))
        if ev.concept_id not in scheduled and \
                fold_concept(per_concept[ev.concept_id], ev.concept_id).band == "mastered":
            scheduled.add(ev.concept_id)
            rows.append((ev.concept_id, ev.seq + 1, "mastered"))
    return rows


def schedules_for(events: Iterable[AttemptEvent], kind_by_item: Mapping[str, str]) -> dict[str, Schedule]:
    return replay(revision_rows(events, kind_by_item))
