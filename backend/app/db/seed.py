"""Seed PostgreSQL from data/clean/*.parquet (synthetic, seeded generator) and create the demo users.

Only the current (2026) cohort and its facts are loaded: the live product works on the current cohort, and the
models are trained offline on all years from the parquet files (see app/ml/train.py).
Run:  python -m app.db.seed [--institutes patna_jee,lucknow_neet] [--force]
"""
from __future__ import annotations

import argparse
import io
import time
import uuid

import numpy as np
import pandas as pd
import yaml

from .. import config
from . import pg

NS = uuid.UUID("5d0e0f0a-3b1f-4c53-9a0e-aa11bb22cc33")


def _uid(*parts: str) -> str:
    return str(uuid.uuid5(NS, "|".join(parts)))


def _read(name: str, **kw) -> pd.DataFrame:
    return pd.read_parquet(config.DATA_DIR / "clean" / f"{name}.parquet", **kw)


def _fmt_arrays(s: pd.Series) -> pd.Series:
    return s.map(lambda a: "{" + ",".join('"' + str(x).replace('"', '\\"') + '"' for x in a) + "}")


def copy_df(cur, table: str, df: pd.DataFrame, cols: list[str] | None = None) -> int:
    if df is None or len(df) == 0:
        return 0
    cols = cols or list(df.columns)
    buf = io.StringIO()
    df[cols].to_csv(buf, index=False, header=False, na_rep="\\N")
    buf.seek(0)
    cur.copy_expert(f"COPY {table} ({', '.join(cols)}) FROM STDIN WITH (FORMAT csv, NULL '\\N')", buf)
    return len(df)


def _static(cur) -> None:
    topics = yaml.safe_load(open(config.CONTRACTS / "topics.yaml", encoding="utf-8"))
    tdf = pd.DataFrame(topics["topics"])
    tdf["exam"] = tdf["exam"].where(tdf["exam"].isin(["jee_main", "neet_ug"]), "jee_main")
    cols = ["id", "exam", "subject", "chapter", "topic", "name_en", "name_hi", "name_hi_reviewed", "parent_id",
            "class_level", "syllabus_year", "weightage", "verified"]
    copy_df(cur, "topics", tdf, cols)
    pre = pd.DataFrame(topics["topic_prereqs"])
    pre = pre[pre.topic_id.isin(set(tdf.id)) & pre.prereq_topic_id.isin(set(tdf.id))]
    copy_df(cur, "topic_prereqs", pre, ["topic_id", "prereq_topic_id"])
    ms = yaml.safe_load(open(config.CONTRACTS / "marking_schemes.yaml", encoding="utf-8"))["schemes"]
    mdf = pd.DataFrame(list(ms.values()))
    copy_df(cur, "marking_schemes", mdf, ["id", "name", "correct", "wrong", "blank", "partial_rule", "dropped_rule"])
    cur.execute(
        "INSERT INTO model_registry(version, trained_at, data_version, metrics) VALUES (%s, now(), %s, '{}')",
        (config.MODEL_VERSION, "synthetic-seed42"),
    )


def seed(slugs: list[str], force: bool = False) -> dict:
    t0 = time.time()
    applied = pg.apply_schema(force=force)
    with pg.admin_cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM institutes")
        if cur.fetchone()["n"] and not force:
            return {"seeded": False, "reason": "database already seeded (use --force to reseed)"}
    inst = _read("institutes")
    inst["slug"] = inst.city.map(config.SLUG)
    if slugs == ["all"]:
        slugs = list(config.SLUG.values())
    inst = inst[inst.slug.isin(slugs)]
    counts: dict[str, int] = {}
    conn = pg.admin_connect()
    try:
        cur = conn.cursor()
        cur.execute("SET session_replication_role = replica")  # bulk load; FKs are satisfied by construction
        _static(cur)
        copy_df(cur, "institutes", inst.drop(columns="slug"))
        from ..ml import train as ml_train  # item difficulty comes from the trained models

        diff = ml_train.load_item_difficulty()
        for _, I in inst.iterrows():
            iid = I.id
            b = _read("batches", filters=[("institute_id", "==", iid)])
            b = b[b.academic_year == config.CURRENT_YEAR]
            st = _read("students", filters=[("institute_id", "==", iid)])
            st = st[st.academic_year == config.CURRENT_YEAR]
            sids = set(st.id)
            counts[I.slug + ".students"] = len(st)
            copy_df(cur, "batches", b)
            copy_df(cur, "students", st)
            copy_df(cur, "legal_settings", pd.DataFrame([{"institute_id": iid, "minor_ml_risk_enabled": False,
                                                          "active_feature_tier": "D", "retention_months_after_leaving": 12}]),
                    ["institute_id", "minor_ml_risk_enabled", "active_feature_tier", "retention_months_after_leaving"])
            g = _read("guardians", filters=[("institute_id", "==", iid)])
            g = g[g.student_id.isin(sids)]
            copy_df(cur, "guardians", g)
            c = _read("consents", filters=[("institute_id", "==", iid)])
            c = c[c.student_id.isin(sids)].drop(columns=["verified_by_user_id"])
            copy_df(cur, "consents", c)
            q = _read("questions", filters=[("institute_id", "==", iid)])
            copy_df(cur, "questions", q)
            qt = _read("question_topics", filters=[("institute_id", "==", iid)])
            qt = qt[qt.topic_id.isin(set(pd.DataFrame(yaml.safe_load(open(config.CONTRACTS / "topics.yaml", encoding="utf-8"))["topics"]).id))]
            qt["reviewed_by"] = None
            copy_df(cur, "question_topics", qt, ["question_id", "institute_id", "topic_id", "weight", "tagged_by", "confidence", "reviewed_by"])
            d = diff[diff.institute_id == iid].copy()
            d["model_version"] = config.MODEL_VERSION
            copy_df(cur, "item_params", d, ["question_id", "institute_id", "model_version", "a", "b", "g", "se_b", "n_responses", "fit_flag"])
            tests = _read("tests", filters=[("institute_id", "==", iid)])
            tests = tests[tests.batch_id.isin(set(b.id))]
            tids = set(tests.id)
            copy_df(cur, "tests", tests)
            tq = _read("test_questions", filters=[("institute_id", "==", iid)])
            copy_df(cur, "test_questions", tq[tq.test_id.isin(tids)])
            ak = _read("answer_keys", filters=[("institute_id", "==", iid)])
            ak = ak[ak.test_id.isin(tids)].copy()
            ak["accepted_answers"] = _fmt_arrays(ak.accepted_answers)
            ak["created_by"] = None
            copy_df(cur, "answer_keys", ak)
            r = _read("responses", filters=[("institute_id", "==", iid)])
            r = r[r.student_id.isin(sids)]
            counts[I.slug + ".responses"] = copy_df(cur, "responses", r)
            tt = _read("test_totals", filters=[("institute_id", "==", iid)])
            copy_df(cur, "test_totals", tt[tt.test_id.isin(tids) & tt.student_id.isin(sids)])
            a = _read("attendance", filters=[("institute_id", "==", iid)])
            a = a[a.student_id.isin(sids)].copy()
            a["source"] = a["source"].where(a["source"].isin(["csv", "manual", "biometric"]), "csv")
            counts[I.slug + ".attendance"] = copy_df(cur, "attendance", a)
            f = _read("fees", filters=[("institute_id", "==", iid)])
            copy_df(cur, "fees", f[f.student_id.isin(sids)])
            e = _read("engagement", filters=[("institute_id", "==", iid)])
            copy_df(cur, "engagement", e[e.student_id.isin(sids)])
            _demo_users(cur, I, st, g, b)
            print(f"  seeded {I.slug}: {counts[I.slug + '.students']} students, {counts[I.slug + '.responses']} responses", flush=True)
        cur.execute("SET session_replication_role = DEFAULT")
        cur.execute("ANALYZE")
        conn.commit()
    finally:
        conn.close()
    return {"seeded": True, "schema_applied": applied, "seconds": round(time.time() - t0, 1), "counts": counts}


def _demo_users(cur, I, st: pd.DataFrame, g: pd.DataFrame, b: pd.DataFrame) -> None:
    n = int(I.slug.__hash__() % 10)  # not used for identity, only to keep phones short
    base = {"owner": ("Owner (demo)", "en"), "admin": ("Admin (demo)", "en"), "teacher": ("Teacher (demo)", "hi"),
            "mentor": ("Mentor (demo)", "hi")}
    rows = []
    for i, (role, (name, lang)) in enumerate(base.items()):
        rows.append({"id": _uid(I.id, role), "institute_id": I.id, "role": role, "phone": f"+91-90000-0{i}00{n}",
                     "name": name, "lang": lang, "active": True})
    demo = st.sort_values("roll_no").iloc[0]
    gd = g[g.student_id == demo.id]
    rows.append({"id": _uid(I.id, "student"), "institute_id": I.id, "role": "student", "phone": f"student-{demo.roll_no}",
                 "name": demo["name"], "lang": "hi", "active": True})
    rows.append({"id": _uid(I.id, "parent"), "institute_id": I.id, "role": "parent",
                 "phone": gd.phone.iloc[0] if len(gd) else "+91-90000-09999",
                 "name": gd.name.iloc[0] if len(gd) else "Guardian", "lang": "hi", "active": True})
    copy_df(cur, "users", pd.DataFrame(rows), ["id", "institute_id", "role", "phone", "name", "lang", "active"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--institutes", default=config.SEED_INSTITUTES)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    print(seed([s.strip() for s in args.institutes.split(",")], force=args.force))
