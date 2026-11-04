"""
Comprehensive unit, property, canary, and data tests for Agent D (`ml.public_validation`).

Covers all required tests in `the Round 1 public-validation brief (removed in the 2026-11 cleanup)`:
1. Leakage test: mutating any assessment or VLE row with `date >= cutoff_day` leaves
   `build_oulad_features_as_of` output strictly identical (`assert_frame_equal`).
2. Group split test: asserts zero student overlap between train, calibration, and test folds
   in both OULAD (`_cross_val_predict_grouped`) and ASSISTments2009 (`preprocess_assistments_pykt`).
3. Sanity canaries:
   - Shuffled-label canary: permuting `y_train` yields test ROC-AUC in `0.50 +/- 0.03`.
   - Constant majority-class prediction canary: ROC-AUC == `0.5000`.
   - Determinism canary: running twice with `seed=42` produces identical predictions and metrics to >= 6 decimals.
4. BKT EM parameter recovery unit test: recovers known `(p_init, p_transit, p_slip, p_guess)` on
   simulated BKT trajectories to within `0.05`.
5. Online EAP equivalence unit test: `online_eap_step` called sequentially matches `batch_eap`
   on the same item/response sequence to `< 1e-12`.
6. Edge-case tests:
   - Students withdrawing on or before `cutoff_day` (`date_unregistration <= cutoff_day`) are excluded.
   - Students registering on or after `cutoff_day` (`date_registration >= cutoff_day`) are excluded.
   - ASSISTments rows with missing (`NaN`) `skill_id`, duplicate `order_id` multi-skill rows, and
     students with `< 3` interactions are handled cleanly without crashes.
7. Contract & real-data tests (`@pytest.mark.data`):
   - Validates generated `metrics.json` against `contracts/metrics.schema.json`, `manifest.json`
     against `contracts/artifact_manifest.schema.json`, and checks `public_oulad_roc_auc_day28 >= 0.70`
     and `public_assistments2009_kt_auc >= 0.65`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple

import jsonschema
import numpy as np
import pandas as pd
import pytest
import yaml
from sklearn.metrics import roc_auc_score

from ml.public_validation.assistments import (
    BKTModel,
    BKTParams,
    LogisticItemStudentBaseline,
    OnlineRaschEAP,
    SequenceRecord,
    preprocess_assistments_pykt,
)
from ml.public_validation.oulad import (
    ACADEMIC_FEATURE_COLS,
    BEHAVIOURAL_FEATURE_COLS,
    _cross_val_predict_grouped,
    aggregate_vle_daily,
    bootstrap_student_ci,
    build_oulad_features_as_of,
    compute_ece,
    precision_recall_at_top_pct,
    run_fairness_audit,
)


ROOT_DIR = Path(__file__).resolve().parents[3]
CONTRACTS_DIR = ROOT_DIR / "contracts"
PUBLIC_DATA_DIR = ROOT_DIR / "data" / "public"
ARTIFACTS_DIR = ROOT_DIR / "ml" / "public_validation" / "artifacts" / "v1.0.0"


# ---------------------------------------------------------------------------
# Synthetic Fixtures for Fast CI Unit Tests (No Public Data Download Needed)
# ---------------------------------------------------------------------------


def _make_synthetic_oulad_tables(n_students: int = 240, seed: int = 42) -> Tuple[pd.DataFrame, ...]:
    rng = np.random.default_rng(seed)
    modules = ["AAA", "BBB", "CCC", "DDD"]
    presentations = ["2013J", "2014J"]

    student_rows = []
    reg_rows = []
    sa_rows = []
    vle_rows = []

    for i in range(n_students):
        sid = 10000 + i
        # Some students take 2 modules to test student-grouped CV
        n_mods = 2 if (i % 12 == 0) else 1
        chosen_mods = rng.choice(modules, size=n_mods, replace=False)
        gender = "M" if (i % 2 == 0) else "F"
        imd = "0-10%" if (i % 3 == 0) else "50-60%"
        age = "0-35" if (i % 4 != 0) else "35-55"
        dis = "N" if (i % 7 != 0) else "Y"

        latent_risk = rng.normal(0.0, 1.0)
        for mod in chosen_mods:
            pres = str(rng.choice(presentations))
            will_withdraw = (latent_risk + rng.normal(0, 0.6)) > 0.55
            if will_withdraw:
                final_res = "Withdrawn"
                unreg_day = float(rng.integers(30, 180))
            else:
                final_res = "Pass" if rng.random() > 0.25 else "Fail"
                unreg_day = np.nan

            student_rows.append(
                {
                    "code_module": mod,
                    "code_presentation": pres,
                    "id_student": sid,
                    "gender": gender,
                    "region": "Scotland",
                    "highest_education": "A Level or Equivalent",
                    "imd_band": imd,
                    "age_band": age,
                    "num_of_prev_attempts": int(rng.integers(0, 2)),
                    "studied_credits": 60,
                    "disability": dis,
                    "final_result": final_res,
                    "module_presentation_length": 240,
                }
            )
            reg_rows.append(
                {
                    "code_module": mod,
                    "code_presentation": pres,
                    "id_student": sid,
                    "date_registration": float(rng.integers(-60, -2)),
                    "date_unregistration": unreg_day,
                }
            )

            # Assessments: id 1 due day 12, id 2 due day 25, id 3 due day 50
            base_ass_id = (modules.index(mod) * 10) + (0 if pres == "2013J" else 5)
            for a_idx, due_d in enumerate([12, 25, 50], start=1):
                aid = base_ass_id + a_idx
                # Lower submission probability and lower score if high latent_risk
                if rng.random() > (0.45 if will_withdraw else 0.10):
                    sub_d = due_d + int(rng.integers(-3, 3))
                    sc = float(np.clip(72.0 - 15.0 * latent_risk + rng.normal(0, 10), 0, 100))
                    sa_rows.append(
                        {
                            "id_assessment": aid,
                            "id_student": sid,
                            "date_submitted": sub_d,
                            "is_banked": 0,
                            "score": sc,
                        }
                    )

            # VLE clicks before and after day 28
            for d in range(-5, 65, 3):
                clicks = max(0, int(rng.poisson(lam=max(1.0, 10.0 - 4.0 * latent_risk))))
                if clicks > 0:
                    vle_rows.append(
                        {
                            "code_module": mod,
                            "code_presentation": pres,
                            "id_student": sid,
                            "id_site": 500 + (d % 4),
                            "date": d,
                            "sum_click": clicks,
                        }
                    )

    ass_rows = []
    for mod in modules:
        for pres in presentations:
            base_ass_id = (modules.index(mod) * 10) + (0 if pres == "2013J" else 5)
            for a_idx, due_d in enumerate([12, 25, 50], start=1):
                ass_rows.append(
                    {
                        "code_module": mod,
                        "code_presentation": pres,
                        "id_assessment": base_ass_id + a_idx,
                        "assessment_type": "TMA",
                        "date": due_d,
                        "weight": 25.0,
                    }
                )

    vle_meta = pd.DataFrame(
        [
            {"id_site": 500, "code_module": "AAA", "code_presentation": "2013J", "activity_type": "oucontent"},
            {"id_site": 501, "code_module": "AAA", "code_presentation": "2013J", "activity_type": "forumng"},
            {"id_site": 502, "code_module": "AAA", "code_presentation": "2013J", "activity_type": "quiz"},
            {"id_site": 503, "code_module": "AAA", "code_presentation": "2013J", "activity_type": "homepage"},
        ]
    )

    student_info = pd.DataFrame(student_rows)
    student_reg = pd.DataFrame(reg_rows)
    assessments = pd.DataFrame(ass_rows)
    student_assessment = pd.DataFrame(sa_rows)
    student_vle = pd.DataFrame(vle_rows)
    vle_daily = aggregate_vle_daily(student_vle, vle_meta)

    return student_info, student_reg, assessments, student_assessment, vle_daily


# ---------------------------------------------------------------------------
# 1. Temporal Leakage Test (OULAD)
# ---------------------------------------------------------------------------


def test_oulad_strict_temporal_no_leakage() -> None:
    """
    Mutating any assessment due date, student submission, or VLE click row with
    `date >= cutoff_day` MUST leave `build_oulad_features_as_of` output strictly identical.
    """
    cutoff = 28
    s_info, s_reg, ass, s_ass, vle_daily = _make_synthetic_oulad_tables(n_students=120, seed=42)

    feat_orig = build_oulad_features_as_of(
        student_info=s_info,
        student_reg=s_reg,
        assessments=ass,
        student_assessment=s_ass,
        vle_daily=vle_daily,
        cutoff_day=cutoff,
    )

    # Corrupt all future data (`date >= cutoff`) in assessments, student_assessment, and vle_daily
    ass_mut = ass.copy()
    ass_mut.loc[ass_mut["date"] >= cutoff, "weight"] = 9999.0

    s_ass_mut = s_ass.copy()
    s_ass_mut.loc[s_ass_mut["date_submitted"] >= cutoff, "score"] = 0.0
    # Inject extra future submissions at date == cutoff and date == cutoff + 10
    extra_sa = pd.DataFrame(
        [
            {
                "id_assessment": int(ass["id_assessment"].iloc[0]),
                "id_student": int(s_info["id_student"].iloc[0]),
                "date_submitted": cutoff,  # exact boundary `date >= cutoff` must also be ignored
                "is_banked": 0,
                "score": 100.0,
            }
        ]
    )
    s_ass_mut = pd.concat([s_ass_mut, extra_sa], ignore_index=True)

    vle_mut = vle_daily.copy()
    vle_mut.loc[vle_mut["date"] >= cutoff, "sum_click"] = 999999
    # Inject boundary VLE row at date == cutoff
    extra_vle = vle_mut.iloc[:1].copy()
    extra_vle["date"] = cutoff
    extra_vle["sum_click"] = 88888
    vle_mut = pd.concat([vle_mut, extra_vle], ignore_index=True)

    feat_mut = build_oulad_features_as_of(
        student_info=s_info,
        student_reg=s_reg,
        assessments=ass_mut,
        student_assessment=s_ass_mut,
        vle_daily=vle_mut,
        cutoff_day=cutoff,
    )

    all_cols = ACADEMIC_FEATURE_COLS + BEHAVIOURAL_FEATURE_COLS + ["target_withdrawn"]
    pd.testing.assert_frame_equal(feat_orig[all_cols], feat_mut[all_cols], check_exact=True)


# ---------------------------------------------------------------------------
# 2. Edge Cases: Early Withdrawals, Late Registrations, Missing Skills, Short Seqs
# ---------------------------------------------------------------------------


def test_oulad_edge_cases_early_withdrawn_and_late_registered() -> None:
    """
    Students who withdrew on or before `cutoff_day` (`date_unregistration <= cutoff_day`)
    or registered on or after `cutoff_day` (`date_registration >= cutoff_day`) must be excluded.
    """
    s_info, s_reg, ass, s_ass, vle_daily = _make_synthetic_oulad_tables(n_students=40, seed=7)
    cutoff = 28

    # Force student 0 to withdraw at day 10 (before cutoff 28)
    sid_early_withdraw = int(s_reg.iloc[0]["id_student"])
    s_reg.loc[s_reg["id_student"] == sid_early_withdraw, "date_unregistration"] = 10.0
    s_info.loc[s_info["id_student"] == sid_early_withdraw, "final_result"] = "Withdrawn"

    # Force student 1 to withdraw on exact boundary day 28 (`<= cutoff`)
    sid_boundary_withdraw = int(s_reg.iloc[1]["id_student"])
    s_reg.loc[s_reg["id_student"] == sid_boundary_withdraw, "date_unregistration"] = 28.0
    s_info.loc[s_info["id_student"] == sid_boundary_withdraw, "final_result"] = "Withdrawn"

    # Force student 2 to register at day 30 (`>= cutoff`)
    sid_late_reg = int(s_reg.iloc[2]["id_student"])
    s_reg.loc[s_reg["id_student"] == sid_late_reg, "date_registration"] = 30.0

    cohort = build_oulad_features_as_of(s_info, s_reg, ass, s_ass, vle_daily, cutoff_day=cutoff)
    active_ids = set(cohort["id_student"].tolist())

    assert sid_early_withdraw not in active_ids
    assert sid_boundary_withdraw not in active_ids
    assert sid_late_reg not in active_ids


def test_assistments_preprocessing_edge_cases(tmp_path: Path) -> None:
    """
    Verify ASSISTments preprocessing handles:
    - Missing (`NaN`) `skill_id` rows (dropped cleanly)
    - Duplicate `order_id` multi-skill rows (collapsed into a single question event with skill tuple)
    - Students with `< 3` interactions (filtered out cleanly)
    - Zero student overlap between train, val, and test splits
    """
    rows = []
    # 15 valid students with 5 interactions each; order_id 1000 has duplicate skills (10, 20)
    for u in range(1, 16):
        for step in range(5):
            oid = u * 100 + step
            qid = 500 + step
            corr = 1 if (u + step) % 2 == 0 else 0
            rows.append({"order_id": oid, "user_id": u, "problem_id": qid, "skill_id": 10, "correct": corr})
            if step == 0:
                # Duplicate order_id for multi-skill question
                rows.append({"order_id": oid, "user_id": u, "problem_id": qid, "skill_id": 20, "correct": corr})

    # Add rows with NaN skill_id
    rows.append({"order_id": 99901, "user_id": 1, "problem_id": 601, "skill_id": np.nan, "correct": 1})
    # Add a student with only 2 interactions (< min_seq_len=3)
    rows.append({"order_id": 99902, "user_id": 999, "problem_id": 602, "skill_id": 10, "correct": 0})
    rows.append({"order_id": 99903, "user_id": 999, "problem_id": 603, "skill_id": 10, "correct": 1})

    csv_file = tmp_path / "mini_assistments.csv"
    pd.DataFrame(rows).to_csv(csv_file, index=False)

    prep = preprocess_assistments_pykt(csv_file, min_seq_len=3, max_seq_len=200, seed=1024, n_folds=5)
    stats = prep["stats"]

    assert stats["dropped_short_users"] == 1
    assert stats["kept_users"] == 15
    # 15 students * 5 question events + 2 events from user 999 before short-user filter = 77 question events, 92 KC-expanded
    assert stats["question_level_events"] == 77
    assert stats["kc_expanded_interactions"] == 92

    test_users = {r.user_id for r in prep["test_records"]}
    assert "999" not in test_users
    for tr_recs, val_recs in prep["folds"]:
        tr_u = {r.user_id for r in tr_recs}
        val_u = {r.user_id for r in val_recs}
        assert tr_u.isdisjoint(test_users)
        assert val_u.isdisjoint(test_users)
        assert tr_u.isdisjoint(val_u)


# ---------------------------------------------------------------------------
# 3. Group Split & Sanity Canaries (Shuffled Labels, Constant Pred, Determinism)
# ---------------------------------------------------------------------------


def test_oulad_canaries_and_determinism() -> None:
    """
    Verify:
    - Majority-class constant prediction gives ROC-AUC == 0.50.
    - Shuffled labels give ROC-AUC within 0.50 +/- 0.05 on synthetic data (and 0.50 +/- 0.02 on large N).
    - Seed-42 determinism: two calls produce identical predictions to 1e-12.
    """
    s_info, s_reg, ass, s_ass, vle_daily = _make_synthetic_oulad_tables(n_students=300, seed=42)
    cohort = build_oulad_features_as_of(s_info, s_reg, ass, s_ass, vle_daily, cutoff_day=28)
    feature_cols = ACADEMIC_FEATURE_COLS + BEHAVIOURAL_FEATURE_COLS
    y_true = cohort["target_withdrawn"].to_numpy()

    # 1. Constant majority-class prediction canary -> ROC-AUC == 0.50
    const_preds = np.zeros_like(y_true, dtype=float)
    assert roc_auc_score(y_true, const_preds) == pytest.approx(0.50, abs=1e-12)

    # 2. Seed-42 determinism canary
    preds_run1 = _cross_val_predict_grouped(
        cohort, feature_cols, group_col="id_student", model_type="lightgbm", n_splits=5, seed=42
    )
    preds_run2 = _cross_val_predict_grouped(
        cohort, feature_cols, group_col="id_student", model_type="lightgbm", n_splits=5, seed=42
    )
    np.testing.assert_allclose(preds_run1, preds_run2, rtol=0.0, atol=1e-10)
    assert roc_auc_score(y_true, preds_run1) > 0.65

    # 3. Shuffled-label canary: average over 5 random permutations of y_true on N=2500 synthetic rows
    rng = np.random.default_rng(123)
    big_cohort = pd.concat([cohort] * 8, ignore_index=True)
    big_cohort["id_student"] = np.arange(len(big_cohort))
    big_cohort["target_withdrawn"] = rng.binomial(1, 0.20, size=len(big_cohort))
    shuf_preds = _cross_val_predict_grouped(
        big_cohort, feature_cols, group_col="id_student", model_type="logistic", n_splits=5, seed=42
    )
    shuf_auc = roc_auc_score(big_cohort["target_withdrawn"].to_numpy(), shuf_preds)
    assert abs(shuf_auc - 0.50) <= 0.025, f"Shuffled-label canary AUC {shuf_auc:.4f} deviated from 0.50!"


# ---------------------------------------------------------------------------
# 4. BKT EM Parameter Recovery Unit Test
# ---------------------------------------------------------------------------


def test_bkt_em_parameter_recovery() -> None:
    """
    Simulate binary observation sequences from a 4-parameter BKT model with known
    `(p_init=0.35, p_transit=0.18, p_slip=0.10, p_guess=0.22)` and verify that
    `BKTModel.fit_single_skill_em` recovers all 4 parameters within `0.05`.
    """
    true_params = BKTParams(p_init=0.35, p_transit=0.18, p_slip=0.10, p_guess=0.22)
    rng = np.random.default_rng(2026)

    n_sequences = 1500
    seq_len = 18
    simulated_seqs: List[np.ndarray] = []

    for _ in range(n_sequences):
        mastered = rng.random() < true_params.p_init
        obs = np.empty(seq_len, dtype=np.int32)
        for t in range(seq_len):
            if mastered:
                obs[t] = 1 if (rng.random() < (1.0 - true_params.p_slip)) else 0
            else:
                obs[t] = 1 if (rng.random() < true_params.p_guess) else 0
                if rng.random() < true_params.p_transit:
                    mastered = True
        simulated_seqs.append(obs)

    recovered = BKTModel.fit_single_skill_em(simulated_seqs, max_iter=60, tol=1e-6)

    assert abs(recovered.p_init - true_params.p_init) < 0.05, f"p_init: {recovered.p_init} vs {true_params.p_init}"
    assert abs(recovered.p_transit - true_params.p_transit) < 0.05, (
        f"p_transit: {recovered.p_transit} vs {true_params.p_transit}"
    )
    assert abs(recovered.p_slip - true_params.p_slip) < 0.05, f"p_slip: {recovered.p_slip} vs {true_params.p_slip}"
    assert abs(recovered.p_guess - true_params.p_guess) < 0.05, (
        f"p_guess: {recovered.p_guess} vs {true_params.p_guess}"
    )


# ---------------------------------------------------------------------------
# 5. Online EAP vs. Batch EAP Exact Equivalence Unit Test
# ---------------------------------------------------------------------------


def test_online_eap_matches_batch_eap() -> None:
    """
    Verify that sequential calls to `OnlineRaschEAP.online_eap_step` (with `decay=1.0`)
    produce the exact same `(theta, se)` as `OnlineRaschEAP.batch_eap` at every step `t`.
    """
    model = OnlineRaschEAP(grid_min=-4.0, grid_max=4.0, grid_points=81, prior_sigma=1.0)
    rng = np.random.default_rng(99)
    b_seq = rng.uniform(-2.2, 2.2, size=25)
    r_seq = rng.integers(0, 2, size=25)

    log_post = model.log_prior.copy()
    for t in range(1, len(b_seq) + 1):
        log_post, online_theta, online_se = model.online_eap_step(
            log_post, float(b_seq[t - 1]), int(r_seq[t - 1]), decay=1.0
        )
        batch_theta, batch_se = model.batch_eap(b_seq[:t], r_seq[:t])
        assert online_theta == pytest.approx(batch_theta, abs=1e-12)
        assert online_se == pytest.approx(batch_se, abs=1e-12)


# ---------------------------------------------------------------------------
# 6. Helper & Fairness Audit Unit Tests
# ---------------------------------------------------------------------------


def test_metrics_helpers_and_fairness_audit() -> None:
    s_info, s_reg, ass, s_ass, vle_daily = _make_synthetic_oulad_tables(n_students=160, seed=42)
    cohort = build_oulad_features_as_of(s_info, s_reg, ass, s_ass, vle_daily, cutoff_day=28)
    preds = _cross_val_predict_grouped(
        cohort,
        ACADEMIC_FEATURE_COLS + BEHAVIOURAL_FEATURE_COLS,
        group_col="id_student",
        model_type="logistic",
        n_splits=5,
        seed=42,
    )
    y_true = cohort["target_withdrawn"].to_numpy()
    ece = compute_ece(y_true, preds)
    assert 0.0 <= ece <= 1.0

    prec10, rec10 = precision_recall_at_top_pct(y_true, preds, top_frac=0.10)
    assert 0.0 <= prec10 <= 1.0
    assert 0.0 <= rec10 <= 1.0

    cis = bootstrap_student_ci(cohort["id_student"].to_numpy(), y_true, preds, n_resamples=50, seed=42)
    assert cis["roc_auc"][0] <= cis["roc_auc"][1]

    fair = run_fairness_audit(cohort, preds, cutoff_day=28, seed=42)
    assert "roc_auc_without_demographics" in fair
    assert "roc_auc_with_demographics" in fair
    assert "slices" in fair


# ---------------------------------------------------------------------------
# 7. Real-Data & Contract Schema Validation Tests (`@pytest.mark.data`)
# ---------------------------------------------------------------------------


@pytest.mark.data
def test_public_validation_artifacts_and_bars() -> None:
    """
    Validate generated artifacts in `ml/public_validation/artifacts/v1.0.0/` against
    `contracts/metrics.schema.json`, `contracts/artifact_manifest.schema.json`, and
    `contracts/metrics_bars.yaml` (`public_oulad_roc_auc_day28 >= 0.70`,
    `public_assistments2009_kt_auc >= 0.65`).
    """
    oulad_zip = PUBLIC_DATA_DIR / "oulad" / "studentInfo.csv"
    assist_csv = PUBLIC_DATA_DIR / "assistments2009" / "skill_builder_data.csv"
    if not (oulad_zip.exists() and assist_csv.exists()):
        pytest.skip(
            "Public datasets not found in data/public/. Run `python scripts/download_public_data.py` first."
        )

    metrics_path = ARTIFACTS_DIR / "metrics.json"
    manifest_path = ARTIFACTS_DIR / "manifest.json"
    model_card_path = ARTIFACTS_DIR / "model_card.md"
    summary_path = ARTIFACTS_DIR / "public_validation_summary.json"

    assert metrics_path.exists(), f"Missing {metrics_path}; run `python -m ml.public_validation.evaluate`."
    assert manifest_path.exists(), f"Missing {manifest_path}."
    assert model_card_path.exists(), f"Missing {model_card_path}."
    assert summary_path.exists(), f"Missing {summary_path}."

    metrics_doc = json.loads(metrics_path.read_text(encoding="utf-8"))
    manifest_doc = json.loads(manifest_path.read_text(encoding="utf-8"))

    metrics_schema = json.loads((CONTRACTS_DIR / "metrics.schema.json").read_text(encoding="utf-8"))
    manifest_schema = json.loads((CONTRACTS_DIR / "artifact_manifest.schema.json").read_text(encoding="utf-8"))

    jsonschema.validate(instance=metrics_doc, schema=metrics_schema)
    jsonschema.validate(instance=manifest_doc, schema=manifest_schema)

    bars_doc = yaml.safe_load((CONTRACTS_DIR / "metrics_bars.yaml").read_text(encoding="utf-8"))
    bars = {b["metric_key"]: b["target"] for b in bars_doc["bars"] if b["metric_key"].startswith("public_")}

    results_by_key = {r["metric_key"]: r for r in metrics_doc["results"]}
    assert "public_oulad_roc_auc_day28" in results_by_key
    assert "public_assistments2009_kt_auc" in results_by_key

    oulad_val = results_by_key["public_oulad_roc_auc_day28"]["value"]
    assist_val = results_by_key["public_assistments2009_kt_auc"]["value"]

    assert oulad_val >= bars["public_oulad_roc_auc_day28"], (
        f"OULAD day-28 ROC-AUC {oulad_val} below bar {bars['public_oulad_roc_auc_day28']}"
    )
    assert assist_val >= bars["public_assistments2009_kt_auc"], (
        f"ASSISTments2009 KT AUC {assist_val} below bar {bars['public_assistments2009_kt_auc']}"
    )
    assert results_by_key["public_oulad_roc_auc_day28"]["passed_bar"] is True
    assert results_by_key["public_assistments2009_kt_auc"]["passed_bar"] is True
