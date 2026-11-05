"""A throw-away PostgreSQL cluster for the RLS tests. Never touches an existing database.

Starts a private server on a unix socket only (no TCP), in a fresh directory, applies
contracts/schema.sql and the prototype migration, and removes everything at the end. If no server
binaries are found, or the cluster cannot start, `start()` returns None and the Postgres tests are
SKIPPED (reported as not run, never as passed).

Environment: PG_BIN (directory with initdb, pg_ctl), PG_TEST_TMP (parent directory for the data dir).
Run as root, the server runs as the OS user `postgres` (PostgreSQL refuses to run as root).
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import psycopg2

REPO = Path(__file__).resolve().parents[4]
SCHEMA = REPO / "contracts" / "schema.sql"
MIGRATION = Path(__file__).resolve().parents[1] / "migrations" / "001_prototype_tables.sql"
PROTO_TABLES = ["proto_served_items", "attempt_events", "proto_cohort_teachers", "proto_learners",
                "proto_cohorts", "proto_users"]


def _bin_dir():
    if os.environ.get("PG_BIN"):
        return os.environ["PG_BIN"]
    found = sorted(glob.glob("/usr/lib/postgresql/*/bin"), reverse=True)
    return found[0] if found else shutil.which("pg_ctl") and os.path.dirname(shutil.which("pg_ctl"))


class Cluster:
    def __init__(self, root, bin_dir, user):
        self.root, self.bin, self.user = root, bin_dir, user
        self.data, self.sock = os.path.join(root, "data"), os.path.join(root, "sock")

    def _run(self, *args, **kw):
        cmd = [os.path.join(self.bin, args[0]), *args[1:]]
        if self.user:
            cmd = ["runuser", "-u", self.user, "--", *cmd]
        return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)

    def connect(self, dbname="postgres", user=None):
        return psycopg2.connect(host=self.sock, dbname=dbname, user=user or self.superuser)

    def stop(self):
        try:
            self._run("pg_ctl", "-D", self.data, "-m", "immediate", "stop")
        except Exception:
            pass
        shutil.rmtree(self.root, ignore_errors=True)


def start() -> Cluster | None:
    bin_dir = _bin_dir()
    if not bin_dir or not os.path.exists(os.path.join(bin_dir, "initdb")):
        return None
    user = "postgres" if os.geteuid() == 0 else None
    root = tempfile.mkdtemp(prefix="pragati_pg_", dir=os.environ.get("PG_TEST_TMP"))
    c = Cluster(root, bin_dir, user)
    c.superuser = user or os.environ.get("USER", "postgres")
    try:
        os.makedirs(c.sock)
        if user:
            shutil.chown(root, user=user)
            shutil.chown(c.sock, user=user)
            os.chmod(root, 0o755)
        c._run("initdb", "-D", c.data, "-U", c.superuser, "--auth=trust", "-E", "UTF8")
        c._run("pg_ctl", "-D", c.data, "-w", "-l", os.path.join(root, "log.txt"),
               "-o", f"-c listen_addresses='' -c unix_socket_directories='{c.sock}' -c fsync=off", "start")
        conn = c.connect()
        conn.autocommit = True
        conn.cursor().execute("CREATE DATABASE proto_test")
        conn.close()
        conn = c.connect("proto_test")
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(SCHEMA.read_text())
        cur.execute(MIGRATION.read_text())
        conn.close()
        return c
    except Exception:
        c.stop()
        return None


def truncate_prototype_tables(c: Cluster, institutes):
    conn = c.connect("proto_test")
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("TRUNCATE " + ", ".join(PROTO_TABLES))
    cur.execute("DELETE FROM institutes")
    for iid, name in institutes:
        cur.execute("INSERT INTO institutes (id, name, city, city_tier, exam_focus) VALUES (%s,%s,'Patna','tier_2','jee_main')",
                    (iid, name))
    conn.close()
