"""P5 live edits (each must answer in under 5 s with recomputed numbers), validation errors, consents, privacy tier; P6 reports."""
from __future__ import annotations

import time

import pytest

from app import deps
from app.db import pg
from app.services import analytics


def _adult_in_batch(client, teacher, batches):
    """An 18+ student who is scored on the full model (so attendance and fees matter), with its batch id."""
    iid = deps.institutes_by_slug()["patna_jee"]["id"]
    for b in batches:
        with pg.tenant_conn(iid) as conn:
            res = analytics.state(conn, iid, b["id"])
        sc = res["scores"]
        full = sc[sc.model == "ABCD"]
        if len(full):
            return b["id"], full.sort_values("p").index[len(full) // 2], res
    pytest.skip("no adult student in the seeded batches")


def _minor_in_batch(batches):
    iid = deps.institutes_by_slug()["patna_jee"]["id"]
    for b in batches:
        with pg.tenant_conn(iid) as conn:
            res = analytics.state(conn, iid, b["id"])
        sc = res["scores"]
        a = sc[sc.model == "A"]
        if len(a):
            return b["id"], a.index[0]
    pytest.skip("no minor")


def test_attendance_edit_changes_risk_for_adult_under_5s(client, teacher, batches, reseed):
    bid, sid, res = _adult_in_batch(client, teacher, batches)
    t = time.perf_counter()
    r = client.patch(f"/api/v1/students/{sid}/attendance", headers=teacher, json={"attendance_pct": 10})
    dt_ = time.perf_counter() - t
    assert r.status_code == 200, r.text
    j = r.json()
    assert dt_ < 5 and j["recompute_seconds"] < 5
    assert j["edited"]["attendance_pct_now"] <= 15
    assert j["after"]["p"] > j["before"]["p"], (j["before"], j["after"])  # attendance fell => risk rose
    assert j["support_list"]["list"] and j["support_list"]["minors_on_full_track"] == 0
    r2 = client.patch(f"/api/v1/students/{sid}/attendance", headers=teacher, json={"attendance_pct": 100}).json()
    assert r2["after"]["p"] < j["after"]["p"]


def test_attendance_edit_on_minor_explains_no_effect(client, teacher, batches, reseed):
    bid, sid = _minor_in_batch(batches)
    j = client.patch(f"/api/v1/students/{sid}/attendance", headers=teacher, json={"attendance_pct": 10}).json()
    assert j["after"]["model"] == "A" and abs(j["after"]["p"] - j["before"]["p"]) < 1e-9
    assert "test results only" in j["note"]


def test_single_day_attendance_edit(client, teacher, batches, reseed):
    bid, sid, _ = _adult_in_batch(client, teacher, batches)
    j = client.patch(f"/api/v1/students/{sid}/attendance", headers=teacher, json={"date": "2026-08-20", "present": False})
    assert j.status_code == 200 and j.json()["edited"]["present"] is False


@pytest.mark.parametrize("body", [{"attendance_pct": 140}, {"attendance_pct": -5}, {}, {"date": "2026-08-20"}, {"attendance_pct": 50, "date": "2026-08-20", "present": True},
                                  {"attendance_pct": 50, "window_days": 0}, {"date": "1999-01-01", "present": True}])
def test_attendance_validation_errors(client, teacher, batches, body):
    bid, sid = _minor_in_batch(batches)
    r = client.patch(f"/api/v1/students/{sid}/attendance", headers=teacher, json=body)
    assert r.status_code == 422, (body, r.text)
    assert r.json()["detail"]


def test_unknown_and_malformed_student_ids(client, teacher):
    assert client.patch("/api/v1/students/00000000-0000-0000-0000-000000000000/attendance", headers=teacher, json={"attendance_pct": 50}).status_code == 404
    assert client.patch("/api/v1/students/not-a-uuid/attendance", headers=teacher, json={"attendance_pct": 50}).status_code == 422
    assert client.patch("/api/v1/students/00000000-0000-0000-0000-000000000000/fees", headers=teacher, json={"instalment_no": 1, "paid": False}).status_code == 404


def test_fee_edit_and_validation(client, teacher, batches, reseed):
    bid, sid, _ = _adult_in_batch(client, teacher, batches)
    t = time.perf_counter()
    r = client.patch(f"/api/v1/students/{sid}/fees", headers=teacher, json={"instalment_no": 1, "paid": False})
    assert r.status_code == 200, r.text
    assert time.perf_counter() - t < 5
    j = r.json()
    assert j["edited"]["paid_amount_inr"] == 0 and j["after"]["p"] is not None and j["before"]["p"] is not None  # fee features carry little weight; direction not asserted
    late = client.patch(f"/api/v1/students/{sid}/fees", headers=teacher, json={"instalment_no": 1, "delay_days": 45})
    assert late.status_code == 200
    for bad in [{"instalment_no": 1, "amount_inr": -500}, {"instalment_no": 0, "paid": True}, {"instalment_no": 1}, {"instalment_no": 1, "paid_amount_inr": 99999999},
                {"instalment_no": 1, "paid_amount_inr": -1}]:
        assert client.patch(f"/api/v1/students/{sid}/fees", headers=teacher, json=bad).status_code == 422, bad
    assert client.patch(f"/api/v1/students/{sid}/fees", headers=teacher, json={"instalment_no": 11, "paid": True}).status_code == 404


def test_answer_key_fix_rescoring(client, teacher, batch_id, reseed):
    tests = client.get(f"/api/v1/tests?batch_id={batch_id}", headers=teacher).json()["tests"]
    tid = next(t["id"] for t in tests if t["source"] in ("omr", "csv"))
    with pg.admin_cursor(commit=False) as cur:
        cur.execute("SELECT count(*) AS n FROM answer_keys WHERE test_id=%s", (tid,))
        assert cur.fetchone()["n"] > 0
        cur.execute("SELECT tq.position, array_to_string(k.accepted_answers,'|') AS acc FROM answer_keys k JOIN test_questions tq ON tq.test_id=k.test_id AND tq.question_id=k.question_id "
                    "JOIN questions q ON q.id=k.question_id WHERE k.test_id=%s AND q.q_type='mcq_single' ORDER BY tq.position LIMIT 1", (tid,))
        q = cur.fetchone()
    new = "B" if q["acc"] != "B" else "C"
    t = time.perf_counter()
    r = client.post(f"/api/v1/answer-keys/{tid}/{q['position']}", headers=teacher, json={"accepted_answers": [new]})
    assert r.status_code == 200, r.text
    j = r.json()
    assert time.perf_counter() - t < 5
    assert j["previous_key"] == [q["acc"]] and j["new_key"] == [new] and j["version"] == 2
    assert j["rescore"]["changed"] > 0 and j["mean_score_before"] != j["mean_score_after"]
    # dropped question: everyone gets full marks, nobody changes back to wrong
    d = client.post(f"/api/v1/answer-keys/{tid}/{q['position']}", headers=teacher, json={"dropped": True})
    assert d.status_code == 200 and d.json()["mean_score_after"] >= j["mean_score_after"]


@pytest.mark.parametrize("body,code", [({"accepted_answers": ["Z"]}, 422), ({"accepted_answers": []}, 422), ({"accepted_answers": ["A", "B"]}, 422)])
def test_answer_key_validation(client, teacher, batch_id, body, code):
    tests = client.get(f"/api/v1/tests?batch_id={batch_id}", headers=teacher).json()["tests"]
    tid = tests[0]["id"]
    with pg.admin_cursor(commit=False) as cur:
        cur.execute("SELECT tq.position FROM test_questions tq JOIN questions q ON q.id=tq.question_id WHERE tq.test_id=%s AND q.q_type='mcq_single' ORDER BY tq.position LIMIT 1", (tid,))
        pos = cur.fetchone()["position"]
    assert client.post(f"/api/v1/answer-keys/{tid}/{pos}", headers=teacher, json=body).status_code == code
    assert client.post(f"/api/v1/answer-keys/{tid}/9999", headers=teacher, json={"accepted_answers": ["A"]}).status_code == 404
    assert client.post(f"/api/v1/answer-keys/{tid}/0", headers=teacher, json={"accepted_answers": ["A"]}).status_code == 422
    assert client.post("/api/v1/answer-keys/not-a-uuid/1", headers=teacher, json={"accepted_answers": ["A"]}).status_code == 422


def test_consent_withdrawal_halts_processing(client, teacher, batches, reseed):
    bid, sid, res = _adult_in_batch(client, teacher, batches)
    before = client.get(f"/api/v1/batches/{bid}/support-list", headers=teacher).json()
    cons = client.get(f"/api/v1/consents?student_id={sid}&purpose=risk_alerts&active_only=true", headers=teacher).json()["consents"]
    assert cons
    t = time.perf_counter()
    r = client.delete(f"/api/v1/consents/{cons[0]['id']}", headers=teacher)
    assert r.status_code == 200 and time.perf_counter() - t < 5
    j = r.json()
    assert j["status"] == "revoked" and j["halted"]["risk_scoring"] and j["standing"]["scored"] is False
    after = client.get(f"/api/v1/batches/{bid}/support-list", headers=teacher).json()
    assert sid not in [x["student_id"] for x in after["list"]]
    assert after["excluded_no_consent"] == before["excluded_no_consent"] + 1
    with pg.admin_cursor(commit=False) as cur:
        cur.execute("SELECT count(*) AS n FROM risk_scores WHERE student_id=%s", (sid,))
        assert cur.fetchone()["n"] == 0
    assert client.delete(f"/api/v1/consents/{cons[0]['id']}", headers=teacher).json()["status"] == "already_revoked"
    # re-grant restores scoring
    g = client.post("/api/v1/consents", headers=teacher, json={"student_id": sid, "purpose": "risk_alerts", "verification_method": "self_adult"})
    assert g.status_code == 201 and g.json()["standing"]["scored"] is True


def test_consent_rules(client, teacher, batches, reseed):
    bid, minor = _minor_in_batch(batches)
    assert client.post("/api/v1/consents", headers=teacher, json={"student_id": minor, "purpose": "engagement_tracking", "verification_method": "in_person_id_check"}).status_code == 422
    assert client.post("/api/v1/consents", headers=teacher, json={"student_id": minor, "purpose": "analytics", "verification_method": "self_adult"}).status_code == 422
    ok = client.post("/api/v1/consents", headers=teacher, json={"student_id": minor, "purpose": "analytics", "verification_method": "otp_known_parent"})
    assert ok.status_code == 201
    assert client.post("/api/v1/consents", headers=teacher, json={"student_id": minor, "purpose": "bogus", "verification_method": "otp_known_parent"}).status_code == 422
    assert client.delete("/api/v1/consents/00000000-0000-0000-0000-000000000000", headers=teacher).status_code == 404


def test_privacy_tier_switch_and_legal_flag(client, owner, teacher, batch_id, reseed):
    g = client.get("/api/v1/settings/privacy-tier", headers=owner).json()
    assert g["tiers"]["D"]["auc"] > g["tiers"]["A"]["auc"] + 0.1  # measured ablation, offline
    t = time.perf_counter()
    r = client.put("/api/v1/settings/privacy-tier", headers=owner, json={"tier": "A", "batch_id": batch_id})
    assert r.status_code == 200 and time.perf_counter() - t < 5
    j = r.json()
    assert set(j["students_by_model"]) <= {"A"} and j["support_list"]["feature_tier_active"] == "A"
    assert all(x["track"] == "academic_support" for x in j["support_list"]["list"])
    assert client.put("/api/v1/settings/privacy-tier", headers=owner, json={"tier": "D", "minor_ml_risk_enabled": True}).status_code == 422
    ok = client.put("/api/v1/settings/privacy-tier", headers=owner, json={"tier": "D", "minor_ml_risk_enabled": True, "legal_opinion_ref": "LO-2026-17", "batch_id": batch_id})
    assert ok.status_code == 200
    sl = ok.json()["support_list"]
    assert sl["minors_on_full_track"] == 0  # opted-in minors are labelled retention_minor_opt_in, and never receive tier D
    iid = deps.institutes_by_slug()["patna_jee"]["id"]
    with pg.tenant_conn(iid) as conn:
        res = analytics.state(conn, iid, batch_id)
    minors = res["elig"].index[res["elig"].is_minor]
    assert not any("D" in m for m in res["scores"].loc[res["scores"].index.intersection(minors), "model"])
    assert client.put("/api/v1/settings/privacy-tier", headers=owner, json={"tier": "E"}).status_code == 422
    assert client.put("/api/v1/settings/privacy-tier", headers=teacher, json={"tier": "A"}).status_code == 403


def test_report_hindi_english_verified_and_fast(client, teacher, batches, reseed):
    bid, sid, _ = _adult_in_batch(client, teacher, batches)
    for lang in ("hi", "en"):
        t = time.perf_counter()
        r = client.post(f"/api/v1/students/{sid}/reports", headers=teacher, json={"lang": lang, "use_llm": False})
        dt_ = time.perf_counter() - t
        assert r.status_code == 201, r.text
        j = r.json()
        assert j["verified"] is True and j["source"] == "template" and len(j["checks"]) == 8 and all(c["passed"] for c in j["checks"])
        assert "{STUDENT}" not in j["body"] and "{INSTITUTE}" not in j["body"]
        assert dt_ < 1.0, dt_
        if lang == "hi":
            assert any("ऀ" <= ch <= "ॿ" for ch in j["body"])
    stored = client.get(f"/api/v1/students/{sid}/reports", headers=teacher).json()["reports"]
    assert len(stored) == 2
    # auto mode with Ollama unreachable or without the model still answers from the template path inside a second
    t = time.perf_counter()
    auto = client.post(f"/api/v1/students/{sid}/reports", headers=teacher, json={"lang": "hi"})
    assert auto.status_code == 201 and auto.json()["verified"]
    if auto.json()["source"] == "template":
        assert time.perf_counter() - t < 1.5


def test_report_blocked_without_consent_and_for_student_role(client, teacher, login, batches, reseed):
    bid, sid, _ = _adult_in_batch(client, teacher, batches)
    cons = client.get(f"/api/v1/consents?student_id={sid}&purpose=parent_reports&active_only=true", headers=teacher).json()["consents"]
    for c in cons:
        client.delete(f"/api/v1/consents/{c['id']}", headers=teacher)
    assert client.post(f"/api/v1/students/{sid}/reports", headers=teacher, json={"lang": "en"}).status_code == 403
    assert client.post(f"/api/v1/students/{sid}/reports", headers=login("patna_jee", "student", student_id=sid), json={"lang": "en"}).status_code == 403


def test_interventions_log(client, teacher, batches, reseed):
    bid, sid = _minor_in_batch(batches)
    r = client.post(f"/api/v1/students/{sid}/interventions", headers=teacher, json={"type": "mentoring", "due_date": "2026-09-05"})
    assert r.status_code == 201
    assert len(client.get(f"/api/v1/students/{sid}/interventions", headers=teacher).json()["interventions"]) == 1
    assert client.post(f"/api/v1/students/{sid}/interventions", headers=teacher, json={"type": "scolding", "due_date": "2026-09-05"}).status_code == 422
