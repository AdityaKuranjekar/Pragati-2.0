"""Runtime configuration. Everything is overridable by environment variable; defaults work on the dev laptop."""
from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
ROOT = BACKEND_DIR.parent  # repository root (contracts/, ml/, datagen/, frontend/ sit beside backend/)
CONTRACTS = ROOT / "contracts"
ARTIFACTS = Path(os.environ.get("ARTIFACTS_DIR", ROOT / "ml" / "artifacts"))
MODELS_DIR = Path(os.environ.get("MODELS_DIR", ARTIFACTS / "models"))

# Generated synthetic data lives outside git (see datagen/README.md); DATA_DIR overrides the default.
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))

PG_DATA_DIR = Path(os.environ.get("PG_DATA_DIR", ROOT / ".pgdata"))
DATABASE_URL = os.environ.get("DATABASE_URL")  # if set, pgserver is not used

SECRET_KEY = os.environ.get("PRAGATI_SECRET", "pragati-dev-secret-change-me")
TOKEN_MAX_AGE_S = int(os.environ.get("TOKEN_MAX_AGE_S", 12 * 3600))
DEMO_MODE = os.environ.get("DEMO_MODE", "1") == "1"  # lets the role switcher pick any student

MODEL_VERSION = "v1.1.0"
ASOF_NOW = os.environ.get("ASOF_NOW", "2026-09-01")  # demo "today" matching the artifacts
CURRENT_YEAR = 2026

SLUG = {"Patna": "patna_jee", "Lucknow": "lucknow_neet", "Gaya": "gaya_both", "Kota": "kota_large"}
SEED_INSTITUTES = os.environ.get("SEED_INSTITUTES", "patna_jee,lucknow_neet,gaya_both")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
