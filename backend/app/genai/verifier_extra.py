# Purpose: R1_E2 verifier additions (extended lexicon, trend vocabulary, study-phrase vocabulary, injection/charset).
# contract_version: 1.0.0
# Used by verifier.verify(); kept in a separate module so the original 8 checks stay untouched. See CCR-010.

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

ZERO_WIDTH = frozenset({"​", "‌", "‍", "⁠", "﻿", "­", "᠎"})
_HI_FOLD_TABLE = {ord("़"): None, ord("ँ"): "ं"}


def hi_fold(s: str) -> str:
    """NFKC, strip zero-width, drop nukta, chandrabindu -> anusvara, lower, collapse spaces/hyphens/underscores."""
    s = "".join(ch for ch in s if ch not in ZERO_WIDTH)
    s = unicodedata.normalize("NFKC", s).lower().translate(_HI_FOLD_TABLE)
    return re.sub(r"[\s\-_]+", " ", s).strip()


@lru_cache(maxsize=1)
def compiled_extra_lexicon() -> dict[str, Any]:
    import yaml

    path = Path(__file__).resolve().parent / "lexicon_extra.yaml"
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)

    def comp_en(pats: list[str]) -> list[re.Pattern[str]]:
        return [re.compile(p, flags=re.IGNORECASE) for p in pats]

    def comp_hi(words: list[str]) -> list[re.Pattern[str]]:
        return [re.compile(r"(?<![ऀ-ॿ])" + re.escape(hi_fold(w))) for w in words]

    def merge(regs: list[re.Pattern[str]]) -> list[re.Pattern[str]]:
        return [re.compile("|".join(f"(?:{r.pattern})" for r in regs), flags=re.IGNORECASE)]

    banned = {c: merge(comp_en(v.get("en", [])) + comp_hi(v.get("hi", []))) for c, v in doc["banned"].items()}
    trend = {t: merge(comp_en(v.get("en", [])) + comp_hi(v.get("hi", []))) for t, v in doc["trend_vocab"].items()}
    return {"banned": banned, "trend": trend}


STUDY_VERB_RE = re.compile(
    r"\b(revis\w*|practi[cs]\w*|focus\w*|study\w*|review\w*|learn\w*|work(?:ing)? on|brush up|drill\w*|"
    r"memori\w*|read\w*|solv\w*|master\w*)\b"
    r"|(?<![ऀ-ॿ])(दोहर|अभ्यास|ध्यान|पढ़|पढ|रिवीज|पुनरावलोकन|याद कर|सीख|हल कर|हल कीजिए|समझें|समझिए)"
)
WORD_RE = re.compile(r"[a-z][a-z'\-]*|[ऀ-ॣ०-ॿ]+")


@lru_cache(maxsize=1)
def template_vocabulary() -> frozenset[str]:
    """Every word used by the human-written templates and the home-tip catalog: the only vocabulary allowed in
    study-instruction sentences (besides allowed topic names)."""
    from .models import TEMPLATES_DIR
    from .pipeline import HOME_TIPS_CATALOG, TREND_HI_LABELS

    texts: list[str] = []
    for path in TEMPLATES_DIR.glob("*/*.j2"):
        t = path.read_text(encoding="utf-8")
        t = re.sub(r"\{#.*?#\}|\{%.*?%\}|\{\{.*?\}\}|\{[A-Z_]+\}", " ", t, flags=re.S)
        texts.append(t)
    for tip in HOME_TIPS_CATALOG.values():
        texts.extend(tip.values())
    texts.extend(TREND_HI_LABELS.values())
    words: set[str] = set()
    for t in texts:
        for w in WORD_RE.findall(hi_fold(t)):
            words.add(w.strip("'-"))
    return frozenset(words)


FORBIDDEN_CHARS_RE = re.compile(r"[<>*`~\[\]\\|#@^_=${}]")
URL_RE = re.compile(
    r"https?\s*:|www\s*\.|\bftp:|[a-z0-9-]+\.(?:com|in|org|net|io|co|edu|gov|app|me|ly|xyz|info|biz|dev|ai)\b|"
    r"\bdot\s*(?:com|in|org|net)\b|\(at\)|\[at\]",
    re.IGNORECASE,
)
ENTITY_RE = re.compile(r"&#?\w+;")
SPACED_LATIN_RE = re.compile(r"(?<![a-z0-9])(?:[a-z][\s.\-_*,/]+){3,}[a-z](?![a-z0-9])")
SPACED_DEVA_RE = re.compile(
    "(?<![ऀ-ॿ])(?:[ऀ-ॿ][\\s.\\-_*,/​-‍]+){3,}[ऀ-ॿ](?![ऀ-ॿ])"
)
MARK_RUN_RE = re.compile(r"[ऀ-ःऺ-ॏ॑-ॗॢॣ]{4,}")


def extra_checks(
    *,
    combined_text: str,
    body: str,
    norm_full_text: str,
    trend: str,
    allowed_topics: list[Any],
    period: str,
    failures: list[str],
) -> None:
    ex = compiled_extra_lexicon()
    topics_longest_first = sorted(allowed_topics, key=lambda x: max(len(x.name_en), len(x.name_hi)), reverse=True)
    # Contract topic names (e.g. Hindi "अदिश राशि" = scalar quantity, "Rank..." style titles) are masked first.
    lex_src = combined_text
    for t in topics_longest_first:
        lex_src = re.sub(re.escape(t.name_en), " ", lex_src, flags=re.IGNORECASE).replace(t.name_hi, " ")
    folded = hi_fold(lex_src)

    # (e2) extended banned lexicon (both languages' lists applied to every report)
    for cat, regs in ex["banned"].items():
        for rx in regs:
            m = rx.search(folded)
            if m:
                failures.append(f"banned_{cat}: '{m.group(0).strip()}'")
                break

    # (g2) trend vocabulary: no vocabulary belonging to any other trend. The fixed home-tip catalog sentences are
    # masked first (e.g. the tip "encourage steady effort" is not a statement about the trend).
    from .pipeline import HOME_TIPS_CATALOG

    trend_text = folded
    for tip in HOME_TIPS_CATALOG.values():
        for tip_text in tip.values():
            trend_text = trend_text.replace(hi_fold(tip_text), " ")
    for other, regs in ex["trend"].items():
        if other == trend:
            continue
        for rx in regs:
            m = rx.search(trend_text)
            if m:
                failures.append(f"trend_vocab_contradiction: '{m.group(0).strip()}' is '{other}' vocabulary, trend='{trend}'")
                break

    # (i) injection / charset checks on text with placeholders, allowed topics and period masked out
    scan = combined_text.replace("{STUDENT}", " ").replace("{INSTITUTE}", " ")
    if period:
        scan = scan.replace(period, " ")
    for t in topics_longest_first:
        scan = scan.replace(t.name_en, " ").replace(t.name_hi, " ")
    if re.search(r"</?[A-Za-z!?]", scan) or ENTITY_RE.search(scan):
        failures.append("markup_injection: HTML tag or entity detected")
    if URL_RE.search(unicodedata.normalize("NFKC", scan)):
        failures.append("url_injection: URL, domain or e-mail pattern detected")
    if FORBIDDEN_CHARS_RE.search(scan):
        failures.append("markup_injection: forbidden markup/special character detected")
    if re.search(r"(?m)^\s*[-+>]\s", scan):
        failures.append("markup_injection: list/quote markdown detected")
    bad: set[str] = set()
    for ch in scan:
        cat = unicodedata.category(ch)
        if cat[0] in "LM":
            if not unicodedata.name(ch, "").startswith(("LATIN", "DEVANAGARI")):
                bad.add(ch)
        elif cat in ("So", "Sk", "Cs", "Co", "Cn"):
            bad.add(ch)
    if bad:
        failures.append(f"disallowed_character: {sorted(bad)[:5]}")
    if re.search(r"(.)\1{5,}", scan):
        failures.append("repetition_run: same character repeated >= 6 times")
    if MARK_RUN_RE.search(scan):
        failures.append("unicode_run: long run of combining marks")
    low = unicodedata.normalize("NFKC", scan).lower()
    if SPACED_LATIN_RE.search(low) or SPACED_DEVA_RE.search(low):
        failures.append("spacing_evasion: letter-spaced word detected")

    # (j) study-instruction sentences may only use template vocabulary + allowed topic names
    vocab = template_vocabulary()
    src = body.replace("{STUDENT}", " ").replace("{INSTITUTE}", " ")
    if period:
        src = src.replace(period, " ")
    for t in topics_longest_first:
        src = src.replace(t.name_en, " ").replace(t.name_hi, " ")
    src = re.sub(r"(\d)\.(\d)", r"\1_\2", src)
    for sent in re.split(r"[.।!?\n]+", src):
        fs = hi_fold(sent)
        if not fs or not STUDY_VERB_RE.search(fs):
            continue
        unknown = [w for w in (x.strip("'-") for x in WORD_RE.findall(fs)) if w and w not in vocab]
        # tokens made only of digits/percent are handled by the number check
        if unknown:
            failures.append(f"unknown_study_phrase: {unknown[:4]} in '{sent.strip()[:50]}'")
