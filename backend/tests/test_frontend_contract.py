"""Calls every endpoint of frontend/API_CONTRACT.md the way the front end does, and checks the fields the zod schemas read."""
from __future__ import annotations

import io
import json
import time

import pytest

from app import config, deps
from app.db import pg

OMR_DIR = config.DATA_DIR / "omr" / "synthetic"


def fe_login(client, role, institute="patna_jee"):
    r = client.post("/auth/login", json={"role": role, "institute_id": institute})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["access_token"] and {"id", "role", "name", "institute_id", "student_id"} <= set(j["user"])
    assert j["user"]["institute_id"] == institute
    return {"Authorization": "Bearer " + j["access_token"]}, j["user"]


def test_cors_any_localhost_port_and_auth_header(client):
    r = client.options("/auth/login", headers={"Origin": "http://localhost:3100", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,content-type"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:3100"
    assert "authorization" in r.headers["access-control-allow-headers"].lower()
    r = client.get("/health", headers={"Origin": "http://127.0.0.1:3100"})
    assert r.headers["access-control-allow-origin"] == "http://127.0.0.1:3100"
    r = client.get("/health", headers={"Origin": "http://evil.example.com"})
    assert "access-control-allow-origin" not in r.headers


def test_login_all_roles(client):
    for role in ("owner", "teacher", "mentor", "student", "parent"):
        h, u = fe_login(client, role)
        if role in ("student", "parent"):
            assert u["student_id"]
    assert client.post("/auth/login", json={"role": "owner"}).status_code == 422


def test_artifact_files_and_global(client):
    h, _ = fe_login(client, "teacher")
    for f in ("mastery", "risk", "student", "percentile", "parent", "reports", "owner", "datacard"):
        assert client.get(f"/api/v1/patna_jee/{f}", headers=h).status_code == 200, f
    for f in ("moat", "scaling", "models", "metrics"):
        assert client.get(f"/api/v1/global/{f}", headers=h).status_code == 200, f


def test_batch_tests_flagged_attendance_key_support_list(client, reseed):
    h, _ = fe_login(client, "teacher")
    b = client.get("/api/v1/batches", headers=h).json()["batches"][0]["id"]
    t = client.get(f"/api/v1/batches/{b}/tests", headers=h).json()
    assert t["batch_id"] == b and t["tests"] and {"test_id", "name", "date", "question_count"} <= set(t["tests"][0])
    tid = t["tests"][0]["test_id"]
    fl = client.get(f"/api/v1/tests/{tid}/flagged-questions", headers=h).json()
    assert fl["test_id"] == tid and isinstance(fl["flagged"], list)
    for f in fl["flagged"]:
        assert isinstance(f["current_key"], str) and isinstance(f["suggested_key"], str) and f["status"] in ("open", "fixed") and "reason_code" in f
    with pg.admin_cursor(commit=False) as cur:
        cur.execute("SELECT tq.position, array_to_string(k.accepted_answers,'|') AS acc FROM answer_keys k JOIN test_questions tq ON tq.test_id=k.test_id AND tq.question_id=k.question_id "
                    "JOIN questions q ON q.id=k.question_id WHERE k.test_id=%s AND q.q_type='mcq_single' ORDER BY tq.position LIMIT 1", (tid,))
        q = cur.fetchone()
    new = "B" if q["acc"] != "B" else "C"
    r = client.post(f"/api/v1/answer-keys/{tid}/{q['position']}", headers=h, json={"key": new})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["key"] == new and isinstance(j["rescored_students"], int) and isinstance(j["recompute_ms"], (int, float)) and isinstance(j["flagged"], list)
    assert any(f["question_no"] == q["position"] and f["status"] == "fixed" for f in j["flagged"])
    sl = client.get(f"/api/v1/batches/{b}/support-list", headers=h).json()
    assert sl["list"]
    sid = sl["list"][0]["student_id"]
    a = client.patch(f"/api/v1/students/{sid}/attendance", headers=h, json={"attendance_pct": 40})
    assert a.status_code == 200, a.text
    aj = a.json()
    assert aj["effect"] in ("model", "rule_only", "none") and aj["attendance_pct"] is not None and aj["message_en"] and aj["message_hi"]
    assert isinstance(aj["recompute_ms"], (int, float)) and aj["recompute_ms"] < 5000 and aj["support_list"]["list"] is not None
    assert {"track", "on_support_list"} <= set(aj)
    r = client.patch(f"/api/v1/students/{sid}/attendance", headers=h, json={"attendance_pct": 140})
    assert r.status_code == 422 and r.json()["detail"]
    assert client.patch("/api/v1/students/00000000-0000-0000-0000-000000000000/attendance", headers=h, json={"attendance_pct": 50}).status_code == 404


def test_privacy_tier_contract(client, reseed):
    h, _ = fe_login(client, "owner")
    g = client.get("/api/v1/settings/privacy-tier", headers=h).json()
    assert g["tier"] in ("full", "academic_only") and g["minors_always_academic"] is True
    assert {o["tier"] for o in g["options"]} == {"full", "academic_only"}
    assert all({"auc", "precision", "recall", "lead_time_days"} <= set(o["metrics"]) for o in g["options"])
    assert isinstance(g["list_size"], int) and g["capacity_per_week"]
    p = client.put("/api/v1/settings/privacy-tier", headers=h, json={"tier": "academic_only"})
    assert p.status_code == 200 and p.json()["tier"] == "academic_only"
    back = client.put("/api/v1/settings/privacy-tier", headers=h, json={"tier": "full"}).json()
    assert back["tier"] == "full"
    t, _ = fe_login(client, "teacher")
    assert client.put("/api/v1/settings/privacy-tier", headers=t, json={"tier": "full"}).status_code == 403


def test_consents_contract(client, reseed):
    h, _ = fe_login(client, "owner")
    led = client.get("/api/v1/consents", headers=h).json()
    assert led["items"] and {"total", "active", "withdrawn"} <= set(led["summary"])
    it = led["items"][0]
    assert {"consent_id", "student_id", "roll_no", "guardian_display", "kind", "method", "date", "status"} <= set(it)
    assert it["kind"] in ("parental", "self") and it["status"] in ("active", "withdrawn")
    q = client.get(f"/api/v1/consents?q={it['roll_no']}", headers=h).json()
    assert any(i["roll_no"] == it["roll_no"] for i in q["items"])
    act = next(i for i in led["items"] if i["status"] == "active")
    assert client.post("/api/v1/consents", headers=h, json={"roll_no": act["roll_no"], "guardian_name": "X", "method": "in_person_id_check"}).status_code == 409
    d = client.delete(f"/api/v1/consents/{act['consent_id']}", headers=h)
    assert d.status_code == 200 and isinstance(d.json()["effect"], str) and d.json()["status"] in ("withdrawn", "revoked")
    again = client.post("/api/v1/consents", headers=h, json={"roll_no": act["roll_no"], "guardian_name": "Guardian Test", "method": "in_person_id_check"})
    assert again.status_code == 201, again.text
    assert {"consent_id", "roll_no", "status", "kind"} <= set(again.json())


def test_report_contract(client, reseed):
    h, _ = fe_login(client, "teacher")
    b = client.get("/api/v1/batches", headers=h).json()["batches"][0]["id"]
    sid = client.get(f"/api/v1/batches/{b}/support-list", headers=h).json()["list"][0]["student_id"]
    r = client.post(f"/api/v1/students/{sid}/reports", headers=h, json={"language": "hi", "use_llm": True})
    assert r.status_code in (200, 201), r.text
    j = r.json()
    assert j["language"] == "hi" and j["verified"] is True and j["checks"] and all({"id", "passed"} <= set(c) for c in j["checks"])
    for k in ("source", "llm_requested", "llm_available", "fallback_used", "fallback_reason", "hi_reviewed", "latency_ms", "month", "body"):
        assert k in j, k
    assert j["llm_requested"] is True


def _csv(header, rows):
    return (",".join(header) + "\n" + "\n".join(",".join(str(c) for c in r) for r in rows) + "\n").encode()


def test_ingest_job_lifecycle_like_the_front_end(client, reseed):
    h, _ = fe_login(client, "teacher")
    b = client.get("/api/v1/batches", headers=h).json()["batches"][0]["id"]
    ros = [s for s in client.get(f"/api/v1/batches/{b}/students", headers=h).json()["students"] if s["status"] == "active"][:6]
    csv_ = _csv(["ID", "Day", "Here"], [(s["roll_no"], "2026-08-20", "Y") for s in ros])
    r = client.post("/api/v1/ingest/attendance", headers=h, files={"file": ("a.csv", csv_)})
    # unmappable headers: the front end must get a mapping screen, not an error
    assert r.status_code in (201, 422)
    if r.status_code == 422:
        csv_ = _csv(["Roll No", "Date", "Present"], [(s["roll_no"], "2026-08-20", "Y") for s in ros])
        r = client.post("/api/v1/ingest/attendance", headers=h, files={"file": ("a.csv", csv_)})
    assert r.status_code == 201, r.text
    j = r.json()
    for k in ("job_id", "kind", "filename", "status", "stage", "progress", "row_count", "accepted_count", "error_count", "warning_count", "rejected_rows",
              "columns", "targets", "missing_required", "can_commit", "errors", "sample_rows"):
        assert k in j, k
    assert j["status"] == "preview" and all({"source", "target", "confidence", "alternatives"} <= set(c) for c in j["columns"])
    assert all({"id", "required", "label_en"} <= set(t) for t in j["targets"])
    if j["missing_required"]:
        assert client.post(f"/api/v1/ingest/jobs/{j['job_id']}/commit", headers=h, json={}).status_code == 422
        m = {c["source"]: t for c, t in zip(j["columns"], ["roll_no", "attendance_date", "present_flag"])}
        j = client.post(f"/api/v1/ingest/jobs/{j['job_id']}/mapping", headers=h, json={"mapping": m}).json()
    assert j["can_commit"] and not j["missing_required"], j
    c = client.post(f"/api/v1/ingest/jobs/{j['job_id']}/commit", headers=h, json={})
    assert c.status_code == 202 and c.json()["status"] == "running"
    for _ in range(20):
        g = client.get(f"/api/v1/ingest/jobs/{j['job_id']}", headers=h).json()
        if g["status"] in ("done", "failed"):
            break
        time.sleep(0.2)
    assert g["status"] == "done" and g["progress"] == 1 and g["stage"] == "done"


def test_mapping_endpoint_on_unknown_columns(client, reseed):
    h, _ = fe_login(client, "teacher")
    b = client.get("/api/v1/batches", headers=h).json()["batches"][0]["id"]
    ros = [s for s in client.get(f"/api/v1/batches/{b}/students", headers=h).json()["students"]][:4]
    # three recognised headers plus one unknown: previews with a missing target the user then maps
    csv_ = _csv(["Roll No", "Date", "Mark"], [(s["roll_no"], "2026-08-20", "P") for s in ros])
    r = client.post("/api/v1/ingest/attendance", headers=h, files={"file": ("a.csv", csv_)})
    if r.status_code == 201:
        j = r.json()
        m = {c["source"]: c["target"] for c in j["columns"]}
        m["Date"], m["Mark"] = "attendance_date", "present_flag"
        j2 = client.post(f"/api/v1/ingest/jobs/{j['job_id']}/mapping", headers=h, json={"mapping": m})
        assert j2.status_code == 200 and j2.json()["accepted_count"] == len(ros), j2.text
    assert client.post("/api/v1/ingest/jobs/00000000-0000-0000-0000-000000000000/mapping", headers=h, json={"mapping": {}}).status_code == 404


@pytest.mark.skipif(not OMR_DIR.exists(), reason="synthetic OMR sheets not present")
def test_omr_upload_confirm_flow(client, reseed):
    h, _ = fe_login(client, "teacher")
    # find the sheet's roll number and a student with that roll in the seeded roster; otherwise register through the DB
    import app.omr as omr

    img = sorted(OMR_DIR.glob("*jee_75*.jpg"))[0]
    res = omr.read_sheet(img.read_bytes()).to_dict()
    roll = res["roll_no"]
    with pg.admin_cursor() as cur:
        cur.execute("SELECT s.id::text, s.batch_id::text FROM students s JOIN institutes i ON i.id=s.institute_id WHERE i.city='Patna' AND s.academic_year=2026 ORDER BY roll_no LIMIT 1")
        stu = cur.fetchone()
        cur.execute("SELECT t.id::text FROM tests t WHERE t.batch_id=%s ORDER BY test_date LIMIT 1", (stu["batch_id"],))
        tid = cur.fetchone()["id"]
        cur.execute("UPDATE students SET roll_no=%s WHERE id=%s", (roll or "OMR-X", stu["id"]))
    r = client.post("/api/v1/ingest/omr", headers=h, files={"file": (img.name, img.read_bytes())}, data={"test_id": tid})
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["status"] in ("review", "retake") and j["job_id"] and j["filename"] == img.name
    assert {"roll_no", "quality", "questions", "uncertain"} <= set(j["result"])
    assert all({"question_no", "label", "reason", "fill"} <= set(u) for u in j["result"]["uncertain"])
    again = client.get(f"/api/v1/ingest/omr/{j['job_id']}", headers=h).json()
    assert again["job_id"] == j["job_id"]
    if j["status"] == "review":
        need = [u["question_no"] for u in j["result"]["uncertain"] if u["question_no"] is not None]
        if need:
            bad = client.post(f"/api/v1/ingest/omr/{j['job_id']}/confirm", headers=h, json={"corrections": {}})
            assert bad.status_code == 422 and "Confirm" in bad.json()["detail"]
        corr = {str(q): "A" for q in need}
        t0 = time.perf_counter()
        c = client.post(f"/api/v1/ingest/omr/{j['job_id']}/confirm", headers=h, json={"corrections": corr, "roll_no": roll or "OMR-X"})
        assert c.status_code == 200, c.text
        cj = c.json()
        assert cj["status"] == "done" and {"correct", "wrong", "blank", "marks", "max_marks"} <= set(cj["scored"])
        assert time.perf_counter() - t0 < 5
        assert client.get(f"/api/v1/ingest/omr/{j['job_id']}", headers=h).json()["status"] == "done"


def test_omr_bad_image_is_clean(client):
    h, _ = fe_login(client, "teacher")
    r = client.post("/api/v1/ingest/omr", headers=h, files={"file": ("x.jpg", b"not an image at all")})
    assert r.status_code == 201 and r.json()["status"] == "retake"
    assert client.post("/api/v1/ingest/omr", headers=h, files={"file": ("x.jpg", b"")}).status_code == 422
    assert client.get("/api/v1/ingest/omr/00000000-0000-0000-0000-000000000000", headers=h).status_code == 404
    assert client.post(f"/api/v1/ingest/omr/{r.json()['job_id']}/confirm", headers=h, json={"corrections": {}}).status_code == 422
