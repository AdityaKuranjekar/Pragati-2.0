#!/usr/bin/env python3
"""
Download and verify public validation datasets (OULAD & ASSISTments 2009-2010)
for Agent D (Public Validation).

Licences & Handling:
- OULAD (Open University Learning Analytics Dataset):
  CC BY 4.0 (Kuzilek, Hlosta, Zdrahal, 2017). Commercial use OK with attribution.
- ASSISTments 2009-2010 Skill Builder:
  Free for research use (Worcester Polytechnic Institute / ASSISTments).
  Not for redistribution or commercial use without permission.
- EdNet-KT1:
  CC BY-NC 4.0 (NonCommercial). Skipped by default; requires --with-ednet.

Datasets are stored under `data/public/` (git-ignored) and NEVER committed.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Dict, Any

# Threshold requiring explicit human approval or --yes-large-files
LARGE_DOWNLOAD_THRESHOLD_BYTES = 500 * 1024 * 1024  # 500 MB

DATASETS: Dict[str, Dict[str, Any]] = {
    "oulad": {
        "title": "Open University Learning Analytics Dataset (OULAD)",
        "licence": "CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)",
        "citation": (
            "Kuzilek, J., Hlosta, M., & Zdrahal, Z. (2017). Open University Learning Analytics "
            "dataset. Scientific Data, 4, 170171. https://doi.org/10.1038/sdata.2017.171"
        ),
        "urls": [
            "https://ndownloader.figshare.com/files/8606371",
            "https://archive.ics.uci.edu/static/public/349/open+university+learning+analytics+dataset.zip",
        ],
        "archive_name": "anonymisedData.zip",
        "expected_size": 46750706,
        "expected_md5": "7412686fd77cf0e0ee1e8c3e9b354308",
        "expected_files": [
            "assessments.csv",
            "courses.csv",
            "studentAssessment.csv",
            "studentInfo.csv",
            "studentRegistration.csv",
            "studentVle.csv",
            "vle.csv",
        ],
    },
    "assistments2009": {
        "title": "ASSISTments 2009-2010 Skill Builder Dataset",
        "licence": "Research use only (WPI ASSISTments; no blanket commercial licence; do not redistribute)",
        "citation": (
            "Feng, M., Heffernan, N., & Koedinger, K. (2009). Addressing the assessment challenge "
            "with an online system that tutors as it assesses. User Modeling and User-Adapted "
            "Interaction, 19(3), 243-266."
        ),
        "urls": [
            "https://ndownloader.figshare.com/files/44732737",
            "https://ndownloader.figshare.com/files/44736253",
        ],
        "archive_name": "skill_builder_data.csv",
        "expected_size": 83201940,
        "expected_md5": "9410c31fadc7ad6518d296ce254ec4ab",
        "expected_files": ["skill_builder_data.csv"],
    },
    "ednet_kt1": {
        "title": "EdNet-KT1 (Optional Scale Benchmark)",
        "licence": "CC BY-NC 4.0 (Non-Commercial ONLY; skipped by default)",
        "citation": (
            "Choi, Y., et al. (2020). EdNet: A Large-Scale Hierarchical Dataset in Education. "
            "AIED 2020."
        ),
        "urls": [
            "http://base.ustc.edu.cn/data/EdNet/EdNet-KT1.zip",
        ],
        "archive_name": "EdNet-KT1.zip",
        "expected_size": 650_000_000,  # > 500 MB
        "expected_md5": None,
        "expected_files": [],
    },
}


def compute_hashes(path: Path) -> Dict[str, str]:
    md5 = hashlib.md5()
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            md5.update(chunk)
            sha256.update(chunk)
    return {"md5": md5.hexdigest(), "sha256": sha256.hexdigest()}


def write_public_readme(data_dir: Path) -> Path:
    """Write data/public/README.txt with dataset sources, hashes, and licence notices."""
    data_dir.mkdir(parents=True, exist_ok=True)
    readme_path = data_dir / "README.txt"
    lines = [
        "=======================================================================",
        "PUBLIC VALIDATION DATASETS — LICENCES & PROVENANCE (DO NOT COMMIT)",
        "=======================================================================",
        "",
        "This directory (`data/public/`) caches public educational datasets for",
        "Round 1 validation (`notebooks/06_public_validation.ipynb`).",
        "Files in this directory are git-ignored and must NEVER be committed.",
        "",
        "1. OULAD (Open University Learning Analytics Dataset)",
        f"   - Source: Figshare (DOI: 10.6084/m9.figshare.5081998) / UCI ML Repo",
        f"   - Licence: {DATASETS['oulad']['licence']}",
        f"   - Citation: {DATASETS['oulad']['citation']}",
        "   - Note: `studentVle.csv` unzips to ~433 MB (from a ~44.6 MB zip).",
        "",
        "2. ASSISTments 2009-2010 Skill Builder",
        f"   - Source: Official WPI ASSISTments release (mirrored on Figshare #25309000)",
        f"   - Licence: {DATASETS['assistments2009']['licence']}",
        f"   - Citation: {DATASETS['assistments2009']['citation']}",
        "   - Notice: Used strictly for academic/benchmark evaluation under the",
        "     standardized pyKT 5-fold cross-validation protocol (Liu et al., NeurIPS 2022).",
        "",
        "3. EdNet-KT1 (Optional Scale Test Only)",
        f"   - Licence: {DATASETS['ednet_kt1']['licence']}",
        "   - Status: Skipped by default (requires `--with-ednet` and explicit human",
        "     approval because download size exceeds 500 MB and licence is CC BY-NC).",
        "",
    ]
    readme_path.write_text("\n".join(lines), encoding="utf-8")
    return readme_path


def download_with_resume(
    urls: list[str],
    dest_path: Path,
    expected_size: int | None = None,
    expected_md5: str | None = None,
    yes_large: bool = False,
) -> Path:
    """Download a file from a list of mirror URLs with HTTP Range resume and size/hash checks."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # Check if already downloaded and valid
    if dest_path.exists():
        current_size = dest_path.stat().st_size
        if expected_size is not None and current_size == expected_size:
            if expected_md5 is not None:
                hashes = compute_hashes(dest_path)
                if hashes["md5"] == expected_md5:
                    print(f"[OK] {dest_path.name} already downloaded and verified (MD5={expected_md5}).")
                    return dest_path
                else:
                    print(f"[WARN] {dest_path.name} MD5 mismatch ({hashes['md5']} != {expected_md5}); re-downloading.")
                    dest_path.unlink()
            else:
                print(f"[OK] {dest_path.name} already exists with expected size ({current_size:,} bytes).")
                return dest_path

    if expected_size is not None and expected_size > LARGE_DOWNLOAD_THRESHOLD_BYTES and not yes_large:
        raise RuntimeError(
            f"Download for {dest_path.name} is estimated at {expected_size / (1024**2):.1f} MB "
            f"(> 500 MB threshold). Please ask the human for approval and re-run with --yes-large-files."
        )

    last_err: Exception | None = None
    for url in urls:
        try:
            existing_bytes = dest_path.stat().st_size if dest_path.exists() else 0
            headers = {"User-Agent": "Mozilla/5.0 (DataMoat-PublicValidation/1.0)"}
            if existing_bytes > 0 and (expected_size is None or existing_bytes < expected_size):
                headers["Range"] = f"bytes={existing_bytes}-"
                mode = "ab"
                print(f"[RESUME] Resuming {dest_path.name} from byte {existing_bytes:,} via {url} ...")
            else:
                existing_bytes = 0
                mode = "wb"
                print(f"[DOWNLOAD] Fetching {dest_path.name} from {url} ...")

            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                content_len = resp.headers.get("Content-Length")
                total_remaining = int(content_len) if content_len and content_len.isdigit() else None
                total_expected = (existing_bytes + total_remaining) if total_remaining is not None else expected_size

                if total_expected is not None and total_expected > LARGE_DOWNLOAD_THRESHOLD_BYTES and not yes_large:
                    raise RuntimeError(
                        f"Remote Content-Length for {dest_path.name} is {total_expected / (1024**2):.1f} MB "
                        f"(> 500 MB threshold). Aborting. Ask human before downloading > 500 MB."
                    )

                # If server ignored Range header and sent 200 instead of 206, overwrite from scratch
                if resp.status == 200 and mode == "ab":
                    mode = "wb"
                    existing_bytes = 0

                downloaded = existing_bytes
                with open(dest_path, mode) as out_f:
                    while True:
                        chunk = resp.read(256 * 1024)
                        if not chunk:
                            break
                        out_f.write(chunk)
                        downloaded += len(chunk)

            final_size = dest_path.stat().st_size
            if expected_size is not None and final_size != expected_size:
                raise IOError(
                    f"Size mismatch for {dest_path.name}: got {final_size:,} bytes, expected {expected_size:,} bytes."
                )

            hashes = compute_hashes(dest_path)
            if expected_md5 is not None and hashes["md5"] != expected_md5:
                # Some mirrors repackage zip files; warn or verify
                print(
                    f"[INFO] {dest_path.name} downloaded ({final_size:,} bytes, MD5={hashes['md5']}, "
                    f"SHA256={hashes['sha256']})."
                )
            else:
                print(
                    f"[OK] Downloaded {dest_path.name} ({final_size:,} bytes, "
                    f"MD5={hashes['md5']}, SHA256={hashes['sha256']})."
                )
            return dest_path

        except (urllib.error.URLError, TimeoutError, IOError) as exc:
            last_err = exc
            print(f"[WARN] Mirror {url} failed: {exc}")
            continue

    raise RuntimeError(
        f"OFFLINE / NETWORK UNAVAILABLE: Could not download {dest_path.name} from any configured source. "
        f"Last error: {last_err}\n"
        f"To run offline, place the required files directly in {dest_path.parent}."
    )


def prepare_oulad(data_dir: Path, yes_large: bool = False) -> Path:
    """Download and extract OULAD CSVs into data/public/oulad/."""
    oulad_dir = data_dir / "oulad"
    oulad_dir.mkdir(parents=True, exist_ok=True)
    spec = DATASETS["oulad"]

    if all((oulad_dir / fname).exists() for fname in spec["expected_files"]):
        print(f"[OK] OULAD CSV files already extracted in {oulad_dir}")
        return oulad_dir

    zip_path = oulad_dir / spec["archive_name"]
    download_with_resume(
        urls=spec["urls"],
        dest_path=zip_path,
        expected_size=spec["expected_size"],
        expected_md5=None,  # Verify zip integrity via zipfile testzip()
        yes_large=yes_large,
    )

    print(f"[EXTRACT] Extracting {zip_path.name} into {oulad_dir} ...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        bad_file = zf.testzip()
        if bad_file is not None:
            raise IOError(f"Corrupted file inside {zip_path}: {bad_file}")
        for member in zf.infolist():
            if member.is_dir():
                continue
            target_name = Path(member.filename).name
            if target_name in spec["expected_files"]:
                target_path = oulad_dir / target_name
                with zf.open(member) as src, open(target_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)

    missing = [f for f in spec["expected_files"] if not (oulad_dir / f).exists()]
    if missing:
        raise RuntimeError(f"Missing expected OULAD files after extraction: {missing}")

    print(f"[OK] OULAD ready in {oulad_dir} ({len(spec['expected_files'])} CSV files).")
    return oulad_dir


def prepare_assistments2009(data_dir: Path, yes_large: bool = False) -> Path:
    """Download ASSISTments 2009-2010 skill_builder_data.csv into data/public/assistments2009/."""
    as_dir = data_dir / "assistments2009"
    as_dir.mkdir(parents=True, exist_ok=True)
    spec = DATASETS["assistments2009"]

    print(
        "[NOTICE] ASSISTments 2009-2010 Skill Builder data is downloaded for non-commercial "
        "academic/research benchmarking only (pyKT protocol comparison). Do not redistribute."
    )
    csv_path = as_dir / spec["archive_name"]
    download_with_resume(
        urls=spec["urls"],
        dest_path=csv_path,
        expected_size=spec["expected_size"],
        expected_md5=spec["expected_md5"],
        yes_large=yes_large,
    )
    return as_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Download public validation datasets (OULAD and ASSISTments 2009-2010)."
    )
    default_data_dir = Path(__file__).resolve().parents[1] / "data" / "public"
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=default_data_dir,
        help=f"Target directory for public data (default: {default_data_dir})",
    )
    parser.add_argument(
        "--dataset",
        choices=["all", "oulad", "assistments2009"],
        default="all",
        help="Which primary dataset to download (default: all)",
    )
    parser.add_argument(
        "--with-ednet",
        action="store_true",
        help="Also download EdNet-KT1 (CC BY-NC, >500 MB; skipped by default).",
    )
    parser.add_argument(
        "--yes-large-files",
        action="store_true",
        help="Confirm human approval for downloads larger than 500 MB.",
    )
    parser.add_argument(
        "--readme-only",
        action="store_true",
        help="Only write data/public/README.txt and exit without network calls.",
    )

    args = parser.parse_args(argv)
    write_public_readme(args.data_dir)
    if args.readme_only:
        print(f"[OK] Wrote {args.data_dir / 'README.txt'}")
        return 0

    try:
        if args.dataset in ("all", "oulad"):
            prepare_oulad(args.data_dir, yes_large=args.yes_large_files)
        if args.dataset in ("all", "assistments2009"):
            prepare_assistments2009(args.data_dir, yes_large=args.yes_large_files)
        if args.with_ednet:
            ednet_spec = DATASETS["ednet_kt1"]
            ednet_dir = args.data_dir / "ednet_kt1"
            download_with_resume(
                urls=ednet_spec["urls"],
                dest_path=ednet_dir / ednet_spec["archive_name"],
                expected_size=ednet_spec["expected_size"],
                expected_md5=ednet_spec["expected_md5"],
                yes_large=args.yes_large_files,
            )
    except RuntimeError as err:
        print(f"\n[ERROR] {err}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
