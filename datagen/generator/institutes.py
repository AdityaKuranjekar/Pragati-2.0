"""Step 1: Generate institutes, batches, students, and guardians."""

from __future__ import annotations

import datetime
from typing import Any

import numpy as np
import pandas as pd

from .synthetic_names import (
    FEMALE_FIRST_NAMES,
    GUARDIAN_FIRST_NAMES,
    MALE_FIRST_NAMES,
    SYNTHETIC_SURNAMES,
    make_synthetic_phone,
)
from .utils import DAY_MAP, EXAM_FOCUS_MAP, TIER_MAP, det_uuid

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

COUNSELLOR_NAMES = [
    "Dr. Meera Test",
    "Dr. Rajesh Sample",
    "Dr. Sunita Demo",
    "Dr. Anil Synth",
]


def generate_institutes_batches_students(
    cfg: dict[str, Any],
    rng: np.random.Generator,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Generate institutes, batches, students, guardians, and auxiliary student metadata."""
    inst_rows: list[dict[str, Any]] = []
    batch_rows: list[dict[str, Any]] = []
    student_rows: list[dict[str, Any]] = []
    guardian_rows: list[dict[str, Any]] = []
    student_meta: dict[str, dict[str, Any]] = {}

    off_day = DAY_MAP[cfg["tests"]["weekly_off_day"].lower()]
    academic_years: list[int] = sorted(int(y) for y in cfg["academic_years"])
    class_mix = cfg["students"]["class_mix"]
    classes = ["class_11", "class_12", "dropper"]
    class_probs = np.array([class_mix["class_11"], class_mix["class_12"], class_mix["dropper"]], dtype=float)
    class_probs = class_probs / class_probs.sum()

    b_min, b_max = cfg["students"]["batch_size"]
    target_b_size = int(round((b_min + b_max) / 2.0))
    out_of_town_p = float(cfg["students"].get("out_of_town_share", 0.45))

    phone_counter = 1
    created_base = datetime.datetime(2024, 4, 1, 9, 0, 0, tzinfo=IST)

    for idx_inst, inst_cfg in enumerate(cfg["institutes"]):
        inst_key = inst_cfg["id"]
        inst_id = det_uuid("institute", inst_key)
        city = inst_cfg["city"]
        city_tier = TIER_MAP[int(inst_cfg["tier"])]
        exam_focus = EXAM_FOCUS_MAP[inst_cfg["exam"]]
        plan = "pro" if int(inst_cfg["students"]) >= 1000 else ("standard" if int(inst_cfg["students"]) >= 300 else "starter")

        inst_rows.append(
            {
                "id": inst_id,
                "name": f"{city} {inst_cfg['exam']} Coaching Centre (Synthetic)",
                "city": city,
                "city_tier": city_tier,
                "exam_focus": exam_focus,
                "plan": plan,
                "weekly_off_day": off_day,
                "counsellor_name": COUNSELLOR_NAMES[idx_inst % len(COUNSELLOR_NAMES)],
                "counsellor_contact": f"+91-{make_synthetic_phone(9000 + idx_inst)}",
                "created_at": created_base,
            }
        )

        n_students_total = int(inst_cfg["students"])
        prefix = inst_key[:3].upper()

        # Cohort sizes: see cfg['cohort_size_mode'] (per_year default; total_split = legacy 10/25/65 split).
        mode = cfg.get("cohort_size_mode", "per_year")
        yr_counts: dict[int, int] = {}
        if mode == "per_year":
            # configured size = size of EACH academic-year cohort
            for yr in academic_years:
                yr_counts[yr] = max(30, n_students_total)
        elif mode == "total_split":
            if len(academic_years) == 3:
                yr_shares = [0.10, 0.25, 0.65]
            elif len(academic_years) == 2:
                yr_shares = [0.30, 0.70]
            else:
                yr_shares = [1.0 / len(academic_years)] * len(academic_years)
            rem_students = n_students_total
            for idx_y, yr in enumerate(academic_years):
                if idx_y < len(academic_years) - 1:
                    c_y = max(30, int(round(n_students_total * yr_shares[idx_y])))
                    yr_counts[yr] = c_y
                    rem_students -= c_y
                else:
                    yr_counts[yr] = max(30, rem_students)
        else:
            raise ValueError(f"Unknown cohort_size_mode '{mode}'")

        # Track some class_11 students who transition to class_12 next year (same student_key in truth)
        prev_year_c11_keys: list[dict[str, Any]] = []

        for yr in academic_years:
            n_students_per_yr = yr_counts[yr]
            yr_start = datetime.date(yr, 4, 15)
            yr_created = datetime.datetime(yr, 4, 1, 9, 0, 0, tzinfo=IST)

            # Determine exact class counts to stay close to 30/30/40
            n_c11 = int(round(n_students_per_yr * class_probs[0]))
            n_c12 = int(round(n_students_per_yr * class_probs[1]))
            n_drop = n_students_per_yr - n_c11 - n_c12
            class_counts = {"class_11": n_c11, "class_12": n_c12, "dropper": n_drop}

            # Create batches per class_level by admission order (never performance)
            batches_for_class: dict[str, list[dict[str, Any]]] = {}
            for c_level in classes:
                cnt = class_counts[c_level]
                n_batches = max(1, int(round(cnt / max(20, target_b_size))))
                batches_for_class[c_level] = []
                for b_idx in range(n_batches):
                    if exam_focus == "mix":
                        b_exam = "jee_main" if (b_idx % 2 == 0) else "neet_ug"
                    else:
                        b_exam = exam_focus
                    b_name = f"{b_exam.upper()[:3]}-{c_level.replace('class_', '')}-{yr}-B{b_idx + 1}"
                    b_id = det_uuid("batch", inst_key, yr, b_name)
                    pub_cap = max(b_max, int(np.ceil(cnt / n_batches)) + 5)
                    mentor_cap = max(2, int(round((cnt / n_batches) * 0.06)))
                    b_row = {
                        "id": b_id,
                        "institute_id": inst_id,
                        "name": b_name,
                        "class_level": c_level,
                        "exam": b_exam,
                        "academic_year": yr,
                        "start_date": yr_start,
                        "published_capacity": pub_cap,
                        "mentor_capacity_per_week": mentor_cap,
                        "created_at": yr_created,
                    }
                    batch_rows.append(b_row)
                    batches_for_class[c_level].append(b_row)

            # Build ordered student list by admission order
            student_idx_in_yr = 0
            new_c11_keys: list[dict[str, Any]] = []

            for c_level in classes:
                cnt = class_counts[c_level]
                b_list = batches_for_class[c_level]
                for s_i in range(cnt):
                    student_idx_in_yr += 1
                    # Reused roll_no across years: Ensure first 5 roll_nos use year-agnostic format like PAT-R001
                    if student_idx_in_yr <= 5:
                        roll_no = f"{prefix}-R{student_idx_in_yr:03d}"
                    else:
                        roll_no = f"{prefix}{str(yr)[2:]}-{student_idx_in_yr:04d}"

                    batch_assigned = b_list[s_i % len(b_list)]
                    b_id = batch_assigned["id"]
                    b_exam = batch_assigned["exam"]

                    # Check if this is a class 11 -> 12 transition student from previous cohort year
                    transition_from = None
                    if c_level == "class_12" and prev_year_c11_keys and s_i < min(10, len(prev_year_c11_keys)):
                        transition_from = prev_year_c11_keys[s_i]

                    if transition_from is not None:
                        gender = transition_from["gender"]
                        name_en = transition_from["name"]
                        name_hi = transition_from["name_alt"]
                        dob = transition_from["dob"]
                        student_key = transition_from["student_key"]
                        out_of_town = transition_from["out_of_town"]
                        fee_plan = transition_from["fee_plan"]
                        g_latent = transition_from["preset_g"]
                    else:
                        p_female = 0.55 if b_exam == "neet_ug" else 0.30
                        r_gen = float(rng.random())
                        if r_gen < p_female:
                            gender = "female"
                        elif r_gen < 0.985:
                            gender = "male"
                        else:
                            gender = "other"

                        sur_en, sur_hi = SYNTHETIC_SURNAMES[int(rng.integers(0, len(SYNTHETIC_SURNAMES)))]
                        if gender == "female":
                            fn_en, fn_hi = FEMALE_FIRST_NAMES[int(rng.integers(0, len(FEMALE_FIRST_NAMES)))]
                        else:
                            fn_en, fn_hi = MALE_FIRST_NAMES[int(rng.integers(0, len(MALE_FIRST_NAMES)))]
                        name_en = f"{fn_en} {sur_en}"
                        name_hi = f"{fn_hi} {sur_hi}"
                        student_key = f"{inst_key}_{yr}_{student_idx_in_yr}"
                        g_latent = None

                        # Join date: 94% within first 10 days of April 15; 6% mid-year joiners (May-July)
                        if rng.random() < 0.06:
                            join_offset = int(rng.integers(25, 90))
                        else:
                            join_offset = int(rng.integers(0, 10))
                        join_date = yr_start + datetime.timedelta(days=join_offset)

                        # Age at enrolment >= 16 (MoE 2024 cl. 6(i))
                        # Also ensure class 11/12/early-dropper DOBs are calibrated so overall minor share (< 18 at as_of 2026-10-01) >= 55%
                        # while every student is strictly >= 16.0 years old on their join_date!
                        if yr == 2025 and c_level in ("class_11", "class_12"):
                            # Born between Oct 15 2008 and Apr 10 2009 -> age 16.0..16.5 at Apr 2025 join_date, and 17.5..17.95 (< 18) on 2026-10-01!
                            dob_start = datetime.date(2008, 10, 15)
                            dob = dob_start + datetime.timedelta(days=int(rng.integers(0, 175)))
                        elif c_level == "class_11":
                            # Age 16.0 to 16.4 at join_date
                            age_days = int(rng.integers(16 * 365 + 10, 16 * 365 + 140))
                            dob = join_date - datetime.timedelta(days=age_days)
                        elif c_level == "class_12":
                            if rng.random() < 0.16:
                                # Turns 18 mid-year (between May and Sep of yr) -> triggers adult self-consent re-collection
                                bday_offset = int(rng.integers(25, 150))
                                bday_18 = yr_start + datetime.timedelta(days=bday_offset)
                                dob = datetime.date(bday_18.year - 18, bday_18.month, min(28, bday_18.day))
                            else:
                                # Age 16.3 to 16.8 at join_date
                                age_days = int(rng.integers(16 * 365 + 110, 16 * 365 + 290))
                                dob = join_date - datetime.timedelta(days=age_days)
                        else:
                            # Dropper: ~45% early-entry droppers (age 16.6-17.3 at join_date), ~55% 18-19 yrs
                            if rng.random() < 0.45:
                                age_days = int(rng.integers(16 * 365 + 220, 17 * 365 + 110))
                            else:
                                age_days = int(rng.integers(18 * 365 + 10, 19 * 365 + 200))
                            dob = join_date - datetime.timedelta(days=age_days)

                        # Enforce minimum age >= 16 on join_date
                        sixteenth_bday = datetime.date(dob.year + 16, dob.month, min(28, dob.day))
                        if join_date < sixteenth_bday:
                            dob = datetime.date(join_date.year - 16, join_date.month, min(28, join_date.day))

                        out_of_town = bool(rng.random() < out_of_town_p)

                        # Fee plan selection
                        upfront_p = float(cfg["fees"]["upfront_share"])
                        r_fee = float(rng.random())
                        if city == "Kota":
                            # Include rajasthan_4_equal for Kota (Rajasthan Act s.6(2)(d))
                            if r_fee < upfront_p:
                                fee_plan = "upfront_full"
                            elif r_fee < upfront_p + 0.50:
                                fee_plan = "rajasthan_4_equal"
                            elif r_fee < 0.93:
                                fee_plan = "standard_3_instalment"
                            else:
                                fee_plan = "custom_scholarship"
                        else:
                            if r_fee < upfront_p:
                                fee_plan = "upfront_full"
                            elif r_fee < 0.85:
                                fee_plan = "standard_3_instalment"
                            elif r_fee < 0.93:
                                fee_plan = "rajasthan_4_equal"
                            else:
                                fee_plan = "custom_scholarship"

                    if transition_from is not None:
                        join_date = yr_start + datetime.timedelta(days=int(rng.integers(0, 5)))

                    stud_id = det_uuid("student", inst_key, yr, roll_no)
                    stud_created = datetime.datetime.combine(
                        join_date, datetime.time(10, 0), tzinfo=IST
                    )

                    s_row = {
                        "id": stud_id,
                        "institute_id": inst_id,
                        "batch_id": b_id,
                        "academic_year": yr,
                        "roll_no": roll_no,
                        "name": name_en,
                        "name_alt": name_hi,
                        "dob": dob,
                        "gender": gender,
                        "join_date": join_date,
                        "status": "active",
                        "left_date": None,
                        "fee_plan": fee_plan,
                        "out_of_town": out_of_town,
                        "created_at": stud_created,
                    }
                    student_rows.append(s_row)

                    # Guardian row (shared phone across occasional siblings ~ 4%)
                    if rng.random() < 0.04 and phone_counter > 2:
                        g_phone = make_synthetic_phone(phone_counter - 1)
                    else:
                        g_phone = make_synthetic_phone(phone_counter)
                        phone_counter += 1

                    g_fn_en, _, g_rel = GUARDIAN_FIRST_NAMES[int(rng.integers(0, len(GUARDIAN_FIRST_NAMES)))]
                    sur_part = name_en.split()[-1]
                    g_id = det_uuid("guardian", stud_id)
                    g_lang = "hi" if (city in ("Patna", "Lucknow", "Gaya") and rng.random() < 0.65) else ("hi" if rng.random() < 0.45 else "en")

                    guardian_rows.append(
                        {
                            "id": g_id,
                            "institute_id": inst_id,
                            "student_id": stud_id,
                            "name": f"{g_fn_en} {sur_part}",
                            "phone": g_phone,
                            "relation": g_rel,
                            "lang_pref": g_lang,
                            "created_at": stud_created,
                        }
                    )

                    # Check non-performance batch change metadata (used in edge cases)
                    changed_batch_info = None
                    if len(b_list) > 1 and rng.random() < float(cfg["students"]["batch_change_rate"]):
                        alt_b = b_list[(s_i + 1) % len(b_list)]
                        changed_batch_info = {
                            "from_batch": b_id,
                            "to_batch": alt_b["id"],
                            "change_date": yr_start + datetime.timedelta(days=int(rng.integers(30, 90))),
                            "reason": str(rng.choice(["timing", "subject_change", "relocation", "other"])),
                        }

                    meta_entry = {
                        "student_id": stud_id,
                        "student_key": student_key,
                        "name": name_en,
                        "name_alt": name_hi,
                        "gender": gender,
                        "institute_id": inst_id,
                        "institute_key": inst_key,
                        "city": city,
                        "city_tier": city_tier,
                        "batch_id": b_id,
                        "class_level": c_level,
                        "exam": b_exam,
                        "academic_year": yr,
                        "yr_start": yr_start,
                        "dob": dob,
                        "join_date": join_date,
                        "out_of_town": out_of_town,
                        "fee_plan": fee_plan,
                        "guardian_id": g_id,
                        "guardian_lang": g_lang,
                        "preset_g": g_latent if g_latent is not None else float(rng.normal(0.0, 1.0)),
                        "batch_change": changed_batch_info,
                    }
                    student_meta[stud_id] = meta_entry
                    if c_level == "class_11":
                        new_c11_keys.append(meta_entry)

            prev_year_c11_keys = new_c11_keys

    return (
        pd.DataFrame(inst_rows),
        pd.DataFrame(batch_rows),
        pd.DataFrame(student_rows),
        pd.DataFrame(guardian_rows),
        student_meta,
    )
