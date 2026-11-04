"""Scoring helper for OMR results using contracts/marking_schemes.yaml."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Mapping

import yaml

from .reader import OmrResult, _contracts_dir


@lru_cache(maxsize=1)
def load_marking_schemes() -> dict[str, dict[str, Any]]:
    doc = yaml.safe_load((_contracts_dir() / "marking_schemes.yaml").read_text(encoding="utf-8"))
    return doc["schemes"]


def _accepted(key: Any) -> set[str]:
    if key is None:
        return set()
    if isinstance(key, (list, tuple, set)):
        return {str(k).strip().upper() for k in key}
    return {s.strip().upper() for s in str(key).split("|") if s.strip()}


def _num_equal(a: str, b: str) -> bool:
    try:
        return abs(float(a) - float(b)) < 1e-6
    except ValueError:
        return False


def score(result: OmrResult, answer_key: Mapping[int | str, Any], marking_scheme: str | Mapping[str, Any]) -> dict[str, Any]:
    """Score a read sheet.

    answer_key: {question_no: "B"} ; several accepted options as "A|C" or ["A","C"]; numeric as "37".
    marking_scheme: scheme id from marking_schemes.yaml (e.g. "jee_main") or a dict with correct/wrong/blank.
    Rules: multi_marked counts as wrong; unreadable counts as blank but is listed in `needs_review`.
    Questions absent from the key are ignored.
    """
    sch = load_marking_schemes()[marking_scheme] if isinstance(marking_scheme, str) else marking_scheme
    key = {int(k): v for k, v in answer_key.items()}
    total, correct, wrong, blank = 0.0, 0, 0, 0
    detail: dict[int, dict[str, Any]] = {}
    needs_review = [u.question_no for u in result.uncertain if u.question_no is not None]
    for qn, k in key.items():
        r = result.questions.get(qn)
        if r is None or r.status in ("blank", "unreadable"):
            outcome, marks = "blank", float(sch["blank"])
            blank += 1
        elif r.status == "multi_marked":
            outcome, marks = "wrong", float(sch["wrong"])
            wrong += 1
        else:
            acc = _accepted(k)
            ok = (r.answer or "").upper() in acc or any(_num_equal(r.answer or "", a) for a in acc)
            outcome, marks = ("correct", float(sch["correct"])) if ok else ("wrong", float(sch["wrong"]))
            correct += ok
            wrong += not ok
        total += marks
        detail[qn] = {"response": r.answer if r else None, "status": r.status if r else "blank", "outcome": outcome, "marks": marks}
    return {
        "marks": total,
        "correct": correct,
        "wrong": wrong,
        "blank": blank,
        "attempted": correct + wrong,
        "max_marks": float(sch["correct"]) * len(key),
        "needs_review": sorted(set(needs_review)),
        "per_question": detail,
    }
