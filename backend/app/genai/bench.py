# Purpose: 500-case deterministic fuzz suite and benchmark fixture generator for the GenAI verifier and local LLM evaluation.
# contract_version: 1.0.0
# Implements: TECH_PLAN §3 #7, §11 (GenAI eval), §18 (Testing strategy), and R1_E_genai_reports.md Acceptance Criteria #1 & #2.

from __future__ import annotations

import copy
import json
import random
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .clients import FakeClient, LLMClient, NullClient, OllamaClient
from .cost import CostMeter
from .models import GENAI_DIR, REPO_ROOT, TEMPLATES_DIR, NumbersJson, load_topics_contract
from .pipeline import build_numbers, generate_report, render_template_output
from .verifier import verify

CORRUPTION_CATEGORIES: tuple[str, ...] = (
    "wrong_number_ascii",
    "wrong_number_devanagari_or_word",
    "unallowed_topic_swap",
    "duplicate_focus_topic",
    "rank_or_comparison",
    "proper_name_injection",
    "dropout_or_mental_health_wording",
    "missing_placeholder",
    "length_or_word_count_violation",
    "inverted_trend",
    "unicode_confusable_or_zero_width",
    "mixed_script_or_missing_tip",
)


def build_50_varied_numbers(seed: int = 42) -> list[NumbersJson]:
    """
    Build 50 varied, deterministic `NumbersJson` instances covering normal and edge cases:
    - 0 strengths, 1-3 strengths
    - 0 focus topics, 1-3 focus topics
    - `tests_taken` = 0, 1, 2, 5, 10, 18
    - `attendance_pct` = 0.0%, 42.5%, 60.0%, 75.0%, 88.5%, 100.0%
    - `trend` in ('improving', 'steady', 'declining')
    - topics containing digits (`1D`, `SN1`, `10% Law`) and parentheses (`Logic Gates (OR, AND, NOT, NAND, NOR)`)
    """
    rng = random.Random(seed)
    topics_map = load_topics_contract()
    all_topic_ids = [tid for tid, t in topics_map.items() if t.get("level") != "subject"]

    # Ensure specific edge-case topics with digits/parentheses are included in early fixtures
    special_ids = [
        "jee.phy.kinematics.relative_velocity",  # Relative Velocity in 1D and 2D
        "jee.chem.organic_halides.sn1_sn2",  # Nucleophilic Substitution SN1 and SN2 Mechanisms
        "jee.phy.semiconductors.logic_gates",  # Logic Gates (OR, AND, NOT, NAND, NOR)
        "neet.bot.ecology_ecosystem.energy_flow_pyramids",  # Energy Flow, 10% Law and Ecological Pyramids
    ]
    special_ids = [sid for sid in special_ids if sid in topics_map]

    explicit_edges: list[dict[str, Any]] = [
        # Edge 0: 0 tests, 0% attendance, no strengths, no focus, steady
        {
            "period": "2026-W01",
            "lang": "en",
            "attendance_pct": 0.0,
            "tests_taken": 0,
            "trend": "steady",
            "strengths": [],
            "focus": [],
        },
        # Edge 1: 100% attendance, 1 test, 0 strengths, 3 focus topics, improving
        {
            "period": "2026-W02",
            "lang": "hi",
            "attendance_pct": 100.0,
            "tests_taken": 1,
            "trend": "improving",
            "strengths": [],
            "focus": [{"topic_id": tid, "mastery_band": "building"} for tid in all_topic_ids[:3]],
        },
        # Edge 2: low attendance (45%), 2 tests, declining trend, 1 strength, 2 focus
        {
            "period": "2026-W03",
            "lang": "en",
            "attendance_pct": 45.0,
            "tests_taken": 2,
            "trend": "declining",
            "strengths": [{"topic_id": all_topic_ids[3], "mastery_band": "strong"}],
            "focus": [{"topic_id": tid, "mastery_band": "building"} for tid in all_topic_ids[4:6]],
        },
        # Edge 3: all topics marked not_enough_data -> results in 0 strengths and 0 focus
        {
            "period": "2026-W04",
            "lang": "hi",
            "attendance_pct": 82.5,
            "tests_taken": 2,
            "trend": "steady",
            "strengths": [{"topic_id": all_topic_ids[6], "mastery_band": "not_enough_data"}],
            "focus": [{"topic_id": all_topic_ids[7], "mastery_band": "not_enough_data"}],
        },
        # Edge 4: topics with digits and parentheses
        {
            "period": "2026-W05",
            "lang": "en",
            "attendance_pct": 91.0,
            "tests_taken": 8,
            "trend": "improving",
            "strengths": [{"topic_id": tid, "mastery_band": "strong"} for tid in special_ids[:2]],
            "focus": [{"topic_id": tid, "mastery_band": "building"} for tid in special_ids[2:4]],
        },
    ]

    results: list[NumbersJson] = [build_numbers(cfg) for cfg in explicit_edges]

    trends = ("improving", "steady", "declining")
    att_pool = (0.0, 38.0, 48.5, 62.0, 74.5, 80.0, 86.5, 92.0, 96.5, 100.0)
    tests_pool = (0, 1, 2, 3, 4, 6, 8, 10, 12, 15)

    for idx in range(len(results), 50):
        sample_ids = rng.sample(all_topic_ids, k=6)
        n_s = rng.choice((0, 1, 2, 3))
        n_f = rng.choice((0, 1, 2, 3))
        s_items = [{"topic_id": tid, "mastery_band": "strong"} for tid in sample_ids[:n_s]]
        f_items = [
            {"topic_id": tid, "mastery_band": rng.choice(("building", "steady"))}
            for tid in sample_ids[n_s : n_s + n_f]
        ]
        lang = "en" if idx % 2 == 0 else "hi"
        cfg = {
            "period": f"2026-W{(idx % 52) + 1:02d}",
            "lang": lang,
            "attendance_pct": rng.choice(att_pool),
            "tests_taken": rng.choice(tests_pool),
            "trend": trends[idx % 3],
            "strengths": s_items,
            "focus": f_items,
        }
        results.append(build_numbers(cfg))

    return results


def _corrupt_output(
    clean_output: dict[str, Any],
    numbers: NumbersJson,
    lang: str,
    category: str,
    idx: int,
) -> dict[str, Any]:
    """Deterministically apply a targeted corruption of `category` to a verified report output."""
    corrupted = copy.deepcopy(clean_output)
    body: str = corrupted["body"]

    if category == "wrong_number_ascii":
        # Inject an unverified number (e.g., 999 or 47.3)
        injected_num = str(317 + (idx % 500))
        body = body + f" Extra score recorded was {injected_num}."
        corrupted["body"] = body
        corrupted["word_count"] = len(body.split())

    elif category == "wrong_number_devanagari_or_word":
        if lang == "hi":
            # Inject Devanagari digits ९७% or Hindi number word पचास
            injected = "९७ प्रतिशत" if idx % 2 == 0 else "पचास अंक"
            body = body + f" अतिरिक्त मूल्यांकन में {injected} प्राप्त हुए।"
        else:
            injected = "ninety percent" if idx % 2 == 0 else "७३%"
            body = body + f" Additional test score reached {injected} recently."
        corrupted["body"] = body
        corrupted["word_count"] = len(body.split())

    elif category == "unallowed_topic_swap":
        # Pick a syllabus topic NOT in strengths or focus
        allowed_ids = {t.topic_id for t in (*numbers.strengths, *numbers.focus)}
        topics_map = load_topics_contract()
        candidate_topics = [
            t for tid, t in topics_map.items()
            if tid not in allowed_ids and t.get("level") == "chapter"
        ]
        rogue = candidate_topics[idx % len(candidate_topics)]
        if lang == "en":
            body = body + f" Next week we will also test {rogue['name_en']}."
        else:
            body = body + f" अगले सप्ताह {rogue['name_hi']} का भी मूल्यांकन होगा।"
        corrupted["body"] = body
        corrupted["word_count"] = len(body.split())

    elif category == "duplicate_focus_topic":
        if numbers.focus:
            f_name = numbers.focus[0].name_en if lang == "en" else numbers.focus[0].name_hi
        else:
            # Even if focus was empty, repeat an unallowed topic twice
            f_name = "Thermodynamics" if lang == "en" else "ऊष्मागतिकी"
        if lang == "en":
            body = body + f" Please revise {f_name} and practise {f_name} again."
        else:
            body = body + f" कृपया {f_name} और {f_name} का बार-बार अभ्यास करें।"
        corrupted["body"] = body
        corrupted["word_count"] = len(body.split())

    elif category == "rank_or_comparison":
        if lang == "en":
            phrases = [
                "Currently {STUDENT} is ranked worse than other students in the leaderboard.",
                "In batch comparison, {STUDENT} is at the bottom of the star batch.",
                "Performance is better than other students in the ranking.",
            ]
        else:
            phrases = [
                "बैच रैंकिंग और लीडरबोर्ड में {STUDENT} बाकी बच्चों से पीछे है।",
                "स्टार बैच की तुलना में {STUDENT} की रैंक कम है।",
                "अन्य छात्रों से तुलना करने पर प्रदर्शन सबसे पीछे दिखा है।",
            ]
        body = body + " " + phrases[idx % len(phrases)]
        corrupted["body"] = body
        corrupted["word_count"] = len(body.split())

    elif category == "proper_name_injection":
        if lang == "en":
            names = ["Aarav Sharma", "Rohan Verma", "Priya Singh", "Allen Kota", "Vikram Gupta"]
            body = body + f" Mentor {names[idx % len(names)]} reviewed the copy."
        else:
            names = ["आरव शर्मा", "रोहन वर्मा", "प्रिया सिंह", "राहुल कुमार", "कोटा एलन"]
            body = body + f" कक्षा में {names[idx % len(names)]} के साथ चर्चा हुई।"
        corrupted["body"] = body
        corrupted["word_count"] = len(body.split())

    elif category == "dropout_or_mental_health_wording":
        if lang == "en":
            bad = [
                "There is a high dropout risk and signs of depression.",
                "The weak student looks lazy, careless, and hopeless.",
                "Mental health and failure indicators suggest dropping out.",
            ]
        else:
            bad = [
                "छात्र में ड्रॉपआउट का जोखिम और डिप्रेशन के लक्षण दिख रहे हैं।",
                "यह एक कमजोर छात्र है जो आलसी और लापरवाह होकर फेल हो रहा है।",
                "मानसिक स्वास्थ्य और असफल होने की स्थिति चिंताजनक है।",
            ]
        body = body + " " + bad[idx % len(bad)]
        corrupted["body"] = body
        corrupted["word_count"] = len(body.split())

    elif category == "missing_placeholder":
        if idx % 2 == 0:
            body = body.replace("{STUDENT}", "the learner")
        else:
            body = body.replace("{INSTITUTE}", "our centre")
        corrupted["body"] = body
        corrupted["word_count"] = len(body.split())

    elif category == "length_or_word_count_violation":
        mode = idx % 3
        if mode == 0:
            # Too short (< 80 words)
            short_body = " ".join(body.split()[:45])
            corrupted["body"] = short_body
            corrupted["word_count"] = len(short_body.split())
        elif mode == 1:
            # Too long (> 180 words)
            filler = " Regular practice builds steady chapter comfort." if lang == "en" else " नियमित अभ्यास से अध्याय की समझ बढ़ती है।"
            long_body = body + (filler * 25)
            corrupted["body"] = long_body
            corrupted["word_count"] = len(long_body.split())
        else:
            # Mismatched declared word_count
            corrupted["word_count"] = corrupted["word_count"] + 7

    elif category == "inverted_trend":
        if numbers.trend == "improving":
            if lang == "en":
                body = body.replace("improving", "declining") + " Recent scores show a declining trend."
            else:
                body = body.replace("सुधार", "गिरावट") + " हाल में गति थोड़ी धीमी रही है और क्रमिक गिरावट है।"
        elif numbers.trend == "declining":
            if lang == "en":
                body = body.replace("declining", "improving").replace("softened", "improved") + " Overall progress shows an improving trend."
            else:
                body = body.replace("धीमी", "तेज") + " हाल के मूल्यांकनों में निरंतर सुधार दिखा है।"
        else:
            if lang == "en":
                body = body.replace("steady", "declining") + " Scores show a declining trend."
            else:
                body = body.replace("स्थिर", "धीमी") + " हाल में गति थोड़ी धीमी रही है।"
        corrupted["body"] = body
        corrupted["word_count"] = len(body.split())

    elif category == "unicode_confusable_or_zero_width":
        if idx % 2 == 0:
            # Inject zero-width space inside a word
            body = body[:30] + "\u200b" + body[30:]
        else:
            # Inject Cyrillic homoglyph 'а' (\u0430) or 'о' (\u043e)
            body = body + " (\u0430ssessment)"
        corrupted["body"] = body
        corrupted["word_count"] = len(body.split())

    elif category == "mixed_script_or_missing_tip":
        if idx % 2 == 0:
            # Wrong script injection
            if lang == "en":
                body = body + " यह हिंदी वाक्य अंग्रेजी रिपोर्ट में है।"
            else:
                # Replace whole Hindi body with English
                en_out, _ = render_template_output(numbers, "en")
                body = en_out["body"]
        else:
            # Strip out the second home tip sentence
            if lang == "en":
                body = re.sub(r"Second,[^.]+\.", "Second, keep studying well.", body)
            else:
                body = re.sub(r"दूसरा,[^।]+।", "दूसरा, मन लगाकर पढ़ाई जारी रखें।", body)
        corrupted["body"] = body
        corrupted["word_count"] = len(body.split())

    return corrupted


def run_fuzz_500(seed: int = 42) -> dict[str, Any]:
    """
    Run the 500-case deterministic corruption fuzz suite across all 12 corruption categories.
    Returns overall catch rate and per-category breakdown.
    """
    fixtures = build_50_varied_numbers(seed=seed)
    total_cases = 500
    caught_total = 0
    by_category: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "caught": 0})
    uncaught_examples: list[dict[str, Any]] = []

    for i in range(total_cases):
        base_num = fixtures[i % len(fixtures)]
        lang = "en" if i % 2 == 0 else "hi"
        num_lang = NumbersJson(
            contract_version=base_num.contract_version,
            period=base_num.period,
            lang=lang,  # type: ignore[arg-type]
            student_placeholder="{STUDENT}",
            institute_placeholder="{INSTITUTE}",
            attendance_pct=base_num.attendance_pct,
            tests_taken=base_num.tests_taken,
            trend=base_num.trend,
            strengths=base_num.strengths,
            focus=base_num.focus,
            home_tips=base_num.home_tips,
        )
        clean_out, _ = render_template_output(num_lang, lang)  # type: ignore[arg-type]
        category = CORRUPTION_CATEGORIES[i % len(CORRUPTION_CATEGORIES)]
        corrupted_out = _corrupt_output(clean_out, num_lang, lang, category, i)

        v_res = verify(corrupted_out, num_lang, lang)  # type: ignore[arg-type]
        by_category[category]["total"] += 1
        if not v_res.ok:
            caught_total += 1
            by_category[category]["caught"] += 1
        else:
            uncaught_examples.append({"index": i, "category": category, "lang": lang, "corrupted": corrupted_out})

    category_summary = {
        cat: {
            "total": stats["total"],
            "caught": stats["caught"],
            "catch_rate": round(stats["caught"] / max(1, stats["total"]), 4),
        }
        for cat, stats in by_category.items()
    }

    return {
        "total_corrupted": total_cases,
        "caught": caught_total,
        "catch_rate": round(caught_total / total_cases, 6),
        "by_category": category_summary,
        "uncaught_examples": uncaught_examples,
    }


def run_1000_fake_client_mix(seed: int = 42) -> dict[str, Any]:
    """
    Generate 1,000 reports with `FakeClient` returning random mixtures of good and corrupted outputs.
    Asserts that every returned report has `verified=True` and passes `verify()`, so
    `genai_unverified_reports_shipped == 0`.
    """
    rng = random.Random(seed)
    fixtures = build_50_varied_numbers(seed=seed)
    total_reports = 1000
    unverified_shipped = 0
    llm_accepted = 0
    template_fallbacks = 0

    for i in range(total_reports):
        base_num = fixtures[i % len(fixtures)]
        lang = "en" if i % 2 == 0 else "hi"
        num_lang = NumbersJson(
            contract_version=base_num.contract_version,
            period=base_num.period,
            lang=lang,  # type: ignore[arg-type]
            student_placeholder="{STUDENT}",
            institute_placeholder="{INSTITUTE}",
            attendance_pct=base_num.attendance_pct,
            tests_taken=base_num.tests_taken,
            trend=base_num.trend,
            strengths=base_num.strengths,
            focus=base_num.focus,
            home_tips=base_num.home_tips,
        )
        clean_out, _ = render_template_output(num_lang, lang)  # type: ignore[arg-type]
        cat = CORRUPTION_CATEGORIES[i % len(CORRUPTION_CATEGORIES)]
        bad_out = _corrupt_output(clean_out, num_lang, lang, cat, i)

        # Mix modes: 40% good on try 1, 30% bad on try 1 -> good on try 2, 30% bad on both tries -> template fallback
        roll = rng.random()
        if roll < 0.40:
            scripted = [clean_out]
        elif roll < 0.70:
            scripted = [bad_out, clean_out]
        else:
            scripted = [bad_out, bad_out]

        fake_client = FakeClient(responses=scripted, model_name="fake_client")
        rep = generate_report(num_lang, lang, client=fake_client)  # type: ignore[arg-type]

        reverify = verify(rep.content, num_lang, lang)  # type: ignore[arg-type]
        if not rep.verified or not reverify.ok:
            unverified_shipped += 1

        if rep.path == "llm":
            llm_accepted += 1
        else:
            template_fallbacks += 1

    return {
        "total_generated": total_reports,
        "unverified_shipped": unverified_shipped,
        "llm_accepted": llm_accepted,
        "template_fallbacks": template_fallbacks,
    }


def export_hindi_review_csv(output_path: Path | None = None) -> Path:
    """
    Generate `docs/genai_hindi_review.csv` listing all 10 Hindi templates (`hi/*.j2`) with columns:
    `template_id,text,reviewer,status,corrected_text` for the native-Hindi teammate.
    """
    import csv

    target = output_path or (REPO_ROOT / "docs" / "genai_hindi_review.csv")
    target.parent.mkdir(parents=True, exist_ok=True)
    hi_dir = TEMPLATES_DIR / "hi"

    rows: list[list[str]] = [["template_id", "text", "reviewer", "status", "corrected_text"]]
    for j2_path in sorted(hi_dir.glob("*.j2")):
        raw_lines = [
            line.strip()
            for line in j2_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("{#")
        ]
        template_text = " ".join(raw_lines)
        rows.append([j2_path.stem, template_text, "", "pending", ""])

    with open(target, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    return target


def export_hindi_rubric_csv(output_path: Path | None = None, seed: int = 42) -> Path:
    """
    Generate `docs/genai_hindi_rubric.csv` with 30 rendered reports (15 HI, 15 EN) and blank human scoring columns:
    `report_id,lang,period,trend,attendance_pct,tests_taken,body,factual_accuracy_1_5,tone_1_5,hindi_naturalness_1_5,reviewer,comments`.
    Scores are left blank per prompt rules until a human fills them.
    """
    import csv

    target = output_path or (REPO_ROOT / "docs" / "genai_hindi_rubric.csv")
    target.parent.mkdir(parents=True, exist_ok=True)
    fixtures = build_50_varied_numbers(seed=seed)

    headers = [
        "report_id",
        "lang",
        "period",
        "trend",
        "attendance_pct",
        "tests_taken",
        "body",
        "factual_accuracy_1_5",
        "tone_1_5",
        "hindi_naturalness_1_5",
        "reviewer",
        "comments",
    ]
    rows: list[list[Any]] = [headers]

    for idx in range(30):
        lang = "hi" if idx < 15 else "en"
        base = fixtures[idx]
        rep = generate_report(base, lang=lang, client=NullClient())  # type: ignore[arg-type]
        rows.append(
            [
                f"rep_{idx + 1:02d}_{lang}",
                lang,
                base.period,
                base.trend,
                base.attendance_pct,
                base.tests_taken,
                rep.content["body"],
                "",
                "",
                "",
                "",
                "",
            ]
        )

    with open(target, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    return target


def run_independent_set() -> dict[str, Any]:
    """Run the reviewer's 50 independent adversarial cases (tests/test_adversarial_independent.py).
    The harmless NFKC-equal 'fullwidth digits' case is excluded from the denominator and asserted to pass."""
    import importlib.util

    path = GENAI_DIR / "tests" / "test_adversarial_independent.py"
    spec = importlib.util.spec_from_file_location("_adv_independent", path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    total = caught = 0
    missed: list[str] = []
    harmless_ok = True
    for lang in ("en", "hi"):
        n, c = mod._mk(lang)
        for name, nb in mod._cases(lang, c["body"]):
            if nb == c["body"]:
                continue
            cc = dict(c)
            cc["body"] = nb
            cc["word_count"] = len(nb.split())
            ok = verify(cc, n, lang).ok
            if name in mod.HARMLESS:
                harmless_ok = harmless_ok and ok
                continue
            total += 1
            if ok:
                missed.append(f"{lang}:{name}")
            else:
                caught += 1
    return {"total": total, "caught": caught, "catch_rate": caught / total, "missed": missed, "harmless_ok": harmless_ok}


def write_genai_artifacts(version: str = "v1.0.0", seed: int = 42) -> dict[str, Any]:
    """
    Compute the deterministic GenAI metrics, validate against `contracts/metrics.schema.json`, and write
    `backend/app/genai/artifacts/<version>/{metrics.json,manifest.json,model_card.md}`.
    `genai_verifier_injected_error_catch_rate` is reported on (a) own fuzz (500), (b) the reviewer's independent
    set, (c) the second 100-case set; the contract value is the LOWER of (a) and (b) (and (c) is in the notes).
    """
    import hashlib

    import jsonschema

    from .adversarial_set2 import run_second_set

    fuzz_res = run_fuzz_500(seed=seed)
    ind_res = run_independent_set()
    set2_res = run_second_set()
    mix_res = run_1000_fake_client_mix(seed=seed)
    rate = min(float(fuzz_res["catch_rate"]), float(ind_res["catch_rate"]))

    new_results = [
        {
            "metric_key": "genai_verifier_injected_error_catch_rate",
            "module": "genai",
            "dataset_origin": "synthetic",
            "value": rate,
            "ci_low": rate,
            "ci_high": 1.0,
            "passed_bar": bool(rate >= 1.0),
            "notes": (
                f"value = min(a, b). (a) own fuzz {fuzz_res['caught']}/500 (own generator, not independent); "
                f"(b) reviewer-written independent set {ind_res['caught']}/{ind_res['total']} "
                f"(missed: {ind_res['missed'] or 'none'}; fullwidth-digit case excluded as NFKC-equal numbers); "
                f"(c) second 100-case set by Agent E {set2_res['caught']}/{set2_res['total']} "
                f"(still passing: {set2_res['still_passing'] or 'none'}). Not a proof of completeness."
            ),
        },
        {
            "metric_key": "genai_unverified_reports_shipped",
            "module": "genai",
            "dataset_origin": "synthetic",
            "value": float(mix_res["unverified_shipped"]),
            "ci_low": 0.0,
            "ci_high": 0.0,
            "passed_bar": bool(mix_res["unverified_shipped"] == 0),
            "notes": (
                f"n=1000 generated reports with FakeClient good/bad mixture; "
                f"llm_accepted={mix_res['llm_accepted']}, template_fallbacks={mix_res['template_fallbacks']}."
            ),
        },
    ]

    artifacts_dir = GENAI_DIR / "artifacts" / version
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = artifacts_dir / "metrics.json"

    metrics_doc = {
        "contract_version": "1.0.0",
        "model_version": version,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "generator_seed": seed,
        "results": new_results,
    }
    with open(REPO_ROOT / "contracts" / "metrics.schema.json", encoding="utf-8") as f:
        jsonschema.validate(instance=metrics_doc, schema=json.load(f))
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics_doc, f, ensure_ascii=False, indent=2)

    card_src = GENAI_DIR / "model_card.md"
    card_dst = artifacts_dir / "model_card.md"
    if card_src.exists():
        card_dst.write_bytes(card_src.read_bytes())
    else:
        card_dst.write_text("# GenAI report pipeline model card\n", encoding="utf-8")

    def sha(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()

    import platform

    manifest = {
        "contract_version": "1.0.0",
        "version": version,
        "trained_at": metrics_doc["evaluated_at"],
        "data_version": {"generator_seed": seed, "generator_config_sha256": hashlib.sha256(b"genai-no-training-data").hexdigest()},
        "files": [
            {"path": "metrics.json", "sha256": sha(metrics_path), "kind": "metrics"},
            {"path": "model_card.md", "sha256": sha(card_dst), "kind": "model_card"},
        ],
        # CCR-010: the manifest schema has no 'genai' module value and requires >= 1 model; there is no trained model here
        # (verifier + templates are code). 'tagging' is the closest allowed enum value; see docs/contract_change_requests.md.
        "models": [{
            "model_id": "genai_verified_report_pipeline_v1",
            "module": "tagging",
            "target": None,
            "feature_tier": "A",
            "features_used": [],
            "minor_eligible": True,
        }],
        "library_versions": {"python": platform.python_version(), "numpy": "not_used", "lightgbm": "not_used", "scikit_learn": "not_used"},
    }
    with open(REPO_ROOT / "contracts" / "artifact_manifest.schema.json", encoding="utf-8") as f:
        jsonschema.validate(instance=manifest, schema=json.load(f))
    with open(artifacts_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return {
        "metrics_path": str(metrics_path),
        "fuzz": fuzz_res,
        "independent": ind_res,
        "set2": set2_res,
        "mix": mix_res,
        "metrics_doc": metrics_doc,
    }


def check_ollama_models_available(required_models: tuple[str, ...] = ("qwen3:4b", "gemma3:4b")) -> dict[str, bool]:
    """Check which of the required Ollama models are currently pulled in `localhost:11434`."""
    import requests

    status = {m: False for m in required_models}
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2.0)
        if r.status_code == 200:
            installed = {m.get("name", "") for m in r.json().get("models", [])}
            for req in required_models:
                if req in installed or any(inst.startswith(req) for inst in installed):
                    status[req] = True
    except Exception:
        pass
    return status


def _get_vram_used_mb() -> int | None:
    """Query `nvidia-smi` for current GPU memory used in MiB (returns None if unavailable)."""
    import subprocess

    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return int(res.stdout.strip().splitlines()[0].strip())
    except Exception:
        pass
    return None


def _reading_level_heuristic(body: str) -> dict[str, float]:
    """Compute average words per sentence and max sentence length as a Class-8 reading-level heuristic."""
    sents = [s.strip() for s in re.split(r"[.।!?]+", body) if s.strip()]
    lengths = [len(s.split()) for s in sents] if sents else [0]
    return {
        "avg_sentence_words": round(sum(lengths) / max(1, len(lengths)), 2),
        "max_sentence_words": float(max(lengths)),
    }


def run_ollama_benchmark(
    models: tuple[str, ...] = ("qwen3:4b", "gemma3:4b"),
    seed: int = 42,
    n_fixtures: int = 50,
    include_cpu_run: bool = True,
) -> dict[str, Any]:
    """
    Run the local Ollama model benchmark on `2 * n_fixtures` reports (100 EN + 100 HI when n_fixtures=50)
    built from 50 varied `NumbersJson` instances.
    For each available model (and optionally CPU-only `num_gpu=0` on a subset or full set), records:
    - `valid_json_rate`
    - `first_try_verifier_pass_rate`
    - `fallback_rate_after_retry`
    - `latency_p50_ms`, `latency_p95_ms`
    - `avg_tokens_in`, `avg_tokens_out`
    - `vram_peak_mb` (via `nvidia-smi`)
    - `avg_word_count`, `avg_sentence_words`
    """
    import statistics

    avail = check_ollama_models_available(models)
    fixtures = build_50_varied_numbers(seed=seed)[:n_fixtures]
    results: dict[str, Any] = {"models_available": avail, "runs": {}}

    for model_name in models:
        if not avail.get(model_name, False):
            results["runs"][model_name] = {"status": "skipped_model_not_pulled"}
            continue

        modes: list[tuple[str, int | None, int]] = [("gpu", None, len(fixtures))]
        if include_cpu_run:
            # Measure CPU latency on 10 representative fixtures (20 reports) so it finishes cleanly
            modes.append(("cpu", 0, min(10, len(fixtures))))

        model_summary: dict[str, Any] = {}
        for mode_label, num_gpu_val, count_f in modes:
            client = OllamaClient(
                model_name=model_name,
                temperature=0.3,
                timeout_s=8.0,
                max_retries=0,
                num_gpu=num_gpu_val,
            )
            latencies: list[float] = []
            tokens_in_list: list[int] = []
            tokens_out_list: list[int] = []
            word_counts: list[int] = []
            sent_words: list[float] = []
            valid_json_count = 0
            first_try_pass_count = 0
            fallback_count = 0
            vram_peak = _get_vram_used_mb() or 0
            total_eval = 0

            for f_item in fixtures[:count_f]:
                for lang in ("en", "hi"):
                    total_eval += 1
                    rep = generate_report(f_item, lang=lang, client=client)  # type: ignore[arg-type]
                    latencies.append(rep.latency_ms)
                    tokens_in_list.append(rep.tokens_in)
                    tokens_out_list.append(rep.tokens_out)
                    word_counts.append(int(rep.content["word_count"]))
                    rl = _reading_level_heuristic(rep.content["body"])
                    sent_words.append(rl["avg_sentence_words"])

                    if not any("schema_error: invalid JSON" in fl for fl in rep.failures):
                        valid_json_count += 1
                    if rep.path == "llm" and len(rep.failures) == 0:
                        first_try_pass_count += 1
                    if rep.path == "template":
                        fallback_count += 1

                    cur_vram = _get_vram_used_mb()
                    if cur_vram is not None and cur_vram > vram_peak:
                        vram_peak = cur_vram

            sorted_lat = sorted(latencies)
            p50 = sorted_lat[len(sorted_lat) // 2] if sorted_lat else 0.0
            p95_idx = min(len(sorted_lat) - 1, int(0.95 * len(sorted_lat))) if sorted_lat else 0
            p95 = sorted_lat[p95_idx] if sorted_lat else 0.0

            model_summary[mode_label] = {
                "total_reports": total_eval,
                "valid_json_rate": round(valid_json_count / max(1, total_eval), 4),
                "first_try_verifier_pass_rate": round(first_try_pass_count / max(1, total_eval), 4),
                "fallback_rate_after_retry": round(fallback_count / max(1, total_eval), 4),
                "latency_p50_ms": round(p50, 2),
                "latency_p95_ms": round(p95, 2),
                "avg_tokens_in": round(statistics.mean(tokens_in_list), 1) if tokens_in_list else 0.0,
                "avg_tokens_out": round(statistics.mean(tokens_out_list), 1) if tokens_out_list else 0.0,
                "vram_peak_mb": vram_peak,
                "avg_word_count": round(statistics.mean(word_counts), 1) if word_counts else 0.0,
                "avg_sentence_words": round(statistics.mean(sent_words), 2) if sent_words else 0.0,
            }
        results["runs"][model_name] = model_summary

    return results


if __name__ == "__main__":
    export_hindi_review_csv()
    export_hindi_rubric_csv()
    res = write_genai_artifacts()
    print("Fuzz 500 catch rate:", res["fuzz"]["catch_rate"])
    print("Unverified shipped (1000 mix):", res["mix"]["unverified_shipped"])
    print("Ollama model availability:", check_ollama_models_available())
