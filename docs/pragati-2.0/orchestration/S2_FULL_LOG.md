# S2 full log: item selection, challenge, revision, budget, simulated comparison

**Date:** 2026-11-05. **Branch:** claude/serene-sagan-8za1vh. **Owner review:** pending.
**Every number below is `[SIM]`**: simulated learners under stated assumptions, task "simulated concept
mastery under an equal item budget". None of it is evidence that the adaptive path improves learning.

## 0. Read this first
- The adaptive path leaves simulated learners with more mastered concepts and far fewer prerequisite violations than a fixed path **and reaches the goal concept less often**. Both are reported below. The goal-reach shortfall is a miss.
- The pre-registered run exposed a defect in the planner (a lapsed concept's recheck could be deferred, so the lapse never cleared). The pre-registered result is kept as run 1. The defect was fixed and the same suite re-run as a post-hoc run 2, labelled as not pre-registered. Both are shown.
- The simulation shows **no measurable benefit** of the challenge ladder (identical to the adaptive path when difficulty cannot matter, and no gain even when it is assumed to matter) and **no measurable benefit of revision** at this budget and forgetting rate. The prerequisite graph is the only component with a clear simulated effect.
- Not built or not run is listed in section 6.

## 1. Status by USP row
| # | Row | Built | Tested | Evaluated | Where |
|---|---|---|---|---|---|
| 3 | Item selection by difficulty, guided entry, no easy-only | yes | yes (21 tests) | `[SIM]` only, through the whole-path comparison; no separate selection ablation | `backend/app/intelligence/selection.py` |
| 4 | Challenge rule (raise after 3 correct in a row, lower after 2 wrong) | yes | yes (11 tests) | `[SIM]`: no measurable effect (section 4.3) | `challenge.py` |
| 5 | Revision (interval grows with each pass, shortens after an error, day number as input) | yes | yes (17 tests, plus planner tests) | `[SIM]`: harmful in run 1 because of the defect; no measurable effect in run 2 | `revision.py`, `planner.py` |
| 6 | Time, goal and pace (budget input, minimum-item path, no response time) | yes | yes (12 tests, including the regression) | `[SIM]`: helps under a short budget, mixed elsewhere | `policy.py` (`recommend_with_budget`), `planner.py` |
| 7 | Comparison with a fixed path, pre-registered | yes | yes (10 tests) | pre-registered, run, reported with misses | `ml/evaluation/` |

Rows 1 and 2 are unchanged from S2 (policy and BKT). Note: `README.md` in the repo's first checkout had no USP table; it was added on the remote branch and this work was done on top of it.

## 2. Commands and test counts
| What | Command (from repo root) | Result |
|---|---|---|
| Engine tests, all | `cd backend && python3 -m pytest app/intelligence/tests -q` | **97 passed** |
| of which the 36 from S2 (E0 21, E7 4, E10 8, demo 3) | same | unchanged, pass |
| of which new: A selection 21, B challenge 11, C revision 17, D budget and planner 12 | same | 61 new, pass |
| Simulator tests (independence, determinism, constraints) | `python3 -m pytest ml/evaluation/tests -q` | **10 passed** |
| Item pipeline tests (not changed) | `python3 -m pytest ml/dataset_pipeline -q` | 266 passed |
| Registered comparison (run 1) | `python3 -m ml.evaluation.sim.compare --suite prereg --n 500 --seed 2026110501` at commit 5407be2 | `ml/evaluation/results/e9_sim_v1_registered.json`, `.md` (44 s) |
| Post-hoc comparison (run 2) | same command plus `--note post_hoc --out ml/evaluation/results/e9_sim_v1_1_posthoc.json` at the fix commit | `e9_sim_v1_1_posthoc.json`, `.md` |

`backend/tests` (the 1.0 suites) was not run: `fastapi` is not installed in this environment, which is a gap in the environment, not a result.
Mutation checks done by hand and restored: raising on one correct answer fails 7 tests; removing the floor fails 3; removing the approved-only filter fails 4; allowing repeats fails 2.

## 3. What was built
| Module | Behaviour |
|---|---|
| `selection.py` | Scale easy=1, medium=2, hard=3 (documented, ordinal, not calibrated). Guided entry one band under the target if the estimate is under 0.5. Steps up through the ladder. Never repeats an answered item. Serves only `approved` items unless `allow_unapproved_demo=True`; the flag is echoed in the output and the trace and the reason says "DEMO ONLY". Returns `item_id`, `reason`, `trace`. A thin bank sets `bank_gap` instead of hiding it |
| `challenge.py` | Raise one band only after k=3 correct answers in a row at the current band; lower after 2 wrong in a row; hold otherwise. Ceiling = target, floor = target-1 (so a hard target never reaches easy). Evidence restarts after every change |
| `revision.py` | Interval 2 days, x2 per pass (cap 30), x0.5 after an error (floor 1). Day is an explicit integer; no clock import (tested). A wrong recheck marks the concept lapsed; the planner treats a lapsed concept as unmastered until a correct recheck. Policy is a configurable dataclass |
| `policy.py` addition | `recommend_with_budget`: same concept choice as `recommend`, plus best-case items needed (all answers correct), a minimum-item plan, a "short" flag (budget under 1.5 x best case) and a reason that says so. No timing parameter exists (tested) |
| `planner.py` | `AdaptiveSession` composes the above with component switches used by the ablations |
| `ml/evaluation/sim/` | `simulator.py` (independent of the estimator, enforced by test), `compare.py` (harness, the only file importing the engine) |

Draft items stay draft: **no item was marked approved**. The real demo bank has 60 items, all `pending`, with no hard items, and `equation_formation` has 20 easy items and no medium (tested as a finding). With a medium target the engine serves easy items there and sets `bank_gap`.

## 4. Simulated comparison [SIM]
Setup is in `ml/evaluation/PREREGISTRATION.md` (committed before run 1): 500 learners, seed 2026110501, 60 item slots, 8 concepts, bootstrap 95% CI over learners with paired resamples. Differences are adaptive minus fixed unless stated.

### 4.1 Run 1: pre-registered (planner defect present)
| Setting | final mastered (of 8) | reached goal (share) | items to goal (censored) | prerequisite violations (items) |
|---|---|---|---|---|
| P_primary_neutral | +0.63 [+0.42, +0.84] | -0.17 [-0.22, -0.13] | +0.52 [+0.30, +0.73] | -16.34 [-17.73, -14.92] |
| S1_zone_learning | +0.37 [+0.18, +0.56] | -0.17 [-0.21, -0.14] | +0.53 [+0.38, +0.67] | -17.88 [-19.34, -16.29] |
| S2_no_forgetting | +0.70 [+0.49, +0.91] | -0.18 [-0.23, -0.14] | +0.54 [+0.32, +0.76] | -16.72 [-18.03, -15.34] |
| S3_short_budget | +1.12 [+0.97, +1.27] | -0.13 [-0.16, -0.10] | +0.23 [+0.17, +0.29] | -12.87 [-13.76, -12.05] |

Mean final mastered: primary setting: adaptive 4.41 | fixed 3.78 | no_budget 5.02 | no_challenge 4.41 | no_graph 3.49 | no_revision 5.08.

### 4.2 Run 2: post-hoc, after the defect fix (not pre-registered)
| Setting | final mastered (of 8) | reached goal (share) | items to goal (censored) | prerequisite violations (items) |
|---|---|---|---|---|
| P_primary_neutral | +1.34 [+1.13, +1.55] | -0.12 [-0.17, -0.07] | +0.40 [+0.17, +0.62] | -13.99 [-15.36, -12.56] |
| S1_zone_learning | +0.68 [+0.49, +0.87] | -0.17 [-0.21, -0.14] | +0.51 [+0.37, +0.66] | -15.03 [-16.52, -13.50] |
| S2_no_forgetting | +1.44 [+1.24, +1.64] | -0.12 [-0.16, -0.06] | +0.40 [+0.17, +0.62] | -14.76 [-16.13, -13.43] |
| S3_short_budget | +1.12 [+0.97, +1.27] | -0.13 [-0.16, -0.10] | +0.23 [+0.17, +0.29] | -12.87 [-13.76, -12.05] |

Mean final mastered: primary setting: adaptive 5.12 | fixed 3.78 | no_budget 5.02 | no_challenge 5.12 | no_graph 3.49 | no_revision 5.08.

Reading, using the pre-registered decision rule:
- **final_mastered (primary, P_primary_neutral):** adaptive better in simulation in both runs (run 1 +0.63 [+0.42, +0.84], run 2 +1.34 [+1.13, +1.55]).
- **violations:** adaptive lower in every setting and run. It is not zero: in the primary setting run 2 still serves about 9.6 of 60 items on a concept with a truly unmastered prerequisite, because the estimate can say "mastered" when the latent state is not (guessing, forgetting). E7's zero is about the policy against its own estimates, not against the truth.
- **reaching the goal concept: a miss.** Adaptive reaches the goal concept in fewer simulated learners than fixed in every setting (run 2 primary: -0.12 [-0.17, -0.07]), and takes more items to it. Only 1.6% of simulated learners start with the goal mastered (measured, seed 2026110501), so the gap is not a starting-state artefact. The cause was not tested. A plausible but unverified explanation: the engine waits for 5 answers and an estimate of 0.85 before it moves on from a concept, so it stays longer on each node than the fixed path's flat 7 or 8 items, and the goal is the last of eight. On the goal-concept metric the fixed path is better.
- **Registered prediction 4 (adaptive might lose):** it did not lose on mastery count; it did lose on goal reach.

### 4.3 Ablations: change in final mastered when a component is removed (path minus adaptive)
Run 1 (defect present):

| Setting | no_graph | no_challenge | no_revision | no_budget |
|---|---|---|---|---|
| P_primary_neutral | -0.92 [-1.14, -0.70] | +0.00 [+0.00, +0.00] | +0.67 [+0.47, +0.87] | +0.61 [+0.45, +0.77] |
| S1_zone_learning | -0.74 [-0.92, -0.55] | +0.03 [+0.00, +0.07] | +0.27 [+0.14, +0.42] | +0.53 [+0.39, +0.66] |
| S2_no_forgetting | -1.08 [-1.30, -0.86] | +0.00 [+0.00, +0.00] | +0.78 [+0.59, +0.97] | +0.59 [+0.44, +0.75] |
| S3_short_budget | -1.32 [-1.49, -1.15] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | -0.24 [-0.37, -0.12] |

Run 2 (post-hoc):

| Setting | no_graph | no_challenge | no_revision | no_budget |
|---|---|---|---|---|
| P_primary_neutral | -1.62 [-1.84, -1.41] | +0.00 [+0.00, +0.00] | -0.04 [-0.22, +0.16] | -0.09 [-0.23, +0.05] |
| S1_zone_learning | -1.05 [-1.23, -0.87] | +0.03 [-0.01, +0.08] | -0.04 [-0.18, +0.12] | +0.22 [+0.08, +0.35] |
| S2_no_forgetting | -1.82 [-2.05, -1.60] | +0.00 [+0.00, +0.00] | +0.04 [-0.14, +0.21] | -0.15 [-0.28, -0.01] |
| S3_short_budget | -1.32 [-1.49, -1.15] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | -0.24 [-0.37, -0.12] |

Prerequisite violations when a component is removed (path minus adaptive), run 2:

| Setting | no_graph | no_challenge | no_revision | no_budget |
|---|---|---|---|---|
| P_primary_neutral | +29.61 [+28.17, +31.03] | +0.00 [+0.00, +0.00] | +4.43 [+3.12, +5.74] | -5.61 [-6.51, -4.72] |
| S1_zone_learning | +27.34 [+25.92, +28.79] | -0.12 [-0.36, +0.09] | +5.45 [+4.09, +6.73] | -9.20 [-10.28, -8.17] |
| S2_no_forgetting | +30.76 [+29.34, +32.14] | +0.00 [+0.00, +0.00] | +4.07 [+2.92, +5.25] | -4.99 [-5.85, -4.16] |
| S3_short_budget | +19.44 [+18.53, +20.33] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | -3.23 [-3.82, -2.64] |

| Component | Simulated result |
|---|---|
| Prerequisite graph | Removing it lowers mastery and raises violations in every setting and run. This is the one clear effect |
| Challenge ladder | `no_challenge` equals `adaptive` exactly when band cannot affect learning (as predicted), and gives no loss even when band is assumed to help (S1 run 2: +0.03 [-0.01, +0.08]). No evidence the ladder helps. Likely reason (not tested): correct runs of three come mostly from learners who already know the concept, so the ladder rises after mastery, not before it |
| Revision | Run 1: removing it **helped** by about 0.7 concepts (defect). Run 2: no detectable difference at 1% forgetting per day (P: -0.04 [-0.22, +0.16]) and none at 0% (S2: +0.04 [-0.14, +0.21]). No evidence revision helps at this budget |
| Budget check | Under the short budget (S3) removing it hurts: -0.24 [-0.37, -0.12], so it helps there. In S1 removing it helps (+0.22 [+0.08, +0.35]) and in S2 it hurts (-0.15 [-0.28, -0.01]). Mixed; the 1.5 slack is an untuned guess |

### 4.4 Registered predictions against outcomes
| # | Prediction | Outcome |
|---|---|---|
| 1 | Adaptive violations below fixed; no_graph above adaptive | Hit |
| 2 | no_challenge equals adaptive when band has no effect | Hit (exactly equal) |
| 3 | In S2, no_revision at least as good as adaptive | Run 1 hit (+0.78, defect). Run 2: no difference (+0.04) |
| 4 | Unknown whether adaptive beats fixed on mastery | Adaptive better on mastery, worse on goal reach |
| 5 | S3 no prediction | Adaptive better on mastery (+1.12 [+0.97, +1.27]); worse on goal reach |

## 5. Defect found and fixed (disclosure)
Run 1 showed `no_revision` and `no_budget` both beating the full adaptive path, which is implausible for a middle option. A diagnostic on 60 learners at an unrelated seed found 789 of 3,519 adaptive steps (22%) practising a lapsed concept while its recheck was unavailable (a short budget deferred it, and a lapse clears only through a correct recheck). Fix: a short budget never defers the recheck of a lapsed concept; regression test added. Run 1 stays in the repo as the pre-registered result. Run 2 is post-hoc and any gain from the fix should be read as a corrected implementation, not as a new finding. No BKT, ladder or revision parameter was changed.

## 6. Still not built or not shown
| Item | State |
|---|---|
| Any approved item | None. Review by Aditya and Ashray (`ml/dataset_pipeline/reviews.py`) has not happened; nothing can be served to a learner |
| Hard items; medium items for `equation_formation` | Missing from the draft bank |
| Calibrated item difficulty | The scale is the author's intent labels |
| Prerequisite role in revision priority (USP row 5 names it) | Not built; revision uses time and errors only |
| Diagnostic design (the first items) | Cold start is guided entry only |
| Persisting the day number | Needs its own ADR (ADR-003 admits no extra fields) |
| API routes and UI for selection, ladder, revision, budget | S3 and S4 |
| E9 ablations "no uncertainty" and "no difficulty-aware selection" | Not run |
| Robustness to a wrong prerequisite graph; item-bank noise; wrong keys in the simulation | Not run |
| Goal-reach shortfall | Open; not tuned (changing the policy after seeing it would need a new pre-registration) |
| E1 on the served model, then fitting BKT parameters | Waits for E1 |
| E3 recovery run, E4, E6 | Not run |
| E8 pilot, any claim of learning gain | Not allowed; needs legal clearance and a randomised pilot |
| `backend/tests` (1.0 suites) in this environment | Not run (`fastapi` missing) |
