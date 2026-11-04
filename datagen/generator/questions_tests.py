"""Steps 3 & 4: Generate question bank, tests, answer keys, responses, test totals, and calibrated item_params."""

from __future__ import annotations

import datetime
from typing import Any

import numpy as np
import pandas as pd

from .institutes import IST
from .utils import CONTRACTS_DIR, det_sha256, det_uuid, load_yaml

WEEKDAY_NAME_TO_INT = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def generate_questions_tests_responses(
    cfg: dict[str, Any],
    institutes_df: pd.DataFrame,
    batches_df: pd.DataFrame,
    students_df: pd.DataFrame,
    student_meta: dict[str, dict[str, Any]],
    leaf_topics: list[dict[str, Any]],
    topics_by_exam: dict[str, list[str]],
    rng_items: np.random.Generator,
    rng_resp: np.random.Generator,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    dict[str, Any],
]:
    """Generate questions, question_topics, item_params, tests, test_questions, answer_keys,
    responses, test_totals, true_item_params, and diagnostic calibration records.
    """
    exam_patterns = load_yaml(CONTRACTS_DIR / "exam_patterns.yaml")["patterns"]
    marking_schemes = load_yaml(CONTRACTS_DIR / "marking_schemes.yaml")["schemes"]

    # Map topic_id -> subject & topic difficulty mean
    topic_by_id = {t["id"]: t for t in leaf_topics}
    topics_by_subject_exam: dict[tuple[str, str], list[str]] = {}
    for t in leaf_topics:
        subj = t["subject"]
        for ex in t.get("exams", [t["exam"]]):
            topics_by_subject_exam.setdefault((ex, subj), []).append(t["id"])

    # Assign topic mean difficulty ~ N(0, 0.45)
    topic_b_mean = {
        t["id"]: float(rng_items.normal(0.0, 0.45)) for t in sorted(leaf_topics, key=lambda x: x["id"])
    }

    inst_ids = institutes_df["id"].tolist()
    created_base = datetime.datetime(2024, 4, 1, 10, 0, 0, tzinfo=IST)

    # 1. Build Question Pool:
    # ~35% shared pool (institute_id = None, used across >= 2 institutes as anchors)
    # ~65% tenant-private questions per institute
    wrong_key_rate = float(cfg["active_knobs"].get("wrong_key_rate", 0.015))
    marks_only_share = float(cfg["active_knobs"].get("marks_only_share", 0.0))
    online_test_share = float(cfg["active_knobs"].get("online_test_share", 0.15))
    neet_variant = str(cfg["active_knobs"].get("neet_variant", "compulsory_180"))

    questions_rows: list[dict[str, Any]] = []
    q_topics_rows: list[dict[str, Any]] = []
    true_item_rows: list[dict[str, Any]] = []
    q_meta: dict[str, dict[str, Any]] = {}

    def _create_question_item(
        q_key: str,
        inst_id: str | None,
        exam: str,
        subj: str,
        q_type: str,
        force_wrong_key: bool,
    ) -> str:
        qid = det_uuid("question", q_key)
        cand_topics = topics_by_subject_exam.get((exam, subj), topics_by_exam[exam])
        tid = str(rng_items.choice(cand_topics))
        t_mean = topic_b_mean[tid]

        # True 2PL parameters: a ~ LogN(0, 0.3), b ~ N(topic_mean, 1.0)
        true_a = float(np.clip(rng_items.lognormal(0.0, 0.30), 0.45, 2.5))
        if force_wrong_key:
            # Make wrong-key items moderately easy/discriminating so able students strongly pick true answer
            true_a = float(np.clip(rng_items.uniform(1.1, 1.8), 1.1, 1.8))
            true_b = float(rng_items.uniform(-0.8, 0.4))
        else:
            true_b = float(np.clip(rng_items.normal(t_mean, 0.95), -2.8, 2.8))

        if q_type == "numeric":
            true_g = 0.0
            options_n = 0
            true_ans = str(int(rng_items.integers(1, 95)))
            keyed_ans = [str(int(true_ans) + 15)] if force_wrong_key else [true_ans]
        elif q_type == "mcq_multi":
            true_g = float(rng_items.beta(2.0, 18.0))
            options_n = 4
            true_ans = "A|C"
            keyed_ans = ["B"] if force_wrong_key else ["A", "C"]
        else:
            true_g = float(rng_items.beta(2.0, 18.0))
            options_n = 4
            opts = ["A", "B", "C", "D"]
            true_ans = str(rng_items.choice(opts))
            if force_wrong_key:
                other_opts = [o for o in opts if o != true_ans]
                keyed_ans = [str(rng_items.choice(other_opts))]
            else:
                keyed_ans = [true_ans]

        questions_rows.append(
            {
                "id": qid,
                "institute_id": inst_id,
                "subject": subj,
                "text_hash": det_sha256(f"stem|{q_key}|{subj}|{tid}"),
                "q_type": q_type,
                "options_n": options_n,
                "created_at": created_base,
            }
        )
        q_topics_rows.append(
            {
                "institute_id": inst_id,
                "question_id": qid,
                "topic_id": tid,
                "weight": 1.0,
                "tagged_by": "human",
                "confidence": 1.0,
                "reviewed_by": None,
            }
        )
        true_item_rows.append(
            {
                "question_id": qid,
                "topic_id": tid,
                "true_a": true_a,
                "true_b": true_b,
                "true_g": true_g,
                "is_injected_wrong_key": bool(force_wrong_key),
                "true_correct_answer": true_ans,
            }
        )
        q_meta[qid] = {
            "question_id": qid,
            "institute_id": inst_id,
            "subject": subj,
            "topic_id": tid,
            "q_type": q_type,
            "options_n": options_n,
            "true_a": true_a,
            "true_b": true_b,
            "true_g": true_g,
            "is_injected_wrong_key": bool(force_wrong_key),
            "true_correct_answer": true_ans,
            "keyed_answers": keyed_ans,
        }
        return qid

    # Create shared question pool (~ 42% of total questions, used across >= 2 institutes as anchors)
    shared_pool: dict[tuple[str, str, str], list[str]] = {}
    all_q_specs: list[tuple[str, str | None, str, str, str]] = []

    for subj in ["Physics", "Chemistry", "Mathematics"]:
        for i in range(40):
            all_q_specs.append((f"shared_jee_{subj}_{i}", None, "jee_main", subj, "mcq_single"))
        for i in range(10):
            all_q_specs.append((f"shared_jee_num_{subj}_{i}", None, "jee_main", subj, "numeric"))
    for subj in ["Physics", "Chemistry", "Botany", "Zoology"]:
        for i in range(38):
            all_q_specs.append((f"shared_neet_{subj}_{i}", None, "neet_ug", subj, "mcq_single"))

    # Create private question pool per institute
    for _, inst_row in institutes_df.iterrows():
        inst_id = inst_row["id"]
        focus = inst_row["exam_focus"]
        exams_for_inst = ["jee_main", "neet_ug"] if focus == "mix" else [focus]
        for ex in exams_for_inst:
            subjs = ["Physics", "Chemistry", "Mathematics"] if ex == "jee_main" else ["Physics", "Chemistry", "Botany", "Zoology"]
            for subj in subjs:
                n_mcq = 14 if ex == "jee_main" else 16
                for i in range(n_mcq):
                    q_t = "mcq_multi" if (i == 0 and ex == "jee_main") else "mcq_single"
                    all_q_specs.append((f"priv_{inst_id[:8]}_{ex}_{subj}_{i}", inst_id, ex, subj, q_t))
                if ex == "jee_main":
                    for i in range(4):
                        all_q_specs.append((f"priv_num_{inst_id[:8]}_{ex}_{subj}_{i}", inst_id, ex, subj, "numeric"))

    total_items = len(all_q_specs)
    n_wrong_keys = max(2, int(round(total_items * wrong_key_rate)))
    # Pick wrong-key indices from MCQ single items so point-biserial flip is clear
    mcq_single_indices = [idx for idx, s in enumerate(all_q_specs) if s[4] == "mcq_single"]
    wrong_key_indices = set(
        rng_items.choice(mcq_single_indices, size=min(n_wrong_keys, len(mcq_single_indices)), replace=False).tolist()
    )

    pool_by_owner_exam_subj_type: dict[tuple[str | None, str, str, str], list[str]] = {}
    for idx, (q_key, owner_id, ex, subj, q_t) in enumerate(all_q_specs):
        is_wk = idx in wrong_key_indices
        qid = _create_question_item(q_key, owner_id, ex, subj, q_t, is_wk)
        bucket_type = "mcq" if q_t in ("mcq_single", "mcq_multi") else "numeric"
        pool_by_owner_exam_subj_type.setdefault((owner_id, ex, subj, bucket_type), []).append(qid)

    # 2. Schedule Tests per Batch
    # To achieve rich IRT sample sizes (>= 200 responses per item) while keeping runtime < 30s on full preset,
    # each batch runs 6 full-length mocks (every 2 months) and 6 chapter tests (20 questions each) across the year = 12 tests/year.
    tests_rows: list[dict[str, Any]] = []
    test_q_rows: list[dict[str, Any]] = []
    answer_key_rows: list[dict[str, Any]] = []
    responses_rows: list[dict[str, Any]] = []
    test_totals_rows: list[dict[str, Any]] = []

    off_day_int = WEEKDAY_NAME_TO_INT[cfg["tests"]["weekly_off_day"].lower()]
    day_after_off_int = (off_day_int + 1) % 7
    untaught_rate = float(cfg["tests"].get("untaught_topic_pair_rate", 0.03))

    # Group students by batch_id
    students_by_batch: dict[str, list[str]] = {}
    for sid, m in student_meta.items():
        students_by_batch.setdefault(m["batch_id"], []).append(sid)

    # Track item response statistics for clean/item_params.parquet and calibration check
    item_resp_tracker: dict[str, list[tuple[float, float]]] = {}  # qid -> list of (is_correct, student_total_score)
    calibration_samples: dict[str, list[tuple[float, int]]] = {}  # inst_id -> list of (p_true, is_correct)

    for _, b_row in batches_df.iterrows():
        b_id = b_row["id"]
        inst_id = b_row["institute_id"]
        b_exam = b_row["exam"]
        yr = int(b_row["academic_year"])
        yr_start: datetime.date = b_row["start_date"]
        b_students = students_by_batch.get(b_id, [])
        if not b_students:
            continue

        # Sample batch/teacher topic effects in [-0.3, +0.3] and ~3% untaught topics
        exam_topics = topics_by_exam[b_exam]
        batch_topic_effect: dict[str, float] = {}
        untaught_topics: set[str] = set()
        for tid in exam_topics:
            if rng_items.random() < untaught_rate:
                untaught_topics.add(tid)
                batch_topic_effect[tid] = -2.2  # untaught topic -> batch-wide failure
            else:
                batch_topic_effect[tid] = float(rng_items.uniform(-0.30, 0.30))

        # 12 scheduled tests across the 12 months (6 full mocks, 6 chapter tests)
        for t_idx in range(12):
            is_full_mock = (t_idx % 2 == 1)
            raw_date = yr_start + datetime.timedelta(days=18 + t_idx * 28)
            # Ensure never on weekly off day or day after weekly off day (MoE 2024 cl. 10.1(v)-(vi))
            while raw_date.weekday() in (off_day_int, day_after_off_int):
                raw_date += datetime.timedelta(days=1)
            t_date = raw_date
            m_idx = min(12, max(1, (t_date - yr_start).days // 30 + 1))

            if is_full_mock:
                if b_exam == "jee_main":
                    pat_code = "jee_main_2026"
                    m_scheme_id = "jee_main"
                    max_marks = 300.0
                    subjs = ["Physics", "Chemistry", "Mathematics"]
                    q_plan = [(s, "mcq", 20, "A") for s in subjs] + [(s, "numeric", 5, "B") for s in subjs]
                else:
                    pat_code = "neet_ug_2026"
                    m_scheme_id = "neet_ug"
                    max_marks = 720.0
                    subjs = ["Physics", "Chemistry", "Botany", "Zoology"]
                    if neet_variant == "sectioned_200":
                        q_plan = [(s, "mcq", 35, "A") for s in subjs] + [(s, "mcq", 10, "B") for s in subjs]
                    else:
                        q_plan = [(s, "mcq", 45, "A") for s in subjs]
                t_name = f"FT-{t_idx // 2 + 1:02d}-{b_exam.upper()[:3]}-{yr}"
            else:
                pat_code = "internal_chapter_test"
                m_scheme_id = "jee_main" if b_exam == "jee_main" else "neet_ug"
                subjs = ["Physics", "Chemistry", "Mathematics"] if b_exam == "jee_main" else ["Physics", "Chemistry", "Botany", "Zoology"]
                q_per_s = 7 if b_exam == "jee_main" else 5
                max_marks = float(len(subjs) * q_per_s * 4)
                q_plan = [(s, "mcq", q_per_s, "A") for s in subjs]
                t_name = f"CT-{t_idx // 2 + 1:02d}-{b_exam.upper()[:3]}-{yr}"

            r_src = float(rng_items.random())
            if r_src < online_test_share:
                t_source = "online"
            elif r_src < online_test_share + 0.45:
                t_source = "omr"
            else:
                t_source = "csv"

            is_marks_only_test = bool(rng_items.random() < marks_only_share) or (t_idx == 10 and marks_only_share == 0.0 and inst_id == inst_ids[-1])

            test_id = det_uuid("test", b_id, t_name)
            t_created = datetime.datetime.combine(t_date, datetime.time(18, 0), tzinfo=IST)

            tests_rows.append(
                {
                    "id": test_id,
                    "institute_id": inst_id,
                    "batch_id": b_id,
                    "name": t_name,
                    "test_date": t_date,
                    "exam_pattern_code": pat_code,
                    "marking_scheme_id": m_scheme_id,
                    "max_marks": max_marks,
                    "source": t_source,
                    "day_after_off_warning": False,
                    "created_at": t_created,
                }
            )

            # Select questions for this test (55% from shared pool across all batches so every shared item appears in >= 2 institutes)
            selected_qids: list[tuple[str, str, str]] = []  # (qid, section, subj)
            used_in_test: set[str] = set()
            for subj, bucket_t, count_q, sec in q_plan:
                sh_list = pool_by_owner_exam_subj_type.get((None, b_exam, subj, bucket_t), [])
                pr_list = pool_by_owner_exam_subj_type.get((inst_id, b_exam, subj, bucket_t), [])
                n_sh = min(len(sh_list), max(1, int(round(count_q * 0.55))))
                n_pr = count_q - n_sh

                avail_sh = [q for q in sh_list if q not in used_in_test]
                avail_pr = [q for q in pr_list if q not in used_in_test]

                # Deterministically rotate through the full shared pool across tests AND batches so 100% of shared items are used across >= 2 institutes
                if avail_sh:
                    k_sh = min(n_sh, len(avail_sh))
                    batch_rot_offset = sum(ord(c) for c in str(b_id)) % len(avail_sh)
                    start_rot = (batch_rot_offset + t_idx * k_sh) % len(avail_sh)
                    rotated_sh = avail_sh[start_rot:] + avail_sh[:start_rot]
                    picked_sh = rotated_sh[:k_sh]
                else:
                    picked_sh = []
                need_pr = count_q - len(picked_sh)
                picked_pr = (
                    rng_items.choice(avail_pr, size=min(need_pr, len(avail_pr)), replace=False).tolist()
                    if avail_pr and need_pr > 0
                    else []
                )
                combined = picked_sh + picked_pr
                # Top up if needed
                if len(combined) < count_q:
                    rem_pool = [q for q in (sh_list + pr_list) if q not in set(combined) and q not in used_in_test]
                    if rem_pool:
                        extra = rng_items.choice(
                            rem_pool, size=min(count_q - len(combined), len(rem_pool)), replace=False
                        ).tolist()
                        combined.extend(extra)

                for qid in combined:
                    used_in_test.add(qid)
                    selected_qids.append((qid, sec, subj))

            scheme = marking_schemes[m_scheme_id]
            c_marks = float(scheme["correct"])
            w_marks = float(scheme["wrong"])
            b_marks = float(scheme["blank"])

            # Record test_questions and answer_keys
            dropped_pos = 1 if (t_idx == 2 and len(selected_qids) >= 15) else -1
            for pos_0, (qid, sec, _) in enumerate(selected_qids):
                pos = pos_0 + 1
                qm = q_meta[qid]
                is_dropped = (pos == dropped_pos)
                test_q_rows.append(
                    {
                        "institute_id": inst_id,
                        "test_id": test_id,
                        "question_id": qid,
                        "position": pos,
                        "section": sec,
                    }
                )
                answer_key_rows.append(
                    {
                        "id": det_uuid("answer_key", test_id, qid, 1),
                        "institute_id": inst_id,
                        "test_id": test_id,
                        "question_id": qid,
                        "accepted_answers": list(qm["keyed_answers"]),
                        "numeric_tolerance": 0.1 if qm["q_type"] == "numeric" else 0.0,
                        "dropped": is_dropped,
                        "version": 1,
                        "created_by": None,
                        "created_at": t_created,
                    }
                )

            # Vectorized response simulation for all enrolled students in this batch
            active_sids = [
                sid
                for sid in b_students
                if student_meta[sid]["join_date"] <= t_date
                and (
                    not student_meta[sid]["dropped_out"]
                    or student_meta[sid]["dropout_date"] is None
                    or t_date < student_meta[sid]["dropout_date"]
                )
            ]
            if not active_sids:
                continue

            # Determine who is absent on test day
            absent_flags: list[bool] = []
            for sid in active_sids:
                m = student_meta[sid]
                p_present = m["base_attendance"]
                if (
                    m["dropped_out"]
                    and m["dropout_type"] == "gradual"
                    and m["fade_start_date"] is not None
                    and t_date >= m["fade_start_date"]
                ):
                    p_present *= 0.45
                # Test attendance is slightly higher than regular daily attendance
                p_test_present = min(0.98, p_present + 0.10)
                absent_flags.append(bool(rng_resp.random() > p_test_present))

            present_indices = [i for i, ab in enumerate(absent_flags) if not ab]
            absent_indices = [i for i, ab in enumerate(absent_flags) if ab]

            # Record absent students in test_totals
            for i_ab in absent_indices:
                sid = active_sids[i_ab]
                test_totals_rows.append(
                    {
                        "institute_id": inst_id,
                        "test_id": test_id,
                        "student_id": sid,
                        "raw_score": None,
                        "physics_score": None,
                        "chemistry_score": None,
                        "math_or_bio_score": None,
                        "absent_flag": True,
                    }
                )

            if not present_indices:
                continue

            present_sids = [active_sids[i] for i in present_indices]
            n_pres = len(present_sids)
            n_q = len(selected_qids)

            # Build matrices (n_pres, n_q)
            theta_mat = np.zeros((n_pres, n_q), dtype=float)
            tau_vec = np.array([student_meta[sid]["risk_aversion_tau"] for sid in present_sids], dtype=float)[:, None]

            a_vec = np.array([q_meta[qid]["true_a"] for qid, _, _ in selected_qids], dtype=float)[None, :]
            b_vec = np.array([q_meta[qid]["true_b"] for qid, _, _ in selected_qids], dtype=float)[None, :]
            g_vec = np.array([q_meta[qid]["true_g"] for qid, _, _ in selected_qids], dtype=float)[None, :]
            wk_vec = np.array([q_meta[qid]["is_injected_wrong_key"] for qid, _, _ in selected_qids], dtype=bool)
            q_topics = [q_meta[qid]["topic_id"] for qid, _, _ in selected_qids]
            bt_eff_vec = np.array([batch_topic_effect.get(tid, 0.0) for tid in q_topics], dtype=float)[None, :]

            # Position fatigue: slight dip towards the end of long papers
            fatigue_vec = np.linspace(0.0, -0.12 if n_q >= 75 else -0.04, n_q)[None, :]

            for row_i, sid in enumerate(present_sids):
                m = student_meta[sid]
                t_init = m["topic_init_theta"]
                lr = m["learning_rate"]
                growth = lr * (m_idx - 1) * (0.6 + 0.6 * m["base_attendance"])
                fade_dip = 0.0
                if (
                    m["dropped_out"]
                    and m["dropout_type"] == "gradual"
                    and m["fade_start_date"] is not None
                    and t_date >= m["fade_start_date"]
                ):
                    fade_dip = -0.55
                base_row = np.array([t_init.get(tid, m["true_g"]) for tid in q_topics], dtype=float)
                theta_mat[row_i, :] = base_row + growth + fade_dip

            eff_theta = theta_mat + bt_eff_vec + fatigue_vec
            logits = np.clip(a_vec * (eff_theta - b_vec), -15.0, 15.0)
            sig = 1.0 / (1.0 + np.exp(-logits))
            p_true_mat = g_vec + (1.0 - g_vec) * sig

            # MNAR Blanks: student blanks when their perceived P(correct) < tau_vec
            # Add small perception noise ~ N(0, 0.055) so blank rate is ~ 6% to 12% and negatively correlated with theta
            p_perceived = p_true_mat + rng_resp.normal(0.0, 0.055, size=(n_pres, n_q))
            is_blank_mat = p_perceived < tau_vec

            # For OMR tests, 1.5% chance of multi_marked / unreadable
            if t_source == "omr":
                omr_err_roll = rng_resp.random(size=(n_pres, n_q))
                is_multi_mat = (~is_blank_mat) & (omr_err_roll < 0.008)
                is_unread_mat = (~is_blank_mat) & (omr_err_roll >= 0.008) & (omr_err_roll < 0.015)
            else:
                is_multi_mat = np.zeros((n_pres, n_q), dtype=bool)
                is_unread_mat = np.zeros((n_pres, n_q), dtype=bool)

            # Determine whether student answers the TRUE correct answer
            u_correct = rng_resp.random(size=(n_pres, n_q))
            got_true_ans_mat = (~is_blank_mat) & (~is_multi_mat) & (~is_unread_mat) & (u_correct < p_true_mat)

            # Sample calibration pairs for ground-truth consistency test (non-blank, non-wrong-key responses)
            valid_cal_mask = (~is_blank_mat) & (~is_multi_mat) & (~is_unread_mat) & (~wk_vec[None, :])
            if np.any(valid_cal_mask):
                cal_p = p_true_mat[valid_cal_mask]
                cal_y = got_true_ans_mat[valid_cal_mask].astype(int)
                inst_cal_list = calibration_samples.setdefault(inst_id, [])
                if len(inst_cal_list) < 25000:
                    take_n = min(len(cal_p), 25000 - len(inst_cal_list))
                    for pv, yv in zip(cal_p[:take_n].tolist(), cal_y[:take_n].tolist()):
                        inst_cal_list.append((float(pv), int(yv)))

            # Score against the KEYED answer (which is flipped for injected wrong keys!)
            is_correct_mat = np.zeros((n_pres, n_q), dtype=bool)
            marks_mat = np.zeros((n_pres, n_q), dtype=float)

            for col_j, (qid, sec, subj) in enumerate(selected_qids):
                pos = col_j + 1
                qm = q_meta[qid]
                is_dropped = (pos == dropped_pos)
                is_wk = qm["is_injected_wrong_key"]
                true_ans = qm["true_correct_answer"]
                keyed_ans_list = qm["keyed_answers"]

                blank_col = is_blank_mat[:, col_j]
                multi_col = is_multi_mat[:, col_j]
                unread_col = is_unread_mat[:, col_j]
                true_hit_col = got_true_ans_mat[:, col_j]

                if is_dropped:
                    # Dropped question: full marks to all per NTA rule
                    is_corr_col = np.ones(n_pres, dtype=bool)
                    m_col = np.full(n_pres, c_marks, dtype=float)
                elif not is_wk:
                    is_corr_col = true_hit_col
                    m_col = np.where(
                        blank_col | unread_col,
                        b_marks,
                        np.where(is_corr_col, c_marks, w_marks),
                    )
                else:
                    # Wrong key injected! Students who know the true answer mark true_ans (which is marked wrong),
                    # while low-ability students who miss true_ans have ~ 1/3 chance of hitting the wrong key!
                    missed_true = (~blank_col) & (~multi_col) & (~unread_col) & (~true_hit_col)
                    # Low-ability students are slightly more likely to pick the distractor that was mistakenly keyed
                    hit_wrong_key = missed_true & (rng_resp.random(size=n_pres) < 0.45)
                    is_corr_col = hit_wrong_key
                    m_col = np.where(
                        blank_col | unread_col,
                        b_marks,
                        np.where(is_corr_col, c_marks, w_marks),
                    )

                is_correct_mat[:, col_j] = is_corr_col
                marks_mat[:, col_j] = m_col

            # Compute student subtotals
            subj_list = [s for _, _, s in selected_qids]
            phy_mask = np.array([s == "Physics" for s in subj_list], dtype=bool)
            chem_mask = np.array([s == "Chemistry" for s in subj_list], dtype=bool)
            mb_mask = np.array([s in ("Mathematics", "Botany", "Zoology") for s in subj_list], dtype=bool)

            raw_totals = marks_mat.sum(axis=1)
            phy_totals = marks_mat[:, phy_mask].sum(axis=1)
            chem_totals = marks_mat[:, chem_mask].sum(axis=1)
            mb_totals = marks_mat[:, mb_mask].sum(axis=1)

            for row_i, sid in enumerate(present_sids):
                test_totals_rows.append(
                    {
                        "institute_id": inst_id,
                        "test_id": test_id,
                        "student_id": sid,
                        "raw_score": float(raw_totals[row_i]),
                        "physics_score": float(phy_totals[row_i]),
                        "chemistry_score": float(chem_totals[row_i]),
                        "math_or_bio_score": float(mb_totals[row_i]),
                        "absent_flag": False,
                    }
                )
                # Update student's running test history for final outcome alignment
                student_meta[sid].setdefault("mock_pcts", []).append(float(raw_totals[row_i]) / max_marks)

            # Emit item-level responses unless this is a marks-only test
            if not is_marks_only_test:
                opts = ["A", "B", "C", "D"]
                for col_j, (qid, _, _) in enumerate(selected_qids):
                    qm = q_meta[qid]
                    q_type = qm["q_type"]
                    true_ans = qm["true_correct_answer"]
                    keyed_first = qm["keyed_answers"][0]
                    is_wk = qm["is_injected_wrong_key"]
                    wrong_opts = [o for o in opts if o not in qm["keyed_answers"] and o != true_ans]
                    if not wrong_opts:
                        wrong_opts = ["B", "D"]

                    tracker_list = item_resp_tracker.setdefault(qid, [])

                    for row_i, sid in enumerate(present_sids):
                        is_bl = bool(is_blank_mat[row_i, col_j])
                        is_mu = bool(is_multi_mat[row_i, col_j])
                        is_un = bool(is_unread_mat[row_i, col_j])
                        is_co = bool(is_correct_mat[row_i, col_j])
                        m_aw = float(marks_mat[row_i, col_j])

                        if is_bl:
                            status_str = "blank"
                            resp_str = None
                            conf = 1.0 if t_source != "omr" else 0.99
                        elif is_un:
                            status_str = "unreadable"
                            resp_str = None
                            conf = 0.42
                        elif is_mu:
                            status_str = "multi_marked"
                            resp_str = "A|B"
                            conf = 0.51
                        else:
                            status_str = "answered"
                            conf = 1.0 if t_source != "omr" else 0.98
                            if is_co:
                                resp_str = keyed_first
                            else:
                                if is_wk and bool(got_true_ans_mat[row_i, col_j]):
                                    resp_str = true_ans
                                elif q_type == "numeric":
                                    resp_str = str(int(true_ans) + 3)
                                else:
                                    resp_str = wrong_opts[(row_i + col_j) % len(wrong_opts)]

                        responses_rows.append(
                            {
                                "institute_id": inst_id,
                                "test_id": test_id,
                                "student_id": sid,
                                "question_id": qid,
                                "response": resp_str,
                                "is_correct": is_co,
                                "marks_awarded": m_aw,
                                "status": status_str,
                                "confidence": conf,
                            }
                        )
                        tracker_list.append((1.0 if is_co else 0.0, float(raw_totals[row_i])))

    # 3. Build item_params.parquet (matching datasets.yaml schema)
    item_params_rows: list[dict[str, Any]] = []
    updated_ts = datetime.datetime(2026, 10, 15, 18, 0, 0, tzinfo=IST)
    for qid in sorted(q_meta.keys()):
        qm = q_meta[qid]
        pairs = item_resp_tracker.get(qid, [])
        n_resp = len(pairs)
        if n_resp >= 5:
            arr = np.array(pairs, dtype=float)
            x = arr[:, 0]
            y = arr[:, 1]
            if np.std(x) > 1e-6 and np.std(y) > 1e-6:
                pb = float(np.corrcoef(x, y)[0, 1])
            else:
                pb = 0.0
        else:
            pb = -0.25 if qm["is_injected_wrong_key"] else 0.35

        suspected = bool(pb < 0.05) if n_resp >= 10 else bool(qm["is_injected_wrong_key"])
        key_conf = float(np.clip(0.5 + pb, 0.05, 0.99))
        item_params_rows.append(
            {
                "institute_id": qm["institute_id"],
                "question_id": qid,
                "a": float(qm["true_a"]),
                "b": float(qm["true_b"]),
                "c": float(qm["true_g"]),
                "point_biserial": pb,
                "key_confidence": key_conf,
                "suspected_wrong_key": suspected,
                "n_responses": int(n_resp),
                "updated_at": updated_ts,
            }
        )

    diagnostics = {
        "calibration_samples": calibration_samples,
        "q_meta": q_meta,
    }

    return (
        pd.DataFrame(questions_rows),
        pd.DataFrame(q_topics_rows),
        pd.DataFrame(item_params_rows),
        pd.DataFrame(tests_rows),
        pd.DataFrame(test_q_rows),
        pd.DataFrame(answer_key_rows),
        pd.DataFrame(responses_rows),
        pd.DataFrame(test_totals_rows),
        pd.DataFrame(true_item_rows),
        diagnostics,
    )
