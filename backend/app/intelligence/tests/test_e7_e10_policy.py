"""E7: no prerequisite violations. E10: cold start, sparse, contradictory and guessed evidence."""
import random

from app.intelligence.chain import A, R, F, NAMES, DEMO_GOAL, demo_graph, make_events
from app.intelligence.graph import Edge, Graph
from app.intelligence.mastery import ConceptState, learner_state
from app.intelligence.policy import cohort_bottlenecks, goal_chain, recommend

ACTIONS_THAT_NAME_A_CONCEPT = {"review_prerequisite", "practice_target", "gather_evidence", "diagnostic"}


def random_dag(rng, n):
    nodes = [f"c{i}" for i in range(n)]
    edges = []
    for j in range(1, n):
        for i in range(j):
            if rng.random() < 0.35:
                edges.append(Edge(nodes[i], nodes[j], rng.choice(["proposed", "reviewed"])))
    return Graph(nodes, edges)


def test_e7_no_recommendation_while_a_prerequisite_is_unmastered():
    """Across 300 random graphs and learner histories: the recommended concept's prerequisites
    inside the goal chain are all mastered, unless the action is the prerequisite itself."""
    violations = 0
    checked = 0
    for seed in range(300):
        rng = random.Random(seed)
        g = random_dag(rng, rng.randint(3, 8))
        goal = g.topo_order()[-1]
        script = [(c, rng.random() < 0.6) for c in g.nodes for _ in range(rng.randint(0, 7))]
        rng.shuffle(script)
        states = learner_state(make_events("L", script, prefix=f"s{seed}"), g.nodes)
        rec = recommend(g, goal, states)
        if rec.concept_id is None or rec.action not in ACTIONS_THAT_NAME_A_CONCEPT | {"practice_target"}:
            continue
        checked += 1
        for anc in g.ancestors(rec.concept_id) & set(goal_chain(g, goal)):
            if states.get(anc, ConceptState(anc, 0, 0, "insufficient")).band != "mastered":
                violations += 1
    assert checked > 100
    assert violations == 0


def test_e7_recommendation_order_is_topological_within_chain():
    g = demo_graph()
    states = learner_state(make_events("L", [(A, True)] * 5), g.nodes)
    rec = recommend(g, F, states)
    assert rec.concept_id == R  # A mastered; R is the first chain concept not mastered


def test_e7_sensitivity_removing_a_prerequisite_changes_the_path():
    """If the A -> R link is wrong, the recommendation must change. Otherwise the graph is not used."""
    evs = make_events("B", [(A, False)] * 3)
    with_edge = recommend(demo_graph(), F, learner_state(evs, [A, R, F]), NAMES)
    without = demo_graph().without_edge(A, R)
    no_edge = recommend(without, F, learner_state(evs, [A, R, F]), NAMES)
    assert with_edge.concept_id == A and with_edge.action == "review_prerequisite"
    assert no_edge.action != with_edge.action or no_edge.concept_id != with_edge.concept_id


def test_e7_proposed_edge_is_named_in_reason():
    rec = recommend(demo_graph("proposed"), F, learner_state(make_events("B", [(A, False)] * 3), [A, R, F]), NAMES)
    assert "not yet teacher-reviewed" in rec.reason
    rec2 = recommend(demo_graph("reviewed"), F, learner_state(make_events("B", [(A, False)] * 3), [A, R, F]), NAMES)
    assert "not yet teacher-reviewed" not in rec2.reason


# ---- E10 ----

def test_e10_cold_start_gives_diagnostic_not_a_path():
    rec = recommend(demo_graph(), DEMO_GOAL, {}, NAMES)
    assert rec.action == "diagnostic" and rec.concept_id == A
    assert "No answers yet" in rec.reason


def test_e10_sparse_one_or_two_answers_is_not_judged():
    for k in (1, 2):
        states = learner_state(make_events("S", [(A, True)] * k), [A, R, F])
        rec = recommend(demo_graph(), F, states, NAMES)
        assert rec.action == "gather_evidence" and rec.concept_id == A
        assert states[A].band == "insufficient"


def test_e10_contradictory_evidence_stays_uncertain():
    states = learner_state(make_events("C", [(A, i % 2 == 0) for i in range(20)]), [A])
    s = states[A]
    assert s.band == "uncertain"
    assert 0.3 < s.p_known < 0.7


def test_e10_lucky_guess_run_is_not_mastery():
    """Three correct answers on a 4-option item can happen by chance (p = 1/64). The engine must not
    call that mastered; the guard requires five answers."""
    s = learner_state(make_events("G", [(A, True)] * 3), [A])[A]
    assert s.p_known > 0.85 and s.band == "uncertain"


def test_e10_missing_concept_in_states_is_treated_as_insufficient():
    rec = recommend(demo_graph(), F, {A: ConceptState(A, 0.95, 6, "mastered")}, NAMES)
    assert rec.action == "gather_evidence" and rec.concept_id == R


def test_e10_unknown_goal_raises():
    try:
        recommend(demo_graph(), "nope", {})
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_e10_goal_mastered_when_chain_mastered():
    g = demo_graph()
    evs = make_events("M", [(A, True)] * 5 + [(R, True)] * 5 + [(F, True)] * 5)
    rec = recommend(g, F, learner_state(evs, [A, R, F]), NAMES)
    assert rec.action == "goal_mastered"


def test_cohort_bottleneck_counts_learners_blocked_by_unmastered_prerequisite():
    g = demo_graph()
    learners = {
        f"L{i}": learner_state(make_events(f"L{i}", [(A, False)] * 3), [A, R, F]) for i in range(3)
    }
    learners["Lok"] = learner_state(make_events("Lok", [(A, True)] * 5), [A, R, F])
    rows = cohort_bottlenecks(g, learners)
    top = rows[0]
    assert top["concept_id"] == A and top["learners_blocked"] == 3
    assert top["edge_review"] == ["proposed"]
