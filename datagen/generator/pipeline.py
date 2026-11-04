"""Main pipeline orchestrating the synthetic generator, messy exports, and synthetic OMR."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd

from .attendance_fees_outcomes import generate_attendance_fees_engagement_outcomes_consents
from .institutes import generate_institutes_batches_students
from .latent_traits import generate_latent_traits_and_dropouts, load_syllabus_topics
from .questions_tests import generate_questions_tests_responses
from .utils import (
    CONFIG_PATH,
    CONTRACTS_DIR,
    load_and_validate_config,
    load_yaml,
    spawn_rng_tree,
    write_contract_parquet,
)
from ..messy.injector import generate_messy_exports
from ..omr_synth.renderer import generate_synthetic_omr_dataset


def run_datagen_pipeline(
    seed: int = 42,
    preset: str = "full",
    out_dir: Path | str = "data",
    scenario_path: Path | str | None = None,
    config_path: Path = CONFIG_PATH,
    include_omr: bool = True,
    include_messy: bool = True,
) -> dict[str, Any]:
    """Run the complete deterministic synthetic data generation pipeline and write outputs to `out_dir`."""
    t0 = time.perf_counter()
    out_root = Path(out_dir)
    clean_dir = out_root / "clean"
    truth_dir = out_root / "truth"
    dirty_dir = out_root / "dirty"

    scen_p = Path(scenario_path) if scenario_path is not None else None
    cfg = load_and_validate_config(
        config_path=config_path,
        preset=preset,
        seed=seed,
        scenario_path=scen_p,
    )

    rngs = spawn_rng_tree(int(cfg["seed"]), n_branches=10)
    (
        rng_inst,
        rng_traits,
        rng_dropout,
        rng_items,
        rng_resp,
        rng_att,
        rng_fees,
        rng_eng,
        rng_out,
        rng_messy_omr,
    ) = rngs

    # Step 1: Institutes, batches, students, guardians
    institutes_df, batches_df, students_df, guardians_df, student_meta = generate_institutes_batches_students(
        cfg, rng_inst
    )

    # Step 2 & 8: Latent traits, topic theta trajectories, and dropout events
    leaf_topics, topics_by_exam, chapter_prereqs = load_syllabus_topics()
    students_df, true_theta_df, dropout_events_df = generate_latent_traits_and_dropouts(
        cfg,
        students_df,
        student_meta,
        leaf_topics,
        topics_by_exam,
        chapter_prereqs,
        rng_traits,
        rng_dropout,
    )

    # Step 3 & 4: Questions, tests, answer keys, responses, test_totals, item_params
    (
        questions_df,
        q_topics_df,
        item_params_df,
        tests_df,
        test_q_df,
        answer_keys_df,
        responses_df,
        test_totals_df,
        true_item_params_df,
        diagnostics,
    ) = generate_questions_tests_responses(
        cfg,
        institutes_df,
        batches_df,
        students_df,
        student_meta,
        leaf_topics,
        topics_by_exam,
        rng_items,
        rng_resp,
    )

    # Step 5, 6, 7, 9, 10: Attendance, fees, engagement, consents, true_final_outcomes
    attendance_df, fees_df, engagement_df, consents_df, outcomes_df = (
        generate_attendance_fees_engagement_outcomes_consents(
            cfg,
            students_df,
            student_meta,
            rng_att,
            rng_fees,
            rng_eng,
            rng_out,
        )
    )

    clean_tables: dict[str, pd.DataFrame] = {
        "institutes": institutes_df,
        "batches": batches_df,
        "students": students_df,
        "guardians": guardians_df,
        "consents": consents_df,
        "questions": questions_df,
        "question_topics": q_topics_df,
        "item_params": item_params_df,
        "tests": tests_df,
        "test_questions": test_q_df,
        "answer_keys": answer_keys_df,
        "responses": responses_df,
        "test_totals": test_totals_df,
        "attendance": attendance_df,
        "fees": fees_df,
        "engagement": engagement_df,
    }

    truth_tables: dict[str, pd.DataFrame] = {
        "true_theta_topic": true_theta_df,
        "true_item_params": true_item_params_df,
        "dropout_events": dropout_events_df,
        "true_final_outcomes": outcomes_df,
    }

    # Write Parquet files conforming strictly to contracts/datasets.yaml
    datasets_contract = load_yaml(CONTRACTS_DIR / "datasets.yaml")
    for tname, spec in datasets_contract["clean_tables"].items():
        write_contract_parquet(clean_tables[tname], spec, clean_dir / f"{tname}.parquet")

    for tname, spec in datasets_contract["truth_tables"].items():
        write_contract_parquet(truth_tables[tname], spec, truth_dir / f"{tname}.parquet")

    # Write generator calibration & metadata summary for tests/notebooks (under truth/calibration_samples.json)
    cal_summary_path = truth_dir / "calibration_samples.json"
    with open(cal_summary_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "seed": int(cfg["seed"]),
                "preset": preset,
                "calibration_samples": diagnostics["calibration_samples"],
            },
            f,
            indent=2,
            sort_keys=True,
        )

    messy_files: list[Path] = []
    if include_messy:
        messy_files = generate_messy_exports(clean_tables, dirty_dir, rng_messy_omr)

    omr_truth_path: Path | None = None
    if include_omr:
        n_omr = 210 if preset == "full" else 24
        omr_truth_path = generate_synthetic_omr_dataset(out_root, rng_messy_omr, n_sheets=n_omr)

    elapsed = time.perf_counter() - t0
    return {
        "seed": int(cfg["seed"]),
        "preset": preset,
        "out_dir": str(out_root),
        "elapsed_sec": elapsed,
        "clean_tables": clean_tables,
        "truth_tables": truth_tables,
        "student_meta": student_meta,
        "messy_files": messy_files,
        "omr_truth_path": omr_truth_path,
    }
