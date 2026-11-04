"""Tenant isolation on every endpoint (a Gaya token must never see Patna data), roles, and raw row-level security."""
from __future__ import annotations

import json

import pytest

from app import deps
from app.db import pg


@pytest.fixture(scope="module")
def ids(client, teacher):
    """Real Patna ids to probe from the other tenant."""
    b = client.get("/api/v1/batches", headers=teacher).json()["batches"][0]["id"]
    sid = client.get(f"/api/v1/batches/{b}/students", headers=teacher).json()["students"][0]["student_id"]
    tid = client.get(f"/api/v1/tests?batch_id={b}", headers=teacher).json()["tests"][0]["id"]
    with pg.admin_cursor(commit=False) as cur:
        cur.execute("SELECT id::text FROM consents WHERE student_id=%s LIMIT 1", (sid,))
        cid = cur.fetchone()["id"]
    return {"batch": b, "student": sid, "test": tid, "consent": cid}


def _calls(ids):
    b, s, t, c = ids["batch"], ids["student"], ids["test"], ids["consent"]
    return [
        ("GET", f"/api/v1/batches/{b}/heatmap", None), ("GET", f"/api/v1/batches/{b}/support-list", None),
        ("GET", f"/api/v1/batches/{b}/percentile", None), ("GET", f"/api/v1/batches/{b}/summary", None), ("GET", f"/api/v1/batches/{b}/students", None),
        ("GET", f"/api/v1/students/{s}/profile", None), ("GET", f"/api/v1/students/{s}/parent-view", None),
        ("GET", f"/api/v1/students/{s}/percentile", None), ("GET", f"/api/v1/students/{s}/reports", None),
        ("GET", f"/api/v1/students/{s}/interventions", None), ("POST", f"/api/v1/students/{s}/interventions", {"type": "mentoring", "due_date": "2026-09-05"}),
        ("POST", f"/api/v1/students/{s}/reports", {"lang": "en"}),
        ("PATCH", f"/api/v1/students/{s}/attendance", {"attendance_pct": 50}), ("PATCH", f"/api/v1/students/{s}/fees", {"instalment_no": 1, "paid": False}),
        ("GET", f"/api/v1/tests/{t}/flagged-questions", None), ("POST", f"/api/v1/answer-keys/{t}/1", {"accepted_answers": ["A"]}),
        ("DELETE", f"/api/v1/consents/{c}", None), ("GET", "/api/v1/ingest/jobs/00000000-0000-0000-0000-000000000000", None),
        ("POST", "/api/v1/ingest/jobs/00000000-0000-0000-0000-000000000000/commit", None),
    ]


def test_other_tenant_gets_404_on_every_id_endpoint(client, login, ids):
    gaya = login("gaya_both", "owner")
    for method, path, body in _calls(ids):
        r = client.request(method, path, headers=gaya, json=body)
        assert r.status_code in (404, 403), (method, path, r.status_code, r.text[:200])
        assert "Patna" not in r.text


def test_other_tenant_lists_contain_no_patna_rows(client, login, ids):
    gaya = login("gaya_both", "owner")
    b = {x["id"] for x in client.get("/api/v1/batches", headers=gaya).json()["batches"]}
    assert ids["batch"] not in b
    assert client.get(f"/api/v1/consents?student_id={ids['student']}", headers=gaya).json()["count"] == 0
    assert client.get(f"/api/v1/tests?batch_id={ids['batch']}", headers=gaya).json()["tests"] == []
    dash = client.get("/api/v1/owner/dashboard", headers=gaya).json()
    assert ids["batch"] not in {x["batch_id"] for x in dash["batch_compare"]}


def test_every_endpoint_requires_a_token(client, ids):
    for method, path, body in _calls(ids) + [("GET", "/api/v1/batches", None), ("GET", "/api/v1/owner/dashboard", None), ("GET", "/api/v1/consents", None),
                                              ("GET", "/api/v1/settings/privacy-tier", None), ("GET", "/api/v1/datacard", None), ("GET", "/api/v1/models", None),
                                              ("GET", "/api/v1/scaling", None), ("POST", "/api/v1/ingest/attendance", None), ("GET", "/me", None)]:
        r = client.request(method, path, json=body)
        assert r.status_code in (401, 422), (method, path, r.status_code)
        if r.status_code == 422:  # multipart endpoint without body: auth is checked first in dependencies, but allow framework ordering
            assert method == "POST" and "ingest" in path


def test_tampered_and_garbage_tokens(client, teacher):
    assert client.get("/api/v1/batches", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401
    assert client.get("/api/v1/batches", headers={"Authorization": teacher["Authorization"][:-3] + "xyz"}).status_code == 401
    assert client.get("/api/v1/batches", headers={"Authorization": "Basic zzz"}).status_code == 401


def test_roles(client, login, ids):
    parent = login("patna_jee", "parent")
    me = client.get("/me", headers=parent).json()
    assert me["role"] == "parent" and me["student_id"]
    own = me["student_id"]
    assert client.get(f"/api/v1/students/{own}/profile", headers=parent).status_code == 200
    assert client.get(f"/api/v1/students/{own}/parent-view", headers=parent).status_code == 200
    other = ids["student"] if ids["student"] != own else None
    if other:
        assert client.get(f"/api/v1/students/{other}/profile", headers=parent).status_code == 403
    for method, path, body in [("GET", f"/api/v1/batches/{ids['batch']}/support-list", None), ("GET", f"/api/v1/batches/{ids['batch']}/heatmap", None),
                               ("GET", "/api/v1/owner/dashboard", None), ("GET", "/api/v1/settings/privacy-tier", None),
                               ("PATCH", f"/api/v1/students/{own}/attendance", {"attendance_pct": 50}), ("GET", "/api/v1/batches", None)]:
        assert client.request(method, path, headers=parent, json=body).status_code == 403, (method, path)
    mentor = login("patna_jee", "mentor")
    assert client.get(f"/api/v1/batches/{ids['batch']}/support-list", headers=mentor).status_code == 200
    assert client.get("/api/v1/owner/dashboard", headers=mentor).status_code == 403
    assert client.patch(f"/api/v1/students/{ids['student']}/attendance", headers=mentor, json={"attendance_pct": 50}).status_code == 403
    teacher = login("patna_jee", "teacher")
    assert client.get("/api/v1/owner/dashboard", headers=teacher).status_code == 403


def test_row_level_security_in_the_database(seeded):
    a = deps.institutes_by_slug()
    pa, ga = a["patna_jee"]["id"], a["gaya_both"]["id"]
    for table in ("students", "batches", "tests", "responses", "attendance", "fees", "consents", "guardians", "questions", "item_params", "users"):
        with pg.tenant_conn(pa) as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT count(*) FROM {table}")
            n_pa = cur.fetchone()[0]
            cur.execute(f"SELECT count(*) FROM {table} WHERE institute_id <> %s", (pa,))
            assert cur.fetchone()[0] == 0, table
        with pg.tenant_conn(ga) as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT count(*) FROM {table}")
            n_ga = cur.fetchone()[0]
        with pg.admin_cursor(commit=False) as cur:
            cur.execute(f"SELECT count(*) AS n FROM {table}")
            assert n_pa + n_ga == cur.fetchone()["n"], table
    with pg.tenant_conn(pa) as conn:  # cross-tenant write is refused by the policy
        cur = conn.cursor()
        with pytest.raises(Exception):
            cur.execute("INSERT INTO batches (institute_id, name, class_level, exam, academic_year, start_date) VALUES (%s,'x','class_11','jee_main',2026,'2026-04-01')", (ga,))
    # no tenant set at all => nothing visible
    conn = pg.admin_connect()
    cur = conn.cursor()
    cur.execute("SET ROLE app_user")
    cur.execute("SELECT count(*) FROM students")
    assert cur.fetchone()[0] == 0
    conn.close()


def test_health_version_login_errors(client):
    h = client.get("/health").json()
    assert h["db"] is True and "ollama" in h
    v = client.get("/version").json()
    assert v["model_version"] and v["data"] == "synthetic"
    assert client.post("/auth/login", json={"institute": "nowhere", "role": "owner"}).status_code == 404
    assert client.post("/auth/login", json={"institute": "patna_jee", "role": "wizard"}).status_code == 422
    assert client.post("/auth/login", json={"institute": "patna_jee"}).status_code == 422


def test_mock_compatible_routes(client, teacher, login):
    assert client.get("/api/v1/patna_jee/mastery").status_code == 401
    r = client.get("/api/v1/patna_jee/mastery", headers=teacher)
    assert r.status_code == 200 and r.json()["schema"] == "mastery/1"
    assert client.get("/api/v1/global/scaling", headers=teacher).status_code == 200
    assert client.get("/api/v1/gaya_both/mastery", headers=teacher).status_code == 403
    assert client.get("/api/v1/..%2f..%2fsecrets/x", headers=teacher).status_code in (400, 404)
    assert client.get("/api/v1/patna_jee/nothing_here", headers=teacher).status_code == 404
    assert client.get("/api/v1/Bad-Name/mastery", headers=teacher).status_code == 400
    ref = json.load(open(__import__("app.config", fromlist=["x"]).ARTIFACTS / "patna_jee" / "risk.json", encoding="utf-8"))
    assert client.get("/api/v1/patna_jee/risk", headers=teacher).json()["capacity_per_week"] == ref["capacity_per_week"]
    parent = login("patna_jee", "parent")
    sid = client.get("/me", headers=parent).json()["student_id"]
    body = client.get("/api/v1/patna_jee/student", headers=parent).json()
    assert all(x["student_id"] == sid for x in body["students"])
    assert all(x["student_id"] == sid for x in client.get("/api/v1/patna_jee/risk", headers=parent).json()["list"])
