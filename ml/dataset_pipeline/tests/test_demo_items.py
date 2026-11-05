"""S1 checks on the 60 demo-chain draft items.

Each answer is recomputed here with a different method from the generator (floating-point complex
arithmetic and cmath roots), so a generator bug cannot pass silently. Validation must fail ONLY on the
human-reviewer requirement: that is the S1 gate, not a bug.
"""
import cmath
import json
import math
from collections import Counter
from pathlib import Path

import pytest

from ml.dataset_pipeline.rights import load_register, validate_item

ITEMS_PATH = Path(__file__).resolve().parents[1] / "items" / "demo_chain_v0.json"
DATA = json.loads(ITEMS_PATH.read_text(encoding="utf-8"))
ITEMS = DATA["items"]
REG = load_register()


def option_value(item, letter):
    for opt in item["options"]:
        if opt.startswith(f"{letter})"):
            return float(opt.split(")", 1)[1].strip().replace(" ", "")) if "/" not in opt else \
                float(eval(opt.split(")", 1)[1].strip()))
    raise KeyError(letter)


def recompute(p):
    op = p["op"]
    if op == "mod2":
        z = complex(p["a"], p["b"])
        return abs(z) ** 2
    if op == "re_inv":
        return (1 / complex(p["a"], p["b"])).real
    if op == "im_conj_prod":
        return ((complex(p["a"], -p["b"])) * complex(p["c"], p["d"])).imag
    if op == "re_sq":
        return (complex(p["a"], p["b"]) ** 2).real
    if op == "disc":
        return p["b"] ** 2 - 4 * p["a"] * p["c"]
    if op == "nature":
        roots = [r for r in _roots(p["a"], p["b"], p["c"])]
        real = [r for r in roots if abs(r.imag) < 1e-9]
        distinct = {round(r.real, 9) for r in real}
        return float(len(distinct))
    if op == "equal_roots":
        return float(p["m"] * 2)
    if op == "sum_roots":
        return -p["b"] / p["a"]
    if op == "coef_x":
        return float(-(p["al"] + p["be"]))
    if op == "const":
        return float(p["al"] * p["be"])
    raise ValueError(op)


def _roots(a, b, c):
    d = cmath.sqrt(b * b - 4 * a * c)
    return [(-b + d) / (2 * a), (-b - d) / (2 * a)]


def test_counts_and_split():
    assert len(ITEMS) == 60 == DATA["manifest"]["count"]
    assert Counter(i["topic_id"] for i in ITEMS) == {
        "jee.math.complex_numbers.algebra_complex_argand": 20,
        "jee.math.quadratic_equations.roots_nature": 20,
        "jee.math.quadratic_equations.equation_formation": 20,
    }


def test_ids_and_texts_are_unique():
    assert len({i["id"] for i in ITEMS}) == 60
    assert len({i["text"] for i in ITEMS}) == 60


@pytest.mark.parametrize("item", ITEMS, ids=lambda i: i["id"])
def test_options_have_one_correct_letter_and_distinct_values(item):
    letters = [o.split(")")[0] for o in item["options"]]
    assert letters == ["A", "B", "C", "D"]
    values = [option_value(item, l) for l in letters]
    assert len(set(round(v, 9) for v in values)) == 4
    assert item["answer"] in letters
    assert math.isclose(option_value(item, item["answer"]), float(eval(item["answer_value"])) if "/" in item["answer_value"] else float(item["answer_value"]))


@pytest.mark.parametrize("item", ITEMS, ids=lambda i: i["id"])
def test_answer_matches_independent_recomputation(item):
    expected = recompute(item["params"])
    stored = float(eval(item["answer_value"])) if "/" in item["answer_value"] else float(item["answer_value"])
    assert math.isclose(expected, stored, rel_tol=1e-9, abs_tol=1e-9), (expected, stored)


@pytest.mark.parametrize("item", ITEMS, ids=lambda i: i["id"])
def test_validation_fails_only_on_human_review(item):
    problems = validate_item(item, REG)
    assert problems == ["needs two distinct human reviewers"], problems


@pytest.mark.parametrize("item", ITEMS, ids=lambda i: i["id"])
def test_drafts_are_pending_and_original(item):
    assert item["review_status"] == "pending"
    assert item["reviewers"] == []
    assert item["provenance"]["source_id"] == "original_reviewed"
    assert item["answer_verified"] is True
    assert "NCERT" not in json.dumps(item) and "JEE Main" not in item["text"]
