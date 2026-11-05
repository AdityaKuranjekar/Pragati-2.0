"""Attempt events (ADR-003). v0 accepts correctness only: no response time, no hint fields.

Minor-safety: any field outside ALLOWED_FIELDS is rejected, so response-time or hint data cannot
enter the engine by accident (BLOCKERS B1, B16).
"""
from __future__ import annotations

from dataclasses import dataclass

ALLOWED_FIELDS = frozenset({"event_id", "learner_id", "concept_id", "item_id", "correct", "seq"})


@dataclass(frozen=True)
class AttemptEvent:
    event_id: str      # idempotency key, unique per tenant
    learner_id: str
    concept_id: str
    item_id: str
    correct: bool
    seq: int           # server-assigned order within a learner (ties not allowed)


def parse_event(raw: dict) -> AttemptEvent:
    if not isinstance(raw, dict):
        raise ValueError("event must be an object")
    extra = set(raw) - ALLOWED_FIELDS
    if extra:
        raise ValueError(f"fields not allowed in v0: {sorted(extra)}")
    missing = ALLOWED_FIELDS - set(raw)
    if missing:
        raise ValueError(f"missing fields: {sorted(missing)}")
    for key in ("event_id", "learner_id", "concept_id", "item_id"):
        if not isinstance(raw[key], str) or not raw[key].strip():
            raise ValueError(f"{key} must be a non-empty string")
    if not isinstance(raw["correct"], bool):
        raise ValueError("correct must be a boolean")
    if not isinstance(raw["seq"], int) or isinstance(raw["seq"], bool) or raw["seq"] < 0:
        raise ValueError("seq must be a non-negative integer")
    return AttemptEvent(
        event_id=raw["event_id"],
        learner_id=raw["learner_id"],
        concept_id=raw["concept_id"],
        item_id=raw["item_id"],
        correct=raw["correct"],
        seq=raw["seq"],
    )
