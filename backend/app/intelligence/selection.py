"""Item selection (USP row 3). Pure Python, deterministic, no database, no LLM, no timing data.

Difficulty scale (ordinal, documented, not a calibrated IRT parameter):
    easy = 1, medium = 2, hard = 3.
The bank labels are `difficulty_target`, an author's intent, not a measured difficulty. Replace this
scale with calibrated item parameters only after E1/E3 support it.

What the module does for one learner and one concept:
  1. Guided entry: if the learner's estimate on the concept is below 0.5 when practice starts, the
     ladder starts one band under the target; otherwise at the target.
  2. The ladder (challenge.py) moves the level after evidence: up after 3 correct in a row, down after
     2 wrong in a row, never above the target, never below target - 1.
  3. The item is the first unanswered item at that level, in item_id order (deterministic). An item the
     learner has already answered is never offered again.
  4. If the level has no unanswered item, it looks upward toward the target first, then downward to the
     floor. If nothing at or above the floor exists, it returns the nearest level and sets
     `bank_gap` so a thin bank is visible rather than hidden.
  5. Only items with status "approved" are served. `allow_unapproved_demo=True` serves draft items for
     demos and the flag is echoed in the output (`demo_unapproved_allowed`) and in the trace.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

from .challenge import floor_for, ladder

DIFFICULTY_SCALE: Mapping[str, int] = {"easy": 1, "medium": 2, "hard": 3}
LEVEL_NAMES = {v: k for k, v in DIFFICULTY_SCALE.items()}
GUIDED_ENTRY_BELOW = 0.5      # p_known below this: start one band under the target
STUCK_AFTER = 6               # answers at the floor with no rise: flag the lock-in risk
APPROVED = "approved"


@dataclass(frozen=True)
class BankItem:
    item_id: str
    topic_id: str
    difficulty_target: str
    status: str

    @property
    def level(self) -> int:
        return DIFFICULTY_SCALE[self.difficulty_target]


def bank_from_records(records: Iterable[Mapping]) -> list[BankItem]:
    """Accepts bank records with `item_id` or `id`, and `status` or `review_status`."""
    out = []
    for r in records:
        item_id = r.get("item_id", r.get("id"))
        status = r.get("status", r.get("review_status"))
        diff = r.get("difficulty_target")
        if not isinstance(item_id, str) or not item_id:
            raise ValueError("bank record needs item_id (or id)")
        if diff not in DIFFICULTY_SCALE:
            raise ValueError(f"unknown difficulty_target {diff!r} on {item_id}")
        if not isinstance(r.get("topic_id"), str):
            raise ValueError(f"bank record {item_id} needs topic_id")
        out.append(BankItem(item_id, r["topic_id"], diff, str(status)))
    ids = [b.item_id for b in out]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate item_id in bank")
    return out


def level_of(name: str) -> int:
    if name not in DIFFICULTY_SCALE:
        raise ValueError(f"unknown difficulty {name!r}; expected one of {sorted(DIFFICULTY_SCALE)}")
    return DIFFICULTY_SCALE[name]


def entry_level(p_known: float, target: int) -> int:
    """Guided entry: one band under the target when p_known < 0.5, never below the floor."""
    if p_known < GUIDED_ENTRY_BELOW:
        return max(floor_for(target), target - 1)
    return target


@dataclass(frozen=True)
class Selection:
    item_id: str | None
    concept_id: str
    level: int
    level_name: str
    served_level_name: str | None
    reason: str
    demo_unapproved_allowed: bool
    item_status: str | None
    bank_gap: bool
    trace: dict = field(default_factory=dict)


def select_item(bank: Sequence[BankItem], concept_id: str, p_known: float,
                history: Sequence[tuple[str, bool]], target: str, *,
                entry_p_known: float | None = None,
                allow_unapproved_demo: bool = False,
                k: int = 3, m: int = 2) -> Selection:
    """history: this learner's (item_id, correct) answers on this concept, oldest first.
    entry_p_known: the estimate when practice on the concept started (defaults to p_known, which is
    right for the first item). Passing it keeps guided entry stable as the estimate moves."""
    target_level = level_of(target)
    entry_p = p_known if entry_p_known is None else entry_p_known
    start = entry_level(entry_p, target_level)
    res = ladder([c for _, c in history], start, target_level, k=k, m=m)
    answered = {i for i, _ in history}
    allowed_status = None if allow_unapproved_demo else {APPROVED}

    pool = [b for b in bank if b.topic_id == concept_id
            and (allowed_status is None or b.status in allowed_status)]
    fresh = sorted((b for b in pool if b.item_id not in answered), key=lambda b: b.item_id)
    by_level: dict[int, list[BankItem]] = {}
    for b in fresh:
        by_level.setdefault(b.level, []).append(b)

    # Search order: the ladder level, then upward to the target, then downward to the floor,
    # then (bank gap) whatever is nearest.
    order = [res.level] + list(range(res.level + 1, res.target + 1)) + \
        list(range(res.level - 1, res.floor - 1, -1))
    chosen, bank_gap = None, False
    for lv in order:
        if by_level.get(lv):
            chosen = by_level[lv][0]
            break
    if chosen is None and fresh:
        chosen = min(fresh, key=lambda b: (abs(b.level - res.level), -b.level, b.item_id))
        bank_gap = True
    if chosen is not None and chosen.level != res.level:
        bank_gap = True

    trace = {
        "p_known": p_known, "entry_p_known": entry_p, "target": target,
        "entry_level": LEVEL_NAMES[start], "ladder_level": LEVEL_NAMES[res.level],
        "floor": LEVEL_NAMES[res.floor], "correct_run": res.correct_run, "wrong_run": res.wrong_run,
        "ladder_changes": [{"after_answer": i, "move": mv, "to": LEVEL_NAMES[lv]}
                           for i, mv, lv in res.changes],
        "answered_on_concept": len(history), "candidates_unanswered": len(fresh),
        "approved_in_pool": sum(1 for b in pool if b.status == APPROVED),
        "demo_unapproved_allowed": allow_unapproved_demo, "bank_gap": bank_gap,
        "k": k, "m": m,
    }
    # lock-in signal: many answers at the floor, below target, with no rise.
    answers_since_change = len(history) - (res.changes[-1][0] + 1 if res.changes else 0)
    stuck = res.level == res.floor < res.target and answers_since_change >= STUCK_AFTER
    trace["stuck_at_floor"] = stuck

    if chosen is None:
        why = ("No unanswered approved items for this concept."
               if not allow_unapproved_demo else "No unanswered items for this concept.")
        return Selection(None, concept_id, res.level, LEVEL_NAMES[res.level], None, why,
                         allow_unapproved_demo, None, True, trace)

    parts = []
    if not history:
        if entry_p < GUIDED_ENTRY_BELOW and start < target_level:
            parts.append(f"Guided entry: the estimate on this concept is {entry_p:.0%} (below "
                         f"{GUIDED_ENTRY_BELOW:.0%}), so practice starts one band under the target "
                         f"({LEVEL_NAMES[target_level]}): {LEVEL_NAMES[start]}.")
        else:
            parts.append(f"Starting at the target band ({LEVEL_NAMES[target_level]}); the estimate "
                         f"is {entry_p:.0%}.")
    else:
        if res.changes:
            i, mv, lv = res.changes[-1]
            why = (f"last {k} answers at the previous band were correct" if mv == "raise"
                   else f"{m} wrong answers in a row")
            parts.append(f"Band is {LEVEL_NAMES[res.level]} ({mv} to {LEVEL_NAMES[lv]} after {why}).")
        else:
            parts.append(f"Band holds at {LEVEL_NAMES[res.level]}: {res.correct_run} correct and "
                         f"{res.wrong_run} wrong in the current run (a raise needs {k} correct in a "
                         f"row, a drop needs {m} wrong in a row).")
    if chosen.level != res.level:
        parts.append(f"No unanswered {LEVEL_NAMES[res.level]} item is available, so a "
                     f"{LEVEL_NAMES[chosen.level]} item is used (bank gap).")
    if res.level < res.target:
        parts.append(f"Target band is {LEVEL_NAMES[res.target]}; the next band up needs {k} correct in a row.")
    if stuck:
        parts.append("Many answers at this band without a rise: reviewing a prerequisite may help more "
                     "than more items here.")
    if chosen.status != APPROVED:
        parts.append(f"DEMO ONLY: this item is '{chosen.status}', not approved, and shown because the "
                     f"demo flag is set.")
    parts.append(f"Item {chosen.item_id} has not been answered before.")
    return Selection(chosen.item_id, concept_id, res.level, LEVEL_NAMES[res.level],
                     LEVEL_NAMES[chosen.level], " ".join(parts), allow_unapproved_demo,
                     chosen.status, bank_gap, trace)
