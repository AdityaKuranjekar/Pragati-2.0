# Pragati 2.0

Adaptive learning-path platform for JEE aspirants (Classes 11 and 12; Physics, Chemistry, Mathematics). It estimates what each learner knows, explains what to learn next, delivers practice, and measures whether the learner improved.

Current target: **DataNova Global Data-thon 2026**, problem statement "Adaptive Learning Path Recommendation" (personalised next-module recommendations with rationale). Submission needs code, documentation, an evaluation and a presentation.

The repository began as Pragati 1.0 (Case B, "The Data Moat", coaching-institute intelligence). Its working code is kept as the base for 2.0; the Case B business and pitch material has been removed (see [docs/CLEANUP_LOG.md](docs/CLEANUP_LOG.md)).

## Start here

| Read | Why |
|---|---|
| [docs/pragati-2.0/README.md](docs/pragati-2.0/README.md) | Phase plan, target architecture, product north star, dataset strategy |
| [docs/pragati-2.0/phases/](docs/pragati-2.0/phases/) | Phases 0 to 6, in order (audit first; no schema or model change before the audit) |
| [docs/pragati-2.0/orchestration/ORCHESTRATOR.md](docs/pragati-2.0/orchestration/ORCHESTRATOR.md) | Work packages, sessions and gates (how the project is run) |
| [docs/pragati-2.0/BLOCKERS.md](docs/pragati-2.0/BLOCKERS.md) | Blockers and owner decisions |
| [CLAUDE.md](CLAUDE.md) | Working rules for AI assistants and teammates |
| [docs/README.md](docs/README.md) | Index of every document in `docs/` |

## Folder map

| Folder | What it holds | Status |
|---|---|---|
| `backend/` | FastAPI app, PostgreSQL access with row-level security, ingestion, ML runtime, OMR reader, report pipeline | Working from 1.0; to be extended for 2.0 modules (curriculum, attempts, adaptive engine) |
| `frontend/` | Next.js 14 (TypeScript, Tailwind, ECharts) console and student views | Working from 1.0; needs a learner path and practice screens |
| `ml/` | Model build scripts, saved models (`artifacts/models/`), public-data validation (OULAD, ASSISTments) | Models were trained on synthetic Case B data; retrain for 2.0 |
| `datagen/` | Seeded synthetic data generator with ground truth | Case B institutes; adapt or replace for learner-interaction data |
| `contracts/` | Schema (`schema.sql`), OpenAPI, enums, topics, routing policy, metric bars | 1.0 contracts; the 2.0 data model is a Phase 0 decision |
| `scripts/` | Public-data download, contract and GenAI test runners | Keep |
| `notebooks/` | Public-validation notebook (ASSISTments and OULAD) | Keep |
| `docs/pragati-2.0/` | The 2.0 phase blueprint | Source of the current plan |
| `docs/legacy-case-b/` | 1.0 technical plan, feasibility checks, model tables, backend and OMR notes, Case B handoff | Reference only |

## What was removed and where it is

Removed from the working tree in the 2026-11 cleanup: the financial model, all Round 1 and Round 2 decks, deck build tooling, Round 1 and Round 2 plans, agent prompts and logs, feasibility simulations, and generated outputs for the Case B synthetic institutes. Each item is in git history at commit `512380d` on `main`. [docs/CLEANUP_LOG.md](docs/CLEANUP_LOG.md) lists them.

## Quick commands (Windows, offline; run from the repository root)

```
python -m pytest contracts/tests -q            # contracts (needs PostgreSQL via pgserver)
make test-datagen                              # synthetic data generator
make test-public                               # OULAD and ASSISTments validation (uses data/ downloads)
make test-genai                                # report generator and verifier
make demo-native                               # database, models, seed and API on http://127.0.0.1:8000
cd frontend && npm install && npm run dev      # front end on http://localhost:3000
```

Known gaps after the cleanup:
- `ml/artifacts/` no longer contains the per-institute JSON that the front-end mock reads. Regenerate after `datagen`: `python ml/build_artifacts.py`.
- Backend and front-end tests that compare against those outputs will fail until regenerated.
- `data/` (generated and downloaded datasets) is git-ignored; nothing in it is committed.

## Ground rules

- Free and local first: no paid service in the prototype; hosting per Phase 0 (Vercel, Render, Neon or Supabase, all free tier).
- No real student data. Public datasets are used under their own terms; JEE questions come from rights-cleared sources only (Phase 1).
- Every recommendation carries a reason a learner or teacher can read. The product must work without an LLM.
- Report every number with its origin (synthetic, public dataset, pilot) and state limitations before the judges do.
