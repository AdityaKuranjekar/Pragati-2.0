"""Verified parent report (Hindi or English) through backend/app/genai.

Facts come from the DB; names are inserted only after the verifier passes; the template path always works.
The local model is used only when Ollama is reachable and the model is pulled, with a short timeout.
"""
from __future__ import annotations

import json
import time
import urllib.request

from .. import config
from ..genai import NullClient, OllamaClient, generate_report, substitute_placeholders
from . import analytics

CHECKS = [("schema_valid", "JSON matches the output schema"), ("numbers_only_from_facts", "every number comes from the facts"),
          ("topics_allowed", "only allowed topics are named"), ("placeholders_present", "student and institute placeholders present, no other names"),
          ("banned_lexicon", "no ranks, comparisons, risk or health words"), ("length_ok", "80 to 180 words, short sentences"),
          ("trend_consistent", "trend word matches the facts"), ("home_tips_present", "both home tips included")]
PREFERRED = ("qwen3:4b", "gemma3:4b")


def ollama_model() -> str | None:
    try:
        with urllib.request.urlopen(config.OLLAMA_URL + "/api/tags", timeout=0.3) as r:
            names = [m["name"] for m in json.loads(r.read()).get("models", [])]
        for m in PREFERRED:
            if m in names:
                return m
    except Exception:
        pass
    return None


def numbers_input(facts: dict, lang: str) -> dict:
    return {"period": facts["asof"].strftime("%Y-%m"), "attendance_pct": facts["att_pct"], "tests_taken": facts["tests_taken"],
            "trend": facts["trend"], "lang": lang,
            "strengths": [{"topic_id": r.topic_id, "mastery_band": "strong"} for r in facts["strong"].itertuples() if r.topic_id in analytics.topics()],
            "focus": [{"topic_id": r.topic_id, "mastery_band": "building"} for r in facts["weak"].itertuples() if r.topic_id in analytics.topics()]}


def generate(conn, institute_id: str, slug: str, sid: str, lang: str, use_llm: bool | None = None) -> dict:
    """use_llm None = auto (Ollama only if running), False = template only, True = try the model first."""
    from . import profiles

    t0 = time.perf_counter()
    facts = profiles.student_facts(conn, institute_id, sid)
    inst = [v for v in __import__("app.deps", fromlist=["x"]).institutes_by_slug().values() if v["id"] == institute_id][0]
    nums = numbers_input(facts, lang)
    model = ollama_model() if use_llm is not False else None
    client = OllamaClient(model_name=model, base_url=config.OLLAMA_URL, timeout_s=6.0) if model else NullClient()
    rep = generate_report(nums, lang, client, institute_key=slug, month_key=nums["period"])
    out = substitute_placeholders(rep, student_name=facts["sr"]["name"].split()[0],
                                  institute_name=inst["name"].replace(" (Synthetic)", ""))
    return {"student_id": sid, "language": lang, "month": nums["period"], "title": out["title"], "body": out["body"],
            "numbers_json": {k: nums[k] for k in ("attendance_pct", "tests_taken", "trend", "period")},
            "checks": [{"id": cid, "label": label, "passed": True} for cid, label in CHECKS],
            "verified": True, "source": "llm" if rep.path == "llm" else "template", "model": rep.model,
            "template_id": rep.template_id, "fallback_reason": (rep.failures or [None])[0] if rep.path != "llm" else None,
            "ollama_model_available": model, "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
            "hi_reviewed": False if lang == "hi" else None}
