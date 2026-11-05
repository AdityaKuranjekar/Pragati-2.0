# Hosted prototype plan (realistic)

**Status:** plan, 2026-11-05. Goal: a hosted link a judge can open and use in about five minutes, backed by real adaptive logic and honest evidence. This plan replaces the earlier "Phase 5 demo" timing with stages that have a gate each.

## 1. What the judge will see (scope that can actually ship)

| In the hosted demo | Not in the hosted demo (and why) |
|---|---|
| Two demo learners (fixtures, labelled `[DEMO FIXTURE]`) and one teacher view | Real student accounts (no real data; B1) |
| A 10-item diagnostic on the chosen chain (see below) | Full syllabus; 300-item bank (authoring is the bottleneck; see §4) |
| Concept profile per learner with uncertainty and evidence counts | Hindi UI (only if a Hindi reviewer signs off) |
| Next step with a plain-language reason, traced to the policy inputs | Parent reports, LMS, payments, OMR (1.0 code exists; not part of the 2.0 loop) |
| Practice; a new attempt; the next step changes | Olympiad and state CET content |
| Teacher panel: bottleneck concept across the cohort; override with reason | Any claim of learning gain (no pilot yet) |
| Evaluation page: each result with origin and task tag, misses shown | Collaborative-filtering recommendations for live learners (benchmark only at first; see §3) |

**The "wow" sequence to protect:** different evidence → different learner state → different next step → new evidence → changed recommendation. If time runs short, this is the one thing that must work.

## 2. The chosen demo chain (taxonomy-valid)

The taxonomy has no Class 10 nodes. The demo uses nodes that exist in `contracts/topics.yaml`:

```text
jee.math.complex_numbers.algebra_complex_argand   (Class 11)
        │  prerequisite (PROPOSED edge, teacher review pending)
        ▼
jee.math.quadratic_equations.roots_nature        (Class 11; complex roots when discriminant < 0)
        │  prerequisite (PROPOSED edge, teacher review pending)
        ▼
jee.math.quadratic_equations.equation_formation  (Class 11)
```

Only the edge `roots_nature` after `algebra_complex_argand` is needed for the story; the second edge is optional. Both are proposals. The demo must show them as **proposed, pending review** on the teacher panel. Showing unreviewed edges as fact would be the first thing a judge tests.

Items for the chain: 60 for the demo (20 per node), built through the dataset pipeline (`DATASET_PIPELINE.md` §4–§5). Two reviewers per item. This is the single largest schedule risk.

## 3. Architecture for the hosted link

| Layer | Choice | Why | Risk and mitigation |
|---|---|---|---|
| Frontend | Next.js on Vercel (account available: hobby plan, verified in this session) | Already in repo (`frontend/`) | Hobby terms are non-commercial. Fine for a hackathon demo; move to a paid plan before any commercial claim |
| Engine and API | FastAPI (same ASGI app either way) deployed as **either** Vercel Python functions **or** Render web service | Keeps the architecture; the code does not change | Render sleeps after inactivity (cold start). Decide after the Render account is connected. Recommended for the demo: Vercel functions, to keep one platform and avoid a second cold start; limits to be confirmed (R7) |
| Database | Neon Postgres | Free tier; SQL and RLS match `contracts/schema.sql` | Scale-to-zero adds latency on first query; warm with a health call before judging |
| Auth | Demo mode: fixed fixture users, no sign-up | No real personal data; avoids auth setup before the loop works | Production auth (Supabase or Firebase) is Phase 6 |
| Collaborative filtering | Offline benchmark on ASSISTments (research only); a results table on the evaluation page | Shows the method without a live CF model on sparse data | CF cannot serve JEE items yet (no interaction data); say so |
| Graph algorithms | Prerequisite traversal and a bottleneck score (personalised-PageRank style) on the teacher panel | Named in the problem brief; deterministic and testable | Scores on a sparse graph (33 edges across the taxonomy) are fragile; show the edge list and its review state |
| Evaluation | Static JSON produced by the pre-registered runs (`ml/evaluation/results/`) | Judges can see numbers without trusting the live app | Must be regenerated after any change to the engine |

**Cold start rule:** the judge should never see a blank wait. Show a loading state, warm the API before the presentation, and keep a recorded backup of the full journey.

## 4. Stage plan with gates

| Stage | Work | Output | Gate to continue |
|---|---|---|---|
| S0 | Connect hosting: Vercel project from the repo; Neon database; API health endpoint on the chosen host | A hosted "hello" page and a health endpoint | Both URLs respond from outside the sandbox |
| S1 | Demo chain: 60 items through the pipeline; topic tags; two reviewers each; proposed edges flagged | 60 validated items; graph with review states | `validate_item` passes for all 60 |
| S2 | Engine v0: per-concept Rasch or BKT state with uncertainty; prerequisite diagnosis on the chain; ranking with a stated reason; minor-safe features only | Engine module and tests | E0 (replay, invariants), E7 (no violations), E10 (cold start, sparse, contradictory) pass |
| S3 | API: learner state, next step, attempt submission (idempotent), teacher cohort | Routes plus tenancy tests (E13) for every route | Cross-tenant tests pass |
| S4 | Frontend: diagnostic, profile, next-step reason, practice, teacher panel, evaluation page | Hosted demo flow | Playwright run on the hosted URL passes the wow sequence |
| S5 | Evidence: re-run E1 and E3 with the pre-registration; publish results with origin tags; show misses | `RESULTS.md`, evaluation page | Numbers match the regenerated JSON |
| S6 | Hardening: warm-up, backup recording, offline snapshot of the demo, demo script | Recording; checklist | Dry run from a cold browser succeeds twice |

Stages S1 and S2 can run in parallel once the schema decision (ADR-003, event model) is accepted. S5 needs the on-computer re-run (WP5).

## 5. Acceptance criteria for the hosted link

- Opens in a fresh browser in under 60 seconds including cold start, with a loading state.
- The two demo learners produce different diagnoses and different next steps from the same engine.
- A submitted attempt changes the state and, where justified, the next step; the reason text names the evidence used.
- The teacher panel shows the bottleneck and marks the proposed edges as unreviewed.
- Every number on screen carries its origin (`[SIM]`, `[PUB]`, `[EXP]`, `[DEMO FIXTURE]`) and task.
- No ASSISTments or pending-source text appears anywhere in the UI or API responses (test by grep on responses).
- Playwright end-to-end passes against the hosted URL, not only localhost.

## 6. What I need from you to start the hosted build

| Item | Why | Status |
|---|---|---|
| Confirm the Vercel hobby plan is acceptable for a non-commercial demo | Frontend and possibly API hosting | Account confirmed in this session |
| Create or connect a Render account, or confirm Vercel functions for the API | Choose the backend host | Not available in this session (no tool) |
| Create or connect a Neon project and share a connection string through the Vercel environment, not the repo | Database | Not available in this session |
| Approve the 60-item demo bank approach and name two reviewers | Largest schedule risk | Pending |
| Send the official DataNova rules page | Sets the deadline and what the judges see | Not found online (see research findings) |
| Approve the D1 to D3 decisions | Demo scope | Pending |

I have not deployed anything yet. The current frontend shows the institute console on mock data; deploying it would show the wrong product. Stage S0 deploys only the new prototype.

## 7. Honest limits to say on stage

- The demo chain is 60 items and a 33-edge prerequisite graph, with two proposed edges. It shows the mechanism, not coverage.
- Mastery numbers are estimates from simulated or public data until the pilot runs (E8).
- Collaborative filtering is evaluated offline; live recommendations do not use it.
- The two learners are fixtures. Their starting states are simulator inputs, not measured outcomes.
