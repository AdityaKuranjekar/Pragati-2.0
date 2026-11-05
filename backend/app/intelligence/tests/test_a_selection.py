"""USP row 3: item selection. Guided entry, step-up, no repeats, approved-only, never easy-only."""
import json
import random
from pathlib import Path

import pytest

from app.intelligence.selection import (DIFFICULTY_SCALE, bank_from_records, entry_level, select_item)

C = "jee.test.c1"
REPO = Path(__file__).resolve().parents[4]


def make_bank(per_level=6, status="approved", concept=C, levels=("easy", "medium", "hard")):
    recs = []
    for lv in levels:
        for i in range(per_level):
            recs.append({"item_id": f"{concept}-{lv[0]}{i:02d}", "topic_id": concept,
                         "difficulty_target": lv, "status": status})
    return bank_from_records(recs)


def serve(bank, target, answers, p0=0.10, **kw):
    """Serve len(answers) items, feeding the given correctness. Returns the Selection list."""
    hist, out = [], []
    for ok in answers:
        sel = select_item(bank, C, p0, hist, target, entry_p_known=p0, **kw)
        out.append(sel)
        hist.append((sel.item_id, ok))
    return out


def test_scale_is_documented_and_ordinal():
    assert DIFFICULTY_SCALE == {"easy": 1, "medium": 2, "hard": 3}
    import app.intelligence.selection as m
    assert "easy = 1" in m.__doc__


@pytest.mark.parametrize("target,p,expected", [
    ("medium", 0.3, "easy"), ("hard", 0.3, "medium"), ("medium", 0.5, "medium"),
    ("hard", 0.9, "hard"), ("easy", 0.1, "easy")])
def test_guided_entry_is_one_band_under_target_when_p_known_below_half(target, p, expected):
    sel = select_item(make_bank(), C, p, [], target)
    assert sel.level_name == expected and sel.served_level_name == expected
    assert entry_level(p, DIFFICULTY_SCALE[target]) == DIFFICULTY_SCALE[expected]


def test_guided_entry_reason_names_the_estimate_and_the_bands():
    sel = select_item(make_bank(), C, 0.30, [], "medium")
    assert "Guided entry" in sel.reason and "30%" in sel.reason and "easy" in sel.reason


def test_a_weak_learner_is_not_kept_on_easy_when_the_target_is_medium_or_hard():
    """Never offer only easy items: with correct evidence the third answer lifts the band."""
    for target in ("medium", "hard"):
        sels = serve(make_bank(), target, [True] * 8)
        names = [s.served_level_name for s in sels]
        assert target in names, names
        assert names.index(target) <= 6
        assert set(names) != {"easy"}


def test_hard_target_never_serves_easy_whatever_the_answers():
    rng = random.Random(3)
    for _ in range(100):
        answers = [rng.random() < 0.4 for _ in range(15)]
        sels = serve(make_bank(per_level=20), "hard", answers)
        assert all(s.served_level_name in ("medium", "hard") for s in sels)


def test_medium_target_never_serves_hard():
    rng = random.Random(4)
    for _ in range(100):
        sels = serve(make_bank(per_level=20), "medium", [rng.random() < 0.9 for _ in range(15)])
        assert all(s.served_level_name != "hard" for s in sels)


def test_steps_up_after_three_correct_and_not_after_one():
    sels = serve(make_bank(), "medium", [True, True, True, True])
    assert [s.served_level_name for s in sels] == ["easy", "easy", "easy", "medium"]
    sels = serve(make_bank(), "medium", [True, False, True, False, True])
    assert {s.served_level_name for s in sels} == {"easy"}


def test_an_answered_item_is_never_repeated_and_a_bank_runs_out_cleanly():
    rng = random.Random(1)
    bank = make_bank(per_level=4)
    sels = serve(bank, "hard", [rng.random() < 0.7 for _ in range(12)], p0=0.9)
    ids = [s.item_id for s in sels]
    assert None not in ids and len(set(ids)) == 12
    hist = [(i, True) for i in ids]
    done = select_item(bank, C, 0.9, hist, "hard", entry_p_known=0.9)
    assert done.item_id is None and "No unanswered" in done.reason


def test_when_a_band_runs_out_it_looks_up_toward_target_not_down():
    bank = make_bank(per_level=2)
    sels = serve(bank, "medium", [False] * 4)         # stays on easy; only 2 easy items exist
    assert [s.served_level_name for s in sels[:2]] == ["easy", "easy"]
    assert sels[2].served_level_name == "medium" and sels[2].bank_gap


def test_only_approved_items_are_served_by_default():
    pending = make_bank(status="pending")
    assert select_item(pending, C, 0.1, [], "medium").item_id is None
    mixed = pending + [b for b in make_bank(status="approved", concept=C) if b.item_id.endswith("e03")]
    sel = select_item(mixed, C, 0.1, [], "medium")
    assert sel.item_id is not None and sel.item_status == "approved"
    assert sel.demo_unapproved_allowed is False and sel.trace["demo_unapproved_allowed"] is False


def test_demo_flag_serves_drafts_and_is_visible_in_the_output():
    sel = select_item(make_bank(status="pending"), C, 0.1, [], "medium", allow_unapproved_demo=True)
    assert sel.item_id is not None and sel.item_status == "pending"
    assert sel.demo_unapproved_allowed is True and sel.trace["demo_unapproved_allowed"] is True
    assert "DEMO ONLY" in sel.reason


def test_needs_edit_and_rejected_items_are_never_served_even_with_the_flag_off():
    for st in ("needs_edit", "rejected", "pending"):
        assert select_item(make_bank(status=st), C, 0.1, [], "medium").item_id is None


def test_thin_bank_is_flagged_not_hidden():
    sel = select_item(make_bank(levels=("easy",)), C, 0.9, [], "medium")
    assert sel.item_id and sel.served_level_name == "easy" and sel.bank_gap
    assert "bank gap" in sel.reason


def test_selection_is_deterministic_and_traced():
    a = serve(make_bank(), "medium", [True, False, True, True, True])
    b = serve(make_bank(), "medium", [True, False, True, True, True])
    assert [x.item_id for x in a] == [y.item_id for y in b]
    t = a[-1].trace
    assert {"ladder_level", "entry_level", "floor", "candidates_unanswered", "ladder_changes"} <= set(t)


def test_bank_records_accept_id_and_review_status_and_reject_bad_rows():
    b = bank_from_records([{"id": "x1", "topic_id": C, "difficulty_target": "easy", "review_status": "approved"}])
    assert b[0].item_id == "x1" and b[0].status == "approved"
    with pytest.raises(ValueError):
        bank_from_records([{"id": "x1", "topic_id": C, "difficulty_target": "trivial", "review_status": "approved"}])
    with pytest.raises(ValueError):
        bank_from_records([{"id": "x1", "topic_id": C, "difficulty_target": "easy", "review_status": "a"}] * 2)


def test_real_demo_bank_is_all_pending_so_nothing_is_served_without_the_flag():
    data = json.loads((REPO / "ml/dataset_pipeline/items/demo_chain_v0.json").read_text())
    bank = bank_from_records(data["items"])
    assert len(bank) == 60 and {b.status for b in bank} == {"pending"}
    topic = "jee.math.complex_numbers.algebra_complex_argand"
    assert select_item(bank, topic, 0.1, [], "medium").item_id is None
    demo = select_item(bank, topic, 0.1, [], "medium", allow_unapproved_demo=True)
    assert demo.item_id and demo.demo_unapproved_allowed


def test_real_demo_bank_has_no_medium_items_for_equation_formation():
    """Finding: equation_formation has only easy items, so a medium target cannot be met there."""
    data = json.loads((REPO / "ml/dataset_pipeline/items/demo_chain_v0.json").read_text())
    bank = bank_from_records(data["items"])
    topic = "jee.math.quadratic_equations.equation_formation"
    sel = select_item(bank, topic, 0.9, [], "medium", allow_unapproved_demo=True)
    assert sel.served_level_name == "easy" and sel.bank_gap
