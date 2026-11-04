# Phase 0 — Codebase Audit & Product Foundation

> **Update 2026-11-04 (orchestrator pass).** Checked against the repo at `fe89cb4`:
> - 31 tables confirmed in `contracts/schema.sql`. No learner-facing attempt or event route exists in `openapi.yaml`.
> - **Blocker B2:** `responses` has primary key (test, student, question) and **no timestamp**. There is no ordered event log to replay, so knowledge tracing cannot be built on it. Add ADR-003 (append-only `attempt_events`) before Phase 1's gate.
> - **Blocker B3:** `questions` stores `text_hash` only; the product cannot show a question to a learner.
> - **Blocker B5:** `topics.exam` allows only `jee_main` and `neet_ug`. ADR-004 covers exam scope.
> - **Blocker B1:** `contracts/routing_policy.yaml` gates ML risk for minors; response-time and hint features (Phase 2) need counsel's answer on DPDP s.9(3) first (research R1).
> - Existing BKT (4-parameter EM) and a 1PL Rasch runtime exist; the 0.763 figure comes from a hierarchical model not served by the runtime (B9).
> - Phase 0 deliverables are now assigned: `docs/audit/*` (prompt P1), ADR-003, ADR-004 (prompt P4). See `orchestration/ORCHESTRATOR.md` and `orchestration/AGENT_PROMPTS.md`.
> - Gates G0 and G1 in `orchestration/ORCHESTRATOR.md` §3 define when Phase 0 is complete.

## 1. Purpose

Establish a verified understanding of the existing Pragati product and define the smallest high-impact Pragati 2.0 scope. This phase prevents a rewrite, duplicate database tables, and last-minute integration failures.

**Outcome:** a repository map, capability inventory, architecture decision record, baseline test report and frozen MVP scope.

### Current product decision

Pragati's first live target is **JEE institutes for Classes 11 and 12**. The MVP must support Physics, Chemistry and Mathematics, personal diagnostic profiles, adaptive learning paths, student progress dashboards, teacher intervention views and free-tier deployment. Do not freeze students into permanent ability categories; store concept mastery, uncertainty, pace and goal progress instead.

## 2. Current baseline to verify

The project summary previously supplied describes the following as existing or partially existing. Treat each as **reported, not independently verified** until inspected in the repository:

- Student-topic mastery heatmap and student performance prediction.
- Weak-topic identification and support recommendations.
- Question difficulty estimation.
- Teacher dashboard and Hindi/English parent reports.
- CSV/Excel and OMR ingestion.
- Topic prerequisite structure and student-specific reports.
- Next.js + TypeScript + Tailwind frontend.
- FastAPI backend, PostgreSQL, Python ML, scikit-learn and LightGBM.
- IRT/Rasch mastery logic and offline training / online inference separation.
- GenAI/LLM components.
- A database reportedly containing about 31 tables.
- A question-tagging model for approximately 150 questions described as unfinished.

Do not assume table names, route names, model interfaces or directory paths from this list.

## 3. Audit workstreams

### 3.1 Repository reconnaissance

Inspect and document:

- Root-level folders, package managers and application entry points.
- Frontend routes, layouts, role guards, components and API clients.
- FastAPI routers, dependencies, service modules, schemas and settings.
- Database ORM models, migrations, indexes, constraints and seed data.
- ML training scripts, inference interfaces, saved artifacts and evaluation notebooks.
- OMR/import pipelines, file storage and external integrations.
- Tests, CI workflows, deployment config, environment variables and secrets handling.

Useful commands (adapt to repository):

```bash
git status --short
find . -maxdepth 3 -type f | sort
# Python
python -m pytest -q
# Frontend
npm install
npm run lint
npm run typecheck
npm test
```

Never commit `.env`, credentials, student data, raw private datasets or model secrets.

### 3.2 Existing feature inventory

Create `docs/audit/feature_inventory.md` with columns:

| Capability | Exists? | Evidence (file/API/table) | Quality | Keep / Improve / Replace | Owner |
|---|---|---|---|---|---|
| Mastery estimation | TBD | TBD | TBD | TBD | TBD |
| Prerequisite graph | TBD | TBD | TBD | TBD | TBD |
| Question tagging | TBD | TBD | TBD | TBD | TBD |
| Adaptive path | TBD | TBD | TBD | TBD | TBD |
| Assessment attempt capture | TBD | TBD | TBD | TBD | TBD |
| Teacher interventions | TBD | TBD | TBD | TBD | TBD |
| OMR ingestion | TBD | TBD | TBD | TBD | TBD |
| Tenant isolation | TBD | TBD | TBD | TBD | TBD |

Mark a capability as complete only when there is code, a test and a working path through the product.

### 3.3 Database and data-flow audit

Produce:

- ER diagram for all current tables.
- Data dictionary with primary/foreign keys and tenant ownership.
- Map of student response ingestion → attempt storage → mastery update → analytics.
- Migration history and a backup/restore test.
- Identification of duplicate concepts (e.g. `topics`, `skills`, `concepts`) before adding new entities.
- Data retention, consent and deletion paths.

For every table, record: purpose, owner module, PII classification, tenant key, retention needs, indexes and dependencies.

### 3.4 Model and evaluation audit

For each model/rule, record:

- Intended prediction or decision.
- Input features and target label.
- Dataset provenance and license.
- Unit of split (student, session, time).
- Baseline and metrics.
- Calibration and uncertainty.
- Model artifact/version and inference latency.
- Known limitations and failure modes.

Previously reported figures that need verification and careful framing:

| Reported result | Context to retain |
|---|---|
| Mastery ability recovery r = 0.53 | Validate on held-out learners; this suggests room for improvement |
| Question difficulty recovery r = 0.79 | Verify sample size and split method |
| Early-warning AUC = 0.81 | Reported on synthetic data; not real-world validation |
| OULAD withdrawal AUC = 0.706 | Separate higher-education task |
| ASSISTments next-answer AUC = 0.763 | Knowledge/response prediction task |
| Synthetic OMR accuracy = 0.9997 | Must be tested on real photographed sheets |

Do not compare these numbers as if they measure the same task.

## 4. Product decisions to freeze

### 4.1 Product statement

“Pragati helps each learner understand what to learn next, provides a personalized path, and measures progress—while giving teachers actionable, explainable insight.”

### 4.2 User roles

- Student: sees next step, rationale, learning activity and progress.
- Teacher: sees class gaps, learners needing support and intervention suggestions.
- Academic admin: configures curriculum, cohorts, assessments and resources.
- Institute owner: sees organization-level outcomes and usage.
- Parent: receives appropriate progress summaries, subject to permissions.
- Platform operator: manages tenants, plans and system configuration.
- Online learning partner: integrates through controlled APIs.

### 4.3 MVP scope

**Must-have**
- One curriculum and one subject for the demo (recommended: Class 10 Mathematics, Quadratic Equations).
- Concept-level mastery profile.
- Explicit prerequisite graph.
- Diagnostic assessment and answer capture.
- Gap diagnosis with prerequisite reasoning.
- Explainable next-step recommendation.
- Student learning path and practice loop.
- Teacher cohort view.
- Evaluation against a fixed-path baseline.

**Should-have**
- LLM-assisted explanation grounded in approved content.
- Simple revision scheduling.
- CSV import for demo cohort.
- Teacher review/override.

**Defer**
- Full LMS/video/live-class/payment features.
- Separate adaptive engines for every education segment.
- Complex deep knowledge tracing unless baseline experiments justify it.
- Broad automated question generation without quality control.
- Microservices and elaborate event infrastructure.

## 5. Target folders and artifacts

```text
docs/
├── audit/
│   ├── repository_map.md
│   ├── feature_inventory.md
│   ├── database_audit.md
│   ├── model_audit.md
│   └── baseline_test_report.md
├── architecture/
│   ├── system_context.md
│   └── decisions/
│       ├── ADR-001-modular-monolith.md
│       └── ADR-002-adaptive-mvp-scope.md
└── product/
    ├── product_requirements.md
    ├── personas_and_jobs.md
    └── success_metrics.md
```

## 6. Architecture decision: modular monolith

Keep Next.js, FastAPI and PostgreSQL as the core. Organize FastAPI into domain modules and intelligence modules with explicit interfaces. Do not introduce a message broker, vector database or microservice unless a concrete use case needs it.

## 7. Tests and exit criteria

Phase 0 is complete when:

- [ ] The application can be run locally from documented steps.
- [ ] Baseline tests and known failures are recorded.
- [ ] Existing routes, tables, ML models and UI screens are mapped.
- [ ] Every reported feature is marked verified / partial / absent.
- [ ] Database backup and migration strategy is understood.
- [ ] One MVP curriculum and demo journey are selected.
- [ ] Architecture and API ownership decisions are documented.
- [ ] Team agrees on scope and acceptance criteria.

**Gate:** no schema migration or model replacement before the audit and ERD are reviewed.
