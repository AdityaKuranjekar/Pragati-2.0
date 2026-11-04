# Purpose: Phase 0 & 0b Contract Validation Suite (14 tests including embedded PostgreSQL 16.2 RLS isolation).
# contract_version: 1.0.0
# Implements: TECH_PLAN §18 (Testing strategy), P0_contracts.md, and P0b_contract_fixes.md.

import csv
import datetime
import json
import math
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import jsonschema
import pandas as pd
import pglast
import psycopg2
import pytest
import yaml
from openapi_spec_validator import validate as validate_openapi

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"

GLOBAL_READONLY_TABLES = {"topics", "topic_prereqs", "model_registry", "marking_schemes"}


def _load_yaml(path: Path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Test 1: SQL parses (pglast) with no Postgres; no CREATE EXTENSION
# ---------------------------------------------------------------------------
def test_01_sql_parses_with_pglast():
    sql_text = (CONTRACTS / "schema.sql").read_text(encoding="utf-8")
    assert "CREATE EXTENSION" not in sql_text.upper(), (
        "schema.sql must not contain CREATE EXTENSION (gen_random_uuid() is built into PG 13+)"
    )

    stmts = pglast.parse_sql(sql_text)
    assert len(stmts) >= 150, f"Expected full DDL in schema.sql, got {len(stmts)} statements"

    # Also ensure deliberately excluded concepts are documented in the header and absent as columns
    assert "DELIBERATELY NOT STORED" in sql_text
    create_tables = [s.stmt for s in stmts if s.stmt.__class__.__name__ == "CreateStmt"]
    assert len(create_tables) == 31, f"Expected all 31 tables from TECH_PLAN §8, found {len(create_tables)}"


# ---------------------------------------------------------------------------
# Test 2: RLS coverage on every table with an institute_id column + global readonly tables
# ---------------------------------------------------------------------------
def test_02_rls_coverage_static():
    sql_text = (CONTRACTS / "schema.sql").read_text(encoding="utf-8")
    stmts = pglast.parse_sql(sql_text)

    tables_with_institute_id = set()
    all_tables = set()
    rls_enabled = set()
    rls_forced = set()
    policies_by_table = {}

    for raw in stmts:
        node = raw.stmt
        cls_name = node.__class__.__name__
        if cls_name == "CreateStmt":
            tname = node.relation.relname
            all_tables.add(tname)
            for elt in node.tableElts or ():
                if elt.__class__.__name__ == "ColumnDef" and elt.colname == "institute_id":
                    tables_with_institute_id.add(tname)
        elif cls_name == "AlterTableStmt":
            tname = node.relation.relname
            for cmd in node.cmds or ():
                subtype_name = repr(cmd.subtype)
                if "EnableRowSecurity" in subtype_name:
                    rls_enabled.add(tname)
                elif "ForceRowSecurity" in subtype_name:
                    rls_forced.add(tname)
        elif cls_name == "CreatePolicyStmt":
            tname = node.table.relname
            policies_by_table.setdefault(tname, []).append(node.policy_name)

    # Every table is either in GLOBAL_READONLY_TABLES or is a tenant table (institutes + tables_with_institute_id)
    tenant_tables = tables_with_institute_id | {"institutes"}
    assert all_tables == (tenant_tables | GLOBAL_READONLY_TABLES), (
        f"Unclassified tables: {all_tables - (tenant_tables | GLOBAL_READONLY_TABLES)}"
    )
    assert "question_topics" in tables_with_institute_id
    assert "item_params" in tables_with_institute_id

    for tname in sorted(tenant_tables):
        assert tname in rls_enabled, f"Table {tname} missing ENABLE ROW LEVEL SECURITY"
        assert tname in rls_forced, f"Table {tname} missing FORCE ROW LEVEL SECURITY"
        assert tname in policies_by_table and len(policies_by_table[tname]) >= 1, (
            f"Table {tname} has no CREATE POLICY statement"
        )
        assert f"ON {tname}" in sql_text and "current_setting('app.institute_id'" in sql_text

    for tname in sorted(GLOBAL_READONLY_TABLES):
        assert tname in rls_enabled, f"Global table {tname} missing ENABLE ROW LEVEL SECURITY"
        assert tname in policies_by_table and len(policies_by_table[tname]) >= 1, (
            f"Global table {tname} missing SELECT policy"
        )


# ---------------------------------------------------------------------------
# Test 3 (plus 1b & 2b): Real Postgres 16 (via pgserver or Docker) & tenant isolation smoke test (-m db)
# ---------------------------------------------------------------------------
def _pgserver_available() -> bool:
    try:
        import pgserver  # noqa: F401
        return True
    except Exception:
        return False


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        res = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


def _run_live_db_assertions(uri: str):
    sql_text = (CONTRACTS / "schema.sql").read_text(encoding="utf-8")

    conn = psycopg2.connect(uri)
    conn.autocommit = True
    cur = conn.cursor()
    try:
        # 1. Apply schema.sql cleanly and assert all 31 tables exist
        cur.execute(sql_text)
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;"
        )
        public_tables = {r[0] for r in cur.fetchall()}
        assert len(public_tables) == 31, f"Expected 31 tables, got {len(public_tables)}: {public_tables}"

        # 2. Assert every table is either tenant-scoped (ENABLE + FORCE RLS + policy)
        #    or in GLOBAL_READONLY_TABLES (ENABLE RLS + app_user has only SELECT)
        cur.execute(
            """
            SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
                   (SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid) AS pol_count
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r';
            """
        )
        rls_info = {r[0]: (r[1], r[2], r[3]) for r in cur.fetchall()}
        for tname in public_tables:
            relrow, relforce, pol_count = rls_info[tname]
            assert relrow is True, f"Table {tname} does not have relrowsecurity = true"
            assert pol_count >= 1, f"Table {tname} has 0 policies in pg_policy"
            if tname in GLOBAL_READONLY_TABLES:
                cur.execute(
                    """
                    SELECT privilege_type
                    FROM information_schema.role_table_grants
                    WHERE table_schema = 'public' AND table_name = %s AND grantee = 'app_user';
                    """,
                    (tname,),
                )
                privs = {r[0] for r in cur.fetchall()}
                assert privs == {"SELECT"}, f"Global table {tname} should grant only SELECT to app_user, got {privs}"
            else:
                assert relforce is True, f"Tenant table {tname} does not have relforcerowsecurity = true"

        # 4. Assert app_user is not a superuser and does not have BYPASSRLS
        cur.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'app_user';")
        rolsuper, rolbypassrls = cur.fetchone()
        assert rolsuper is False, "app_user must not be a superuser"
        assert rolbypassrls is False, "app_user must not have BYPASSRLS"

        # 3. Seed global rows + two institutes (A and B) with batches, students, private questions,
        #    and their item_params + question_topics rows
        inst_a = "11111111-1111-1111-1111-111111111111"
        inst_b = "22222222-2222-2222-2222-222222222222"
        batch_a = "aaaaaaaa-1111-1111-1111-111111111111"
        batch_b = "bbbbbbbb-2222-2222-2222-222222222222"
        stud_a = "cccccccc-1111-1111-1111-111111111111"
        stud_b = "dddddddd-2222-2222-2222-222222222222"
        q_priv_a = "eeeeeeee-1111-1111-1111-111111111111"
        q_priv_b = "ffffffff-2222-2222-2222-222222222222"

        cur.execute(
            """
            INSERT INTO topics (id, exam, subject, chapter, topic, name_en, name_hi, name_hi_reviewed, parent_id, class_level, syllabus_year, verified)
            VALUES ('jee.phy', 'jee_main', 'Physics', 'Physics', 'Physics', 'Physics', 'भौतिक विज्ञान', false, NULL, 'class_11', 2026, false);

            INSERT INTO model_registry (version, trained_at, data_version, metrics)
            VALUES ('v1.0.0', '2026-10-20T18:00:00+05:30', 'seed42', '{}'::jsonb);

            INSERT INTO marking_schemes (id, name, correct, wrong, blank, partial_rule, dropped_rule)
            VALUES ('jee_main', 'JEE Main', 4, -1, 0, 'full_marks_if_any_accepted', 'full_marks_all');

            INSERT INTO institutes (id, name, city, city_tier, exam_focus, plan) VALUES
              (%s, 'Inst A', 'Patna', 'tier_2', 'jee_main', 'standard'),
              (%s, 'Inst B', 'Kota',  'tier_2', 'jee_main', 'standard');

            INSERT INTO batches (id, institute_id, name, class_level, exam, academic_year, start_date) VALUES
              (%s, %s, 'Batch A', 'class_11', 'jee_main', 2026, '2026-04-15'),
              (%s, %s, 'Batch B', 'class_11', 'jee_main', 2026, '2026-04-15');

            INSERT INTO students (id, institute_id, batch_id, academic_year, roll_no, name, dob, gender, join_date) VALUES
              (%s, %s, %s, 2026, 'R1', 'Aarav Test', '2009-05-14', 'male', '2026-04-15'),
              (%s, %s, %s, 2026, 'R1', 'Rohan Demo', '2009-05-14', 'male', '2026-04-15');

            INSERT INTO questions (id, institute_id, subject, text_hash, q_type, options_n) VALUES
              (%s, %s, 'Physics', 'hash_priv_a', 'mcq_single', 4),
              (%s, %s, 'Physics', 'hash_priv_b', 'mcq_single', 4);

            INSERT INTO question_topics (institute_id, question_id, topic_id, weight, tagged_by, confidence) VALUES
              (%s, %s, 'jee.phy', 1.0, 'human', 1.0),
              (%s, %s, 'jee.phy', 1.0, 'human', 1.0);

            INSERT INTO item_params (institute_id, question_id, model_version, a, b, g, se_b, n_responses, fit_flag) VALUES
              (%s, %s, 'v1.0.0', 1.1, 0.2, 0.1, 0.15, 100, 'ok'),
              (%s, %s, 'v1.0.0', 1.2, -0.3, 0.1, 0.15, 100, 'suspect_wrong_key');
            """,
            (
                inst_a, inst_b,
                batch_a, inst_a, batch_b, inst_b,
                stud_a, inst_a, batch_a, stud_b, inst_b, batch_b,
                q_priv_a, inst_a, q_priv_b, inst_b,
                inst_a, q_priv_a, inst_b, q_priv_b,
                inst_a, q_priv_a, inst_b, q_priv_b,
            ),
        )

        # Verify trigger rejects mismatched institute_id between question and question_topics / item_params
        with pytest.raises(psycopg2.Error):
            cur.execute(
                "INSERT INTO item_params (institute_id, question_id, model_version, a, b, g, se_b, n_responses, fit_flag) "
                "VALUES (%s, %s, 'v1.0.0', 1.0, 0.0, 0.1, 0.1, 10, 'ok');",
                (inst_a, q_priv_b),
            )
        with pytest.raises(psycopg2.Error):
            cur.execute(
                "INSERT INTO item_params (institute_id, question_id, model_version, a, b, g, se_b, n_responses, fit_flag) "
                "VALUES (NULL, %s, 'v1.0.0', 1.0, 0.0, 0.1, 0.1, 10, 'ok');",
                (q_priv_b,),
            )

        # Switch to app_user and test with GUC set to Institute A
        cur.execute("SET ROLE app_user;")
        cur.execute("SET app.institute_id = %s;", (inst_a,))

        # A sees exactly its own rows in every seeded tenant table (including item_params and question_topics)
        cur.execute("SELECT id FROM institutes;")
        assert [r[0] for r in cur.fetchall()] == [inst_a]

        cur.execute("SELECT id FROM batches;")
        assert [r[0] for r in cur.fetchall()] == [batch_a]

        cur.execute("SELECT id FROM students;")
        assert [r[0] for r in cur.fetchall()] == [stud_a]

        cur.execute("SELECT id FROM questions;")
        assert [r[0] for r in cur.fetchall()] == [q_priv_a]

        cur.execute("SELECT question_id FROM question_topics;")
        assert [r[0] for r in cur.fetchall()] == [q_priv_a]

        cur.execute("SELECT question_id FROM item_params;")
        assert [r[0] for r in cur.fetchall()] == [q_priv_a]

        # A cannot SELECT B's student by id (0 rows)
        cur.execute("SELECT count(*) FROM students WHERE id = %s;", (stud_b,))
        assert cur.fetchone()[0] == 0

        # A cannot INSERT a row carrying B's institute_id (RLS WITH CHECK error)
        with pytest.raises(psycopg2.Error):
            cur.execute(
                "INSERT INTO batches (id, institute_id, name, class_level, exam, academic_year, start_date) "
                "VALUES ('99999999-2222-2222-2222-222222222222', %s, 'Hack', 'class_11', 'jee_main', 2026, '2026-04-15');",
                (inst_b,),
            )

        # A cannot INSERT a shared (institute_id IS NULL) question as app_user
        with pytest.raises(psycopg2.Error):
            cur.execute(
                "INSERT INTO questions (id, institute_id, subject, text_hash, q_type, options_n) "
                "VALUES ('99999999-0000-0000-0000-000000000000', NULL, 'Physics', 'hack_shared', 'mcq_single', 4);"
            )

        # A cannot modify global read-only tables
        for gtable in GLOBAL_READONLY_TABLES:
            with pytest.raises(psycopg2.Error):
                cur.execute(f"DELETE FROM {gtable};")

        # UPDATE / DELETE on B's rows affect 0 rows
        cur.execute("UPDATE students SET name = 'Hacked' WHERE id = %s;", (stud_b,))
        assert cur.rowcount == 0
        cur.execute("DELETE FROM students WHERE id = %s;", (stud_b,))
        assert cur.rowcount == 0
        cur.execute("UPDATE item_params SET b = 9.9 WHERE question_id = %s;", (q_priv_b,))
        assert cur.rowcount == 0
        cur.execute("DELETE FROM question_topics WHERE question_id = %s;", (q_priv_b,))
        assert cur.rowcount == 0

        # With the GUC unset or empty (''), every tenant table returns 0 rows
        for empty_val in ("RESET", "EMPTY"):
            if empty_val == "RESET":
                cur.execute("RESET app.institute_id;")
            else:
                cur.execute("SET app.institute_id = '';")

            for tname in sorted(public_tables - GLOBAL_READONLY_TABLES):
                cur.execute(f"SELECT count(*) FROM {tname};")
                cnt = cur.fetchone()[0]
                assert cnt == 0, f"Tenant table {tname} returned {cnt} rows when GUC was {empty_val}"
    finally:
        cur.close()
        conn.close()


@pytest.mark.db
def test_03_db_container_and_tenant_isolation():
    if _pgserver_available():
        import pgserver

        tmp_dir = tempfile.mkdtemp(prefix="datamoat_pg16_")
        db = pgserver.get_server(tmp_dir)
        try:
            _run_live_db_assertions(db.get_uri())
        finally:
            try:
                db.cleanup()
            except Exception:
                pass
            shutil.rmtree(tmp_dir, ignore_errors=True)
    elif _docker_available():
        container_name = f"datamoat_pg16_test_{int(time.time())}"
        try:
            subprocess.run(
                [
                    "docker", "run", "-d", "--rm",
                    "--name", container_name,
                    "-p", "55439:5432",
                    "-e", "POSTGRES_PASSWORD=postgres",
                    "-e", "POSTGRES_DB=datamoat_test",
                    "postgres:16-alpine",
                ],
                check=True,
            )
            for _ in range(30):
                r = subprocess.run(
                    ["docker", "exec", container_name, "pg_isready", "-U", "postgres"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                if r.returncode == 0:
                    break
                time.sleep(1)
            _run_live_db_assertions("postgresql://postgres:postgres@127.0.0.1:55439/datamoat_test")
        finally:
            subprocess.run(["docker", "rm", "-f", container_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        pytest.skip("SKIPPED: Neither pgserver nor Docker is available on this host to run -m db tests.")


# ---------------------------------------------------------------------------
# Test 4: Enum consistency (enums.yaml == SQL CHECK == OpenAPI == data_dictionary)
# ---------------------------------------------------------------------------
def test_04_enum_consistency():
    enums_doc = _load_yaml(CONTRACTS / "enums.yaml")["enums"]
    sql_text = (CONTRACTS / "schema.sql").read_text(encoding="utf-8")
    openapi_doc = _load_yaml(CONTRACTS / "openapi.yaml")
    data_dict_text = (CONTRACTS / "data_dictionary.md").read_text(encoding="utf-8")

    # 1. Verify batch_change_reason has no "performance"
    assert "performance" not in enums_doc["batch_change_reason"]["values"]

    # 2. Extract all CHECK (... IN ('v1', 'v2', ...)) sets from schema.sql
    check_pattern = re.compile(r"CHECK\s*\(\s*[a-z0-9_]+\s+IN\s*\(([^)]+)\)\s*\)")
    sql_enum_tuples = set()
    for match in check_pattern.finditer(sql_text):
        raw_vals = [v.strip().strip("'") for v in match.group(1).split(",")]
        sql_enum_tuples.add(tuple(raw_vals))

    yaml_enum_tuples = {tuple(v["values"]) for v in enums_doc.values()}
    # Every SQL IN-list CHECK constraint must match an enum in enums.yaml
    for sq_t in sql_enum_tuples:
        assert sq_t in yaml_enum_tuples, f"SQL CHECK constraint {sq_t} not found in enums.yaml"

    # 3. Every enum in enums.yaml must match its corresponding `<key>_enum` in OpenAPI components.schemas
    oa_schemas = openapi_doc["components"]["schemas"]
    for enum_key, spec in enums_doc.items():
        oa_name = f"{enum_key}_enum"
        assert oa_name in oa_schemas, f"Missing {oa_name} in openapi.yaml components.schemas"
        assert oa_schemas[oa_name]["enum"] == spec["values"], (
            f"Mismatch for {enum_key} between enums.yaml and openapi.yaml"
        )

    # 4. Every enum in enums.yaml must appear with exact values in data_dictionary.md §2 table
    for enum_key, spec in enums_doc.items():
        expected_vals_str = ", ".join(f"`{val}`" for val in spec["values"])
        expected_row_prefix = f"| `{enum_key}` | {expected_vals_str} |"
        assert expected_row_prefix in data_dict_text, (
            f"Missing or mismatched row in data_dictionary.md for enum {enum_key}"
        )


# ---------------------------------------------------------------------------
# Test 5: OpenAPI valid + operationId, 200 example, Problem responses, security, model_version
# ---------------------------------------------------------------------------
def test_05_openapi_valid_and_complete():
    openapi_doc = _load_yaml(CONTRACTS / "openapi.yaml")
    assert openapi_doc["openapi"].startswith("3.1.")
    validate_openapi(openapi_doc)

    # Required endpoints from TECH_PLAN §13
    expected_paths = {
        "/auth/login", "/me",
        "/ingest/students", "/ingest/results", "/ingest/omr",
        "/ingest/omr/{job}/confirm", "/ingest/jobs/{id}",
        "/batches/{id}/heatmap", "/batches/{id}/support-list", "/batches/{id}/summary",
        "/students/{id}/profile", "/students/{id}/attendance", "/students/{id}/fees",
        "/students/{id}/interventions", "/interventions/{id}",
        "/students/{id}/reports",
        "/tests/{id}/flagged-questions", "/answer-keys/{test}/{q}",
        "/owner/dashboard", "/consents", "/consents/{id}", "/settings/privacy-tier",
        "/health", "/version",
    }
    assert expected_paths.issubset(set(openapi_doc["paths"].keys()))
    assert "delete" not in openapi_doc["paths"]["/consents"], "DELETE must be on /consents/{id}, not /consents"
    assert "delete" in openapi_doc["paths"]["/consents/{id}"]
    assert openapi_doc["paths"]["/consents/{id}"]["delete"]["operationId"] == "revoke_consent"

    oa_schemas = openapi_doc["components"]["schemas"]
    operation_ids = set()

    model_output_schemas = [
        "omr_ingest_response",
        "batch_heatmap_response",
        "support_list_response",
        "batch_summary_response",
        "student_profile_response",
        "report_generate_response",
        "flagged_questions_response",
        "answer_key_update_response",
        "owner_dashboard_response",
        "privacy_tier_settings_response",
        "version_response",
    ]
    for sname in model_output_schemas:
        props = oa_schemas[sname]["properties"]
        assert "model_version" in props, f"Schema {sname} carries model output but lacks model_version"
        assert "model_version" in oa_schemas[sname]["required"]

    for path, methods in openapi_doc["paths"].items():
        for method, op in methods.items():
            op_id = op.get("operationId")
            assert op_id, f"{method.upper()} {path} missing operationId"
            assert op_id not in operation_ids, f"Duplicate operationId {op_id}"
            operation_ids.add(op_id)

            assert op.get("tags"), f"{op_id} missing tags"
            assert op.get("security"), f"{op_id} missing security declaration"
            assert "Role filtering:" in op.get("description", ""), f"{op_id} missing documented role filtering"

            resps = op.get("responses", {})
            assert "200" in resps, f"{op_id} missing 200 response"
            content_200 = resps["200"]["content"]["application/json"]
            assert "schema" in content_200, f"{op_id} 200 response missing schema"
            assert "example" in content_200, f"{op_id} 200 response missing example"

            for err_code in ("401", "403", "404", "422"):
                assert err_code in resps, f"{op_id} missing {err_code} Problem response"
                err_schema = resps[err_code]["content"]["application/problem+json"]["schema"]
                assert err_schema.get("$ref") == "#/components/schemas/problem"


# ---------------------------------------------------------------------------
# Test 6: Every YAML/JSON validates against its schema in contracts/schemas/
# ---------------------------------------------------------------------------
def test_06_yaml_and_json_validate_against_schemas():
    yaml_to_schema = [
        ("enums.yaml", "schemas/enums.schema.json"),
        ("topics.yaml", "schemas/topics.schema.json"),
        ("exam_patterns.yaml", "schemas/exam_patterns.schema.json"),
        ("marking_schemes.yaml", "schemas/marking_schemes.schema.json"),
        ("features.yaml", "schemas/features.schema.json"),
        ("routing_policy.yaml", "schemas/routing_policy.schema.json"),
        ("reason_templates.yaml", "schemas/reason_templates.schema.json"),
        ("csv_templates/header_synonyms.yaml", "schemas/header_synonyms.schema.json"),
        ("datasets.yaml", "schemas/datasets.schema.json"),
        ("metrics_bars.yaml", "schemas/metrics_bars.schema.json"),
    ]
    for y_rel, s_rel in yaml_to_schema:
        instance = _load_yaml(CONTRACTS / y_rel)
        schema = _load_json(CONTRACTS / s_rel)
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(instance=instance, schema=schema)

    # Also validate standalone JSON schemas and OMR layouts
    standalone_schemas = [
        "report_numbers.schema.json",
        "report_output.schema.json",
        "omr_template.schema.json",
        "artifact_manifest.schema.json",
        "metrics.schema.json",
    ]
    for s_rel in standalone_schemas:
        schema = _load_json(CONTRACTS / s_rel)
        jsonschema.Draft202012Validator.check_schema(schema)

    omr_schema = _load_json(CONTRACTS / "omr_template.schema.json")
    for layout_file in (CONTRACTS / "omr_layouts").glob("*.json"):
        layout_doc = _load_json(layout_file)
        clean_doc = {k: v for k, v in layout_doc.items() if k != "$comment"}
        jsonschema.validate(instance=clean_doc, schema=omr_schema)


# ---------------------------------------------------------------------------
# Test 7: CSV templates match data_dictionary, parse with declared types, and have >= 5 synonyms
# ---------------------------------------------------------------------------
def test_07_csv_templates_and_synonyms():
    synonyms_doc = _load_yaml(CONTRACTS / "csv_templates" / "header_synonyms.yaml")
    col_synonyms = synonyms_doc["column_synonyms"]
    data_dict_text = (CONTRACTS / "data_dictionary.md").read_text(encoding="utf-8")

    expected_csvs = {
        "students.csv": [
            ("roll_no", str), ("name", str), ("name_alt", str), ("dob", "date"),
            ("gender", str), ("class_level", str), ("exam", str), ("batch_name", str),
            ("join_date", "date"), ("fee_plan", str), ("out_of_town", "bool")
        ],
        "guardians.csv": [
            ("roll_no", str), ("guardian_name", str), ("phone", str),
            ("relation", str), ("lang_pref", str)
        ],
        "results_responses_wide.csv": [
            ("test_name", str), ("test_date", "date"), ("roll_no", str),
            ("q1", str), ("q2", str), ("q3", str), ("q4", str), ("q5", str)
        ],
        "results_marks_only.csv": [
            ("test_name", str), ("test_date", "date"), ("roll_no", str),
            ("raw_score", "float_opt"), ("physics_score", "float_opt"),
            ("chemistry_score", "float_opt"), ("math_or_bio_score", "float_opt"),
            ("absent_flag", "bool")
        ],
        "answer_key.csv": [
            ("question_no", "int"), ("q_type", str), ("subject", str),
            ("topic_id", str), ("accepted_answers", str),
            ("numeric_tolerance", "float"), ("dropped", "bool")
        ],
        "attendance.csv": [
            ("roll_no", str), ("attendance_date", "date"),
            ("present_flag", "bool"), ("source", str)
        ],
        "fees.csv": [
            ("roll_no", str), ("instalment_no", "int"), ("due_date", "date"),
            ("amount_paise", "int"), ("paid_date", "date_opt"),
            ("paid_amount_paise", "int"), ("refund_due_paise", "int"),
            ("refund_paid_date", "date_opt")
        ],
    }

    for fname, col_specs in expected_csvs.items():
        fpath = CONTRACTS / "csv_templates" / fname
        assert fpath.exists(), f"Missing CSV template {fname}"
        assert f"CSV Template: `{fname}`" in data_dict_text

        lines = [
            line for line in fpath.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        reader = list(csv.reader(lines))
        headers = reader[0]
        rows = reader[1:]

        expected_headers = [c[0] for c in col_specs]
        assert headers == expected_headers, f"Header mismatch in {fname}: {headers} != {expected_headers}"
        assert len(rows) == 3, f"Expected 3 synthetic example rows in {fname}, found {len(rows)}"

        for col_name, _ in col_specs:
            assert f"| `{col_name}` |" in data_dict_text, f"Column {col_name} missing from data_dictionary.md"
            assert col_name in col_synonyms, f"Column {col_name} missing from header_synonyms.yaml"
            assert len(col_synonyms[col_name]) >= 5, (
                f"Column {col_name} has fewer than 5 synonyms in header_synonyms.yaml"
            )

        for row in rows:
            assert len(row) == len(col_specs)
            for val, (col_name, dtype) in zip(row, col_specs):
                if dtype == "int":
                    int(val)
                elif dtype == "float":
                    float(val)
                elif dtype == "float_opt":
                    if val != "":
                        float(val)
                elif dtype == "bool":
                    assert val in ("true", "false")
                elif dtype == "date":
                    datetime.date.fromisoformat(val)
                elif dtype == "date_opt":
                    if val != "":
                        datetime.date.fromisoformat(val)


# ---------------------------------------------------------------------------
# Test 8: Topics graph (unique ids, parents exist, Devanagari name_hi, DAG, counts)
# ---------------------------------------------------------------------------
def test_08_topics_graph():
    doc = _load_yaml(CONTRACTS / "topics.yaml")
    topics = doc["topics"]
    prereqs = doc["topic_prereqs"]

    ids = [t["id"] for t in topics]
    assert len(ids) == len(set(ids)), "Duplicate topic IDs found in topics.yaml"
    id_set = set(ids)

    devanagari_re = re.compile(r"[\u0900-\u097F]")
    chapters_by_subject = {}
    topics_by_chapter = {}

    for t in topics:
        if t["parent_id"] is not None:
            assert t["parent_id"] in id_set, f"Missing parent_id {t['parent_id']} for {t['id']}"
        assert t["name_hi"].strip(), f"Empty name_hi for {t['id']}"
        assert devanagari_re.search(t["name_hi"]), f"name_hi for {t['id']} lacks Devanagari characters: {t['name_hi']}"
        assert t["name_hi_reviewed"] is False, f"Topic {t['id']} must have name_hi_reviewed: false until reviewed"
        assert t["verified"] is False, "Unsourced NTA topic nodes must have verified: false"
        assert t["weightage"] is None, "Must not invent syllabus weightages"

        if t["level"] == "chapter":
            chapters_by_subject.setdefault(t["subject"], []).append(t["id"])
        elif t["level"] == "topic":
            topics_by_chapter.setdefault(t["parent_id"], []).append(t["id"])

    # Check chapter counts per subject (Physics 20, Chemistry 20, Mathematics 20, Biology=Botany+Zoology 32)
    assert 15 <= len(chapters_by_subject["Physics"]) <= 30
    assert 15 <= len(chapters_by_subject["Chemistry"]) <= 30
    assert 15 <= len(chapters_by_subject["Mathematics"]) <= 30
    bio_chapters = len(chapters_by_subject["Botany"]) + len(chapters_by_subject["Zoology"])
    assert 20 <= bio_chapters <= 35

    for ch_id, t_list in topics_by_chapter.items():
        assert 3 <= len(t_list) <= 8, f"Chapter {ch_id} has {len(t_list)} topics (expected 3..8)"

    # Verify prerequisite graph is a valid DAG
    adj = {}
    for edge in prereqs:
        u = edge["prereq_topic_id"]
        v = edge["topic_id"]
        assert u in id_set and v in id_set, f"Prereq references unknown topic: {edge}"
        adj.setdefault(u, []).append(v)

    visiting = set()
    visited = set()

    def dfs(node):
        visiting.add(node)
        for nxt in adj.get(node, ()):
            assert nxt not in visiting, f"Cycle detected in topic_prereqs involving {nxt}"
            if nxt not in visited:
                dfs(nxt)
        visiting.remove(node)
        visited.add(node)

    for n in list(adj.keys()):
        if n not in visited:
            dfs(n)

    # Verify contracts/topics_hi_review.csv matches topics.yaml 1-to-1
    review_csv_path = CONTRACTS / "topics_hi_review.csv"
    assert review_csv_path.exists(), "Missing contracts/topics_hi_review.csv"
    csv_lines = [
        line for line in review_csv_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    reader = list(csv.reader(csv_lines))
    assert reader[0] == ["id", "name_en", "name_hi", "reviewer", "status", "corrected_name_hi"]
    csv_rows = reader[1:]
    assert len(csv_rows) == len(topics), f"Expected {len(topics)} rows in topics_hi_review.csv, got {len(csv_rows)}"
    csv_ids = [r[0] for r in csv_rows]
    assert csv_ids == ids, "Topic IDs in topics_hi_review.csv must match topics.yaml 1-to-1"
    for r, t in zip(csv_rows, topics):
        assert r[1] == t["name_en"]
        assert r[2] == t["name_hi"]
        assert r[3] == ""
        assert r[4] == "pending"
        assert r[5] == ""


# ---------------------------------------------------------------------------
# Test 9: Exam patterns (computed max marks == declared max marks; NEET verified: false)
# ---------------------------------------------------------------------------
def test_09_exam_patterns():
    doc = _load_yaml(CONTRACTS / "exam_patterns.yaml")
    patterns = doc["patterns"]

    # JEE Main 2026
    jee = patterns["jee_main_2026"]
    assert jee["verified"] is True
    n_subj_jee = len(jee["subjects"])
    computed_jee = n_subj_jee * sum(
        s["questions_to_attempt"] * s["correct_marks"] for s in jee["sections_per_subject"]
    )
    assert computed_jee == jee["max_marks"] == 300

    # NEET-UG 2026 (verified: false + both variants)
    neet = patterns["neet_ug_2026"]
    assert neet["verified"] is False
    assert neet["default_variant"] == "compulsory_180"
    n_subj_neet = len(neet["subjects"])
    for vname in ("compulsory_180", "sectioned_200"):
        variant = neet["variants"][vname]
        computed_neet = n_subj_neet * sum(
            s["questions_to_attempt"] * s["correct_marks"] for s in variant["sections_per_subject"]
        )
        assert computed_neet == variant["max_marks"] == 720, (
            f"NEET variant {vname} computed {computed_neet} != {variant['max_marks']}"
        )

    # Internal chapter test
    chap = patterns["internal_chapter_test"]
    assert chap["verified"] is False
    assert chap["source"] == "assumption (ours)"
    computed_chap = len(chap["subjects"]) * sum(
        s["questions_to_attempt"] * s["correct_marks"] for s in chap["sections_per_subject"]
    )
    assert computed_chap == chap["max_marks"]

    # Rule: any pattern whose source does not start with https:// must have verified: false
    for pname, p in patterns.items():
        if not str(p.get("source", "")).startswith("https://"):
            assert p["verified"] is False, (
                f"Pattern {pname} has non-URL source '{p.get('source')}' but verified={p['verified']}"
            )


# ---------------------------------------------------------------------------
# Test 10: Percentile tables (monotone per (exam, year, session); percentiles in [0, 100])
# ---------------------------------------------------------------------------
def test_10_percentile_tables_monotone():
    lines = [
        line for line in (CONTRACTS / "percentile_tables.csv").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    df = pd.read_csv(pd.io.common.StringIO("\n".join(lines)))
    expected_cols = ["exam", "year", "session", "marks", "percentile", "rank_approx", "source", "confidence"]
    assert list(df.columns) == expected_cols

    assert (df["percentile"] >= 0.0).all() and (df["percentile"] <= 100.0).all()

    # Check NEET 2026 confidence == 'projected'
    neet_2026 = df[(df["exam"] == "neet_ug") & (df["year"] == 2026)]
    assert len(neet_2026) >= 8
    assert (neet_2026["confidence"] == "projected").all()

    # Check strict monotonicity: higher marks -> higher percentile (and lower rank_approx)
    for (exam, year, session), grp in df.groupby(["exam", "year", "session"]):
        sorted_grp = grp.sort_values("marks")
        marks_diff = sorted_grp["marks"].diff().dropna()
        pct_diff = sorted_grp["percentile"].diff().dropna()
        rank_diff = sorted_grp["rank_approx"].diff().dropna()
        assert (marks_diff > 0).all(), f"Duplicate marks in {(exam, year, session)}"
        assert (pct_diff > 0).all(), f"Non-monotone percentiles in {(exam, year, session)}"
        assert (rank_diff <= 0).all(), f"Non-monotone ranks in {(exam, year, session)}"


# ---------------------------------------------------------------------------
# Test 11: Features & legal routing policy consistency
# ---------------------------------------------------------------------------
def test_11_features_and_routing_policy():
    features_doc = _load_yaml(CONTRACTS / "features.yaml")
    routing_doc = _load_yaml(CONTRACTS / "routing_policy.yaml")
    reasons_doc = _load_yaml(CONTRACTS / "reason_templates.yaml")

    templates = reasons_doc["templates"]
    features_by_name = {f["name"]: f for f in features_doc["features"]}

    for f in features_doc["features"]:
        rt_key = f["reason_template_key"]
        assert rt_key in templates, f"Feature {f['name']} references unknown reason_template_key {rt_key}"
        assert templates[rt_key]["en"].strip() and templates[rt_key]["hi"].strip()
        if f["tier"] == "D":
            assert f["allowed_for_minor"] is False, f"Tier D feature {f['name']} must have allowed_for_minor: false"

    # Routing matrix checks: every (is_minor, minor_ml_risk_enabled, target) combination appears EXACTLY ONCE
    matrix_rows = routing_doc["routing_matrix"]
    expected_keys = {
        (is_minor, flag, target)
        for is_minor in (True, False)
        for flag in (False, True)
        for target in ("academic_support", "retention", "fee")
    }
    actual_keys = [
        (row["is_minor"], row["minor_ml_risk_enabled"], row["target"])
        for row in matrix_rows
    ]
    assert len(actual_keys) == 12, f"Expected 12 rows in routing_matrix, got {len(actual_keys)}"
    assert set(actual_keys) == expected_keys, "routing_matrix does not cover all 12 combinations exactly once"

    matrix = {
        (row["is_minor"], row["minor_ml_risk_enabled"], row["target"]): row
        for row in matrix_rows
    }

    # For is_minor=true and flag=false: retention -> rules, fee -> rules, academic_support -> ml with tiers <= {A}
    assert matrix[(True, False, "academic_support")]["method"] == "ml"
    assert set(matrix[(True, False, "academic_support")]["allowed_tiers"]).issubset({"A"})
    assert matrix[(True, False, "retention")]["method"] == "rules"
    assert matrix[(True, False, "fee")]["method"] == "rules"

    # For adults (is_minor=false): academic_support allows [A, B, D]
    assert matrix[(False, False, "academic_support")]["allowed_tiers"] == ["A", "B", "D"]
    assert matrix[(False, True, "academic_support")]["allowed_tiers"] == ["A", "B", "D"]

    # Tier D is never allowed for any minor row
    for (is_minor, _, _), row in matrix.items():
        if is_minor:
            assert "D" not in row["allowed_tiers"], f"Minor routing row allows Tier D: {row}"

    # Every rule's referenced feature and reason_template_key exist
    for rule in routing_doc["rules"]:
        assert rule["feature"] in features_by_name, f"Rule {rule['id']} references unknown feature {rule['feature']}"
        assert rule["reason_template_key"] in templates, (
            f"Rule {rule['id']} references unknown reason_template_key {rule['reason_template_key']}"
        )


# ---------------------------------------------------------------------------
# Test 12: Reason templates (EN and HI slots match; no banned words appear)
# ---------------------------------------------------------------------------
def test_12_reason_templates_slots_and_banned_words():
    reasons_doc = _load_yaml(CONTRACTS / "reason_templates.yaml")
    banned_en = [w.lower() for w in reasons_doc["banned_words"]["en"]]
    banned_hi = reasons_doc["banned_words"]["hi"]

    slot_re = re.compile(r"\{([a-z0-9_]+)\}")

    for key, tmpl in reasons_doc["templates"].items():
        declared_slots = {s["name"] for s in tmpl["slots"]}
        en_slots = set(slot_re.findall(tmpl["en"]))
        hi_slots = set(slot_re.findall(tmpl["hi"]))
        assert en_slots == hi_slots == declared_slots, (
            f"Slot mismatch in template {key}: declared={declared_slots}, en={en_slots}, hi={hi_slots}"
        )

        en_text_lower = (tmpl["en"] + " " + tmpl["action_text"]["en"]).lower()
        hi_text = tmpl["hi"] + " " + tmpl["action_text"]["hi"]

        for bw in banned_en:
            assert not re.search(rf"\b{re.escape(bw)}\b", en_text_lower), (
                f"Banned EN word '{bw}' found in template {key}"
            )
        for bw_hi in banned_hi:
            assert bw_hi not in hi_text, f"Banned HI word '{bw_hi}' found in template {key}"

        # No statistical jargon in mentor/parent reason templates
        for stat_jargon in ("standard deviation", "z-score", "z score", "मानक विचलन"):
            assert stat_jargon not in en_text_lower and stat_jargon not in hi_text, (
                f"Statistical jargon '{stat_jargon}' found in template {key}"
            )


# ---------------------------------------------------------------------------
# Test 13: OMR layouts (bubbles inside page, min gap >= 1 mm, question count, roll grid)
# ---------------------------------------------------------------------------
def test_13_omr_layouts_geometry():
    expected_counts = {
        "generic_mcq_100": 100,
        "neet_200": 200,
        "jee_75": 75,
    }
    for layout_name, exp_q in expected_counts.items():
        doc = _load_json(CONTRACTS / "omr_layouts" / f"{layout_name}.json")
        assert doc["layout_name"] == layout_name
        assert doc["total_questions"] == exp_q
        assert len(doc["question_blocks"]) == exp_q

        # Roll number grid: 8 digits x 0-9
        rg = doc["roll_number_grid"]
        assert rg["digits_count"] == 8
        assert rg["digit_values"] == list(range(10))
        assert len(rg["columns"]) == 8
        for col in rg["columns"]:
            assert len(col["bubbles"]) == 10

        r = doc["bubble_radius_mm"]
        tl_x = doc["fiducials"]["top_left"]["x_mm"]
        tl_y = doc["fiducials"]["top_left"]["y_mm"]
        w = doc["page_size_mm"]["width_mm"]
        h = doc["page_size_mm"]["height_mm"]

        centers = []
        for col in rg["columns"]:
            for b in col["bubbles"]:
                centers.append((tl_x + b["dx_mm"], tl_y + b["dy_mm"]))
        for qb in doc["question_blocks"]:
            for b in qb["bubbles"]:
                centers.append((tl_x + b["dx_mm"], tl_y + b["dy_mm"]))

        for cx, cy in centers:
            assert cx - r >= 0.0 and cx + r <= w, f"{layout_name}: bubble ({cx}, {cy}) outside width {w}"
            assert cy - r >= 0.0 and cy + r <= h, f"{layout_name}: bubble ({cx}, {cy}) outside height {h}"

        min_gap = float("inf")
        for i in range(len(centers)):
            x1, y1 = centers[i]
            for j in range(i + 1, len(centers)):
                dist = math.hypot(x1 - centers[j][0], y1 - centers[j][1])
                gap = dist - 2.0 * r
                if gap < min_gap:
                    min_gap = gap
        assert min_gap >= 1.0, f"{layout_name}: minimum bubble edge-to-edge gap {min_gap:.3f} mm < 1.0 mm"


# ---------------------------------------------------------------------------
# Test 14: CONTRACT_VERSION is semver and every contract file header matches it
# ---------------------------------------------------------------------------
def test_14_contract_version_consistency():
    version_str = (CONTRACTS / "CONTRACT_VERSION").read_text(encoding="utf-8").strip()
    assert re.match(r"^[0-9]+\.[0-9]+\.[0-9]+$", version_str), f"Invalid semver: {version_str}"

    # Check every contract file in contracts/ (excluding tests/ and CONTRACT_VERSION itself)
    checked_files = []
    for path in CONTRACTS.rglob("*"):
        if path.is_dir():
            continue
        if "tests" in path.parts or "__pycache__" in path.parts:
            continue
        if path.name == "CONTRACT_VERSION":
            continue

        checked_files.append(path)
        head_lines = "\n".join(path.read_text(encoding="utf-8").splitlines()[:15])
        assert f"contract_version: {version_str}" in head_lines, (
            f"File {path.relative_to(ROOT)} missing 'contract_version: {version_str}' in header comment"
        )
        assert "Purpose:" in head_lines, f"File {path.relative_to(ROOT)} missing 'Purpose:' in header comment"
        assert "Implements:" in head_lines, f"File {path.relative_to(ROOT)} missing 'Implements:' in header comment"

    assert len(checked_files) >= 30
