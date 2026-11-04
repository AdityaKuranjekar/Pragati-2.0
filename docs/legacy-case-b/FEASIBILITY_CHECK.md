# Feasibility check of the acceptance bars (senior-analyst review, 2026-10-21)

**Purpose.** Before parallel agents chase numbers in `contracts/metrics_bars.yaml`, check whether the bars are realistic, too easy (judges will shrug), or structurally unachievable (agents will waste days or fudge the data).
**Status.** These are *toy simulations* in `technical/analysis/feasibility/`. They use our own assumptions (circular), a logistic-regression stand-in for LightGBM, and numpy/scipy only. They are **directional evidence for choosing bars, never results for slides.**

## 1. IRT difficulty recovery: the bars are too lenient
Setup: 60 items, b ~ N(0,1), a ~ LogN(0,0.3), true guessing floor 0.10, fitted with a **misspecified** floor 0.15, MAP with priors, 12 repetitions.

| Students answering each item | r(b̂, b) 2PL | r(b̂, b) Rasch |
|---|---|---|
| 30 | 0.88 (min 0.85) | 0.89 |
| 60 | 0.92 (min 0.90) | 0.92 |
| 100 | 0.95 | 0.95 |
| 200 | 0.97 | 0.96 |
| 500 | 0.98 | 0.98 |

Findings:
- The current bars (r ≥ 0.90 @ 200, ≥ 0.75 @ 60) would be passed with large margin by a *naive* model. They prove nothing.
- Rasch ≈ 2PL for n ≤ 100, so the "use Rasch below 50 responses" rule should be chosen by cross-validated likelihood, not a fixed threshold.
- Discrimination (a) is much harder than difficulty (b), which matters for wrong-key detection (negative a) and should be reported separately.
- Real data will be worse (blanks that are not at random, ability drift, cheating clusters, a narrower b spread within a batch). Hence **the bars must be tested under the misspecified generators of NB07**, and tightened.

**Proposed bars (v1.0.1):** r ≥ 0.90 @ n = 60 and ≥ 0.85 @ n = 30 on the base generator (blocking); r ≥ 0.80 @ n = 60 under the misspecified generators (report); report Spearman and RMSE(b̂); report r(â, a) separately.

## 2. Early warning: three problems found
Setup: 3,000 students, 52 weeks, 25 % sudden dropouts, 75 % gradual with a fade of 3–8 weeks, chronic low attenders (base attendance SD 0.09), a festival dip hitting out-of-town students, biweekly tests. Labels: dropout within the next 4 weeks. Time split. 3 seeds. Rule baseline: attendance(4 wk) < 75 % or last test z < −1.

| Metric (3 seeds) | Model (LR stand-in) | Institute rule |
|---|---|---|
| AUC-PR | 0.059–0.061 (prevalence 2.6 %) | 0.036–0.037 → **+67 % to +70 %** relative |
| Gradual-dropout recall at top 4 % per week | 0.49–0.55 | 0.37–0.42 |
| Median lead time (caught gradual dropouts) | 14–21 days | **35–49 days** |
| Share of all students flagged at least once over the test period | 31–34 % | 44–45 % |

**Problem 1: the time split in TECH_PLAN §10 is broken.** "Train months 1–6, test months 7–12" puts the dropout *peak* (months 3–4) in training. In a first run with the plan's hazard shape, the test window had a 0.17 % event rate (a handful of events, results unstable). **Fix:** generate several academic-year cohorts (e.g. 2024, 2025, 2026): train on earlier years, test on the last year, plus leave-one-institute-out. Per-year scoring is always as-of weekly.

**Problem 2: the lead-time bar is gameable and generator-dependent.** The *rule* shows a longer lead time (35–49 days) than the model because it flags chronic low attenders months early, which is mostly false positives. A bare "median lead ≥ 21 days" says nothing without the workload. In addition, lead time is largely set by our own generator's assumption (`pre_dropout_fade_weeks: [3, 8]`), which is circular. **Fix:** lead time is only reported *at a fixed workload (top-k per week)* and *next to the baseline at the same workload*; the absolute 21-day bar becomes `report`.

**Problem 3: recall ≥ 0.60 at 4 % capacity is not reached by a basic model (0.49–0.55)** in a noisy but plausible world. A better model and a larger capacity may pass, but moving the generator until the bar passes would be p-hacking. **Fix:** make the bars *relative to the baseline at equal workload* (blocking) and the absolute numbers `report`:
- recall@k lift over the rule ≥ +25 % relative (observed here: +26 % to +43 % across the 3 seeds, so it only just clears; treat it as a real test),
- precision@k lift over the rule ≥ +25 %,
- AUC-PR lift ≥ +30 % (already in the contract).

**Problem 4: alert fatigue is real.** A third of students get flagged at some point over ~22 weeks when the top 4 % is re-selected weekly. Required behaviours (Agent C): flag persistence with hysteresis (a student stays on the list until resolved or improving; re-surfacing needs worsening), a cap by `mentor_capacity_per_week`, and a measured "distinct students flagged per month".

**Honest framing for slides.** At a fixed workload the model finds roughly half of the gradual dropouts, about 25–45 % more than today's rule would. Overall ranking quality is modest: AUC-PR 0.06 against a 2.6 % base rate is only ≈ 2.3× better than random (precision at the top-k itself was not measured here; Agent C reports it). The signal is noisy and a quarter of dropouts are sudden. The product claim is *"cheap, supportive check-ins for the students most worth a call"*, not prediction accuracy.

## 3. Items not simulated yet (checks queued for the agents)
- Conformal 80 % coverage ∈ [0.77, 0.83]: guaranteed by construction under exchangeability. The real test is **under covariate shift** (new institute, new year), so evaluate on the held-out institute/year and report the coverage there, not only i.i.d.
- Fairness slices need ≥ 30 events per slice; with fewer, report "insufficient data" instead of a gap.
- Mastery AUC gain over raw % correct: depends on items per topic per test (1–3 in real tests). Agent B must report the gain *by items-per-topic*.

## 4. Environment facts discovered on the build laptop (2026-10-21)
- GPU RTX 4060 Laptop, 8 GB. Ollama 0.40.6 installed. **Only `nomic-embed-text` is pulled**; `qwen3:4b` and `gemma3:4b` still need `ollama pull`.
- Python 3.12 present; **scikit-learn, LightGBM, PyTorch, SHAP, OpenCV are not installed**; each agent installs into its own venv from a pinned `requirements.txt`.
- **Docker is not installed** (the compose fallback needs Docker Desktop with WSL2, or native scripts).

## 5. Statistical power of the planned `full` preset (computed from `generator_config_draft.yaml`, checked by `tests/test_docs_consistency.py`)
| Institute | Students / year | Expected dropouts / year (18 %) |
|---|---|---|
| Kota (large) | 2,000 | 360 |
| Lucknow (NEET) | 900 | 162 |
| Patna (JEE) | 400 | 72 |
| Gaya (mixed, small) | 150 | **27** |
| **Total** | 3,450 | **621** (≈ 466 gradual) |

- Final-year test cohort: ≈ 620 events overall, enough for stable AUC-PR/recall CIs. Three cohorts ≈ 1,860 events in total.
- **Gaya has fewer than 30 events per year**: leave-one-institute-out results for Gaya and any per-slice fairness number on it will be wide or "insufficient data". This is a real small-institute limitation, to be stated, not hidden.
- Kota is 58 % of all students. Report institute-balanced metrics next to pooled ones so that Kota does not dominate.

## 6. Preview on the ACTUAL generator output (Agent A, `full` preset seed 42), 2026-10-21
Script: `analysis/feasibility/preview_early_warning_on_generator.py` (6-feature logistic regression; train 2024-25, test 2026; 802 train / 1,507 test positive student-weeks; weekly snapshots, next-30-day label).

| Metric | Model | Institute rule (ranked by attendance) | Relative gain |
|---|---|---|---|
| AUC-PR (test prevalence 1.74 %) | 0.181 | 0.079 | +131 % |
| precision@top-2 % / week | 0.193 | 0.182 | +6 % |
| precision@top-4 % / week | 0.136 (7.8× base) | 0.131 (7.5×) | +4 % |
| precision@top-8 % / week | 0.095 | 0.089 | +7 % |
| recall@top-4 % / week | 0.310 | 0.298 | +4 % |
| share of students flagged at least once (top-4 %/wk) | 38 % | 38 % | none |

What this means (and what we must not hide):
1. The generator confirms the headline marginals (dropout 17–19 % per cohort-year, 25 % sudden, 43 % of dropouts in months 3–4, festival ratio 0.60 / 0.90, blanks 10.9 %, 78 % of students minors at join).
2. **A simple model is only marginally better than a ranked attendance rule at a fixed workload**; its advantage is in overall ranking (AUC-PR), calibration, explanations and routing. Real institutes use the rule *unranked*, firing on ~37 % of students, so against the practice, the gain at equal workload is large; against a smart ranking it is small. Agent C must report both (baselines B1/B2).
3. Item responses per question are large (median 3,754) because shared questions are pooled over institutes and years; the n = 30 / 60 subsampled bars are what represent a single small batch.
4. Cohort sizes were 10 % / 25 % / 65 % of the configured size per year, leaving 230 training events; fixed by `R1_A2_datagen_fixes.md`.
5. Recall defined as "ever flagged before dropout" is inflated by weekly re-selection; use snapshot precision/recall.
