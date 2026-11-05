"""USP row 5: revision. Intervals grow with each successful recheck, shorten after an error, day is an input."""
import ast
from pathlib import Path

import pytest

import app.intelligence.revision as rev
from app.intelligence.mastery import ConceptState
from app.intelligence.revision import (RevisionPolicy, apply_lapses, due, on_mastered, on_recheck, refresh, replay)


def test_interval_grows_with_each_successful_recheck():
    s = on_mastered("c", 0)
    assert (s.interval, s.due_day) == (2, 2)
    seen = [s.interval]
    day = s.due_day
    for _ in range(5):
        s = on_recheck(s, day, True)
        seen.append(s.interval)
        day = s.due_day
    assert seen == [2, 4, 8, 16, 30, 30]          # doubles, capped
    assert all(b >= a for a, b in zip(seen, seen[1:])) and seen[1] > seen[0]
    assert s.successes == 5 and not s.lapsed


def test_interval_shortens_after_an_error_and_the_concept_is_lapsed():
    s = on_mastered("c", 0)
    s = on_recheck(s, 2, True)          # 4
    s = on_recheck(s, 6, True)          # 8
    before = s.interval
    s = on_recheck(s, 14, False)
    assert s.interval < before and s.interval == 4 and s.due_day == 18
    assert s.lapsed and s.lapses == 1 and s.successes == 0


def test_after_a_lapse_a_correct_recheck_clears_it_and_growth_resumes_from_the_short_interval():
    s = on_recheck(on_mastered("c", 0), 2, False)       # 2 -> 1
    assert s.interval == 1 and s.lapsed
    s = on_recheck(s, 3, True)
    assert not s.lapsed and s.interval == 2 and s.successes == 1


def test_interval_never_falls_below_min():
    s = on_mastered("c", 0)
    for d in range(1, 8):
        s = on_recheck(s, d, False)
    assert s.interval == 1


def test_replay_is_deterministic_and_order_dependent_only_through_the_rows():
    rows = [("a", 0, "mastered"), ("b", 1, "mastered"), ("a", 2, "pass"), ("b", 3, "fail"), ("a", 6, "pass")]
    assert replay(rows) == replay(list(rows))
    assert replay(rows)["a"].interval == 8 and replay(rows)["b"].lapsed


def test_recheck_before_mastery_and_unknown_kinds_are_refused():
    with pytest.raises(ValueError):
        replay([("a", 1, "pass")])
    with pytest.raises(ValueError):
        replay([("a", 1, "seen")])


@pytest.mark.parametrize("bad", [-1, 1.5, "3", True, None])
def test_day_must_be_a_non_negative_integer(bad):
    with pytest.raises(ValueError):
        on_mastered("c", bad)  # type: ignore[arg-type]


def test_day_cannot_go_backwards_for_one_concept():
    s = on_mastered("c", 5)
    with pytest.raises(ValueError):
        on_recheck(s, 4, True)


def test_due_returns_only_overdue_schedules_most_overdue_first():
    sch = {"b": on_mastered("b", 0), "a": on_mastered("a", 0), "c": on_mastered("c", 3)}
    assert [s.concept_id for s in due(sch, 1)] == []
    assert [s.concept_id for s in due(sch, 2)] == ["a", "b"]
    assert [s.concept_id for s in due(sch, 9)] == ["a", "b", "c"]


def test_refresh_schedules_only_newly_mastered_concepts_and_keeps_existing_ones():
    st = {"a": ConceptState("a", 0.95, 6, "mastered"), "b": ConceptState("b", 0.4, 6, "unmastered")}
    s1 = refresh({}, st, 4)
    assert set(s1) == {"a"} and s1["a"].due_day == 6
    s2 = refresh(s1, st, 9)
    assert s2["a"] == s1["a"]


def test_a_lapsed_concept_is_not_treated_as_mastered():
    st = {"a": ConceptState("a", 0.95, 6, "mastered")}
    lapsed = on_recheck(on_mastered("a", 0), 2, False)
    out = apply_lapses(st, {"a": lapsed})
    assert out["a"].band == "uncertain" and out["a"].p_known == 0.95
    assert apply_lapses(st, {"a": on_mastered("a", 0)})["a"].band == "mastered"


def test_policy_is_configurable_and_validated():
    p = RevisionPolicy(base_interval=1, growth=3.0, max_interval=9, error_factor=0.5, min_interval=1)
    s = on_mastered("c", 0, p)
    seq = []
    for _ in range(4):
        s = on_recheck(s, s.due_day, True, p)
        seq.append(s.interval)
    assert seq == [3, 9, 9, 9]
    for bad in (dict(growth=1.0), dict(error_factor=1.0), dict(min_interval=0), dict(max_interval=1, base_interval=2)):
        with pytest.raises(ValueError):
            RevisionPolicy(**bad)


def test_module_does_not_use_a_clock():
    tree = ast.parse(Path(rev.__file__).read_text())
    mods = {n.names[0].name for n in ast.walk(tree) if isinstance(n, ast.Import)} | \
           {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not ({"time", "datetime"} & mods)
