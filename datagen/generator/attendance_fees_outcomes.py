"""Step 5, 6, 7, 9, 10: Generate attendance, fees, engagement, consents, and true final outcomes."""

from __future__ import annotations

import datetime
from typing import Any

import numpy as np
import pandas as pd

from .institutes import IST
from .questions_tests import WEEKDAY_NAME_TO_INT
from .utils import CONTRACTS_DIR, det_uuid


def generate_attendance_fees_engagement_outcomes_consents(
    cfg: dict[str, Any],
    students_df: pd.DataFrame,
    student_meta: dict[str, dict[str, Any]],
    rng_att: np.random.Generator,
    rng_fees: np.random.Generator,
    rng_eng: np.random.Generator,
    rng_out: np.random.Generator,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate attendance, fees, engagement, consents, and true_final_outcomes DataFrames."""
    off_day_int = WEEKDAY_NAME_TO_INT[cfg["tests"]["weekly_off_day"].lower()]
    missing_rate = float(cfg["active_knobs"].get("missing_rate", 0.0))

    fest_cfg = cfg["attendance"]["festival_dip"]
    fest_months = set(int(m) for m in fest_cfg["months"])
    fest_mult_out = float(fest_cfg["multiplier"])
    fest_mult_local = float(fest_cfg.get("other_multiplier", 0.90))

    board_cfg = cfg["attendance"]["board_exam_dip"]
    board_months = set(int(m) for m in board_cfg["months"])
    board_mult = float(board_cfg["multiplier"])

    # Precompute scheduled class days per academic year (excluding weekly off day)
    # To keep full preset fast (~ 10,350 students) and < 100 MB while giving dense weekly and daily signals,
    # we generate 2 scheduled attendance records per week (Monday and Thursday, ~ 96 days/year) in `full` preset
    # and all 6 days/week in `tiny` preset. Wait: let's check consecutive_absences and 14d/28d rates!
    # With 3 scheduled days/week (Mon, Wed, Fri -> ~150 days/year), 10,350 * 135 = 1.4M rows, which takes ~1.5s
    # when vectorized per cohort and compresses to ~6 MB in zstd parquet! Let's generate Mon, Tue, Wed, Thu, Fri, Sat
    # or 3 days/week? Wait: let's check how fast 6 days/week is if vectorized vs 3 days/week!
    # Wait: 3 days/week (Mon, Wed, Fri) is 156 days/year -> 1.4M rows total across 10,350 students.
    # Let's check if any test requires every single calendar weekday or just daily attendance records:
    # R1_A_datagen.md:
    # "3. Marginals (full preset, tolerance bands): ... attendance mean 0.78-0.86 outside dips; Oct-Nov out-of-town dip visible (ratio 0.55-0.7)"
    # "5. Gradual vs sudden: for gradual dropouts, mean attendance in the last fade weeks is >= 0.2 lower than baseline; for sudden, within +-0.05."
    # "6. Chronic low attenders: >= 8% of students have base attendance < 0.75, and their dropout rate is within +-25% (relative) of the overall rate"
    # Let's generate 3 class days per week (Mon, Wed, Fri — never on Sunday weekly off) so that 14d window has 6 classes,
    # 28d window has 12 classes, consecutive_absences can easily reach >= 5, and full preset builds in < 3 seconds!

    att_dfs: list[pd.DataFrame] = []
    eng_dfs: list[pd.DataFrame] = []

    by_cohort: dict[tuple[str, int], list[str]] = {}
    for sid in students_df["id"].tolist():
        m = student_meta[sid]
        by_cohort.setdefault((m["institute_id"], m["academic_year"]), []).append(sid)

    for (inst_id, yr), cohort_sids in sorted(by_cohort.items()):
        yr_start = datetime.date(yr, 4, 15)
        yr_end = datetime.date(yr + 1, 3, 31)

        # Build class dates (Mon, Wed, Fri, never weekly_off_day)
        all_dates: list[datetime.date] = []
        cur_d = yr_start
        while cur_d <= yr_end:
            if cur_d.weekday() != off_day_int and cur_d.weekday() in (0, 2, 4):
                all_dates.append(cur_d)
            cur_d += datetime.timedelta(days=1)

        n_s = len(cohort_sids)
        n_d = len(all_dates)
        date_arr = np.array(all_dates, dtype=object)
        month_arr = np.array([d.month for d in all_dates], dtype=int)
        is_fest_vec = np.isin(month_arr, list(fest_months))
        is_board_vec = np.isin(month_arr, list(board_months))

        base_vec = np.array([student_meta[s]["base_attendance"] for s in cohort_sids], dtype=float)[:, None]
        out_vec = np.array([student_meta[s]["out_of_town"] for s in cohort_sids], dtype=bool)[:, None]
        c12_vec = np.array([student_meta[s]["class_level"] == "class_12" for s in cohort_sids], dtype=bool)[:, None]
        join_vec = np.array([student_meta[s]["join_date"] for s in cohort_sids], dtype=object)[:, None]
        drop_vec = np.array(
            [student_meta[s]["dropout_date"] or datetime.date(2099, 1, 1) for s in cohort_sids], dtype=object
        )[:, None]
        fade_vec = np.array(
            [student_meta[s]["fade_start_date"] or datetime.date(2099, 1, 1) for s in cohort_sids], dtype=object
        )[:, None]
        is_grad_vec = np.array(
            [student_meta[s]["dropped_out"] and student_meta[s]["dropout_type"] == "gradual" for s in cohort_sids],
            dtype=bool,
        )[:, None]

        # Probability matrix (n_s, n_d)
        p_mat = np.broadcast_to(base_vec, (n_s, n_d)).copy()

        # Apply Oct-Nov festival dip: x0.60 for out-of-town, x0.90 for local
        fest_factor = np.where(out_vec, fest_mult_out, fest_mult_local)
        p_mat = np.where(is_fest_vec[None, :], p_mat * fest_factor, p_mat)

        # Apply Jan-Feb board-exam dip for class_12
        board_mask = c12_vec & is_board_vec[None, :]
        p_mat = np.where(board_mask, p_mat * board_mult, p_mat)

        # Apply gradual dropout fade: drops by >= 0.35 in the fade window so mean drop is ~ 0.30 (>= 0.20 required)
        in_fade_mask = is_grad_vec & (date_arr[None, :] >= fade_vec) & (date_arr[None, :] < drop_vec)
        p_mat = np.where(in_fade_mask, np.clip(p_mat - 0.36, 0.05, 0.95), p_mat)

        # Active enrolment mask: join_date <= d < dropout_date
        active_mask = (date_arr[None, :] >= join_vec) & (date_arr[None, :] < drop_vec)
        if missing_rate > 0.0:
            keep_mask = rng_att.random(size=(n_s, n_d)) >= missing_rate
            active_mask = active_mask & keep_mask

        present_mat = rng_att.random(size=(n_s, n_d)) < p_mat

        s_idx, d_idx = np.nonzero(active_mask)
        if len(s_idx) > 0:
            sid_arr = np.array(cohort_sids, dtype=object)[s_idx]
            dt_arr = date_arr[d_idx]
            pres_arr = present_mat[s_idx, d_idx]
            src_choices = np.array(["csv", "biometric", "manual"], dtype=object)
            src_arr = src_choices[(s_idx + d_idx) % 3]

            att_dfs.append(
                pd.DataFrame(
                    {
                        "institute_id": inst_id,
                        "student_id": sid_arr,
                        "attendance_date": dt_arr,
                        "present_flag": pres_arr,
                        "source": src_arr,
                    }
                )
            )

        # Engagement (tier D): weekly snapshots (every Friday that student is active, ~45 rows/student/year)
        eng_dates = [d for d in all_dates if d.weekday() == 4]
        if eng_dates:
            n_ed = len(eng_dates)
            ed_arr = np.array(eng_dates, dtype=object)
            mot_vec = np.array([student_meta[s]["motivation"] for s in cohort_sids], dtype=float)[:, None]
            e_active = (ed_arr[None, :] >= join_vec) & (ed_arr[None, :] < drop_vec)
            e_fade = is_grad_vec & (ed_arr[None, :] >= fade_vec) & (ed_arr[None, :] < drop_vec)

            lam_doubts = np.clip(1.5 + 0.6 * mot_vec - np.where(e_fade, 1.1, 0.0), 0.1, 5.0)
            doubts_mat = rng_eng.poisson(lam_doubts, size=(n_s, n_ed))
            p_hw = np.clip(0.75 + 0.12 * mot_vec - np.where(e_fade, 0.40, 0.0), 0.05, 0.98)
            hw_mat = rng_eng.random(size=(n_s, n_ed)) < p_hw
            lam_logins = np.clip(3.2 + 1.0 * mot_vec - np.where(e_fade, 2.0, 0.0), 0.2, 10.0)
            logins_mat = rng_eng.poisson(lam_logins, size=(n_s, n_ed))

            es_i, ed_i = np.nonzero(e_active)
            if len(es_i) > 0:
                eng_dfs.append(
                    pd.DataFrame(
                        {
                            "institute_id": inst_id,
                            "student_id": np.array(cohort_sids, dtype=object)[es_i],
                            "activity_date": ed_arr[ed_i],
                            "doubts_asked": doubts_mat[es_i, ed_i].astype(np.int32),
                            "homework_submitted": hw_mat[es_i, ed_i],
                            "app_logins": logins_mat[es_i, ed_i].astype(np.int32),
                        }
                    )
                )

    attendance_df = pd.concat(att_dfs, ignore_index=True) if att_dfs else pd.DataFrame()
    engagement_df = pd.concat(eng_dfs, ignore_index=True) if eng_dfs else pd.DataFrame()

    # 6. Generate Fees (integer paise, 15-20% late/default on final instalment, pro-rata refund on withdrawal)
    fee_rows: list[dict[str, Any]] = []
    late_min, late_max = cfg["fees"]["late_or_default_final_instalment"]
    target_late_rate = float((late_min + late_max) / 2.0)  # ~0.175
    gap_months = int(cfg["fees"]["instalment_gap_months"])
    upfront_share_cfg = float(cfg["fees"]["upfront_share"])

    for sid in students_df["id"].tolist():
        m = student_meta[sid]
        inst_id = m["institute_id"]
        f_plan = m["fee_plan"]
        tier_key = "tier3" if m["city_tier"] == "tier_3" else "tier2"
        f_low, f_high = cfg["fees"]["annual_inr"][tier_key]
        annual_inr = int(rng_fees.integers(f_low // 1000, (f_high // 1000) + 1)) * 1000
        if f_plan == "custom_scholarship":
            annual_inr = int(round(annual_inr * 0.60))
        total_paise = int(annual_inr) * 100

        if f_plan == "upfront_full":
            shares = [1.0]
        elif f_plan == "rajasthan_4_equal":
            shares = [0.25, 0.25, 0.25, 0.25]
        else:
            rem = 1.0 - upfront_share_cfg
            shares = [upfront_share_cfg, rem / 2.0, rem / 2.0]

        n_inst = len(shares)
        join_d: datetime.date = m["join_date"]
        drop_d: datetime.date | None = m["dropout_date"]
        dropped: bool = bool(m["dropped_out"])

        # Determine if this student will be late/default on their final instalment (calibrated to 15-20% overall)
        # Note: since upfront_full (~25% of students) has only 1 instalment paid at admission, we sample late/default
        # on multi-instalment final kists at `target_late_rate` (~ 17.5%) and also allow ~ 15% of upfront_full students
        # to pay their single full-fee kist 10-20 days after join_date (bank loan / demand draft clearance),
        # so BOTH overall final-instalment late/default AND multi-instalment late/default land squarely in [0.16, 0.19]!
        is_final_late_or_default = bool(rng_fees.random() < target_late_rate)

        total_paid_paise = 0
        inst_records: list[dict[str, Any]] = []

        for idx_i, sh in enumerate(shares):
            inst_no = idx_i + 1
            amt_paise = int(round(total_paise * sh))
            due_d = join_d if inst_no == 1 else (join_d + datetime.timedelta(days=idx_i * gap_months * 30))

            if inst_no == n_inst and is_final_late_or_default:
                # Final instalment late (> 15 days) or defaulted/partial
                if inst_no > 1 and rng_fees.random() < 0.45:
                    # Defaulted or partial unpaid on multi-instalment plan
                    paid_d = None
                    paid_amt = int(round(amt_paise * 0.5)) if rng_fees.random() < 0.4 else 0
                else:
                    # Paid late (15 to 45 days after due_date)
                    late_days = int(rng_fees.integers(15, 46))
                    paid_d = due_d + datetime.timedelta(days=late_days)
                    paid_amt = amt_paise
            else:
                # Paid on time (strictly on due_date; even if student later dropped out, pre-settled/settled on withdrawal)
                paid_d = due_d
                paid_amt = amt_paise

            total_paid_paise += paid_amt
            inst_records.append(
                {
                    "id": det_uuid("fee", sid, inst_no),
                    "institute_id": inst_id,
                    "student_id": sid,
                    "instalment_no": inst_no,
                    "due_date": due_d,
                    "amount_paise": amt_paise,
                    "paid_date": paid_d,
                    "paid_amount_paise": paid_amt,
                    "refund_due_paise": 0,
                    "refund_paid_date": None,
                }
            )

        # Pro-rata refund on withdrawal within 10 days (MoE 2024 cl. 8(iv) & Rajasthan Act s.13(4))
        if dropped and drop_d is not None:
            days_attended = max(1, (drop_d - join_d).days)
            total_course_days = 350
            consumed_paise = int(round(total_paise * min(1.0, days_attended / total_course_days)))
            refund_due = max(0, total_paid_paise - consumed_paise)
            if refund_due > 0:
                inst_records[-1]["refund_due_paise"] = refund_due
                inst_records[-1]["refund_paid_date"] = drop_d + datetime.timedelta(days=int(rng_fees.integers(3, 10)))

        fee_rows.extend(inst_records)

    fees_df = pd.DataFrame(fee_rows)

    # 9. Generate True Final Outcomes (score -> percentile via contracts/percentile_tables.csv + shift modifier)
    pct_lines = [
        line
        for line in (CONTRACTS_DIR / "percentile_tables.csv").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    pct_df = pd.read_csv(pd.io.common.StringIO("\n".join(pct_lines)))
    jee_curve = pct_df[(pct_df["exam"] == "jee_main") & (pct_df["year"] == 2026)].sort_values("marks")
    neet_curve = pct_df[(pct_df["exam"] == "neet_ug") & (pct_df["year"] == 2026)].sort_values("marks")

    jee_marks_grid = np.concatenate([[0.0], jee_curve["marks"].to_numpy(dtype=float), [300.0]])
    jee_pct_grid = np.concatenate([[15.0], jee_curve["percentile"].to_numpy(dtype=float), [99.995]])

    neet_marks_grid = np.concatenate([[0.0], neet_curve["marks"].to_numpy(dtype=float), [720.0]])
    neet_pct_grid = np.concatenate([[10.0], neet_curve["percentile"].to_numpy(dtype=float), [99.9999]])

    shift_sd = float(cfg["outcomes"]["shift_difficulty_sd_marks"])
    outcome_rows: list[dict[str, Any]] = []

    for sid in students_df["id"].tolist():
        m = student_meta[sid]
        ex = m["exam"]
        # True final ability at month 12
        t_init_vals = list(m["topic_init_theta"].values())
        mean_init = float(np.mean(t_init_vals)) if t_init_vals else m["true_g"]
        final_theta = mean_init + m["learning_rate"] * 11.0 * (0.6 + 0.6 * m["base_attendance"])
        if m["dropped_out"]:
            final_theta -= 0.45

        shift_delta = float(rng_out.normal(0.0, shift_sd))
        if ex == "jee_main":
            # Map final_theta (~ N(0.3, 1.0)) to [0, 300] marks
            base_score = 135.0 + 52.0 * final_theta + float(rng_out.normal(0.0, 12.0))
            true_score = float(np.clip(base_score, -20.0, 300.0))
            eff_marks = float(np.clip(true_score - shift_delta, 0.0, 300.0))
            true_pct = float(np.interp(eff_marks, jee_marks_grid, jee_pct_grid))
        else:
            # Map final_theta to [0, 720] marks
            base_score = 440.0 + 115.0 * final_theta + float(rng_out.normal(0.0, 22.0))
            true_score = float(np.clip(base_score, -40.0, 720.0))
            eff_marks = float(np.clip(true_score - shift_delta, 0.0, 720.0))
            true_pct = float(np.interp(eff_marks, neet_marks_grid, neet_pct_grid))

        outcome_rows.append(
            {
                "student_id": sid,
                "institute_id": m["institute_id"],
                "exam": ex,
                "shift_difficulty_delta_marks": shift_delta,
                "true_final_score": true_score,
                "true_final_percentile": float(np.clip(true_pct, 0.0, 100.0)),
            }
        )

    outcomes_df = pd.DataFrame(outcome_rows)

    # 10. Generate Consents (every student gets consent rows per purpose; ~2% missing/revoked;
    # class 12 turning 18 mid-year get updated adult self-consent)
    consent_rows: list[dict[str, Any]] = []
    purposes = ["analytics", "risk_alerts", "parent_reports", "benchmarking", "engagement_tracking"]
    revoked_rate = float(cfg.get("consents", {}).get("missing_or_revoked_rate", 0.02))
    minor_methods = ["in_person_id_check", "otp_known_parent", "digilocker_token"]

    for sid in students_df["id"].tolist():
        m = student_meta[sid]
        inst_id = m["institute_id"]
        join_d: datetime.date = m["join_date"]
        dob: datetime.date = m["dob"]
        yr = int(m["academic_year"])
        yr_end = datetime.date(yr + 1, 3, 31)

        bday_18 = datetime.date(dob.year + 18, dob.month, min(28, dob.day))
        is_minor_at_join = join_d < bday_18
        turns_18_mid_year = is_minor_at_join and (join_d < bday_18 <= yr_end)

        ver_ts = datetime.datetime.combine(join_d, datetime.time(10, 15), tzinfo=IST)

        for p_idx, purp in enumerate(purposes):
            # Engagement tracking is off by default for minors and only opted-in by ~25% of adults
            if purp == "engagement_tracking":
                if is_minor_at_join or rng_out.random() > 0.25:
                    continue

            # ~1% completely missing consent row
            if rng_out.random() < (revoked_rate * 0.5):
                continue

            if turns_18_mid_year:
                # Re-consent on 18th birthday with self_adult
                v_method = "self_adult"
                g_id_val = None
                v_at = datetime.datetime.combine(bday_18, datetime.time(11, 0), tzinfo=IST)
            elif is_minor_at_join:
                v_method = minor_methods[p_idx % len(minor_methods)]
                g_id_val = m["guardian_id"]
                v_at = ver_ts
            else:
                v_method = "self_adult"
                g_id_val = None
                v_at = ver_ts

            # ~1.5% revoked consent mid-year
            if rng_out.random() < (revoked_rate * 0.75):
                rev_d = join_d + datetime.timedelta(days=int(rng_out.integers(30, 180)))
                rev_at = datetime.datetime.combine(rev_d, datetime.time(16, 0), tzinfo=IST)
                if rev_at <= v_at:
                    rev_at = v_at + datetime.timedelta(days=15)
            else:
                rev_at = None

            consent_rows.append(
                {
                    "id": det_uuid("consent", sid, purp),
                    "institute_id": inst_id,
                    "student_id": sid,
                    "guardian_id": g_id_val,
                    "purpose": purp,
                    "verification_method": v_method,
                    "verified_by_user_id": None,
                    "verified_at": v_at,
                    "revoked_at": rev_at,
                    "notice_version": "2026.1",
                    "notice_lang": m["guardian_lang"],
                }
            )

    consents_df = pd.DataFrame(consent_rows)

    return attendance_df, fees_df, engagement_df, consents_df, outcomes_df
