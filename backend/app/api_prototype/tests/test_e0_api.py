"""E0 for the API: idempotency, conflicts, rejected fields, determinism."""
import pytest

from .conftest import A, F, R, attempt, build, hdr, item_for

URL = "/api/prototype/learners/a-stu1/events"
T = hdr("tok-a-stu1")


def test_new_event_is_created_with_server_seq(env):
    _, c = env
    r = c.post(URL, json=attempt("e1"), headers=T)
    assert r.status_code == 201 and r.json()["seq"] == 0 and r.json()["duplicate"] is False
    assert c.post(URL, json=attempt("e2"), headers=T).json()["seq"] == 1


def test_identical_duplicate_returns_same_state_and_stores_one_event(env):
    repo, c = env
    first = c.post(URL, json=attempt("e1", correct=False), headers=T)
    state_before = c.get("/api/prototype/learners/a-stu1/state", headers=T).json()
    again = c.post(URL, json=attempt("e1", correct=False), headers=T)
    assert again.status_code == 200 and again.json()["duplicate"] is True
    assert again.json()["seq"] == first.json()["seq"]
    assert again.json()["concepts"] == first.json()["concepts"]
    assert c.get("/api/prototype/learners/a-stu1/state", headers=T).json() == state_before
    assert len(repo.events_for("inst-A", "a-stu1")) == 1


@pytest.mark.parametrize("changed", [{"correct": False}, {"item_id": item_for(A, "easy", 1)},
                                     {"concept_id": R, "item_id": item_for(R)}])
def test_conflicting_duplicate_event_id_is_rejected_and_state_unchanged(env, changed):
    repo, c = env
    c.post(URL, json=attempt("e1"), headers=T)
    before = c.get("/api/prototype/learners/a-stu1/state", headers=T).json()
    r = c.post(URL, json={**attempt("e1"), **changed}, headers=T)
    assert r.status_code == 409
    assert c.get("/api/prototype/learners/a-stu1/state", headers=T).json() == before
    assert len(repo.events_for("inst-A", "a-stu1")) == 1


def test_event_id_is_unique_per_tenant_not_global(env):
    repo, c = env
    assert c.post(URL, json=attempt("shared-id"), headers=T).status_code == 201
    # the same id in another institute is independent: no conflict, and no signal that it exists in A
    r = c.post("/api/prototype/learners/b-stu1/events", json=attempt("shared-id", correct=False),
               headers=hdr("tok-b-stu1"))
    assert r.status_code == 201
    assert len(repo.events_for("inst-B", "b-stu1")) == 1 and len(repo.events_for("inst-A", "a-stu1")) == 1


def test_same_event_id_for_another_learner_in_same_institute_is_a_conflict(env):
    _, c = env
    c.post(URL, json=attempt("e1"), headers=T)
    r = c.post("/api/prototype/learners/a-stu2/events", json=attempt("e1"), headers=hdr("tok-a-stu2"))
    assert r.status_code == 409


@pytest.mark.parametrize("field,value", [
    ("response_time_ms", 1200), ("response_time", 3.2), ("time_spent", 10), ("hints_used", 1),
    ("hint_count", 0), ("hint", "x"), ("seq", 5), ("learner_id", "a-stu2"), ("institute_id", "inst-A"),
    ("client_time", "2026-11-05T10:00:00Z"), ("anything_else", 1)])
def test_field_outside_adr003_is_refused_with_422_and_nothing_is_stored(env, field, value):
    repo, c = env
    r = c.post(URL, json={**attempt("e1"), field: value}, headers=T)
    assert r.status_code == 422
    assert repo.events_for("inst-A", "a-stu1") == []


@pytest.mark.parametrize("bad", [
    {"correct": "true"}, {"correct": 1}, {"event_id": ""}, {"event_id": "   "}, {"concept_id": 3},
    {"concept_id": "jee.unknown.concept"}, {"item_id": "no-such-item"},
    {"concept_id": R, "item_id": item_for(A)}])   # item belongs to another concept
def test_malformed_or_unknown_values_are_422(env, bad):
    repo, c = env
    assert c.post(URL, json={**attempt("e1"), **bad}, headers=T).status_code == 422
    assert repo.events_for("inst-A", "a-stu1") == []


def test_missing_field_is_422(env):
    _, c = env
    body = attempt("e1")
    del body["correct"]
    assert c.post(URL, json=body, headers=T).status_code == 422


def test_unknown_learner_is_404_for_a_teacher_route_target(env):
    _, c = env
    assert c.get("/api/prototype/learners/nobody/state", headers=hdr("tok-a-teacher")).status_code == 404


def test_replay_gives_identical_state_in_two_stores():
    script = [(A, True)] * 5 + [(R, False)] * 3
    states = []
    for _ in range(2):
        _, c = build()
        for i, (cid, ok) in enumerate(script):
            assert c.post(URL, json=attempt(f"e{i}", cid, correct=ok), headers=T).status_code == 201
        states.append(c.get("/api/prototype/learners/a-stu1/state", headers=T).json())
    assert states[0] == states[1]
    by = {s["concept_id"]: s for s in states[0]["concepts"]}
    assert by[A]["evidence_count"] == 5 and by[A]["band"] == "mastered"
    assert by[R]["band"] == "unmastered" and by[F]["band"] == "insufficient"
    assert 0 < by[R]["uncertainty"] < 1


def test_state_on_cold_start_has_all_concepts_with_zero_evidence(env):
    _, c = env
    s = c.get("/api/prototype/learners/a-stu1/state", headers=T).json()
    assert [x["evidence_count"] for x in s["concepts"]] == [0, 0, 0]
    assert {x["band"] for x in s["concepts"]} == {"insufficient"}
