"""E0: invariants, determinism, idempotency, input contracts, graph validity."""
import random

import pytest

from app.intelligence.chain import A, R, F, make_events, demo_graph
from app.intelligence.events import AttemptEvent, parse_event
from app.intelligence.graph import Edge, Graph
from app.intelligence.mastery import fold_concept, learner_state

VALID = {"event_id": "e1", "learner_id": "L", "concept_id": A, "item_id": "i1", "correct": True, "seq": 0}


def test_replay_is_deterministic_regardless_of_input_order():
    evs = make_events("L", [(A, True), (A, False), (A, True), (A, True), (A, False)])
    shuffled = evs[:]
    random.Random(7).shuffle(shuffled)
    assert fold_concept(evs, A) == fold_concept(shuffled, A)


def test_identical_duplicate_is_ignored():
    evs = make_events("L", [(A, True), (A, True)])
    assert fold_concept(evs + [evs[0]], A) == fold_concept(evs, A)


def test_conflicting_duplicate_event_id_raises():
    ev = make_events("L", [(A, True)])[0]
    clash = AttemptEvent(ev.event_id, ev.learner_id, ev.concept_id, ev.item_id, False, ev.seq)
    with pytest.raises(ValueError):
        fold_concept([ev, clash], A)


def test_duplicate_seq_raises():
    a = AttemptEvent("x", "L", A, "i", True, 0)
    b = AttemptEvent("y", "L", A, "i", True, 0)
    with pytest.raises(ValueError):
        fold_concept([a, b], A)


def test_prefix_independence_no_future_leakage():
    evs = make_events("L", [(A, True), (A, False), (A, True), (A, True), (A, False), (A, True)])
    prefix = fold_concept(evs[:3], A)
    later = fold_concept(evs[:3] + [AttemptEvent("z", "L", A, "i", True, 99)], A)
    assert prefix.n == 3
    assert later.n == 4 and later.p_known != prefix.p_known  # later evidence changes only the later state


def test_other_concepts_do_not_leak_into_state():
    evs = make_events("L", [(R, False)] * 4)
    assert fold_concept(evs, A).n == 0


def test_parse_accepts_valid_event():
    assert parse_event(VALID).correct is True


@pytest.mark.parametrize("extra", ["response_time_ms", "hint_count", "hints_used", "time_on_item"])
def test_minor_safety_rejects_timing_and_hint_fields(extra):
    with pytest.raises(ValueError, match="not allowed"):
        parse_event({**VALID, extra: 1200})


@pytest.mark.parametrize("bad", [
    {"correct": "yes"}, {"seq": -1}, {"seq": True}, {"event_id": ""}, {"concept_id": None},
])
def test_parse_rejects_malformed_fields(bad):
    with pytest.raises(ValueError):
        parse_event({**VALID, **bad})


def test_parse_rejects_missing_field():
    d = dict(VALID)
    del d["seq"]
    with pytest.raises(ValueError, match="missing"):
        parse_event(d)


def test_graph_rejects_cycle():
    with pytest.raises(ValueError, match="cycle"):
        Graph(["a", "b"], [Edge("a", "b"), Edge("b", "a")])


def test_graph_rejects_unknown_node_self_loop_duplicate_and_bad_status():
    with pytest.raises(ValueError):
        Graph(["a"], [Edge("a", "z")])
    with pytest.raises(ValueError):
        Graph(["a"], [Edge("a", "a")])
    with pytest.raises(ValueError):
        Graph(["a", "b"], [Edge("a", "b"), Edge("a", "b")])
    with pytest.raises(ValueError):
        Graph(["a", "b"], [Edge("a", "b", "guessed")])


def test_topo_order_respects_prerequisites_and_ancestors_are_transitive():
    g = demo_graph()
    order = g.topo_order()
    assert order.index(A) < order.index(R) < order.index(F)
    assert g.ancestors(F) == {A, R}
    assert g.descendants(A) == {R, F}


def test_demo_chain_is_taxonomy_valid_names():
    g = demo_graph()
    assert set(g.nodes) == {A, R, F}
    assert all(e.review_status == "proposed" for e in g.edges)
