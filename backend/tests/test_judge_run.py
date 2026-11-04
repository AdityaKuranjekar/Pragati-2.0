"""Scripted 'judge changes an input live' run, 10 repetitions: every edit must answer in under 5 s with recomputed numbers."""
from __future__ import annotations

import os
import statistics
import time

from app import deps
from app.db import pg
from app.services import analytics

N = 10


def _adult(batches):
    iid = deps.institutes_by_slug()["patna_jee"]["id"]
    for b in batches:
        with pg.tenant_conn(iid) as conn:
            res = analytics.state(conn, iid, b["id"])
        full = res["scores"][res["scores"].model == "ABCD"]
        if len(full):
            return b["id"], list(full.sort_values("p").index[:3])
    raise AssertionError("no adult")


def test_ten_scripted_live_edits(client, teacher, owner, batches, reseed):
    bid, sids = _adult(batches)
    tests = client.get(f"/api/v1/tests?batch_id={bid}", headers=teacher).json()["tests"]
    tid = tests[0]["id"]
    with pg.admin_cursor(commit=False) as cur:
        cur.execute("SELECT tq.position, array_to_string(k.accepted_answers,'|') AS acc FROM answer_keys k JOIN test_questions tq ON tq.test_id=k.test_id AND tq.question_id=k.question_id "
                    "JOIN questions q ON q.id=k.question_id WHERE k.test_id=%s AND q.q_type='mcq_single' ORDER BY tq.position LIMIT 1", (tid,))
        q = cur.fetchone()
    lat: dict[str, list[float]] = {}

    def timed(name, fn):
        t = time.perf_counter()
        r = fn()
        dt_ = time.perf_counter() - t
        lat.setdefault(name, []).append(dt_)
        assert r.status_code in (200, 201), (name, r.status_code, r.text[:200])
        assert dt_ < 5.0, (name, dt_)
        return r.json()

    for i in range(N):
        sid = sids[i % len(sids)]
        timed("attendance_to_30pct", lambda: client.patch(f"/api/v1/students/{sid}/attendance", headers=teacher, json={"attendance_pct": 30 + i}))
        timed("fee_delay", lambda: client.patch(f"/api/v1/students/{sid}/fees", headers=teacher, json={"instalment_no": 1, "delay_days": 20 + i}))
        new = "B" if (i % 2 == 0) else "C"
        timed("answer_key_fix", lambda: client.post(f"/api/v1/answer-keys/{tid}/{q['position']}", headers=teacher, json={"accepted_answers": [new]}))
        timed("privacy_tier", lambda: client.put("/api/v1/settings/privacy-tier", headers=owner, json={"tier": "ABCD"[i % 4], "batch_id": bid}))
        timed("report_hi", lambda: client.post(f"/api/v1/students/{sid}/reports", headers=teacher, json={"lang": "hi", "use_llm": False}))
        j = timed("support_list_read", lambda: client.get(f"/api/v1/batches/{bid}/support-list", headers=teacher))
        assert j["list"]
        timed("heatmap_read", lambda: client.get(f"/api/v1/batches/{bid}/heatmap", headers=teacher))
    summary = {k: {"n": len(v), "median_s": round(statistics.median(v), 3), "max_s": round(max(v), 3)} for k, v in lat.items()}
    print("\nLIVE-EDIT LATENCY", summary)
    assert all(v["max_s"] < 5 for v in summary.values())
