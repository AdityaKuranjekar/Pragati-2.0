# Phase 4 — Evaluation, Experiments, Privacy & Reliability

> **Update 2026-11-04 (orchestrator pass).**
> - The full evaluation plan is in `evaluation/EVAL_PLAN.md`: sets E0 to E14, origin and task tags, splits, baselines, proposed pass bars, sample sizes, and a re-map of every existing number.
> - **Pre-registration:** bars are proposals until written in `ml/evaluation/PREREGISTRATION.md` before a run.
> - **Re-mapped numbers:** 0.763 (ASSISTments) is from a hierarchical Rasch model; the served runtime is 1PL. OULAD 0.706 misses the 0.794 anchor, and the repo marks it as passed against its own bar. Disclose both.
> - **Sample size for a pilot (computed):** d = 0.3, α = 0.05, power 0.80 → 175 per arm if individually randomised, 428 per arm if randomised by class of 30 at ICC 0.05 (assumed; R8 to check).
> - **Benchmarks added:** a collaborative-filtering baseline and a graph-score ablation (Phase 2 update).
> - **Privacy:** E12 subgroup analysis is blocked for minors; E13 tenant tests apply to every new route.

## 1. Purpose

Demonstrate that Pragati 2.0 is technically sound and that its adaptive decisions are better than a reasonable non-adaptive baseline. A hackathon-winning claim must be supported by transparent evidence.

**Outcome:** reproducible evaluation report, failure analysis, privacy checks and a stable product build.

### JEE prototype success measures

Evaluate mastery prediction and next-question appropriateness using ASSISTments interaction patterns and JEE-benchmark/question-bank data, but report domain transfer limits. Success should include concept mastery gain, reduction in the initial easy-to-hard ability gap, time-to-mastery, hint reliance, response time, revision retention, learning-path completion and teacher usability. Add guardrails preventing easy-question lock-in, permanently low student labels, unfair group comparisons, leakage, guessed responses, incorrect answer keys, and unsafe content scraping.

## 2. Evaluation questions

1. Does the learner model predict future responses better than a simple baseline?
2. Are mastery estimates calibrated and useful for concept-level diagnosis?
3. Do recommendations respect prerequisite relationships?
4. Are recommendations relevant to teachers and learners?
5. Does an adaptive sequence improve learning gain compared with a fixed sequence in a controlled evaluation?
6. Does the system remain reliable with sparse, missing or contradictory evidence?

## 3. Experimental design

### Adaptive vs fixed-path comparison

- **Control:** learners receive the same pre-defined sequence or a fixed sequence based on the course blueprint.
- **Treatment:** learners receive activities selected by the adaptive policy using their current learner state.
- Keep content quality, total time budget and assessment difficulty comparable.
- Use the same pre-test and post-test blueprint, with non-identical items where possible to reduce memorization.
- Randomize learners when feasible. If only simulation is possible, label the experiment as simulation.
- Report sample size, inclusion criteria, exclusions and confidence intervals.

### Demo simulation

Create two synthetic learners with deliberately different initial evidence:

| Concept | Learner A | Learner B |
|---|---:|---:|
| Factorisation | 85% | 35% |
| Quadratic equations | 70% | 45% |
| Discriminant | 40% | 20% |

These values are illustrative demo fixtures, not measured student outcomes. The product should calculate its own state from the simulated attempts. Use the example to show how prerequisite reasoning changes the recommended path.

## 4. Metrics

| Metric | What it measures | Important caveat |
|---|---|---|
| AUC / log loss | Next-response prediction | Not a direct measure of learning improvement |
| Calibration / Brier score | Whether predicted probabilities match outcomes | Requires enough held-out examples |
| Mastery recovery error/correlation | Ability to recover known simulated or labeled mastery | Synthetic ground truth may be unrealistic |
| Learning gain | Post-test minus pre-test performance | Needs comparable assessments and a credible design |
| Recommendation Precision@K | Whether top recommendations are judged relevant | Requires expert/teacher labels |
| Prerequisite violation rate | Invalid ordering of dependent concepts | Define violation precisely |
| Time to mastery | Time/attempts to reach a pre-defined criterion | Avoid comparing learners with different objectives |
| Completion rate | Whether learners complete assigned path | Completion alone is not learning |
| Teacher override rate | How often recommendations are changed | An override is not automatically a model failure |

## 5. Dataset-specific evaluation

### ASSISTments
Use for K-12 mathematics response prediction and knowledge-tracing comparisons where skill tags and event sequences fit the chosen release. Split by learner to test generalization to unseen learners. Keep preprocessing and release version fixed.

### OULAD
Use only for a distinct higher-education retention/withdrawal task. It is not a direct measure of concept mastery in school mathematics. Avoid mixing it with ASSISTments as if labels were interchangeable.

### EdNet / PSLC DataShop
Consider only after the initial benchmark is reproducible. Inspect data schema, population, access conditions and license. Keep each benchmark's results separate.

## 6. Leakage prevention

- Split by learner, and where appropriate by time.
- Never let future attempts contribute to features for an earlier prediction.
- Fit preprocessing, vocabulary, scalers and item statistics on training data only.
- Keep duplicate or near-duplicate question variants in the same split where possible.
- Avoid learner IDs or institution IDs acting as shortcuts.
- Record all random seeds and dataset versions.
- Evaluate cold-start learners separately.
- Use a final untouched test set for the reported result.

## 7. Baselines and ablations

Compare:
- Random or curriculum-order recommendation (sanity baseline).
- Fixed learning path.
- Rule-based mastery and recommendation.
- Existing Pragati mastery approach.
- BKT-based learner state.
- BKT plus prerequisite-aware ranking.

Ablate:
- Without prerequisite graph.
- Without uncertainty.
- Without recency/revision.
- Without difficulty-aware selection.
- Without GenAI explanation (to show whether LLM adds actual value).

The purpose is to show which components contribute, not merely to maximize a metric.

## 8. Model reporting

For every reported model:
- Task and target definition.
- Dataset and version.
- Population and sample size.
- Train/validation/test split method.
- Baseline.
- Metrics with uncertainty.
- Model and feature version.
- Known limitations.
- Reproduction command.

Previously reported Pragati metrics (mastery recovery r=0.53, question difficulty recovery r=0.79, synthetic early-warning AUC=0.81, OULAD withdrawal AUC=0.706, ASSISTments next-answer AUC=0.763 and synthetic OMR accuracy=0.9997) should be independently re-run and described in their original task context. Do not combine them into one “accuracy” claim.

## 9. Privacy, safety and fairness

- Minimize collection of personal data.
- Use synthetic demo accounts unless real data is authorized.
- Protect minors and apply appropriate guardian/institutional consent.
- Do not introduce invasive screen-time, keystroke, location or unrelated app-activity tracking.
- Enforce least-privilege access and tenant isolation.
- Encrypt transport and protect secrets.
- Log administrative access and sensitive exports.
- Define retention and deletion processes.
- Avoid public leaderboards or labels that stigmatize learners.
- Test recommendation quality across relevant groups when lawful and data supports it.
- Provide human review and override for consequential interventions.
- Avoid presenting predictions as diagnoses or certainties.

## 10. Reliability and security tests

- Authentication, authorization and tenant-isolation tests.
- SQL injection and input validation checks.
- File upload limits, MIME validation and malware scanning strategy.
- Rate limiting for expensive endpoints.
- LLM timeout, malformed response and prompt-injection handling.
- Database backup and restore drill.
- Migration rollback test.
- Observability for latency, errors and model version.
- Graceful degradation if ML/LLM provider is down.

## 11. Deliverables and exit criteria

- [ ] Reproducible training/evaluation scripts.
- [ ] Dataset provenance and split manifests.
- [ ] Baseline comparison table.
- [ ] Ablation study.
- [ ] Error analysis with examples.
- [ ] Recommendation quality review by a subject-matter reviewer.
- [ ] Privacy and security checklist.
- [ ] Clear separation of synthetic, public-dataset and pilot results.
- [ ] No critical tenant-isolation or data-integrity defect.
- [ ] Backup demo path exists.

**Gate:** do not claim “improves learning outcomes” based only on next-answer AUC or a synthetic demo. State exactly what the evidence establishes.
