# Public validation module (`ml.public_validation`)

External, third-party benchmark validation for the **Institute Intelligence Platform (Case B: The Data Moat)** (`TECH_PLAN.md` §10, §24 D6 & D15).

## 1. Purpose & Honest Framing

Synthetic data (`datagen/`) proves pipeline wiring and ground-truth parameter recovery, but cannot prove real-world signal on its own. This module evaluates the **exact same algorithm families** used by the platform on two real, peer-reviewed public education datasets under published protocols:

1. **OULAD (Open University Learning Analytics Dataset, CC BY 4.0):**
   - **Task:** Early course withdrawal (`final_result == 'Withdrawn'`) from data strictly before day 14, 28, 42, and 60 (`date < cutoff_day`).
   - **Models:** Calibrated LightGBM (`LGBMClassifier` + inner-fold `IsotonicRegression`), Calibrated Logistic Regression, and two deterministic rule baselines (*"No assessment submitted by cutoff"*, *"Zero VLE clicks in last 7 days"*).
   - **Real-data privacy-cost ablation:** Compares **Tier A (Academic-only)** vs. **Tier A+D (Academic + Behavioural VLE click streams)** across all four windows, plus a demographic-exclusion fairness audit at day 28.
   - **Splits:** 5-fold student-grouped CV (`GroupKFold` on `id_student`) and 7-fold course-held-out CV (`GroupKFold` on `code_module`).
2. **ASSISTments 2009–2010 (Skill Builder, Research Use Only):**
   - **Task:** Question-level one-step-ahead next-response prediction (`t >= 1`) under the standardized **`pyKT` 5-fold student-held-out protocol** (Liu et al., NeurIPS 2022).
   - **Models:** `OnlineRaschEAP` (Hierarchical Rasch/1PL IRT with skill difficulty priors and exact online EAP ability updates), `1PL Rasch` (global student online EAP), `BKTModel` (4-parameter Baum-Welch EM with LF-AVG multi-skill fusion), and `LogisticItemStudentBaseline`.

---

## 2. Quickstart

### Step 1: Install Pinned Dependencies
```powershell
python -m venv ml/public_validation/.venv
.\ml\public_validation\.venv\Scripts\pip install -r ml/public_validation/requirements.txt
```

### Step 2: Download & Verify Public Datasets (~130 MB total)
```powershell
.\ml\public_validation\.venv\Scripts\python scripts/download_public_data.py
```
- Downloads OULAD (`46.75 MB`, CC BY 4.0) and ASSISTments 2009–2010 Skill Builder (`83.20 MB`, research use only) into git-ignored `data/public/`, verifies MD5 & SHA-256 digests, and writes `data/public/README.txt`.
- **EdNet-KT1** (`CC BY-NC 4.0`) is skipped by default; pass `--with-ednet --yes-large-files` only if running optional scale stress-tests.

### Step 3: Run Full Evaluation & Write Validated Artifacts (~3.5 min on CPU)
```powershell
.\ml\public_validation\.venv\Scripts\python -m ml.public_validation.evaluate
```
Writes and schema-validates:
- `ml/public_validation/artifacts/v1.0.0/metrics.json` (validates against `contracts/metrics.schema.json`)
- `ml/public_validation/artifacts/v1.0.0/manifest.json` (validates against `contracts/artifact_manifest.schema.json`)
- `ml/public_validation/artifacts/v1.0.0/model_card.md`
- `ml/public_validation/artifacts/v1.0.0/public_validation_summary.json`

### Step 4: Run Unit, Canary, Leakage, and Data Tests
```powershell
# Fast CI unit & canary tests (no public data required; runs in ~5s):
.\ml\public_validation\.venv\Scripts\python -m pytest ml/public_validation/tests -m "not data" -v -rs

# Full suite including @pytest.mark.data contract & acceptance-bar checks:
.\ml\public_validation\.venv\Scripts\python -m pytest ml/public_validation/tests -v -rs
```

---

## 3. Acceptance Bars (`contracts/metrics_bars.yaml`)

| Metric Key | Gate | Target | Our Result (Seed 42) | 95% Student Bootstrap CI | Status |
|---|---|---:|---:|---:|---|
| `public_oulad_roc_auc_day28` | `report` | `>= 0.70` | **0.7061** | `[0.6989, 0.7140]` | **PASS** |
| `public_assistments2009_kt_auc` | `report` | `>= 0.65` | **0.7633** | `[0.7560, 0.7785]` | **PASS** |

---

## 4. Explicit Limitations & External Validity

1. **OULAD ≠ Indian JEE/NEET Coaching:** OULAD covers UK adult distance-education university courses (`Open University`), where engagement is measured via VLE clicks and course withdrawal is self-initiated online. In Tier-2/3 Indian coaching (Patna/Kota), students are 16–19-year-olds attending physical classes with weekly OMR mock tests and fee instalments.
2. **DPDP Section 9(3) & Behavioural Clicks:** OULAD's strongest early predictors at days 14–28 are VLE click streams, which correspond to **Tier D (digital behavioural tracking)** in DataMoat's taxonomy. Under DPDP s.9(3), Tier D is strictly off for minors (`< 18`). Our real-data ablation quantifies this exact gap on OULAD and explains why offline coaching's weekly test cadence + physical attendance (Tiers A & B) closes the gap much earlier than a sparse-assessment MOOC.
3. **ASSISTments ≠ Negative-Marked Mock Exams:** ASSISTments Skill Builder logs formative US middle-school math practice with hints, whereas JEE/NEET exams use `+4/-1` negative marking where strategic question skipping (MNAR) is critical.
4. **No Cross-Domain Weight Transfer:** Public datasets validate *algorithmic soundness* only. Production models train and calibrate strictly on tenant-scoped coaching records.
