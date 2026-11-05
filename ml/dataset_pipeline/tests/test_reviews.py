import copy
import csv
import json
from pathlib import Path

import pytest

from ml.dataset_pipeline.rights import load_register, validate_item
from ml.dataset_pipeline.reviews import COLUMNS, apply_sheet, export_sheet

ITEMS = json.loads((Path(__file__).resolve().parents[1] / "items" / "demo_chain_v0.json")
                   .read_text(encoding="utf-8"))["items"]
REG = load_register()


def write_sheet(path, rows):
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            full = {c: "" for c in COLUMNS}
            full.update(r)
            w.writerow(full)


def test_export_one_row_per_item(tmp_path):
    p = tmp_path / "s.csv"
    assert export_sheet(ITEMS, p) == 60
    with p.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 60 and all(r["Aditya_verdict"] == "" and r["Ashray_verdict"] == "" for r in rows)


def test_export_gives_reviewers_the_key_and_solution(tmp_path):
    p = tmp_path / "s.csv"
    export_sheet(ITEMS, p)
    with p.open(encoding="utf-8") as fh:
        row = next(csv.DictReader(fh))
    assert row["answer_key"] in "ABCD" and row["solution"] and row["question"]


def test_both_approvals_make_item_approved_and_valid(tmp_path):
    items = copy.deepcopy(ITEMS[:2])
    p = tmp_path / "s.csv"
    write_sheet(p, [{"item_id": items[0]["id"], "Aditya_verdict": "approve", "Ashray_verdict": "approve"},
                    {"item_id": items[1]["id"], "Aditya_verdict": "approve"}])
    res = apply_sheet(items, p)
    assert res[items[0]["id"]] == "approved"
    assert items[0]["reviewers"] == ["Aditya", "Ashray"]
    assert validate_item(items[0], REG) == []
    assert res[items[1]["id"]] == "pending" and items[1]["reviewers"] == []


def test_one_edit_blocks_approval(tmp_path):
    items = copy.deepcopy(ITEMS[:1])
    p = tmp_path / "s.csv"
    write_sheet(p, [{"item_id": items[0]["id"], "Aditya_verdict": "approve", "Ashray_verdict": "edit",
                     "Ashray_notes": "answer unclear"}])
    res = apply_sheet(items, p)
    assert res[items[0]["id"]] == "needs_edit" and items[0]["reviewers"] == []
    assert validate_item(items[0], REG)


def test_reject_marks_rejected(tmp_path):
    items = copy.deepcopy(ITEMS[:1])
    p = tmp_path / "s.csv"
    write_sheet(p, [{"item_id": items[0]["id"], "Aditya_verdict": "reject", "Ashray_verdict": "approve"}])
    assert apply_sheet(items, p)[items[0]["id"]] == "rejected"


def test_blank_sheet_changes_nothing(tmp_path):
    items = copy.deepcopy(ITEMS)
    p = tmp_path / "s.csv"
    export_sheet(items, p)
    before = copy.deepcopy(items)
    apply_sheet(items, p)
    assert items == before


def test_invalid_verdict_is_an_error(tmp_path):
    items = copy.deepcopy(ITEMS[:1])
    p = tmp_path / "s.csv"
    write_sheet(p, [{"item_id": items[0]["id"], "Aditya_verdict": "looks good", "Ashray_verdict": "approve"}])
    with pytest.raises(ValueError):
        apply_sheet(items, p)


def test_unknown_item_id_is_an_error(tmp_path):
    p = tmp_path / "s.csv"
    write_sheet(p, [{"item_id": "nope", "Aditya_verdict": "approve", "Ashray_verdict": "approve"}])
    with pytest.raises(ValueError):
        apply_sheet(copy.deepcopy(ITEMS), p)
