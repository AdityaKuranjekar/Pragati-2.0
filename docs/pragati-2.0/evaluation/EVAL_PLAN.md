# Evaluation plan (Pragati 2.0)

**Status:** proposal, 2026-11-04. Nothing here has been run for 2.0. Pass bars are **proposed** and must be written into `ml/evaluation/PREREGISTRATION.md` (with date and commit hash) **before** the run they judge. A bar set after seeing a result is not a pass.

## 0. Rules that apply to every set

| Rule | Why |
|---|---|
| Every number carries an **origin tag**: `[SIM]` synthetic, `[PUB]` public dataset, `[EXP]` expert-labelled, `[PILOT]` real learners. Tables must not mix tags without a column for it. | `CLAUDE.md` §4; a synthetic AUC is not a learning outcome. |
| Every number carries a **task tag**: what is being predicted or decided. | Next-response AUC, mastery recovery and retention AUC are different tasks. |
| **Split by learner** (student-held-out) unless the set says otherwise. Fit all preprocessing and item statistics on train only. | Leakage inflates results; ASSISTments and OULAD both reward memorising learners. |
| Record dataset version and SHA-256, split seed, code commit, model version, and the exact command. | Reproducibility rule, Phase 4 §8. |
| Report a bootstrap 95% CI over **learners** (resample students, not rows). | Rows from one learner are not independent. |
| Every set has a **baseline** and at least one **ablation** where the set is about a component. | A metric without a baseline proves nothing. |
| Negative results stay in the report. | Judges will ask for them; the plan requires "honest misses". |

## 1. Evaluation sets at a glance

| Set | Question it answers | Origin | Ground truth | Status now |
|---|---|---|---|---|
| E0 | Is the engine deterministic, leak-free, and structurally valid? | Code tests | Invariants | Not built for 2.0 |
| E1 | Does the learner model predict the next response better than simple baselines? | `[PUB]` ASSISTments 2009 | Observed correctness | Pipeline exists (`ml/public_validation/assistments.py`); 2.0 re-run needed |
| E2 | Does retention prediction work on a non-school task? | `[PUB]` OULAD | Withdrawal | Exists; **misses** published anchor |
| E3 | Does mastery estimation recover known ability? | `[SIM]` simulator independent of the estimator | Simulated θ and concept mastery | Partly exists (1.0, circular risk) |
| E4 | Does diagnosis name the **root-cause** prerequisite? | `[EXP]` 60 expert-labelled learner profiles | Expert root cause | Not started |
| E5 | Are question-to-concept tags correct? | `[EXP]` 150 items, two annotators | Expert tags | Not started (1.0 carry-over) |
| E6 | Are recommendations judged relevant, and better than a fixed path? | `[EXP]` teacher panel, blinded | Teacher ratings | Not started |
| E7 | Does the recommender ever violate a prerequisite? | Graph + policy output | Deterministic rule | Not started |
| E8 | Does an adaptive path improve learning versus a fixed path? | `[PILOT]` randomised | Post-test | Requires legal clearance (BLOCKERS B1) |
| E9 | What would the adaptive policy do under the simulator? | `[SIM]` | Simulated outcome | Not started; label as simulation only |
| E10 | Does the system behave safely with no, sparse, or contradictory evidence? | Scripted fixtures | Expected behaviour | Not started |
| E11 | Are explanations faithful to what the policy used? | Code trace + expert read | Policy trace | Not started |
| E12 | Are predictions equally good across subgroups? | `[PUB]` or consented adults only | Outcome | Blocked for minors (BLOCKERS B1) |
| E13 | Is tenant isolation complete? | Automated cross-tenant tests | Expected denial | Partly exists (RLS in schema; tests in `backend/tests/test_tenancy_auth.py`) |
| E14 | Is the product fast enough to demo on free tier? | Load test | p95 latency, cold start | Not started (R7) |

---

## 2. Set-by-set specification

### E0: Invariants and determinism `[code]`
- **Checks:** same ordered events plus same model version gives identical state (replay); no event after `as_of` affects its state; the prerequisite graph is acyclic; every question-concept row points to an existing concept; every published item has an approved curriculum version and at least one tag; idempotent event submission (same key twice gives one row).
- **Data:** hand-written fixtures (no real data).
- **Pass bar (proposed):** 100% of invariants.
- **Can establish:** the code does what it says. **Cannot establish:** that the model is right.

### E1: Next-response prediction on ASSISTments `[PUB]`
- **Task:** predict whether a learner answers item *t* correctly from items 1 to *t*−1. Target: `correct`.
- **Data:** ASSISTments 2009-2010 Skill Builder, **server-side only**, licence unverified (R2). Preprocessing follows pyKT (`min_seq_len=3`, `max_seq_len=200`, `random_state=1024`, 20% test students, 5-fold CV on the rest). Sample size from repo notes: 770 students, 55,755 predictions (verify on re-run).
- **Split:** student-held-out. Folds fixed. Preprocessing fitted on training folds only.
- **Baselines (in order of simplicity):**
  1. Global mean correctness.
  2. Per-student mean (uses only that learner's past).
  3. Per-item mean (item difficulty only).
  4. Additive logistic (student bias + item bias), already in code as `LogisticItemStudentBaseline`.
  5. 1PL Rasch with online EAP (the **runtime** model family).
  6. Hierarchical Rasch with online EAP (the model behind the **0.7633** figure).
  7. 4-parameter BKT fitted by EM (already in code; repo reports **0.7135**).
  8. Published DKT / SAKT numbers from pyKT: **context only**, not the same pipeline; do not put them on the same bar.
- **Metrics:** ROC-AUC (primary), log loss, Brier score, ECE (10 bins), and ECE after isotonic calibration.
- **Proposed pass bar:** the chosen model beats baseline 4 with a bootstrap CI (over students) that excludes zero. Beating published DKT is **not** a pass criterion because the pipelines differ.
- **Must report:** that 0.7633 is from a hierarchical model, while the product runtime is a 1PL model. Either re-run the 1PL number on the same protocol or say the product number is different.
- **Can establish:** next-response skill on K-12 maths skill-builder data. **Cannot establish:** JEE item difficulty, mastery, or learning gain.

### E2: Retention prediction on OULAD `[PUB]`
- **Task:** withdrawal risk at day 14, 28, 42, 60. This is **not** a mastery task.
- **Data:** OULAD (CC BY 4.0 per repo; verify). Student-grouped 5-fold CV and course-held-out split.
- **Baselines:** rule 1 (no assessment by cutoff), rule 2 (zero VLE clicks in last 7 days), academic-only LightGBM, logistic regression.
- **Result already in repo:** LightGBM + isotonic at day 28 **0.706** [0.699, 0.714]. Published anchor **0.794**. This is a **miss by 0.088**. The gate in `contracts/metrics_bars.yaml` is **0.70** (`gate: report`), below the 0.794 anchor the repo cites, and the artifact records `passed_bar: true`. The ASSISTments gate is 0.65 against a DKT anchor of 0.7541. The bar comparison must be stated honestly in any slide. Recommend changing the bar to the anchor and reporting a miss, or dropping the anchor from the claim.
- **Use in pitch:** none for mastery. At most, "our retention pipeline is tested on a public higher-education dataset and not used for JEE students".

### E3: Mastery recovery on simulated learners `[SIM]`
- **Task:** recover each learner's latent concept mastery θ (and binary mastery state) from a simulated response history.
- **Simulator rule (to avoid circularity):** the generator must be **written separately** from the estimator and must include: guessing (0.2 to 0.25 for 4-option MCQ), slips, item difficulty spread, prerequisite structure (a learner cannot master a dependent concept far above its prerequisites), and learning during practice (a rise in θ per opportunity). The estimator must not import the generator's parameters.
- **Design factors:** items per concept per learner (3, 6, 10, 20); number of concepts (10, 30); prerequisite depth (1, 3); guessing rate; learning rate.
- **Metrics:** Pearson and Spearman r between estimated and true θ; RMSE; 80% credible-interval coverage (target 0.75 to 0.85); mastery-state accuracy, precision and recall at the product threshold.
- **Baselines:** raw share correct per concept; BKT (4-param); 1PL Rasch EAP.
- **Proposed pass bar:** r ≥ 0.80 and interval coverage 0.75 to 0.85 **at ≥ 10 items per concept per learner**; report the curve for fewer items. Below 10 items, the product must show "not enough evidence".
- **Repo baseline for context:** Rasch ability recovery **r = 0.53** at few answers per cell (1.0, `MODEL_TABLES.md` §1); difficulty recovery 0.79. These were the 1.0 synthetic data; say so.
- **Can establish:** the estimator works when its assumptions hold, and how many items are needed. **Cannot establish:** that real students behave like the simulator.

### E4: Root-cause diagnosis from expert labels `[EXP]`
- **Task:** given a learner's concept-level estimates and the prerequisite graph, name the **root-cause concept** a teacher would target first.
- **Data:** 60 learner profiles built from E3-style simulated histories (so ground truth exists) **and** 20 hand-written profiles from teachers. Two subject experts (one Physics, one Maths; Chemistry if time) label each case independently, blind to the policy's output. Disagreements go to a third reviewer. Report Cohen's κ.
- **Baselines:** (a) lowest mastery concept; (b) lowest mastery among concepts with ≥ 5 items; (c) deepest unmastered prerequisite; (d) random concept in the unmastered set.
- **Metrics:** top-1 accuracy, top-3 accuracy, and the share of cases where the policy picks a concept that is a **descendant** of the root (a useful but wrong step).
- **Proposed pass bar:** κ between experts ≥ 0.6; policy top-1 ≥ 0.70 and ≥ 0.15 above baseline (a), CI excludes zero.
- **Can establish:** the diagnosis matches expert judgement on built cases. **Cannot establish:** that teachers agree on real learners.

### E5: Question-to-concept tagging `[EXP]`
- **Task:** assign each question to its primary concept (and optional secondary concepts).
- **Data:** the 150 labelled questions carried over from 1.0 (not yet built) or new questions from R2-approved sources. Each item needs a licence record before it enters the set.
- **Annotators:** two subject experts, independent, plus adjudication. Report κ.
- **Baselines:** keyword rules on concept names; text-embedding nearest concept (if used; no vector DB required, a flat index is enough at this size).
- **Metrics:** primary-tag precision and recall; any-tag recall; per-subject breakdown.
- **Proposed pass bar:** κ ≥ 0.7 between annotators; tool precision ≥ 0.90 and recall ≥ 0.80 on primary tags **or** the tool only suggests and teachers approve every tag (the fallback).
- **Can establish:** tagging quality on this set. **Cannot establish:** tagging on the full bank without a new sample.

### E6: Recommendation relevance with teacher raters `[EXP]`
- **Task:** rate whether each recommended next activity is one the rater would assign, given the learner profile and the reason shown.
- **Data:** 100 profiles × top-3 recommendations from (i) the adaptive policy, (ii) a fixed curriculum-order path, (iii) a random in-syllabus choice. Presented in random order, the policy label hidden.
- **Raters:** at least 3 teachers from the pilot institute or a partner (no more than 2 raters per learner profile). Rate on a 1 to 5 scale and "assign / don't assign".
- **Metrics:** Precision@3 (share of top-3 rated ≥ 4), mean rating, rater agreement (ICC), and the share of reasons rated "understandable".
- **Proposed pass bar:** adaptive Precision@3 ≥ 0.80 and fixed path lower by ≥ 0.10 with a CI excluding zero. If the gap is smaller, report it as no evidence of advantage.
- **Can establish:** teacher-judged relevance on profiles. **Cannot establish:** learning gain (see E8).

### E7: Prerequisite violations `[code]`
- **Task:** share of recommendations where a prerequisite concept is unmastered per the active graph and the recommended item is not a prerequisite review.
- **Data:** every policy output on E0 and E3 fixtures.
- **Proposed pass bar:** 0 violations on the active graph. **Sensitivity:** when one prerequisite edge is removed from the graph, the violation rate must rise (show it moves); when one spurious edge is added, report how many paths change.
- **Can establish:** the policy respects the graph it is given. **Cannot establish:** that the graph is right (that is E5 plus teacher review of edges).

### E8: Learning gain, adaptive versus fixed `[PILOT]`
- **Task:** post-test minus pre-test, adaptive arm minus fixed arm.
- **Design:** randomised. Individual randomisation if the legal route allows; otherwise class-level randomisation.
- **Sample size** (two-sided α = 0.05, power 0.80, computed in this repo session):

  | Standardised effect d | Per arm, individual randomisation | Per arm, class of 30, ICC 0.05 (design effect 2.45) |
  |---|---:|---:|
  | 0.2 | 393 | 962 |
  | 0.3 | 175 | 428 |
  | 0.4 | 99 | 241 |

  The effect size is a placeholder until R8 reports a prior. Pre-register d and ICC before the pilot.
- **Covariates:** pre-test score (ANCOVA). Time-on-task reported but **not** used as a predictor for minors (B1).
- **Metrics:** adjusted mean difference with 95% CI; completion rate; time to a mastery criterion (count of items, not seconds, for minors).
- **Proposed pass bar:** difference > 0 with CI excluding 0, pre-registered. A null result is reported as null.
- **Can establish:** effect on this cohort over this period. **Cannot establish:** effect in other exams or institutes without replication.

### E9: Simulated adaptive vs fixed path `[SIM]`
- **Purpose:** show the design space (which settings favour adaptivity) before the pilot. **Never** present it as learning evidence.
- **Settings:** the E3 simulator; a fixed path in curriculum order; the adaptive policy with each ablation (no prerequisite graph; no uncertainty; no revision; no difficulty-aware selection).
- **Metrics:** final mastery count at equal item budget; items to mastery; violations.
- **Label:** every chart carries "SIMULATION, not evidence of learning outcomes".

### E10: Robustness fixtures `[code]`
| Case | Expected behaviour |
|---|---|
| No evidence (cold start) | Returns a **diagnostic** activity, not a path; reason says "no evidence yet" |
| One or two items per concept | Mastery flagged "not enough evidence"; no ranking by that concept |
| Contradictory evidence (right then wrong then right) | Uncertainty stays wide; no hard label change |
| Guessed run (4-option MCQ, 4 right in a row by chance) | Estimate moves less than a genuine run; documented |
| Wrong answer key injected in a test | Flagged by the wrong-key detector; recall target ≥ 0.80 on 20 injected keys |
| Missing prerequisite data | Falls back to curriculum order with a visible note |
| Empty or malformed event | Rejected with a clear error; no state change |

- **Pass bar:** 100% of fixtures behave as expected. The wrong-key recall bar is separate.
- **Repo note:** the 1.0 wrong-key detector had recall 0.75 and precision 0.75 on tiny counts (3 + 1 + 0 + 1 injected keys). Treat as a starting point, not a result.

### E11: Explanation faithfulness `[code + EXP]`
- **Automatic check:** every reason string is generated from the policy trace; each claim (concept, mastery band, prerequisite, evidence count) must map to a field present in the trace. Pass: 100% coverage, zero unmapped claims.
- **LLM check (only if an LLM phrases the reason):** the 8-stage verifier in `backend/app/genai` must pass ≥ 95% of outputs; failures fall back to the template; zero unverified outputs are shown.
- **Expert read:** 30 reasons rated for accuracy and "would a teacher understand this?" (1 to 5).
- **Can establish:** the reason is tied to the evidence the policy used. **Cannot establish:** that the reason changes what the learner does.

### E12: Subgroup performance `[PUB or consented adults]`
- **Groups:** only those the lawful route allows (for example medium of instruction if collected with consent). No demographic inference.
- **Metrics:** AUC and calibration per group; gap in AUC.
- **Proposed pass bar:** AUC gap ≤ 0.05 and calibration gap ≤ 0.05; otherwise report the gap and the group sizes.
- **Repo note:** on OULAD, dropping demographic features changed AUC by almost zero (`ml/public_validation` model card). The repo therefore already removes demographics for data minimisation.
- **Blocked for minors** until B1 is resolved.

### E13: Tenant isolation `[code]`
- **Checks:** for every endpoint that reads or writes a learner, teacher, cohort, intervention, report or response: a user from institute A asking for institute B's record gets 403 or 404. Include an attempt with a forged `institute_id` in the body, query or header. Include RLS checks with a different `app.institute_id`.
- **Proposed pass bar:** 100% denial; zero data leaks; a failure blocks the release.
- **Repo note:** RLS policies are present on the tenant tables (the schema uses `app.institute_id`). `backend/tests/test_tenancy_auth.py` exists; the 2.0 endpoints do not yet exist and need the same tests.

### E14: Demo performance `[code]`
- **Targets (proposed):** p95 next-step latency ≤ 500 ms on the free tier with 300 items and 20 learners; cold start ≤ 60 s with a visible loading state; backup recording ready.
- **Blocked by:** R7 (free-tier limits). Re-measure after any hosting change.

---

## 3. Existing results, re-mapped

These numbers are in the repo. Each must be shown with its task and origin, and not combined into one "accuracy".

| Reported figure | Task | Origin | Where in repo | Status for 2.0 |
|---|---|---|---|---|
| 0.7633 (AUC) | Next-response, hierarchical Rasch | `[PUB]` ASSISTments 2009 | `ml/public_validation/artifacts/v1.0.0/metrics.json` | Re-run on 2.0 protocol. The product runtime is 1PL, so this is not the served model |
| 0.7135 (AUC) | Next-response, 4-param BKT | `[PUB]` ASSISTments 2009 | `public_validation_summary.json` notes | Re-run; available as a baseline |
| 0.706 (AUC) | Day-28 withdrawal | `[PUB]` OULAD | `metrics.json` | Retention only; **misses** the 0.794 anchor |
| 0.53 (r) | Ability recovery, Rasch | `[SIM]` 1.0 synthetic | `MODEL_TABLES.md` §1 | Circular risk; re-run with E3 simulator |
| 0.79 (r) | Difficulty recovery | `[SIM]` 1.0 synthetic | `MODEL_TABLES.md` §1 | Re-run; report sample size |
| 0.81 (AUC) | Early warning, full model | `[SIM]` 1.0 | `MODEL_TABLES.md` §2 | Not part of 2.0 for minors (B1); exclude from the pitch |
| 0.9997 (accuracy) | Synthetic OMR | `[SIM]` | Phase 0 table | Must be re-tested on real phone photos (no real data yet) |
| 0.75 (recall) | Wrong-key detection | `[SIM]` tiny counts | `MODEL_TABLES.md` §1 | Re-test with E10 |

**Do not** call these a "76% accuracy model" or similar. Each row is a different task.

---

## 4. Demo fixtures (illustrative, not evidence)

The two demo learners in Phase 4 §3 (Learner A and B) are **illustrative fixtures**. Their mastery values must be **generated by the engine** from simulated attempts, not typed into the UI. Label them `[DEMO FIXTURE]` on screen. Their values in the phase document (85/35, 70/45, 40/20 per cent) are inputs to the simulator, not outputs the engine must reproduce.

---

## 5. Sample sizes and the things that will limit us

| Set | Size we can get by Dec | Limit |
|---|---|---|
| E4 | 60 cases (40 simulated + 20 teacher-written) | Two experts' time; κ unknown until labelled |
| E5 | 150 items | Rights clearance for each item (R2) |
| E6 | 100 profiles × 3 rankings, 3 raters | Teacher availability |
| E8 | Not in the hackathon window unless a pilot is already running | Legal clearance (B1), consent, school calendar |

---

## 6. Pre-registration template

Copy into `ml/evaluation/PREREGISTRATION.md` before a run:

```text
Set:               E__  name
Date (IST):        YYYY-MM-DD HH:MM
Commit:            <short hash>
Data version:      <name, version, SHA-256, licence status>
Split:             <rule, seed, folds>
Model/baseline:    <names and versions>
Primary metric:    <name, definition>
Pass bar:          <number, with CI rule>
Secondary metrics: <list>
Expected limits:   <what this cannot show>
Planned command:   <exact command>
```
