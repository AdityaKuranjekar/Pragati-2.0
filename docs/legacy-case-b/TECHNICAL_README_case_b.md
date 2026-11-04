# Technical: the Pragati platform (Case B: The Data Moat)

Pragati turns the data small coaching institutes already hold (OMR sheets, Excel, WhatsApp) into a topic-mastery heatmap, a weekly support list with plain reasons, an honest percentile range and a verified Hindi/English parent report. It runs fully **offline on one laptop**: no Docker, no paid API, no internet. Student data is **synthetic** (seeded generator with ground truth); methods are also checked on **public data** (OULAD, ASSISTments 2009).

## What works today
| Part | Where | What it does | Evidence |
|---|---|---|---|
| Contracts | `contracts/` | 31-table schema with row-level security, OpenAPI, enums, routing policy, 380-topic syllabus, CSV templates, OMR layouts | 14 tests |
| Synthetic data | `datagen/` | Seeded institutes (4 institutes, 3,450 students per academic year, 10,350 in total), truth tables, 12 messy exports with golden outputs, synthetic OMR sheets | 15 tests |
| Backend API | `backend/app/` | FastAPI on PostgreSQL 16 (via `pgserver`) with tenant isolation, login by role, CSV/XLSX ingestion with mapping preview and row errors, live what-if edits with recompute, consents, privacy tier, reports | 95 tests, edits under 1 s |
| ML runtime | `backend/app/ml/` | Rasch topic mastery, LightGBM early warning (age-routed), conformal percentile band, wrong-answer-key detection; models trained once and saved in `ml/artifacts/models/` | parity tests against the batch artifacts |
| OMR reader | `backend/app/omr/` | OpenCV: corner marks, warp, QR layout, bubble confidence, one-tap review of unsure cells | 0.9997 per question on 210 synthetic sheets, 6 tests; **no real phone photos tested** |
| Parent reports | `backend/app/genai/` | Facts from numbers, optional local model, 8-check verifier plus extra lexicon, template fallback | 68 tests, independent adversarial set |
| Front end | `web/` | Next.js console for owner, teacher, mentor, student and parent; Hindi/English; works offline and at phone width | typecheck, lint, build; 54 browser tests (against the mock server) |
| Public validation | `ml/public_validation/` | OULAD withdrawal and ASSISTments next-answer baselines | 8 tests (OULAD day-28 AUC 0.706, ASSISTments 0.763) |
| Artifacts | `ml/artifacts/` | Model results as JSON per institute, `metrics.json`, `models.json`, figures, samples | see `docs/MODEL_TABLES.md` |

Results are on synthetic data and several bars are not met (for example topic-ability recovery r about 0.53 against a 0.80 bar; the academic-only risk model that minors may use has AUC 0.67). `docs/MODEL_TABLES.md` states each number and what was not built.

## Run the demo (Windows, offline)
Needs Python 3.12 with the packages in `docs/BACKEND_README.md` and Node 20 or newer. The synthetic data folder `data/` is not in git; regenerate it with `python -m datagen --seed 42 --preset full --out data/` (about 30 s) or copy it in.
```
cd technical/backend
set PYTHONUTF8=1
python -m app.cli demo                    # database, schema, models, seed, API on http://127.0.0.1:8000
```
In a second terminal:
```
cd technical/web
npm install
set NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000/api/v1
npm run dev                               # http://localhost:3000, sign in as Teacher
```
Without the backend, `npm run dev` uses a built-in mock server. Details: `docs/BACKEND_README.md`, `web/README.md`, `web/API_CONTRACT.md`, `docs/OMR_README.md`.

## Run the tests
```
cd technical
python -m pytest tests -q                 # documents, deck and numbers (68)
make test-contracts                       # contracts (live PostgreSQL via pgserver)
make test-datagen && make test-public && make test-genai
make test-api                             # backend, ML parity, ingestion, OMR, tenancy (95, about 4 min)
cd web && npm run lint && npm run typecheck && npx playwright test    # front end (54)
```
Large local-only folders (not in git): `data/` (about 630 MB), `.pgdata/`, `ml/public_validation/.venv`, `web/node_modules`.

## Folder map
| Folder | What is in it |
|---|---|
| `contracts/` | Frozen schema, OpenAPI, enums, routing policy, metric bars, topics |
| `datagen/` | Synthetic data generator and curveball scenarios |
| `backend/` | API, ML runtime, OMR reader, report pipeline, tests |
| `web/` | Front end |
| `ml/` | `build_artifacts.py` and `build_datacard.py` (batch results and figures), `artifacts/`, `public_validation/` |
| `analysis/`, `notebooks/`, `scripts/`, `tests/` | Feasibility work, notebooks, deck-number tools, document tests |
| `docs/` | Plans, research, reviews, agent prompts (index: `docs/README.md`); start with `TECH_PLAN.md` and `BUILD_PLAN_R2.md` |

## Not done yet (honest list)
- Real phone-photo OMR accuracy, and the OMR review screen against the real server, are unverified.
- The local model path for reports (`qwen3:4b`, `gemma3:4b`) has not been benchmarked; reports use the verified template path.
- Hierarchical 2PL (Rasch is used), SHAP and survival models, and the 150-question tagging model are not built.
- The front end's browser tests run against the mock server; only login, the heatmap, the support list and the attendance edit were clicked through against the real one.
- Hindi text is unreviewed. Real WhatsApp sending is a preview only (paid, needs internet).
- Round 2 report, demo script, curveball drills and a clean-clone offline run are next; see `docs/BUILD_PLAN_R2.md`.
