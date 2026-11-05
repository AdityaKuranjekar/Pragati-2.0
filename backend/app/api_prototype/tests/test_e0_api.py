"""E0 for the API: idempotency, conflicts, rejected fields, determinism, served-item check, day clock.
Runs on both repositories."""
import pytest

from .conftest import A, F, INST_A, INST_B, R, attempt, hdr, item_for, post_script, serve

URL = "/api/prototype/learners/a-stu1/events"
T = hdr("tok-a-stu1")


def test_new_event_is_created_with_server_seq(env):
    repo, c = env
    serve(repo, "a-stu1", A, item_for(A, "easy", 0)); serve(repo, "a-stu1", A, item_for(A, "easy", 1))
    r = c.post(URL, json=attempt("e1", item=item_for(A, "easy", 0)), headers=T)
    assert r.status_code == 201 and r.json()["seq"] == 0 and r.json()["duplicate"] is False
    assert c.post(URL, json=attempt("e2", item=item_for(A, "easy", 1)), headers=T).json()["seq"] == 1


def test_identical_duplicate_returns_same_state_and_stores_one_event(env):
    repo, c = env
    serve(repo, "a-stu1", A)
    first = c.post(URL, json=attempt("e1", correct=False), headers=T)
    state_before = c.get("/api/prototype/learners/a-stu1/state", headers=T).json()
    again = c.post(URL, json=attempt("e1", correct=False), headers=T)   # item already consumed: still idempotent
    assert again.status_code == 200 and again.json()["duplicate"] is True
    assert again.json()["seq"] == first.json()["seq"]
    assert again.json()["concepts"] == first.json()["concepts"]
    assert c.get("/api/prototype/learners/a-stu1/state", headers=T).json() == state_before
    assert len(repo.events_for(INST_A, "a-stu1")) == 1
    assert repo.day_of(INST_A, "a-stu1") == 1


@pytest.mark.parametrize("changed", [{"correct": False}, {"item_id": item_for(A, "easy", 1)},
                                     {"concept_id": R, "item_id": item_for(R)}])
def test_conflicting_duplicate_event_id_is_rejected_and_state_unchanged(env, changed):
    repo, c = env
    serve(repo, "a-stu1", A); serve(repo, "a-stu1", A, item_for(A, "easy", 1)); serve(repo, "a-stu1", R)
    c.post(URL, json=attempt("e1"), headers=T)
    before = c.get("/api/prototype/learners/a-stu1/state", headers=T).json()
    r = c.post(URL, json={**attempt("e1"), **changed}, headers=T)
    assert r.status_code == 409
    assert c.get("/api/prototype/learners/a-stu1/state", headers=T).json() == before
    assert len(repo.events_for(INST_A, "a-stu1")) == 1 and repo.day_of(INST_A, "a-stu1") == 1


def test_event_id_is_unique_per_tenant_not_global(env):
    repo, c = env
    serve(repo, "a-stu1", A); serve(repo, "b-stu1", A, inst=INST_B)
    assert c.post(URL, json=attempt("shared-id"), headers=T).status_code == 201
    r = c.post("/api/prototype/learners/b-stu1/events", json=attempt("shared-id", correct=False),
               headers=hdr("tok-b-stu1"))
    assert r.status_code == 201
    assert len(repo.events_for(INST_B, "b-stu1")) == 1 and len(repo.events_for(INST_A, "a-stu1")) == 1


def test_same_event_id_for_another_learner_in_same_institute_is_a_conflict(env):
    repo, c = env
    serve(repo, "a-stu1", A); serve(repo, "a-stu2", A)
    c.post(URL, json=attempt("e1"), headers=T)
    r = c.post("/api/prototype/learners/a-stu2/events", json=attempt("e1"), headers=hdr("tok-a-stu2"))
    assert r.status_code == 409


@pytest.mark.parametrize("field,value", [
    ("response_time_ms", 1200), ("response_time", 3.2), ("time_spent", 10), ("hints_used", 1),
    ("hint_count", 0), ("hint", "x"), ("seq", 5), ("learner_id", "a-stu2"), ("institute_id", INST_A),
    ("day", 99), ("client_time", "2026-11-05T10:00:00Z"), ("anything_else", 1)])
def test_field_outside_adr003_is_refused_with_422_and_nothing_is_stored(env, field, value):
    repo, c = env
    serve(repo, "a-stu1", A)
    r = c.post(URL, json={**attempt("e1"), field: value}, headers=T)
    assert r.status_code == 422
    assert repo.events_for(INST_A, "a-stu1") == [] and repo.day_of(INST_A, "a-stu1") == 0


@pytest.mark.parametrize("bad", [
    {"correct": "true"}, {"correct": 1}, {"event_id": ""}, {"event_id": "   "}, {"concept_id": 3},
    {"concept_id": "jee.unknown.concept"}, {"item_id": "no-such-item"},
    {"concept_id": R, "item_id": item_for(A)}])   # item belongs to another concept
def test_malformed_or_unknown_values_are_422(env, bad):
    repo, c = env
    serve(repo, "a-stu1", A)
    assert c.post(URL, json={**attempt("e1"), **bad}, headers=T).status_code == 422
    assert repo.events_for(INST_A, "a-stu1") == []


def test_missing_field_is_422(env):
    _, c = env
    body = attempt("e1")
    del body["correct"]
    assert c.post(URL, json=body, headers=T).status_code == 422


def test_unknown_learner_is_404_for_an_assigned_teacher_in_same_institute(env):
    _, c = env
    assert c.get("/api/prototype/learners/nobody/state", headers=hdr("tok-a-teacher")).status_code == 404


def test_replay_gives_identical_state_in_two_stores(env_factory):
    script = [(A, True)] * 5 + [(R, False)] * 3
    states = []
    for _ in range(2):
        repo, c = env_factory()
        post_script(repo, c, "a-stu1", "tok-a-stu1", script)
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


# ---- item 4: served-item check ------------------------------------------------------------
def test_attempt_for_an_item_never_served_is_refused(env):
    repo, c = env
    r = c.post(URL, json=attempt("e1"), headers=T)
    assert r.status_code == 422 and "not served" in r.json()["detail"]
    assert repo.events_for(INST_A, "a-stu1") == [] and repo.day_of(INST_A, "a-stu1") == 0


def test_attempt_for_item_served_to_someone_else_or_for_another_concept_is_refused(env):
    repo, c = env
    serve(repo, "a-stu2", A)                      # served to the other student only
    assert c.post(URL, json=attempt("e1"), headers=T).status_code == 422
    serve(repo, "a-stu1", A, item_for(A, "easy", 1))
    r = c.post(URL, json={**attempt("e2"), "concept_id": R, "item_id": item_for(A, "easy", 1)}, headers=T)
    assert r.status_code == 422                   # item exists, but not for concept R


def test_served_item_is_accepted_once_then_refused_with_a_new_event_id(env):
    repo, c = env
    serve(repo, "a-stu1", A)
    assert c.post(URL, json=attempt("e1"), headers=T).status_code == 201
    r = c.post(URL, json=attempt("e2"), headers=T)       # same item, new event id
    assert r.status_code == 422 and "already been answered" in r.json()["detail"]
    assert len(repo.events_for(INST_A, "a-stu1")) == 1


def test_serving_again_cannot_reopen_an_answered_item(env):
    repo, c = env
    serve(repo, "a-stu1", A)
    c.post(URL, json=attempt("e1"), headers=T)
    serve(repo, "a-stu1", A)                             # re-serve attempt: no effect
    assert c.post(URL, json=attempt("e2"), headers=T).status_code == 422


def test_next_step_by_the_learner_serves_the_item_it_returns_and_it_can_then_be_answered(env):
    repo, c = env
    step = c.get("/api/prototype/learners/a-stu1/next-step", headers=T).json()
    assert step["item_id"]
    assert [(s.concept_id, s.item_id, s.kind) for s in repo.served_for(INST_A, "a-stu1")] == \
        [(step["concept_id"], step["item_id"], step["kind"])]
    r = c.post(URL, json=attempt("e1", step["concept_id"], step["item_id"], True), headers=T)
    assert r.status_code == 201
    nxt = c.get("/api/prototype/learners/a-stu1/next-step", headers=T).json()
    assert nxt["item_id"] != step["item_id"]             # the answered item is not offered again


def test_teacher_viewing_next_step_does_not_serve_items(env):
    repo, c = env
    assert c.get("/api/prototype/learners/a-stu1/next-step", headers=hdr("tok-a-teacher")).json()["item_id"]
    assert repo.served_for(INST_A, "a-stu1") == []


def test_teacher_cannot_submit_even_if_the_item_was_served(env):
    repo, c = env
    serve(repo, "a-stu1", A)
    assert c.post(URL, json=attempt("e1"), headers=hdr("tok-a-teacher")).status_code == 403


# ---- item 3: server-side day --------------------------------------------------------------
def test_day_counter_goes_up_once_per_accepted_attempt_only(env):
    repo, c = env
    serve(repo, "a-stu1", A); serve(repo, "a-stu1", A, item_for(A, "easy", 1))
    assert repo.day_of(INST_A, "a-stu1") == 0
    c.post(URL, json=attempt("e1"), headers=T)
    c.post(URL, json=attempt("e1"), headers=T)                                   # duplicate
    c.post(URL, json={**attempt("e1"), "correct": False}, headers=T)             # conflict
    c.post(URL, json=attempt("e9", item="no-such-item"), headers=T)              # 422
    c.post(URL, json={**attempt("e8"), "day": 5}, headers=T)                     # 422 field
    assert repo.day_of(INST_A, "a-stu1") == 1
    r = c.post(URL, json=attempt("e2", item=item_for(A, "easy", 1)), headers=T)
    assert r.json()["day"] == 2 and repo.day_of(INST_A, "a-stu1") == 2
    assert repo.day_of(INST_A, "a-stu2") == 0


def test_client_cannot_choose_the_day(env):
    repo, c = env
    base = c.get("/api/prototype/learners/a-stu1/next-step", headers=T).json()
    for q in ({"day": 1000}, {"day": -5}, {"Day": 7}, {"server_day": 9}):
        r = c.get("/api/prototype/learners/a-stu1/next-step", params=q, headers=T)
        assert r.status_code == 200
        body = r.json()
        assert body["engine_inputs"]["day"] == 0 == base["engine_inputs"]["day"]
        assert (body["kind"], body["item_id"], body["reason"], body["trace"]) == \
               (base["kind"], base["item_id"], base["reason"], base["trace"])
    r = c.get("/api/prototype/learners/a-stu1/next-step", headers={**T, "X-Day": "1000"})
    assert r.json()["engine_inputs"]["day"] == 0
    # a day field in the attempt body is refused (see the ADR-003 field test) and the counter is unchanged
    serve(repo, "a-stu1", A)
    assert c.post(URL, json={**attempt("e1"), "day": 40}, headers=T).status_code == 422
    assert repo.day_of(INST_A, "a-stu1") == 0


def test_revision_uses_the_server_day_and_a_client_day_cannot_pull_a_recheck_forward(env):
    repo, c = env
    # Learner answers everything correctly. A is mastered after 5 answers (day 5); recheck is due
    # base_interval (2) attempts later. The client's day= must have no effect on when it appears.
    kinds = []
    for i in range(40):
        step = c.get("/api/prototype/learners/a-stu1/next-step", params={"day": 10_000}, headers=T).json()
        if not step["item_id"]:
            break
        kinds.append(step["kind"])
        assert c.post(URL, headers=T, json=attempt(f"p{i}", step["concept_id"], step["item_id"], True)).status_code == 201
        if step["kind"] == "recheck":
            assert "Recheck of" in step["reason"] and "due on day" in step["reason"]
            break
    assert "recheck" in kinds, kinds
    first = kinds.index("recheck")
    assert first >= 7                       # not before 5 answers to master + 2 attempts of interval
    # the recheck was a real revision step: its answer is recorded on the same clock
    assert repo.day_of(INST_A, "a-stu1") == len(repo.events_for(INST_A, "a-stu1"))


def test_revision_rows_are_a_pure_function_of_history_and_serve_kinds():
    from app.api_prototype.service import revision_rows
    from app.intelligence.chain import make_events
    ev = make_events("L", [(A, True)] * 5 + [(R, True)] * 2 + [(A, False)])
    kinds = {e.item_id: "practice" for e in ev}
    kinds[ev[-1].item_id] = "recheck"
    rows = revision_rows(ev, kinds)
    assert rows == revision_rows(list(reversed(ev)), kinds) == [(A, 5, "mastered"), (A, 7, "fail")]
