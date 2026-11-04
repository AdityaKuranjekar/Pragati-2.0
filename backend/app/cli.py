"""One-command local start (no Docker, no internet):  python -m app.cli demo   (from backend)

  bootstrap  start PostgreSQL (pgserver), apply the schema, train models if missing, seed if empty
  demo       bootstrap, then serve the API on 127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import time

from . import config


def bootstrap() -> dict:
    t0 = time.time()
    from .db import pg, seed

    uri = pg.database_uri()
    applied = pg.apply_schema()
    out = {"database": uri.split("@")[-1], "schema_applied": applied}
    if not (config.MODELS_DIR / "manifest.json").exists():
        from .ml import train

        print("no saved models found: training once (about 10 s)")
        train.train()
        out["trained"] = True
    with pg.admin_cursor(commit=False) as cur:
        cur.execute("SELECT count(*) AS n FROM institutes")
        empty = cur.fetchone()["n"] == 0
    if empty:
        if not config.DATA_DIR.joinpath("clean").exists():
            raise SystemExit(f"data not found at {config.DATA_DIR}: set DATA_DIR to the folder that holds clean/ and truth/")
        print(f"seeding {config.SEED_INSTITUTES} from {config.DATA_DIR} ...")
        out["seed"] = seed.seed([s.strip() for s in config.SEED_INSTITUTES.split(",")])
    out["seconds"] = round(time.time() - t0, 1)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m app.cli")
    ap.add_argument("command", choices=["bootstrap", "demo"])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    try:
        from .ml import percentile, risk

        for n in risk.MODEL_FEATURES:
            risk.load_booster(n)
        percentile._model()
    except Exception as ex:  # noqa: BLE001
        raise SystemExit(f"a saved model failed to load ({type(ex).__name__}: {str(ex)[:150]}). Run `python -m app.ml.train` to rebuild ml/artifacts/models/ and try again.")
    info = bootstrap()
    print(info)
    if a.command == "demo":
        import uvicorn

        print(f"API on http://{a.host}:{a.port}  (docs at /docs)")
        uvicorn.run("app.main:app", host=a.host, port=a.port, log_level="info")


if __name__ == "__main__":
    main()
