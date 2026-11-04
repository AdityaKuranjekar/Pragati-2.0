# Backend (Round 2): run steps, endpoints, measured results

Branch `claude/r2-backend-d476cf`. Code: `technical/backend/app/` (`main`, `config`, `deps`, `cli`, `routers/`, `services/`, `ml/`, `db/`; the existing `genai/` is reused, `omr/` belongs to another session). Tests: `technical/backend/tests/`. Saved models: `technical/ml/artifacts/models/`.

Everything runs on one Windows laptop with no Docker and no internet. PostgreSQL 16 comes from the `pgserver` Python package (it worked on Windows, so the in-memory fallback was **not** needed).

## Start it
Needs Python 3.12 with `fastapi uvicorn psycopg2-binary pgserver lightgbm scikit-learn pandas pyarrow openpyxl pyyaml python-multipart itsdangerous jinja2 jsonschema requests` (all already installed on the dev laptop). The synthetic data (`data/clean`, `data/truth`) is gitignored; the default path is the main checkout, override with `DATA_DIR`.

```bash
cd technical/backend
set PYTHONUTF8=1
python -m app.cli demo
```
or `make demo-native` from `technical/` if `make` exists. This starts the database (data folder `technical/.pgdata`, kept running between runs), applies `contracts/schema.sql` with row-level security, trains the models if `ml/artifacts/models/manifest.json` is missing, seeds if the database is empty, and serves **http://127.0.0.1:8000** (interactive docs at `/docs`). Point the front end at it with `NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000/api/v1`.

| Command | What it does |
|---|---|
| `python -m app.cli bootstrap` | database, schema, models, seed only |
| `python -m app.ml.train` / `make train` | retrain all saved models (about 10 s), rewrite `ml/artifacts/models/*` and the manifest with hashes |
| `python -m app.db.seed --force` / `make seed` | reseed (drops and recreates the schema) |
| `python -m pytest tests -q` / `make test-api` | all backend tests (about 3 minutes; they use their own database in `.pgdata_test`) |

Environment: `DATA_DIR`, `PG_DATA_DIR`, `DATABASE_URL` (use another PostgreSQL instead of pgserver), `SEED_INSTITUTES` (default `patna_jee,lucknow_neet,gaya_both`; `all` adds Kota with 2,000 students), `ASOF_NOW` (default `2026-09-01`), `PRAGATI_SECRET`, `OLLAMA_URL`, `PG_KEEP_RUNNING`.

Only the **2026 cohort** and its facts are loaded into the database (3 institutes, 1,450 students, about 1.1 M responses). Models are trained offline on all years from the parquet files.

## Auth and tenancy
`POST /auth/login {"institute":"patna_jee","role":"teacher"}` returns a signed token (itsdangerous, 12 h, **demo role switcher, no OTP**) and `/me` data. Roles: owner, admin, teacher, mentor, parent, student. For parent/student the token carries a `student_id` (the seeded demo student, or any student of that institute while `DEMO_MODE=1`). Send `Authorization: Bearer <token>`.
Every request connection runs `SET ROLE app_user` plus `app.institute_id`, so PostgreSQL row-level security applies to every query. Only `/auth/login` (to find the tenant) and the seed use the superuser connection. Other-tenant ids return 404; family roles can only read their own child (403).

## Endpoints (all under `/api/v1`; `/health`, `/version`, `/auth/login`, `/me` also at root)
| Method and path | Roles | Notes |
|---|---|---|
| `GET /health`, `/version` | none | db, Ollama (and pulled models), model version, hashes |
| `POST /auth/login`, `GET /me` | none / any | |
| `GET /batches`, `/batches/{id}/students`, `/tests[?batch_id=]` | staff | pickers |
| `GET /batches/{id}/heatmap[?top_topics=25&as_of=]` | staff | `mastery.json` shape (+`students`, `as_of`), wrong-key flags from the batch's last 3 tests |
| `GET /batches/{id}/support-list` | staff | `risk.json` shape, capped at the batch's mentor capacity; adds `p`, `model`, `track`, `excluded_no_consent`, `minors_on_full_track` |
| `GET /batches/{id}/percentile`, `/summary` | staff | `percentile.json` shape; counts |
| `GET /students/{id}/profile` | staff, own family | `student.json` envelope with one student |
| `GET /students/{id}/parent-view`, `/percentile`, `/reports` | staff, own family | `parent.json`, `percentile.json`, `reports.json` shapes |
| `POST /students/{id}/reports {"lang":"hi","use_llm":null}` | staff, parent | verified report, 8 verifier ticks, stored in `reports`; 403 without active `parent_reports` consent |
| `GET /tests/{id}/flagged-questions` | staff | point-biserial below 0.05 with 20+ answers; shows current and suggested key |
| `POST /answer-keys/{test}/{q}` | manager | new key version, re-score, difficulty refresh, recompute; returns before/after |
| `GET /owner/dashboard` | owner, admin | `owner.json` shape plus a live `compliance` block |
| `PATCH /students/{id}/attendance` | manager | `{"attendance_pct":30,"window_days":30}` or `{"date":..,"present":..}`; returns before/after, new list |
| `PATCH /students/{id}/fees` | manager | `{"instalment_no":1,"paid":false}` / `delay_days` / `amount_inr` / `paid_amount_inr` |
| `GET/POST /consents`, `DELETE /consents/{id}` | manager (DELETE: also own family) | withdrawal purges derived scores and recomputes |
| `GET/PUT /settings/privacy-tier` | owner, admin | tier A to D, legal flag for minors (needs `legal_opinion_ref`), measured ablation table, live list when `batch_id` is given |
| `POST/GET /students/{id}/interventions` | staff | supportive-action log |
| `POST /ingest/{students,guardians,attendance,fees,results,answer-key}` | manager | multipart `file`; optional `mapping` (JSON header→field), `test_id`, `test_name`, `batch_id`, `test_date`, `max_marks`, `commit=true` |
| `GET /ingest/jobs/{id}`, `POST /ingest/jobs/{id}/commit` | manager | status, mapping, errors; commit writes and recomputes |
| `GET /datacard`, `/scaling`, `/models` | any | static evidence files (+ runtime manifest) |
| `GET /{institute\|global}/{file}`, `/figures/{name}` | none | **exactly the mock API**: `ml/artifacts/<institute>/<file>.json`, no auth, synthetic files only |

Shapes are the artifact files' shapes; a few extra keys were added (zod ignores unknown keys). `POST /ingest/omr…` belongs to the OMR session. The frozen `openapi.yaml` was not made identical (plan decision 1); FastAPI's own `/openapi.json` is the real contract and a CCR is still to be logged.

### Ingestion behaviour
- Reads CSV (UTF-8, Windows-1252, comma, semicolon or tab) and XLSX (picks the sheet with the best header match, skips merged title rows, hidden rows, totals rows, evaluates formula cells through the cached value or the reference rule). Header mapping reuses `contracts/csv_templates/header_synonyms.yaml` (English, Hinglish, Devanagari), `Q.1/Ques 2/प्र. 3` question columns, and a fuzzy fallback; `mapping.detected` lists each column with a confidence. If required columns are missing the job is `pending_mapping` and the caller re-uploads with a `mapping` override.
- Row errors keep the reference parser's codes (`duplicate_roll_no`, `underage_enrolment_lt_16`, `negative_fee_amount`, `invalid_date`, …) plus roster errors (`missing_student_in_roster`, `unknown_batch`, `no_answer_key_for_test`). Warnings: minors needing consent, **under 16**, **test on the day after the weekly off**, tests that will be created, rows dated after the as-of date.
- Idempotent: the job key is the SHA-256 of file + kind + options. Re-uploading returns the same job (and `committed: true` if done); writes are upserts.
- An answer key with `test_name` + `batch_id` for an unknown test **creates** the test with questions and topics; wide or long response files are then scored from that key. Marks-only files create or update `test_totals` and do not touch mastery (no item data).

## Models at request time (`app/ml/`)
`irt.py` Rasch mastery (stored item difficulties, MAP per student and topic, bands, wrong-key detector, re-scoring); `risk.py` snapshot features, four saved LightGBM models (tiers A, A+B, A+B+C, A+B+C+D), routing from `contracts/routing_policy.yaml`, reasons from contribution values; `percentile.py` saved point model plus conformal half-width; `train.py` fits and writes `models/*` with a manifest. Nothing is trained in a request. Results are cached per (institute, batch, as-of) and every write drops the cache and recomputes synchronously, then writes `mastery_snapshots`, `risk_scores`, `predictions`.
Routing: under-18 students are scored on tier A only (`track: academic_support`); with the institute legal flag on they may use tiers B and C but never D (`retention_minor_opt_in`); adults use up to the institute's active tier, tier D only with their own `engagement_tracking` consent. No minor can reach the `full` track (tested).

## Measured results (this laptop, synthetic data, 25 Oct 2026)
**Tests: 73 passed** (`make test-api`, 175 s): 7 ML parity and routing, 12 golden parses, 12 dirty files through the API, 11 other ingest cases, 22 live edit and validation, 8 tenancy and role, 1 scripted live-edit run.
| Item | Result |
|---|---|
| ML parity vs `ml/artifacts/patna_jee` | Mastery: 1,860 cells, max difference 0.0005, 0 band differences. Percentile: 73 students, max difference below 0.15 points; conformal half-width 3.4349 equals the artifact exactly. Risk metrics of the saved models equal `metrics.json` (full AUC 0.8123, academic 0.6680). Support list: same 25 students as `risk.json`; about 80 % identical reasons and weights, the rest differ where a student has two tests on the same date (the reference sort has no tie-break). |
| Batch recompute (whole path: SQL load, Rasch, 4 models, percentile) | 60 to 70 students: 0.15 to 0.22 s; all 900 Lucknow students at once: 1.4 s (281,526 answered responses). Cut off is 5 s. |
| Live edits, 10 scripted rounds each (Patna, 60-student batch) | median / max: attendance edit 0.35 / 0.68 s, fee edit 0.34 / 0.36 s, answer-key fix with re-score 0.48 / 0.51 s, privacy-tier switch with new list 0.35 / 0.37 s, Hindi report 0.02 / 0.36 s, heatmap read 0.12 / 0.14 s. 70 of 70 edits under 5 s. |
| Ingest | 2,040-row attendance file (60 students x 34 days), preview and commit: 0.5 s. Marks-only file with new test and commit: 0.7 s. Not tested: a literal 2,000-student results file (Kota is not seeded by default). |
| Cold start from an empty folder | database init, schema, seed of 3 institutes: 21 s (`bootstrap`); first heatmap response after that: 3.5 s. |
| Reports | template path 0.02 to 0.36 s, 8 verifier ticks, Hindi contains Devanagari, placeholders replaced after verification. |

## Not done, cut, or not verified
- **LLM path not exercised.** Ollama is running on this laptop but only `nomic-embed-text` is pulled, so every report ran on the template path. `POST …/reports` checks `/api/tags` with a 0.3 s timeout and uses `qwen3:4b` or `gemma3:4b` only if present (6 s model timeout, then template). That path is unit-tested only inside `genai/tests`.
- **Hindi is unreviewed** (`hi_reviewed: false` in responses).
- OMR endpoints (other session). No hierarchical 2PL (Rasch only, as in the artifacts). The percentile mapping table is returned but **not editable** through the API. No interventions outcome analytics. Attendance, fee and ingest edits are not audit-logged because `audit_log.action` allows only ten fixed actions.
- **As-of date is fixed** at 2026-09-01 (`ASOF_NOW`). Data dated later (a judge uploading September attendance) is stored but ignored until `?as_of=` is passed on the read endpoints; the upload warns and suggests the date. Mastery uses all stored responses, like the artifacts.
- The 12 dirty files use their own roll numbers (`PAT-R001`…), which are not in the seeded roster, so through the API they show roster errors next to the golden parse errors; the golden comparison is done on the parser directly and matches all 12 (rows and errors).
- `GET /{institute}/{file}` is unauthenticated by design (mock parity) and serves only synthetic artifact files.
- Revoked or missing consents exclude a student from the ranked list (strict). The static artifacts list them with a flag, so parity is checked with consent enforcement off.
- Fee edits barely move risk (fee features carry little weight in the model); the test checks the recompute, not a direction. Attendance and fee edits on a minor correctly change nothing and say why (`note`).
- Kota (2,000 students) and `SEED_INSTITUTES=all` were not run. The 4-model ablation numbers are measured once offline on the 2026 synthetic snapshots, not per request.
- Windows only checked here; `make` may not exist on this laptop, use the `python -m` commands above.

## Front-end contract and OMR (added 25 Oct, second pass)
The server now follows `technical/web/API_CONTRACT.md` (read from the front-end branch) and keeps the earlier field names alongside (responses are supersets; requests accept both).
- **Login** takes `institute_id` (slug) or `institute`; returns `access_token`, `user{id, role, name, institute_id (slug), student_id}` and the old `token` / `me`.
- **CORS** allows any `http://localhost:<port>` and `127.0.0.1:<port>` with the `Authorization` header (tested for port 3100).
- **`GET /{institute|global}/{file}`** now needs a token; another institute is 403; parent and student only get their own `student_id` rows. `/figures/{name}` stays open (images cannot send a header).
- **Ingest:** upload returns **201** with the job preview (`status: preview`, `columns`, `targets`, `missing_required`, `errors` with `row`, `column`, `severity`, `message_en`, `sample_rows` and so on); unknown headers give a preview with `missing_required` instead of an error; `POST /ingest/jobs/{id}/mapping` re-validates the stored file; `POST …/commit` answers **202** with `status: running` after the write and recompute are already finished, and the next `GET` returns `done` (so the polling UI works, but the stages are not real background progress).
- **New/changed endpoints:** `GET /batches/{id}/tests`; flagged questions `{flagged:[…]}` with shares, `open|fixed`; `POST /answer-keys` accepts `{key}` and returns `rescored_students`, `recompute_ms`, `flagged`; attendance PATCH returns `track`, `effect` (`model|rule_only|none`), `on_support_list`, `recompute_ms`, `message_en/hi`; privacy tier GET/PUT use `tier: full|academic_only` plus `options`, `list_size`, `capacity_per_week` (A to D still accepted); consents list returns `items` + `summary` with `?q=`, POST takes `{roll_no, guardian_name, method}` (creates analytics, risk_alerts and parent_reports rows, 409 if active), DELETE returns `effect`; reports accept `language` and return `llm_requested`, `llm_available`, `fallback_used`.
- **OMR** (`app/omr/` merged from `claude/r2-omr-5efd0a`): `POST /ingest/omr` (optional form `test_id`; otherwise a UUID in the QR, otherwise the student's latest keyed test), `GET /ingest/omr/{job}`, `POST /ingest/omr/{job}/confirm {corrections, roll_no?}`. Poor photos or undecodable files return `status: retake`. Confirm needs every uncertain question corrected (422 text otherwise), scores with the stored key through the same path as CSV responses, recomputes the batch, returns `scored{correct, wrong, blank, marks, max_marks}`.
- **Models:** `.gitattributes` marks `technical/ml/artifacts/models/**` as `-text` (no CRLF rewrite), files are LF in git, loading strips CRs anyway, and `python -m app.cli demo` exits with a clear message if a model cannot be loaded.

Tests: **95 passed** (73 before, plus 11 front-end contract tests and the OMR flow; some earlier tests were updated for 201/202 and the token on artifact routes).

Still different from the contract: consent POST/DELETE and the ingest roles also allow `admin` and (consents) `teacher`, where the mock says owner only; `attendance_pct` as an ingest target (percent-per-student sheets) is not supported; commit stages are not real progress; OMR was tested on synthetic sheets only (accuracy numbers are in `OMR_README.md`); `kind: "parental"|"self"` in the ledger is derived from the verification method.
