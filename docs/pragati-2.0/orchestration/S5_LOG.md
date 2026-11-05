# S5 log: evidence the prototype can honestly show

**Branch:** claude/s5-evidence (from origin/main). **Not merged. No pull request opened** (owner has not asked).
**Every number below is tagged** by origin and task. Nothing here is evidence about real learners or about learning outcomes.

## 1. Status by set
| Set | Origin | Task | Status | Where |
|---|---|---|---|---|
| E3 | [SIM] | mastery recovery, latent continuous mastery and binary state at 0.85 | **Run, pre-registered, reported with misses** | `ml/evaluation/results/e3_recovery_v1.json` |
| E1 | [PUB] | next-response, ASSISTments 2009 | Pre-registered (no data downloaded). **Not computed** | `ml/evaluation/PREREGISTRATION.md`, `LAPTOP_RUN.md` |
| E2 | [PUB] | day-28 withdrawal, OULAD | Pre-registered. **Not computed** | same |
| E4 | [EXP] | root-cause diagnosis | 40 sheets and key written; **no expert labels. Not computed** | `ml/evaluation/review/` |
| E6 | [EXP] | teacher relevance of top-3 | 450 rows written; **no ratings. Not computed** | same |
| E9 | [SIM] | simulated adaptive vs fixed (S2) | Unchanged; shown on the page | `ml/evaluation/results/e9_*` |

## 2. Pre-registration and provenance
| Item | Value |
|---|---|
| Pre-registration entries (E3, E1, E2) | commit `f3e922d`, written 2026-11-05 13:30 IST, before any E3 code ran |
| Amendment 1 (command path only) | commit `82892a0`. The CLI is `recovery_run.py` because `recovery.py` must not import the engine. No design value changed. This is the `prereg_commit` in the results file |
| Code that ran (`code_commit`) | `ad47d93`. `recovery.py` and `recovery_run.py` are unchanged after it (checked) |
| Registered run | seed 2026110502, 500 learners per (concepts, depth) cell, 32 settings, 2000 learner bootstrap resamples, boot seed 7. Finished 08:06 UTC |
| Smoke test (disclosed) | seed 1, 20 learners per cell, run only to check the harness executes. Its numbers were not used to set anything |
| Generator sha256 / harness sha256 | `db3433ff…` / `5fafb645…` (full values in the results file `_provenance`) |
| Engine under test | `backend/app/intelligence/mastery.py` at `ad47d93`. **Parameters not fitted**: p_init 0.10, p_transit 0.20, guess 0.25, slip 0.10. The 0.85 threshold and the 5-answer guard are **design choices**, not fitted |

## 3. E3 results [SIM]
Truth: latent continuous mastery m (prerequisite-capped) and binary state m >= 0.85. Responses: correct with probability guess + 0.90 m. The engine estimate is the BKT posterior. The **80% interval is the engine's own uncertainty 1/sqrt(n+1), read as a standard deviation** (the engine produces no credible interval; this is not calibrated). The baseline is the raw share correct with a Wilson 80% interval, and the mastered prediction uses the same 0.85 and 5-answer guard.

Prevalence of latent mastery: 0.26 (10 concepts), 0.17 (30 concepts).

| Concepts | Depth | Guess | Items/concept | r [95% CI] (estimate) | r [95% CI] (raw-share baseline) | RMSE | Spearman [95% CI] | 80% coverage [95% CI] | State acc | State precision | State recall | Shows band | Pre-registered verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 10 | 1 | 0.25 | 10 | 0.67 [0.65, 0.69] | 0.82 [0.80, 0.83] | 0.34 | 0.77 [0.76, 0.79] | 0.74 [0.72, 0.76] | 0.58 | 0.38 | 0.98 | 1.00 | Miss: r and coverage |
| 10 | 1 | 0.25 | 20 | 0.69 [0.67, 0.71] | 0.90 [0.89, 0.90] | 0.35 | 0.84 [0.83, 0.85] | 0.57 [0.55, 0.60] | 0.54 | 0.36 | 1.00 | 1.00 | Miss: r and coverage |
| 10 | 1 | 0.25 | 3 | 0.56 [0.53, 0.58] | 0.62 [0.60, 0.64] | 0.29 | 0.58 [0.56, 0.60] | 0.97 [0.96, 0.97] | 0.74 | n/d | 0.00 | 1.00 | Miss: band shown below 10 items |
| 10 | 1 | 0.25 | 6 | 0.65 [0.63, 0.67] | 0.74 [0.72, 0.76] | 0.31 | 0.69 [0.67, 0.71] | 0.86 [0.85, 0.88] | 0.64 | 0.41 | 0.91 | 1.00 | Miss: band shown below 10 items |
| 10 | 1 | 0.40 | 10 | 0.55 [0.53, 0.57] | 0.74 [0.72, 0.75] | 0.40 | 0.70 [0.68, 0.72] | 0.64 [0.62, 0.67] | 0.48 | 0.33 | 0.98 | 1.00 | Miss: r and coverage |
| 10 | 1 | 0.40 | 20 | 0.54 [0.52, 0.56] | 0.84 [0.83, 0.85] | 0.43 | 0.77 [0.75, 0.79] | 0.48 [0.45, 0.51] | 0.42 | 0.31 | 1.00 | 1.00 | Miss: r and coverage |
| 10 | 1 | 0.40 | 3 | 0.46 [0.43, 0.49] | 0.52 [0.49, 0.54] | 0.32 | 0.49 [0.46, 0.51] | 0.94 [0.93, 0.95] | 0.74 | n/d | 0.00 | 1.00 | Miss: band shown below 10 items |
| 10 | 1 | 0.40 | 6 | 0.53 [0.51, 0.55] | 0.65 [0.62, 0.67] | 0.37 | 0.60 [0.58, 0.63] | 0.79 [0.76, 0.81] | 0.55 | 0.36 | 0.92 | 1.00 | Miss: band shown below 10 items |
| 10 | 3 | 0.25 | 10 | 0.70 [0.68, 0.72] | 0.84 [0.83, 0.85] | 0.35 | 0.80 [0.79, 0.81] | 0.73 [0.71, 0.75] | 0.63 | 0.41 | 0.99 | 1.00 | Miss: r and coverage |
| 10 | 3 | 0.25 | 20 | 0.71 [0.69, 0.72] | 0.91 [0.90, 0.91] | 0.37 | 0.85 [0.84, 0.86] | 0.57 [0.54, 0.60] | 0.59 | 0.38 | 1.00 | 1.00 | Miss: r and coverage |
| 10 | 3 | 0.25 | 3 | 0.59 [0.57, 0.61] | 0.66 [0.64, 0.68] | 0.29 | 0.62 [0.59, 0.63] | 0.96 [0.96, 0.97] | 0.75 | n/d | 0.00 | 1.00 | Miss: band shown below 10 items |
| 10 | 3 | 0.25 | 6 | 0.66 [0.64, 0.69] | 0.77 [0.75, 0.78] | 0.33 | 0.72 [0.70, 0.74] | 0.83 [0.81, 0.84] | 0.68 | 0.43 | 0.92 | 1.00 | Miss: band shown below 10 items |
| 10 | 3 | 0.40 | 10 | 0.57 [0.55, 0.59] | 0.77 [0.76, 0.79] | 0.43 | 0.74 [0.73, 0.76] | 0.61 [0.58, 0.64] | 0.51 | 0.34 | 0.99 | 1.00 | Miss: r and coverage |
| 10 | 3 | 0.40 | 20 | 0.54 [0.52, 0.56] | 0.86 [0.85, 0.87] | 0.46 | 0.80 [0.78, 0.81] | 0.46 [0.43, 0.49] | 0.45 | 0.32 | 1.00 | 1.00 | Miss: r and coverage |
| 10 | 3 | 0.40 | 3 | 0.49 [0.47, 0.52] | 0.56 [0.54, 0.58] | 0.34 | 0.52 [0.50, 0.54] | 0.93 [0.92, 0.94] | 0.75 | n/d | 0.00 | 1.00 | Miss: band shown below 10 items |
| 10 | 3 | 0.40 | 6 | 0.55 [0.53, 0.58] | 0.68 [0.66, 0.70] | 0.40 | 0.64 [0.62, 0.66] | 0.74 [0.72, 0.76] | 0.59 | 0.37 | 0.93 | 1.00 | Miss: band shown below 10 items |
| 30 | 1 | 0.25 | 10 | 0.68 [0.66, 0.69] | 0.82 [0.81, 0.83] | 0.37 | 0.77 [0.75, 0.78] | 0.69 [0.67, 0.71] | 0.63 | 0.31 | 0.99 | 1.00 | Miss: r and coverage |
| 30 | 1 | 0.25 | 20 | 0.69 [0.67, 0.70] | 0.90 [0.89, 0.90] | 0.40 | 0.83 [0.81, 0.84] | 0.53 [0.51, 0.55] | 0.57 | 0.29 | 1.00 | 1.00 | Miss: r and coverage |
| 30 | 1 | 0.25 | 3 | 0.56 [0.54, 0.58] | 0.62 [0.61, 0.64] | 0.31 | 0.58 [0.56, 0.60] | 0.95 [0.95, 0.96] | 0.83 | n/d | 0.00 | 1.00 | Miss: band shown below 10 items |
| 30 | 1 | 0.25 | 6 | 0.65 [0.63, 0.66] | 0.75 [0.73, 0.76] | 0.35 | 0.69 [0.67, 0.71] | 0.81 [0.80, 0.82] | 0.69 | 0.34 | 0.91 | 1.00 | Miss: band shown below 10 items |
| 30 | 1 | 0.40 | 10 | 0.55 [0.53, 0.56] | 0.74 [0.73, 0.76] | 0.46 | 0.71 [0.69, 0.72] | 0.56 [0.53, 0.58] | 0.49 | 0.25 | 0.99 | 1.00 | Miss: r and coverage |
| 30 | 1 | 0.40 | 20 | 0.52 [0.51, 0.54] | 0.84 [0.83, 0.85] | 0.50 | 0.78 [0.76, 0.79] | 0.39 [0.36, 0.41] | 0.42 | 0.23 | 1.00 | 1.00 | Miss: r and coverage |
| 30 | 1 | 0.40 | 3 | 0.46 [0.44, 0.48] | 0.52 [0.50, 0.54] | 0.36 | 0.48 [0.46, 0.50] | 0.91 [0.90, 0.92] | 0.83 | n/d | 0.00 | 1.00 | Miss: band shown below 10 items |
| 30 | 1 | 0.40 | 6 | 0.53 [0.51, 0.54] | 0.65 [0.63, 0.66] | 0.43 | 0.61 [0.58, 0.62] | 0.70 [0.68, 0.72] | 0.58 | 0.28 | 0.93 | 1.00 | Miss: band shown below 10 items |
| 30 | 3 | 0.25 | 10 | 0.67 [0.66, 0.69] | 0.82 [0.82, 0.83] | 0.38 | 0.77 [0.75, 0.78] | 0.68 [0.67, 0.70] | 0.63 | 0.31 | 0.98 | 1.00 | Miss: r and coverage |
| 30 | 3 | 0.25 | 20 | 0.68 [0.67, 0.69] | 0.90 [0.89, 0.90] | 0.40 | 0.82 [0.81, 0.83] | 0.52 [0.50, 0.54] | 0.58 | 0.29 | 1.00 | 1.00 | Miss: r and coverage |
| 30 | 3 | 0.25 | 3 | 0.56 [0.54, 0.57] | 0.62 [0.60, 0.63] | 0.32 | 0.57 [0.56, 0.59] | 0.95 [0.95, 0.96] | 0.83 | n/d | 0.00 | 1.00 | Miss: band shown below 10 items |
| 30 | 3 | 0.25 | 6 | 0.64 [0.63, 0.66] | 0.75 [0.73, 0.76] | 0.36 | 0.69 [0.67, 0.71] | 0.80 [0.79, 0.81] | 0.69 | 0.34 | 0.92 | 1.00 | Miss: band shown below 10 items |
| 30 | 3 | 0.40 | 10 | 0.54 [0.52, 0.55] | 0.74 [0.73, 0.75] | 0.47 | 0.71 [0.69, 0.72] | 0.55 [0.53, 0.57] | 0.50 | 0.25 | 0.99 | 1.00 | Miss: r and coverage |
| 30 | 3 | 0.40 | 20 | 0.52 [0.50, 0.53] | 0.84 [0.83, 0.85] | 0.51 | 0.77 [0.76, 0.79] | 0.38 [0.36, 0.40] | 0.42 | 0.23 | 1.00 | 1.00 | Miss: r and coverage |
| 30 | 3 | 0.40 | 3 | 0.46 [0.44, 0.48] | 0.51 [0.50, 0.53] | 0.37 | 0.48 [0.46, 0.50] | 0.91 [0.90, 0.91] | 0.83 | n/d | 0.00 | 1.00 | Miss: band shown below 10 items |
| 30 | 3 | 0.40 | 6 | 0.53 [0.51, 0.54] | 0.65 [0.64, 0.66] | 0.43 | 0.61 [0.59, 0.63] | 0.70 [0.68, 0.71] | 0.58 | 0.28 | 0.93 | 1.00 | Miss: band shown below 10 items |

### What the table shows (negative results first)
1. **The r bar (>= 0.80) is missed in every setting.** Best estimate r is 0.71 (CI up to 0.72).
2. **Coverage is missed at every item count from 10 up**, and falls with more items: 0.74 at 10 items, 0.57 at 20 (guess 0.25, 10 concepts). The interval shrinks while the estimate keeps a systematic bias.
3. **Below 10 items the engine shows a band, so the "not enough evidence" rule is a miss in all 16 settings at 3 and 6 items.** The engine's MIN_EVIDENCE is 3.
4. **The engine is worse than the raw-share baseline on correlation with latent mastery in every one of the 16 settings at 10 and 20 items.** Paired difference (estimator minus baseline) runs from -0.14 to -0.33, and every interval excludes zero. The baseline also has higher state accuracy (paired difference -0.22 to -0.48). This is the most important finding, and it is against the engine.
5. At 3 items the engine **never** says "mastered" (state recall 0.00, precision not defined in every bootstrap resample). That follows from its 5-answer guard.
6. Coverage at 3 items (0.91 to 0.97) is high, because the interval is wide there, not because the engine is well calibrated.

### Predictions written before the run, checked after
| # | Prediction | Outcome |
|---|---|---|
| 1 | No "mastered" at 3 items, so recall 0 | **Hit** (0.00 in all 8 cells) |
| 2 | r rises with items in every cell | **Partly missed.** Rises in all 8 guess 0.25 cells; in all 8 guess 0.40 cells r falls from 10 to 20 items (e.g. 0.55 to 0.54, 0.57 to 0.54) |
| 3 | r >= 0.80 fails everywhere | **Hit** |
| 4 | Guess 0.40 lowers r and precision | **Hit** at 10 items (r 0.55 vs 0.67, precision 0.33 vs 0.38) |
| 5 | Coverage falls with items from 6 up, below 0.75 at 20 | **Hit** |
| 6 | Band shown at 3 and 6 items is a certain miss | **Hit** |
| 7 | Depth has no predicted direction | Recorded; depth changes r by under 0.05 at most |

Full numbers, including Spearman, RMSE and every CI, are in `ml/evaluation/results/e3_recovery_v1.md` and the JSON. Some cells show `NaN` (state precision at 3 items) as Python writes it; the reader maps it to null. The file is therefore not strict JSON, and this is disclosed rather than changed after the run.

### Limits (stated before the run)
- Every generator constant is an assumption. The generator shares the author's model of mastery.
- **No item difficulty** is modelled, and the engine ignores difficulty in BKT anyway.
- The 1PL Rasch EAP baseline from EVAL_PLAN §E3 is **not computed** (no such estimator exists in the engine).
- The implied interval is not a credible interval. Coverage is a test of the engine's stated uncertainty.

## 4. Other sets: what was built and what is not computed
| Set | Built | Not computed, and why |
|---|---|---|
| E1 | Pre-registration with pass bar: 1PL beats logistic baseline with student-bootstrap CI excluding zero | No download. Baselines 1 to 3 (global, per-student, per-item mean) are **not in the 1.0 pipeline** and are not computed. The 0.7633 figure is the hierarchical model, not the served 1PL; the 1PL is pre-registered as the primary |
| E2 | Pre-registration with bar = 0.794 anchor (both point estimate and CI lower bound must reach it) | No download. The only result in the repo (0.706) **misses** the anchor by 0.088. The repo's gate (0.70, "report") and the README's "PASS" are **not** the pass bar. The product-relevant row is academic-only; VLE clicks are behavioural tracking and off for minors (DPDP s.9(3)) |
| E4 | 40 simulated cases (20 depth-1 and 20 depth-3 courses), root-cause key defined as the lowest-mastery frontier concept on the goal chain. Sheets show counts and the graph only; key kept apart | No expert has labelled them. **Not pre-registered yet**; must be before any label is read. The 20 teacher-written cases in EVAL_PLAN are not built |
| E6 | 50 profiles x three policies x top-3, shuffled, label removed; 450 rows | No teacher rating. The adaptive policy's top-3 is the engine's recommendation plus the next unmastered concepts; the reason shown is one neutral line for every slot, so **the engine's explanation text is not tested here** (that is E11) |

## 5. Tests (counts recorded at the end of the run)
| Suite | Command | Result |
|---|---|---|
| Engine and API prototype (backend, unchanged) | `cd backend && python3 -m pytest app/intelligence/tests app/api_prototype/tests -q` | **365 passed** |
| Evaluation (simulator, E3, review) | `python3 -m pytest ml/evaluation/tests -q` | **33 passed** (10 existing, 14 new E3, 9 new review) |
| Frontend unit | `npm test` | **66 passed** (6 existing evaluation, 28 components, 17 contract, 15 new states) |
| Frontend types | `npx tsc --noEmit` | clean |
| Prototype end-to-end | `npx playwright test -c playwright.prototype.config.ts` | **8 passed** (S4 tests unchanged and passing; 4 of the 8 screenshots regenerated) |

Tests added: E3 determinism; the generator never imports or names the engine; the simulator folder allowlist now includes `recovery_run.py` only; the sheet generator never opens a key (open() is monkeypatched to fail on key paths and the writers still succeed); committed sheets carry blank rater columns and no policy labels; keys are git-ignored; a missing file shows **not computed**, never zero; unreadable and wrong-shape files are refused; the committed E3 file produces 32 rows with the pre-registered verdicts; the NaN token parses.

## 6. Files
- `ml/evaluation/sim/recovery.py` (engine-free generator and metrics), `recovery_run.py` (harness)
- `ml/evaluation/review/`: `cases.py`, `sheets.py`, `keys.py`, `build.py`, the two CSV sheets, `manifest.json`, `keys/` (git-ignored)
- `frontend/lib/prototype/evaluation.ts`, `evaluation-files.ts`, `schemas.ts`, the route, the page component: read the result files and show every set
- `docs/pragati-2.0/orchestration/LAPTOP_RUN.md`

**Changed, not added:** `ml/evaluation/tests/test_sim.py` (one allowlist entry). `.gitignore` (keys directory). Page screenshots regenerated by the e2e run.

**Not touched (checked with git diff):** the engine (`backend/app/intelligence`), the API, migrations, the 1.0 console, `ml/dataset_pipeline/items/`, `ml/public_validation/`, `contracts/`.

## 7. Key-file hashes (keys are not in git)
Recorded in `ml/evaluation/review/manifest.json` under `key_files_gitignored`. Regenerate with `python3 -m ml.evaluation.review.build`. The keys are deterministic from the seeds, so a regenerated key must match.

## 8. What the owner must do next
1. **Laptop run (E1, E2).** Follow `docs/pragati-2.0/orchestration/LAPTOP_RUN.md` in a separate worktree. First check the ASSISTments licence (R2). Send back only the two raw JSON files, digests, commit and pip freeze.
2. **Expert raters (E4).** Two subject experts and an adjudicator fill `e4_root_cause_sheet.csv`. Pre-register E4 (κ, baselines, bar) **before** any label is read.
3. **Teacher raters (E6).** At least three teachers rate `e6_relevance_sheet.csv`, no more than two per profile. Pre-register the bar (adaptive Precision@3 >= 0.80, gap >= 0.10) first.
4. **Decide the E2 bar.** Keep the 0.794 anchor as the pass bar (recommended in EVAL_PLAN), or change it in `contracts/metrics_bars.yaml` and say so.
5. **Decision D15 (retention).** Still open in `ORCHESTRATOR.md`: how long to keep retention events. Needed before any real data, and before E2 is used for anything beyond a public-data check.
6. **Engine work the E3 run points to:** the BKT estimate is worse than the raw share on this generator. Any change must be pre-registered as a new run, not tuned against E3.
7. **Baselines 1 to 3 for E1** need adding, with tests, before that run.
8. **Approve the 60 demo items** (Aditya and Ashray). Nothing in S5 changes them.
