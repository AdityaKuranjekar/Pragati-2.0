"""Template generator for the S1 demo chain (original items; no third-party text).

Writes ml/dataset_pipeline/items/demo_chain_v0.json. Every answer is computed with exact
fractions from the stored parameters, and each item carries a run manifest.

Items are DRAFTS: review_status is "pending" and reviewers is empty. validate_item() will keep
reporting "needs two distinct human reviewers" until two people review each item (S1 gate).

Run:  python -m ml.dataset_pipeline.generate_demo_items
"""
from __future__ import annotations

import json
import random
from fractions import Fraction
from pathlib import Path

from .rights import load_register  # noqa: F401  (import check: register loads)

SEED = 20261105
GENERATOR_VERSION = "demo-templates-v0"
OUT = Path(__file__).with_name("items") / "demo_chain_v0.json"

A = "jee.math.complex_numbers.algebra_complex_argand"
R = "jee.math.quadratic_equations.roots_nature"
F = "jee.math.quadratic_equations.equation_formation"


def fmt(x: Fraction) -> str:
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


def complex_text(a: int, b: int) -> str:
    if b >= 0:
        return f"{a} + {b}i"
    return f"{a} - {abs(b)}i"


def make_options(correct: Fraction, distractors: list[Fraction], rng: random.Random) -> tuple[list[str], str]:
    pool: list[Fraction] = []
    for d in distractors:
        if d != correct and d not in pool:
            pool.append(d)
    # fill to three distractors with small nearby values if templates gave too few
    k = 1
    while len(pool) < 3:
        for cand in (correct + k, correct - k):
            if cand != correct and cand not in pool:
                pool.append(cand)
        k += 1
    options = [correct] + pool[:3]
    rng.shuffle(options)
    letters = "ABCD"
    labelled = [f"{letters[i]}) {fmt(v)}" for i, v in enumerate(options)]
    answer = letters[options.index(correct)]
    return labelled, answer


def item(idx, topic, text, correct: Fraction, distractors, params, solution, difficulty, rng):
    options, answer = make_options(correct, distractors, rng)
    return {
        "id": f"demo-v0-{idx:03d}",
        "subject": "Mathematics",
        "class_level": "class_11",
        "topic_id": topic,
        "q_type": "mcq_single",
        "text": text,
        "options": options,
        "answer": answer,
        "solution": solution,
        "difficulty_target": difficulty,
        "params": params,           # used by tests to recompute the answer independently
        "answer_value": fmt(correct),
        "answer_verified": True,    # computed exactly by the generator; re-checked in tests
        "reviewers": [],            # S1 gate: two distinct human reviewers required
        "review_status": "pending",
        "provenance": {
            "source_id": "original_reviewed",
            "rights_record": f"template generator {GENERATOR_VERSION}, seed {SEED}; original text, no third-party source",
        },
    }


def poly(a: int, b: int, c: int) -> str:
    """Readable quadratic a x^2 + b x + c with signs, e.g. '3x^2 - 6x + 0'."""
    def term(coef, rest):
        sign = "-" if coef < 0 else "+"
        mag = abs(coef)
        body = rest if mag == 1 and rest else f"{mag}{rest}"
        return sign, body
    s = ("" if a == 1 else f"{a}") + "x^2"
    sg, body = term(b, "x")
    s += f" {sg} {body}"
    s += f" {'-' if c < 0 else '+'} {abs(c)}"
    return s


def _fresh_pair(rng: random.Random, seen: set) -> tuple[int, int]:
    """Draw a root pair not used before, so no two items share a question text."""
    while True:
        pair = (rng.randint(-5, 5), rng.randint(-5, 5))
        if pair not in seen:
            seen.add(pair)
            return pair


def build() -> list[dict]:
    """Draw each item until its question text is new (no duplicate question across the bank)."""
    rng = random.Random(SEED)
    items: list[dict] = []
    seen_texts: set[str] = set()

    def add(count: int, make) -> None:
        added = 0
        while added < count:
            cand = make(len(items) + 1)
            if cand["text"] in seen_texts:
                continue
            seen_texts.add(cand["text"])
            items.append(cand)
            added += 1

    # --- A: algebra of complex numbers (20 items) ---
    def mod2(idx):
        a, b = rng.randint(1, 9), rng.randint(1, 9) * rng.choice([1, -1])
        c = Fraction(a * a + b * b)
        return item(idx, A, f"If z = {complex_text(a, b)}, find |z|^2.", c,
                    [Fraction(a * a - b * b), Fraction(a + b) ** 2, c + 2],
                    {"op": "mod2", "a": a, "b": b},
                    f"|z|^2 = a^2 + b^2 = {a*a} + {b*b} = {a*a+b*b}.", "easy", rng)

    def re_inv(idx):
        a, b = rng.randint(1, 7), rng.randint(1, 7) * rng.choice([1, -1])
        n = a * a + b * b
        c = Fraction(a, n)
        return item(idx, A, f"For z = {complex_text(a, b)}, find the real part of 1/z.", c,
                    [Fraction(b, n), Fraction(a, 1), Fraction(-a, n)],
                    {"op": "re_inv", "a": a, "b": b},
                    f"1/z = conj(z)/|z|^2, so Re(1/z) = a/(a^2+b^2) = {a}/{n}.", "medium", rng)

    def im_conj(idx):
        a, b = rng.randint(1, 6), rng.randint(1, 6) * rng.choice([1, -1])
        c_, d = rng.randint(1, 6), rng.randint(1, 6) * rng.choice([1, -1])
        val = a * d - b * c_
        return item(idx, A, f"Let z = {complex_text(a, b)} and w = {complex_text(c_, d)}. "
                            f"Find the imaginary part of conj(z)·w.", Fraction(val),
                    [Fraction(a * c_ + b * d), Fraction(-val), Fraction(val + 2 * b)],
                    {"op": "im_conj_prod", "a": a, "b": b, "c": c_, "d": d},
                    f"conj(z)·w = (ac+bd) + (ad-bc)i, so Im = ad - bc = {val}.", "medium", rng)

    def re_sq(idx):
        a, b = rng.randint(1, 8), rng.randint(1, 8) * rng.choice([1, -1])
        val = a * a - b * b
        return item(idx, A, f"Find the real part of ({complex_text(a, b)})^2.", Fraction(val),
                    [Fraction(a * a + b * b), Fraction(2 * a * b), Fraction(-val)],
                    {"op": "re_sq", "a": a, "b": b},
                    f"(a+bi)^2 = (a^2-b^2) + 2abi, so Re = {a*a} - {b*b} = {val}.", "easy", rng)

    add(5, mod2); add(5, re_inv); add(5, im_conj); add(5, re_sq)

    # --- R: nature of roots and discriminant (20 items) ---
    def disc(idx):
        a, b, c = rng.randint(1, 5), rng.randint(-6, 6), rng.randint(-6, 6)
        val = b * b - 4 * a * c
        return item(idx, R, f"Find the discriminant of {poly(a, b, c)} = 0.", Fraction(val),
                    [Fraction(b * b + 4 * a * c), Fraction(-b * b), Fraction(b * b - 2 * a * c)],
                    {"op": "disc", "a": a, "b": b, "c": c},
                    f"D = b^2 - 4ac = {b*b} - 4({a})({c}) = {val}.", "easy", rng)

    def nature(idx):
        a, b, c = rng.randint(1, 4), rng.randint(-6, 6), rng.randint(-6, 6)
        d_ = b * b - 4 * a * c
        code = 2 if d_ > 0 else (1 if d_ == 0 else 0)
        return item(idx, R, f"For {poly(a, b, c)} = 0, how many distinct real roots exist? "
                            f"(Answer as a number.)", Fraction(code),
                    [Fraction(3), Fraction(0 if code != 0 else 2), Fraction(code + 1 if code < 2 else 1)],
                    {"op": "nature", "a": a, "b": b, "c": c},
                    f"D = {d_}: " + ("two distinct real roots." if d_ > 0 else
                                     "one repeated real root." if d_ == 0 else "no real roots."),
                    "medium", rng)

    def equal_roots(idx):
        m = rng.randint(1, 6)
        q = m * m
        return item(idx, R, f"For x^2 + px + {q} = 0, find the positive value of p for which the roots are equal.",
                    Fraction(2 * m), [Fraction(m), Fraction(4 * m), Fraction(m * m)],
                    {"op": "equal_roots", "m": m},
                    f"Equal roots need p^2 = 4q = {4*q}, so p = {2*m}.", "medium", rng)

    def sum_roots(idx):
        a, b = rng.randint(2, 7), rng.randint(-9, 9)
        val = Fraction(-b, a)
        return item(idx, R, f"What is the sum of the roots of {poly(a, b, 5)} = 0?", val,
                    [Fraction(b, a), Fraction(-5, a), Fraction(5, a)],
                    {"op": "sum_roots", "a": a, "b": b},
                    f"Sum of roots = -b/a = {fmt(val)}.", "easy", rng)

    add(5, disc); add(5, nature); add(5, equal_roots); add(5, sum_roots)

    # --- F: formation of quadratic equations from roots (20 items) ---
    seen_pairs: set[tuple[int, int]] = set()

    def coef_x(idx):
        al, be = _fresh_pair(rng, seen_pairs)
        val = Fraction(-(al + be))
        return item(idx, F, f"A quadratic equation has roots {al} and {be}. "
                            f"If it is written as x^2 + Bx + C = 0, find B.", val,
                    [Fraction(al + be), Fraction(al * be), Fraction(-al * be)],
                    {"op": "coef_x", "al": al, "be": be},
                    f"x^2 - (sum)x + product, so B = -(sum) = {fmt(val)}.", "easy", rng)

    def const(idx):
        al, be = _fresh_pair(rng, seen_pairs)
        val = Fraction(al * be)
        return item(idx, F, f"A quadratic equation has roots {al} and {be}. "
                            f"If it is written as x^2 + Bx + C = 0, find C.", val,
                    [Fraction(-al * be), Fraction(al + be), Fraction(-(al + be))],
                    {"op": "const", "al": al, "be": be},
                    f"C = product of roots = {al} x {be} = {fmt(val)}.", "easy", rng)

    add(10, coef_x); add(10, const)
    return items


def main() -> None:
    items = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"generator": GENERATOR_VERSION, "seed": SEED, "count": len(items),
                "concepts": {A: 20, R: 20, F: 20}, "status": "draft; review pending"}
    OUT.write_text(json.dumps({"manifest": manifest, "items": items}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"wrote {len(items)} items to {OUT}")


if __name__ == "__main__":
    main()
