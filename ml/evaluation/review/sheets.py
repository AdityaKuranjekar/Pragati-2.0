"""Review sheets for E4 and E6 [SIM]. Writes CSV from VISIBLE fields only.

This module takes plain visible dicts and presentation rows. It never imports keys.py or the engine,
never opens the keys directory, and never receives truth. ml/evaluation/tests/test_review.py checks this.
Rater columns are written blank: no rating or label is invented here.
"""
from __future__ import annotations

import csv
from pathlib import Path

RATERS_E4 = ("Rater_A", "Rater_B", "Adjudicator")
TEACHERS_E6 = ("Teacher_1", "Teacher_2", "Teacher_3")
E4_COLUMNS = (["case_id", "goal_concept", "prerequisite_graph", "attempts_and_correct"]
              + [f"{r}_root_concept" for r in RATERS_E4]
              + [f"{r}_confidence_1to5" for r in RATERS_E4[:2]]
              + [f"{r}_notes" for r in RATERS_E4])
E6_COLUMNS = (["row_id", "profile_id", "goal_concept", "prerequisite_graph", "attempts_and_correct",
               "rank", "recommended_concept", "reason_shown"]
              + [f"{t}_rating_1to5" for t in TEACHERS_E6]
              + [f"{t}_assign_yes_no" for t in TEACHERS_E6]
              + [f"{t}_notes" for t in TEACHERS_E6])


def graph_text(prereqs: dict) -> str:
    parts = []
    for c in sorted(prereqs):
        pre = prereqs[c]
        parts.append(f"{c} needs {' and '.join(pre)}" if pre else f"{c} has no prerequisite")
    return "; ".join(parts)


def evidence_text(concepts, correct: dict, attempts: int) -> str:
    return "; ".join(f"{c}: {correct[c]} of {attempts} correct" for c in concepts)


def export_e4(visible: list[dict], path: Path) -> int:
    """visible: dicts from cases.visible_view. Rows are written in the order given (the caller shuffles)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=E4_COLUMNS)
        w.writeheader()
        for v in visible:
            row = {c: "" for c in E4_COLUMNS}
            row.update({"case_id": v["case_id"], "goal_concept": v["goal"],
                        "prerequisite_graph": graph_text(v["prereqs"]),
                        "attempts_and_correct": evidence_text(v["concepts"], v["correct"], v["attempts"])})
            w.writerow(row)
    return len(visible)


def export_e6(rows: list[dict], path: Path) -> int:
    """rows: one per (profile, slot, rank), already shuffled and already carrying visible text only."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=E6_COLUMNS)
        w.writeheader()
        for r in rows:
            row = {c: "" for c in E6_COLUMNS}
            row.update({k: r[k] for k in ("row_id", "profile_id", "goal_concept", "prerequisite_graph",
                                          "attempts_and_correct", "rank", "recommended_concept", "reason_shown")})
            w.writerow(row)
    return len(rows)
