# Purpose: End-to-end GenAI parent report pipeline (`build_numbers`, `render_prompt`, `generate_report`, template engine, PDF export).
# contract_version: 1.0.0
# Implements: TECH_PLAN §11 (GenAI layer) and R1_E_genai_reports.md #1, #2, #5, #6.

from __future__ import annotations

import hashlib
import io
import json
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

import jinja2
import jsonschema

from .clients import LLMClient, LLMClientError, NullClient
from .cost import CostMeter
from .models import (
    ALLOWED_HOME_TIPS,
    PROMPTS_DIR,
    TEMPLATES_DIR,
    Lang,
    NumbersJson,
    Prompt,
    Report,
    TopicItem,
    get_report_numbers_validator,
    load_report_numbers_schema,
    load_report_output_schema,
    load_topics_contract,
)
from .verifier import verify

PROMPT_VERSION = "1.0.0"

# Bilingual phrasing catalog for the 8 contract-defined home_tips
HOME_TIPS_CATALOG: dict[str, dict[str, str]] = {
    "tip_fixed_revision_slot": {
        "en": "keep a fixed daily revision slot at a quiet desk",
        "hi": "प्रतिदिन एक शांत स्थान पर निश्चित दोहराव समय निर्धारित करें",
    },
    "tip_mistake_notebook_review": {
        "en": "review the mistake notebook before every practice test",
        "hi": "प्रत्येक अभ्यास टेस्ट से पहले अपनी गलती नोटबुक का पुनरावलोकन करें",
    },
    "tip_sleep_and_rest_day": {
        "en": "ensure adequate nightly sleep and a calm weekly rest day",
        "hi": "पर्याप्त नींद और साप्ताहिक विश्राम दिवस का पूरा ध्यान रखें",
    },
    "tip_formula_flashcards": {
        "en": "revise key chapter formulas using short flashcards",
        "hi": "प्रमुख अध्याय सूत्रों को संक्षिप्त फ्लैशकार्ड से दोहराएँ",
    },
    "tip_timed_practice_set": {
        "en": "solve one short timed practice set at home without interruption",
        "hi": "घर पर बिना रुकावट एक संक्षिप्त समयबद्ध अभ्यास सेट हल करें",
    },
    "tip_ask_faculty_doubts": {
        "en": "write down unsolved questions and ask faculty doubts promptly",
        "hi": "अनसुलझे प्रश्नों को लिखकर शिक्षक से समय पर डाउट पूछें",
    },
    "tip_regular_class_attendance": {
        "en": "prioritise regular class attendance so lectures stay connected",
        "hi": "नियमित कक्षा उपस्थिति बनाए रखें ताकि सभी अध्याय क्रम से समझ आएँ",
    },
    "tip_encourage_steady_effort": {
        "en": "encourage steady effort and praise consistent daily study",
        "hi": "निरंतर प्रयास की सराहना करें और शांत अध्ययन के लिए प्रोत्साहित करें",
    },
}

TREND_HI_LABELS: dict[str, str] = {
    "improving": "सुधारोन्मुख",
    "steady": "स्थिर और संतुलित",
    "declining": "थोड़ी धीमी गति वाली",
}

PERIOD_CLEAN_RE = re.compile(r"^[A-Za-z0-9\-_/ ]{4,32}$")


def _select_home_tips_by_rules(
    attendance_pct: float,
    tests_taken: int,
    trend: str,
    strengths_count: int,
    focus_count: int,
    explicit_tips: list[str] | tuple[str, ...] | None = None,
) -> tuple[str, str]:
    """Deterministic rule selector for 2 distinct home_tips from the contract enum."""
    if explicit_tips is not None and len(explicit_tips) == 2:
        t1, t2 = str(explicit_tips[0]), str(explicit_tips[1])
        if t1 in ALLOWED_HOME_TIPS and t2 in ALLOWED_HOME_TIPS and t1 != t2:
            return (t1, t2)

    chosen: list[str] = []
    if attendance_pct < 75.0:
        chosen.append("tip_regular_class_attendance")
    if trend == "declining":
        if "tip_encourage_steady_effort" not in chosen:
            chosen.append("tip_encourage_steady_effort")
        if "tip_ask_faculty_doubts" not in chosen and len(chosen) < 2:
            chosen.append("tip_ask_faculty_doubts")
    if tests_taken < 3 and len(chosen) < 2:
        if "tip_fixed_revision_slot" not in chosen:
            chosen.append("tip_fixed_revision_slot")
        if "tip_encourage_steady_effort" not in chosen and len(chosen) < 2:
            chosen.append("tip_encourage_steady_effort")
    if focus_count >= 2 and len(chosen) < 2:
        if "tip_mistake_notebook_review" not in chosen:
            chosen.append("tip_mistake_notebook_review")
        if "tip_formula_flashcards" not in chosen and len(chosen) < 2:
            chosen.append("tip_formula_flashcards")
    if trend == "improving" and len(chosen) < 2:
        if "tip_timed_practice_set" not in chosen:
            chosen.append("tip_timed_practice_set")
        if "tip_sleep_and_rest_day" not in chosen and len(chosen) < 2:
            chosen.append("tip_sleep_and_rest_day")

    # Fill any remaining slot deterministically
    fallback_order = (
        "tip_fixed_revision_slot",
        "tip_mistake_notebook_review",
        "tip_sleep_and_rest_day",
        "tip_encourage_steady_effort",
    )
    for tip in fallback_order:
        if len(chosen) >= 2:
            break
        if tip not in chosen:
            chosen.append(tip)

    return (chosen[0], chosen[1])


def _resolve_topic_item(raw: dict[str, Any] | TopicItem, topics_catalog: dict[str, dict[str, Any]]) -> TopicItem | None:
    """
    Resolve a topic entry strictly through `contracts/topics.yaml` allow-list.
    - Filters out any topic with `mastery_band == 'not_enough_data'`.
    - Overrides any caller-supplied `name_en` / `name_hi` with the canonical strings from `topics.yaml`
      so prompt injection inside topic names is impossible.
    """
    if isinstance(raw, TopicItem):
        tid = raw.topic_id
        band = raw.mastery_band
    elif isinstance(raw, dict):
        tid = str(raw.get("topic_id", "")).strip()
        band = str(raw.get("mastery_band") or raw.get("band") or "steady").strip()
    else:
        raise ValueError(f"Unsupported topic item type: {type(raw)}")

    if band == "not_enough_data":
        return None
    if band not in ("building", "steady", "strong"):
        raise ValueError(f"Invalid mastery_band '{band}' for topic '{tid}'")

    if tid not in topics_catalog:
        raise ValueError(f"Topic '{tid}' is not in the canonical contracts/topics.yaml allow-list")

    canonical = topics_catalog[tid]
    return TopicItem(
        topic_id=tid,
        name_en=str(canonical["name_en"]),
        name_hi=str(canonical["name_hi"]),
        mastery_band=band,  # type: ignore[arg-type]
    )


def build_numbers(inputs: dict[str, Any]) -> NumbersJson:
    """
    Step 1: Build deterministic `NumbersJson` from analytics outputs.
    - Enforces `0.0 <= attendance_pct <= 100.0` and `tests_taken >= 0`.
    - Validates `period` against prompt injection (strictly alphanumeric/date window).
    - Filters out `not_enough_data` topics.
    -Resolves topic names exclusively from `contracts/topics.yaml` (blocks prompt injection via topic names).
    - Truncates to `<= 3` strengths and `<= 3` focus topics (with no overlap).
    - Selects exactly 2 `home_tips` by deterministic rules.
    - Validates output against `contracts/report_numbers.schema.json`.
    """
    topics_catalog = load_topics_contract()

    raw_period = str(inputs.get("period", "2026-W20")).strip()
    if not PERIOD_CLEAN_RE.match(raw_period):
        raise ValueError(
            f"Invalid period label '{raw_period}': must match {PERIOD_CLEAN_RE.pattern} (no free text allowed)"
        )

    lang = str(inputs.get("lang", "en")).strip()
    if lang not in ("en", "hi"):
        raise ValueError(f"Invalid lang '{lang}': must be 'en' or 'hi'")

    attendance_pct = round(float(inputs.get("attendance_pct", 0.0)), 1)
    if not (0.0 <= attendance_pct <= 100.0):
        raise ValueError(f"attendance_pct={attendance_pct} out of range [0.0, 100.0]")

    tests_taken = int(inputs.get("tests_taken", 0))
    if tests_taken < 0:
        raise ValueError(f"tests_taken={tests_taken} must be >= 0")

    trend = str(inputs.get("trend", "steady")).strip()
    if trend not in ("improving", "steady", "declining"):
        raise ValueError(f"Invalid trend '{trend}'")

    # Process topics: callers may pass `strengths` + `focus` or a unified `topics` list
    raw_strengths = list(inputs.get("strengths", []))
    raw_focus = list(inputs.get("focus", []))

    if "topics" in inputs and not raw_strengths and not raw_focus:
        for t in inputs["topics"]:
            b = t.get("mastery_band") or t.get("band")
            if b == "strong":
                raw_strengths.append(t)
            elif b in ("building", "steady"):
                raw_focus.append(t)

    strengths_list: list[TopicItem] = []
    seen_ids: set[str] = set()
    for item in raw_strengths:
        resolved = _resolve_topic_item(item, topics_catalog)
        if resolved is not None and resolved.topic_id not in seen_ids:
            strengths_list.append(resolved)
            seen_ids.add(resolved.topic_id)
            if len(strengths_list) == 3:
                break

    focus_list: list[TopicItem] = []
    for item in raw_focus:
        resolved = _resolve_topic_item(item, topics_catalog)
        if resolved is not None and resolved.topic_id not in seen_ids:
            focus_list.append(resolved)
            seen_ids.add(resolved.topic_id)
            if len(focus_list) == 3:
                break

    home_tips = _select_home_tips_by_rules(
        attendance_pct=attendance_pct,
        tests_taken=tests_taken,
        trend=trend,
        strengths_count=len(strengths_list),
        focus_count=len(focus_list),
        explicit_tips=inputs.get("home_tips"),
    )

    numbers = NumbersJson(
        contract_version="1.0.0",
        period=raw_period,
        lang=lang,  # type: ignore[arg-type]
        student_placeholder="{STUDENT}",
        institute_placeholder="{INSTITUTE}",
        attendance_pct=attendance_pct,
        tests_taken=tests_taken,
        trend=trend,  # type: ignore[arg-type]
        strengths=tuple(strengths_list),
        focus=tuple(focus_list),
        home_tips=home_tips,
    )

    get_report_numbers_validator().validate(numbers.to_dict())
    return numbers


@lru_cache(maxsize=4)
def _load_system_prompt(lang: Lang) -> str:
    path = PROMPTS_DIR / f"system_{lang}.txt"
    return path.read_text(encoding="utf-8").strip()


def render_prompt(
    numbers: NumbersJson | dict[str, Any],
    lang: Lang | None = None,
    *,
    prior_failures: list[str] | None = None,
) -> Prompt:
    """
    Step 2: Build a deterministic `Prompt` with fixed system instructions and the validated `NumbersJson` as data.
    Never accepts student names, institute names, roll numbers, phone numbers, or free text.
    """
    if isinstance(numbers, dict):
        numbers_obj = build_numbers(numbers)
    else:
        numbers_obj = numbers
        get_report_numbers_validator().validate(numbers_obj.to_dict())

    target_lang: Lang = lang if lang is not None else numbers_obj.lang
    if target_lang not in ("en", "hi"):
        raise ValueError(f"Unsupported language: {target_lang}")

    if numbers_obj.lang != target_lang:
        numbers_obj = NumbersJson(
            contract_version=numbers_obj.contract_version,
            period=numbers_obj.period,
            lang=target_lang,
            student_placeholder="{STUDENT}",
            institute_placeholder="{INSTITUTE}",
            attendance_pct=numbers_obj.attendance_pct,
            tests_taken=numbers_obj.tests_taken,
            trend=numbers_obj.trend,
            strengths=numbers_obj.strengths,
            focus=numbers_obj.focus,
            home_tips=numbers_obj.home_tips,
        )

    system_text = _load_system_prompt(target_lang)
    tip_1, tip_2 = numbers_obj.home_tips
    tips_expanded = [
        {"id": tip_1, "phrasing": HOME_TIPS_CATALOG[tip_1][target_lang]},
        {"id": tip_2, "phrasing": HOME_TIPS_CATALOG[tip_2][target_lang]},
    ]

    user_payload: dict[str, Any] = {
        "numbers_json": numbers_obj.to_dict(),
        "home_tips_phrasing": tips_expanded,
    }
    if prior_failures:
        user_payload["retry_corrections_required"] = list(prior_failures)

    user_text = json.dumps(user_payload, ensure_ascii=False, indent=2, sort_keys=True)
    return Prompt(
        system=system_text,
        user=user_text,
        lang=target_lang,
        prompt_version=PROMPT_VERSION,
        output_schema=load_report_output_schema(),
    )


def _format_attendance(val: float) -> str:
    f = float(val)
    if f.is_integer():
        return str(int(round(f)))
    return f"{f:.1f}".rstrip("0").rstrip(".")


def _join_topic_names(items: tuple[TopicItem, ...], lang: Lang) -> str:
    names = [t.name_en if lang == "en" else t.name_hi for t in items]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    conj = "and" if lang == "en" else "और"
    if len(names) == 2:
        return f"{names[0]} {conj} {names[1]}"
    return f"{', '.join(names[:-1])} {conj} {names[-1]}"


def _choose_template_name(numbers: NumbersJson, lang: Lang) -> str:
    """
    Deterministically select one of the 10 human-written templates per language based on
    trend, strengths/focus counts, tests_taken, attendance_pct, and the input hash seed.
    """
    prefix = "en" if lang == "en" else "hi"
    seed_int = int(numbers.sha256()[:8], 16)

    if numbers.tests_taken < 3:
        return f"{prefix}_07_new_student_early.j2"
    if numbers.attendance_pct < 65.0:
        if numbers.trend == "declining":
            return f"{prefix}_06_declining_attendance_support.j2"
        return f"{prefix}_08_attendance_check_in.j2"

    if numbers.trend == "improving":
        if len(numbers.strengths) >= 2 and len(numbers.focus) <= 1:
            return f"{prefix}_09_all_strong_momentum.j2"
        candidates = [f"{prefix}_01_improving_balanced.j2", f"{prefix}_02_improving_focus.j2"]
        return candidates[seed_int % len(candidates)]

    if numbers.trend == "steady":
        if len(numbers.strengths) == 0:
            return f"{prefix}_04_steady_no_strengths.j2"
        candidates = [
            f"{prefix}_03_steady_balanced.j2",
            f"{prefix}_09_all_strong_momentum.j2",
            f"{prefix}_10_general_fallback.j2",
        ]
        return candidates[seed_int % len(candidates)]

    # trend == "declining"
    candidates = [f"{prefix}_05_declining_supportive.j2", f"{prefix}_06_declining_attendance_support.j2"]
    return candidates[seed_int % len(candidates)]


@lru_cache(maxsize=2)
def _get_jinja_env(lang: Lang) -> jinja2.Environment:
    folder = TEMPLATES_DIR / lang
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(folder)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_template_output(
    numbers: NumbersJson,
    lang: Lang,
    *,
    template_filename: str | None = None,
) -> tuple[dict[str, Any], str]:
    """
    Render a human-written `.j2` template into a structured `ReportOutputJson` dict and return `(output_dict, template_id)`.
    """
    env = _get_jinja_env(lang)
    fname = template_filename or _choose_template_name(numbers, lang)
    tmpl = env.get_template(fname)
    template_id = Path(fname).stem

    tip_1, tip_2 = numbers.home_tips
    context = {
        "period": numbers.period,
        "attendance_str": _format_attendance(numbers.attendance_pct),
        "tests_taken": numbers.tests_taken,
        "trend": numbers.trend,
        "trend_hi": TREND_HI_LABELS[numbers.trend],
        "strengths_text": _join_topic_names(numbers.strengths, lang),
        "focus_text": _join_topic_names(numbers.focus, lang),
        "tip_1_text": HOME_TIPS_CATALOG[tip_1][lang],
        "tip_2_text": HOME_TIPS_CATALOG[tip_2][lang],
    }

    rendered_lines = [
        line.strip()
        for line in tmpl.render(**context).splitlines()
        if line.strip() and not line.strip().startswith("{#")
    ]
    body = re.sub(r"\s+", " ", " ".join(rendered_lines)).strip()
    words = body.split()

    if lang == "en":
        title = f"Progress Update ({numbers.period})"
    else:
        title = f"प्रगति रिपोर्ट ({numbers.period})"

    output_dict = {
        "contract_version": "1.0.0",
        "title": title,
        "body": body,
        "word_count": len(words),
    }
    return output_dict, template_id


def compute_cache_key(numbers: NumbersJson, lang: Lang, prompt_version: str, model_name: str) -> str:
    payload = f"{numbers.canonical_json()}|lang={lang}|prompt={prompt_version}|model={model_name}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def _get_default_cost_meter() -> CostMeter:
    return CostMeter()


def generate_report(
    numbers: NumbersJson | dict[str, Any],
    lang: Lang | None = None,
    client: LLMClient | None = None,
    *,
    cache: dict[str, Report] | None = None,
    cost_meter: CostMeter | None = None,
    institute_key: str = "default",
    month_key: str = "current",
) -> Report:
    """
    Step 5: Generate a verified parent report:
    1. Validate/normalise `numbers` and check cache by `sha256(numbers_json canonical + lang + prompt_version + model)`.
    2. Check `CostMeter` monthly cap; if reached or `client` is `NullClient`/None, jump directly to template fallback.
    3. Try `client.generate(prompt)` -> `verify(output, numbers, lang)`.
    4. On verifier failure, retry ONCE with `prior_failures` appended to the prompt data.
    5. If still failing, or if client raises timeout/error/malformed JSON, fall back to deterministic template path.
    6. Verify the template output; a report with `verified=False` can NEVER be returned.
    """
    t_start = time.perf_counter()
    numbers_obj = build_numbers(numbers) if isinstance(numbers, dict) else numbers
    target_lang: Lang = lang if lang is not None else numbers_obj.lang
    active_client: LLMClient = client if client is not None else NullClient()
    meter = cost_meter if cost_meter is not None else _get_default_cost_meter()

    cache_key = compute_cache_key(numbers_obj, target_lang, PROMPT_VERSION, active_client.model_name)
    if cache is not None and cache_key in cache:
        cached = cache[cache_key]
        return Report(
            content=cached.content,
            path=cached.path,
            verified=True,
            model=cached.model,
            latency_ms=cached.latency_ms,
            tokens_in=cached.tokens_in,
            tokens_out=cached.tokens_out,
            cost_inr=cached.cost_inr,
            failures=list(cached.failures),
            template_id=cached.template_id,
            cache_hit=True,
        )

    collected_failures: list[str] = []
    total_tokens_in = 0
    total_tokens_out = 0
    total_cost_inr = 0.0

    # Check if monthly budget cap allows calling the LLM
    est_call_cost = meter.compute_cost_inr(active_client.model_name, 600, 300)
    can_use_llm = not isinstance(active_client, NullClient) and meter.can_spend(
        institute_key=institute_key,
        month_key=month_key,
        estimated_cost_inr=est_call_cost,
    )
    if not isinstance(active_client, NullClient) and not can_use_llm:
        collected_failures.append("cost_cap_reached: monthly institute LLM cap reached; using template fallback")

    if can_use_llm:
        for attempt in range(2):
            prompt = render_prompt(
                numbers_obj,
                target_lang,
                prior_failures=collected_failures if attempt == 1 else None,
            )
            try:
                llm_resp = active_client.generate(prompt)
                total_tokens_in += llm_resp.tokens_in
                total_tokens_out += llm_resp.tokens_out
                call_cost = meter.record(
                    active_client.model_name,
                    llm_resp.tokens_in,
                    llm_resp.tokens_out,
                    institute_key=institute_key,
                    month_key=month_key,
                )
                total_cost_inr = round(total_cost_inr + call_cost, 6)

                v_res = verify(llm_resp.raw_text, numbers_obj, target_lang)
                if v_res.ok:
                    parsed_content = json.loads(llm_resp.raw_text)
                    elapsed_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
                    report = Report(
                        content=parsed_content,
                        path="llm",
                        verified=True,
                        model=llm_resp.model,
                        latency_ms=elapsed_ms,
                        tokens_in=total_tokens_in,
                        tokens_out=total_tokens_out,
                        cost_inr=total_cost_inr,
                        failures=collected_failures,
                        template_id=None,
                        cache_hit=False,
                    )
                    if cache is not None:
                        cache[cache_key] = report
                    return report
                else:
                    collected_failures.extend([f"attempt_{attempt + 1}: {f}" for f in v_res.failures])
            except Exception as exc:
                collected_failures.append(f"attempt_{attempt + 1}_client_error: {exc}")
                # On transport/client error (timeout, HTTP 500, NullClient), fall back immediately to templates
                break

    # Guaranteed deterministic template path
    tmpl_output, tmpl_id = render_template_output(numbers_obj, target_lang)
    v_tmpl = verify(tmpl_output, numbers_obj, target_lang)
    if not v_tmpl.ok:
        # Try general fallback template if specific variant failed for any edge reason
        fallback_fname = "en_10_general_fallback.j2" if target_lang == "en" else "hi_10_general_fallback.j2"
        tmpl_output, tmpl_id = render_template_output(
            numbers_obj, target_lang, template_filename=fallback_fname
        )
        v_tmpl = verify(tmpl_output, numbers_obj, target_lang)
        if not v_tmpl.ok:
            raise RuntimeError(f"CRITICAL: Deterministic template '{tmpl_id}' failed verification: {v_tmpl.failures}")

    meter.record("template_fallback", 0, 0, institute_key=institute_key, month_key=month_key)
    elapsed_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
    report = Report(
        content=tmpl_output,
        path="template",
        verified=True,
        model="template_fallback",
        latency_ms=elapsed_ms,
        tokens_in=total_tokens_in,
        tokens_out=total_tokens_out,
        cost_inr=total_cost_inr,
        failures=collected_failures,
        template_id=tmpl_id,
        cache_hit=False,
    )
    if cache is not None:
        cache[cache_key] = report
    return report


def substitute_placeholders(
    report: Report,
    *,
    student_name: str,
    institute_name: str,
) -> dict[str, Any]:
    """
    Post-verification placeholder substitution: replaces `{STUDENT}` and `{INSTITUTE}` ONLY after
    the report has been verified, ensuring student PII never enters the LLM or prompt cache.
    """
    if not report.verified:
        raise ValueError("Cannot substitute placeholders on an unverified report.")
    s_clean = student_name.strip()
    i_clean = institute_name.strip()
    if not s_clean or not i_clean:
        raise ValueError("student_name and institute_name must be non-empty.")

    body = report.content["body"].replace("{STUDENT}", s_clean).replace("{INSTITUTE}", i_clean)
    title = report.content["title"].replace("{STUDENT}", s_clean).replace("{INSTITUTE}", i_clean)
    return {
        "contract_version": report.content["contract_version"],
        "title": title,
        "body": body,
        "word_count": report.content["word_count"],
        "path": report.path,
        "verified": report.verified,
        "model": report.model,
    }


def export_report_pdf_bytes(report_content: dict[str, Any], lang: Lang = "hi") -> bytes:
    """
    Export a verified report (`title` + `body`) to a PDF in memory with the bundled
    OFL `NotoSansDevanagari-Regular.ttf` font embedded.
    Also asserts that every character in `title` and `body` has a valid glyph in the bundled font cmap.
    """
    from fontTools.ttLib import TTFont
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont as RLTTFont
    from reportlab.pdfgen import canvas

    font_path = TEMPLATES_DIR / "fonts" / "NotoSansDevanagari-Regular.ttf"
    if not font_path.exists():
        raise FileNotFoundError(f"Bundled font missing at {font_path}")

    tt = TTFont(str(font_path))
    cmap = tt.getBestCmap() or {}

    title = str(report_content.get("title", ""))
    body = str(report_content.get("body", ""))
    full_text = f"{title}\n{body}"

    missing_glyphs = sorted({ch for ch in full_text if not ch.isspace() and ord(ch) not in cmap})
    if missing_glyphs:
        raise ValueError(f"Missing glyphs in bundled NotoSansDevanagari font: {missing_glyphs}")

    font_name = "NotoSansDevanagariRegular"
    if font_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(RLTTFont(font_name, str(font_path)))

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    c.setFont(font_name, 14)
    c.drawString(50, height - 60, title)

    c.setFont(font_name, 11)
    y = height - 95
    words = body.split()
    line_words: list[str] = []
    for w in words:
        line_words.append(w)
        if len(" ".join(line_words)) > 75:
            c.drawString(50, y, " ".join(line_words[:-1]))
            line_words = [w]
            y -= 18
            if y < 60:
                c.showPage()
                c.setFont(font_name, 11)
                y = height - 60
    if line_words:
        c.drawString(50, y, " ".join(line_words))

    c.save()
    return buf.getvalue()
