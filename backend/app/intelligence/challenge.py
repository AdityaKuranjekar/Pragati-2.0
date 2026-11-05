"""Challenge ladder (USP row 4). Pure Python, deterministic, no timing data.

Rule, stated exactly:
  * Raise the difficulty one band only when the last K = 3 answers on the concept are ALL correct.
    One correct answer never raises it. A run that restarts after a change must be re-earned.
  * Lower the difficulty one band after M = 2 wrong answers in a row.
  * Anything else holds the level (contradictory runs such as right, wrong, right hold).
  * The level never goes above the target band and never below the floor (target - 1, at least 1).

"Last K answers" are counted since the most recent level change, so evidence gathered at one level is
not reused as evidence for the next. This is stricter than counting any 3 recent answers and is meant
to be: a raise should be supported by 3 answers at the level being left.

K and M are policy parameters, not facts about learning. Three correct answers in a row by pure guessing on
a 4-option item has probability 0.25^3 = 1.6%, which is why K = 3 is the minimum used here.
Nothing here is fitted to data.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

RAISE_AFTER = 3   # k: consecutive correct answers at the current level needed to raise
LOWER_AFTER = 2   # m: consecutive wrong answers that lower the level


@dataclass(frozen=True)
class LadderResult:
    level: int                 # 1 easy, 2 medium, 3 hard (see selection.DIFFICULTY_SCALE)
    floor: int
    target: int
    correct_run: int           # consecutive correct answers at the current level
    wrong_run: int             # consecutive wrong answers at the current level
    changes: tuple             # ((answer_index, "raise"|"lower", new_level), ...)

    @property
    def at_target(self) -> bool:
        return self.level >= self.target


def floor_for(target: int) -> int:
    """One band under the target, never below 1. A hard target never falls to easy-only practice."""
    return max(1, target - 1)


def ladder(correct_history: Sequence[bool], entry_level: int, target: int, *,
           k: int = RAISE_AFTER, m: int = LOWER_AFTER) -> LadderResult:
    if k < 2:
        raise ValueError("k must be at least 2: a single correct answer must never raise difficulty")
    if m < 1:
        raise ValueError("m must be at least 1")
    if target < 1:
        raise ValueError("target must be at least 1")
    floor = floor_for(target)
    level = min(max(entry_level, floor), target)
    correct_run = wrong_run = 0
    changes = []
    for i, ok in enumerate(correct_history):
        if not isinstance(ok, bool):
            raise ValueError("history must hold booleans")
        if ok:
            correct_run, wrong_run = correct_run + 1, 0
        else:
            wrong_run, correct_run = wrong_run + 1, 0
        if correct_run >= k and level < target:
            level += 1
            correct_run = wrong_run = 0
            changes.append((i, "raise", level))
        elif wrong_run >= m and level > floor:
            level -= 1
            correct_run = wrong_run = 0
            changes.append((i, "lower", level))
    return LadderResult(level, floor, target, correct_run, wrong_run, tuple(changes))
