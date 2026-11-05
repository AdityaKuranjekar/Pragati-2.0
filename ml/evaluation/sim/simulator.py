"""Learner simulator [SIM]. Independent of the estimator: no import from backend/app/intelligence.

What it generates
  * A prerequisite DAG of 8 synthetic concepts (c0..c7), goal c7.
  * Learners with latent binary mastery per concept. A concept can start mastered only if all its
    prerequisites are mastered (generated in topological order), so initial states respect the graph.
  * Responses: a mastered concept is answered correctly with probability 1 - SLIP (0.10); an unmastered
    one with probability GUESS (0.25, a 4-option item). Item difficulty does not change correctness.
  * Learning: after each answer on an unmastered concept the learner may become mastered.
      neutral model: probability P_LEARN (0.15) if every prerequisite is mastered, else P_LEARN_UNREADY (0.02).
      zone model (an ASSUMPTION about difficulty, labelled as such): the probability above is multiplied by
        1.0 / 0.5 / 0.2 when the served band is 0 / 1 / 2 bands away from the learner's latent readiness band.
  * Forgetting: at each day boundary a mastered concept is forgotten with probability FORGET_PER_DAY.
  * Common random numbers: the initial learner and the response stream depend only on (seed, learner index),
    so every path faces the same learners; paths differ only in what they serve.

Every constant is an assumption of the simulation, not a measurement of any real learner.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

GUESS = 0.25
SLIP = 0.10
ZONE_FACTORS = (1.0, 0.5, 0.2)        # |served band - readiness band| = 0, 1, >=2
SIM_NODES = tuple(f"c{i}" for i in range(8))
SIM_EDGES = (("c0", "c1"), ("c1", "c2"), ("c0", "c3"), ("c3", "c4"),
             ("c2", "c5"), ("c4", "c5"), ("c5", "c6"), ("c6", "c7"))
SIM_GOAL = "c7"
LEVELS = ("easy", "medium", "hard")


@dataclass(frozen=True)
class SimConfig:
    n_learners: int = 500
    seed: int = 2026110501
    budget: int = 60                 # items each path may serve
    items_per_day: int = 4
    forget_per_day: float = 0.01
    p_learn: float = 0.15
    p_learn_unready: float = 0.02
    learning_model: str = "neutral"  # neutral | zone
    base_logit: float = -0.5         # starting mastery: sigmoid(theta + base_logit) when prerequisites are mastered
    readiness_probs: tuple = (0.4, 0.4, 0.2)
    bank_per_level: int = 14

    def __post_init__(self):
        if self.learning_model not in ("neutral", "zone"):
            raise ValueError("learning_model must be neutral or zone")
        if self.budget < 1 or self.items_per_day < 1:
            raise ValueError("budget and items_per_day must be positive")


def prereq_map() -> dict[str, tuple[str, ...]]:
    return {n: tuple(p for p, d in SIM_EDGES if d == n) for n in SIM_NODES}


def make_bank(per_level: int = 14) -> list[dict]:
    """A synthetic item bank, plain dicts (item_id, topic_id, difficulty_target, status). The status
    'approved' here is a property of simulated items only; it says nothing about the demo bank."""
    return [{"item_id": f"{c}-{lv[0]}{i:02d}", "topic_id": c, "difficulty_target": lv, "status": "approved"}
            for c in SIM_NODES for lv in LEVELS for i in range(per_level)]


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


class SimLearner:
    def __init__(self, idx: int, cfg: SimConfig):
        self.idx, self.cfg = idx, cfg
        self._pre = prereq_map()
        init = random.Random(f"{cfg.seed}:{idx}:init")
        theta = init.gauss(0.0, 1.0)
        self.mastered: dict[str, bool] = {}
        for n in SIM_NODES:    # SIM_NODES is in topological order by construction
            ready = all(self.mastered[p] for p in self._pre[n])
            self.mastered[n] = ready and init.random() < _sigmoid(theta + cfg.base_logit)
        self.readiness = {n: 1 + _categorical(init, cfg.readiness_probs) for n in SIM_NODES}
        self.initial_mastered = dict(self.mastered)
        self._rng = random.Random(f"{cfg.seed}:{idx}:resp")

    def violates(self, concept: str) -> bool:
        """True if the concept has a prerequisite the learner has not truly mastered."""
        return any(not self.mastered[p] for p in self._pre[concept])

    def respond(self, concept: str, band: int) -> bool:
        """Answer one item on `concept` served at band 1..3. Returns correctness, then applies learning."""
        m = self.mastered[concept]
        correct = self._rng.random() < ((1.0 - SLIP) if m else GUESS)
        if not m:
            p = self.cfg.p_learn_unready if self.violates(concept) else self.cfg.p_learn
            if self.cfg.learning_model == "zone":
                p *= ZONE_FACTORS[min(2, abs(band - self.readiness[concept]))]
            if self._rng.random() < p:
                self.mastered[concept] = True
        return correct

    def end_day(self) -> None:
        for n in SIM_NODES:
            if self.mastered[n] and self._rng.random() < self.cfg.forget_per_day:
                self.mastered[n] = False

    @property
    def mastered_count(self) -> int:
        return sum(self.mastered.values())

    @property
    def goal_mastered(self) -> bool:
        return self.mastered[SIM_GOAL]


def _categorical(rng: random.Random, probs) -> int:
    u, acc = rng.random(), 0.0
    for i, p in enumerate(probs):
        acc += p
        if u < acc:
            return i
    return len(probs) - 1
