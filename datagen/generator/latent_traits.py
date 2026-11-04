"""Step 2 & Step 8: Generate student latent traits, topic ability trajectories, and dropout events."""

from __future__ import annotations

import datetime
from typing import Any

import numpy as np
import pandas as pd

from .utils import CONTRACTS_DIR, load_yaml


def load_syllabus_topics() -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, list[str]]]:
    """Load leaf topics and prerequisite DAG from contracts/topics.yaml."""
    doc = load_yaml(CONTRACTS_DIR / "topics.yaml")
    all_nodes = doc["topics"]
    prereqs = doc.get("topic_prereqs", [])

    # Build chapter-to-prereq map
    chapter_prereqs: dict[str, list[str]] = {}
    for edge in prereqs:
        chapter_prereqs.setdefault(edge["topic_id"], []).append(edge["prereq_topic_id"])

    leaf_topics = [t for t in all_nodes if t.get("level") == "topic"]
    topics_by_exam: dict[str, list[str]] = {"jee_main": [], "neet_ug": []}
    for t in leaf_topics:
        for ex in t.get("exams", [t["exam"]]):
            if ex in topics_by_exam:
                topics_by_exam[ex].append(t["id"])

    return leaf_topics, topics_by_exam, chapter_prereqs


def generate_latent_traits_and_dropouts(
    cfg: dict[str, Any],
    students_df: pd.DataFrame,
    student_meta: dict[str, dict[str, Any]],
    leaf_topics: list[dict[str, Any]],
    topics_by_exam: dict[str, list[str]],
    chapter_prereqs: dict[str, list[str]],
    rng_traits: np.random.Generator,
    rng_dropout: np.random.Generator,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate latent traits, monthly topic ability trajectories, and dropout events.

    Also updates students_df status ('left' / 'transferred') and left_date in place.
    """
    base_att = float(cfg["attendance"]["base_rate"])
    base_sd = float(cfg["attendance"].get("base_sd", 0.09))
    annual_dropout_rate = float(cfg["dropout"]["annual_rate"])
    sudden_share = float(cfg["dropout"]["sudden_share"])
    dropper_mult = float(cfg["dropout"]["dropper_hazard_multiplier"])
    fade_min, fade_max = cfg["attendance"]["pre_dropout_fade_weeks"]

    reasons_mix = cfg["dropout"]["reasons_mix"]
    reason_keys = list(reasons_mix.keys())
    reason_probs = np.array([float(reasons_mix[k]) for k in reason_keys], dtype=float)
    reason_probs = reason_probs / reason_probs.sum()

    # Map topic -> chapter parent
    topic_to_chapter = {t["id"]: t["parent_id"] for t in leaf_topics}
    all_chapters = sorted({t["parent_id"] for t in leaf_topics if t["parent_id"] is not None})

    # Assign a difficulty baseline per topic ~ N(0, 0.35)
    topic_ids_sorted = sorted(t["id"] for t in leaf_topics)
    topic_base_offset = {
        tid: float(rng_traits.normal(0.0, 0.25)) for tid in topic_ids_sorted
    }

    student_ids = students_df["id"].tolist()
    n_students = len(student_ids)

    # 1. Sample student-level latent traits
    for sid in student_ids:
        meta = student_meta[sid]
        if meta.get("preset_g") is not None:
            true_g = float(meta["preset_g"]) + 0.15  # slight growth from class 11 to 12
        else:
            true_g = float(rng_traits.normal(0.0, 1.0))
        meta["true_g"] = true_g

        # SES proxy ~ N(0, 1); custom_scholarship or tier_3 slightly lower on average
        ses_shift = -0.3 if meta["city_tier"] == "tier_3" else 0.0
        meta["ses_proxy"] = float(rng_traits.normal(ses_shift, 1.0))

        # Learning rate per month and motivation slope
        meta["learning_rate"] = float(np.clip(rng_traits.normal(0.045, 0.02), -0.01, 0.12))
        meta["motivation"] = float(rng_traits.normal(0.0, 1.0))

        # Base attendance rate: to guarantee >= 8% chronic low attenders (< 0.75) whose dropout rate is within +-25%
        # of the overall rate, we explicitly draw a 16% chronic low attender group with base_attendance in [0.58, 0.70]
        # and an 84% normal attender group with base_attendance in [0.80, 0.94] so non-fade empirical attendance cleanly
        # separates the two groups around 0.75!
        if rng_traits.random() < 0.16:
            meta["base_attendance"] = float(rng_traits.uniform(0.58, 0.70))
            meta["is_chronic_low_attender"] = True
        else:
            meta["base_attendance"] = float(np.clip(rng_traits.normal(0.84, 0.035), 0.80, 0.95))
            meta["is_chronic_low_attender"] = False

        # Risk aversion threshold tau for MNAR blanks under negative marking (-1 for wrong, +4 for correct)
        # Break-even P(correct) is 0.20. Low-ability students have slightly higher risk aversion / blank threshold
        # so that correlation(blank_rate, -theta) > 0.20.
        tau_base = 0.24 - 0.035 * np.tanh(true_g) + float(rng_traits.normal(0.0, 0.025))
        meta["risk_aversion_tau"] = float(np.clip(tau_base, 0.15, 0.36))

    # 2. Sample dropout events per (institute, academic_year) cohort
    # Group students by (institute_id, academic_year)
    dropout_rows: list[dict[str, Any]] = []
    by_cohort: dict[tuple[str, int], list[str]] = {}
    for sid in student_ids:
        m = student_meta[sid]
        by_cohort.setdefault((m["institute_id"], m["academic_year"]), []).append(sid)

    # Monthly hazard weights (1..12), months 3 and 4 (index 3, 4 => July/Aug-Sep) have >= 42% of total mass
    month_weights = np.array(
        [0.04, 0.07, 0.23, 0.22, 0.11, 0.09, 0.07, 0.06, 0.05, 0.03, 0.02, 0.01],
        dtype=float,
    )
    month_weights = month_weights / month_weights.sum()

    for (inst_id, yr), cohort_sids in sorted(by_cohort.items()):
        # Compute relative hazard score per student
        # IMPORTANT: keep chronic-low-attender trait orthogonal to dropout propensity so criterion #6 holds!
        propensities = []
        for sid in cohort_sids:
            m = student_meta[sid]
            # Academic struggle + low motivation + financial stress drive gradual dropout
            lin = -0.45 * m["true_g"] - 0.45 * m["motivation"] - 0.25 * m["ses_proxy"]
            w = float(np.exp(np.clip(lin, -2.5, 2.5)))
            if m["class_level"] == "dropper":
                w *= dropper_mult
            propensities.append(w)
        prop_arr = np.array(propensities, dtype=float)
        prop_arr = prop_arr / prop_arr.mean()

        # Calibrate cohort dropout probability to target annual_dropout_rate
        # Use exact stratified count within [0.14, 0.22] around annual_dropout_rate with binomial noise
        n_c = len(cohort_sids)
        noisy_rate = float(np.clip(rng_dropout.normal(annual_dropout_rate, 0.012), 0.135, 0.235))
        if annual_dropout_rate > 0.25:
            # Scenario override like dropout_x2
            noisy_rate = float(np.clip(rng_dropout.normal(annual_dropout_rate, 0.015), 0.25, 0.70))
        target_k = int(round(n_c * noisy_rate))
        target_k = max(1, min(n_c - 1, target_k))

        # Sample without replacement weighted by prop_arr, preserving chronic_low_attender orthogonality
        # Since gradual fade slightly lowers overall empirical attendance for normal dropouts, we set the dropout rate
        # among the chronic low attender group (`base_attendance < 0.75`) to `0.85 * noisy_rate` so that both
        # `base_attendance < 0.75` AND `empirical_attendance < 0.75` have dropout rates within +-15% (well inside +-25%) of overall!
        chronic_ids = [s for s in cohort_sids if student_meta[s]["is_chronic_low_attender"]]
        normal_ids = [s for s in cohort_sids if not student_meta[s]["is_chronic_low_attender"]]

        k_chronic = int(round(len(chronic_ids) * noisy_rate))
        k_normal = max(0, target_k - k_chronic)

        dropped_set: set[str] = set()
        if k_chronic > 0 and len(chronic_ids) > 0:
            p_c = np.array([prop_arr[cohort_sids.index(s)] for s in chronic_ids], dtype=float)
            p_c /= p_c.sum()
            chosen_c = rng_dropout.choice(chronic_ids, size=min(k_chronic, len(chronic_ids)), replace=False, p=p_c)
            dropped_set.update(chosen_c.tolist())

        if k_normal > 0 and len(normal_ids) > 0:
            p_n = np.array([prop_arr[cohort_sids.index(s)] for s in normal_ids], dtype=float)
            p_n /= p_n.sum()
            chosen_n = rng_dropout.choice(normal_ids, size=min(k_normal, len(normal_ids)), replace=False, p=p_n)
            dropped_set.update(chosen_n.tolist())

        # Assign sudden vs gradual and dates
        dropped_list = sorted(dropped_set)
        n_drop_cohort = len(dropped_list)
        n_sudden = int(round(n_drop_cohort * sudden_share))
        sudden_indices = set(
            rng_dropout.choice(n_drop_cohort, size=min(n_sudden, n_drop_cohort), replace=False).tolist()
        ) if n_drop_cohort > 0 else set()

        for idx_d, sid in enumerate(dropped_list):
            m = student_meta[sid]
            is_sudden = idx_d in sudden_indices
            d_type = "sudden" if is_sudden else "gradual"

            # Month index 1..12
            m_idx = int(rng_dropout.choice(np.arange(1, 13), p=month_weights))
            day_in_month = int(rng_dropout.integers(5, 27))
            drop_date = m["yr_start"] + datetime.timedelta(days=(m_idx - 1) * 30 + day_in_month)
            # Ensure drop_date is at least 25 days after join_date
            min_drop_date = m["join_date"] + datetime.timedelta(days=28)
            if drop_date < min_drop_date:
                drop_date = min_drop_date

            if d_type == "gradual":
                fade_wks = int(rng_dropout.integers(fade_min, fade_max + 1))
                fade_start = drop_date - datetime.timedelta(days=fade_wks * 7)
                if fade_start < m["join_date"]:
                    fade_start = m["join_date"]
            else:
                fade_wks = 0
                fade_start = None

            d_reason = str(rng_dropout.choice(reason_keys, p=reason_probs))
            m["dropped_out"] = True
            m["dropout_date"] = drop_date
            m["fade_start_date"] = fade_start
            m["fade_weeks"] = fade_wks
            m["dropout_type"] = d_type
            m["dropout_reason"] = d_reason

        for sid in cohort_sids:
            m = student_meta[sid]
            if not m.get("dropped_out", False):
                m["dropped_out"] = False
                m["dropout_date"] = None
                m["fade_start_date"] = None
                m["fade_weeks"] = 0
                m["dropout_type"] = None
                m["dropout_reason"] = None

            dropout_rows.append(
                {
                    "student_id": sid,
                    "institute_id": m["institute_id"],
                    "dropped_out": bool(m["dropped_out"]),
                    "dropout_date": m["dropout_date"],
                    "fade_start_date": m["fade_start_date"],
                    "dropout_type": m["dropout_type"],
                    "dropout_reason": m["dropout_reason"],
                }
            )

    # Update students_df status and left_date
    status_list = []
    left_date_list = []
    for sid in students_df["id"].tolist():
        m = student_meta[sid]
        if m["dropped_out"]:
            if m["dropout_reason"] == "switched_institute":
                status_list.append("transferred")
            else:
                status_list.append("left")
            left_date_list.append(m["dropout_date"])
        else:
            status_list.append("active")
            left_date_list.append(None)
    students_df["status"] = status_list
    students_df["left_date"] = left_date_list

    # 3. Generate true_theta_topic.parquet
    # To keep full preset fast (< 1 min) and well within < 400 MB while giving comprehensive coverage across
    # all syllabus topics and months, we select the student's target exam topics (or a representative subset of 24
    # core syllabus topics per exam across 6 bimonthly checkpoints: months 1, 3, 5, 7, 9, 12) and store the
    # full lookup dictionary in student_meta for fast response simulation.
    theta_rows: list[dict[str, Any]] = []
    months_tracked = [1, 3, 5, 7, 9, 12]

    # Select 24 core topics per exam (covering all chapters) for the parquet snapshot table,
    # while computing chapter-level residuals for all chapters so any question topic can be evaluated.
    core_topics_by_exam: dict[str, list[str]] = {}
    for ex, t_list in topics_by_exam.items():
        # Pick 1 topic per chapter up to 24 topics
        seen_ch: set[str] = set()
        picked: list[str] = []
        for tid in t_list:
            ch = topic_to_chapter[tid]
            if ch not in seen_ch:
                seen_ch.add(ch)
                picked.append(tid)
        core_topics_by_exam[ex] = picked[:25]

    lam = 0.72
    resid_sd = float(np.sqrt(max(0.05, 1.0 - lam * lam)))

    for sid in student_ids:
        m = student_meta[sid]
        g_val = m["true_g"]
        tau_val = m["risk_aversion_tau"]
        inst_id = m["institute_id"]
        ex = m["exam"]
        lr = m["learning_rate"]
        is_gradual = m["dropped_out"] and m["dropout_type"] == "gradual"
        fade_m = (
            max(1, int((m["fade_start_date"] - m["yr_start"]).days // 30) + 1)
            if (is_gradual and m["fade_start_date"] is not None)
            else 99
        )

        # Sample correlated chapter residuals following topic_prereqs DAG
        ch_resid: dict[str, float] = {}
        for ch in all_chapters:
            preds = chapter_prereqs.get(ch, [])
            if preds and any(p in ch_resid for p in preds):
                parent_mean = float(np.mean([ch_resid[p] for p in preds if p in ch_resid]))
                ch_resid[ch] = 0.5 * parent_mean + float(rng_traits.normal(0.0, resid_sd * 0.86))
            else:
                ch_resid[ch] = float(rng_traits.normal(0.0, resid_sd))
        m["chapter_resid"] = ch_resid

        # Store per-topic initial theta for all exam topics
        topic_init: dict[str, float] = {}
        for tid in topics_by_exam[ex]:
            ch = topic_to_chapter[tid]
            eps = 0.75 * ch_resid.get(ch, 0.0) + float(rng_traits.normal(0.0, 0.28))
            topic_init[tid] = lam * g_val + eps + topic_base_offset.get(tid, 0.0)
        m["topic_init_theta"] = topic_init

        for tid in core_topics_by_exam[ex]:
            base_th = topic_init[tid]
            for m_idx in months_tracked:
                growth = lr * (m_idx - 1) * (0.6 + 0.6 * m["base_attendance"])
                fade_dip = -0.35 * max(0, m_idx - fade_m + 1) if m_idx >= fade_m else 0.0
                th_m = base_th + growth + fade_dip
                theta_rows.append(
                    {
                        "student_id": sid,
                        "institute_id": inst_id,
                        "topic_id": tid,
                        "month_index": m_idx,
                        "true_g": g_val,
                        "true_theta": float(th_m),
                        "risk_aversion_tau": tau_val,
                    }
                )

    return (
        students_df,
        pd.DataFrame(theta_rows),
        pd.DataFrame(dropout_rows),
    )
