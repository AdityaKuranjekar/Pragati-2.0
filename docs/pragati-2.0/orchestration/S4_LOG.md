# S4 log: prototype screens wired to the S3 API

**Date:** 2026-11-05. **Branch:** claude/serene-sagan-8za1vh (synced to origin/main first; no merge to main; no pull request).
**Untouched:** `backend/` (API, engine, migration), the 1.0 console, `components/shell.tsx`. Hosting and the public link are not part of this stage.
Work is in `frontend/app/(prototype)/`, `frontend/components/prototype/`, `frontend/lib/prototype/`, tests, and the files that run them (`package.json`, `vitest.config.ts`, `playwright.prototype.config.ts`).

## What changed from the earlier prototype
The earlier S0-era prototype computed estimates and next steps in the browser (`lib/prototype/engine.ts`, seeded simulator, in-browser attempts). All of that is **deleted**. The browser now only fetches and displays. It follows `DESIGN_BRIEF.md` (teal tokens, dark-mode overrides, 8px radius, no shadows), which replaces the later "console look, light only" restyle recorded in PROPOSAL section 9. Origin tags are printed literally (`[DEMO FIXTURE]`, `[SIM]`), replacing the plain-word chips of PROPOSAL section 10, as this task requires.

## Screens built
| Screen | Route | Reads |
|---|---|---|
| A Teacher cohort view (default) | `/prototype/teacher` (also `/prototype`) | bottlenecks, and state of each roster learner, as the teacher. Summary (learners, evidence coverage, bottleneck concept and learners blocked), group view, heatmap (band label as text plus answer count, "Insufficient evidence" marker, dashed warning style), click a learner for read-only detail, bottleneck panel with "proposed, not yet reviewed" in the warning colour. No attempt control exists in teacher mode (the component does not render one). `/prototype/teacher/bottleneck` shows the panel alone |
| B Learner next step | `/prototype/learner/[id]`, index `/prototype/learner` | state and next-step as that learner. `[DEMO FIXTURE]` label; one primary action; the reason, the evidence counts and the policy version exactly as returned; concept cards with band, `p_known ± uncertainty`, or "early estimate" when the band is insufficient. A non-demo learner id shows permission denied |
| C Practice | inside B | Items come only from next-step. With no served item: "No practice item is available. The item bank has no approved items yet..." plus the API's own reason. No placeholder question. After a submit, state and next-step are re-fetched; the browser never edits state |
| D Evaluation | `/prototype/evaluation` | `/api/proto/evaluation`, which reads `ml/evaluation/results/*.json` and applies the pre-registered decision rule. 32 rows (2 runs x 4 settings x 4 metrics), each with metric, task, origin `[SIM]`, baseline (fixed path), result, interval, Pass or Miss in identical row style |

The two misses named by the S2 log (reaching the goal concept; extra items to reach it) are in the table, post-hoc primary setting: reached goal difference −0.12 [−0.17, −0.07], items to goal +0.40 [+0.17, +0.62]. They are tagged "Named as a miss in the S2 log." Interpretation note: S2_FULL_LOG section 4.2 calls the goal-reach shortfall "a miss" and says the adaptive path "takes more items to it"; I read those as the two numbers. Check this reading.
Every state is implemented per screen: loading, empty, error (with retry), permission denied (no retry).

## How it connects (no host or token in browser code)
Browser calls the app's own routes under `/api/proto/`. `as/[principal]/[...path]` forwards an allow-listed set of API paths with the stub token for that principal; `config` serves cohort id and roster. Server environment, nothing committed:
`PROTOTYPE_API_URL`, `PROTOTYPE_TOKENS` (JSON role or learner id to stub token), `PROTOTYPE_COHORT_ID`, `PROTOTYPE_ROSTER` (JSON id, label, origin). `e2e/api/serve_demo_api.py` seeds the demo data for local runs (two `[DEMO FIXTURE]` learners from the engine fixtures, six `[SIM]` learners, fixed seed 20261105, bank with every item `pending`).

## Tests and counts (clean `npm ci`, then the commands below)
| Step | Result |
|---|---|
| `npm run lint` | no warnings or errors |
| `npm run typecheck` | passes |
| `npm test` (vitest) | **51 passed, 0 failed**, 3 files: components 28, evaluation 6, contract 17 |
| `npx playwright test -c playwright.prototype.config.ts` | **8 passed, 0 failed, 0 skipped** (5 desktop 1280x800, 3 phone 375x740) |

Covered: each band label as text; each empty state; unreviewed-edge marking (and a reviewed edge not marked); no attempt control for a teacher (panel and full-screen, and no non-GET call); submit then re-fetch; refusal shown in the API's words; denied, wrong-shape and error states. **Contract test:** starts the real API and parses real responses with the UI's own zod schemas (`lib/prototype/schemas.ts`), so a field the UI reads that the API does not return fails. It fails, not skips, if the API cannot start. Playwright path: teacher cohort view, learner next step (two learners get different steps), refused attempt, evaluation page, keyboard focus, phone no-horizontal-scroll.
Practice attempt: the page offers no control when no item is served, so the Playwright attempt is POSTed through the same forwarder the UI uses; the API answers 422, a teacher's attempt gets 403, and after a reload the state is unchanged.
Contrast, computed: body text 14.6 to 15.7 (light) and 13.5 to 15.3 (dark); muted text 5.4 to 7.4; warning text 5.1 to 7.4; band label pairs 4.7 to 10.0. Not run: a colour-blindness simulator, a screen reader.

Commands:
```bash
pip install -r backend/app/api_prototype/requirements.txt uvicorn
cd frontend && npm ci && npm run lint && npm run typecheck && npm test
npx playwright test -c playwright.prototype.config.ts   # builds the app, starts the API, uses /opt/pw-browsers/chromium when present
```

## Screenshots (deviceScaleFactor 2), `docs/pragati-2.0/orchestration/s4_screenshots/`
`01_teacher_cohort_light.png`, `02_teacher_cohort_dark.png`, `03_learner_next_step.png`, `04_evaluation.png`, `05_phone_teacher.png`, `05_phone_learner.png`, `05_phone_evaluation.png`.

## Stub, and not built
| Item | State |
|---|---|
| Sign-in | Stub tokens held in server env and chosen by the URL. NOT FOR PRODUCTION. Real auth is not built |
| Roster | The API has no route that lists a cohort's learners, so the roster and origin tags are configuration. A route is needed |
| Practice answering | The API returns an item id but no question text or key. The "Record as correct or incorrect" buttons exist only for a learner and only when the API echoes `demo_unapproved_allowed`; they record by hand. With the bank unapproved they never appear |
| Next-step side effect | A learner's page load serves an item (API behaviour); a teacher's does not |
| Evidence coverage, group counts | Counted from the bands the API returned (display only). `p_known ± uncertainty` is the API's heuristic, not a calibrated interval |
| Concept names | A three-entry label map for the demo concepts in `lib/prototype/labels.ts`; the API returns ids |
| Heatmap on phone | The table scrolls inside its own region (page does not scroll sideways) |
| Not built | Hosting, the public link, real auth, learner and cohort creation, the teacher override form from the brief (accept, modify, dismiss with reason), `[PUB]` and `[EXP]` rows (none computed), Playwright against a hosted URL. The evaluation route reads files from the repo at request time; hosting will need those files traced or copied at build |

## Still open
Owner review of the screens; the S2 "two misses" reading; list-learners route; ADR-003 acceptance; approved items and question text (until then practice is an empty state); override form; hosting (S0/S6).
