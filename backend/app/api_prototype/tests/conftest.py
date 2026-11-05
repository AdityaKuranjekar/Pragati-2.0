"""Fixtures: two institutes with a student pair and a teacher in A, one student and teacher in B.
All data is a [DEMO FIXTURE]; tokens belong to the auth stub."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from . import pg_cluster

from app.api_prototype.app import create_app
from app.api_prototype.auth import Principal, StubTokenAuth
from app.api_prototype.repository import CohortRecord, InMemoryRepository, LearnerRecord
from app.intelligence.chain import A, F, R
from app.intelligence.selection import BankItem

CONCEPTS = [A, R, F]
INST_A = "aaaaaaaa-0000-4000-8000-00000000000a"   # uuids so the same tests run on PostgreSQL
INST_B = "bbbbbbbb-0000-4000-8000-00000000000b"
TOKENS = {
    "tok-a-stu1": Principal("u-a-stu1", INST_A, "student", "a-stu1"),
    "tok-a-stu2": Principal("u-a-stu2", INST_A, "student", "a-stu2"),
    "tok-a-teacher": Principal("u-a-teacher", INST_A, "teacher"),
    "tok-a-teacher2": Principal("u-a-teacher2", INST_A, "teacher"),   # same institute, NOT assigned
    "tok-a-owner": Principal("u-a-owner", INST_A, "owner"),
    "tok-b-stu1": Principal("u-b-stu1", INST_B, "student", "b-stu1"),
    "tok-b-teacher": Principal("u-b-teacher", INST_B, "teacher"),
    "tok-b-owner": Principal("u-b-owner", INST_B, "owner"),
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


@pytest.fixture(scope="session")
def pg():
    c = pg_cluster.start()
    yield c
    if c is not None:
        c.stop()


def build(bank=None, demo=False, pg=None):
    """pg: a running pg_cluster.Cluster to use PostgreSQL, else the in-memory repository."""
    if pg is None:
        repo = InMemoryRepository()
    else:
        from app.api_prototype.pg_repository import PostgresRepository
        pg_cluster.truncate_prototype_tables(pg, [(INST_A, "A"), (INST_B, "B")])
        repo = PostgresRepository(host=pg.sock, dbname="proto_test", user=pg.superuser)
    for tok, p in TOKENS.items():
        repo.add_user(p.institute_id, p.user_id, p.role)
    for inst, coh in ((INST_A, "cohort-A"), (INST_B, "cohort-B")):
        repo.add_cohort(CohortRecord(inst, coh))
    repo.add_learner(LearnerRecord(INST_A, "a-stu1", "cohort-A", F))
    repo.add_learner(LearnerRecord(INST_A, "a-stu2", "cohort-A", F))
    repo.add_learner(LearnerRecord(INST_B, "b-stu1", "cohort-B", F))
    repo.assign_teacher(INST_A, "cohort-A", "u-a-teacher")
    repo.assign_teacher(INST_B, "cohort-B", "u-b-teacher")
    app = create_app(repo, StubTokenAuth(TOKENS), bank if bank is not None else make_bank(),
                     demo_allow_unapproved=demo)
    return repo, TestClient(app)


@pytest.fixture(params=["memory", "postgres"])
def env_factory(request, pg):
    """Every test using this runs on both repositories; the postgres run is SKIPPED (reported as
    not run, never as passed) when no throw-away cluster can start."""
    if request.param == "postgres":
        if pg is None:
            pytest.skip("no throw-away PostgreSQL available: Postgres run NOT RUN")
        return lambda bank=None, demo=False: build(bank, demo, pg=pg)
    return lambda bank=None, demo=False: build(bank, demo)


@pytest.fixture
def env(env_factory):
    return env_factory()


def hdr(token):
    return {"Authorization": f"Bearer {token}"}


def serve(repo, learner, concept, item=None, kind="practice", inst=INST_A):
    """Record an item as served (what next-step does for the learner) and return its id."""
    item = item or item_for(concept)
    repo.mark_served(inst, learner, concept, item, kind)
    return item


def attempt(event_id, concept=A, item=None, correct=True):
    return {"event_id": event_id, "concept_id": concept, "item_id": item or item_for(concept), "correct": correct}


LEVEL_ORDER = [(lvl, i) for lvl in ("easy", "medium", "hard") for i in range(4)]


def post_script(repo, c, learner, token, script, prefix="e", inst=INST_A):
    """Serve then submit each (concept, correct) with a distinct item per concept. Returns responses."""
    used, out = {}, []
    for n, (cid, ok) in enumerate(script):
        k = used[cid] = used.get(cid, -1) + 1
        lvl, i = LEVEL_ORDER[k]
        item = serve(repo, learner, cid, item_for(cid, lvl, i), inst=inst)
        r = c.post(f"/api/prototype/learners/{learner}/events", json=attempt(f"{prefix}{n}", cid, item, ok),
                   headers=hdr(token))
        assert r.status_code == 201, r.text
        out.append(r)
    return out
