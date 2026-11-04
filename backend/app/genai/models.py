# Purpose: Data structures and contract loaders for the GenAI verified parent-report layer.
# contract_version: 1.0.0
# Implements: TECH_PLAN §11 (GenAI layer) and R1_E_genai_reports.md.

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml

GENAI_DIR = Path(__file__).resolve().parent
REPO_ROOT = GENAI_DIR.parents[2]
CONTRACTS_DIR = REPO_ROOT / "contracts"
TEMPLATES_DIR = REPO_ROOT / "backend" / "templates"
PROMPTS_DIR = GENAI_DIR / "prompts"

Lang = Literal["en", "hi"]
Trend = Literal["improving", "steady", "declining"]
MasteryBand = Literal["not_enough_data", "building", "steady", "strong"]
ReportPath = Literal["llm", "template"]

ALLOWED_HOME_TIPS: tuple[str, ...] = (
    "tip_fixed_revision_slot",
    "tip_mistake_notebook_review",
    "tip_sleep_and_rest_day",
    "tip_formula_flashcards",
    "tip_timed_practice_set",
    "tip_ask_faculty_doubts",
    "tip_regular_class_attendance",
    "tip_encourage_steady_effort",
)


@lru_cache(maxsize=1)
def load_report_numbers_schema() -> dict[str, Any]:
    path = CONTRACTS_DIR / "report_numbers.schema.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def get_report_numbers_validator() -> Any:
    import jsonschema

    return jsonschema.Draft202012Validator(load_report_numbers_schema())


@lru_cache(maxsize=1)
def load_report_output_schema() -> dict[str, Any]:
    path = CONTRACTS_DIR / "report_output.schema.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def get_report_output_validator() -> Any:
    import jsonschema

    return jsonschema.Draft202012Validator(load_report_output_schema())


@lru_cache(maxsize=1)
def load_reason_templates_contract() -> dict[str, Any]:
    path = CONTRACTS_DIR / "reason_templates.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def load_topics_contract() -> dict[str, dict[str, Any]]:
    path = CONTRACTS_DIR / "topics.yaml"
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    return {t["id"]: t for t in doc["topics"]}


@dataclass(frozen=True)
class TopicItem:
    topic_id: str
    name_en: str
    name_hi: str
    mastery_band: MasteryBand

    def to_dict(self) -> dict[str, str]:
        return {
            "topic_id": self.topic_id,
            "name_en": self.name_en,
            "name_hi": self.name_hi,
            "mastery_band": self.mastery_band,
        }


@dataclass(frozen=True)
class NumbersJson:
    period: str
    lang: Lang
    attendance_pct: float
    tests_taken: int
    trend: Trend
    strengths: tuple[TopicItem, ...]
    focus: tuple[TopicItem, ...]
    home_tips: tuple[str, str]
    contract_version: str = "1.0.0"
    student_placeholder: str = "{STUDENT}"
    institute_placeholder: str = "{INSTITUTE}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "period": self.period,
            "lang": self.lang,
            "student_placeholder": self.student_placeholder,
            "institute_placeholder": self.institute_placeholder,
            "attendance_pct": float(self.attendance_pct),
            "tests_taken": int(self.tests_taken),
            "trend": self.trend,
            "strengths": [s.to_dict() for s in self.strengths],
            "focus": [f.to_dict() for f in self.focus],
            "home_tips": list(self.home_tips),
        }

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NumbersJson:
        strengths = tuple(
            TopicItem(
                topic_id=t["topic_id"],
                name_en=t["name_en"],
                name_hi=t["name_hi"],
                mastery_band=t["mastery_band"],
            )
            for t in data.get("strengths", [])
        )
        focus = tuple(
            TopicItem(
                topic_id=t["topic_id"],
                name_en=t["name_en"],
                name_hi=t["name_hi"],
                mastery_band=t["mastery_band"],
            )
            for t in data.get("focus", [])
        )
        tips = data.get("home_tips", [])
        if len(tips) != 2:
            raise ValueError(f"Expected exactly 2 home_tips, got {len(tips)}")
        return cls(
            contract_version=data.get("contract_version", "1.0.0"),
            period=str(data["period"]),
            lang=data["lang"],
            student_placeholder=data.get("student_placeholder", "{STUDENT}"),
            institute_placeholder=data.get("institute_placeholder", "{INSTITUTE}"),
            attendance_pct=float(data["attendance_pct"]),
            tests_taken=int(data["tests_taken"]),
            trend=data["trend"],
            strengths=strengths,
            focus=focus,
            home_tips=(str(tips[0]), str(tips[1])),
        )


@dataclass(frozen=True)
class Prompt:
    system: str
    user: str
    lang: Lang
    prompt_version: str
    output_schema: dict[str, Any]


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    failures: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Report:
    content: dict[str, Any]
    path: ReportPath
    verified: Literal[True]
    model: str
    latency_ms: float
    tokens_in: int
    tokens_out: int
    cost_inr: float
    failures: list[str] = field(default_factory=list)
    template_id: str | None = None
    cache_hit: bool = False
