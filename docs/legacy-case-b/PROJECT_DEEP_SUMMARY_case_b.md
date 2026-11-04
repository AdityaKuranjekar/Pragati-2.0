# Pragati: deep project summary

Team AlphaQ · Nextute × Finance Club IIT Patna · Case B "The Data Moat"
Status as of 3 Nov 2026. Built from the repository docs, code layout and the Round 2 build plan. Test counts are the ones the READMEs state; they were not re-run for this document.

---

## 1. What it is built for

**The problem.** Tier-2 and Tier-3 JEE/NEET coaching institutes (roughly 150 to 1,200 students) keep their data in paper OMR sheets, Excel files and WhatsApp groups. Nobody sees, in one place, which topic each student is weak in. Staff cannot see early signs that a student is falling behind. The case guide's example puts mid-session dropouts at 8 to 15 percent, about ₹36,000 of fees per leaver, and ₹17.3 lakh a year for a 400-student institute at 12 percent. That last number is the guide's illustration, not measured data.

**The product.** Pragati turns the data an institute already has into four outputs:

1. **Topic mastery.** A heatmap of student by topic (380 topics in the syllabus), shown as bands (building, steady, strong, not enough data), never as a bare score.
2. **Weekly support list.** A short list per batch, capped at what a mentor can call in a week (8 students per batch in the deck's framing), with plain reasons and a supportive action. There are no public ranks for students or parents.
3. **Predicted performance range.** A percentile band, not a single rank, with an editable NTA mapping table (labelled as an assumption).
4. **Parent reports in Hindi and English.** Generated from numbers the system computes; every message passes eight automatic checks, and a human-written template is sent if any check fails.

**Who uses it.** Owner (business view), admin, teacher, mentor, student and parent. The demo signs people in by role with no password.

**The moat (as designed).** Institutes pool anonymised item statistics (how hard each question is), never student records, so the shared question-difficulty bank improves for everyone. This is simulated, not proven on real institutes (the simulation gives RMSE 0.22 with one institute's borrowing and 0.17 with twenty).

**Design principles that drive the code.**
- Local-first and free: one laptop, no paid API, no mandatory internet.
- Support, never surveillance: risk lists go to mentors and the owner only.
- Purpose- and age-aware: under-18s get academic-support models only; dropout and fee signals use transparent rules for them; engagement or app-activity tracking is never used for minors (DPDP Act s.9(3)).
- Honest uncertainty: "not enough data" is a normal output; missed gates are reported, not hidden.

---

## 2. What it does, end to end (the demo flow)

1. **Sign in** as a role (demo login, signed token, 12-hour lifetime).
2. **Capture.** Upload CSV or XLSX (students, attendance, fees, results, answer keys) or an OMR sheet photo. The system previews the column mapping, lists row errors, and commits in an idempotent job.
3. **Recompute.** Mastery, risk, percentile and reasons are recomputed for the batch using models that were trained offline and saved to disk. Requests never retrain.
4. **Look.** Teacher sees the heatmap, the flagged-question panel and the support list. Student and parent see their own view. Owner sees the dashboard, data card and scaling.
5. **Change an input live.** Edit attendance or fees, correct an answer key, or change the privacy tier. The list recomputes; the backend tests set a target of under 5 seconds per recompute and report edits under 1 second.
6. **Generate a report.** Hindi or English, verified, with a template fallback.
7. **Consent and privacy.** Consent ledger and privacy-tier page; withdrawing consent stops processing.

---

## 3. How it runs

**Requirements (Windows, offline):** Python 3.12, Node 20 or newer. No Docker.

**Start the backend and database:**
```
cd technical/backend
set PYTHONUTF8=1
python -m app.cli demo
```
This starts PostgreSQL 16 through the `pgserver` Python package (data in `technical/.pgdata`), applies `contracts/schema.sql` with row-level security, trains the models if they are missing, seeds the database if empty, and serves the API at http://127.0.0.1:8000 (interactive docs at `/docs`). `make demo-native` does the same from `technical/` if `make` is installed.

**Start the front end:**
```
cd technical/web
npm install
set NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000/api/v1
npm run dev
```
Open http://localhost:3000. Without the backend, the front end falls back to a built-in mock server that reads precomputed JSON from `technical/ml/artifacts/`.

**Environment variables** (backend): `DATA_DIR`, `PG_DATA_DIR`, `DATABASE_URL` (to use another PostgreSQL), `SEED_INSTITUTES` (default `patna_jee,lucknow_neet,gaya_both`; `all` adds Kota), `ASOF_NOW` (default 2026-09-01), `PRAGATI_SECRET`, `OLLAMA_URL`, `PG_KEEP_RUNNING`.

**Data.** The synthetic data folder `data/` is not in git (about 630 MB). Regenerate with `python -m datagen --seed 42 --preset full --out data/` (about 30 seconds).

---

## 4. What is inside (repository map)

```
FC_Case_Dhruvi/
  CLAUDE.md, README.md          handoff and folder map (CLAUDE.md §5 is out of date: see section 9)
  technical/                    the software, data generator, ML, tests and technical docs
  financial/                    the financial model (xlsx), audit, explainer PDFs, research R1 to R7
  presentation/                 the Round 1 deck (v1 to v6), previews, design system, scripts
  _archive/                     backups, not in git
  datamoat/, institute-intelligence-platform/   older folders, not reviewed for this summary
```

### 4.1 technical/

| Folder | What it holds | Status |
|---|---|---|
| `contracts/` | 31-table `schema.sql` with row-level security; `openapi.yaml` (23 endpoints in the contract); enums; `routing_policy.yaml` (age and purpose routing); `metrics_bars.yaml` (go-live gates); `topics.yaml` (380 topics); `datasets.yaml`, `marking_schemes.yaml`, `exam_patterns.yaml`; OMR layouts; CSV templates; JSON schemas for reports and metrics | Frozen at contracts-v1.0.0 with amendments; tests use a live PostgreSQL |
| `datagen/` | Seeded synthetic generator with ground truth; 4 institutes, about 3,450 students per academic year; 12 messy export files with golden outputs; synthetic OMR sheets; curveball scenarios | Built, 15 tests |
| `backend/app/` (about 8,400 lines) | FastAPI app. Subfolders: `db/` (connections, tenant session, seed), `routers/` (auth, system, read, write, ingest, consents, OMR API), `services/` (analytics, ingestion and parsing, scoring, profiles, reports), `ml/` (IRT, risk, percentile, training), `omr/` (reader, scoring, overlay, stress tests, evaluation), `genai/` (report pipeline, verifier, model clients, templates) | Built, about 95 tests (API, tenancy, ingestion, ML parity) |
| `backend/templates/` | Report templates (20 in the deck's count) | Built |
| `ml/` | `build_artifacts.py` (batch results and figures), `build_datacard.py`, `artifacts/` (JSON for each institute, saved models, figures), `public_validation/` (OULAD and ASSISTments checks) | Built |
| `web/` | Next.js 14 (App Router), TypeScript, Tailwind, ECharts, zod schemas per artifact, Playwright end-to-end tests | Built, about 54 browser tests against the mock server |
| `scripts/`, `analysis/`, `notebooks/`, `tests/` | Deck-number tools, feasibility analysis, notebooks, document and deck tests | Supporting |
| `docs/` | `TECH_PLAN.md` (source of truth, v2), `BUILD_PLAN_R2.md`, `ROUND2_PLAN.md`, `MODEL_TABLES.md`, `BACKEND_README.md`, `OMR_README.md`, `FEASIBILITY_CHECK.md`, `CITATIONS.md`, agent prompts and logs | Index in `docs/README.md` |

### 4.2 The backend in more detail

**Database and tenancy.** PostgreSQL 16 through `pgserver` (no Docker). Every request opens a connection that sets the app role and the institute ID, so PostgreSQL's row-level security applies to every query. Other institutes' IDs return 404; family roles can read only their own child (403). Only login and the seed use the superuser connection.

**Data model (31 tables in five groups).**
- People: institutes, users, students, guardians, batches, batch changes, consents, legal settings.
- Learning: topics, prerequisites, questions, question-topic links, item parameters, tests, test questions, answer keys, marking schemes.
- Results: responses, test totals, attendance, fees, engagement.
- Intelligence: mastery snapshots, risk scores, predictions, interventions, reports, model registry.
- Operations: ingestion jobs, OMR templates, audit log.
- Deliberately not stored: counselling notes or mental-health information, ID document images, student photographs, any public rank.

**Ingestion.** CSV and XLSX for students, attendance, fees, results (long, wide or marks-only) and answer keys. Header detection, synonym matching, merged-cell and footer handling, Devanagari text, negative fees, absurd dates and reused roll numbers. The mapping preview and row errors come back before commit. Commit writes to the database and triggers a batch recompute. Re-uploading the same file is idempotent. The 12 messy files are checked against golden outputs.

**Compliance checks at ingest.** Age under 16 is flagged; tests on the day after the weekly off are flagged (MoE 2024 rules as encoded).

**Endpoints built (sample, from the routers):**
- Auth and system: `POST /auth/login`, `GET /me`, `GET /health`, `GET /version`.
- Ingestion: `POST /jobs/{id}/mapping`, `POST /jobs/{id}/commit`, `GET /jobs/{id}`, OMR `confirm`.
- Batch reads: `heatmap`, `support-list`, `summary`, `percentile`, `students`, `tests`.
- Student reads: `profile`, `percentile`, `reports`, `interventions`, `parent-view`.
- Writes: `PATCH` attendance and fees, `POST` answer keys, `POST` consents, `DELETE` consent, `PUT` privacy tier, `POST` reports and interventions.
- Owner and evidence: `owner/dashboard`, `datacard`, `scaling`, `models`, figures.

The contract lists 23 endpoints; the routers implement the set the front end needs, with some additional read routes.

### 4.3 Machine learning

| Part | Method | Result on synthetic data (MODEL_TABLES.md) |
|---|---|---|
| Topic mastery | Rasch (1-parameter IRT) per topic, MAP ability with a N(0, 1.5²) prior, item difficulty from pass rates. Hierarchical 2PL is planned, not built. | Ability recovery r 0.53 vs raw share 0.49 (bar 0.80: missed). Difficulty recovery r 0.79 (bar 0.90: missed). |
| Wrong answer keys | Point-biserial below 0.05 flags a likely wrong key | Recall 0.75 on small counts |
| Early warning | Two LightGBM models: academic-only (minors) and full (18+ with consent). Reasons from contribution values mapped to fixed wording. Capacity-sized list. | Full model AUC 0.81, precision at capacity 0.32 vs 0.23 for the attendance rule. Academic-only AUC 0.67. Calibration error 0.005. |
| Percentile band | Point model plus conformal half-width, 80 % target; editable NTA mapping table | Coverage 0.80, half-width 3.4 points (synthetic) |
| Reports | Facts from numbers, verifier with 8 checks plus an extra lexicon, template fallback | 160 reports, all verified; the local-model path (qwen3:4b / gemma3:4b) has not been benchmarked |

**Public validation** (`ml/public_validation/`):
- OULAD withdrawal at day 28, student-grouped 5-fold: AUC 0.706 (published 0.794, so we report our lower number). Academic-only costs 0.008 AUC.
- ASSISTments 2009 next-answer under the pyKT protocol: AUC 0.763 against DKT 0.754, SAKT 0.725, AKT 0.785 (published).
- On OULAD the precision at top 10 percent is 0.46, against 0.24 to 0.31 for simple rules.

**Models are trained offline** (`python -m app.ml.train` or `make train`, about 10 seconds) and saved with a manifest and hashes in `ml/artifacts/models/`. Requests only run inference, and parity tests check the runtime against the batch artifacts.

**Not built yet (as stated in the docs):** hierarchical 2PL, SHAP (contribution values were used instead), survival models, the 150-question tagging model, and the local LLM benchmark.

### 4.4 OMR reader

Pure Python: OpenCV, NumPy, PyYAML, QR decoding through OpenCV.
1. Find the four corner marks, perspective-warp to a flat page.
2. Decode the QR code to pick the layout (fallback: ring match over all layouts).
3. Measure darkness of each bubble after removing shadows and paper baseline.
4. Mark at 0.22 fill or above; a second mark counts only if it is strong enough. Faint or weak marks go to one-tap review.
5. Retake verdicts for no corner marks, a small or dark or blurred sheet, or more than 20 percent unreadable questions.

Accuracy is 0.9997 per question on 210 synthetic sheets. **No real phone photos have been tested yet.** This is the biggest unverified claim.

### 4.5 Reports (GenAI)

- `backend/app/genai/`: pipeline, verifier, model clients (Ollama optional), templates, lexicon, cost and pricing files, an adversarial test set, and a model card.
- The verifier checks the numbers in the text against the numbers the system computed, the topic names, the trend, and the approved tips. Names are inserted after generation.
- If any check fails, the template goes out. The system does not depend on any model being available.
- Hindi text has not been reviewed by a native speaker (`hi_reviewed: false`).

### 4.6 Front end (technical/web)

- Next.js 14 App Router, TypeScript, Tailwind, ECharts for charts, zod for validating each artifact file, and bundled Devanagari and Inter fonts (no CDN).
- Screens: login, capture (spreadsheet and OMR), teacher (heatmap, flagged questions, support list, attendance edits), student profile, parent view with a WhatsApp-style preview, owner dashboard, privacy tier and consents, data card, how-it-works.
- Two data paths: the real API (set `NEXT_PUBLIC_API_BASE`) and a built-in mock server reading the artifact JSON. All HTTP goes through one client that handles tokens and 401/403.
- Phone width and offline behaviour are part of the design; the README reports they were checked.
- Students are never sorted by performance.

### 4.7 Financial model (financial/)

A live-formula workbook (`DataMoat_Financial_Model_CURRENT_v1.1.xlsx`) with sheets: Cover, Assumptions, Seasonality, Pricing, COGS_Build, Institute_ROI, Unit_Econ, Projection (3 years), Scenarios, Sensitivity, Checks, Sources, and hidden engine sheets. The Cover's C7 must show ALL CHECKS PASS before any number is quoted.

Headline (Mid institute, 400 students, Base, model output not measured):
- Effective dropout reduction 4.0 % (guide 25 %).
- Owner return 1.7x with admissions, 0.55x with fees and staff time only, 0.35x fees only.
- LTV ÷ CAC 3.6x discounted, 4.8x undiscounted (guide 10.7x). Payback 5.7 months.
- Contribution margin 78 %.
- Year-3 revenue ₹65.3 lakh, EBITDA ₹11.9 lakh, 58 paying institutes, funding ask ₹45 lakh, break-even month 16.
- Bear case funding ₹1 crore; Stress case (all inputs worst) returns 0.09x, used as a survival test only.

Unverified inputs (need owner interviews or a pilot): willingness to pay at ₹30, admissions uplift (1 %), pilot conversion (30 %), addressable market, recall and precision (placeholders until the ML numbers are final), mentor minutes per call, support cost per institute.

### 4.8 Presentation (presentation/)

- Round 1 deck in six versions. **v6** (`decks/AlphaQ_CaseB_Round1_v6_technical_update.pptx`, 23 slides) is the current technical update; v5 is the previous combined version.
- `source/build/` holds the generators (Node and Python), `update_v6.py` (text-level update of v5 to v6), `render_check.py` (overflow checker, approximate, no PowerPoint needed), and charts and map generators.
- Each slide's numbers come from the financial model or `metrics.json`. Amber PENDING tags mark numbers not yet measured.
- Known layout issue on slide 13 (tag labels overflow their boxes); present with a real PowerPoint export.

---

## 5. How it is built (engineering choices)

| Decision | Choice | Why |
|---|---|---|
| Database | PostgreSQL 16 via `pgserver` | Row-level security for tenant isolation; runs on Windows without Docker |
| API | FastAPI, uvicorn | Typed, fast to write, OpenAPI docs for free |
| ML | LightGBM, NumPy IRT, conformal prediction, OpenCV | Fast, explainable enough, free |
| Training vs serving | Train offline, save, infer in requests | Predictable latency for live edits |
| Front end | Next.js 14, TypeScript, zod | Typed artifacts, offline-capable build |
| Charts | ECharts | Rich heatmaps and fan charts, no CDN dependency |
| Reports | Templates first, LLM optional | Reports always work; the model is only an upgrade |
| Multi-agent build | Parallel agents against frozen contracts | Contracts first, then parallel work by branch |
| Data | Synthetic generator with ground truth | No real institute data; accuracy is measured against known truth |
| Validation | Public datasets (OULAD, ASSISTments) | Credible external baselines |

**Work process.** Contracts were frozen first (schema, OpenAPI, enums, topics, routing policy). Round 1 built the data generator, public validation and the report pipeline. Round 2 built the backend (P1 to P6 in `BUILD_PLAN_R2.md`), the OMR reader, and the front end on separate branches merged into `r2-integration`, then `main`. Git history on `main` shows the merges and per-area commits.

---

## 6. Honest status

**Working and tested (on synthetic data or public data):**
- Multi-tenant database with row-level security tests.
- Ingestion with mapping preview, row errors and idempotent commits.
- Live edits with recompute.
- Topic mastery (Rasch) with a small gain over raw percentages.
- Early-warning model for 18+ with consent; academic-only model for minors.
- Percentile bands at the target coverage on synthetic data.
- Verified report generation with template fallback.
- OMR reader on synthetic sheets.
- Front end on the mock and on the real API.

**Missed bars (reported as missed):**
- Difficulty recovery 0.79 against 0.90.
- Ability recovery 0.53 against 0.80 (raw 0.49).
- Wrong-key recall is small-sample.

**Not done:**
- Real phone-photo OMR accuracy.
- Hierarchical 2PL, SHAP, survival models.
- The 150-question tagging model.
- Local LLM benchmark (`qwen3:4b`, `gemma3:4b`).
- Hindi review by a native speaker.
- Real WhatsApp sending (preview only; paid and needs internet).
- Early-warning lead time and fairness gap.
- A pilot with a real institute. Willingness to pay and the uplift from acting on the list cannot be measured here.

---

## 7. How to verify the claims yourself

```
cd technical
python -m pytest tests -q                        # documents, deck and numbers
make test-contracts                              # contracts on live PostgreSQL
make test-datagen && make test-public && make test-genai
make test-api                                    # backend, about 4 minutes
cd web && npm run lint && npm run typecheck && npx playwright test
```

Financial model: open the workbook in Excel and check Cover C7. Verify with `python verify_model.py --all` in `financial/model/` (needs the `formulas` package, about 3 minutes).

---

## 8. Glossary

- **OMR**: optical mark recognition, the bubble-sheet exam.
- **IRT / Rasch**: a model of how hard a question is and how able a student is, from right and wrong answers.
- **Conformal prediction**: a way to give a range that covers the truth a stated share of the time (here 80 %).
- **AUC**: how well a model ranks people who will leave above those who will stay (0.5 is chance, 1.0 is perfect).
- **Precision at capacity**: of the students on the list (sized to what a mentor can call), the share who really were at risk.
- **LTV ÷ CAC**: lifetime value of a customer divided by the cost to win it.
- **Row-level security**: database rules that stop one institute's rows being read by another's login.
- **DPDP Act s.9**: India's data protection law; s.9(3) bars tracking children's behaviour, even with consent.

---

## 9. Things to fix in the handoff documents

- `CLAUDE.md` §5 still lists Wave 3 (backend, front end, OMR) as to do, and says Docker is not installed. Both are out of date: the backend, OMR and front end are built, and the backend runs without Docker.
- `technical/README.md` test counts come from earlier runs; re-run before quoting them.
- `MODEL_TABLES.md` gives per-institute wrong-key counts that do not obviously match the 0.75 recall it quotes. Check before presenting that number.
- The deck's slide 7 "PENDING" label on the shared item bank is intentional (not built).
