# Verified Bilingual Parent Reports (`backend/app/genai` & `backend/templates`)

## Overview & Design Principle

`backend/app/genai` is a **pure Python, deterministic-first GenAI layer** that turns structured academic metrics (`numbers_json`) into a verified English (`en`) or Hindi (`hi`) parent progress report.

**Core Principle:**
1. **Code decides facts** (`build_numbers`): only numbers and syllabus topic IDs from `contracts/topics.yaml` enter the payload. Topics with `mastery_band = "not_enough_data"` are filtered out.
2. **Zero PII reaches the LLM** (`render_prompt`): prompts use `{STUDENT}` and `{INSTITUTE}` placeholders. Student names, institute names, roll numbers, guardian phone numbers, and free text never enter a prompt, eliminating both PII leakage and prompt-injection vectors.
3. **The LLM only phrases facts** (`LLMClient` / `OllamaClient`): runs locally via Ollama (`http://localhost:11434/api/chat`) with JSON-schema constrained decoding (`format=report_output.schema.json`), `temperature=0.3`, and thinking mode disabled (`think=False`, `/no_think`) for Qwen3 models.
4. **A deterministic 8-stage verifier decides whether phrasing may ship** (`verify`): checks JSON schema, ASCII/Devanagari digits & number words, allowed topic names (`name_en` / `name_hi`), focus topic uniqueness, `{STUDENT}`/`{INSTITUTE}` placeholders, proper-name leaks, banned shaming/ranking/mental-health lexicon (`contracts/reason_templates.yaml`), word count (`80..180`), sentence length (`<= 22` words), trend consistency, and home tips.
5. **Templates are the guaranteed fallback path** (`backend/templates/en/*.j2`, `hi/*.j2`): **the product works with zero LLM**. On verifier failure (after 1 retry with the failure list appended), LLM timeout (`> 8 s`), HTTP error, malformed JSON, or monthly cost cap reached (`CostMeter`), the system deterministically renders a human-written Jinja2 template and verifies it before returning. A report with `verified=False` can **never** be returned.

---

## Public API (`backend.app.genai`)

```python
from backend.app.genai import (
    CostMeter,
    FakeClient,
    NullClient,
    OllamaClient,
    build_numbers,
    export_report_pdf_bytes,
    generate_report,
    render_prompt,
    substitute_placeholders,
    verify,
)

# 1. Build schema-validated NumbersJson (filters out not_enough_data topics)
numbers = build_numbers({
    "period": "2026-W20",
    "lang": "hi",
    "attendance_pct": 86.5,
    "tests_taken": 6,
    "trend": "improving",
    "strengths": [{"topic_id": "jee.phy.kinematics", "mastery_band": "strong"}],
    "focus": [{"topic_id": "jee.phy.thermodynamics_phy", "mastery_band": "building"}],
})

# 2. Generate verified report (works with NullClient when no LLM is running)
report = generate_report(numbers, lang="hi", client=NullClient())
assert report.verified is True  # Guaranteed True

# 3. Substitute student and institute names ONLY after verification
final_payload = substitute_placeholders(
    report,
    student_name="आदित्य",
    institute_name="पटना साइंस अकादमी",
)

# 4. Optional offline PDF export with bundled OFL Noto Sans Devanagari font
pdf_bytes = export_report_pdf_bytes(report.content, lang="hi")
```

---

## How to Run & Test

From the repository root (repo root):

```bash
# Install pinned dependencies (if setting up a fresh venv)
pip install -r backend/app/genai/requirements.txt

# Run the offline GenAI test suite (16 tests, 0 network calls, 0 Ollama dependency)
make test-genai
# Or directly via pytest:
python -X utf8 -m pytest backend/app/genai/tests -v

# Re-run the 500-case fuzz evaluation, 1,000-report mix evaluation, and export CSVs / metrics.json:
python -X utf8 -m backend.app.genai.bench
```

**Measured Test Runtime:** `~35 s` on laptop CPU (includes 500-case corruption fuzz test, 1,000-report FakeClient mix test, 300x2 random template gate, and ReportLab PDF glyph verification). `NullClient` single-report latency is `< 3 ms` (`< 50 ms` bar).

---

## Known Limitations

1. **Hindi Template Native Review Pending:** All 10 Hindi templates (`backend/templates/hi/*.j2`) are marked `reviewed: false` in their header comments and exported to `docs/genai_hindi_review.csv` for native-speaker review before production use.
2. **Local LLM Benchmark Pending Model Pulls:** The automated benchmark harness (`run_ollama_benchmark` in `backend/app/genai/bench.py`) is ready, and requires human execution of `ollama pull qwen3:4b` and `ollama pull gemma3:4b` (~2.5–3.3 GB each).
3. **Human Rubric Scoring Pending:** `docs/genai_hindi_rubric.csv` (30 reports: 15 HI, 15 EN) is generated with blank score columns (`factual_accuracy_1_5`, `tone_1_5`, `hindi_naturalness_1_5`) awaiting human evaluation.
