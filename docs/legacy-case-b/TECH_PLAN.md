# The Data Moat — Technical Implementation Plan (v2)
Case B · Nextute × Finance Club IIT Patna · 2026 · updated 2026-10-20
Supersedes v1 (kept as `TECH_PLAN_v1.md`). **This file is the single source of truth for all agents.**
Research R1–R5 integrated on 2026-10-20 → see §24 for decisions, sources and what is still unverified.

Weight: 70% technology (architecture 25%, ML rigour 25%, feasibility/privacy/safety 20%), 30% business.

**Hard constraints (decided):**
- Everything free. Runs fully local first (laptop RTX 4060 8 GB + Colab). Hosting gets decided later. Production hosting is described on a slide, with costs.
- There is no real institute data. All student data is synthetic: generated with a seed, and with ground truth. Questions and the syllabus come from public sources. Methods are validated on public datasets as well.
- Stack: Next.js (TS, Tailwind, shadcn/ui, ECharts) · FastAPI (Py 3.11) · PostgreSQL · LightGBM · NumPy/PyTorch IRT · SHAP · conformal prediction · OpenCV. No Streamlit/Gradio.
- Built by parallel Antigravity agents. Contracts first; every module has its own tests.

Numbers in this file are **targets/acceptance bars, not results**. Results live only in `ml/artifacts/vX/metrics.json`.

---

## 1. Changes vs v1 (and why)

| # | Change | Why |
|---|---|---|
| 1 | **Local-first runtime**: `docker-compose` with `db` (Postgres 16), `api` (FastAPI), `web` (Next.js), `llm` (Ollama, optional). It needs no internet at demo time. | You decided this. Venue Wi-Fi is a risk. It costs ₹0. It also gives a privacy story: "student data never leaves the institute's box." |
| 2 | **LLM = local open model via Ollama** (model picked by research R3), with **human-written bilingual templates as the guaranteed path**. Free cloud APIs are used only for dev and synthetic text, **never for student data**. | Free tiers of hosted APIs may use inputs for training, which can't be allowed for minors' data. The model also has to fit in 8 GB VRAM and run offline. |
| 3 | **IRT revised**: blanks are scored as incorrect. Default is a hierarchical 2PL with a *prior* on the guessing floor (not a fixed c = 0.25). Items with fewer than ~50 responses fall back to Rasch (1PL) with topic-level priors. | Under JEE/NEET-style −1 marking, guessing is *optional*, so a fixed c = 0.25 misspecifies the model. Real batches have 40–150 students, which is too few for a free 3PL. Sensitivity analysis (blank = missing vs blank = wrong) goes in the report. |
| 4 | **Misspecification suite + "current practice" baseline** added to validation. | This answers "you graded your own homework" (circularity). It also produces the strongest tech-to-business slide: "the model vs. what the institute does today." |
| 5 | **Privacy tiers for features** (A: academic only → B: + attendance → C: + fees → D: + app engagement, **D off by default**). Each tier gets its own AUC. | It is defensible whatever DPDP "behavioural monitoring" turns out to mean. It also gives a ready answer to the curveball "regulation tightens." |
| 6 | **The moat is made explicit** (§5): pooled item bank, real-exam outcome labels, intervention outcomes. | The case is literally called "The Data Moat." The tech has to show *why data compounds*. |
| 7 | **Scope tiers P0/P1/P2** (§14) and a **Round 1 package** (§4). | One flawless end-to-end flow beats ten half-features. |
| 8 | **Auth**: seeded demo users, local JWT and a role switcher. Phone OTP is designed but not built. | SMS costs money and breaks offline. |
| 9 | **Student names never reach the LLM** (placeholder substitution after generation). | It kills both PII leakage and prompt injection through names at once. |
| 10 | **Percentile = two stages**: (i) a conformal band on the internal scale; (ii) an explicit, editable mapping to the NTA percentile, plus a mapping-uncertainty term. | No real internal→NTA history exists, so the mapping is shown as an assumption, not as calibration. |
| 11 | **Purpose- and age-aware model routing** (R1, R1b, R4b). Under-18: **academic-support** early warning (test-based "falling behind", for the child's learning) is allowed. Attendance/fee-based **dropout/retention ML** and **fee-default ML** are off by default; transparent rules on mandatory records are used instead. 18+ with their own consent: the full ML. A per-institute legal flag can enable the gated models for minors only after a legal opinion. | DPDP s.9(3) bans tracking/behavioural monitoring of children *even with consent*. The 4th Schedule exemption (definition: "institution of learning that imparts education") may cover coaching, but **only for monitoring "for the educational activities"**. Academic support fits that, and MoE 2024 cl. 10.2(xi) actually asks institutes to analyse performance and counsel students who are falling behind. Retention and fee prediction serve the business, not education, so they stay gated. |
| 12 | **Exam patterns versioned by year** (`exam_patterns.yaml`). Answer keys hold a *set* of accepted answers plus a `dropped` flag. | NTA's multi-correct and dropped-question rules (R4). The NEET pattern given by R4 conflicts with the 2025 reform, so it must be verified (§24). |
| 13 | **Topic tagging moves from P2 to Round 1 data prep** (offline). | No public JEE/NEET dataset has chapter/topic labels (R2). We tag JEEBench ourselves (LLM-assisted, human-checked), which also produces the tagging validation metric. |
| 14 | **Generator recalibrated**: attrition 12–25 % (default 18 %), peak months 3–4, full-length fortnightly mocks plus weekly chapter tests, Oct–Nov festival dip, Jan–Feb class-12 board dip, min age 16, 3–4 instalments. | R4 numbers (mostly medium or low confidence, so every value is a knob). See `generator_config_draft.yaml`. |
| 15 | **Compliance-as-a-feature** (small, cheap wins): age-at-enrolment check, test-schedule check (no test the day after the weekly off), pro-rata refund calculator, attendance/fee registers export, consent ledger. | MoE 2024 guidelines and state acts (R5). This is a real reason for an owner to pay, and it serves the business half of the score. |

---

## 2. The plan in 10 bullets

1. **Product**: a local-first "Institute Intelligence" web app. A teacher uploads a CSV/Excel or an OMR phone photo. The app shows a topic-mastery heatmap, a "needs support" list with reasons and a suggested supportive action, a predicted percentile *range*, and a verified Hindi/English parent report.
2. **Data**: a seeded generator simulates 3–5 institutes (students, questions, tests, responses, attendance, fees, dropout, final percentile) with known ground truth. A messy-data injector produces realistic dirty Excel files and OMR photos. Questions and the topic graph come from public JEE/NEET sources and the NTA syllabus.
3. **Question difficulty**: a hierarchical IRT (2PL with a guessing prior; Rasch fallback for small n), fitted offline and updated incrementally. Items with negative discrimination are flagged as probable **wrong answer keys**.
4. **Topic mastery**: per-topic EAP ability with an SE, shrunk toward the student's overall ability and the batch mean. Mastery bands appear only when the SE is small; otherwise the app says "not enough data." BKT and raw % correct are the baselines.
5. **Early warning**: three targets (dropout within 30/60 days, falling behind, fee default). LightGBM + isotonic calibration vs logistic regression vs the institute's current rule. SHAP turns top reasons into plain-language reasons and a supportive action. The operating point is set by mentor capacity, not 0.5.
6. **Honest prediction**: quantile LightGBM + conformalized quantile regression gives a guaranteed-coverage band. It maps to the NTA percentile through an explicit assumption table. The band narrows as the year goes on and is never a single number.
7. **GenAI**: a deterministic `numbers_json` is phrased by a local LLM. A verifier checks every number and topic plus banned phrases. On failure, a human-written bilingual template is used. Names are inserted after generation.
8. **Architecture**: FastAPI + Postgres with an `institute_id` on every row plus Row-Level Security. Models are trained offline and shipped as versioned files. Scoring happens on request (ms). Everything runs in docker-compose, offline.
9. **Privacy and well-being**: purpose-wise revocable parental consent gates processing. Feature privacy tiers. Risk is visible only to the assigned mentor and owner. No ranks, no shaming, human review before outreach. Audit log, retention and deletion.
10. **Proof**: validation on synthetic data (ground-truth recovery, temporal and institute-held-out splits, misspecification), on public data (OULAD dropout, ASSISTments/EdNet next-response), and on a self-made real OMR photo set. A cost per student per month is computed, and limitations are stated up front.

---

## 3. Top 10 technical risks to winning

| # | Risk | How a judge exposes it | Mitigation (built into this plan) | Test / evidence |
|---|---|---|---|---|
| 1 | **Circular validation**: models validated on data from our own generator | "You recover what you planted." | Misspecification suite (data generated by a *different* process than the model assumes) + public datasets + real self-shot OMR photos. Synthetic results are always labelled "pipeline proof." | `notebooks/07_robustness`, metrics table split synthetic / public / real-photo |
| 2 | **Feature leakage** in early warning (future attendance or fees used as features) | An AUC that is too good (≥0.95) | Strict `as_of` feature builder. Property test: mutating any data after `as_of` must not change features. | `test_no_leakage` (hypothesis) |
| 3 | **Live demo breaks** (judge's input, OMR on an odd photo, LLM slow or crashing) | Changes inputs live | Local-only stack. Template fallback. OMR low-confidence review screen. Pre-warmed model. Chaos rehearsals (kill LLM, unplug network). | `make chaos`; 3 full rehearsals |
| 4 | **DPDP: risk scoring = "behavioural monitoring of children"?** There is no official definition (R1b: no MeitY FAQ). The ban applies even with parental consent. The exemption covers only "educational activities" of the institution as Data Fiduciary. | "Is this even legal for minors?" | **Purpose- and age-aware routing** (§1 #11): academic support for everyone; retention/fee ML only for 18+ or behind a legal flag; transparent rules on mandatory records. No cross-tenant training on real minors' data. Consent gating, privacy tiers, engagement tracking never used for minors, human-in-the-loop, audit. | Routing test (a minor never gets an ML risk score unless the flag is on); tier-ablation chart; consent-revoked test |
| 5 | **Percentile prediction overclaims** | "Based on what real data?" | Two-stage band, explicit assumption table, conformal coverage reported, MoE-style disclaimer, wording instead of decimals. | Coverage 80 % ± 3 %; band-width-by-month chart |
| 6 | **IRT unstable at real batch sizes** (40–150 students) | "3PL with 60 students?" | Hierarchical priors, Rasch fallback, SE shown, "recovery r vs n responses" curve, and pooling across institutes (= the moat). | Recovery curve at n = 30/60/100/200/500 |
| 7 | **GenAI hallucination or bad Hindi** | They read the Hindi report aloud | Numbers come from `numbers_json` only. Verifier normalises Devanagari digits. Topic names come from the bilingual `topics.yaml`. Native-speaker rubric. Template fallback. | Verifier fuzz: 100 % of injected wrong numbers caught; 0 unverified reports shipped |
| 8 | **Integration failure** across parallel agents (contract drift) | Nothing works end to end on the day | Frozen `contracts/` with a version tag, schemathesis contract tests, a mock API from OpenAPI, daily `make demo` from a clean clone. | CI green on `make e2e` |
| 9 | **Cost per student isn't credible** ("free tier" ≠ production) | "What happens at 50 institutes?" | A separate production cost model (paid VPS, managed DB, backups, LLM tokens or self-hosted, WhatsApp utility messages), with sensitivity and stated assumptions. | `notebooks/09_cost_model` → financial model |
| 10 | **Synthetic data feels fake** (wrong exam pattern, wrong fee or attendance norms) | A coaching-insider judge | Generator parameters calibrated from research R4 (exam patterns, batch sizes, fee instalments, test cadence), each cited in `generator_config.yaml`. Real self-made OMR sheets. | Config with a `source:` field per parameter |

Also watched: tenant data leaks (RLS + isolation tests), Hindi font rendering offline (self-hosted Noto Sans Devanagari), and 8 GB VRAM contention during the demo (use a ≤5 GB model, with CPU fallback).

---

## 4. Round 1 — the technical submission (and what goes on slides)

### 4.1 What to submit
1. **Public GitHub repo** (`datamoat`) whose README contains a **results table** at the top (synthetic / public / real-photo columns), a model card link, and one command per notebook.
2. **A Colab link** to a single "Run all" notebook (or a notebook index). It must run top to bottom on free Colab CPU in **< 15 min**, generate data with seed 42, and download public data with a script. **Datasets are not committed** (licences).
3. **`metrics.json` + `model_card.md`** (intended use, not-intended use, data, metrics, fairness slices, limitations, privacy).
4. **A 1-page `VALIDATION.md`** that every deck number traces to.

### 4.2 Notebooks (each proves one claim and yields one slide figure)

| NB | Proves | Headline metric (target) | Slide figure |
|---|---|---|---|
| 01_synthetic_data | Realistic, cited generator; messy-data injector | Dropout 8–15 %, peak months 3–5, a source for every parameter | Student journey timeline (attendance fading → dropout) |
| 02_irt_difficulty | Difficulty recovery + wrong-key detection | r(b̂, b) ≥ 0.90 at ≥ 200 resp/item; ≥ 4/5 injected wrong keys caught, ≤ 2 false flags | **Recovery r vs #students** (also the moat argument) |
| 03_topic_mastery | Mastery beats raw % correct | Next-test AUC > raw-% and BKT baselines; θ recovery r | Student × topic heatmap |
| 04_early_warning | Earlier and more precise than current practice | AUC-PR, precision@mentor-capacity, **median lead time ≥ 3 weeks**, ECE < 0.05, institute-held-out AUC | **Model vs "attendance < 75 %" rule** at equal workload; SHAP reasons → actions |
| 05_percentile_range | Honest uncertainty | 80 % band coverage 77–83 %; width shrinks over months | **Band-width-by-month funnel** |
| 06_public_validation | Method works on real data | OULAD withdrawal AUC at d14/28/42/60 vs PLOS ONE 2026 (0.727/0.794/0.804); ASSISTments2009 next-response AUC under the pyKT protocol vs DKT 0.754 / SAKT 0.725 / AKT 0.785 | Table: ours vs literature, same protocol |
| 07_robustness | Not circular | Metrics under misspecified generators (2PL→3PL data, drift, MNAR blanks, noisy keys) | Degradation bar chart |
| 08_genai_reports | Reliable bilingual reports, cheap | 0 unverified numbers delivered; fallback rate; latency on RTX 4060; ₹/report | Report sample EN/HI with verifier ticks |
| 09_cost_model | ₹/student/month | Within ₹3–10 under stated assumptions; sensitivity | Stacked cost bar |
| 10_privacy_tiers | Privacy vs accuracy trade-off | AUC by feature tier A→D | **Privacy cost curve** |
| (opt) 11_omr_poc | Reads phone photos | ≥ 99 % bubble accuracy synthetic; ≥ 98 % on our real phone photos; 100 % of uncertain cells flagged | Before/after warp + detected bubbles |

### 4.3 Suggested 12-slide map (tech ≈ 7 slides to match 70 %)
1 Title + one-line promise · 2 Owner's reality (problem) · 3 Product in one picture (4 screens) · 4 **Capture & architecture** (offline-first, OMR, Excel mapper) · 5 **Mastery & difficulty** (heatmap, recovery curve, wrong-key catch) · 6 **Early warning → supportive action** (vs current rule, lead time, reasons) · 7 **Honest prediction + verified parent report** · 8 **Privacy & well-being by design** (consent, tiers curve, no ranking) · 9 **The data moat** (§5) · 10 Unit economics (₹/student) · 11 GTM & financials · 12 **Validation, limitations, pilot plan**.

**Rules:** every number on a slide comes from `metrics.json` (`scripts/deck_numbers.py` prints them). Every number is labelled synthetic, public or real-photo. Slide 12 lists limitations before the judges do.

---

## 5. The moat (technical substance)

1. **Pooled calibrated item bank.** Every institute's responses sharpen difficulty and discrimination for shared questions. Small institutes (one batch of 60) borrow strength from the pool, through hierarchical priors and anchor items. *Evidence:* the recovery-vs-n curve (NB02).
2. **Real-exam outcome labels.** After JEE/NEET results, institutes enter actual percentiles. Over time this is the only dataset mapping internal tests → NTA percentile. It shrinks band width year on year.
3. **Intervention outcomes.** Logged supportive actions and their results enable uplift modelling ("which action works for whom"), which competitors with only marks data cannot do.

Governance: cross-institute use only for opt-in, aggregated, k-anonymous (k ≥ 20) statistics and item parameters. Raw student rows never leave the tenant. **No cross-tenant model training on real minors' data** (that would make us a Data Fiduciary, §15). Global risk models come from synthetic and public data; each tenant calibrates on its own data. The moat is the *item bank and outcome tables*, not a pooled profile of children. Say this explicitly on the moat slide.

---

## 6. Architecture

```
 OFFLINE (Colab / RTX 4060)                       LOCAL DEMO (docker-compose, no internet)
 ──────────────────────────                       ─────────────────────────────────────────
 topics.yaml + question bank                      web  : Next.js (owner/teacher/parent views)
 datagen (seed, ground truth)                         │ JSON over HTTP, JWT, role switcher
 ml/train_*.py → artifacts/vX/ ───baked into image──► api  : FastAPI
 ml/evaluate.py → metrics.json                          ingest (CSV/XLSX mapper, OMR/OpenCV)
                                                        analytics (IRT score, mastery, risk, band)
                                                        genai (numbers_json → LLM → verifier → template)
                                                        scheduler (APScheduler, nightly recompute)
                                                      │                      │
                                                  db : Postgres 16 + RLS   llm : Ollama (optional;
                                                                             absence ⇒ templates)
```
- **Request path**: upload → parse/validate → write → **synchronous recompute for the affected batch** (target < 5 s for 150 students) → UI refresh. The nightly job recomputes everything.
- **What-if**: a judge edits attendance → features are rebuilt for that student → LightGBM predicts in milliseconds → reasons update live.
- **Production (slide only)**: India-region VPS or managed containers, managed Postgres with PITR, object storage for OMR images (auto-delete after 7 days), WhatsApp Business Cloud API, PWA offline queue, per-tenant keys, backups. Costs come from R8/R9 research.

---

## 7. Repository layout

```
datamoat/
  contracts/   schema.sql · openapi.yaml · data_dictionary.md · csv_templates/ · topics.yaml
               exam_patterns.yaml · omr_template.json · metrics_bars.yaml · CONTRACT_VERSION
  datagen/     generator/ · messy/ · omr_synth/ · config/generator_config.yaml · tests/
  ml/          irt/ mastery/ risk/ rank/ tagging/ common/(features, splits) · train.py · evaluate.py
               artifacts/vX/{*.pkl|*.npz|*.txt, metrics.json, model_card.md} · tests/
  backend/     app/{api,services,db,ingest,omr,genai,auth,jobs} · templates/(en,hi) · tests/
  frontend/    app/ components/ lib/api(generated from openapi) · public/fonts(Noto Sans Devanagari) · e2e/
  notebooks/   01…11 (see §4.2)
  ops/         docker-compose.yml · Dockerfiles · Makefile · seed/ · ci/
  docs/        TECH_PLAN.md · MODEL_REPORT.md · PRIVACY.md · decisions.md · agent_logs/ · contract_change_requests.md
  scripts/     deck_numbers.py · download_public_data.py
```

---

## 8. Data model (Postgres; `institute_id` on every tenant row + RLS)

| Table | Key fields | Notes |
|---|---|---|
| institutes | id, name, city, city_tier, exam_focus, plan, created_at | |
| users | id, institute_id, role (owner/admin/teacher/mentor/parent/student), phone, name, lang, active | demo: seeded users |
| batches | id, institute_id, name, class (11/12/dropper), exam (JEE/NEET), start_date, mentor_capacity_per_week | capacity sets the risk cut-off |
| students | id, institute_id, batch_id, roll_no, name, name_alt, dob, gender, join_date, status (active/left/transferred), fee_plan | roll_no unique per (institute, academic_year). `is_minor` is derived from dob at each `as_of` (routing switches on the 18th birthday + re-consent) |
| batch_changes | student_id, from_batch, to_batch, at, reason (timing/subject_change/relocation/other — **never performance**), by_user | MoE cl. 12(vii) |
| guardians | id, institute_id, student_id, phone, relation, lang_pref | one phone can map to siblings |
| consents | id, institute_id, student_id, guardian_id (null if the student is 18+ and consents personally), purpose (analytics/risk_alerts/parent_reports/benchmarking/engagement_tracking), verification_method (in_person_id_check/otp_known_parent/digilocker_token), verified_by_user_id, verified_at, revoked_at, notice_version, notice_lang | processing checks these. **No ID document copies are stored**, only the method and the verifier. Re-consent is required when a student turns 18. |
| legal_settings | institute_id, minor_ml_risk_enabled (default false), legal_opinion_ref, updated_by, updated_at | §15 routing flag, audited |
| topics | id, exam, subject, chapter, topic, name_hi, parent_id, syllabus_year, weightage | global |
| topic_prereqs | topic_id, prereq_topic_id | |
| questions | id, institute_id (null = shared), subject, text_hash, q_type (mcq_single/mcq_multi/numeric), options_n | |
| answer_keys | id, test_id, question_id, accepted_answers (array), numeric_tolerance, dropped (bool), version, created_by | **versioned**; re-scoring on change. NTA rule: dropped → full marks to everyone (configurable to "attempted only"); multi-correct → full marks to anyone who marked any accepted answer |
| question_topics | question_id, topic_id, weight, tagged_by, confidence, reviewed_by | |
| item_params | question_id, model_version, a, b, g, se_b, n_responses, fit_flag | `fit_flag` = suspect key |
| tests | id, institute_id, batch_id, name, date, marking_scheme_id, source (omr/csv/online) | |
| marking_schemes | id, correct, wrong, blank, partial_rule | JEE/NEET/custom |
| test_questions | test_id, question_id, position, section | |
| responses | test_id, student_id, question_id, response, is_correct, status (answered/blank/multi_marked/unreadable), confidence | |
| test_totals | test_id, student_id, raw_score, absent_flag | supports marks-only institutes |
| attendance | institute_id, student_id, date, present_flag, source | |
| fees | institute_id, student_id, instalment_no, due_date, amount, paid_date, paid_amount | |
| engagement | institute_id, student_id, date, doubts_asked, homework_submitted, app_logins | **tier D, consent-gated, off by default** |
| mastery_snapshots | student_id, topic_id, theta, se, n_items, computed_at, model_version | |
| risk_scores | student_id, as_of, target, p, band, reasons (jsonb), feature_tier, model_version | |
| predictions | student_id, as_of, q10, q50, q90, mapped_low, mapped_high, coverage_level, model_version | |
| interventions | id, student_id, type (mentoring/counselling/remedial/fee_plan), owner_user_id, due, done_at, outcome | |
| reports | id, student_id, period, lang, numbers_json, content, verified, path (llm/template), sent_via, sent_at | |
| ingest_jobs | id, institute_id, file_hash, type, status, mapping (jsonb), errors (jsonb), rows_ok, rows_failed | idempotent by hash |
| omr_templates | id, institute_id, name, layout (jsonb) | |
| model_registry | version, trained_at, data_version, metrics (jsonb) | `/version` |
| audit_log | actor, institute_id, action, entity, entity_id, at | who saw risk data. **Retain ≥ 1 year** (DPDP Rules, Rule 6). No PII in the log payload. |

**Deliberately NOT stored:** counselling notes or mental-health information (out of scope; never a model feature), ID document images, student photos.

Synthetic-only truth (separate schema `truth`, never loaded into the app DB): true θ per topic, true item params, dropout type (gradual/sudden), true final percentile.

---

## 9. Synthetic data generator (`datagen/`)

**Process**: as in v1 §5.1 (institutes → students with latent g and correlated topic θ → items → tests following syllabus order → responses → attendance → fees → dropout hazard with ~25 % sudden dropouts → final percentile). **Calibrated defaults (R4)** are in `Technical/generator_config_draft.yaml`, and every value has a source and a confidence:
- Class mix 30/30/40 (11/12/dropper). Batch size 40–80. Institutes have 150–2,000 students. Age ≥ 16 at enrolment, so DOBs are consistent, with ~all class 11/12 students being minors and most droppers adults.
- Attrition 18 % per year (knob 12–25 %), with the hazard peaking at months 3–4 (Aug–Sep, after the first cumulative test and before the 2nd instalment). Droppers have a lower base hazard.
- Fees: ₹60k–1.5L per year, 35 % upfront plus 2–3 instalments (4 under the Rajasthan rule). *(Finance R2, 2026-10-20: the upfront share has no source; the finance model uses 15/25/40 % as an assumption. Local Tier-2 fees are ₹50k–1.25L; pro-rata refunds apply only to full payers and are widely ignored in practice.)* 15–20 % pay the final instalment late or default, correlated with disengagement. Withdrawal triggers a pro-rata refund event.
- Tests: full-length mocks every 14 days (JEE 75 Q/300 marks; NEET per the verified 2026 pattern) and weekly chapter tests (20–30 Q). No test on the day after the weekly off (MoE).
- Attendance: base 0.82; Oct–Nov festival dip (Diwali/Chhath, ×0.6 for out-of-town students); Jan–Feb dip for class 12 (boards).
- The OMR read-error rate of the institute's existing scanner is 2–4 % (low confidence), used by the messy injector.
- Final percentile: through the score→percentile tables (§10), with a shift-difficulty modifier (easy vs tough shift envelope).

**Additions:**
- **Exam realism**: marking schemes, question types and section structure come from `exam_patterns.yaml` (R4). Under negative marking, students *choose* to blank when their P(correct) is low (a per-student risk-aversion parameter), which gives MNAR blanks.
- **Batch/teacher effects** (topic taught well or badly in a batch) and **untaught-topic tests** (a whole batch fails because the topic wasn't covered, not because of weakness). Analytics must detect this.
- **Calendar**: festival dips (Diwali, Chhath for Bihar), board-exam season, monsoon. Holidays are the same for everyone, so features must be batch-relative.
- **Scenario knobs** (YAML): dropout multiplier, % marks-only institutes, % online tests, fee upfront share, missing-data rate, wrong-key count, institute size. Used for curveballs.
- **Misspecified variants** for NB07: data from 3PL with item-specific guessing, ability drift mid-year, a non-IRT "cheating cluster," noisy answer keys.
- **Every parameter has `source:`** (research citation or "assumption").
- **Messy injector**: per v1 §5.2 (merged cells, header in row 3, Devanagari/transliterated names, AB/A/-/blank, DD/MM mix, duplicates, reused roll numbers, extra sheets, formulas, marks-only files, a wrong key).
- **OMR images**: render the template → fill bubbles (pen/pencil intensity, partial fill, erasure, double mark) → augment (perspective, rotation ±15°, shadow gradient, blur, low light, JPEG q=30–60 to mimic WhatsApp, photo-of-screen). **Plus a real set**: print 20 sheets, fill them by hand (including deliberate errors), and take 60+ phone photos in different conditions. Ground truth is recorded by hand. This is our "real data."
- **Outputs**: `data/clean/*.parquet`, `data/truth/*.parquet`, `data/dirty/*`, `data/omr/{synthetic,real}/*.jpg + truth.json`, the config and the seed. Same seed → byte-identical output.

---

## 10. ML modules — method, validation, acceptance bars

| Module | Method | Baselines | Validation | Bars (`metrics_bars.yaml`) |
|---|---|---|---|---|
| IRT | Hierarchical 2PL, guessing prior Beta(2,18) for MCQ (0 for numeric), blank = wrong; Rasch + topic prior when n < 50; MAP/EM in NumPy or PyTorch | Classical p-value difficulty | Recovery r vs n; item fit; injected wrong keys | r ≥ 0.90 @ n ≥ 200; ≥ 0.75 @ n = 60; wrong-key recall ≥ 0.8, ≤ 2 false flags / 300 items |
| Mastery | Per-topic EAP with shrinkage to overall θ and batch mean; exponential time decay (half-life tuned); band only if SE < τ | Raw % correct per topic; pyBKT | Next-test response AUC (held-out tests); θ recovery; band calibration | AUC > both baselines (CI non-overlapping on synthetic); recovery r ≥ 0.8 |
| Early warning | LightGBM + isotonic calibration; features by `as_of`; batch-relative; feature tiers A–D; discrete-time hazard for "when" (optional) | Logistic regression; **institute rule** (attendance < 75 % or last test < 40 %) | Temporal split (train months 1–6 / test 7–12) **and** leave-one-institute-out | AUC-PR > rule by ≥ 30 % rel.; median lead time ≥ 3 wks; ECE < 0.05; recall on *gradual* dropouts ≥ 0.6 at capacity; sudden-dropout ceiling reported |
| Falling behind | Target: batch-relative θ drop > 0.5 SD over 4 weeks | Last-test drop rule | Same splits | AUC-PR > rule |
| Fee default | Target: next instalment > 30 days overdue | Last-payment-late rule | Same | AUC-PR > rule; never shown to students |
| Percentile band | Quantile LightGBM (10/50/90) + conformalized quantile regression (CQR) on a calibration fold; mapping to NTA percentile via monotone table (R4) + mapping error term | Linear regression on last 3 test averages | Coverage, width by month, MAE of median | 80 % coverage within 77–83 %; width shrinks monotonically by month |
| Tagging (**Round 1 data prep**, product UI P2) | Embedding shortlist (multilingual small model, local) → LLM choice (free cloud API is allowed here: public questions, no PII) → human check | Keyword match | JEEBench (515 Q, MIT): we hand-label 150 to chapter/topic as the gold set | ≥ 95 % precision on the auto-accepted share; report coverage |

**Rigour notes for the report:** split by student and by time (never by row). Report confidence intervals (bootstrap). Fairness slices (gender, class, city tier, fee plan): recall and precision at the operating point, gap ≤ 0.1 or explained. Reasons come from SHAP on the calibrated model's input and are mapped through `reason_templates.yaml` (EN/HI) → `action_templates.yaml`. Reasons computed from raw features ("absent 6 of last 10 classes") are shown, not SHAP numbers.

**Operating point:** top-k per batch per week, with k = `mentor_capacity_per_week`. The UI says "These 8 students would most benefit from a check-in this week."

**Deployment routing (legal, §15):**
| Student | Academic support ("falling behind") | Retention (dropout) | Fee | Engagement (tier D) |
|---|---|---|---|---|
| Under 18 (default) | **ML on test-result features (tier A)** + SHAP reasons. Basis: 4th Sch. "educational activities" + MoE cl. 10.2(xi) | **Rules only** ("absent 5 consecutive days", "missed 2 mocks") | **Rules only** (overdue reminders; fee data concerns the paying parent) | Never |
| Under 18 + `minor_ml_risk_enabled` | as above | ML (tiers A–B) | Rules only | Never |
| 18+ with own consent | ML | ML (tiers A–C) | ML | Opt-in |

Every alert goes to a mentor as a *supportive* task. All alerts and views are audited.

Training and validation use all synthetic students (it is synthetic data). NB04 reports both modes side by side: **"rules-only (minor-safe)" vs "ML"**, recall at equal mentor capacity and lead time. This *is* the privacy-cost slide.

**Score → percentile mapping (R4):** JEE Main uses the 2026 session-average marks→percentile table as the centre, with the 2024 easy-shift and tough-shift tables as the mapping-uncertainty envelope. NEET: marks→rank tables converted to a percentile with candidate count N (percentile = 100·(1 − rank/N)). **Both are low/medium-confidence aggregator data**: stored in `contracts/percentile_tables.csv`, editable by the owner, and labelled as an assumption in the UI and the report.

**Public validation protocol (R2, R2b, verified):**
| Benchmark | Our protocol | Published reference (verified) |
|---|---|---|
| OULAD withdrawal | Observation windows of day 14 / 28 / 42 / 60, student-grouped CV, LightGBM + LR + calibration | Wu, Duan & Luo 2026, PLOS ONE e0352867 (+ correction e0355736): ROC-AUC **0.727 @ d14, 0.794 @ d28, 0.804 @ d42**. IJET 2026 (online-journals.org i-jet/62480): **0.735 @ d14, 0.815 @ d60** |
| ASSISTments2009 next response | **pyKT protocol**: question-level, 5-fold CV, 20 % students held out, one-step-ahead. We run our IRT/mastery model + pyBKT | pyKT (Liu et al., NeurIPS 2022): **DKT 0.7541, SAKT 0.7246, AKT 0.7853** AUC. pyKT has no IRT/BKT rows, so ours are new rows in the same protocol |

Framing: "a lightweight, explainable model that runs on a laptop CPU, compared with deep KT under the identical protocol." We report the result whether it wins or loses. EdNet is dropped from P0 (not in pyKT, CC BY-NC); it's an optional scale test only.

---

## 11. GenAI layer

- **Pipeline**: `numbers_json` (attendance %, tests taken, ≤ 3 strengths, ≤ 3 focus topics with HI names, trend word, 2 home-support tips chosen by rules) → prompt with **placeholders** (`{STUDENT}`, `{INSTITUTE}`) → local LLM (temperature 0.3, JSON-mode output) → **verifier** → substitute names → store.
- **Models (R3)**: benchmark `qwen3:4b` (Apache-2.0, ~2.5 GB Q4; thinking mode must be **disabled**) vs `gemma3:4b` (Gemma terms, ~3 GB) on 50 fact-JSONs. Keep the Q4 file ≤ 3.5 GB so it fits in 8 GB with the KV cache. **Path B** if the Hindi is stiff: generate English → IndicTrans2 distilled EN→Indic (~0.2–0.3 B, MIT) → verifier. Not used: Sarvam-1 (non-commercial), Sarvam-M (24 B, too big), and any free cloud API for real student data (free tiers may train on inputs).
- **Production option (slide)**: a paid API with no-training terms and a DPA (e.g. a Flash-Lite-class model ≈ ₹0.02/report at R3 prices, *to re-verify*) or self-hosted. Even at 4 reports per student per month, LLM cost is < ₹0.1/student/month. **The LLM is not the cost driver.**
- **Verifier**: normalise Devanagari↔Latin digits and number words. Every number in the output must be in `numbers_json`. Every topic mention must match the allowed topic list (EN/HI). Banned lexicon (EN/HI: dropout, fail, weak student, rank, compare, sibling names, mental-health guesses). Length 80–180 words. Reading level by heuristic. Any failure → one retry → template.
- **Templates**: 6–10 human-written variants per language, chosen by trend. The Hindi is reviewed by a native speaker on the team. *The product works with zero LLM.*
- **Study plan**: rule engine (weak topics × exam weightage × prerequisites satisfied) → LLM explains. **Practice set**: retrieve from the bank by topic and difficulty band (θ ± 0.5). No generated questions in P0/P1.
- **Eval (NB08)**: 200 reports (100 EN, 100 HI) → automatic verifier pass rate, fallback rate, latency p50/p95 on RTX 4060 and on CPU-only, plus a 30-report human rubric (accuracy, tone, Hindi naturalness 1–5). Fuzz test: inject 500 wrong numbers or topics into outputs → 100 % caught.
- **Cost**: local = ₹0 marginal (electricity); production options come from R3/R8 (small hosted model per 1M tokens vs nightly CPU batch vs template-only).

---

## 12. Data capture

| Source | P0/P1 build | Production (slide) |
|---|---|---|
| CSV/XLSX | Upload → sheet and header-row detection → fuzzy column mapping (EN/HI synonyms) saved per institute → preview with row errors → confirm. Marks-only files supported. | Google Sheets sync |
| OMR photo | Our template: 4 corner fiducials + QR (test_id, page) + roll-number bubbles. Pipeline: detect fiducials → warp → grid from `omr_template.json` → fill ratio relative to the sheet's own blank-bubble distribution → per-bubble confidence → review screen for uncertain cells → confirm. | Batch capture via phone; WhatsApp intake; template registry for other sheet layouts |
| Offline | P2: IndexedDB upload queue | PWA sync |
| WhatsApp / Forms | Mocked "WhatsApp preview" of the parent report | Business Cloud API, Sheets API |

**Judge brings a random OMR sheet:** prepared answer: "Different layouts are onboarded once via the template registry (≈ 30 min per layout). Live, we read our template. Here's the CSV path for anything else." P2: a manual grid calibration tool (click 4 corners + first/last bubble).

---

## 13. API (FastAPI; OpenAPI in `contracts/openapi.yaml`)

```
POST /auth/login (demo) · GET /me
POST /ingest/students | /ingest/results  (csv/xlsx) → ingest_job
POST /ingest/omr (image[]) → parsed + low-confidence cells ; POST /ingest/omr/{job}/confirm
GET  /ingest/jobs/{id}
GET  /batches/{id}/heatmap · /batches/{id}/support-list?week= · /batches/{id}/summary
GET  /students/{id}/profile   (mastery, trend, band, reasons — role-filtered)
PATCH /students/{id}/attendance|fees (what-if / corrections) → recompute
POST /students/{id}/interventions · PATCH /interventions/{id}
POST /students/{id}/reports?lang=en|hi → {content, verified, path}
GET  /tests/{id}/flagged-questions · POST /answer-keys/{test}/{q} (re-score)
GET  /owner/dashboard
GET/POST/DELETE /consents
GET  /settings/privacy-tier · PUT (owner)  → recompute with tier
GET  /health · /version
```
Every response carries `model_version`. Tenant comes from the JWT, never from the request body. Upload size limits and rate limits apply. Errors use RFC 7807.

---

## 14. Prototype scope & demo

| Tier | Features |
|---|---|
| **P0 (must work flawlessly)** | Seeded institutes · CSV/XLSX upload with mapping + errors · heatmap · support list with reasons + action · student profile with band · EN/HI report with verifier + fallback · wrong-key flag + re-score · consent gating · tenant isolation · offline docker-compose |
| **P1** | OMR photo upload + review · what-if edit → live risk update · privacy-tier switch (live ablation) · interventions log · mobile parent view · owner dashboard |
| **P2** | Offline upload queue · study plan · practice set · WhatsApp-style preview · OMR grid calibrator · tagging review queue |
| **Compliance quick wins (P1, ~1 day total)** | Age-at-enrolment < 16 warning at ingest · test-schedule check (no test the day after the weekly off) · pro-rata refund calculator on withdrawal · attendance/fee register export (inspection-ready) · consent ledger export |

**Never build:** public leaderboards, performance-based batch allocation (remedial sessions are *supplementary* to the regular batch, never a replacement), marketing use of student photos or results.

**Demo script (7 min):** (1) Owner logs in, sees 3 batches. (2) Teacher uploads a messy Excel export; the mapper fixes headers and shows 3 row errors. (3) Heatmap shows that a whole batch is weak on one topic, flagged as "probably untaught". (4) Flagged question: probable wrong key → fix → scores update. (5) Support list: the top 8 for this week with reasons and actions; the judge edits attendance and the list re-ranks. (6) OMR photo taken on stage → reviewed → added. (7) Hindi parent report generated, with verifier ticks; pull the LLM container plug → the template still works. (8) Privacy tier → "academic only" → AUC drop shown honestly.

---

## 15. Privacy, DPDP, well-being (20 % of score)

**Legal posture (R1). We design for the strictest reading:**
- **Roles**: the institute is the Data Fiduciary and we are the Data Processor (s.8). The fiduciary stays liable "irrespective of any agreement", so our DPA (`docs/DPA_template.md`) must contain: documented-instructions-only, data categories and purposes, security safeguards (Rule 6), log retention ≥ 1 year, sub-processor flow-down, **breach notice to the institute within 6 hours** (so they can meet "without delay" + 72 h to the Board, and CERT-In's 6 h), and deletion or return at contract end.
- **The educational-institution exemption is narrow, so we don't rely on it for consent.** The definition is broad: "an institution of learning that imparts education, including vocational education" (4th Sch. note (d)), so a coaching centre *may* qualify. But Part A item 3 only disapplies s.9(1) and 9(3) for "tracking and behavioural monitoring (a) for the educational activities of such institution; or (b) in the interests of safety of children enrolled". It is not a blanket waiver, and no MeitY clarification exists (R1b). So:
  - **Verifiable parental consent before any processing** of a minor's data (s.9(1), Rule 10), even where the exemption might apply. Practical flow, matching Rule 10(1)(a) and the Illustration (Cases 3–4): at the admission desk, the institute (the Data Fiduciary) checks the parent's identity and age against a government-issued ID and records the *method* and the verifier, not the document. It then holds "reliable details of identity and age". An OTP to the parent's phone records the digital consent. Remote/production: a DigiLocker token (Rule 10(1)(b)(ii)). *Confidence: medium; a lawyer's check is still advised.*
  - **s.9(3) ban** → purpose- and age-aware routing (§10). Academic support is monitoring "for the educational activities" and is explicitly expected by MoE cl. 10.2(xi). Retention and fee prediction are gated for minors. Engagement/app tracking is never used for minors. No targeted advertising, ever.
  - **We stay a Data Processor.** The exemption only works when the *institution* is the fiduciary acting for its own educational activities. If we trained our own cross-tenant models on real minors' data, we would become a fiduciary for that purpose. So **global models are trained only on synthetic and public data, plus per-tenant calibration on that tenant's own data.** Cross-tenant pooling is limited to non-personal aggregates (item difficulty parameters, k ≥ 20), with the institute opting in.
  - s.9(2) (no detrimental effect on well-being) → the well-being rules below are a legal requirement, not just nice-to-have.
- **Notice** (s.5, Rule 3): standalone, itemised (each data field → purpose → service), in English and Hindi, with withdrawal as easy as giving consent (one tap). Built on i18n files so more Eighth-Schedule languages can be added later.
- **Commencement**: the Board has operated since Nov 2025. Consent managers from Nov 2026. **The substantive duties (notice, s.9 consent, Rule 6 security, Rule 7 breach) bind from ~13 May 2027.** We say: "compliant before the deadline, so institutes can adopt now."
- **Penalties for context**: up to ₹200 cr (children's obligations) and ₹250 cr (security safeguards).
- **Data location**: transfer abroad is allowed by default (s.16 negative list). We still default to India-region hosting in production and fully on-prem for the demo.
- **Purposes**: consent is purpose-wise and revocable, with the notice version and method recorded. Revocation → processing for that purpose stops, and derived scores are deleted.
- **Behavioural monitoring**: tier D (app engagement) is off by default and never needed for P0. Risk scores are used only for the child's benefit, visible to the mentor and owner, logged, and explainable, with a human decision before any outreach. No ads, no sale, no cross-tenant profiling.
- **Coaching regulation (verified from primary text, R4b)**:
  | Rule | Source | Product consequence |
  |---|---|---|
  | Assessment results must not be made public; use them for regular performance analysis and counselling for deteriorating students | MoE 2024 cl. 10.2(xi), p. 8 | Results private to student/guardian/mentor; no leaderboards. **The early warning → counselling flow is what the guideline asks for** (headline slide quote) |
  | No batch segregation on academic performance; batches formed by admission order and not changed until the course ends | MoE cl. 12(vii); Rajasthan Act s.12(ix) | No "auto-batch by score" feature; remedial help is a *supplementary session*; batch changes need a non-performance reason (logged) |
  | Weekly off; no test on the day after the weekly off | MoE cl. 10.1(v)–(vi) | Test-schedule check |
  | Pro-rata refund within 10 days (incl. hostel/mess) | MoE cl. 8(iv); Rajasthan s.13(4) | Refund calculator |
  | Counselling system available to students and parents | MoE cl. 11(ii); Rajasthan s.14(2) | Counsellor contact per institute; "counselling referral" is an intervention type |
  | Option of ≥ 4 equal fee instalments | **Rajasthan only**, s.6(2)(d) (corrected from 6(2)(e) after reading the enacted text, finance R2, 2026-10-20; not in the MoE guidelines). Commencement notification not found. | Fee plans support N instalments; Rajasthan profile defaults to 4 |
  | Batch size published, not increased mid-course | Rajasthan s.12(i) | Batch capacity field; warn on overflow |
  | Records "as may be prescribed"; penalties ₹50k / ₹2L / cancellation | Rajasthan s.15, s.19(1) | Register exports |
  Other states (from R5, secondary sources): Bihar Act 2010 in force; UP Act 2002 (written consent for student photos in ads); MP unclear. The MoE document is a *model guideline* for states, not a central statute.
- **Well-being**: no leaderboards or public ranks. The UI says "needs support." Parent reports never mention dropout risk or comparisons. Every flag maps to a supportive action. A counsellor/helpline field per institute. Copy reviewed against a banned-phrase list.
- **Security**: RLS + app filters, least-privilege roles, hashed secrets, encryption in transit (production) and at rest (DB-level), OMR images deleted after confirm, an audit log of risk-data views, no PII in logs, no PII sent to an LLM.
- **Retention**: delete student data N months after leaving (configurable). Export on churn.
- **MoE 2024 guidelines / state acts**: predictions shown as ranges with a disclaimer (no misleading results claims). Well-being features map to the guidelines' counselling provisions (R5).

---

## 16. Cost model (method; numbers after R3/R8/R9)

₹/student/month = (compute + DB + storage + backups + LLM + messaging + monitoring) / active students, for 3 scales (10, 50, 200 institutes × 300 students). Inputs are in `ops/cost_inputs.yaml`, each with a `source:` field. NB09 outputs a table plus sensitivity (LLM price ×5, template-only, WhatsApp off). The prototype runs at ₹0 locally; state that this is not production.

---

## 17. Edge cases

All of v1 §11 still apply (ingestion, OMR, analytics, risk, GenAI, platform). Added in v2:
- Blank vs wrong under negative marking (MNAR). Bonus/cancelled questions are marked correct for all, or removed from IRT.
- An untaught topic shows up as batch-wide failure → shown as a "topic coverage" issue, not student weakness.
- Marks-only institutes: test-level IRT (graded totals) → mastery shown at subject level only, clearly labelled.
- One guardian phone shared by siblings → one consent per child, reports kept separate.
- Student changes batch mid-year: history follows the student; batch-relative features use the batch at `as_of`.
- Model version changes mid-year: snapshots keep `model_version`, and trends never mix versions without a note.
- Judge enters absurd values (attendance 140 %, a negative fee) → validation error, not a crash.
- LLM returns invalid JSON or empty output, or takes too long (> 8 s) → template.
- Devanagari rendering offline: fonts self-hosted, PDF export with the font embedded.
- Clock and timezone: everything is in IST dates. A DD/MM/YYYY parser with an explicit per-file override.

---

## 18. Testing strategy

| Layer | Tests | Tooling | Gate |
|---|---|---|---|
| Contracts | Agents' outputs validate against schema.sql, openapi.yaml, CSV templates, metrics_bars | pytest, schemathesis, jsonschema | CI |
| Generator | Determinism by seed; marginal stats in bounds; truth consistency | pytest | CI |
| Leakage | Mutating any row with date > `as_of` leaves features unchanged | hypothesis | CI (blocking) |
| Scoring | Marking schemes, bonus questions, multi-correct, numeric tolerance | pytest + property tests | CI |
| Models | `evaluate.py` vs `metrics_bars.yaml`; regression vs last version (no metric drops > 2 pts unexplained) | pytest | CI |
| Robustness | Misspecified generators: metrics reported, not gated | NB07 | report |
| Ingestion | Golden files: dirty input → expected parse + expected error list | pytest | CI |
| OMR | Synthetic set accuracy; real-photo set accuracy; uncertain cells flagged | pytest + OpenCV | CI (synthetic), manual (real) |
| GenAI | Verifier fuzz (100 % catch); banned phrases; fallback when LLM is down; JSON-invalid handling | pytest with mocked LLM | CI |
| Security | Tenant A cannot read B by ID guessing (every endpoint); role matrix; RLS enabled on all tenant tables | pytest | CI (blocking) |
| Privacy | Consent revoked → no processing or report; tier D off by default; no PII in LLM payloads (assert on the captured prompt) | pytest | CI (blocking) |
| E2E | Upload → heatmap → support list → report; OMR path; what-if | Playwright | nightly + before demo |
| Chaos | Stop `llm`; network off; DB restart mid-upload; same file uploaded twice | `make chaos` script | before demo |
| Perf | 2,000 × 90 file < 30 s; batch recompute < 5 s; dashboard < 1 s on laptop | locust / timers | before demo |
| UX | Low-end Android emulation (Moto G / slow 3G); Hindi toggle on every screen; tap targets | Lighthouse, Playwright device | before demo |

---

## 19. Processes

- **Git**: one repo, `main` protected, one branch and one PR per agent task, squash-merge. Free GitHub Actions run `make test` + `make contract-test`.
- **Contracts**: version tag `contracts-v1.0`. Changes go only through `docs/contract_change_requests.md` → your approval → version bump → affected agents re-run.
- **Make targets**: `data`, `train`, `evaluate`, `test-<module>`, `e2e`, `chaos`, `demo` (clean clone → compose up → seed → open browser).
- **Daily integration**: `make demo` from a clean clone must pass. Red = stop new features.
- **Single source of numbers**: `metrics.json` → `scripts/deck_numbers.py` → deck/report. No hand-typed numbers.
- **Decision log**: `docs/decisions.md` (date, decision, why, alternatives). Judges' "why X?" answers come from here.
- **Agent hygiene**: each agent writes `docs/agent_logs/<agent>.md` (what it did, decisions, limitations, open issues). You review before merge.
- **Rehearsals**: 3 full demo runs + 5 curveball drills (§21), timed.

---

## 20. Agent plan

**Phase 0 (1 agent, you review):** `contracts/` + `metrics_bars.yaml` + `exam_patterns.yaml` + `topics.yaml` (with HI names). Blocks everything else.

**Phase 1 — Round 1 track (parallel):**
| Agent | Owns | Needs |
|---|---|---|
| A DataGen | `datagen/` (clean, truth, dirty, synthetic OMR) + NB01 | contracts, R4 |
| B IRT + Mastery | `ml/irt`, `ml/mastery`, NB02–03, NB07 (IRT part) | A sample |
| C Risk + Band | `ml/risk`, `ml/rank`, `ml/common/features`, NB04–05, NB10 | A sample |
| D Public validation | `scripts/download_public_data.py`, NB06 | R2 |
| E GenAI eval | `backend/app/genai` (pure module) + templates + NB08 | contracts, R3 |
| F Cost + OMR PoC (optional) | NB09, `backend/app/omr` core + NB11 | R8/R9; real photos |

**Phase 2 — Round 2 track:** G Backend (API, DB, RLS, ingest, auth, jobs) · H Frontend (against a mock server generated from OpenAPI) · I QA (golden files, isolation, E2E, chaos) · J DevOps (compose, Makefile, CI, seed) → **Integration agent** → rehearsals.

Agent prompt template: as in v1 §13.2, plus the "READ FIRST: contracts at tag X" and "Bars you must hit: metrics_bars.yaml keys …" lines.

---

## 21. Curveball drills ("a little technical")

| Curveball | 60-min response |
|---|---|
| "Behavioural monitoring of minors is banned" | Switch privacy tier → A/B; show the AUC change; consent screen |
| "Institute has only total marks" | Marks-only path: subject-level mastery, test-level IRT |
| "Add a new exam (CUET / Class 10 boards)" | New `topics.yaml` + `exam_patterns.yaml`; IRT is exam-agnostic; regenerate |
| "Dropout doubles / sudden-dropout share up" | Generator knob → retrain → show metric change + ceiling |
| "No GPU / LLM banned" | Template-only path; cost recomputed |
| "Internet down for a week" | Local-first already; P2 queue |
| "Parent says the prediction was wrong" | Show band, coverage, disclaimer, human review, feedback logged |
| "Judge's OMR sheet layout" | Template registry story + CSV path (+ P2 calibrator) |
| "Add a new risk factor (e.g. distance from home)" | Feature added to the builder + tier assignment + retrain (< 10 min) |

---

## 22. Known limitations (say them first)
- Synthetic results prove the pipeline, not real-world accuracy. Real validation needs a pilot (proposed: 2 institutes, one term, staggered rollout).
- Sudden dropouts are not predictable from academic data. We report the ceiling.
- Internal → NTA percentile mapping is an assumption until institutes contribute real outcomes.
- Cross-institute IRT comparability requires shared anchor items.
- Intervention impact (reduced dropout) is unproven without an A/B or staggered pilot.
- The local LLM's Hindi quality was checked by a small human panel, not at scale.
- OMR works on our template. Other layouts need one-time onboarding.

---

## 23. Open questions
| Q | Blocks | Status |
|---|---|---|
| NEET-UG 2026 exact pattern. R4b could not extract the bulletin PDF. We believe 2025 reverted to 180 compulsory Q / 180 min; R4 claimed 200 / 180 / 200 min | `exam_patterns.yaml` *values* (not the schema). Contracts proceed with both variants and `verified: false` | **Manual 5-min check of the NTA bulletin** (§24) |
| Whether the in-person ID check at admission satisfies Rule 10(1)(a) | §15 consent flow | Text supports it (medium); ideally a 15-min lawyer/professor check |
| Classic OULAD weekly baselines | NB06 | Not needed; the 2026 anchors are verified |
| Local LLM Hindi quality and tok/s on RTX 4060 | §11 | **We benchmark ourselves** (NB08) |
| Production hosting, LLM and WhatsApp prices (India) | §16 cost | R8, R9 (queued) |

---

## 24. Research log (R1–R5, integrated 2026-10-20)

### Decisions taken
| # | Decision | Source | Confidence |
|---|---|---|---|
| D1 | Verifiable parental consent for every minor; never rely on the exemption for consent | R1b: Rule 10 full text; 4th Sch. note (d) definition is broad (coaching *may* qualify), but Part A item 3 is purpose-limited. **R1's "coaching clearly excluded, High" was overstated** | High (text) |
| D2 | Purpose- and age-aware routing: academic-support ML for all; retention/fee ML gated for minors | R1b: Part A item 3 "for the educational activities"; MoE cl. 10.2(xi); "behavioural monitoring" undefined, no MeitY FAQ | Medium (interpretation) |
| D2b | Consent flow = in-person ID check by the institute (Rule 10(1)(a), Illustration Cases 3–4) + OTP record; DigiLocker in production | R1b Rule 10 text | Medium |
| D2c | No cross-tenant training on real minors' data; pool only non-personal aggregates | Inference from fiduciary/processor roles + exemption scope | Medium |
| D3 | DPA terms: 6 h breach notice to institute, logs ≥ 1 yr, deletion/return | R1: s.8, Rules 6, 7, 8 | High |
| D4 | Bilingual itemised notice; one-tap withdrawal | R1: s.5–6, Rule 3 | High (whether all 22 languages are mandatory is **overstated** in R1; the Act gives the *option* to access in English or an Eighth-Schedule language) |
| D5 | Build for the ~13 May 2027 enforcement date | R1 phased commencement | Medium-High |
| D6 | OULAD (CC BY 4.0) for dropout with day 14/28/42/60 windows; ASSISTments2009 under the pyKT protocol; EdNet optional only | R2, R2b (PLOS ONE 2026 e0352867; pyKT NeurIPS 2022) | High |
| D7 | Question bank = JEEBench (MIT, 515 Q, JEE Advanced, subject labels only) + self-tagged topics; NTA papers for internal eval only (no reuse licence) | R2 | High |
| D8 | Local LLM shortlist qwen3:4b vs gemma3:4b; IndicTrans2 as path B; no free APIs for PII | R3 | Medium (benchmark pending) |
| D9 | JEE Main: 75 Q (20 MCQ + 5 NVT per subject), +4/−1 incl. NVT, 300 marks, 180 min, no optional Qs | R4: NTA notices 2024–2026 | High |
| D10 | Dropped Q → +4 to all; multi-correct → +4 to anyone marking an accepted option | R4: NTA notice | High |
| D11 | Generator defaults (attrition 18 %, peak m3–4, 30/30/40 mix, fees, instalments, attendance, dips) | R4 | **Low–Medium** (many "inferred"); all knobs |
| D12 | Percentile tables as an editable assumption with a shift envelope | R4 (blogs/aggregators; NEET 2026 row is "projected") | **Low** |
| D13 | Compliance quick wins + no-ranking + no performance batching | **R4b primary text**: MoE cl. 8(iv), 10.1(v–vi), 10.2(xi), 11(ii), 12(vii); Rajasthan Act 16/2025 s.6(2)(d) [was mis-cited as 6(2)(e)], 12(i), 12(ix), 13(4), 14(2), 19(1) | High |
| D14 | Four equal instalments is a **Rajasthan** rule, not MoE | R4b | High |
| D15 | pyKT has no IRT/BKT baselines and no EdNet → our IRT/BKT results become new rows under the pyKT protocol | R2b | High |

### Slide-safe quotes (verified primary text, ≤ 30 words)
- MoE 2024 cl. 10.2(xi): results "should be used for regular analysis of performance of students and the student whose education performance is deteriorating, should be provided counselling". **This is our product's mandate in one line.**
- MoE 2024 cl. 12(vii): "Batch segregation on academic performance ground shall not be done".
- DPDP s.9(3): "shall not undertake tracking or behavioural monitoring of children".

### Claims still NOT trusted (keep off slides)
- **NEET-UG 2026 pattern**: unverified (bulletin PDF not extracted). Manual check: open `https://neet.nta.nic.in` → Information Bulletin 2026 → "Scheme of Examination" section; note questions per subject, whether Section B exists, total marks, duration, marking.
- R1's "coaching clearly not an educational institution (High)" and the "NCDRC" claim: **superseded by R1b** (the definition is broad; the exemption is purpose-limited).
- R1's "PAN against NSDL" detail: not in the Rule text.
- R1's claim that all 22 languages are mandatory: overstated.
- Coaching ops numbers marked "inferred" (class mix, upfront %, attendance): assumptions; label them so.
- Percentile tables: aggregator/blog data, and the NEET 2026 row is "projected".
- LLM tok/s: estimates; we measure our own.
- R5's state summaries for Bihar/UP/MP: secondary sources only.
