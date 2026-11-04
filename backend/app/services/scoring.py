"""Answer keys, re-scoring and item difficulty refresh (all inside one tenant transaction)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import psycopg2.extras

from ..ml import irt
from .analytics import qdf

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def day_after_off(test_date, weekly_off_day: str) -> bool:
    """True if the test falls on the day after the weekly off (MoE 2024 cl. 10.1)."""
    off = WEEKDAYS.index(str(weekly_off_day).lower())
    return pd.Timestamp(test_date).weekday() == (off + 1) % 7


def scheme_for(conn, test_id: str) -> dict:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT m.correct, m.wrong, m.blank FROM tests t JOIN marking_schemes m ON m.id=t.marking_scheme_id WHERE t.id=%s", (test_id,))
        r = cur.fetchone()
    return dict(r) if r else {"correct": 4.0, "wrong": -1.0, "blank": 0.0}


def latest_keys(conn, test_id: str) -> pd.DataFrame:
    """Latest key version per question: question_id, position, accepted (list), tolerance, dropped, q_type, subject."""
    df = qdf(conn, "SELECT k.question_id::text AS question_id, tq.position, array_to_string(k.accepted_answers, '|') AS accepted, k.numeric_tolerance AS tol, "
                   "k.dropped, k.version, q.q_type, q.subject FROM answer_keys k JOIN test_questions tq ON tq.test_id=k.test_id AND tq.question_id=k.question_id "
                   "JOIN questions q ON q.id=k.question_id WHERE k.test_id=%s AND k.version=(SELECT max(version) FROM answer_keys k2 WHERE k2.test_id=k.test_id AND k2.question_id=k.question_id)", (test_id,))
    if len(df):
        df["accepted"] = df.accepted.fillna("").map(lambda s: [x for x in str(s).split("|") if x != ""])
    return df


def score_frame(resp: pd.DataFrame, keys: pd.DataFrame, scheme: dict) -> pd.DataFrame:
    """resp: question_id, response, status. Adds is_correct, marks, new_status."""
    k = keys.set_index("question_id")
    ic, mk, st = [], [], []
    for q, r, s in zip(resp.question_id, resp.response, resp.status):
        if q not in k.index:
            ic.append(False); mk.append(0.0); st.append(s)
            continue
        kr = k.loc[q]
        status = s
        got = irt._norm_set(r)
        if status == "answered" and kr.q_type == "mcq_single" and len(got) > 1:
            status = "multi_marked"
        ok, marks = irt.score_response(r, status, kr.accepted, float(kr.tol or 0.0), bool(kr.dropped), kr.q_type, scheme)
        ic.append(ok); mk.append(marks); st.append(status)
    out = resp.copy()
    out["is_correct"], out["marks"], out["new_status"] = ic, mk, st
    return out


def rebuild_totals(conn, test_id: str) -> int:
    """Recompute test_totals (raw and per-subject) from responses; keeps absent flags."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO test_totals (institute_id, test_id, student_id, raw_score, physics_score, chemistry_score, math_or_bio_score, absent_flag)
            SELECT r.institute_id, r.test_id, r.student_id, sum(r.marks_awarded),
                   sum(r.marks_awarded) FILTER (WHERE lower(q.subject) LIKE 'phys%%'),
                   sum(r.marks_awarded) FILTER (WHERE lower(q.subject) LIKE 'chem%%'),
                   sum(r.marks_awarded) FILTER (WHERE lower(q.subject) NOT LIKE 'phys%%' AND lower(q.subject) NOT LIKE 'chem%%'),
                   false
            FROM responses r JOIN questions q ON q.id = r.question_id WHERE r.test_id = %s GROUP BY r.institute_id, r.test_id, r.student_id
            ON CONFLICT (test_id, student_id) DO UPDATE SET raw_score = EXCLUDED.raw_score, physics_score = EXCLUDED.physics_score,
              chemistry_score = EXCLUDED.chemistry_score, math_or_bio_score = EXCLUDED.math_or_bio_score
            WHERE NOT test_totals.absent_flag
            """, (test_id,))
        return cur.rowcount


def rescore_test(conn, test_id: str, question_ids: list[str] | None = None) -> dict:
    """Re-score stored responses with the latest keys. Returns counts of changed rows."""
    keys = latest_keys(conn, test_id)
    if not len(keys):
        return {"rows": 0, "changed": 0, "students_changed": 0}
    if question_ids:
        keys = keys[keys.question_id.isin(question_ids)]
    scheme = scheme_for(conn, test_id)
    resp = qdf(conn, "SELECT student_id::text AS student_id, question_id::text AS question_id, response, status, is_correct, marks_awarded "
                     "FROM responses WHERE test_id=%s AND question_id = ANY(%s::uuid[])", (test_id, list(keys.question_id)))
    if not len(resp):
        return {"rows": 0, "changed": 0, "students_changed": 0}
    sc = score_frame(resp, keys, scheme)
    chg = sc[(sc.is_correct.astype(bool) != resp.is_correct.astype(bool)) | (np.abs(sc.marks - resp.marks_awarded) > 1e-9)]
    if len(chg):
        with conn.cursor() as cur:
            vals = [(r.student_id, r.question_id, bool(r.is_correct), float(r.marks), r.new_status) for r in chg.itertuples()]
            cur.execute("CREATE TEMP TABLE _rs (sid uuid, qid uuid, ic boolean, mk double precision, st text) ON COMMIT DROP")
            psycopg2.extras.execute_values(cur, "INSERT INTO _rs VALUES %s", vals, page_size=5000)
            cur.execute("UPDATE responses r SET is_correct=_rs.ic, marks_awarded=_rs.mk, status=_rs.st FROM _rs "
                        "WHERE r.test_id=%s AND r.student_id=_rs.sid AND r.question_id=_rs.qid", (test_id,))
        rebuild_totals(conn, test_id)
    return {"rows": int(len(resp)), "changed": int(len(chg)), "students_changed": int(chg.student_id.nunique())}


def refresh_item_difficulty(conn, question_ids: list[str], model_version: str) -> int:
    """Set Rasch difficulty b from the pass rate of the responses stored for these questions (answered rows)."""
    if not question_ids:
        return 0
    df = qdf(conn, "SELECT question_id::text AS question_id, is_correct::int AS y FROM responses WHERE question_id = ANY(%s::uuid[]) AND status='answered'", (question_ids,))
    if not len(df):
        return 0
    d = irt.item_difficulty(df)
    with conn.cursor() as cur:
        cur.execute("SELECT institute_id::text FROM questions WHERE id=%s::uuid", (question_ids[0],))
        iid = cur.fetchone()[0]
        for r in d.itertuples():
            flag = "ok" if r.n >= 30 else "too_few_responses"
            cur.execute("INSERT INTO item_params (question_id, institute_id, model_version, a, b, g, se_b, n_responses, fit_flag) VALUES (%s,%s,%s,1.0,%s,0.0,%s,%s,%s) "
                        "ON CONFLICT (question_id, model_version) DO UPDATE SET b=EXCLUDED.b, se_b=EXCLUDED.se_b, n_responses=EXCLUDED.n_responses, fit_flag=EXCLUDED.fit_flag",
                        (r.question_id, iid, model_version, float(r.b), float(r.se_b), int(r.n), flag))
    return int(len(d))
