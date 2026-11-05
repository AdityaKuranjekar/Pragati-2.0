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

---

# Pre-registration: E3 mastery recovery on simulated learners (`[SIM]`)

**Written:** 2026-11-05 13:30 IST, before any E3 code was run. **Origin tag:** `[SIM]`.
**Task tag:** recovery of each learner's latent concept mastery from simulated responses, judged against the
product's mastery threshold. Not evidence about real students.
The results file records `code_commit` (the code that ran) and `prereg_commit` (the commit holding this file).

## Question
Given the attempts a learner makes, how well does the engine's BKT fold (`backend/app/intelligence/mastery.py`,
fixed parameters, not fitted) recover each concept's latent mastery, at how many items per concept, and with
what error? Does the engine's stated uncertainty cover the truth at the nominal 80% level?

## Design (fixed now)
| Item | Value |
|---|---|
| Generator | `ml/evaluation/sim/recovery.py`; imports nothing from `backend/app/intelligence` (enforced by test) |
| Engine under test | `fold_concept` / `band_for` / `ConceptState.uncertainty` as they stand at `code_commit`. Parameters not changed |
| Master seed | **2026110502** (distinct from E9) |
| Learners | **N = 500 per (concepts, depth) cell**; the same 500 learners are used for every item and guessing setting in that cell (common random numbers) |
| Concepts | C in {10, 30} |
| Prerequisite depth | D in {1, 3}: the longest prerequisite chain has D edges. Concepts split into D+1 contiguous layers; each concept in layer l >= 1 has one or two (50/50) prerequisites in layer l-1 |
| Concept difficulty | b_c ~ N(0, 0.5), drawn once per concept from the graph seed |
| Learner ability | theta ~ N(0, 1) per learner |
| Latent mastery (truth, continuous) | Layers in order: raw_c = sigmoid(2 (theta - b_c)); m_c = min(raw_c, min over prerequisites of m_p + 0.10); no prerequisite means m_c = raw_c |
| Latent mastery state (truth, binary) | M_c = 1 if m_c >= 0.85 (the product threshold), else 0 |
| Responses | Item j on concept c is correct if u < g + (1 - g - s) m_c, with s = 0.10 and u ~ U(0,1) from the stream `seed:i:C:D:c`. Item j uses u_j, so the first k items of a longer run equal a shorter run |
| Guessing g | 0.25 and 0.40 (same u for both, so the guessing effect is paired) |
| Items per concept k | 3, 6, 10, 20 (prefixes of the same stream) |
| Item difficulty | **Not modelled** in E3 (the engine ignores difficulty in BKT; the simulator does not add it). Stated as a limit |
| Estimator output | `p_known` from `fold_concept` (events in seq order 0..k-1); `band` from `band_for`; uncertainty `1/sqrt(n+1)` from `ConceptState` |
| Estimator implied 80% interval | p ± 1.2816 x uncertainty, clipped to [0, 1]. **The engine produces no credible interval.** This is the engine's own stated heuristic read as a standard deviation. It is not calibrated, and the result is reported as coverage of that implied interval, not of a credible interval |
| Estimator mastered prediction | band == "mastered" (requires p >= 0.85 and n >= 5; design choices, not fitted) |
| Baseline B0 (raw share correct) | estimate = correct / k; 80% interval = Wilson score (z = 1.2816); predicted mastered = share >= 0.85 and k >= 5 (the same guard) |
| Bootstrap | 2000 resamples of learners (indices shared across estimator and baseline, so differences are paired), percentile 95% CI, boot seed 7 |
| Command | `python3 -m ml.evaluation.sim.recovery --suite prereg --n 500 --seed 2026110502 --out ml/evaluation/results/e3_recovery_v1.json` |

BKT parameters are the engine's fixed defaults: p_init 0.10, p_transit 0.20, guess 0.25, slip 0.10. **They were not fitted.** The 0.85 mastery threshold and the 5-answer guard are design choices. Guessing 0.40 is outside the engine's 0.25 guess parameter by design (misspecification).

## Metrics (per setting, over all learner x concept rows, N x C rows)
| Metric | Definition | Better is |
|---|---|---|
| **pearson_r (primary)** | Pearson correlation of estimate with continuous latent m | higher |
| spearman_rho | Spearman correlation, same pairs | higher |
| rmse | Root mean squared error of estimate against m | lower |
| coverage80 | Share of rows with m inside the implied 80% interval | 0.75 to 0.85 |
| state_accuracy | Share of rows where predicted mastered equals M | higher |
| state_precision | TP / predicted mastered; null when nothing is predicted mastered | higher |
| state_recall | TP / truly mastered | higher |
| share_shown_as_band | Share of rows where the engine shows a band (not "insufficient") | descriptive |
| prevalence | Share of rows with M = 1 | descriptive |

Paired differences (estimator minus B0) with bootstrap 95% CIs for pearson_r, spearman_rho, rmse, coverage80, state_accuracy.

## Pass bar (proposed in EVAL_PLAN §E3, applied per setting at k in {10, 20})
- **r:** pass if the 95% CI lower bound of pearson_r is >= 0.80.
- **Coverage:** pass if the 95% CI lies inside [0.75, 0.85].
- **Below 10 items:** EVAL_PLAN requires "not enough evidence" to be shown. The check is whether the engine shows a band at k = 3 and 6. A band shown at k < 10 is recorded as a **miss** against that rule.

## Predictions written before the run (so misses are visible)
1. At k = 3 the estimator predicts "mastered" for **no** row (it needs 5 answers), so state_recall is 0 at k = 3.
2. Point estimates of pearson_r rise with k in every (C, D, g) cell.
3. The r >= 0.80 bar fails in **every** setting. The estimator is a binary model with a transit term, scored against a continuous truth. A run of correct answers pushes p upward, so it over-states intermediate mastery.
4. At the same k, guessing 0.40 lowers pearson_r and state_precision compared with 0.25.
5. Coverage of the implied interval falls with k at k >= 6, because the width shrinks while the upward bias stays.
6. Prediction 2 and 3 are the expected results from the design. The engine's shown band at k = 3 and 6 is a certain miss against the EVAL_PLAN "not enough evidence" rule.
7. Depth has no predicted direction; the engine has no prerequisite term, so depth acts only through the truth.

## Expected limits (stated before the result)
- Every constant of the generator is an assumption. The generator shares the author's mental model of mastery; it cannot show that the engine works for real learners.
- No item difficulty; no response time (none is in the engine by design).
- The implied interval is not a credible interval. Coverage on it is a test of the engine's stated uncertainty, not of a calibrated model.
- The baselines are the raw share and the engine itself. The 1PL Rasch EAP baseline from EVAL_PLAN §E3 is **not computed** here (it would need a new estimator that is not in the engine). It is reported as not computed.
- The results describe this generator only.

---

# Pre-registration: E1 next-response prediction on ASSISTments 2009 (`[PUB]`)

**Written:** 2026-11-05 13:30 IST, before any run. **Origin tag:** `[PUB]`. **Task tag:** one-step-ahead next-response correctness on K-12 maths skill-builder data.
**Not run in this commit.** The owner runs it on the laptop (see `docs/pragati-2.0/orchestration/LAPTOP_RUN.md`). No data was downloaded.

| Item | Value |
|---|---|
| Data | ASSISTments 2009-2010 Skill Builder. Server-side only; **not committed**. Download script: `scripts/download_public_data.py` (research use only per its notice; licence status still open under R2). The script records MD5 and SHA-256 at download; **the SHA-256 is recorded in the laptop output, not known now** |
| Preprocessing | `ml/public_validation/assistments.py::preprocess_assistments_pykt`, min_seq_len 3, max_seq_len 200, pyKT-style |
| Split | Student-held-out. Student shuffle and 20% test with **random_state 1024**; 5-fold CV on the remaining 80%. Preprocessing and item statistics fitted on training folds only |
| Bootstrap | Over students, pipeline default **500 resamples**, seed 42 (as in `evaluate_assistments_pykt`) |
| Command | `python -m ml.public_validation.assistments` (see LAPTOP_RUN.md for the exact call) |
| Chosen model | **`rasch_1pl_global`** (1PL Rasch, global student online EAP): the runtime family in EVAL_PLAN. The hierarchical `irt_online_eap` (the 0.7633 figure) is reported as a secondary row, not as the served model |
| Baseline 4 | `logistic_baseline` (`LogisticItemStudentBaseline`, additive item and student) |
| Other baselines | `bkt_em` (4-parameter EM with LF-AVG) |
| Baselines 1 to 3 (global mean, per-student mean, per-item mean) | **Not in the pipeline.** Not computed until added with tests. Reported as not computed |
| Primary metric | ROC-AUC on the test predictions, 1PL minus baseline 4 |
| **Pass bar** | The 1PL model beats baseline 4 with a student-level bootstrap 95% CI for the AUC difference that **excludes zero** (EVAL_PLAN §E1) |
| Secondary metrics | Log loss, Brier score, ECE (10 bins), ECE after isotonic calibration; AUC of every model with CI |
| Reference numbers | 0.7633 (hierarchical, from `artifacts/v1.0.0`) and 0.7135 (BKT). Context only. DKT 0.7541 is a published pyKT figure, **not the same pipeline**; it is not a bar |
| Expected limits | K-12 maths skill-builder data with hints. Cannot establish JEE item difficulty, mastery, learning gain, or any claim about the served engine's BKT parameters (they are not fitted) |
| Decision rule | Pass if the CI excludes zero from above. Otherwise **miss**, reported as a miss. The secondary numbers are not used to choose a winner |
| Planned command | see LAPTOP_RUN.md |

---

# Pre-registration: E2 day-28 retention on OULAD (`[PUB]`)

**Written:** 2026-11-05 13:30 IST, before any run. **Origin tag:** `[PUB]`. **Task tag:** withdrawal risk at day 28 of a UK distance-learning course. **This is not a mastery task and not JEE evidence.**
**Not run in this commit.** The owner runs it on the laptop.

| Item | Value |
|---|---|
| Data | OULAD, CC BY 4.0 per the repo (attribution required; licence re-verified before the run). Server-side only; not committed. Download via `scripts/download_public_data.py` |
| Split | 5-fold **student-grouped** CV (`GroupKFold` on `id_student`). Course-held-out 7-fold (`GroupKFold` on `code_module`) as a secondary |
| Cutoffs | 14, 28, 42, 60 (pipeline default). Primary: 28 |
| Seed | 42 (`run_oulad_suite` default); bootstrap 500 resamples over students (pipeline default) |
| Command | `python -m ml.public_validation.evaluate` (see LAPTOP_RUN.md) |
| Models | `lgbm_academic_only_student_cv` (**product-relevant row**: academic only, no VLE behaviour), `lgbm_acad_behav_student_cv` (**not usable for minors**, DPDP s.9(3): VLE clicks are Tier D; reported as a privacy-cost ablation only), `logreg_*`, `rule_no_assessment`, `rule_zero_vle_7d` |
| Primary metric | ROC-AUC at day 28, student-grouped CV, student bootstrap CI, on the **academic-only** LightGBM |
| **Pass bar** | **The published anchor 0.794** (PLOS ONE 2026, Wu et al., as cited in the repo). Pass only if the point estimate and the CI lower bound are both >= 0.794. Otherwise **miss** |
| Gate in `contracts/metrics_bars.yaml` | `>= 0.70`, `gate: report`. **Recorded, not a pass bar.** EVAL_PLAN §E2 says the bar comparison must be stated honestly, and it names the 0.794 anchor. The repo's README reports this gate as PASS. Owner decision required (see S5_LOG) |
| Result already in the repo (not this run) | Day 28, LightGBM plus isotonic, **0.706 [0.699, 0.714]**. Against the anchor this is a **miss by 0.088**. It is kept as a prior result, not as this pre-registered run |
| Expected limits | UK adult distance-learning, not Indian coaching students. Cannot say anything about mastery, JEE, or minors. The product-relevant row is the academic-only model |
| Decision rule | As stated in the pass bar. The secondary ablation (VLE clicks) is never reported as the product's result |
| Planned command | see LAPTOP_RUN.md |
