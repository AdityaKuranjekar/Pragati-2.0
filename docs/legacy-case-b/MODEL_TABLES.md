# Model comparison tables (Tab 1, v1.1.0, synthetic data, seed 42)

Built by `ml/build_artifacts.py`; numbers live in `ml/artifacts/metrics.json` and `ml/artifacts/models.json`. All results are on **synthetic** data unless marked public. Informal bars come from `contracts/metrics_bars.yaml`; where the bar was not met we say so.

## 1. Mastery (IRT)
| Item | Value |
|---|---|
| Method | Rasch (1-parameter) with item difficulty from item pass rates and a MAP ability per student and topic (prior N(0, 1.5²)). Per institute. This is the "Rasch fallback" in the plan; the hierarchical 2PL was **not** built in this pass. |
| Compared | Raw share-correct per student and topic (baseline). BKT, DKT and SAKT were compared only on public ASSISTments (AUC DKT 0.754, ours 0.763; see `ml/public_validation`). |
| Ability recovery r (cells with at least 5 answers) | Rasch **0.53**, raw share **0.49** (4-institute mean; range 0.49 to 0.55). Bar 0.80 **not met**: only a few questions per topic per student. |
| Difficulty recovery r | **0.79** mean (0.66 to 0.90). Bar 0.90 **not met** at three institutes. |
| Wrong-key detection | Point-biserial below 0.05. Found 3 of 3, 1 of 1, 0 of 0 and 1 of 1 injected wrong keys; recall 0.75 mean, precision 0.75 mean (tiny counts). |
| Verdict | Topic-level theta is noisy by nature, so the heatmap always shows uncertainty and "not enough data". Honest claim: a small gain over raw percentages, not a big one. |

## 2. Risk (early warning)
Test = 2026 cohort, three as-of dates (15 Jul, 15 Aug, 1 Sep), label = leaves within 45 days (3.7 % base rate), capacity = 5 % of active students per institute and date. Trained on 2024 and 2025.
| Model | Features | AUC | Precision at capacity | Recall at capacity | Lead time (days) |
|---|---|---|---|---|---|
| B1: attendance below 75 % (institute rule) | attendance | n/a | 0.09 (flags 25 % of students) | 0.61 | n/a |
| B2: lowest attendance, top 5 % | attendance | 0.74 | 0.23 | 0.31 | 13.6 |
| LightGBM, academic only (minors) | scores, trend, tests taken | 0.67 | 0.08 | 0.11 | 15.7 |
| LightGBM, full (18+ only, own consent) | academic + attendance + engagement + fees | **0.81** | **0.32** | **0.44** | 14.3 |
Calibration error (deciles, full model) 0.005. Reasons come from LightGBM contribution values mapped to fixed wording.
**Honest reading:** the academic-only model that minors are allowed to use is weak (AUC 0.67). The full model beats the ranked attendance rule (0.32 vs 0.23 precision) but is only legal for 18+ with consent. For minors the product value is topic gaps, capacity-sized lists and supportive actions, not prediction accuracy. Sudden dropouts (25 % by design) cannot be predicted. Uplift from acting on the list cannot be measured here; a pilot settles it. SHAP and a survival check were not run (library not installed); contribution values were used instead.

## 3. Percentile band
| Model | Setup | Result |
|---|---|---|
| Point (LightGBM on mock scores) | Train 2024, test 2026 | MAE 2.5 percentile points |
| Conformal band | Calibrate on 2025, test 2026, target 80 % | Coverage **0.80**, half-width 3.4 points |
The mapping is learned from the generator's outcomes, so the band is tight; real NTA shifts will be wider. Labelled as an assumption in the files.

## 4. Reports
Template path with the 8-check verifier (after the `R1_E2` fixes; 68 genai tests pass). 160 reports across 4 institutes, all verified, none invented. The local-model path was **not benchmarked** (`qwen3:4b` and `gemma3:4b` not pulled). Hindi text is unreviewed (`hi_reviewed: false`).

## 5. Owner comparison
Batch comparison of mean test score with a bootstrap 95 % interval and an `enough_data` flag (n of at least 30). Faculty comparison is empty because faculty is not in the data schema. Mixed-effects was not run.

## 6. Data moat (simulation)
Difficulty error (RMSE, logit) for 120 items when a new institute borrows responses from k institutes of 150 students: **0.22 (k=1), 0.17 (k=20)**. Real but modest; only item statistics are shared, never student data. Pooling helps most when an institute has few students.

## What was not done in this pass (time-boxed)
Hierarchical 2PL; BKT/DKT on our synthetic data; SHAP and lifelines; the 150 labelled questions and the tagging model; the live LLM benchmark; JSON Schema files for the artifacts; the full notebook rewrite (figures were produced by `ml/build_datacard.py` instead).
