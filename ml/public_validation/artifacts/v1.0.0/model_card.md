# Model Card — Public Dataset Validation (`ml/public_validation`, `v1.0.0`)

- **Contract version:** `1.0.0`
- **Model version:** `v1.0.0`
- **Evaluated at:** `2026-10-20T20:30:56.403264+00:00`
- **Dataset origin:** `public` (OULAD CC BY 4.0 & ASSISTments 2009–2010 Skill Builder)

## 1. Intended Use & Framing
- **Purpose:** Independently validate DataMoat's early-warning (calibrated LightGBM vs. logistic regression and heuristic rules) and mastery/knowledge-tracing (hierarchical Rasch/IRT with online EAP ability updates and 4-parameter BKT EM) algorithms on **real, third-party public datasets** under published evaluation protocols.
- **Why this exists:** Synthetic data proves pipeline correctness and ground-truth recovery, but cannot prove real-world signal on its own. Evaluating the exact same model families on OULAD and ASSISTments2009 answers the circularity critique (*"you graded your own homework"*).
- **Not-intended use:** Models trained on OULAD (UK higher-education distance learners) or ASSISTments (US school mathematics skill practice) are **never** deployed directly to score Indian JEE/NEET coaching students. Tenant production models calibrate strictly on tenant-scoped coaching records under `contracts/routing_policy.yaml`.

## 2. Datasets & Licences
| Dataset | Task | Licence | Cohort / Size | Handling |
|---|---|---|---|---|
| **OULAD** (Kuzilek et al., 2017) | Early course withdrawal (`final_result = Withdrawn`) at day 14 / 28 / 42 / 60 | CC BY 4.0 (attribution required; commercial OK) | 32,593 registrations (28,785 unique students) across 7 modules / 22 presentations; 27,520 active at day 28 (5,104 withdrawals) | Downloaded via `scripts/download_public_data.py` into git-ignored `data/public/oulad/` |
| **ASSISTments 2009–2010** (Skill Builder) | One-step-ahead next-response prediction (`pyKT` 5-fold protocol) | Research use only (WPI ASSISTments; not redistributed) | 525,534 raw rows → 283,105 question events (338,001 KC-expanded) across 3,852 students (≥3 interactions), 17,751 questions, 123 skills | Cached in git-ignored `data/public/assistments2009/` |
| **EdNet-KT1** (Choi et al., 2020) | Optional scale stress-test only | CC BY-NC 4.0 (Non-Commercial) | ~784k students, ~131M interactions | Skipped by default (`--with-ednet` flag only) |

## 3. Part 1 — OULAD Early Withdrawal Results vs. Published Literature
### 3.1 Multi-Window ROC-AUC (5-Fold Student-Grouped CV, 500-Resample Student Bootstrap 95% CI)
| Cutoff Window | Active Cohort (`n` / `n_events`) | Ours: LightGBM (Academic + Behavioural, Tier A+D) | Ours: LightGBM (Academic-Only, Tier A) | Ours: Logistic Regression (Tier A+D) | Published Reference (Same Cutoff Window) |
|---|---|---|---|---|---|
| **Day 14** | 28,060 / 5,673 | **0.6699** [0.6635, 0.6775] | 0.6452 [0.6389, 0.6524] | 0.6483 | **0.727** (Wu et al., *PLOS ONE* 2026) · **0.735** (*IJET* 2026) |
| **Day 28** | 27,520 / 5,104 | **0.7061** [0.6989, 0.7140] | 0.6980 [0.6903, 0.7069] | 0.6901 | **0.794** (Wu et al., *PLOS ONE* 2026) |
| **Day 42** | 27,012 / 4,594 | **0.7115** [0.7025, 0.7189] | 0.7045 [0.6959, 0.7119] | 0.6952 | **0.804** (Wu et al., *PLOS ONE* 2026) |
| **Day 60** | 26,353 / 3,931 | **0.7171** [0.7073, 0.7243] | 0.7092 [0.6995, 0.7168] | 0.6953 | **0.815** (*IJET* 2026) |

### 3.2 Day-28 Detailed Model & Baseline Comparison
| Model / Rule | Split Scheme | Feature Tier | ROC-AUC [95% CI] | AUC-PR [95% CI] | ECE | Precision@Top-10% | Recall@Top-10% |
|---|---|---|---|---|---|---|---|
| **LightGBM + Isotonic** | Student-Grouped 5-Fold | Tier A+D (Acad + VLE) | **0.7061** [0.6989, 0.7140] | **0.3716** [0.3587, 0.3857] | 0.0089 | 0.4608 | 0.2484 |
| **LightGBM + Isotonic (Privacy-Safe)** | Student-Grouped 5-Fold | Tier A (Academic-Only) | 0.6980 [0.6903, 0.7069] | 0.3637 [0.3515, 0.3780] | 0.0079 | 0.4557 | 0.2457 |
| **Logistic Regression + Isotonic** | Student-Grouped 5-Fold | Tier A+D (Acad + VLE) | 0.6901 [0.6831, 0.6986] | 0.3439 [0.3312, 0.3568] | 0.0085 | 0.4331 | 0.2335 |
| **LightGBM + Isotonic (Course Holdout)** | Course-Held-Out (7 Modules) | Tier A+D (Acad + VLE) | 0.6539 [0.6468, 0.6631] | 0.2919 [0.2824, 0.3042] | 0.0272 | 0.3630 | 0.1957 |
| **Rule Baseline 1:** No assessment by cutoff | Deterministic Rule | Tier A | 0.5209 | 0.1926 | — | 0.3085 | 0.1663 |
| **Rule Baseline 2:** Zero VLE clicks in last 7d | Deterministic Rule | Tier D | 0.5318 | 0.1974 | — | 0.2391 | 0.1289 |

### 3.3 Real-Data Privacy-Cost Findings (Tier A vs. Tier A+D)
- At Day 14 (before many courses have had their first graded assessment due), excluding behavioural VLE click logs drops ROC-AUC from **0.6699** to **0.6452** (Δ = **-0.0247**).
- By Day 28, Academic-Only Tier A reaches **0.6980** vs. **0.7061** with VLE clicks (Δ = **-0.0081**), and by Day 60 Academic-Only reaches **0.7092** vs. **0.7171** (Δ = **-0.0080**).
- **Takeaway for Indian Coaching (DPDP s.9(3)):** Unlike online MOOCs where assessment is sparse early on, offline JEE/NEET coaching institutes run weekly chapter tests and fortnightly mocks plus mandatory physical attendance registers (Tier B). Thus, gating off Tier D digital behavioural tracking for minors under DPDP s.9(3) incurs a bounded, transparent trade-off that shrinks rapidly once test history accumulates.

## 4. Part 2 — ASSISTments2009 Next-Response Prediction (`pyKT` Protocol)
| Model | Category | 5-Fold Mean ROC-AUC ± SD | Student Bootstrap 95% CI | 5-Fold Mean Accuracy | Runs on Laptop CPU (<15s)? |
|---|---|---|---|---|---|
| **Ours: Hierarchical Rasch/IRT + Online EAP** | Explainable Psychometric (CPU) | **0.7633 ± 0.0012** | [0.7560, 0.7785] | 0.7376 | Yes (~3 s/fold) |
| **Ours: 1PL Rasch (Global Online EAP only)** | Explainable Psychometric (CPU) | 0.7588 ± 0.0011 | [0.7519, 0.7746] | 0.7345 | Yes (~2 s/fold) |
| **Ours: 4-Param BKT (Baum-Welch EM + LF-AVG)** | Classical KT Baseline (CPU) | 0.7135 ± 0.0006 | [0.7023, 0.7273] | 0.7205 | Yes (~4 s/fold) |
| **Ours: Additive Logistic (Student + Item Bias)** | Simple Baseline (CPU) | 0.7407 ± 0.0006 | [0.7310, 0.7550] | 0.7292 | Yes (<1 s/fold) |
| **Published: SAKT** (Liu et al., NeurIPS 2022) | Self-Attentive Deep KT (GPU) | 0.7246 ± 0.0017 | — | — | No (GPU training) |
| **Published: DKT** (Liu et al., NeurIPS 2022) | Recurrent Deep KT (GPU) | 0.7541 ± 0.0011 | — | 0.7244 ± 0.0014 | No (GPU training) |
| **Published: AKT** (Liu et al., NeurIPS 2022) | Attentive Deep KT (GPU) | 0.7853 | — | — | No (GPU training) |

## 5. Fairness & Data-Minimisation Audit (OULAD Day 28)
- **Demographic exclusion check:** Training LightGBM *without* demographic features (`gender`, `region`, `highest_education`, `imd_band`, `age_band`, `disability`) yields ROC-AUC = **0.7061**, compared to **0.7114** when demographics are included (Δ = **+0.0053**). Excluding demographic PII aligns with DPDP data minimisation at virtually zero AUC cost.

## 6. Limits of External Validity & Protocol Notes (Stated Upfront)
1. **Domain shift (OULAD ≠ Indian JEE/NEET Coaching):** OULAD tracks adult UK distance-learning university students (`Open University`), where engagement is measured via VLE clicks and course withdrawal is self-initiated online. In Tier-2/3 Indian coaching (Patna/Kota), students are predominantly 16–19-year-olds attending physical classes with OMR mock tests and structured fee instalments.
2. **DPDP Section 9(3) & Behavioural Clicks:** OULAD's strongest early predictors (days 14–28) are VLE click streams, which correspond to **Tier D (digital behavioural tracking)** in DataMoat's feature taxonomy. Under DPDP s.9(3), Tier D is strictly disabled for under-18 students.
3. **ASSISTments2009 ≠ Negative-Marked Mock Exams:** ASSISTments Skill Builder logs formative middle-school mathematics practice with hints and multiple attempts, whereas JEE/NEET mock tests have +4/−1 negative marking where strategic blanking (MNAR) occurs.
4. **Protocol comparability notes:**
   - On OULAD, Wu et al. (*PLOS ONE* 2026) and *IJET* (2026) evaluate day 14/28/42/60 cutoffs; exact cohort filtering (e.g. handling of pre-course withdrawals and demographic inclusion) varies slightly across papers, so we report both student-grouped CV and course-held-out splits and treat published values as benchmark anchors rather than claiming leaderboard superiority.
   - On ASSISTments2009, we follow `pyKT`'s `assist2009_preprocess.py` + `split_datasets.py` pipeline (`random_state=1024`, 20% test students, 5-fold CV, `min_seq_len=3`, `maxlen=200`). While `pyKT` trains neural models on KC-expanded sequences and aggregates to question level via LF-AVG, our `OnlineRaschEAP` scores question difficulty directly (`b_q` shrunk to skill `b_s`) with online EAP updates.
