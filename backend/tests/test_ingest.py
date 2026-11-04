"""P4: golden parsing of the 12 messy files, API preview/commit, idempotence, validation, timing."""
from __future__ import annotations

import glob
import io
import json
import os
import time

import openpyxl
import pytest

from app import config, deps
from app.db import pg
from app.services import ingest_parse as ip

DIRTY = config.DATA_DIR / "dirty"
FILES = sorted(p for p in glob.glob(str(DIRTY / "*.*")) if not p.endswith(".json") and os.path.isfile(p))


@pytest.mark.parametrize("path", FILES, ids=[os.path.basename(f)[:30] for f in FILES])
def test_golden_parse(path):
    name = os.path.basename(path)
    exp = json.load(open(DIRTY / "expected" / f"{name}.json", encoding="utf-8"))
    r = ip.parse(open(path, "rb").read(), name)
    rows = [{k: v for k, v in x.items() if k != "_row"} for x in r["canonical_rows"]]
    errs = [{k: e[k] for k in ("row_number", "code", "field", "value")} for e in r["errors"]]
    assert r["ingest_type"] == exp["ingest_type"]
    assert rows == exp["canonical_rows"]
    assert errs == exp["expected_errors"]


def test_twelve_files_present():
    assert len(FILES) == 12


@pytest.mark.parametrize("path", FILES, ids=[os.path.basename(f)[:30] for f in FILES])
def test_dirty_files_through_api(client, teacher, path):
    """Every dirty file gets a preview (never a 500); golden parse errors survive; roster errors are added."""
    name = os.path.basename(path)
    exp = json.load(open(DIRTY / "expected" / f"{name}.json", encoding="utf-8"))
    kind = {"results_marks_only": "results", "results_responses": "results", "answer_key": "answer-key"}.get(exp["ingest_type"], exp["ingest_type"])
    form = {"test_id": "", "batch_id": ""}
    r = client.post(f"/api/v1/ingest/{kind}", headers=teacher, files={"file": (name, open(path, "rb").read())}, data=form)
    if exp["ingest_type"] == "answer_key":
        assert r.status_code == 422  # a target test is mandatory for keys
        return
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["ingest_type"] == exp["ingest_type"]
    got = {(e["row_number"], e["code"]) for e in j["errors"]}
    for e in exp["expected_errors"]:
        assert (e["row_number"], e["code"]) in got
    assert j["rows_ok"] + j["rows_failed"] >= exp["expected_rows_ok"]
    assert all(e.get("message") for e in j["errors"])
    assert j["mapping"]["detected"], "mapping preview must be returned"


def test_wrong_kind_is_rejected(client, teacher):
    p = str(DIRTY / "02_lucknow_attendance_markers_mix.csv")
    r = client.post("/api/v1/ingest/fees", headers=teacher, files={"file": ("a.csv", open(p, "rb").read())})
    assert r.status_code == 422 and r.json()["detail"]["detected_type"] == "attendance"


def test_garbage_files_are_clean_errors(client, teacher):
    for blob, nm in [(b"\x00\x01\x02garbage", "x.xlsx"), (b"just,some\n1,2\n", "x.csv"), (b"", "x.csv"), (b"a", "x.pdf")]:
        r = client.post("/api/v1/ingest/attendance", headers=teacher, files={"file": (nm, blob)})
        assert r.status_code in (201, 413, 422), (nm, r.status_code, r.text[:200])
        if r.status_code == 201:
            assert r.json()["can_commit"] is False and r.json()["missing_required"]


def _roster(client, teacher, batch_id, n=12):
    st = client.get(f"/api/v1/batches/{batch_id}/students", headers=teacher).json()["students"]
    return [s for s in st if s["status"] == "active"][:n]


def _csv(header, rows):
    return (",".join(header) + "\n" + "\n".join(",".join(str(c) for c in r) for r in rows) + "\n").encode()


def test_marks_only_e2e_idempotent_and_recompute(client, teacher, batch_id, reseed):
    ros = _roster(client, teacher, batch_id)
    csv_ = _csv(["Test Name", "Test Date", "Roll No", "Total Marks", "Physics", "Chemistry", "Maths Marks"],
                [("LIVE-MARKS-1", "2026-08-27", s["roll_no"], 60 + i, 20, 20, 20 + i) for i, s in enumerate(ros)] +
                [("LIVE-MARKS-1", "2026-08-27", "NOPE-1", 10, 1, 1, 1), ("LIVE-MARKS-1", "2026-08-27", ros[0]["roll_no"], 70, 20, 20, 30)])
    r = client.post("/api/v1/ingest/results", headers=teacher, files={"file": ("m.csv", csv_)})
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["rows_ok"] == len(ros) and j["can_commit"]
    codes = {e["code"] for e in j["errors"]}
    assert "missing_student_in_roster" in codes and "duplicate_or_out_of_bounds_score" in codes
    assert any(w["code"] == "new_tests_will_be_created" for w in j["warnings"])
    t = time.perf_counter()
    c = client.post(f"/api/v1/ingest/jobs/{j['job_id']}/commit", headers=teacher)
    assert c.status_code == 202, c.text
    assert c.json()["result"]["score_rows_written"] == len(ros) and c.json()["result"]["tests_created"] == 1
    assert time.perf_counter() - t < 5
    again = client.post(f"/api/v1/ingest/jobs/{j['job_id']}/commit", headers=teacher).json()
    assert again["idempotent"] is True
    same = client.post("/api/v1/ingest/results", headers=teacher, files={"file": ("m.csv", csv_)}).json()
    assert same["duplicate"] is True and same["job_id"] == j["job_id"] and same["committed"] is True
    tests = client.get(f"/api/v1/tests?batch_id={batch_id}", headers=teacher).json()["tests"]
    assert sum(t["name"] == "LIVE-MARKS-1" for t in tests) == 1


def test_answer_key_then_wide_responses_e2e(client, teacher, batch_id, reseed):
    ros = _roster(client, teacher, batch_id, 10)
    topic = "jee.phy.kinematics.projectile"
    key = _csv(["Q.No.", "Question Type", "Subject", "Topic Code", "Answer Key", "Tolerance", "Is Bonus"],
               [(1, "mcq_single", "Physics", topic, "A", 0.0, "false"), (2, "mcq_multi", "Chemistry", topic, "A|C", 0.0, "false"),
                (3, "numeric", "Mathematics", topic, "42.5", 0.1, "false"), (4, "mcq_single", "Physics", topic, "D", 0.0, "false"),
                (5, "mcq_single", "Chemistry", topic, "B", 0.0, "true")])
    r = client.post("/api/v1/ingest/answer-key", headers=teacher, files={"file": ("k.csv", key)}, data={"test_name": "LIVE-WIDE-1", "batch_id": batch_id, "test_date": "2026-08-26", "commit": "true"})
    assert r.status_code == 201, r.text
    assert r.json()["committed"] and r.json()["commit"]["result"]["test_created"]
    rows = [("LIVE-WIDE-1", "26/08/2026", s["roll_no"], "A", "A|C", "-", "B", "42.5") for s in ros]
    wide = _csv(["Mock Test", "Pariksha Tithi", "Roll No", "Q.1", "Ques 2", "प्र. 3", "Q4", "Q5"], rows)
    j = client.post("/api/v1/ingest/results", headers=teacher, files={"file": ("w.csv", wide)}, data={"commit": "true"}).json()
    assert j["rows_ok"] == len(ros), j
    res = j["commit"]["result"]
    assert res["response_rows_written"] == 5 * len(ros)
    # scoring: Q1 correct (+4), Q2 multi correct (+4), Q3 blank (dropped? no) 0, Q4 wrong (-1), Q5 bonus correct (+4)
    # (Q5 is "bonus"/dropped: everyone gets full marks) => 4 + 4 + 0 - 1 + 4 = 11 ... Q3 numeric answered '-' is blank
    tt = [t for t in client.get(f"/api/v1/tests?batch_id={batch_id}", headers=teacher).json()["tests"] if t["name"] == "LIVE-WIDE-1"]
    assert len(tt) == 1
    with pg.admin_cursor(commit=False) as cur:
        cur.execute("SELECT raw_score, count(*) AS n FROM test_totals WHERE test_id=%s GROUP BY 1", (tt[0]["id"],))
        got = cur.fetchall()
    assert len(got) == 1 and got[0]["n"] == len(ros) and abs(got[0]["raw_score"] - 11.0) < 1e-9


def test_students_upload_with_underage_and_unknown_batch(client, teacher, batches, reseed):
    b = batches[0]["name"]
    csv_ = _csv(["Roll No", "Student Name", "Date of Birth", "Admission Date", "Batch"],
                [("NEW-1", "Riya Test", "2009-05-14", "2026-04-15", b), ("NEW-2", "Tiny Test", "2013-01-01", "2026-04-15", b),
                 ("NEW-3", "Lost Test", "2009-05-14", "2026-04-15", "NO-SUCH-BATCH"), ("NEW-1", "Dup Test", "2009-05-14", "2026-04-15", b)])
    j = client.post("/api/v1/ingest/students", headers=teacher, files={"file": ("s.csv", csv_)}).json()
    codes = {e["code"] for e in j["errors"]}
    assert {"underage_enrolment_lt_16", "unknown_batch", "duplicate_roll_no"} <= codes
    assert j["rows_ok"] == 1
    assert any(w["code"] == "underage_enrolment_lt_16" for w in j["warnings"])
    assert any(w["code"] == "minors_need_consent" for w in j["warnings"])
    c = client.post(f"/api/v1/ingest/jobs/{j['job_id']}/commit", headers=teacher)
    assert c.status_code == 202 and c.json()["result"]["students_written"] == 1


def test_attendance_upload_warns_after_as_of(client, teacher, batch_id, reseed):
    ros = _roster(client, teacher, batch_id, 3)
    csv_ = _csv(["Roll No", "Date", "Attendance Status"] if False else ["Roll No", "Attendance Date", "Present"], [])
    csv_ = _csv(["roll_no", "attendance_date", "present_flag"], [(s["roll_no"], "2026-09-10", "A") for s in ros] + [(ros[0]["roll_no"], "32/13/2026", "P")])
    j = client.post("/api/v1/ingest/attendance", headers=teacher, files={"file": ("a.csv", csv_)}).json()
    assert any(w["code"] == "after_demo_as_of" for w in j["warnings"])
    assert any(e["code"] == "invalid_date" for e in j["errors"])


def test_xlsx_upload_with_merged_title_row(client, teacher, batch_id, reseed):
    ros = _roster(client, teacher, batch_id, 5)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "Weekly register - Batch A"
    ws.merge_cells("A1:C1")
    ws.append([])
    ws.append(["R.No", "Date", "M/F"][:2] + ["Attendance Status"])
    for s in ros:
        ws.append([s["roll_no"], "2026-08-20", "P"])
    bio = io.BytesIO()
    wb.save(bio)
    j = client.post("/api/v1/ingest/attendance", headers=teacher, files={"file": ("a.xlsx", bio.getvalue())})
    # "Date" alone is not a known synonym: expect a clear request to map columns, not a crash
    assert j.status_code in (201, 422)


def test_manual_mapping_override(client, teacher, batch_id, reseed):
    ros = _roster(client, teacher, batch_id, 4)
    csv_ = _csv(["ID", "Day", "Here"], [(s["roll_no"], "2026-08-20", "Y") for s in ros])
    r = client.post("/api/v1/ingest/attendance", headers=teacher, files={"file": ("a.csv", csv_)})
    assert r.status_code == 201 and r.json()["can_commit"] is False and r.json()["missing_required"]  # mapping screen, not an error
    m = json.dumps({"ID": "roll_no", "Day": "attendance_date", "Here": "present_flag"})
    r = client.post("/api/v1/ingest/attendance", headers=teacher, files={"file": ("a.csv", csv_)}, data={"mapping": m, "commit": "true"})
    assert r.status_code == 201, r.text
    assert r.json()["rows_ok"] == 4 and r.json()["committed"]


def test_2000_student_file_under_30s(client, teacher, batch_id, reseed):
    ros = _roster(client, teacher, batch_id, 60)
    rows = []
    for k in range(34):  # 60 students x 34 days ~ 2,040 attendance rows
        for s in ros:
            rows.append((s["roll_no"], f"2026-07-{(k % 28) + 1:02d}", "P" if (k + len(s["roll_no"])) % 3 else "A"))
    csv_ = _csv(["roll_no", "attendance_date", "present_flag"], rows)
    t = time.perf_counter()
    r = client.post("/api/v1/ingest/attendance", headers=teacher, files={"file": ("big.csv", csv_)}, data={"commit": "true"})
    dt_ = time.perf_counter() - t
    assert r.status_code == 201 and r.json()["committed"]
    assert dt_ < 30, dt_


def test_ingest_requires_staff_role(client, login):
    parent = login("patna_jee", "parent")
    r = client.post("/api/v1/ingest/attendance", headers=parent, files={"file": ("a.csv", b"roll_no,attendance_date,present_flag\n1,2026-01-01,P\n")})
    assert r.status_code == 403
