# Pre-registration: E9 simulated comparison, fixed path vs adaptive path

**Written:** 2026-11-05, before the registered run. **Origin tag for every number it will produce:** `[SIM]`.
**Task tag:** simulated concept mastery under an equal item budget. This is not evidence of learning outcomes.
The results file records `code_commit` (the code that ran) and `prereg_commit` (the commit holding this file).

## Question
At the same number of items, does the adaptive path (concept choice from the prerequisite graph, item
band by challenge ladder, revision rechecks, budget check) leave simulated learners with more mastered
concepts, fewer items to the goal, and fewer prerequisite violations than a fixed curriculum-order path?
Which component, when removed, changes the answer?

## Design (fixed now)
| Item | Value |
|---|---|
| Simulator | `ml/evaluation/sim/simulator.py`; independent of the estimator (no import from `backend/app/intelligence`) |
| Concepts | 8 synthetic concepts c0..c7, edges c0>c1, c1>c2, c0>c3, c3>c4, c2>c5, c4>c5, c5>c6, c6>c7; goal c7 |
| Learners | **N = 500** per setting, generated from the master seed, identical across paths (common random numbers) |
| Master seed | **2026110501** (learner i uses the string seeds `seed:i:init` and `seed:i:resp`) |
| Item budget | **B = 60** item slots per path (4 per day, 15 days). Idle slots (nothing to do) still pass time. S3 uses B = 36 |
| Item bank | Synthetic, 14 easy + 14 medium + 14 hard per concept; target band = medium |
| Guessing / slip | 0.25 / 0.10 (4-option items); item band does not change correctness |
| Learning | After an answer on an unmastered concept: 0.15 if all prerequisites are mastered, 0.02 otherwise |
| Forgetting | A mastered concept is forgotten with probability 0.01 at each day boundary |
| Start state | Latent mastery respects prerequisites; P(start mastered) = sigmoid(theta - 0.5), theta ~ N(0,1) |
| Bootstrap | 2000 resamples of learners (indices shared across paths, so differences are paired), percentile 95% CI, seed 7 |
| Command | `python3 -m ml.evaluation.sim.compare --suite prereg --n 500 --seed 2026110501` |

### Paths (all given the same B)
| Path | What it does |
|---|---|
| fixed | Curriculum (topological) order, equal items per concept (extra items go to the earliest), always target band, no revision, no adaptation |
| adaptive | Engine `AdaptiveSession` with defaults: prerequisite chain, guided entry and challenge ladder (k=3, m=2), revision (2 days, x2, cap 30, x0.5 after an error), budget check |
| no_graph | As adaptive, but the concept is the unmastered one with the lowest estimate (ties by id); no prerequisite reasoning |
| no_challenge | As adaptive, but the band stays at the guided-entry band; no raise or lower |
| no_revision | As adaptive, with no recheck scheduling and no lapse handling |
| no_budget | As adaptive, but the budget check never defers rechecks |

### Settings
| Name | Change from the primary | Why it is here |
|---|---|---|
| P_primary_neutral | none | Difficulty band has **no** effect on learning (the simulator does not presuppose that the ladder helps) |
| S1_zone_learning | learning probability scaled 1.0 / 0.5 / 0.2 by distance between served band and latent readiness band | An **assumption** that matching difficulty helps; any ladder benefit here holds by that assumption |
| S2_no_forgetting | forgetting 0 | Revision has nothing to find; shows its cost |
| S3_short_budget | B = 36 | Exercises the short-budget mode |

## Metrics
| Metric | Definition | Better is |
|---|---|---|
| **final_mastered (primary)** | Latent concepts mastered at the end (0..8) | higher |
| items_to_goal | Items served until the goal concept is first mastered; censored at B | lower |
| reached_goal | Share of learners whose goal concept was mastered at some point | higher |
| violations | Items served on a concept that had a truly unmastered prerequisite | lower |
| items_used, rechecks | Descriptive | n/a |

## Decision rule (stated now)
For each setting and metric, take the paired difference (adaptive minus fixed; each ablation minus adaptive)
with its bootstrap 95% CI. Better-direction CI excludes 0: "better in simulation". CI contains 0: "no
evidence of a difference". Worse-direction CI excludes 0: "worse in simulation". The primary claim is
final_mastered in P_primary_neutral. All other cells are descriptive; there is no multiplicity correction and
they are not used to pick a winner.
Nothing here licenses the sentence "the adaptive path improves learning".

## Predictions written before the run (so misses are visible)
1. violations: adaptive lower than fixed, and no_graph higher than adaptive. (Expected from the design, not a finding.)
2. P_primary_neutral: no_challenge equals adaptive in expectation, because band does not affect anything in that model.
3. S2_no_forgetting: no_revision is at least as good as adaptive on final_mastered (rechecks spend items for nothing).
4. Unknown, and the main risk: whether adaptive beats fixed on final_mastered. Confirming mastery needs 5
   answers per concept (the engine's lucky-guess guard), which costs items the fixed path spends blindly. A loss or tie is plausible.
5. S3: no prediction.

## Limits (stated before the result)
- Every constant is an assumption. The simulator shares the author's mental model of learning; it cannot validate the engine against real learners.
- The engine receives the true graph. Robustness to a wrong graph is not tested here.
- Engine parameters (BKT, ladder k and m, revision interval) are fixed defaults and are **not** changed after any result. Fitting waits for E1.
- Not run: "no uncertainty" and "no difficulty-aware selection" ablations from EVAL_PLAN E9; learner subgroups; item-bank noise; wrong answer keys.

## Disclosure of earlier runs
The harness was run once before this file was committed, on 20 learners at seed 1, only to check it executes.
Its numbers were not used to choose any value above. One change was made after it: the budget given to the policy
is now the remaining slots (idle slots pass time) instead of items already served. That corrects what the input means; it was not tuned on results.

## Addendum 1 (2026-11-05, written after run 1)
Run 1 followed this file exactly (`ml/evaluation/results/e9_sim_v1_registered.*`, commit 5407be2). It exposed a planner
defect (a lapsed concept's recheck could be deferred under a short budget, so the lapse never cleared). The defect was fixed
with a regression test and the same suite was re-run as **run 2, post-hoc and not pre-registered**
(`e9_sim_v1_1_posthoc.*`). Same parameters, same seed, same N. Both runs are reported in `docs/pragati-2.0/orchestration/S2_FULL_LOG.md`.
The decision rule and the primary metric above were not changed. No engine parameter was changed.
