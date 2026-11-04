"""Test fixtures: a throw-away PostgreSQL (pgserver, no Docker) seeded with two institutes, and a TestClient."""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
ROOT = BACKEND.parent
os.environ.setdefault("PG_DATA_DIR", str(ROOT / ".pgdata_test"))
os.environ.setdefault("PG_KEEP_RUNNING", "0")
os.environ.setdefault("PYTHONUTF8", "1")
sys.path.insert(0, str(BACKEND))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

TEST_INSTITUTES = ["patna_jee", "gaya_both"]


@pytest.fixture(scope="session")
def seeded():
    from app.db import seed as seed_mod

    out = seed_mod.seed(TEST_INSTITUTES, force=True)
    assert out["seeded"], out
    return out


@pytest.fixture(scope="session")
def client(seeded):
    from app.main import app

    with TestClient(app) as c:
        yield c


def _login(client, institute, role, **kw):
    r = client.post("/auth/login", json={"institute": institute, "role": role, **kw})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


@pytest.fixture(scope="session")
def login(client):
    return lambda institute, role, **kw: _login(client, institute, role, **kw)


@pytest.fixture(scope="session")
def teacher(login):
    return login("patna_jee", "teacher")


@pytest.fixture(scope="session")
def owner(login):
    return login("patna_jee", "owner")


@pytest.fixture(scope="session")
def batches(client, teacher):
    return client.get("/api/v1/batches", headers=teacher).json()["batches"]


@pytest.fixture(scope="session")
def batch_id(batches):
    return batches[0]["id"]


@pytest.fixture()
def reseed(seeded):
    """Function-scoped: restore pristine data after a destructive test."""
    yield
    from app.db import seed as seed_mod
    from app.services import analytics

    seed_mod.seed(TEST_INSTITUTES, force=True)
    analytics._cache.clear()
