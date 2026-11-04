# System Model Card — Verified Bilingual Parent Report Layer (`genai` v1.0.0)

- **Module:** `backend/app/genai` & `backend/templates/{en,hi}`
- **Contract Version:** `1.0.0` (`report_numbers.schema.json`, `report_output.schema.json`, `reason_templates.yaml`, `topics.yaml`, `metrics_bars.yaml`)
- **System Version:** `v1.0.0`

---

## 1. Intended Use
- Generate short (`80–180` words), Class-8 reading-level, supportive progress updates for parents/guardians of JEE Main and NEET-UG coaching students in **English (`en`)** and **Hindi (`hi`)**.
- Phrase strictly pre-computed, deterministic analytics facts (`attendance_pct`, `tests_taken`, `trend`, up to 3 `strengths` and 3 `focus` topics from `contracts/topics.yaml`, and 2 rule-selected `home_tips`).
- Operate **100% offline** in local-first deployments (`docker-compose` or native laptop/server) with **zero dependency on an active LLM** via 20 human-written bilingual Jinja2 templates (`10 EN + 10 HI`).

## 2. Not-Intended Use (Out of Scope / Prohibited)
- **Never** used to compute or invent academic scores, attendance rates, percentiles, or risk bands (all facts are computed upstream by deterministic SQL/ML modules).
- **Never** used to rank students, compare a student against peers/batches/siblings, predict dropout to parents, or speculate on mental or physical health.
- **Never** used with free-tier cloud LLM APIs on real student data (free cloud APIs may train on inputs, violating DPDP Act 2023 s.9 protections for minors).
- **Never** used to merge sibling reports even when two siblings share a single guardian phone number (`guardians.phone`).

## 3. Architecture & Verification Pipeline
1. **`build_numbers(inputs) -> NumbersJson`**: Validates ranges (`0 <= attendance_pct <= 100`, `tests_taken >= 0`), filters out topics where `mastery_band == "not_enough_data"`, overrides topic names exclusively from `contracts/topics.yaml` (blocking prompt injection via topic names), selects 2 `home_tips`, and validates against `contracts/report_numbers.schema.json`.
2. **`render_prompt(numbers, lang) -> Prompt`**: Emits a fixed system prompt plus `NumbersJson` with `{STUDENT}` and `{INSTITUTE}` placeholders. Student/institute names never enter the prompt.
3. **`LLMClient` (`OllamaClient` / `FakeClient` / `NullClient`)**: Calls local Ollama (`qwen3:4b` with `think=False` or `gemma3:4b`) with `temperature=0.3`, JSON-schema constrained decoding, and an `8.0 s` timeout.
4. **`verify(output, numbers, lang) -> VerifyResult`**: Deterministic 8-stage gate:
   - **(a) Schema:** Valid against `contracts/report_output.schema.json`.
   - **(b) Numeric Exactness:** Normalises Devanagari digits (`०–९`) ↔ ASCII, `%` / `प्रतिशत` / `percent` forms, and EN/HI number words (`zero`..`hundred`, `शून्य`..`सौ`). Every number in the text must appear in `numbers`.
   - **(c) Syllabus Topic Allow-List:** Masks allowed `strengths` and `focus` topics, then rejects any other topic from the 380-node `contracts/topics.yaml` graph. Enforces that each `focus` topic is mentioned at most once.
   - **(d) Placeholders & Proper Names:** Requires `{STUDENT}` and `{INSTITUTE}` in `body`, forbids placeholders in `title`, and rejects unallowed capitalised words or common Indian student/coaching proper names.
   - **(e) Banned Lexicon & Unicode Evasion:** Strips zero-width characters (`U+200B..U+200D`, `U+FEFF`), rejects Cyrillic/Greek homoglyphs, and blocks all EN/HI banned words from `contracts/reason_templates.yaml` plus rank/comparison/dropout/mental-health patterns.
   - **(f) Length & Readability:** Enforces `80..180` whitespace words, `word_count == len(body.split())`, and sentence length `<= 22` words.
   - **(g) Trend Consistency:** Requires language-appropriate trend markers matching `numbers.trend` (`improving`, `steady`, `declining`) and rejects contradictory trend phrases.
   - **(h) Home Tips:** Verifies both rule-selected `home_tips` appear in the report body.
5. **`generate_report(...) -> Report`**: Tries LLM → `verify` → 1 retry with `retry_corrections_required` → deterministic template fallback. Guaranteed `verified=True`.

## 4. Quantitative Validation Metrics (`backend/app/genai/artifacts/v1.0.0/metrics.json`)

Verifier catch rate is reported on three separate sets; the contract value is the LOWER of (a) and (b):
(a) own fuzz 500/500 (written by the same agent as the verifier, so NOT independent); (b) the reviewer's independent
cases (48 EN+HI, fullwidth digits excluded as NFKC-equal numbers), all caught after the R1_E2 fix (the same set caught
only 38/48 before it); (c) a second 100-case set written after the fix (paraphrases, spacing/mixed-script, markup,
URL/phone, Unicode runs): 100/100 after one extra fix (letter-spaced Devanagari with matras). This is evidence, not a
proof of completeness. Known residual surface: an unknown topic named in a sentence WITHOUT a study verb.

| Metric Key (`metrics_bars.yaml`) | Dataset Origin | Target Bar | Measured Value | 95% CI | Gate Status |
|---|---|---|---|---|---|
| `genai_verifier_injected_error_catch_rate` | `synthetic` | `>= 1.0` (blocking) | **`1.0000`** = min(fuzz 500/500, independent set 48/48) | `[1.0, 1.0]` | **PASS** |
| `genai_unverified_reports_shipped` | `synthetic` | `<= 0.0` (blocking) | **`0.0`** (`0 / 1,000` shipped in random good/bad mix) | `[0.0, 0.0]` | **PASS** |

- **No-LLM Template Latency:** `p50 = 1.6 ms`, `p95 = 3.2 ms` (`< 50 ms` requirement) across 100 reports (50 EN + 50 HI).
- **Template Verification Gate:** `600 / 600` (`100%`) across 300 random valid `NumbersJson` payloads in both English and Hindi.

## 5. Privacy, DPDP Compliance & Well-Being
- **Consent Gate:** Parent report generation requires active `parent_reports` consent in `consents` (`contracts/enums.yaml`).
- **Zero PII in Prompts:** Verified by blocking unit test `test_privacy_no_pii_in_captured_prompt`. Names are substituted post-verification via `substitute_placeholders()`.
- **No Shaming / No Comparisons:** Complies with DPDP Act 2023 s.9(2) (no detrimental effect on child well-being) and MoE 2024 Coaching Guidelines cl. 10.2(xi).

## 6. Known Limitations
- **Verifier Boundaries:** The deterministic verifier guarantees numerical, topic, placeholder, length, and lexicon compliance, but cannot judge subtle stylistic awkwardness if an LLM writes grammatically odd yet rule-compliant prose.
- **Hindi Review & Local Model Benchmark:** All 10 Hindi templates carry `reviewed: false` pending native-speaker sign-off in `docs/genai_hindi_review.csv`. Local GPU/CPU benchmarks (`qwen3:4b` vs `gemma3:4b`) and the 30-report human rubric (`docs/genai_hindi_rubric.csv`) are prepared and awaiting human model pull and scoring.
