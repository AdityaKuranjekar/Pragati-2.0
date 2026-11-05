"""USP row 4: raise only after k=3 correct in a row, never on one lucky answer; lower after 2 wrong."""
import random

import pytest

from app.intelligence.challenge import RAISE_AFTER, LOWER_AFTER, floor_for, ladder

T, F = True, False


def test_constants_are_k3_and_m2():
    assert RAISE_AFTER == 3 and LOWER_AFTER == 2


def test_one_lucky_correct_answer_does_not_raise():
    assert ladder([T], entry_level=1, target=2).level == 1
    assert ladder([T], entry_level=2, target=3).level == 2


def test_two_correct_do_not_raise_three_do():
    assert ladder([T, T], 2, 3).level == 2
    r = ladder([T, T, T], 2, 3)
    assert r.level == 3 and r.changes == ((2, "raise", 3),)


def test_lucky_correct_between_wrong_answers_holds():
    assert ladder([F, T, F, T, T], 2, 3).level == 2     # never 3 in a row


def test_contradictory_runs_hold_the_level():
    for target, start in ((2, 1), (2, 2), (3, 2), (3, 3)):
        assert ladder([T, F] * 10, start, target).level == start
        assert ladder([F, T] * 10, start, target).level == start
        assert ladder([T, T, F] * 6, start, target).level == start


def test_two_wrong_in_a_row_lower_one_band_one_wrong_does_not():
    assert ladder([F], 2, 2).level == 2
    r = ladder([F, F], 2, 2)
    assert r.level == 1 and r.changes == ((1, "lower", 1),)


def test_evidence_must_be_earned_again_after_each_change():
    # target hard: floor is medium, so use a 4-band-free check on target medium->hard via entry 2
    assert ladder([T, T, T, T, T], 1, 2).level == 2
    assert ladder([T, T, T, T, T], 2, 3).level == 3 and len(ladder([T] * 5, 2, 3).changes) == 1
    r = ladder([T, T, T, F, T, T], 1, 2)   # raised at index 2; then F T T is not 3 in a row
    assert r.level == 2 and r.correct_run == 2


def test_level_is_capped_at_target_and_floored_below_it():
    assert ladder([T] * 30, 1, 2).level == 2
    assert ladder([F] * 30, 2, 3).level == floor_for(3) == 2   # hard target never reaches easy
    assert floor_for(1) == 1 and floor_for(2) == 1


def test_property_every_raise_is_backed_by_k_correct_and_every_lower_by_m_wrong():
    rng = random.Random(7)
    for _ in range(500):
        hist = [rng.random() < rng.choice([0.2, 0.5, 0.8]) for _ in range(rng.randint(0, 40))]
        target, entry = rng.randint(1, 3), rng.randint(1, 3)
        r = ladder(hist, entry, target)
        assert floor_for(target) <= r.level <= target
        for i, move, _ in r.changes:
            if move == "raise":
                assert all(hist[i - RAISE_AFTER + 1:i + 1]) and i >= RAISE_AFTER - 1
            else:
                assert not any(hist[i - LOWER_AFTER + 1:i + 1]) and i >= LOWER_AFTER - 1


def test_k_below_two_is_refused():
    with pytest.raises(ValueError):
        ladder([T], 1, 2, k=1)


def test_non_boolean_history_is_refused():
    with pytest.raises(ValueError):
        ladder([1, 0, 1], 1, 2)  # type: ignore[list-item]
