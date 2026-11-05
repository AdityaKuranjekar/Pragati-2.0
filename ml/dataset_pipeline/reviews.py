"""Review workflow for demo-chain items (S1).

export: writes a CSV review sheet, one row per item, with a verdict and notes column per reviewer.
apply:  reads the returned sheet and updates items. An item becomes "approved" only when BOTH named
        reviewers wrote "approve". Anything else stays pending, or becomes "needs_edit" / "rejected".
        The script never invents an approval: a blank verdict changes nothing.

Usage (from repo root):
  python -m ml.dataset_pipeline.reviews export
  python -m ml.dataset_pipeline.reviews apply <returned_sheet.csv>
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ITEMS_PATH = HERE / "items" / "demo_chain_v0.json"
SHEET_PATH = HERE / "review" / "demo_chain_v0_review.csv"
REVIEWERS = ("Aditya", "Ashray")
VERDICTS = {"approve", "edit", "reject", ""}

COLUMNS = (["item_id", "topic_id", "question", "A", "B", "C", "D", "answer_key", "solution",
            "difficulty_target"]
           + [f"{r}_verdict" for r in REVIEWERS] + [f"{r}_notes" for r in REVIEWERS])


def export_sheet(items: list[dict], path: Path = SHEET_PATH) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        for it in items:
            opts = {o.split(")")[0]: o.split(")", 1)[1].strip() for o in it["options"]}
            row = {"item_id": it["id"], "topic_id": it["topic_id"], "question": it["text"],
                   "A": opts["A"], "B": opts["B"], "C": opts["C"], "D": opts["D"],
                   "answer_key": it["answer"], "solution": it["solution"],
                   "difficulty_target": it["difficulty_target"]}
            for r in REVIEWERS:
                row[f"{r}_verdict"] = ""
                row[f"{r}_notes"] = ""
            w.writerow(row)
    return len(items)


def apply_sheet(items: list[dict], path: Path) -> dict[str, str]:
    """Update items in place from a returned sheet. Returns {item_id: resulting status}."""
    by_id = {it["id"]: it for it in items}
    results: dict[str, str] = {}
    with Path(path).open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            iid = row["item_id"]
            if iid not in by_id:
                raise ValueError(f"unknown item_id {iid}")
            verdicts = {r: (row.get(f"{r}_verdict") or "").strip().lower() for r in REVIEWERS}
            for r, v in verdicts.items():
                if v not in VERDICTS:
                    raise ValueError(f"{iid}: {r} verdict '{v}' must be approve, edit, reject or blank")
            it = by_id[iid]
            if all(v == "approve" for v in verdicts.values()):
                it["reviewers"] = list(REVIEWERS)
                it["review_status"] = "approved"
                it["review_notes"] = {r: row.get(f"{r}_notes", "") for r in REVIEWERS}
                results[iid] = "approved"
            elif "reject" in verdicts.values():
                it["reviewers"] = []
                it["review_status"] = "rejected"
                results[iid] = "rejected"
            elif "edit" in verdicts.values():
                it["reviewers"] = []
                it["review_status"] = "needs_edit"
                results[iid] = "needs_edit"
            else:
                results[iid] = it["review_status"]  # blank or partial: unchanged
    return results


def main(argv: list[str]) -> int:
    data = json.loads(ITEMS_PATH.read_text(encoding="utf-8"))
    if argv[:1] == ["export"]:
        n = export_sheet(data["items"])
        print(f"wrote {n} rows to {SHEET_PATH}")
        return 0
    if argv[:1] == ["apply"] and len(argv) == 2:
        results = apply_sheet(data["items"], Path(argv[1]))
        ITEMS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        from collections import Counter
        print(dict(Counter(results.values())))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
