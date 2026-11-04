"""
OULAD (Open University Learning Analytics Dataset, CC BY 4.0) Early-Withdrawal Validation.

Implements TECH_PLAN §10 (Public validation protocol) & Agent D prompt:
- Observation windows: day 14, 28, 42, 60 from course start (`date < cutoff_day`).
- Cohort filtering: excludes students who withdrew on or before the cutoff (`date_unregistration <= cutoff_day`)
  or who registered on/after the cutoff (`date_registration >= cutoff_day`).
- Strict temporal leakage boundary: only assessments and VLE interactions with `date < cutoff_day`
  are used to build features.
- Privacy-cost experiment on real data:
  * Tier A (Academic-only): registration timing, course credits/attempts, assessments submitted & scores before cutoff.
  * Tier A + D (Academic + Behavioural VLE clicks): adds VLE click counts, active days, recency, and activity-type counts.
  * Demographics (`gender`, `region`, `highest_education`, `imd_band`, `age_band`, `disability`) are EXCLUDED from the
    production feature sets (DPDP minimisation) and evaluated only in a separate fairness audit.
- Evaluation splits:
  * 5-fold Student-Grouped Cross-Validation (`GroupKFold` by `id_student`, since a student can take multiple modules).
  * Course-Held-Out Split (`GroupKFold` by `code_module` across the 7 OU modules).
- Models:
  * LightGBM + Isotonic Calibration (fitted strictly on an inner validation split inside each training fold).
  * Logistic Regression + Isotonic Calibration.
  * Rule Baseline 1: "No assessment submitted by cutoff" (or missed due assessment).
  * Rule Baseline 2: "Zero VLE clicks in last 7 days" (`[cutoff - 7, cutoff)`).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler


CORE_VLE_ACTIVITIES = (
    "oucontent",
    "forumng",
    "quiz",
    "subpage",
    "homepage",
    "resource",
    "url",
)

DEMOGRAPHIC_COLS = (
    "gender",
    "region",
    "highest_education",
    "imd_band",
    "age_band",
    "disability",
)

ACADEMIC_FEATURE_COLS = [
    "date_registration_rel",
    "num_of_prev_attempts",
    "studied_credits",
    "module_presentation_length",
    "due_assessments_count",
    "assessments_submitted_count",
    "assessments_submitted_ratio_vs_due",
    "assessments_missed_due_count",
    "score_mean_so_far",
    "score_min_so_far",
    "score_max_so_far",
    "score_weighted_so_far",
    "score_z_vs_cohort",
    "submission_delay_mean_days",
    "no_assessment_submitted_flag",
]

BEHAVIOURAL_FEATURE_COLS = [
    "vle_total_clicks",
    "vle_log_total_clicks",
    "vle_active_days",
    "vle_active_days_ratio",
    "vle_clicks_per_active_day",
    "vle_clicks_last_7d",
    "vle_clicks_last_14d",
    "vle_clicks_prev_14d",
    "vle_clicks_slope_14d",
    "vle_clicks_ratio_last7_vs_total",
    "vle_days_since_last_click",
    "vle_first_active_date",
    "vle_span_days",
    "vle_pre_course_clicks",
    "vle_unique_sites",
    "vle_clicks_z_vs_cohort",
    "vle_active_days_z_vs_cohort",
    "zero_vle_clicks_last_7d_flag",
] + [f"vle_clicks_{act}" for act in CORE_VLE_ACTIVITIES]


@dataclass
class ModelEvalSummary:
    model_name: str
    feature_tier: str
    split_scheme: str
    cutoff_day: int
    n_samples: int
    n_students: int
    n_events: int
    roc_auc: float
    roc_auc_ci_low: float
    roc_auc_ci_high: float
    auc_pr: float
    auc_pr_ci_low: float
    auc_pr_ci_high: float
    ece: float
    precision_at_top10pct: float
    recall_at_top10pct: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OULADWindowResult:
    cutoff_day: int
    n_samples: int
    n_students: int
    n_events: int
    models: Dict[str, ModelEvalSummary]
    fairness_audit: Optional[Dict[str, Any]] = None
    calibration_curve: Optional[Dict[str, List[float]]] = None


def aggregate_vle_daily(student_vle: pd.DataFrame, vle: pd.DataFrame) -> pd.DataFrame:
    """
    Pre-aggregate raw `studentVle` (~10.6M rows) with `vle` activity types into a compact
    per-(code_module, code_presentation, id_student, date) table.
    """
    if student_vle.empty:
        cols = [
            "code_module",
            "code_presentation",
            "id_student",
            "date",
            "sum_click",
            "n_sites",
        ] + [f"clicks_{act}" for act in CORE_VLE_ACTIVITIES]
        return pd.DataFrame(columns=cols)

    vle_meta = vle[["id_site", "code_module", "code_presentation", "activity_type"]].drop_duplicates(
        subset=["id_site"]
    )
    merged = student_vle.merge(
        vle_meta[["id_site", "activity_type"]],
        on="id_site",
        how="left",
    )
    merged["activity_type"] = merged["activity_type"].fillna("other")

    key_cols = ["code_module", "code_presentation", "id_student", "date"]
    daily = (
        merged.groupby(key_cols, as_index=False)
        .agg(
            sum_click=("sum_click", "sum"),
            n_sites=("id_site", "nunique"),
        )
    )

    # Activity-specific clicks for core activity types
    act_sub = merged[merged["activity_type"].isin(CORE_VLE_ACTIVITIES)]
    if not act_sub.empty:
        piv = (
            act_sub.pivot_table(
                index=key_cols,
                columns="activity_type",
                values="sum_click",
                aggfunc="sum",
                fill_value=0,
            )
            .reset_index()
        )
        piv.columns = [
            col if col in key_cols else f"clicks_{col}" for col in piv.columns
        ]
        daily = daily.merge(piv, on=key_cols, how="left")

    for act in CORE_VLE_ACTIVITIES:
        col = f"clicks_{act}"
        if col not in daily.columns:
            daily[col] = 0
        else:
            daily[col] = daily[col].fillna(0).astype(np.int32)

    daily["sum_click"] = daily["sum_click"].astype(np.int32)
    daily["n_sites"] = daily["n_sites"].astype(np.int32)
    daily["date"] = daily["date"].astype(np.int32)
    return daily


def load_or_build_vle_daily_cache(oulad_dir: Path, max_cutoff_day: int = 65) -> pd.DataFrame:
    """
    Load pre-aggregated daily VLE cache from `oulad_dir / 'vle_daily_cache.parquet'`.
    If not present, stream `studentVle.csv` in chunks (filtering `date <= max_cutoff_day`)
    and write the parquet cache so subsequent runs and Colab executions take < 2 seconds.
    """
    cache_path = oulad_dir / "vle_daily_cache.parquet"
    if cache_path.exists():
        return pd.read_parquet(cache_path)

    vle = pd.read_csv(oulad_dir / "vle.csv")
    vle_map = vle.set_index("id_site")["activity_type"].to_dict()

    chunks: List[pd.DataFrame] = []
    key_cols = ["code_module", "code_presentation", "id_student", "date"]

    for chunk in pd.read_csv(
        oulad_dir / "studentVle.csv",
        chunksize=1_000_000,
        dtype={
            "code_module": "string",
            "code_presentation": "string",
            "id_student": "int64",
            "id_site": "int64",
            "date": "int32",
            "sum_click": "int32",
        },
    ):
        chunk = chunk[chunk["date"] <= max_cutoff_day].copy()
        if chunk.empty:
            continue
        chunk["activity_type"] = chunk["id_site"].map(vle_map).fillna("other")
        for act in CORE_VLE_ACTIVITIES:
            chunk[f"clicks_{act}"] = np.where(chunk["activity_type"] == act, chunk["sum_click"], 0)

        agg_spec = {
            "sum_click": ("sum_click", "sum"),
            "n_sites": ("id_site", "nunique"),
        }
        for act in CORE_VLE_ACTIVITIES:
            agg_spec[f"clicks_{act}"] = (f"clicks_{act}", "sum")

        chunks.append(chunk.groupby(key_cols, as_index=False).agg(**agg_spec))

    if not chunks:
        empty_df = aggregate_vle_daily(pd.DataFrame(), vle)
        empty_df.to_parquet(cache_path, index=False)
        return empty_df

    combined = pd.concat(chunks, ignore_index=True)
    agg_final = {
        "sum_click": ("sum_click", "sum"),
        "n_sites": ("n_sites", "sum"),
    }
    for act in CORE_VLE_ACTIVITIES:
        agg_final[f"clicks_{act}"] = (f"clicks_{act}", "sum")

    daily = combined.groupby(key_cols, as_index=False).agg(**agg_final)
    daily.to_parquet(cache_path, index=False)
    return daily


def build_oulad_features_as_of(
    student_info: pd.DataFrame,
    student_reg: pd.DataFrame,
    assessments: pd.DataFrame,
    student_assessment: pd.DataFrame,
    vle_daily: pd.DataFrame,
    cutoff_day: int,
) -> pd.DataFrame:
    """
    Build strictly leakage-free OULAD student-module features as of `cutoff_day`.

    Temporal rule (`as_of_rule`):
    - Only rows with timestamp/date `< cutoff_day` are used (`date < cutoff_day` for VLE and
      assessment due dates; `date_submitted < cutoff_day` for student submissions).
    - Students who already withdrew before or on `cutoff_day` (`date_unregistration <= cutoff_day`)
      are excluded from the active risk cohort at `cutoff_day`.
    - Students who registered on or after `cutoff_day` (`date_registration >= cutoff_day`)
      are excluded.
    """
    key_cols = ["code_module", "code_presentation", "id_student"]

    base = student_info.merge(student_reg, on=key_cols, how="inner")

    # Exclude students who withdrew on or before cutoff_day
    already_withdrawn = base["date_unregistration"].notna() & (base["date_unregistration"] <= cutoff_day)
    # Exclude students whose registration date is on or after cutoff_day
    registered_after = base["date_registration"].notna() & (base["date_registration"] >= cutoff_day)
    # Exclude students with missing registration date AND withdrawn without unregistration date
    invalid_reg = base["date_registration"].isna() & (base["final_result"] == "Withdrawn") & base["date_unregistration"].isna()

    cohort = base[~(already_withdrawn | registered_after | invalid_reg)].copy().reset_index(drop=True)
    if cohort.empty:
        return cohort

    cohort["target_withdrawn"] = (cohort["final_result"] == "Withdrawn").astype(int)
    cohort["date_registration_rel"] = cohort["date_registration"].fillna(0.0).astype(float)

    if "module_presentation_length" not in cohort.columns:
        cohort["module_presentation_length"] = 240.0
    else:
        cohort["module_presentation_length"] = cohort["module_presentation_length"].fillna(240.0).astype(float)

    # --- 1. Academic Features (Assessments strictly before cutoff_day) ---
    ass_non_exam = assessments[assessments["assessment_type"] != "Exam"].copy()
    ass_non_exam["date"] = pd.to_numeric(ass_non_exam["date"], errors="coerce")

    # Assessments due strictly before cutoff_day
    ass_due = ass_non_exam[ass_non_exam["date"].notna() & (ass_non_exam["date"] < cutoff_day)]
    due_counts = (
        ass_due.groupby(["code_module", "code_presentation"], as_index=False)
        .agg(due_assessments_count=("id_assessment", "count"))
    )
    cohort = cohort.merge(due_counts, on=["code_module", "code_presentation"], how="left")
    cohort["due_assessments_count"] = cohort["due_assessments_count"].fillna(0).astype(float)

    # Student submissions strictly before cutoff_day
    sa = student_assessment.copy()
    sa["date_submitted"] = pd.to_numeric(sa["date_submitted"], errors="coerce")
    sa["score"] = pd.to_numeric(sa["score"], errors="coerce")
    sa_prior = sa[sa["date_submitted"].notna() & (sa["date_submitted"] < cutoff_day)].copy()

    # Join with assessment metadata (ignore assessment `date` if >= cutoff_day so future due dates are not leaked)
    ass_meta = ass_non_exam[["id_assessment", "code_module", "code_presentation", "date", "weight"]].copy()
    ass_meta["due_date_known"] = np.where(ass_meta["date"] < cutoff_day, ass_meta["date"], np.nan)
    sa_prior = sa_prior.merge(
        ass_meta[["id_assessment", "code_module", "code_presentation", "due_date_known", "weight"]],
        on="id_assessment",
        how="inner",
    )

    if not sa_prior.empty:
        sa_prior["delay_days"] = (sa_prior["date_submitted"] - sa_prior["due_date_known"]).fillna(0.0)
        sa_prior["weighted_score"] = sa_prior["score"].fillna(0.0) * sa_prior["weight"].fillna(1.0)
        sa_prior["submitted_for_due"] = sa_prior["due_date_known"].notna().astype(int)

        stu_ass = (
            sa_prior.groupby(key_cols, as_index=False)
            .agg(
                assessments_submitted_count=("id_assessment", "nunique"),
                submitted_due_count=("submitted_for_due", "sum"),
                score_mean_so_far=("score", "mean"),
                score_min_so_far=("score", "min"),
                score_max_so_far=("score", "max"),
                weighted_score_sum=("weighted_score", "sum"),
                weight_sum=("weight", "sum"),
                submission_delay_mean_days=("delay_days", "mean"),
            )
        )
        stu_ass["score_weighted_so_far"] = np.where(
            stu_ass["weight_sum"] > 0,
            stu_ass["weighted_score_sum"] / stu_ass["weight_sum"],
            stu_ass["score_mean_so_far"],
        )
        cohort = cohort.merge(
            stu_ass[
                key_cols
                + [
                    "assessments_submitted_count",
                    "submitted_due_count",
                    "score_mean_so_far",
                    "score_min_so_far",
                    "score_max_so_far",
                    "score_weighted_so_far",
                    "submission_delay_mean_days",
                ]
            ],
            on=key_cols,
            how="left",
        )
    else:
        for col in [
            "assessments_submitted_count",
            "submitted_due_count",
            "score_mean_so_far",
            "score_min_so_far",
            "score_max_so_far",
            "score_weighted_so_far",
            "submission_delay_mean_days",
        ]:
            cohort[col] = np.nan

    cohort["assessments_submitted_count"] = cohort["assessments_submitted_count"].fillna(0.0)
    cohort["submitted_due_count"] = cohort["submitted_due_count"].fillna(0.0)
    cohort["assessments_missed_due_count"] = np.maximum(
        0.0, cohort["due_assessments_count"] - cohort["submitted_due_count"]
    )
    cohort["assessments_submitted_ratio_vs_due"] = np.where(
        cohort["due_assessments_count"] > 0,
        np.clip(cohort["assessments_submitted_count"] / cohort["due_assessments_count"], 0.0, 2.0),
        np.where(cohort["assessments_submitted_count"] > 0, 1.0, 0.0),
    )
    cohort["score_mean_so_far"] = cohort["score_mean_so_far"].fillna(0.0)
    cohort["score_min_so_far"] = cohort["score_min_so_far"].fillna(0.0)
    cohort["score_max_so_far"] = cohort["score_max_so_far"].fillna(0.0)
    cohort["score_weighted_so_far"] = cohort["score_weighted_so_far"].fillna(0.0)
    cohort["submission_delay_mean_days"] = cohort["submission_delay_mean_days"].fillna(0.0)
    cohort["no_assessment_submitted_flag"] = (cohort["assessments_submitted_count"] == 0).astype(float)

    # Cohort-relative z-score of mean score so far
    mod_stats = cohort.groupby(["code_module", "code_presentation"])["score_mean_so_far"].transform
    mod_mean = mod_stats("mean")
    mod_std = mod_stats("std").fillna(1.0).replace(0.0, 1.0)
    cohort["score_z_vs_cohort"] = (cohort["score_mean_so_far"] - mod_mean) / mod_std

    # --- 2. Behavioural VLE Features (strictly date < cutoff_day) ---
    vle_prior = vle_daily[vle_daily["date"] < cutoff_day].copy()
    if not vle_prior.empty:
        vle_prior["clicks_7d"] = np.where(vle_prior["date"] >= cutoff_day - 7, vle_prior["sum_click"], 0)
        vle_prior["clicks_14d"] = np.where(vle_prior["date"] >= cutoff_day - 14, vle_prior["sum_click"], 0)
        vle_prior["clicks_prev14d"] = np.where(
            (vle_prior["date"] >= cutoff_day - 28) & (vle_prior["date"] < cutoff_day - 14),
            vle_prior["sum_click"],
            0,
        )
        vle_prior["clicks_pre_course"] = np.where(vle_prior["date"] < 0, vle_prior["sum_click"], 0)

        vle_agg_spec = {
            "vle_total_clicks": ("sum_click", "sum"),
            "vle_active_days": ("date", "nunique"),
            "vle_clicks_last_7d": ("clicks_7d", "sum"),
            "vle_clicks_last_14d": ("clicks_14d", "sum"),
            "vle_clicks_prev_14d": ("clicks_prev14d", "sum"),
            "vle_pre_course_clicks": ("clicks_pre_course", "sum"),
            "vle_first_active_date": ("date", "min"),
            "vle_last_active_date": ("date", "max"),
            "vle_unique_sites": ("n_sites", "sum"),
        }
        for act in CORE_VLE_ACTIVITIES:
            col = f"clicks_{act}"
            if col in vle_prior.columns:
                vle_agg_spec[f"vle_clicks_{act}"] = (col, "sum")

        stu_vle = vle_prior.groupby(key_cols, as_index=False).agg(**vle_agg_spec)
        cohort = cohort.merge(stu_vle, on=key_cols, how="left")
    else:
        for col in [
            "vle_total_clicks",
            "vle_active_days",
            "vle_clicks_last_7d",
            "vle_clicks_last_14d",
            "vle_clicks_prev_14d",
            "vle_pre_course_clicks",
            "vle_first_active_date",
            "vle_last_active_date",
            "vle_unique_sites",
        ] + [f"vle_clicks_{act}" for act in CORE_VLE_ACTIVITIES]:
            cohort[col] = np.nan

    for col in [
        "vle_total_clicks",
        "vle_active_days",
        "vle_clicks_last_7d",
        "vle_clicks_last_14d",
        "vle_clicks_prev_14d",
        "vle_pre_course_clicks",
        "vle_unique_sites",
    ] + [f"vle_clicks_{act}" for act in CORE_VLE_ACTIVITIES]:
        if col not in cohort.columns:
            cohort[col] = 0.0
        cohort[col] = cohort[col].fillna(0.0).astype(float)

    cohort["vle_log_total_clicks"] = np.log1p(cohort["vle_total_clicks"])
    cohort["vle_active_days_ratio"] = cohort["vle_active_days"] / float(max(cutoff_day + 15, 1))
    cohort["vle_clicks_per_active_day"] = np.where(
        cohort["vle_active_days"] > 0,
        cohort["vle_total_clicks"] / cohort["vle_active_days"],
        0.0,
    )
    cohort["vle_days_since_last_click"] = np.where(
        cohort["vle_last_active_date"].notna(),
        cutoff_day - cohort["vle_last_active_date"],
        float(cutoff_day + 30),
    )
    cohort["vle_first_active_date"] = np.where(
        cohort["vle_first_active_date"].notna(),
        cohort["vle_first_active_date"],
        float(cutoff_day),
    )
    cohort["vle_span_days"] = np.where(
        cohort["vle_last_active_date"].notna(),
        cohort["vle_last_active_date"] - cohort["vle_first_active_date"] + 1.0,
        0.0,
    )
    cohort["vle_clicks_slope_14d"] = cohort["vle_clicks_last_14d"] - cohort["vle_clicks_prev_14d"]
    cohort["vle_clicks_ratio_last7_vs_total"] = np.where(
        cohort["vle_total_clicks"] > 0,
        cohort["vle_clicks_last_7d"] / cohort["vle_total_clicks"],
        0.0,
    )
    cohort["zero_vle_clicks_last_7d_flag"] = (cohort["vle_clicks_last_7d"] == 0).astype(float)

    vle_mod_mean = cohort.groupby(["code_module", "code_presentation"])["vle_total_clicks"].transform("mean")
    vle_mod_std = (
        cohort.groupby(["code_module", "code_presentation"])["vle_total_clicks"]
        .transform("std")
        .fillna(1.0)
        .replace(0.0, 1.0)
    )
    cohort["vle_clicks_z_vs_cohort"] = (cohort["vle_total_clicks"] - vle_mod_mean) / vle_mod_std

    ad_mod_mean = cohort.groupby(["code_module", "code_presentation"])["vle_active_days"].transform("mean")
    ad_mod_std = (
        cohort.groupby(["code_module", "code_presentation"])["vle_active_days"]
        .transform("std")
        .fillna(1.0)
        .replace(0.0, 1.0)
    )
    cohort["vle_active_days_z_vs_cohort"] = (cohort["vle_active_days"] - ad_mod_mean) / ad_mod_std

    return cohort


def compute_ece(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Compute Expected Calibration Error (ECE) across `n_bins` uniform probability bins."""
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bin_ids = np.digitize(y_prob, bins[1:-1], right=True)
    ece = 0.0
    n = len(y_true)
    if n == 0:
        return 0.0
    for b in range(n_bins):
        mask = bin_ids == b
        if np.any(mask):
            frac_pos = float(np.mean(y_true[mask]))
            mean_pred = float(np.mean(y_prob[mask]))
            ece += (np.sum(mask) / n) * abs(frac_pos - mean_pred)
    return float(ece)


def compute_calibration_curve_bins(
    y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10
) -> Dict[str, List[float]]:
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bin_ids = np.digitize(y_prob, bins[1:-1], right=True)
    mean_preds, frac_positives, counts = [], [], []
    for b in range(n_bins):
        mask = bin_ids == b
        if np.any(mask):
            mean_preds.append(float(np.mean(y_prob[mask])))
            frac_positives.append(float(np.mean(y_true[mask])))
            counts.append(int(np.sum(mask)))
    return {
        "mean_predicted_prob": mean_preds,
        "empirical_fraction_positive": frac_positives,
        "bin_counts": counts,
    }


def precision_recall_at_top_pct(
    y_true: np.ndarray, y_score: np.ndarray, top_frac: float = 0.10
) -> Tuple[float, float]:
    """Compute precision@top-k and recall@top-k where k = int(top_frac * len(y_true))."""
    n = len(y_true)
    if n == 0:
        return 0.0, 0.0
    k = max(1, int(round(top_frac * n)))
    # Stable sort descending
    order = np.argsort(-y_score, kind="mergesort")
    top_y = y_true[order[:k]]
    prec = float(np.mean(top_y))
    total_pos = int(np.sum(y_true))
    rec = float(np.sum(top_y) / total_pos) if total_pos > 0 else 0.0
    return prec, rec


def bootstrap_student_ci(
    student_ids: np.ndarray,
    y_true: np.ndarray,
    y_score: np.ndarray,
    n_resamples: int = 500,
    seed: int = 42,
) -> Dict[str, Tuple[float, float]]:
    """
    Cluster bootstrap over unique `student_ids` (95% CI, >= 500 resamples).
    Uses fast group index gathering so 500 resamples over 28,000 rows run in ~1.2s.
    """
    rng = np.random.default_rng(seed)
    unique_students, inv = np.unique(student_ids, return_inverse=True)
    n_stu = len(unique_students)

    # Check if each student appears roughly once (90% of OULAD students appear in 1 module)
    # Use multinomial weights over students mapped back to rows via `inv`
    roc_vals = np.empty(n_resamples, dtype=float)
    pr_vals = np.empty(n_resamples, dtype=float)

    for i in range(n_resamples):
        stu_counts = rng.multinomial(n_stu, np.full(n_stu, 1.0 / n_stu))
        row_weights = stu_counts[inv]
        active = row_weights > 0
        if np.unique(y_true[active]).size < 2:
            roc_vals[i] = np.nan
            pr_vals[i] = np.nan
            continue
        roc_vals[i] = roc_auc_score(y_true[active], y_score[active], sample_weight=row_weights[active])
        pr_vals[i] = average_precision_score(
            y_true[active], y_score[active], sample_weight=row_weights[active]
        )

    roc_clean = roc_vals[~np.isnan(roc_vals)]
    pr_clean = pr_vals[~np.isnan(pr_vals)]
    return {
        "roc_auc": (
            float(np.percentile(roc_clean, 2.5)),
            float(np.percentile(roc_clean, 97.5)),
        ),
        "auc_pr": (
            float(np.percentile(pr_clean, 2.5)),
            float(np.percentile(pr_clean, 97.5)),
        ),
    }


def _cross_val_predict_grouped(
    df: pd.DataFrame,
    feature_cols: List[str],
    group_col: str,
    model_type: str,
    n_splits: int = 5,
    seed: int = 42,
) -> np.ndarray:
    """
    Run grouped cross-validation with inner student-grouped isotonic calibration.
    Asserts zero group overlap between train, calibration, and test folds.
    """
    n_unique_groups = df[group_col].nunique()
    actual_splits = min(n_splits, n_unique_groups)
    gkf = GroupKFold(n_splits=actual_splits)

    X = df[feature_cols].to_numpy(dtype=np.float64)
    y = df["target_withdrawn"].to_numpy(dtype=np.int32)
    groups = df[group_col].to_numpy()
    student_ids = df["id_student"].to_numpy()

    oof_preds = np.zeros(len(df), dtype=np.float64)

    for fold_idx, (train_idx, test_idx) in enumerate(gkf.split(X, y, groups=groups)):
        # Leakage assertion: no group in common between train and test
        train_groups = set(groups[train_idx])
        test_groups = set(groups[test_idx])
        assert train_groups.isdisjoint(test_groups), (
            f"Leakage detected: {len(train_groups & test_groups)} overlapping groups in {group_col}"
        )

        # Split train_idx into 85% fit and 15% calibration grouped by student_id
        train_students = student_ids[train_idx]
        uniq_tr_stu = np.unique(train_students)
        rng = np.random.default_rng(seed + fold_idx * 101)
        shuffled_stu = rng.permutation(uniq_tr_stu)
        n_cal = max(1, int(0.15 * len(shuffled_stu)))
        cal_stu_set = set(shuffled_stu[:n_cal])

        is_cal = np.isin(train_students, list(cal_stu_set))
        fit_sub_idx = train_idx[~is_cal]
        cal_sub_idx = train_idx[is_cal]

        X_fit, y_fit = X[fit_sub_idx], y[fit_sub_idx]
        X_cal, y_cal = X[cal_sub_idx], y[cal_sub_idx]
        X_test = X[test_idx]

        if model_type == "lightgbm":
            clf = LGBMClassifier(
                n_estimators=220,
                learning_rate=0.04,
                num_leaves=23,
                max_depth=6,
                min_child_samples=60,
                subsample=0.8,
                colsample_bytree=0.8,
                reg_alpha=1.0,
                reg_lambda=2.0,
                random_state=seed + fold_idx,
                n_jobs=-1,
                verbose=-1,
            )
            clf.fit(X_fit, y_fit)
            raw_cal = clf.predict_proba(X_cal)[:, 1]
            raw_test = clf.predict_proba(X_test)[:, 1]
        elif model_type == "logistic":
            scaler = StandardScaler()
            X_fit_s = scaler.fit_transform(X_fit)
            X_cal_s = scaler.transform(X_cal)
            X_test_s = scaler.transform(X_test)
            clf = LogisticRegression(C=1.0, max_iter=500, random_state=seed + fold_idx)
            clf.fit(X_fit_s, y_fit)
            raw_cal = clf.predict_proba(X_cal_s)[:, 1]
            raw_test = clf.predict_proba(X_test_s)[:, 1]
        else:
            raise ValueError(f"Unknown model_type: {model_type}")

        iso = IsotonicRegression(y_min=0.001, y_max=0.999, out_of_bounds="clip")
        iso.fit(raw_cal, y_cal)
        oof_preds[test_idx] = iso.transform(raw_test)

    return oof_preds


def _summarize_predictions(
    model_name: str,
    feature_tier: str,
    split_scheme: str,
    cutoff_day: int,
    df: pd.DataFrame,
    y_score: np.ndarray,
    n_bootstrap: int = 500,
    seed: int = 42,
) -> ModelEvalSummary:
    y_true = df["target_withdrawn"].to_numpy(dtype=np.int32)
    student_ids = df["id_student"].to_numpy()
    roc = float(roc_auc_score(y_true, y_score))
    pr = float(average_precision_score(y_true, y_score))
    ece = compute_ece(y_true, y_score)
    prec10, rec10 = precision_recall_at_top_pct(y_true, y_score, top_frac=0.10)

    if n_bootstrap > 0:
        cis = bootstrap_student_ci(student_ids, y_true, y_score, n_resamples=n_bootstrap, seed=seed)
        roc_low, roc_high = cis["roc_auc"]
        pr_low, pr_high = cis["auc_pr"]
    else:
        roc_low = roc_high = roc
        pr_low = pr_high = pr

    return ModelEvalSummary(
        model_name=model_name,
        feature_tier=feature_tier,
        split_scheme=split_scheme,
        cutoff_day=cutoff_day,
        n_samples=len(df),
        n_students=int(df["id_student"].nunique()),
        n_events=int(np.sum(y_true)),
        roc_auc=roc,
        roc_auc_ci_low=roc_low,
        roc_auc_ci_high=roc_high,
        auc_pr=pr,
        auc_pr_ci_low=pr_low,
        auc_pr_ci_high=pr_high,
        ece=ece,
        precision_at_top10pct=prec10,
        recall_at_top10pct=rec10,
    )


def run_fairness_audit(
    df: pd.DataFrame,
    y_score_no_demo: np.ndarray,
    cutoff_day: int,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Fairness and DPDP data-minimisation audit at `cutoff_day`:
    1. Measures slice-level recall@top-10% and ROC-AUC across demographic attributes
       (gender, age_band, imd_band, disability) for the demographic-free LightGBM model.
       Slices with < 30 withdrawal events are explicitly labelled 'insufficient_data'.
    2. Compares demographic-free LightGBM vs. LightGBM trained WITH one-hot demographics
       to quantify whether excluding demographics hurts accuracy.
    """
    y_true = df["target_withdrawn"].to_numpy(dtype=np.int32)
    n = len(df)
    k = max(1, int(round(0.10 * n)))
    order = np.argsort(-y_score_no_demo, kind="mergesort")
    flagged = np.zeros(n, dtype=bool)
    flagged[order[:k]] = True

    slices_report: Dict[str, Dict[str, Any]] = {}
    for col in ("gender", "age_band", "imd_band", "disability"):
        if col not in df.columns:
            continue
        col_report: Dict[str, Any] = {}
        recalls = []
        for val, grp in df.groupby(col, dropna=False):
            idx = grp.index.to_numpy()
            y_sub = y_true[idx]
            n_events = int(np.sum(y_sub))
            val_key = str(val)
            if n_events < 30:
                col_report[val_key] = {
                    "n": len(idx),
                    "n_events": n_events,
                    "status": "insufficient_data",
                }
            else:
                rec = float(np.sum(flagged[idx] & (y_sub == 1)) / n_events)
                auc = float(roc_auc_score(y_sub, y_score_no_demo[idx])) if np.unique(y_sub).size > 1 else np.nan
                recalls.append(rec)
                col_report[val_key] = {
                    "n": len(idx),
                    "n_events": n_events,
                    "recall_at_top10pct": round(rec, 4),
                    "roc_auc": round(auc, 4),
                    "status": "ok",
                }
        col_report["max_recall_gap"] = (
            round(float(max(recalls) - min(recalls)), 4) if len(recalls) >= 2 else 0.0
        )
        slices_report[col] = col_report

    # Separate run WITH demographics to verify DPDP minimisation impact
    demo_dummies = pd.get_dummies(
        df[[c for c in DEMOGRAPHIC_COLS if c in df.columns]].fillna("missing"),
        prefix="demo",
        dtype=float,
    )
    df_with_demo = pd.concat([df, demo_dummies], axis=1)
    full_Plus_demo_cols = ACADEMIC_FEATURE_COLS + BEHAVIOURAL_FEATURE_COLS + list(demo_dummies.columns)
    preds_with_demo = _cross_val_predict_grouped(
        df_with_demo,
        feature_cols=full_Plus_demo_cols,
        group_col="id_student",
        model_type="lightgbm",
        n_splits=5,
        seed=seed,
    )
    auc_no_demo = float(roc_auc_score(y_true, y_score_no_demo))
    auc_with_demo = float(roc_auc_score(y_true, preds_with_demo))

    return {
        "cutoff_day": cutoff_day,
        "roc_auc_without_demographics": round(auc_no_demo, 4),
        "roc_auc_with_demographics": round(auc_with_demo, 4),
        "delta_roc_auc_from_demographics": round(auc_with_demo - auc_no_demo, 4),
        "slices": slices_report,
    }


def evaluate_oulad_window(
    student_info: pd.DataFrame,
    student_reg: pd.DataFrame,
    assessments: pd.DataFrame,
    student_assessment: pd.DataFrame,
    vle_daily: pd.DataFrame,
    cutoff_day: int = 28,
    n_bootstrap: int = 500,
    seed: int = 42,
    include_course_holdout: bool = True,
    include_fairness: bool = False,
) -> OULADWindowResult:
    """
    Evaluate all models, baselines, and privacy-tier ablations on OULAD at `cutoff_day`.
    """
    cohort = build_oulad_features_as_of(
        student_info=student_info,
        student_reg=student_reg,
        assessments=assessments,
        student_assessment=student_assessment,
        vle_daily=vle_daily,
        cutoff_day=cutoff_day,
    )

    full_cols = ACADEMIC_FEATURE_COLS + BEHAVIOURAL_FEATURE_COLS
    acad_cols = ACADEMIC_FEATURE_COLS

    models_out: Dict[str, ModelEvalSummary] = {}

    # 1. LightGBM (Academic + Behavioural, Student-Grouped 5-fold CV)
    preds_lgb_full = _cross_val_predict_grouped(
        cohort, full_cols, group_col="id_student", model_type="lightgbm", n_splits=5, seed=seed
    )
    models_out["lgbm_acad_behav_student_cv"] = _summarize_predictions(
        model_name="LightGBM + Isotonic (Academic + Behavioural)",
        feature_tier="A+D",
        split_scheme="student_grouped_5fold",
        cutoff_day=cutoff_day,
        df=cohort,
        y_score=preds_lgb_full,
        n_bootstrap=n_bootstrap,
        seed=seed,
    )

    # 2. LightGBM (Academic-Only Tier A, Student-Grouped 5-fold CV) -> Privacy-cost ablation
    preds_lgb_acad = _cross_val_predict_grouped(
        cohort, acad_cols, group_col="id_student", model_type="lightgbm", n_splits=5, seed=seed
    )
    models_out["lgbm_academic_only_student_cv"] = _summarize_predictions(
        model_name="LightGBM + Isotonic (Academic-Only Tier A)",
        feature_tier="A",
        split_scheme="student_grouped_5fold",
        cutoff_day=cutoff_day,
        df=cohort,
        y_score=preds_lgb_acad,
        n_bootstrap=n_bootstrap,
        seed=seed,
    )

    # 3. Logistic Regression (Academic + Behavioural, Student-Grouped 5-fold CV)
    preds_lr_full = _cross_val_predict_grouped(
        cohort, full_cols, group_col="id_student", model_type="logistic", n_splits=5, seed=seed
    )
    models_out["logreg_acad_behav_student_cv"] = _summarize_predictions(
        model_name="Logistic Regression + Isotonic (Academic + Behavioural)",
        feature_tier="A+D",
        split_scheme="student_grouped_5fold",
        cutoff_day=cutoff_day,
        df=cohort,
        y_score=preds_lr_full,
        n_bootstrap=max(100, n_bootstrap // 2),
        seed=seed,
    )

    # 4. Logistic Regression (Academic-Only Tier A)
    preds_lr_acad = _cross_val_predict_grouped(
        cohort, acad_cols, group_col="id_student", model_type="logistic", n_splits=5, seed=seed
    )
    models_out["logreg_academic_only_student_cv"] = _summarize_predictions(
        model_name="Logistic Regression + Isotonic (Academic-Only Tier A)",
        feature_tier="A",
        split_scheme="student_grouped_5fold",
        cutoff_day=cutoff_day,
        df=cohort,
        y_score=preds_lr_acad,
        n_bootstrap=max(100, n_bootstrap // 2),
        seed=seed,
    )

    # 5. Baseline Rule 1: "No assessment submitted by cutoff"
    rule_no_ass = cohort["no_assessment_submitted_flag"].to_numpy(dtype=float)
    models_out["rule_no_assessment"] = _summarize_predictions(
        model_name="Rule: No assessment submitted by cutoff",
        feature_tier="A",
        split_scheme="student_grouped_5fold",
        cutoff_day=cutoff_day,
        df=cohort,
        y_score=rule_no_ass,
        n_bootstrap=max(100, n_bootstrap // 2),
        seed=seed,
    )

    # 6. Baseline Rule 2: "Zero VLE clicks in last 7 days"
    rule_zero_vle7 = cohort["zero_vle_clicks_last_7d_flag"].to_numpy(dtype=float)
    models_out["rule_zero_vle_7d"] = _summarize_predictions(
        model_name="Rule: Zero VLE clicks in last 7 days",
        feature_tier="D",
        split_scheme="student_grouped_5fold",
        cutoff_day=cutoff_day,
        df=cohort,
        y_score=rule_zero_vle7,
        n_bootstrap=max(100, n_bootstrap // 2),
        seed=seed,
    )

    # 7. Course-Held-Out Split (GroupKFold by code_module)
    if include_course_holdout and cohort["code_module"].nunique() >= 2:
        preds_course_ho = _cross_val_predict_grouped(
            cohort,
            full_cols,
            group_col="code_module",
            model_type="lightgbm",
            n_splits=min(7, cohort["code_module"].nunique()),
            seed=seed,
        )
        models_out["lgbm_acad_behav_course_holdout"] = _summarize_predictions(
            model_name="LightGBM + Isotonic (Course-Held-Out Split)",
            feature_tier="A+D",
            split_scheme="course_held_out",
            cutoff_day=cutoff_day,
            df=cohort,
            y_score=preds_course_ho,
            n_bootstrap=max(100, n_bootstrap // 2),
            seed=seed,
        )

    cal_curve = compute_calibration_curve_bins(
        cohort["target_withdrawn"].to_numpy(dtype=np.int32),
        preds_lgb_full,
        n_bins=10,
    )
    fairness = (
        run_fairness_audit(cohort, preds_lgb_full, cutoff_day=cutoff_day, seed=seed)
        if include_fairness
        else None
    )

    return OULADWindowResult(
        cutoff_day=cutoff_day,
        n_samples=len(cohort),
        n_students=int(cohort["id_student"].nunique()),
        n_events=int(cohort["target_withdrawn"].sum()),
        models=models_out,
        fairness_audit=fairness,
        calibration_curve=cal_curve,
    )


def run_oulad_suite(
    oulad_dir: Path,
    cutoffs: Tuple[int, ...] = (14, 28, 42, 60),
    n_bootstrap: int = 500,
    seed: int = 42,
) -> Dict[int, OULADWindowResult]:
    """Load OULAD tables and run the full evaluation across observation windows."""
    courses = pd.read_csv(oulad_dir / "courses.csv")
    student_info = pd.read_csv(oulad_dir / "studentInfo.csv").merge(
        courses, on=["code_module", "code_presentation"], how="left"
    )
    student_reg = pd.read_csv(oulad_dir / "studentRegistration.csv")
    assessments = pd.read_csv(oulad_dir / "assessments.csv")
    student_assessment = pd.read_csv(oulad_dir / "studentAssessment.csv")
    vle_daily = load_or_build_vle_daily_cache(oulad_dir, max_cutoff_day=max(cutoffs) + 5)

    results: Dict[int, OULADWindowResult] = {}
    for day in cutoffs:
        results[day] = evaluate_oulad_window(
            student_info=student_info,
            student_reg=student_reg,
            assessments=assessments,
            student_assessment=student_assessment,
            vle_daily=vle_daily,
            cutoff_day=day,
            n_bootstrap=n_bootstrap if day == 28 else max(200, n_bootstrap // 2),
            seed=seed,
            include_course_holdout=True,
            include_fairness=(day == 28),
        )
    return results
