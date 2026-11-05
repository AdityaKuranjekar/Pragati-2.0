"""Storage interface and the in-memory implementation.

Every method takes `institute_id` first and returns nothing for another institute's record: a record
is found only under (institute_id, id). A PostgreSQL implementation is NOT provided: ADR-003 is
proposed, not accepted, so the attempt_events table is not migrated. When accepted, it must set
`app.institute_id` per transaction (see contracts/schema.sql) so RLS applies as a second layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.intelligence.events import AttemptEvent


@dataclass(frozen=True)
class LearnerRecord:
    institute_id: str
    learner_id: str
    cohort_id: str | None
    goal: str


@dataclass(frozen=True)
class CohortRecord:
    institute_id: str
    cohort_id: str
    learner_ids: tuple[str, ...]


class ConflictingEvent(Exception):
    """Same event_id, different content (ADR-003 item 3)."""


class Repository(Protocol):
    def get_learner(self, institute_id: str, learner_id: str) -> LearnerRecord | None: ...
    def get_cohort(self, institute_id: str, cohort_id: str) -> CohortRecord | None: ...
    def events_for(self, institute_id: str, learner_id: str) -> list[AttemptEvent]: ...
    def append_event(self, institute_id: str, learner_id: str, event_id: str, concept_id: str,
                     item_id: str, correct: bool) -> tuple[AttemptEvent, bool]:
        """Returns (event, created). created=False for an identical repeat. Raises ConflictingEvent.
        `seq` is assigned here, by the server."""


class InMemoryRepository:
    def __init__(self) -> None:
        self._learners: dict[tuple[str, str], LearnerRecord] = {}
        self._cohorts: dict[tuple[str, str], CohortRecord] = {}
        self._events: dict[tuple[str, str], list[AttemptEvent]] = {}
        self._by_event_id: dict[tuple[str, str], AttemptEvent] = {}   # unique per tenant

    # seeding (tests and demo fixtures; there is no public route that creates learners)
    def add_learner(self, rec: LearnerRecord) -> None:
        self._learners[(rec.institute_id, rec.learner_id)] = rec

    def add_cohort(self, rec: CohortRecord) -> None:
        self._cohorts[(rec.institute_id, rec.cohort_id)] = rec

    def get_learner(self, institute_id, learner_id):
        return self._learners.get((institute_id, learner_id))

    def get_cohort(self, institute_id, cohort_id):
        return self._cohorts.get((institute_id, cohort_id))

    def events_for(self, institute_id, learner_id):
        return list(self._events.get((institute_id, learner_id), []))

    def append_event(self, institute_id, learner_id, event_id, concept_id, item_id, correct):
        prior = self._by_event_id.get((institute_id, event_id))
        if prior is not None:
            same = (prior.learner_id, prior.concept_id, prior.item_id, prior.correct) == \
                   (learner_id, concept_id, item_id, correct)
            if not same:
                raise ConflictingEvent(event_id)
            return prior, False
        log = self._events.setdefault((institute_id, learner_id), [])
        ev = AttemptEvent(event_id, learner_id, concept_id, item_id, correct, seq=len(log))
        log.append(ev)
        self._by_event_id[(institute_id, event_id)] = ev
        return ev, True
