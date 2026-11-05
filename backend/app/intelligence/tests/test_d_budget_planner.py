"""USP row 6: budget input, minimum-item path, no timing data. Plus planner composition."""
import inspect

import pytest

from app.intelligence import policy
from app.intelligence.chain import A, R, F, NAMES, DEMO_GOAL, demo_graph, make_events
from app.intelligence.mastery import ConceptState, learner_state
from app.intelligence.planner import AdaptiveSession, PlannerConfig
from app.intelligence.policy import items_available, items_to_reach, recommend, recommend_with_budget
from app.intelligence.revision import on_mastered
from app.intelligence.selection import bank_from_records


def bank():
    recs = []
    for c in (A, R, F):
        for lv in ("easy", "medium"):
            for i in range(12):
                recs.append({"item_id": f"{c[-6:]}-{lv[0]}{i:02d}", "topic_id": c,
                             "difficulty_target": lv, "status": "approved"})
    return bank_from_records(recs)


def test_best_case_items_is_zero_when_mastered_and_respects_the_five_answer_guard():
    assert items_to_reach(0.95, 6) == 0
    assert items_to_reach(0.95, 2) == 3          # estimate is high but 5 answers are needed
    assert items_to_reach(0.10, 0) >= 5
    assert items_to_reach(0.50, 3) <= items_to_reach(0.10, 3)


def test_items_available_is_an_explicit_product_of_days_and_rate():
    assert items_available(10, 4) == 40
    with pytest.raises(ValueError):
        items_available(-1, 4)


def test_short_budget_says_so_gives_a_minimum_plan_and_keeps_the_concept_choice():
    g = demo_graph()
    st = learner_state(make_events("B", [(A, False)] * 3), [A, R, F])
    base = recommend(g, DEMO_GOAL, st, NAMES)
    rec = recommend_with_budget(g, DEMO_GOAL, st, 6, NAMES)
    b = rec.trace["budget"]
    assert rec.concept_id == base.concept_id and rec.action == base.action
    assert b["short"] and b["goal_unreachable_in_budget"] and b["min_items_needed"] > 6
    assert "Budget is short" in rec.reason and "minimum" in rec.reason.lower()
    assert [p["concept_id"] for p in b["plan"]] == [A, R, F]
    assert b["needed_is"] == "best case, every answer correct"


def test_budget_that_just_fits_is_short_but_reachable_and_a_roomy_one_is_not_short():
    g = demo_graph()
    st = learner_state([], [A, R, F])
    need = recommend_with_budget(g, DEMO_GOAL, st, 100).trace["budget"]["min_items_needed"]
    tight = recommend_with_budget(g, DEMO_GOAL, st, need).trace["budget"]
    assert tight["short"] and not tight["goal_unreachable_in_budget"]
    roomy = recommend_with_budget(g, DEMO_GOAL, st, need * 2)
    assert not roomy.trace["budget"]["short"] and "Budget is short" not in roomy.reason


def test_budget_must_be_a_non_negative_integer():
    st = learner_state([], [A, R, F])
    for bad in (-1, 2.5, True, None):
        with pytest.raises(ValueError):
            recommend_with_budget(demo_graph(), DEMO_GOAL, st, bad)  # type: ignore[arg-type]


def test_no_response_time_or_speed_input_exists_anywhere_in_the_budget_api():
    for fn in (recommend_with_budget, items_available, items_to_reach):
        names = set(inspect.signature(fn).parameters)
        assert not any(w in n for n in names for w in ("time", "second", "latency", "speed", "hint")), names
    with pytest.raises(TypeError):
        recommend_with_budget(demo_graph(), DEMO_GOAL, {}, 10, response_time=3.2)  # type: ignore[call-arg]
    assert policy.SHORT_SLACK >= 1.0


def _mastered_session(cfg=PlannerConfig()):
    s = AdaptiveSession("L", demo_graph(), DEMO_GOAL, bank(), cfg, NAMES)
    # master A: 5 correct answers on day 0 (5 is the minimum for a 'mastered' label)
    for i in range(5):
        st = s.next_step(0, 60)
        assert st.concept_id == A, st
        s.record(st, True, 0)
    assert s.states()[A].band == "mastered"
    return s


def test_planner_serves_a_recheck_when_due_and_defers_it_when_the_budget_is_short():
    s = _mastered_session()
    s.next_step(0, 60)                     # creates the schedule on day 0
    assert s.schedules[A].due_day == 2
    roomy = s.next_step(2, 60)
    assert roomy.kind == "recheck" and roomy.concept_id == A and "recheck" in roomy.reason.lower()
    short = s.next_step(2, 4)
    assert short.kind == "practice" and short.concept_id != A
    assert "Budget is short" in short.reason


def test_a_failed_recheck_sends_the_learner_back_to_that_concept():
    s = _mastered_session()
    s.next_step(0, 60)
    st = s.next_step(2, 60)
    assert st.kind == "recheck"
    s.record(st, False, 2)
    assert s.schedules[A].lapsed
    nxt = s.next_step(2, 60)
    assert nxt.concept_id == A and nxt.kind in ("practice", "recheck")


def test_planner_is_deterministic_and_events_carry_no_timing_fields():
    def run():
        s = AdaptiveSession("L", demo_graph(), DEMO_GOAL, bank(), PlannerConfig(), NAMES)
        out = []
        for i in range(25):
            st = s.next_step(i // 4, 60 - i)
            if st.kind == "none":
                continue
            s.record(st, (i % 3) != 0, i // 4)
            out.append((st.kind, st.concept_id, st.item_id))
        return out, [vars(e) if hasattr(e, "__dict__") else e for e in s.events]
    a, b = run(), run()
    assert a == b
    from app.intelligence.events import ALLOWED_FIELDS
    assert set(a[1][0]) == set(ALLOWED_FIELDS)


def test_every_planner_step_has_a_reason_and_no_unapproved_item_is_served():
    pend = bank_from_records([{**{"item_id": f"p{i}", "topic_id": A, "difficulty_target": "easy"},
                               "status": "pending"} for i in range(5)])
    s = AdaptiveSession("L", demo_graph(), DEMO_GOAL, pend, PlannerConfig(), NAMES)
    st = s.next_step(0, 30)
    assert st.kind == "none" and st.item_id is None and st.reason
    s2 = AdaptiveSession("L", demo_graph(), DEMO_GOAL, pend, PlannerConfig(allow_unapproved_demo=True), NAMES)
    st2 = s2.next_step(0, 30)
    assert st2.item_id and st2.selection.demo_unapproved_allowed and "DEMO ONLY" in st2.reason


def test_ablation_flags_change_behaviour_in_the_expected_direction():
    s = AdaptiveSession("L", demo_graph(), DEMO_GOAL, bank(), PlannerConfig(use_graph=False), NAMES)
    assert s.next_step(0, 60).concept_id == A      # lowest estimate, ties by id: no prerequisite reasoning
    s = AdaptiveSession("L", demo_graph(), DEMO_GOAL, bank(), PlannerConfig(use_challenge=False), NAMES)
    for i in range(8):
        st = s.next_step(0, 60)
        assert st.selection.served_level_name == "easy"
        s.record(st, True, 0)
