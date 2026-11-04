"""PostgreSQL 16 lifecycle (pgserver, no Docker) and tenant-scoped connections.

Every request connection does `SET ROLE app_user` and sets `app.institute_id`, so the row-level-security
policies of contracts/schema.sql apply to every query the API makes. The superuser connection is used only
by the seed loader and by /auth/login (to resolve which tenant a login belongs to).
"""
from __future__ import annotations

import contextlib
import os
import threading
from typing import Iterator

import psycopg2
import psycopg2.extras
import psycopg2.pool

from .. import config

_lock = threading.Lock()
_server = None
_uri: str | None = None
_pool: psycopg2.pool.ThreadedConnectionPool | None = None
psycopg2.extras.register_uuid()


def database_uri() -> str:
    """Start (or attach to) the local server and return a libpq URI. Idempotent."""
    global _server, _uri
    with _lock:
        if config.DATABASE_URL:
            return config.DATABASE_URL
        if _uri is None:
            import pgserver

            config.PG_DATA_DIR.mkdir(parents=True, exist_ok=True)
            keep = os.environ.get("PG_KEEP_RUNNING", "1") == "1"
            _server = pgserver.get_server(str(config.PG_DATA_DIR), cleanup_mode=None if keep else "stop")  # demo keeps it running
            _uri = _server.get_uri()
        return _uri


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    uri = database_uri()
    with _lock:
        if _pool is None:
            _pool = psycopg2.pool.ThreadedConnectionPool(1, 16, uri)
        return _pool


def admin_connect():
    """New superuser connection (RLS bypassed). Caller closes it."""
    conn = psycopg2.connect(database_uri())
    conn.autocommit = False
    return conn


@contextlib.contextmanager
def admin_cursor(commit: bool = True) -> Iterator[psycopg2.extras.RealDictCursor]:
    conn = _get_pool().getconn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        yield cur
        if commit:
            conn.commit()
        else:
            conn.rollback()
    except Exception:
        conn.rollback()
        raise
    finally:
        _get_pool().putconn(conn)


@contextlib.contextmanager
def tenant_conn(institute_id: str) -> Iterator[psycopg2.extensions.connection]:
    """Pooled connection restricted to one tenant by SET ROLE app_user + app.institute_id (RLS enforced)."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SET ROLE app_user")
            cur.execute("SELECT set_config('app.institute_id', %s, false)", (str(institute_id),))
        conn.commit()
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        try:
            with conn.cursor() as cur:
                cur.execute("RESET ROLE")
                cur.execute("RESET app.institute_id")
            conn.commit()
        except Exception:
            conn.rollback()
        pool.putconn(conn)


def tenant_cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def db_ok() -> bool:
    try:
        with admin_cursor(commit=False) as cur:
            cur.execute("SELECT 1 AS x")
            return cur.fetchone()["x"] == 1
    except Exception:
        return False


def apply_schema(force: bool = False) -> bool:
    """Apply contracts/schema.sql if the institutes table is missing. Returns True if applied."""
    with admin_cursor() as cur:
        cur.execute("SELECT to_regclass('public.institutes') AS t")
        exists = cur.fetchone()["t"] is not None
        if exists and not force:
            return False
        if exists and force:
            cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT USAGE ON SCHEMA public TO PUBLIC;")
        cur.execute((config.CONTRACTS / "schema.sql").read_text(encoding="utf-8"))
    return True
