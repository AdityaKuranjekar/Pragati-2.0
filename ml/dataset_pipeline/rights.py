"""Rights gate for JEE content and interaction data.

Every use of a source passes through `require(source_id, purpose)`. It raises PermissionError
unless sources.yaml allows that purpose for that source. Items that reach learners must also
pass `validate_item`, which checks provenance, answer verification and two human reviewers.

Run from the repository root:  python -m pytest ml/dataset_pipeline/tests -q
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REGISTER_PATH = Path(__file__).with_name("sources.yaml")
PURPOSES = {"student_facing_item", "benchmark_eval", "server_side_model", "reference"}


class RightsError(PermissionError):
    """Raised when a source is used for a purpose its register entry does not allow."""


@dataclass(frozen=True)
class Source:
    id: str
    status: str
    allowed_purposes: frozenset[str]
    rights_evidence: str


@dataclass
class Register:
    sources: dict[str, Source] = field(default_factory=dict)

    def get(self, source_id: str) -> Source:
        try:
            return self.sources[source_id]
        except KeyError:
            raise RightsError(f"source '{source_id}' is not in the register") from None

    def allows(self, source_id: str, purpose: str) -> bool:
        if purpose not in PURPOSES:
            raise ValueError(f"unknown purpose '{purpose}'")
        src = self.get(source_id)
        return purpose in src.allowed_purposes and src.status not in {"pending", "blocked"}

    def require(self, source_id: str, purpose: str) -> Source:
        if not self.allows(source_id, purpose):
            src = self.get(source_id)
            raise RightsError(
                f"source '{source_id}' (status {src.status}) is not cleared for '{purpose}'"
            )
        return self.get(source_id)


def load_register(path: Path = REGISTER_PATH) -> Register:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    reg = Register()
    for entry in data["sources"]:
        sid = entry["id"]
        if sid in reg.sources:
            raise ValueError(f"duplicate source id '{sid}'")
        purposes = frozenset(entry.get("allowed_purposes") or [])
        unknown = purposes - PURPOSES
        if unknown:
            raise ValueError(f"source '{sid}' lists unknown purposes {sorted(unknown)}")
        reg.sources[sid] = Source(
            id=sid,
            status=entry["status"],
            allowed_purposes=purposes,
            rights_evidence=entry.get("rights_evidence", ""),
        )
    return reg


REQUIRED_ITEM_FIELDS = ("id", "subject", "class_level", "topic_id", "q_type", "text", "answer", "provenance")


def validate_item(item: dict[str, Any], register: Register) -> list[str]:
    """Return a list of problems. An empty list means the item may be shown to learners."""
    problems = [f"missing field '{f}'" for f in REQUIRED_ITEM_FIELDS if not item.get(f)]
    if problems:
        return problems
    prov = item["provenance"]
    source_id = prov.get("source_id")
    if not source_id:
        return ["provenance.source_id missing"]
    try:
        register.require(source_id, "student_facing_item")
    except RightsError as exc:
        problems.append(str(exc))
    if not prov.get("rights_record"):
        problems.append("provenance.rights_record missing")
    if not item.get("answer_verified"):
        problems.append("answer not verified (answer_verified must be true)")
    reviewers = item.get("reviewers") or []
    if len({r for r in reviewers if r}) < 2:
        problems.append("needs two distinct human reviewers")
    if item.get("topic_id") and not str(item["topic_id"]).startswith(("jee.", "neet.")):
        problems.append("topic_id is not a known taxonomy prefix")
    return problems
