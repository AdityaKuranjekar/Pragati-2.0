from pathlib import Path

import pytest

from ml.dataset_pipeline.rights import RightsError, load_register, validate_item

REG = load_register()


def good_item(**over):
    item = {
        "id": "q-0001",
        "subject": "Mathematics",
        "class_level": "class_11",
        "topic_id": "jee.math.quadratic_equations.roots_nature",
        "q_type": "mcq_single",
        "text": "Original question text.",
        "answer": "B",
        "answer_verified": True,
        "reviewers": ["rev-a", "rev-b"],
        "provenance": {"source_id": "original_reviewed", "rights_record": "author log 2026-11-05"},
    }
    item.update(over)
    return item


def test_register_loads_all_sources():
    assert {"original_reviewed", "ncert_textbooks", "jeebench", "assistments_2009", "openstax"} <= set(REG.sources)


@pytest.mark.parametrize("sid", ["nta_jee_main_archive", "jee_advanced_archive"])
def test_pending_sources_are_blocked_for_every_purpose(sid):
    for purpose in ("student_facing_item", "benchmark_eval", "server_side_model", "reference"):
        assert not REG.allows(sid, purpose)


def test_ncert_is_reference_only():
    assert REG.allows("ncert_textbooks", "reference")
    assert not REG.allows("ncert_textbooks", "student_facing_item")


def test_jeebench_is_benchmark_only():
    assert REG.allows("jeebench", "benchmark_eval")
    with pytest.raises(RightsError):
        REG.require("jeebench", "student_facing_item")


def test_assistments_never_supplies_item_text():
    assert not REG.allows("assistments_2009", "student_facing_item")
    assert REG.allows("assistments_2009", "server_side_model")


def test_openstax_is_blocked_for_student_items():
    assert not REG.allows("openstax", "student_facing_item")


def test_unknown_source_raises():
    with pytest.raises(RightsError):
        REG.require("scraped_coaching_pdf", "reference")


def test_unknown_purpose_raises():
    with pytest.raises(ValueError):
        REG.allows("original_reviewed", "marketing")


def test_valid_original_item_passes():
    assert validate_item(good_item(), REG) == []


def test_item_from_pending_source_fails():
    item = good_item(provenance={"source_id": "nta_jee_main_archive", "rights_record": "x"})
    problems = validate_item(item, REG)
    assert any("not cleared" in p for p in problems)


def test_item_without_two_reviewers_fails():
    problems = validate_item(good_item(reviewers=["rev-a", "rev-a"]), REG)
    assert any("two distinct" in p for p in problems)


def test_unverified_answer_fails():
    problems = validate_item(good_item(answer_verified=False), REG)
    assert any("answer not verified" in p for p in problems)


def test_missing_rights_record_fails():
    problems = validate_item(good_item(provenance={"source_id": "original_reviewed"}), REG)
    assert any("rights_record" in p for p in problems)


def test_register_rejects_duplicate_ids(tmp_path: Path):
    f = tmp_path / "dup.yaml"
    f.write_text(
        "sources:\n"
        "  - {id: a, status: pending, allowed_purposes: []}\n"
        "  - {id: a, status: pending, allowed_purposes: []}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_register(f)


def test_register_rejects_unknown_purpose(tmp_path: Path):
    f = tmp_path / "bad.yaml"
    f.write_text("sources:\n  - {id: a, status: cleared, allowed_purposes: [marketing]}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_register(f)
