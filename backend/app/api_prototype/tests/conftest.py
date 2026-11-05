"""Fixtures: two institutes with a student pair and a teacher in A, one student and teacher in B.
All data is a [DEMO FIXTURE]; tokens belong to the auth stub."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api_prototype.app import create_app
from app.api_prototype.auth import Principal, StubTokenAuth
from app.api_prototype.repository import CohortRecord, InMemoryRepository, LearnerRecord
from app.intelligence.chain import A, F, R
from app.intelligence.selection import BankItem

CONCEPTS = [A, R, F]
TOKENS = {
    "tok-a-stu1": Principal("u-a-stu1", "inst-A", "student", "a-stu1"),
    "tok-a-stu2": Principal("u-a-stu2", "inst-A", "student", "a-stu2"),
    "tok-a-teacher": Principal("u-a-teacher", "inst-A", "teacher"),
    "tok-b-stu1": Principal("u-b-stu1", "inst-B", "student", "b-stu1"),
    "tok-b-teacher": Principal("u-b-teacher", "inst-B", "teacher"),
}


def make_bank(status_by_concept=None, per_level=4):
    out = []
    for c in CONCEPTS:
        status = (status_by_concept or {}).get(c, "approved")
        for lvl in ("easy", "medium", "hard"):
            for i in range(per_level):
                out.append(BankItem(f"{c.split('.')[-1]}-{lvl}-{i}", c, lvl, status))
    return out


def item_for(concept, lvl="easy", i=0):
    return f"{concept.split('.')[-1]}-{lvl}-{i}"


def build(bank=None, demo=False):
    repo = InMemoryRepository()
    repo.add_learner(LearnerRecord("inst-A", "a-stu1", "cohort-A", F))
    repo.add_learner(LearnerRecord("inst-A", "a-stu2", "cohort-A", F))
    repo.add_learner(LearnerRecord("inst-B", "b-stu1", "cohort-B", F))
    repo.add_cohort(CohortRecord("inst-A", "cohort-A", ("a-stu1", "a-stu2")))
    repo.add_cohort(CohortRecord("inst-B", "cohort-B", ("b-stu1",)))
    app = create_app(repo, StubTokenAuth(TOKENS), bank if bank is not None else make_bank(),
                     demo_allow_unapproved=demo)
    return repo, TestClient(app)


@pytest.fixture
def env():
    return build()


def hdr(token):
    return {"Authorization": f"Bearer {token}"}


def attempt(event_id, concept=A, item=None, correct=True):
    return {"event_id": event_id, "concept_id": concept, "item_id": item or item_for(concept), "correct": correct}
