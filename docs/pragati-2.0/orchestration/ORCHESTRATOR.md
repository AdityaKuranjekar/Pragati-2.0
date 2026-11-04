# Orchestrator: Pragati 2.0 (this tab)

**Role.** This tab plans, routes, gates and reviews. It does not build modules itself. It hands self-contained work packages to cloud sessions and to on-computer sessions (Windows laptop, `data/` present), checks their output against the gates below, and keeps the decision log.

**Branch.** All work lands on `claude/serene-sagan-8za1vh`. Nothing goes to `main`. No pull request is opened unless the owner asks.

**Last checked:** 2026-11-04. Other tabs on this account (from `list_sessions`): none is a Pragati session. The visible ones are unrelated projects (GraphSmile, Adobe Hackathon, churn agents, and others). Nothing to reconcile yet. Sessions for Pragati are to be created when the owner approves the plan below.

---

## 1. Ground truth from the repo (what exists, checked)

| Fact | Evidence | Consequence |
|---|---|---|
| 31 tables | `contracts/schema.sql` (31 `CREATE TABLE`) | Matches the phase docs |
| No learner-facing attempt or event route | `grep` of `@router` decorators; `openapi.yaml` has 24 path entries | Phase 3 student journey has no backend yet |
| `responses` has no timestamp; key is (test, student, question) | `contracts/schema.sql` | No event log for knowledge tracing (B2) |
| `questions` has no question text | `contracts/schema.sql` | No content to show a learner (B3) |
| Exam values limited to `jee_main`, `neet_ug` | `topics.exam` CHECK | JEE Advanced and CET need a migration (B5) |
| 380 nodes (283 topic, 92 chapter, 5 subject) and **33 prerequisite edges** (0 dangling, 0 cycles, 0 self-loops); `verified: true` count = 0 | `contracts/topics.yaml`, parsed with PyYAML on 2026-11-04 | Graph is acyclic but sparse; curriculum unverified (B13, B14) |
| No Class 10 nodes; `class_level` allows only class_11, class_12, dropper | `contracts/topics.yaml`; `schema.sql` CHECK | A Class 10 foundation needs a schema change or new nodes (B5, B6) |
| 1PL Rasch runtime (`backend/app/ml/irt.py`); hierarchical Rasch only in validation | `irt.py` docstring; `ml/public_validation/assistments.py` | The 0.763 figure is not the served model (B9) |
| BKT (4-param EM) already implemented as a baseline | `ml/public_validation/assistments.py` (`BKTModel`), summary notes 0.7135 | Reuse; no need to write BKT from scratch |
| Minor-routing rule gates ML risk | `contracts/routing_policy.yaml` | Start point for B1 |
| Multi-tenant RLS on tenant tables | `schema.sql` (`app.institute_id`) | Reuse; add E13 tests for new routes |
| GenAI with deterministic verifier and template fallback | `backend/app/genai/README.md` | Reuse for explanations (E11) |
| Public data is local only | `.gitignore` (`data/`), CLAUDE.md §3 | Anything reading `data/` must run on the laptop |

## 2. Work packages

| WP | Work | Where to run | Needs `data/`? | Depends on | Output |
|---|---|---|---|---|---|
| WP1 | Phase 0 audit: repo map, feature inventory, DB audit, baseline tests | Cloud | No (tests with fixtures) | none | `docs/audit/*.md` |
| WP2 | Research R1 and R2 (legal and licences) | Cloud (web) | No | none | `docs/pragati-2.0/research/findings/` |
| WP3 | Research R3 to R10 | Cloud (web) | No | none | findings files |
| WP4 | ADR-003 event model and ADR-004 exam scope (design only, no migration) | Cloud | No | WP1 | `docs/architecture/decisions/` |
| WP5 | Re-run E1 and E2 with the 2.0 protocol; pre-registration file | **On computer** | **Yes** | WP1 | `ml/evaluation/` results, tagged `[PUB]` |
| WP6 | E3 simulator (independent of the estimator) and E0 fixtures | Cloud | No | WP4 | `ml/evaluation/sim/`, tests |
| WP7 | Curriculum: demo chain (B6), `verified` source per topic, item plan | Cloud for files; academic review by a human | No | WP3 (R3) | `data/curriculum/` is git-ignored: keep the content in `contracts/` or a new `curriculum/` folder (decide in WP4) |
| WP8 | Adaptive engine v0: BKT or Rasch state, prerequisite diagnosis, ranking with reasons, CF and graph module (B7) | Cloud | No | WP4, WP6 | `backend/app/intelligence/` (proposed) |
| WP9 | Student practice loop and teacher panel (Phase 3) | Cloud (code) | No | WP8 | Frontend routes |
| WP10 | Expert labels and teacher ratings (E4, E5, E6) | Human + on computer for logs | No | WP7, WP8 | `ml/evaluation/expert/` |
| WP11 | Full evaluation run, error analysis, honest report | **On computer** | Yes | WP5, WP8, WP10 | `docs/pragati-2.0/evaluation/RESULTS.md` |
| WP12 | Pitch, deck, demo script, backup recording | Cloud, then human | No | WP11 | `docs/pitch/` |

## 3. Gates

| Gate | Passes when | Blocks |
|---|---|---|
| G0 | WP1 audit done; R1 memo written; scope decision (B5, B6) made by the owner | Any schema or model change |
| G1 | ADR-003 (event model) and ADR-004 (exam scope) accepted; reversible migration written and tested on a copy | WP8 and WP9 |
| G2 | E0, E7 and E10 pass on the engine; no tenancy failure (E13) on new routes | WP9 and any demo recording |
| G3 | E1 and E3 re-run with pre-registration; results tagged and honest | Any "accuracy" or "recovery" claim on a slide |
| G4 | End-to-end journey works (student diagnostic → path → practice → new evidence → changed next step) with no manual DB edits | Teacher demo polish |
| G5 | E4 and E6 done, or the claim is removed; submission checklist done; backup recording made | Submission |

Rule: **do not polish a screen before its gate passes** (Phase 3 gate).

## 4. Session plan

| Session | Type | First task | Reads | Writes | Must not |
|---|---|---|---|---|---|
| Orchestrator (this tab) | Cloud | Plan, gates, review | All docs | `docs/pragati-2.0/**` planning files | Build modules |
| Audit | Cloud | WP1 | Repo; `docs/pragati-2.0/phases/PHASE_0_*` | `docs/audit/` | Change schema or models |
| Research-legal | Cloud | WP2 | Repo licence files; web | `docs/pragati-2.0/research/findings/` | Download datasets |
| Research-scope | Cloud | WP3 | Web | findings | Choose scope alone |
| Evaluation-local | **On computer** | WP5 | `data/public/`, `ml/public_validation/` | `ml/evaluation/`, results | Commit anything in `data/` |
| Engine | Cloud | WP4, then WP6 and WP8 | `contracts/`, `backend/app/ml/`, `ml/public_validation/` | `backend/app/intelligence/`, tests | Use the raw ASSISTments file in a test |
| Product | Cloud | WP9 after G2 | Frontend, API | `frontend/` | Compute mastery in the browser (Phase 3 §10) |
| Pitch | Cloud | WP12 | Results only | `docs/pitch/` | Quote a number without origin and task tags |

Cloud sessions cannot reach `data/`. Any step that needs the public datasets or the photographed OMR sheets goes to an on-computer session.

## 5. Decisions log

| # | Date | Decision | Why | Reversible? |
|---|---|---|---|---|
| D1 | 2026-11-04 | Demo chain in-graph JEE chain: `jee.math.complex_numbers.algebra_complex_argand` → `jee.math.quadratic_equations.roots_nature` (complex roots when the discriminant is negative) → `jee.math.quadratic_equations.equation_formation`. These edges do not exist yet and need teacher review (B14) (B6). Class 10 foundation optional. Owner to confirm. | Stays inside the existing JEE taxonomy; the prerequisite story is real once edges are reviewed | Yes |
| D2 | 2026-11-04 | Hackathon exam scope: JEE Main and JEE Advanced; CET after the loop passes; Olympiad deferred. Owner to confirm. | One concept graph, two patterns; smaller rights risk | Yes |
| D3 | 2026-11-04 | Under-18 learners: correctness-only evidence; no response-time or hint features until counsel answers B1. Owner to confirm. | DPDP s.9(3) risk | Yes, once counsel answers |
| D4 | 2026-11-04 | Collaborative filtering and graph algorithms added to Phase 2 (B7). | Named in the brief; missing from the plan | Yes |
| D5 | 2026-11-04 | Evaluation bars are proposals until written in `PREREGISTRATION.md`. | Prevents post-hoc passes | Yes, before a run only |

## 6. Phase updates made in this pass

See the "Update 2026-11-04" block at the top of each phase file and the new documents:

- `research/RESEARCH_PROMPTS.md`: ten self-contained research prompts with a findings register.
- `evaluation/EVAL_PLAN.md`: fifteen evaluation sets (E0 to E14) with origin tags, splits, baselines, proposed pass bars, sample sizes, and a re-mapping of every number already in the repo.
- `BLOCKERS.md`: fourteen blockers, fifteen risks, six assumptions, and four decisions for the owner.
- `orchestration/AGENT_PROMPTS.md`: ready-to-paste prompts for WP1, WP2, WP5, WP4 and WP6.
- `PITCH.md`: defining user, positioning, claims and their evidence, judge questions.

## 7. What the owner needs to do next

1. Confirm D1 to D3 (or change them). They gate WP4 and WP8.
2. Give the DataNova rules link or text (R4). Without it the rubric is a guess.
3. Choose which on-computer session will run WP5 (it needs `data/public/`; check the ASSISTments licence first, R2).
4. Approve creating the cloud sessions in §4. This orchestrator will not create them without approval.
5. Name the subject experts for E4 and E5 (B11). The sooner they are named, the sooner the labels can be done.
