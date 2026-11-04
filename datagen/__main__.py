"""CLI entrypoint for `python -m datagen`."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .generator.pipeline import run_datagen_pipeline
from .generator.utils import DATAGEN_DIR


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m datagen",
        description="Seeded, deterministic synthetic data generator for DataMoat.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Integer random seed (default: 42)")
    parser.add_argument(
        "--preset",
        choices=["tiny", "full"],
        default="full",
        help="Dataset size preset: 'tiny' (M1: 1 inst, 150 students, 2 yrs) or 'full' (M2: 4 insts, 3 yrs)",
    )
    parser.add_argument("--out", type=str, default="data/", help="Output root directory (default: data/)")
    parser.add_argument(
        "--scenario",
        type=str,
        default=None,
        help="Optional scenario override YAML path (e.g., scenarios/dropout_x2.yaml)",
    )
    args = parser.parse_args(argv)

    scenario_path: Path | None = None
    if args.scenario:
        cand = Path(args.scenario)
        if not cand.exists():
            cand = DATAGEN_DIR / args.scenario
        if not cand.exists():
            raise FileNotFoundError(f"Scenario file not found: {args.scenario}")
        scenario_path = cand

    res = run_datagen_pipeline(
        seed=args.seed,
        preset=args.preset,
        out_dir=Path(args.out),
        scenario_path=scenario_path,
    )
    n_students = len(res["clean_tables"]["students"])
    n_resp = len(res["clean_tables"]["responses"])
    print(
        f"[datagen] Done preset={res['preset']} seed={res['seed']} "
        f"students={n_students} responses={n_resp} in {res['elapsed_sec']:.2f}s -> {res['out_dir']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
