"""PostgreSQL repository. Every call runs in one transaction that first does

    SET LOCAL ROLE app_user            -- the role the RLS policies are written for (NOBYPASSRLS)
    set_config('app.institute_id', <id>, true)   -- transaction-local, as contracts/schema.sql expects

so row-level security is a second layer under the (institute_id, id) lookups. The connecting role must
be a member of app_user (a superuser is, but bypasses RLS until it switches role, which is why the
switch is explicit). An institute id that is not a uuid matches nothing.

Do not point this at a shared or production database until ADR-003 is accepted.
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager

import psycopg2

from app.intelligence.events import AttemptEvent

from .repository import (SERVE_KINDS, CohortRecord, ConflictingEvent, LearnerRecord, NotServed,
                         ServedRecord)


def _uuid(value: str) -> str | None:
    try:
        return str(uuid.UUID(str(value)))
    except ValueError:
        return None


class PostgresRepository:
    def __init__(self, dsn: str | None = None, **connect_kwargs):
        self._dsn, self._kw = dsn, connect_kwargs

    @contextmanager
    def tx(self, institute_id: str):
        """A cursor inside a transaction scoped to one institute. Commits on success."""
        tid = _uuid(institute_id)
        if tid is None:
            raise LookupError("institute id is not a uuid")
        conn = psycopg2.connect(self._dsn, **self._kw) if self._dsn else psycopg2.connect(**self._kw)
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SET LOCAL ROLE app_user")
                cur.execute("SELECT set_config('app.institute_id', %s, true)", (tid,))
                yield cur
        finally:
            conn.close()

    def _read(self, institute_id, sql, args, default):
        try:
            with self.tx(institute_id) as cur:
                cur.execute(sql, args)
                return cur.fetchall()
        except LookupError:
            return default

    # reads
    def get_user_role(self, institute_id, user_id):
        rows = self._read(institute_id, "SELECT role FROM proto_users WHERE institute_id=%s AND user_id=%s",
                          (_uuid(institute_id), user_id), [])
        return rows[0][0] if rows else None

    def get_learner(self, institute_id, learner_id):
        rows = self._read(institute_id, "SELECT cohort_id, goal FROM proto_learners "
                          "WHERE institute_id=%s AND learner_id=%s", (_uuid(institute_id), learner_id), [])
        return LearnerRecord(institute_id, learner_id, rows[0][0], rows[0][1]) if rows else None

    def get_cohort(self, institute_id, cohort_id):
        rows = self._read(institute_id, "SELECT cohort_id FROM proto_cohorts WHERE institute_id=%s AND cohort_id=%s",
                          (_uuid(institute_id), cohort_id), [])
        return CohortRecord(institute_id, cohort_id) if rows else None

    def cohort_learner_ids(self, institute_id, cohort_id):
        rows = self._read(institute_id, "SELECT learner_id FROM proto_learners WHERE institute_id=%s "
                          "AND cohort_id=%s ORDER BY learner_id", (_uuid(institute_id), cohort_id), [])
        return [r[0] for r in rows]

    def is_teacher_assigned(self, institute_id, cohort_id, user_id):
        rows = self._read(institute_id, "SELECT 1 FROM proto_cohort_teachers WHERE institute_id=%s "
                          "AND cohort_id=%s AND user_id=%s", (_uuid(institute_id), cohort_id, user_id), [])
        return bool(rows)

    def events_for(self, institute_id, learner_id):
        rows = self._read(institute_id, "SELECT event_id, concept_id, item_id, correct, seq FROM attempt_events "
                          "WHERE institute_id=%s AND learner_id=%s ORDER BY seq",
                          (_uuid(institute_id), learner_id), [])
        return [AttemptEvent(e, learner_id, c, i, ok, s) for e, c, i, ok, s in rows]

    def served_for(self, institute_id, learner_id):
        rows = self._read(institute_id, "SELECT concept_id, item_id, kind, answered_event_id FROM proto_served_items "
                          "WHERE institute_id=%s AND learner_id=%s ORDER BY item_id",
                          (_uuid(institute_id), learner_id), [])
        return [ServedRecord(*r) for r in rows]

    def day_of(self, institute_id, learner_id):
        rows = self._read(institute_id, "SELECT day_counter FROM proto_learners WHERE institute_id=%s AND learner_id=%s",
                          (_uuid(institute_id), learner_id), [])
        return rows[0][0] if rows else 0

    # writes
    def assign_teacher(self, institute_id, cohort_id, user_id):
        with self.tx(institute_id) as cur:
            cur.execute("INSERT INTO proto_cohort_teachers (institute_id, cohort_id, user_id) VALUES (%s,%s,%s) "
                        "ON CONFLICT DO NOTHING", (_uuid(institute_id), cohort_id, user_id))
            return cur.rowcount == 1

    def mark_served(self, institute_id, learner_id, concept_id, item_id, kind):
        if kind not in SERVE_KINDS:
            raise ValueError(f"unknown serve kind {kind}")
        with self.tx(institute_id) as cur:
            cur.execute(
                "INSERT INTO proto_served_items (institute_id, learner_id, item_id, concept_id, kind) "
                "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (institute_id, learner_id, item_id) DO UPDATE "
                "SET kind = EXCLUDED.kind WHERE proto_served_items.answered_event_id IS NULL "
                "AND proto_served_items.concept_id = EXCLUDED.concept_id",
                (_uuid(institute_id), learner_id, item_id, concept_id, kind))

    def append_event(self, institute_id, learner_id, event_id, concept_id, item_id, correct):
        tid = _uuid(institute_id)
        with self.tx(institute_id) as cur:
            # Row lock on the learner serialises seq assignment and the day counter.
            cur.execute("SELECT day_counter FROM proto_learners WHERE institute_id=%s AND learner_id=%s "
                        "FOR UPDATE", (tid, learner_id))
            if cur.fetchone() is None:
                raise LookupError("learner not found")
            cur.execute("SELECT learner_id, concept_id, item_id, correct, seq FROM attempt_events "
                        "WHERE institute_id=%s AND event_id=%s", (tid, event_id))
            prior = cur.fetchone()
            if prior is not None:
                if tuple(prior[:4]) != (learner_id, concept_id, item_id, correct):
                    raise ConflictingEvent(event_id)
                return AttemptEvent(event_id, learner_id, concept_id, item_id, correct, prior[4]), False
            cur.execute("SELECT concept_id, answered_event_id FROM proto_served_items "
                        "WHERE institute_id=%s AND learner_id=%s AND item_id=%s", (tid, learner_id, item_id))
            served = cur.fetchone()
            if served is None or served[0] != concept_id:
                raise NotServed("this item was not served to this learner for this concept")
            if served[1] is not None:
                raise NotServed("this item has already been answered")
            cur.execute("SELECT COALESCE(MAX(seq) + 1, 0) FROM attempt_events WHERE institute_id=%s AND learner_id=%s",
                        (tid, learner_id))
            seq = cur.fetchone()[0]
            cur.execute("INSERT INTO attempt_events (institute_id, event_id, learner_id, concept_id, item_id, correct, seq) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s)", (tid, event_id, learner_id, concept_id, item_id, correct, seq))
            cur.execute("UPDATE proto_served_items SET answered_event_id=%s WHERE institute_id=%s "
                        "AND learner_id=%s AND item_id=%s", (event_id, tid, learner_id, item_id))
            cur.execute("UPDATE proto_learners SET day_counter = day_counter + 1 WHERE institute_id=%s AND learner_id=%s",
                        (tid, learner_id))
            return AttemptEvent(event_id, learner_id, concept_id, item_id, correct, seq), True

    # seeding
    def add_user(self, institute_id, user_id, role):
        with self.tx(institute_id) as cur:
            cur.execute("INSERT INTO proto_users VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                        (_uuid(institute_id), user_id, role))

    def add_cohort(self, rec):
        with self.tx(rec.institute_id) as cur:
            cur.execute("INSERT INTO proto_cohorts VALUES (%s,%s) ON CONFLICT DO NOTHING",
                        (_uuid(rec.institute_id), rec.cohort_id))

    def add_learner(self, rec):
        with self.tx(rec.institute_id) as cur:
            cur.execute("INSERT INTO proto_learners (institute_id, learner_id, cohort_id, goal) VALUES (%s,%s,%s,%s) "
                        "ON CONFLICT DO NOTHING", (_uuid(rec.institute_id), rec.learner_id, rec.cohort_id, rec.goal))
