"""Deterministic ID, RNG, config loading, and canonical Parquet writer utilities."""

from __future__ import annotations

import copy
import datetime
import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

import jsonschema
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_DIR = ROOT / "contracts"
DATAGEN_DIR = ROOT / "datagen"
CONFIG_DIR = DATAGEN_DIR / "config"
SCENARIOS_DIR = DATAGEN_DIR / "scenarios"
CONFIG_PATH = CONFIG_DIR / "generator_config.yaml"
SCHEMA_PATH = CONFIG_DIR / "generator_config.schema.json"

NAMESPACE_DATAMOAT = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

EXAM_FOCUS_MAP = {"JEE": "jee_main", "NEET": "neet_ug", "MIX": "mix"}
TIER_MAP = {1: "tier_1", 2: "tier_2", 3: "tier_3"}
DAY_MAP = {
    "monday": "monday",
    "tuesday": "tuesday",
    "wednesday": "wednesday",
    "thursday": "thursday",
    "friday": "friday",
    "saturday": "saturday",
    "sunday": "sunday",
}


def det_uuid(domain: str, *parts: Any) -> str:
    """Generate a deterministic UUID5 string from domain and parts."""
    key = f"datamoat|{domain}|" + "|".join(str(p) for p in parts)
    return str(uuid.uuid5(NAMESPACE_DATAMOAT, key))


def det_sha256(text: str) -> str:
    """Return hex SHA-256 of UTF-8 string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def spawn_rng_tree(seed: int, n_branches: int = 12) -> list[np.random.Generator]:
    """Create a deterministic tree of numpy Generators from a single integer seed."""
    ss = np.random.SeedSequence(int(seed))
    return [np.random.Generator(np.random.PCG64(child)) for child in ss.spawn(n_branches)]


def load_yaml(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_and_validate_config(
    config_path: Path = CONFIG_PATH,
    preset: str = "full",
    seed: int | None = None,
    scenario_path: Path | None = None,
) -> dict[str, Any]:
    """Load generator_config.yaml, apply preset and scenario overrides, and validate against JSON schema + enums."""
    cfg = copy.deepcopy(load_yaml(config_path))
    schema = load_json(SCHEMA_PATH)
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(instance=cfg, schema=schema)

    if seed is not None:
        cfg["seed"] = int(seed)

    # Apply preset
    if preset == "tiny":
        cfg["institutes"] = [
            {"id": "patna_jee", "city": "Patna", "tier": 2, "exam": "JEE", "students": 150}
        ]
        cfg["academic_years"] = [2025, 2026]
    elif preset == "full":
        cfg["academic_years"] = [2024, 2025, 2026]
    else:
        raise ValueError(f"Unknown preset '{preset}'. Expected 'tiny' or 'full'.")

    active_knobs: dict[str, Any] = {
        "dropout_multiplier": 1.0,
        "sudden_share": cfg["dropout"]["sudden_share"],
        "marks_only_share": 0.0,
        "online_test_share": 0.15,
        "upfront_full_fee_share": cfg["fees"]["upfront_share"],
        "missing_rate": 0.0,
        "institute_size_scale": 1.0,
        "neet_variant": cfg["exam_patterns"]["NEET_UG_2026"]["default_variant"],
        "wrong_key_rate": cfg["messy"]["wrong_answer_keys_per_100_items"] / 100.0,
        "fade_weeks": cfg["attendance"]["pre_dropout_fade_weeks"],
    }

    if scenario_path is not None:
        scen_doc = load_yaml(scenario_path)
        knobs = scen_doc.get("knobs", {})
        for k, v in knobs.items():
            active_knobs[k] = v
        if "dropout_multiplier" in knobs:
            cfg["dropout"]["annual_rate"] = float(
                np.clip(cfg["dropout"]["annual_rate"] * float(knobs["dropout_multiplier"]), 0.01, 0.75)
            )
        if "sudden_share" in knobs:
            cfg["dropout"]["sudden_share"] = float(knobs["sudden_share"])
        if "upfront_full_fee_share" in knobs:
            cfg["fees"]["upfront_share"] = float(knobs["upfront_full_fee_share"])
        if "institute_size_scale" in knobs:
            scale = float(knobs["institute_size_scale"])
            for inst in cfg["institutes"]:
                inst["students"] = max(20, int(round(inst["students"] * scale)))
        if "batch_size_override" in knobs:
            cfg["students"]["batch_size"] = list(knobs["batch_size_override"])
        if "neet_variant" in knobs:
            cfg["exam_patterns"]["NEET_UG_2026"]["default_variant"] = str(knobs["neet_variant"])
        if "wrong_key_rate" in knobs:
            cfg["messy"]["wrong_answer_keys_per_100_items"] = float(knobs["wrong_key_rate"]) * 100.0
        if "fade_weeks" in knobs:
            cfg["attendance"]["pre_dropout_fade_weeks"] = list(knobs["fade_weeks"])

    cfg["active_knobs"] = active_knobs
    jsonschema.validate(instance=cfg, schema=schema)

    # Validate enum mappings against contracts/enums.yaml
    enums_doc = load_yaml(CONTRACTS_DIR / "enums.yaml")["enums"]
    for inst in cfg["institutes"]:
        mapped_exam = EXAM_FOCUS_MAP[inst["exam"]]
        mapped_tier = TIER_MAP[inst["tier"]]
        assert mapped_exam in enums_doc["institute_exam_focus"]["values"]
        assert mapped_tier in enums_doc["city_tier"]["values"]

    off_day = cfg["tests"]["weekly_off_day"].lower()
    assert DAY_MAP[off_day] in enums_doc["day_of_week"]["values"]

    return cfg


def _pa_type_for_contract(dtype_str: str) -> pa.DataType:
    if dtype_str == "string":
        return pa.string()
    if dtype_str == "int32":
        return pa.int32()
    if dtype_str == "int64":
        return pa.int64()
    if dtype_str == "float64":
        return pa.float64()
    if dtype_str == "bool":
        return pa.bool_()
    if dtype_str == "date32":
        return pa.date32()
    if dtype_str == "timestamp_tz":
        return pa.timestamp("us", tz="Asia/Kolkata")
    if dtype_str == "list_string":
        return pa.list_(pa.string())
    raise ValueError(f"Unsupported contract dtype: {dtype_str}")


def write_contract_parquet(
    df: pd.DataFrame,
    table_spec: dict[str, Any],
    out_path: Path,
) -> None:
    """Sort DataFrame by contract sort_by keys, cast to exact Arrow schema, and write deterministic zstd Parquet."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sort_keys = table_spec["sort_by"]
    col_specs = table_spec["columns"]
    col_names = [c["name"] for c in col_specs]

    if len(df) == 0:
        df_sorted = pd.DataFrame(columns=col_names)
    else:
        df_sorted = df[col_names].sort_values(by=sort_keys, kind="mergesort").reset_index(drop=True)

    fields = []
    arrays = []
    for c in col_specs:
        cname = c["name"]
        dtype_str = c["dtype"]
        nullable = bool(c["nullable"])
        pa_type = _pa_type_for_contract(dtype_str)
        fields.append(pa.field(cname, pa_type, nullable=nullable))

        series = df_sorted[cname] if cname in df_sorted.columns else pd.Series([], dtype=object)
        if dtype_str == "date32":
            vals = [
                None
                if (v is None or pd.isna(v))
                else (datetime.date.fromisoformat(v) if isinstance(v, str) else v)
                for v in series.tolist()
            ]
            arr = pa.array(vals, type=pa_type)
        elif dtype_str == "timestamp_tz":
            vals = []
            for v in series.tolist():
                if v is None or pd.isna(v):
                    vals.append(None)
                elif isinstance(v, str):
                    vals.append(datetime.datetime.fromisoformat(v))
                elif isinstance(v, pd.Timestamp):
                    vals.append(v.to_pydatetime())
                else:
                    vals.append(v)
            arr = pa.array(vals, type=pa_type)
        elif dtype_str == "list_string":
            vals = [list(v) if v is not None else None for v in series.tolist()]
            arr = pa.array(vals, type=pa_type)
        elif dtype_str == "bool":
            vals = [bool(v) if v is not None and not pd.isna(v) else None for v in series.tolist()]
            arr = pa.array(vals, type=pa_type)
        elif dtype_str in ("int32", "int64"):
            vals = [int(v) if v is not None and not pd.isna(v) else None for v in series.tolist()]
            arr = pa.array(vals, type=pa_type)
        elif dtype_str == "float64":
            vals = [float(v) if v is not None and not pd.isna(v) else None for v in series.tolist()]
            arr = pa.array(vals, type=pa_type)
        else:
            vals = [str(v) if v is not None and not pd.isna(v) else None for v in series.tolist()]
            arr = pa.array(vals, type=pa_type)
        arrays.append(arr)

    schema = pa.schema(fields)
    table = pa.Table.from_arrays(arrays, schema=schema)
    pq.write_table(
        table,
        out_path,
        compression="zstd",
        write_statistics=True,
        use_dictionary=False,
    )
