"""Storage interface and the in-memory implementation.

Every method takes `institute_id` first and returns nothing for another institute's record: a record
is found only under (institute_id, id). The PostgreSQL implementation is in pg_repository.py and adds
row-level security as a second layer (migrations/001_prototype_tables.sql).

ADR-003 is still PROPOSED. The SQL migration is written but must not be applied to any shared or
production database until the owner accepts the ADR.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.intelligence.events import AttemptEvent

SERVE_KINDS = frozenset({"practice", "recheck"})


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


@dataclass(frozen=True)
class ServedRecord:
    concept_id: str
    item_id: str
    kind: str                       # practice | recheck (the planner's step kind when it was served)
    answered_event_id: str | None   # None until an accepted attempt consumes it


class ConflictingEvent(Exception):
    """Same event_id, different content (ADR-003 item 3)."""


class NotServed(Exception):
    """The item was not served to this learner for this concept, or was already answered."""


class Repository(Protocol):
    # reads
    def get_user_role(self, institute_id: str, user_id: str) -> str | None: ...
    def get_learner(self, institute_id: str, learner_id: str) -> LearnerRecord | None: ...
    def get_cohort(self, institute_id: str, cohort_id: str) -> CohortRecord | None: ...
    def cohort_learner_ids(self, institute_id: str, cohort_id: str) -> list[str]: ...
    def is_teacher_assigned(self, institute_id: str, cohort_id: str, user_id: str) -> bool: ...
    def events_for(self, institute_id: str, learner_id: str) -> list[AttemptEvent]: ...
    def served_for(self, institute_id: str, learner_id: str) -> list[ServedRecord]: ...
    def day_of(self, institute_id: str, learner_id: str) -> int: ...
    # writes
    def assign_teacher(self, institute_id: str, cohort_id: str, user_id: str) -> bool:
        """True if newly assigned, False if already assigned."""
    def mark_served(self, institute_id: str, learner_id: str, concept_id: str, item_id: str,
                    kind: str) -> None:
        """Idempotent. An already-answered item is left alone."""
    def append_event(self, institute_id: str, learner_id: str, event_id: str, concept_id: str,
                     item_id: str, correct: bool) -> tuple[AttemptEvent, bool]:
        """Returns (event, created). created=False for an identical repeat (checked first).
        Raises ConflictingEvent, or NotServed when the item was not served / already answered.
        `seq` is assigned here, by the server, and the learner's day counter is incremented in the
        same step, once per accepted attempt."""
    # seeding (tests and demo fixtures; no public route creates users, cohorts or learners)
    def add_user(self, institute_id: str, user_id: str, role: str) -> None: ...
    def add_cohort(self, rec: CohortRecord) -> None: ...
    def add_learner(self, rec: LearnerRecord) -> None: ...


class InMemoryRepository:
    def __init__(self) -> None:
        self._users: dict[tuple[str, str], str] = {}
        self._learners: dict[tuple[str, str], LearnerRecord] = {}
        self._cohorts: dict[tuple[str, str], CohortRecord] = {}
        self._assigned: set[tuple[str, str, str]] = set()
        self._events: dict[tuple[str, str], list[AttemptEvent]] = {}
        self._by_event_id: dict[tuple[str, str], AttemptEvent] = {}   # unique per tenant
        self._served: dict[tuple[str, str], dict[str, ServedRecord]] = {}
        self._day: dict[tuple[str, str], int] = {}

    # seeding
    def add_user(self, institute_id, user_id, role):
        self._users[(institute_id, user_id)] = role

    def add_cohort(self, rec):
        self._cohorts[(rec.institute_id, rec.cohort_id)] = rec

    def add_learner(self, rec):
        self._learners[(rec.institute_id, rec.learner_id)] = rec

    # reads
    def get_user_role(self, institute_id, user_id):
        return self._users.get((institute_id, user_id))

    def get_learner(self, institute_id, learner_id):
        return self._learners.get((institute_id, learner_id))

    def get_cohort(self, institute_id, cohort_id):
        return self._cohorts.get((institute_id, cohort_id))

    def cohort_learner_ids(self, institute_id, cohort_id):
        return sorted(l.learner_id for (i, _), l in self._learners.items()
                      if i == institute_id and l.cohort_id == cohort_id)

    def is_teacher_assigned(self, institute_id, cohort_id, user_id):
        return (institute_id, cohort_id, user_id) in self._assigned

    def events_for(self, institute_id, learner_id):
        return list(self._events.get((institute_id, learner_id), []))

    def served_for(self, institute_id, learner_id):
        return list(self._served.get((institute_id, learner_id), {}).values())

    def day_of(self, institute_id, learner_id):
        return self._day.get((institute_id, learner_id), 0)

    # writes
    def assign_teacher(self, institute_id, cohort_id, user_id):
        key = (institute_id, cohort_id, user_id)
        new = key not in self._assigned
        self._assigned.add(key)
        return new

    def mark_served(self, institute_id, learner_id, concept_id, item_id, kind):
        if kind not in SERVE_KINDS:
            raise ValueError(f"unknown serve kind {kind}")
        row = self._served.setdefault((institute_id, learner_id), {})
        prior = row.get(item_id)
        if prior is None or (prior.answered_event_id is None and prior.concept_id == concept_id):
            row[item_id] = ServedRecord(concept_id, item_id, kind, None)

    def append_event(self, institute_id, learner_id, event_id, concept_id, item_id, correct):
        prior = self._by_event_id.get((institute_id, event_id))
        if prior is not None:
            same = (prior.learner_id, prior.concept_id, prior.item_id, prior.correct) == \
                   (learner_id, concept_id, item_id, correct)
            if not same:
                raise ConflictingEvent(event_id)
            return prior, False
        served = self._served.get((institute_id, learner_id), {}).get(item_id)
        if served is None or served.concept_id != concept_id:
            raise NotServed("this item was not served to this learner for this concept")
        if served.answered_event_id is not None:
            raise NotServed("this item has already been answered")
        log = self._events.setdefault((institute_id, learner_id), [])
        ev = AttemptEvent(event_id, learner_id, concept_id, item_id, correct, seq=len(log))
        log.append(ev)
        self._by_event_id[(institute_id, event_id)] = ev
        self._served[(institute_id, learner_id)][item_id] = ServedRecord(
            served.concept_id, served.item_id, served.kind, event_id)
        self._day[(institute_id, learner_id)] = self.day_of(institute_id, learner_id) + 1
        return ev, True
