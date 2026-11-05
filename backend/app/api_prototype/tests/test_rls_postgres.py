"""E13, row-level-security half. Runs ONLY against a throw-away PostgreSQL started by pg_cluster.py.
If none can start these tests are skipped, and the log must say 'not run'."""
import psycopg2
import pytest

from app.api_prototype.pg_repository import PostgresRepository

from .conftest import A, INST_A, INST_B, R, build, item_for, serve
from .pg_cluster import PROTO_TABLES

pytestmark = pytest.mark.usefixtures("pg")


@pytest.fixture
def world(pg):
    if pg is None:
        pytest.skip("no throw-away PostgreSQL available: RLS tests NOT RUN")
    repo, client = build(pg=pg)
    for inst, learner, ev in ((INST_A, "a-stu1", "a-ev-0"), (INST_B, "b-stu1", "b-ev-0")):
        serve(repo, learner, A, inst=inst)
        repo.append_event(inst, learner, ev, A, item_for(A), True)
    return pg, repo


_OPEN = []


@pytest.fixture(autouse=True)
def _close_connections():
    """A failing assertion must not leave a transaction open: it would block the next test's reset."""
    yield
    while _OPEN:
        try:
            _OPEN.pop().close()
        except Exception:
            pass


def as_tenant(pg, institute_id, role="app_user"):
    """A raw connection in a transaction acting as app_user with app.institute_id set (or not)."""
    conn = pg.connect("proto_test")
    _OPEN.append(conn)
    cur = conn.cursor()
    cur.execute(f"SET LOCAL ROLE {role}")
    if institute_id is not None:
        cur.execute("SELECT set_config('app.institute_id', %s, true)", (institute_id,))
    return conn, cur


def count(cur, table, where=""):
    cur.execute(f"SELECT count(*) FROM {table} {where}")
    return cur.fetchone()[0]


def test_app_user_cannot_bypass_rls_and_all_tables_force_it(world):
    pg, _ = world
    conn = pg.connect("proto_test"); _OPEN.append(conn); cur = conn.cursor()
    cur.execute("SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname='app_user'")
    assert cur.fetchone() == (False, False)
    cur.execute("SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = ANY(%s)", (PROTO_TABLES,))
    rows = cur.fetchall()
    assert {r[0] for r in rows} == set(PROTO_TABLES) and all(r[1] and r[2] for r in rows)
    cur.execute("SELECT tablename FROM pg_policies WHERE policyname LIKE '%%_tenant_isolation' AND tablename = ANY(%s)", (PROTO_TABLES,))
    assert {r[0] for r in cur.fetchall()} == set(PROTO_TABLES)
    conn.close()


@pytest.mark.parametrize("table", PROTO_TABLES)
def test_context_b_sees_no_institute_a_rows(world, table):
    pg, _ = world
    conn, cur = as_tenant(pg, INST_B)
    assert count(cur, table, f"WHERE institute_id = '{INST_A}'") == 0     # asking for A explicitly
    assert count(cur, table, f"WHERE institute_id <> '{INST_B}'") == 0
    own = count(cur, table)
    conn.close()
    conn, cur = as_tenant(pg, INST_A)
    assert count(cur, table, f"WHERE institute_id = '{INST_A}'") == count(cur, table) > 0
    assert own > 0
    conn.close()


@pytest.mark.parametrize("setting", [None, "", "not-a-uuid-sees-error"])
def test_no_context_sees_nothing(world, setting):
    pg, _ = world
    conn, cur = as_tenant(pg, setting if setting != "not-a-uuid-sees-error" else None)
    if setting == "not-a-uuid-sees-error":
        cur.execute("SELECT set_config('app.institute_id', 'garbage', true)")
        with pytest.raises(psycopg2.Error):   # a malformed id fails closed (cast error), never open
            cur.execute("SELECT count(*) FROM proto_learners")
    else:
        for t in PROTO_TABLES:
            assert count(cur, t) == 0
    conn.close()


@pytest.mark.parametrize("sql", [
    "INSERT INTO proto_users VALUES ('{a}', 'x-user', 'teacher')",
    "INSERT INTO proto_cohorts VALUES ('{a}', 'x-cohort')",
    "INSERT INTO proto_learners (institute_id, learner_id, cohort_id, goal) VALUES ('{a}', 'x', NULL, 'g')",
    "INSERT INTO attempt_events VALUES ('{a}', 'x-ev', 'a-stu1', 'c', 'i', true, 99)",
    "INSERT INTO proto_served_items (institute_id, learner_id, item_id, concept_id, kind) VALUES ('{a}', 'a-stu1', 'zz', 'c', 'practice')",
    "INSERT INTO proto_cohort_teachers VALUES ('{a}', 'cohort-A', 'u-a-teacher2')",
])
def test_context_b_cannot_write_institute_a_rows(world, sql):
    pg, _ = world
    conn, cur = as_tenant(pg, INST_B)
    with pytest.raises(psycopg2.Error) as e:      # RLS WITH CHECK violation (or an FK that RLS cannot see)
        cur.execute(sql.format(a=INST_A))
    assert "row-level security" in str(e.value) or "foreign key" in str(e.value)
    conn.close()


def test_context_b_update_and_delete_of_a_rows_change_nothing(world):
    pg, _ = world
    conn, cur = as_tenant(pg, INST_B)
    cur.execute(f"UPDATE proto_learners SET day_counter = 99, goal = 'hijack' WHERE institute_id = '{INST_A}'")
    assert cur.rowcount == 0
    cur.execute(f"UPDATE proto_learners SET day_counter = 99 WHERE learner_id = 'a-stu1'")
    assert cur.rowcount == 0
    cur.execute(f"DELETE FROM proto_learners WHERE institute_id = '{INST_A}'")
    assert cur.rowcount == 0
    cur.execute(f"DELETE FROM proto_served_items WHERE institute_id = '{INST_A}'")
    assert cur.rowcount == 0
    cur.execute(f"DELETE FROM proto_cohort_teachers WHERE institute_id = '{INST_A}'")
    assert cur.rowcount == 0
    conn.close()
    assert PostgresRepository(host=pg.sock, dbname="proto_test", user=pg.superuser).day_of(INST_A, "a-stu1") == 1


def test_a_query_that_forgot_its_where_clause_still_sees_only_its_own_institute(world):
    pg, _ = world
    conn, cur = as_tenant(pg, INST_B)
    cur.execute("SELECT institute_id::text, learner_id FROM proto_learners")
    assert {r[0] for r in cur.fetchall()} == {INST_B}
    cur.execute("SELECT DISTINCT institute_id::text FROM attempt_events")
    assert [r[0] for r in cur.fetchall()] == [INST_B]
    conn.close()


def test_attempt_events_is_append_only_for_the_app_role(world):
    pg, _ = world
    for sql in ("UPDATE attempt_events SET correct = false", "DELETE FROM attempt_events"):
        conn, cur = as_tenant(pg, INST_A)
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute(sql)
        conn.close()


def test_repository_returns_nothing_across_institutes(world):
    pg, repo = world
    assert repo.get_learner(INST_B, "a-stu1") is None
    assert repo.get_cohort(INST_B, "cohort-A") is None or repo.cohort_learner_ids(INST_B, "cohort-A") == []
    assert repo.events_for(INST_B, "a-stu1") == [] and repo.served_for(INST_B, "a-stu1") == []
    assert repo.day_of(INST_B, "a-stu1") == 0
    assert repo.get_user_role(INST_B, "u-a-teacher") is None
    assert not repo.is_teacher_assigned(INST_B, "cohort-A", "u-a-teacher")
    with pytest.raises(LookupError):
        repo.append_event(INST_B, "a-stu1", "evil", A, item_for(A), True)
    assert len(repo.events_for(INST_A, "a-stu1")) == 1


def test_repository_treats_a_non_uuid_institute_as_nothing(world):
    _, repo = world
    for bad in ("inst-A", "", "' OR 1=1 --", "00000000-0000-0000-0000-000000000000"):
        assert repo.get_learner(bad, "a-stu1") is None
        assert repo.events_for(bad, "a-stu1") == []


def test_set_local_does_not_leak_to_the_next_transaction_on_a_connection(world):
    pg, repo = world
    conn = pg.connect("proto_test"); _OPEN.append(conn)
    cur = conn.cursor()
    cur.execute("SET LOCAL ROLE app_user")
    cur.execute("SELECT set_config('app.institute_id', %s, true)", (INST_A,))
    cur.execute("SELECT count(*) FROM proto_learners")
    assert cur.fetchone()[0] > 0
    conn.commit()
    cur.execute("SELECT current_setting('app.institute_id', true), current_user")
    setting, user = cur.fetchone()
    assert setting in (None, "") and user == pg.superuser     # role and tenant both reset at commit
    conn.close()


def test_api_over_postgres_denies_a_bug_that_skips_the_lookup(world):
    """Second layer: even a handler that fetched events by learner id alone, under B's context, gets nothing."""
    pg, repo = world
    with repo.tx(INST_B) as cur:
        cur.execute("SELECT count(*) FROM attempt_events WHERE learner_id = 'a-stu1'")
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT count(*) FROM attempt_events WHERE learner_id = 'b-stu1'")
        assert cur.fetchone()[0] == 1
