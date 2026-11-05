"""The wow sequence (PROTOTYPE_PLAN §1): different evidence -> different next step -> new evidence -> changed step."""
from app.intelligence.chain import A, R, F, NAMES, DEMO_GOAL, LEARNER_A, LEARNER_B, demo_graph, make_events
from app.intelligence.mastery import learner_state
from app.intelligence.policy import recommend


def test_two_fixture_learners_get_different_next_steps():
    g = demo_graph()
    a = recommend(g, DEMO_GOAL, learner_state(make_events("A", LEARNER_A), [A, R, F]), NAMES)
    b = recommend(g, DEMO_GOAL, learner_state(make_events("B", LEARNER_B), [A, R, F]), NAMES)
    assert (a.action, a.concept_id) != (b.action, b.concept_id)
    assert a.concept_id == R      # A is fine; the roots step is the gap
    assert b.concept_id == A      # B's gap is the foundation


def test_new_evidence_changes_the_recommendation():
    g = demo_graph()
    before = recommend(g, DEMO_GOAL, learner_state(make_events("B", LEARNER_B), [A, R, F]), NAMES)
    more = make_events("B", LEARNER_B) + make_events("B", [(A, True)] * 5, start_seq=3, prefix="later")
    after = recommend(g, DEMO_GOAL, learner_state(more, [A, R, F]), NAMES)
    assert before.concept_id == A and before.action == "review_prerequisite"
    assert after.action == "gather_evidence" and after.concept_id == R
    assert after.trace["rule"] == "insufficient_evidence_first"


def test_every_recommendation_carries_reason_trace_and_policy_version():
    rec = recommend(demo_graph(), DEMO_GOAL, learner_state(make_events("B", LEARNER_B), [A, R, F]), NAMES)
    assert rec.reason and rec.policy_version == "policy-v0.1"
    assert rec.trace["chain"] == [A, R, F]
    assert set(rec.trace["bands"]) == {A, R, F}
