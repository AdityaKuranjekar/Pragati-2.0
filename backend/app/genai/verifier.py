# Purpose: Deterministic verifier (`verify`) for parent reports in English and Hindi.
# contract_version: 1.0.0
# Implements: TECH_PLAN §3 #7, §11 (GenAI verifier), §15 (Well-being), and R1_E_genai_reports.md #4.

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from typing import Any

import jsonschema

from .verifier_extra import extra_checks
from .models import (
    Lang,
    NumbersJson,
    VerifyResult,
    get_report_output_validator,
    load_reason_templates_contract,
    load_report_output_schema,
    load_topics_contract,
)

# Zero-width and invisible formatting characters used in Unicode evasion attacks
ZERO_WIDTH_CHARS: frozenset[str] = frozenset(
    {
        "\u200b",  # zero-width space
        "\u200c",  # zero-width non-joiner
        "\u200d",  # zero-width joiner
        "\u2060",  # word joiner
        "\ufeff",  # zero-width no-break space / BOM
        "\u00ad",  # soft hyphen
        "\u180e",  # Mongolian vowel separator
    }
)

# Common Cyrillic and Greek homoglyphs mapping to Latin characters
CONFUSABLE_MAP: dict[str, str] = {
    "а": "a", "А": "A",
    "е": "e", "Е": "E",
    "о": "o", "О": "O",
    "р": "p", "Р": "P",
    "с": "c", "С": "C",
    "у": "y", "У": "Y",
    "х": "x", "Х": "X",
    "і": "i", "І": "I",
    "ј": "j", "Ј": "J",
    "ѕ": "s", "Ѕ": "S",
    "α": "a", "Α": "A",
    "β": "b", "Β": "B",
    "ε": "e", "Ε": "E",
    "ι": "i", "Ι": "I",
    "κ": "k", "Κ": "K",
    "ν": "v", "Ν": "N",
    "ο": "o", "Ο": "O",
    "ρ": "p", "Ρ": "P",
    "τ": "t", "Τ": "T",
    "υ": "u", "Υ": "Y",
    "χ": "x", "Χ": "X",
}

DEVANAGARI_DIGITS_MAP = str.maketrans("०१२३४५६७८९", "0123456789")

# English number words (0..100) mapped to integer values
EN_NUMBER_WORDS: dict[str, int] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
    "thrice": 3,
}

# Hindi number words mapped to integer values
HI_NUMBER_WORDS: dict[str, int] = {
    "शून्य": 0, "एक": 1, "दो": 2, "तीन": 3, "चार": 4,
    "पांच": 5, "पाँच": 5, "छह": 6, "सात": 7, "आठ": 8, "नौ": 9,
    "दस": 10, "ग्यारह": 11, "बारह": 12, "तेरह": 13, "चौदह": 14,
    "पंद्रह": 15, "सोलह": 16, "सत्रह": 17, "अठारह": 18, "उन्नीस": 19,
    "बीस": 20, "पच्चीस": 25, "तीस": 30, "पैंतीस": 35, "चालीस": 40,
    "पैंतालीस": 45, "पचास": 50, "पचपन": 55, "साठ": 60, "पैंसठ": 65,
    "सत्तर": 70, "पचहत्तर": 75, "अस्सी": 80, "पचासी": 85, "नब्बे": 90,
    "पचानवे": 95, "सौ": 100,
}

# Narrative structural words ("two simple habits", "First", "Second", "step by step") permitted in report prose
NARRATIVE_NUMBER_WORDS_ALLOW: dict[str, set[str]] = {
    "en": {"one", "two", "first", "second"},
    "hi": {"एक", "दो", "पहला", "दूसरा", "तीसरा"},
}

# Extended banned patterns (ranks, comparisons, risk/dropout, mental-health guesses, inflections)
EXTRA_BANNED_PATTERNS_EN: tuple[str, ...] = (
    r"\bdropping\s+out\b",
    r"\bdropped\s+out\b",
    r"\bdropout\s+risk\b",
    r"\bretention\s+risk\b",
    r"\bat\s+risk\s+of\b",
    r"\bhigh\s+risk\b",
    r"\bfailing\b",
    r"\bfailed\b",
    r"\bfails\b",
    r"\branked\b",
    r"\branks\b",
    r"\btopper\b",
    r"\btoppers\b",
    r"\bpercentile\s+rank\b",
    r"\bbetter\s+than\b",
    r"\bworse\s+than\b",
    r"\bother\s+students\b",
    r"\bother\s+children\b",
    r"\bpeer\s+comparison\b",
    r"\bcompared\s+to\b",
    r"\bcompared\s+with\b",
    r"\bcomparing\b",
    r"\blaziest\b",
    r"\blaziness\b",
    r"\bcarelessness\b",
    r"\bdefaulters\b",
    r"\bmental\s+illness\b",
    r"\banxiety\s+disorder\b",
    r"\bpsychiatric\b",
    r"\bsuicide\b",
    r"\bworthless\b",
    r"\bincompetent\b",
)

EXTRA_BANNED_SUBSTRINGS_HI: tuple[str, ...] = (
    "बाकी बच्चों",
    "अन्य छात्रों",
    "दूसरे बच्चों",
    "दूसरे छात्रों",
    "से बेहतर",
    "से कमतर",
    "से पीछे",
    "अवसाद",
    "आत्महत्या",
    "मानसिक रोग",
    "मनोरोग",
    "जोखिम",
    "छोड़ने का खतरा",
    "टॉपर",
    "फिसड्डी",
    "नालायक",
    "बेकार छात्र",
)

# Home tip keyword signatures for verification check (h)
HOME_TIP_SIGNATURES: dict[str, dict[str, tuple[str, ...]]] = {
    "tip_fixed_revision_slot": {
        "en": ("fixed daily revision", "revision slot", "quiet desk"),
        "hi": ("निश्चित दोहराव", "शांत स्थान पर निश्चित", "दोहराव समय"),
    },
    "tip_mistake_notebook_review": {
        "en": ("mistake notebook", "error notebook"),
        "hi": ("गलती नोटबुक", "त्रुटि नोटबुक"),
    },
    "tip_sleep_and_rest_day": {
        "en": ("nightly sleep", "weekly rest day", "adequate sleep"),
        "hi": ("पर्याप्त नींद", "विश्राम दिवस"),
    },
    "tip_formula_flashcards": {
        "en": ("formula", "flashcard", "flashcards"),
        "hi": ("सूत्रों को", "फ्लैशकार्ड"),
    },
    "tip_timed_practice_set": {
        "en": ("timed practice set", "timed set"),
        "hi": ("समयबद्ध अभ्यास सेट", "बिना रुकावट"),
    },
    "tip_ask_faculty_doubts": {
        "en": ("ask faculty doubts", "unsolved questions", "doubts promptly"),
        "hi": ("डाउट पूछें", "अनसुलझे प्रश्नों"),
    },
    "tip_regular_class_attendance": {
        "en": ("prioritise regular class attendance", "lectures stay connected"),
        "hi": ("नियमित कक्षा उपस्थिति बनाए रखें", "अध्याय क्रम से समझ आएँ"),
    },
    "tip_encourage_steady_effort": {
        "en": ("encourage steady effort", "praise consistent daily study"),
        "hi": ("निरंतर प्रयास की सराहना", "शांत अध्ययन के लिए प्रोत्साहित"),
    },
}

# Trend keyword expectations for check (g)
TREND_REQUIRED_MARKERS: dict[str, dict[str, tuple[str, ...]]] = {
    "improving": {
        "en": ("improving", "improvement", "upward", "growing"),
        "hi": ("सुधार", "बेहतर", "सकारात्मक प्रगति", "बढ़त"),
    },
    "steady": {
        "en": ("steady", "consistent", "balanced", "stable"),
        "hi": ("स्थिर", "संतुलित", "नियमित गति"),
    },
    "declining": {
        "en": ("declining", "softened", "dipped", "slowed"),
        "hi": ("धीमी", "कमी", "गिरावट", "नरम"),
    },
}

TREND_CONTRADICTIONS: dict[str, dict[str, tuple[str, ...]]] = {
    "improving": {
        "en": ("declining trend", "downward trend", "scores have softened"),
        "hi": ("गति थोड़ी धीमी रही है", "क्रमिक गिरावट", "प्रदर्शन में गिरावट"),
    },
    "steady": {
        "en": ("declining trend", "improving trend", "downward trend"),
        "hi": ("गति थोड़ी धीमी रही है", "निरंतर सुधार दिखा है", "क्रमिक गिरावट"),
    },
    "declining": {
        "en": ("improving trend", "upward trend", "rapidly improving"),
        "hi": ("निरंतर सुधार दिखा है", "उत्साहजनक सुधार", "तेजी से सुधार"),
    },
}

# Common allowed capitalized words in English parent reports (sentence starts, headings, educational terms)
BASE_ALLOWED_CAP_WORDS_EN: frozenset[str] = frozenset(
    {
        "A", "An", "And", "Across", "Additional", "All", "Also", "Although", "Always", "Are", "As", "At",
        "Academic", "Assessment", "Assessments", "Attendance", "Batch", "Biology", "Botany", "Building",
        "By", "Calm", "Chapter", "Chapters", "Chemistry", "Class", "Classroom", "Clear", "Comfortable",
        "Consistent", "Continued", "Continuing", "Core", "Current", "Currently", "Daily", "Dear", "During",
        "Each", "Early", "Encourage", "Encouraging", "Encouragingly", "English", "Every", "Everyone", "Exam",
        "Extra", "Faculty", "First", "Focus", "Focused", "For", "Foundational", "From", "Further",
        "Gentle", "Good", "Guided", "Happy", "Has", "Have", "Help", "Helpful", "Helping", "Here", "Hindi",
        "Home", "How", "If", "In", "Initial", "Institute", "Is", "It", "Its", "JEE", "Keep", "Keeping",
        "Key", "Learning", "Lecture", "Lectures", "Main", "Maintain", "Maintaining", "Make", "Mathematics",
        "Mentor", "Mentors", "Month", "More", "Most", "NEET", "New", "Next", "No", "Note", "Notes", "Now",
        "Of", "On", "Once", "One", "Ongoing", "Only", "Or", "Our", "Over", "Overall", "Pace", "Pacing",
        "Parent", "Parents", "Participation", "Path", "Pattern", "Percentage", "Performance", "Period",
        "Physics", "Place", "Placed", "Plan", "Planned", "Please", "Positive", "Practice", "Practise",
        "Prepared", "Priority", "Problem", "Problems", "Progress", "Put", "Questions", "Reach", "Reading",
        "Ready", "Reassuring", "Recent", "Recently", "Recommended", "Recorded", "Regular", "Regularly",
        "Remain", "Remains", "Report", "Reporting", "Rest", "Results", "Review", "Reviewing", "Reviews",
        "Revision", "Right", "Routine", "Routines", "Schedule", "Scheduled", "Score", "Scores", "Second",
        "Section", "Session", "Sessions", "Set", "Sets", "Settle", "Settling", "Share", "Shared", "Sharing",
        "Sheet", "Short", "Show", "Showed", "Showing", "Shows", "Simple", "Since", "Sleep", "Slot", "Slots",
        "Smooth", "Smoothly", "So", "Solid", "Solving", "Some", "Specific", "Speed", "Stage", "Start",
        "Stay", "Stayed", "Steady", "Step", "Steps", "Still", "Strength", "Strengthen", "Strengths",
        "Strong", "Stronger", "Structured", "Student", "Study", "Subject", "Subjects", "Summary", "Support",
        "Supporting", "Supportive", "Syllabus", "Take", "Taken", "Taking", "Targeted", "Team", "Teaching",
        "Term", "Test", "Testing", "Tests", "Thank", "That", "The", "Their", "Them", "There", "These",
        "They", "This", "Those", "Three", "Through", "Throughout", "Time", "Timed", "Tip", "Tips", "To",
        "Together", "Took", "Topic", "Topics", "Total", "Toward", "Trajectory", "Trend", "Two", "UG",
        "Understanding", "Unit", "Units", "Up", "Upcoming", "Update", "Updated", "Us", "Use", "Useful",
        "Using", "Very", "Visible", "Warm", "Was", "Way", "Ways", "We", "Week", "Weekly", "Weeks",
        "Welcome", "Well", "Were", "What", "When", "Whenever", "Where", "Which", "While", "Window",
        "With", "Within", "Work", "Working", "Worksheet", "Worksheets", "Writing", "You", "Your", "Zoology",
    }
)

# Explicit list of common Indian/English first and last names and coaching brand names to reject if leaked
FORBIDDEN_PROPER_NAMES_HI: tuple[str, ...] = (
    "आरव", "रोहन", "राहुल", "प्रिया", "नेहा", "आदित्य", "अंकित", "अंकिता", "ध्रुवी",
    "शर्मा", "वर्मा", "कुमार", "सिंह", "गुप्ता", "पटना", "कोटा", "एलन", "फिजिक्सवाला",
)

FORBIDDEN_PROPER_NAMES_EN: frozenset[str] = frozenset(
    {
        "aarav", "rohan", "rahul", "priya", "neha", "aditya", "ankit", "ankita", "dhruvi",
        "vihaan", "ananya", "diya", "ishaan", "kabir", "meera", "riya", "sanya", "vikram",
        "sharma", "verma", "kumar", "singh", "gupta", "patel", "agarwal", "mishra", "jha",
        "allen", "aakash", "resonances", "fiitjee", "pw", "physicswallah", "narayana",
        "chaitanya", "vidyamandir", "bansal", "vibrant",
    }
)


def strip_zero_width(text: str) -> str:
    return "".join(ch for ch in text if ch not in ZERO_WIDTH_CHARS)


def has_zero_width_or_control(text: str) -> bool:
    for ch in text:
        if ch in ZERO_WIDTH_CHARS:
            return True
        cat = unicodedata.category(ch)
        if cat in ("Cf", "Cc") and ch not in ("\n", "\r", "\t"):
            return True
    return False


def has_confusable_homoglyphs(text: str) -> bool:
    return any(ch in CONFUSABLE_MAP for ch in text)


def normalize_digits_and_percent(text: str) -> str:
    s = unicodedata.normalize("NFKC", strip_zero_width(text))
    s = s.translate(DEVANAGARI_DIGITS_MAP)
    s = re.sub(r"(\d+(?:\.\d+)?)\s*(?:प्रतिशत|फीसदी|percent|per\s+cent)\b", r"\1%", s, flags=re.IGNORECASE)
    return s


def _canonical_number_token(val: float | int | str) -> set[str]:
    """Return canonical numeric string representations (e.g. 85.0 -> {'85', '85.0'})."""
    out: set[str] = set()
    try:
        f = float(val)
        if f.is_integer():
            i = int(round(f))
            out.add(str(i))
            out.add(f"{i}.0")
        else:
            out.add(str(round(f, 2)))
            out.add(f"{f:.1f}")
            out.add(f"{f:.2f}".rstrip("0").rstrip("."))
    except (ValueError, TypeError):
        out.add(str(val))
    return out


def extract_allowed_number_tokens(numbers: NumbersJson) -> set[str]:
    allowed: set[str] = set()
    allowed |= _canonical_number_token(numbers.attendance_pct)
    allowed |= _canonical_number_token(numbers.tests_taken)

    # Note: numbers embedded inside `period` (e.g. 2026-W50) or inside `topic_item` names (e.g. SN1, 1D, 10% Law)
    # are valid ONLY when they appear inside the exact `period` or topic string (which `verify()` masks out before
    # scanning for standalone numbers). They must NOT be whitelisted as free-standing numbers in the report prose.
    return allowed


@lru_cache(maxsize=1)
def _all_syllabus_topics() -> list[dict[str, Any]]:
    topics_map = load_topics_contract()
    result: list[dict[str, Any]] = []
    for tid, t in topics_map.items():
        lvl = str(t.get("level", ""))
        n_en = _norm_phrase(str(t["name_en"]))
        n_hi = _norm_phrase(str(t["name_hi"]))
        re_en = re.compile(rf"\b{re.escape(n_en)}\b") if len(n_en) >= 5 else None
        re_hi = re.compile(rf"(?<![\u0900-\u097F\w]){re.escape(n_hi)}(?![\u0900-\u097F\w])") if len(n_hi) >= 4 else None
        result.append(
            {
                "id": tid,
                "level": lvl,
                "name_en": str(t["name_en"]),
                "name_hi": str(t["name_hi"]),
                "norm_en": n_en,
                "norm_hi": n_hi,
                "re_en": re_en,
                "re_hi": re_hi,
            }
        )
    return result


@lru_cache(maxsize=1)
def _compiled_banned_lexicon() -> dict[str, Any]:
    reasons_contract = load_reason_templates_contract()
    banned_en: list[str] = reasons_contract["banned_words"]["en"]
    banned_hi: list[str] = reasons_contract["banned_words"]["hi"]

    en_regexes = [(bw, re.compile(rf"\b{re.escape(_norm_phrase(bw))}\b")) for bw in banned_en]
    extra_en_regexes = [(pat, re.compile(pat, flags=re.IGNORECASE)) for pat in EXTRA_BANNED_PATTERNS_EN]
    hi_norms = [(bw_hi, _norm_phrase(bw_hi)) for bw_hi in banned_hi]
    extra_hi_norms = [(sub_hi, _norm_phrase(sub_hi)) for sub_hi in EXTRA_BANNED_SUBSTRINGS_HI]
    return {
        "en_regexes": en_regexes,
        "extra_en_regexes": extra_en_regexes,
        "hi_norms": hi_norms,
        "extra_hi_norms": extra_hi_norms,
    }


def _norm_phrase(s: str) -> str:
    s = unicodedata.normalize("NFKC", strip_zero_width(s)).translate(DEVANAGARI_DIGITS_MAP).lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def verify(
    output: dict[str, Any] | str,
    numbers: NumbersJson | dict[str, Any],
    lang: Lang,
) -> VerifyResult:
    """
    Deterministic 8-stage verifier:
    (a) JSON valid against `contracts/report_output.schema.json`
    (b) Every number in text (digits, Devanagari digits, number words, % variants) appears in `numbers`
    (c) Every topic mentioned is in the allowed list (`numbers.strengths` + `numbers.focus`);
        every allowed focus topic appears at most once; unallowed syllabus topics are rejected
    (d) Both `{STUDENT}` and `{INSTITUTE}` placeholders present; no other proper names
        (reject capitalised tokens not in allow-list and known proper names)
    (e) Banned lexicon from `contracts/reason_templates.yaml` (EN & HI) + ranks/comparisons/risk/mental-health
    (f) Length 80-180 words (whitespace tokens) and `word_count` matches actual word count; max sentence <= 22 words
    (g) Trend word consistent with `numbers.trend`
    (h) Both `home_tips` present in body
    """
    failures: list[str] = []

    if isinstance(numbers, dict):
        try:
            numbers_obj = NumbersJson.from_dict(numbers)
        except Exception as exc:
            return VerifyResult(ok=False, failures=[f"invalid_numbers_input: {exc}"])
    else:
        numbers_obj = numbers

    # Parse JSON if passed as string
    if isinstance(output, str):
        if not output.strip():
            return VerifyResult(ok=False, failures=["schema_error: empty output string"])
        try:
            output_dict = json.loads(output)
        except Exception as exc:
            return VerifyResult(ok=False, failures=[f"schema_error: invalid JSON ({exc})"])
    elif isinstance(output, dict):
        output_dict = output
    else:
        return VerifyResult(ok=False, failures=["schema_error: output must be dict or JSON string"])

    # (a) JSON Schema validation against contracts/report_output.schema.json
    try:
        get_report_output_validator().validate(output_dict)
    except jsonschema.ValidationError as exc:
        failures.append(f"schema_error: {exc.message}")
        return VerifyResult(ok=False, failures=failures)

    title: str = str(output_dict.get("title", ""))
    body: str = str(output_dict.get("body", ""))
    declared_word_count: int = int(output_dict.get("word_count", 0))
    combined_text = f"{title}\n{body}"

    # Reject Unicode evasion (zero-width characters or homoglyph confusables)
    if has_zero_width_or_control(combined_text):
        failures.append("unicode_evasion: zero-width or control character detected")
    if has_confusable_homoglyphs(combined_text):
        failures.append("unicode_evasion: Cyrillic/Greek homoglyph confusable detected")

    # Script check: Hindi report must contain Devanagari characters; English report must not contain Devanagari
    has_devanagari = bool(re.search(r"[\u0900-\u097F]", body))
    if lang == "hi" and not has_devanagari:
        failures.append("script_error: Hindi report body lacks Devanagari script")
    elif lang == "en" and has_devanagari:
        failures.append("script_error: English report body contains unexpected Devanagari script")

    # Mask allowed topic names and period when scanning for numbers/proper-names so topic digits (like SN1, 10% Law)
    # and topic proper nouns (Newton's, Carnot) are handled cleanly alongside general text.
    allowed_topics = list(numbers_obj.strengths) + list(numbers_obj.focus)
    allowed_en_names = {t.name_en for t in allowed_topics}
    allowed_hi_names = {t.name_hi for t in allowed_topics}
    allowed_norm_en = {_norm_phrase(t.name_en) for t in allowed_topics}
    allowed_norm_hi = {_norm_phrase(t.name_hi) for t in allowed_topics}

    # (b) Numeric verification
    allowed_numbers = extract_allowed_number_tokens(numbers_obj)
    norm_combined = normalize_digits_and_percent(combined_text)

    # Remove exact allowed topic names and period before extracting free-standing numbers
    masked_for_numbers = norm_combined
    for t in allowed_topics:
        masked_for_numbers = masked_for_numbers.replace(normalize_digits_and_percent(t.name_en), " ")
        masked_for_numbers = masked_for_numbers.replace(normalize_digits_and_percent(t.name_hi), " ")
    masked_for_numbers = masked_for_numbers.replace(normalize_digits_and_percent(numbers_obj.period), " ")

    found_numbers = re.findall(r"\d+(?:\.\d+)?", masked_for_numbers)
    for num_str in found_numbers:
        if num_str not in allowed_numbers:
            failures.append(f"unverified_number: '{num_str}' not in allowed numbers {sorted(allowed_numbers)}")

    # Check number words in English and Hindi (excluding structural narrative words like "two tips", "first", "second")
    norm_lower = _norm_phrase(masked_for_numbers)
    if lang == "en":
        for word, val in EN_NUMBER_WORDS.items():
            if word in NARRATIVE_NUMBER_WORDS_ALLOW["en"]:
                continue
            if re.search(rf"\b{re.escape(word)}\b", norm_lower):
                if str(val) not in allowed_numbers:
                    failures.append(f"unverified_number_word: '{word}' ({val}) not in allowed numbers")
    else:
        tokens_hi = re.split(r"[\s,।.;:!?()\[\]\"']+", norm_lower)
        for tok in tokens_hi:
            if tok in HI_NUMBER_WORDS and tok not in NARRATIVE_NUMBER_WORDS_ALLOW["hi"]:
                val = HI_NUMBER_WORDS[tok]
                if str(val) not in allowed_numbers:
                    failures.append(f"unverified_number_word: '{tok}' ({val}) not in allowed numbers")

    # (c) Topic verification:
    # 1. Mask out the exact allowed topic names from the text first, then check that no OTHER topic
    #    from contracts/topics.yaml appears in the remaining text.
    masked_for_topics = combined_text
    # Sort allowed topics longest-first so longer names are masked before shorter substrings
    for t in sorted(allowed_topics, key=lambda x: max(len(x.name_en), len(x.name_hi)), reverse=True):
        masked_for_topics = re.sub(re.escape(t.name_en), " ", masked_for_topics, flags=re.IGNORECASE)
        masked_for_topics = masked_for_topics.replace(t.name_hi, " ")
    norm_masked_topics = _norm_phrase(masked_for_topics)
    norm_full_text = _norm_phrase(combined_text)

    for syl_topic in _all_syllabus_topics():
        if syl_topic["level"] == "subject":
            continue
        t_norm_en = syl_topic["norm_en"]
        t_norm_hi = syl_topic["norm_hi"]
        re_en = syl_topic["re_en"]
        re_hi = syl_topic["re_hi"]
        if re_en is not None and t_norm_en not in allowed_norm_en:
            if t_norm_en in norm_masked_topics and re_en.search(norm_masked_topics):
                failures.append(f"unallowed_topic_en: '{syl_topic['name_en']}' is not in numbers.strengths/focus")
        if re_hi is not None and t_norm_hi not in allowed_norm_hi:
            if t_norm_hi in norm_masked_topics and re_hi.search(norm_masked_topics):
                failures.append(f"unallowed_topic_hi: '{syl_topic['name_hi']}' is not in numbers.strengths/focus")

    # 2. Every allowed focus topic appears at most once in body (and strengths/focus are in the matching language)
    #    Allow either the exact language-matched topic name (`name_en` for en, `name_hi` for hi) OR the cross-language
    #    counterpart from the same `TopicItem` so that `topic_item` mentions in either EN or HI are recognised,
    #    while still enforcing that each focus topic is mentioned at most once in total.
    norm_body = _norm_phrase(body)
    for f_item in numbers_obj.focus:
        primary_name = _norm_phrase(f_item.name_en if lang == "en" else f_item.name_hi)
        alt_name = _norm_phrase(f_item.name_hi if lang == "en" else f_item.name_en)
        c_primary = len(re.findall(re.escape(primary_name), norm_body)) if primary_name else 0
        c_alt = len(re.findall(re.escape(alt_name), norm_body)) if (alt_name and alt_name != primary_name) else 0
        total_count = c_primary + c_alt
        if total_count == 0:
            failures.append(f"missing_focus_topic: focus topic '{primary_name}' was not mentioned")
        elif total_count > 1:
            failures.append(f"duplicate_focus_topic: focus topic '{primary_name}' appeared {total_count} times (max 1)")

    for s_item in numbers_obj.strengths:
        primary_name = _norm_phrase(s_item.name_en if lang == "en" else s_item.name_hi)
        alt_name = _norm_phrase(s_item.name_hi if lang == "en" else s_item.name_en)
        if primary_name not in norm_body and alt_name not in norm_body:
            failures.append(f"missing_strength_topic: strength topic '{primary_name}' was not mentioned")

    # (d) Placeholders & Proper-name leak check
    if "{STUDENT}" not in body:
        failures.append("missing_placeholder: '{STUDENT}' must appear in body")
    if "{INSTITUTE}" not in body:
        failures.append("missing_placeholder: '{INSTITUTE}' must appear in body")

    # Check for any brace placeholders: `{STUDENT}` and `{INSTITUTE}` are allowed ONLY in `body` (not `title`),
    # and no other `{...}` placeholders may appear anywhere.
    title_placeholders = set(re.findall(r"\{[A-Za-z0-9_]+\}", title))
    if title_placeholders:
        failures.append(f"placeholder_in_title: {sorted(title_placeholders)}")
    other_placeholders = set(re.findall(r"\{[A-Za-z0-9_]+\}", combined_text)) - {"{STUDENT}", "{INSTITUTE}"}
    if other_placeholders:
        failures.append(f"unknown_placeholder: {sorted(other_placeholders)}")

    # Build dynamic capitalized token allow-list from allowed topics and period
    dynamic_cap_allow = set(BASE_ALLOWED_CAP_WORDS_EN)
    for item in allowed_topics:
        for s_name in (item.name_en, item.name_hi):
            for w in re.findall(r"[A-Za-z][A-Za-z0-9'-]*", s_name):
                dynamic_cap_allow.add(w)
                dynamic_cap_allow.add(w.strip("'"))
                for part in w.split("-"):
                    if part:
                        dynamic_cap_allow.add(part)
    for w in re.findall(r"[A-Za-z][A-Za-z0-9'-]*", numbers_obj.period):
        dynamic_cap_allow.add(w)

    text_without_placeholders = combined_text.replace("{STUDENT}", "Student").replace("{INSTITUTE}", "Institute")
    for cap_tok in re.findall(r"\b[A-Z][A-Za-z'-]*\b", text_without_placeholders):
        clean_tok = cap_tok.rstrip("'s").rstrip("'")
        if clean_tok not in dynamic_cap_allow and cap_tok not in dynamic_cap_allow:
            failures.append(f"unallowed_proper_name_or_cap_token: '{cap_tok}'")

    # Also check lowercase forbidden proper names in EN and HI
    words_lower = set(re.findall(r"[a-z]+", norm_full_text))
    leaked_en_names = words_lower & FORBIDDEN_PROPER_NAMES_EN
    if leaked_en_names:
        failures.append(f"proper_name_leak_en: {sorted(leaked_en_names)}")
    for hi_name in FORBIDDEN_PROPER_NAMES_HI:
        if hi_name in norm_full_text:
            failures.append(f"proper_name_leak_hi: '{hi_name}'")

    # (e) Banned lexicon from contracts/reason_templates.yaml + extended patterns
    compiled_banned = _compiled_banned_lexicon()
    collapsed_en = re.sub(r"[\s\-_]+", " ", norm_full_text)
    for bw, bw_re in compiled_banned["en_regexes"]:
        if bw_re.search(collapsed_en):
            failures.append(f"banned_word_en: '{bw}'")

    for pat, pat_re in compiled_banned["extra_en_regexes"]:
        if pat_re.search(collapsed_en):
            failures.append(f"banned_pattern_en: '{pat}'")

    for bw_hi, bw_hi_norm in compiled_banned["hi_norms"]:
        if bw_hi_norm in collapsed_en:
            failures.append(f"banned_word_hi: '{bw_hi}'")

    for sub_hi, sub_hi_norm in compiled_banned["extra_hi_norms"]:
        if sub_hi_norm in collapsed_en:
            failures.append(f"banned_pattern_hi: '{sub_hi}'")

    # (f) Word count 80..180 and sentence length <= 22 words (excluding multi-word topic names expanded in-place)
    words = body.split()
    actual_word_count = len(words)
    if not (80 <= actual_word_count <= 180):
        failures.append(f"length_error: body has {actual_word_count} words (must be 80..180)")
    if declared_word_count != actual_word_count:
        failures.append(
            f"word_count_mismatch: declared word_count={declared_word_count} != actual={actual_word_count}"
        )

    # Sentence length check (collapse allowed multi-word topic names to a single token so long NTA topic titles
    # don't artificially inflate sentence word counts)
    body_for_sentences = body
    for t in allowed_topics:
        body_for_sentences = body_for_sentences.replace(t.name_en, "TOPIC")
        body_for_sentences = body_for_sentences.replace(t.name_hi, "TOPIC")
    # Protect decimal numbers like 85.5% before splitting on sentence punctuation
    body_for_sentences = re.sub(r"(\d)\.(\d)", r"\1_\2", body_for_sentences)
    sentences = [s.strip() for s in re.split(r"[.।!?]+", body_for_sentences) if s.strip()]
    for sent in sentences:
        sw_count = len(sent.split())
        if sw_count > 22:
            failures.append(f"reading_level_sentence_too_long: {sw_count} words (> 22) in '{sent[:60]}...'")

    # (g) Trend consistency
    trend = numbers_obj.trend
    req_markers = TREND_REQUIRED_MARKERS[trend][lang]
    if not any(_norm_phrase(m) in norm_body for m in req_markers):
        failures.append(f"trend_mismatch: missing required '{trend}' marker ({req_markers}) in {lang} body")

    contradictions = TREND_CONTRADICTIONS[trend][lang]
    for c_phrase in contradictions:
        if _norm_phrase(c_phrase) in norm_body:
            failures.append(f"trend_contradiction: found '{c_phrase}' when trend='{trend}'")

    # (h) Both home tips present in body
    for tip_id in numbers_obj.home_tips:
        sigs = HOME_TIP_SIGNATURES.get(tip_id, {}).get(lang, ())
        if sigs and not any(_norm_phrase(sig) in norm_body for sig in sigs):
            failures.append(f"missing_home_tip: tip '{tip_id}' signature not found in {lang} body")

    extra_checks(
        combined_text=combined_text,
        body=body,
        norm_full_text=norm_full_text,
        trend=trend,
        allowed_topics=allowed_topics,
        period=numbers_obj.period,
        failures=failures,
    )

    return VerifyResult(ok=(len(failures) == 0), failures=failures)
