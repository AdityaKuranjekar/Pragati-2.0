"""/health, /version, /auth/login, /me."""
from __future__ import annotations

import json
import urllib.request

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import config, deps
from ..db import pg

router = APIRouter()


def _ollama() -> dict:
    try:
        with urllib.request.urlopen(config.OLLAMA_URL + "/api/tags", timeout=0.4) as r:
            tags = json.loads(r.read())
        return {"up": True, "models": [m["name"] for m in tags.get("models", [])]}
    except Exception:
        return {"up": False, "models": []}


@router.get("/health")
def health():
    ok = pg.db_ok()
    return {"status": "ok" if ok else "degraded", "db": ok, "ollama": _ollama(),
            "models_present": (config.MODELS_DIR / "manifest.json").exists()}


@router.get("/version")
def version():
    m = {}
    mp = config.MODELS_DIR / "manifest.json"
    if mp.exists():
        m = json.loads(mp.read_text(encoding="utf-8"))
    return {"api": "pragati-backend/0.1", "model_version": config.MODEL_VERSION,
            "trained_at": m.get("trained_at"), "model_files": m.get("files", {}),
            "asof_demo_date": config.ASOF_NOW, "data": "synthetic"}


class LoginIn(BaseModel):
    institute: str | None = None  # slug (patna_jee) or institute uuid
    institute_id: str | None = None  # front-end field name; same meaning
    role: str
    student_id: str | None = None  # for parent/student demo logins


def _me(p: deps.Principal, user: dict) -> dict:
    inst = next((v for v in deps.institutes_by_slug().values() if v["id"] == p.institute_id), {})
    return {"user_id": p.user_id, "name": user.get("name"), "role": p.role, "lang": p.lang,
            "institute_id": p.institute_id, "institute_slug": deps.slug_of(p.institute_id),
            "institute_name": inst.get("name"), "student_id": p.student_id,
            "counsellor": {"name": inst.get("counsellor_name"), "contact": inst.get("counsellor_contact")}}


@router.post("/auth/login")
def login(body: LoginIn):
    """Demo role switcher: no OTP. Resolves the tenant here with the admin connection, then issues a signed token."""
    body.institute = body.institute or body.institute_id
    if not body.institute:
        raise HTTPException(422, "institute_id is required")
    if body.role not in deps.ROLES:
        raise HTTPException(422, f"role must be one of {deps.ROLES}")
    insts = deps.institutes_by_slug()
    inst = insts.get(body.institute) or next((v for v in insts.values() if v["id"] == body.institute), None)
    if not inst:
        raise HTTPException(404, f"unknown institute '{body.institute}'; seeded: {sorted(insts)}")
    with pg.admin_cursor(commit=False) as cur:
        cur.execute("SELECT id::text, name, lang FROM users WHERE institute_id=%s AND role=%s AND active ORDER BY created_at LIMIT 1",
                    (inst["id"], body.role))
        u = cur.fetchone()
        if not u:
            raise HTTPException(404, f"no demo user for role {body.role}")
        sid = None
        if body.role in ("parent", "student"):
            if body.student_id and config.DEMO_MODE:
                cur.execute("SELECT id::text FROM students WHERE id=%s AND institute_id=%s", (body.student_id, inst["id"]))
            else:
                cur.execute("SELECT s.id::text FROM students s LEFT JOIN guardians g ON g.student_id=s.id "
                            "WHERE s.institute_id=%s AND (s.roll_no = replace(%s,'student-','') OR g.phone=%s) "
                            "ORDER BY s.roll_no LIMIT 1", (inst["id"], _phone_for(cur, u["id"]), _phone_for(cur, u["id"])))
            r = cur.fetchone()
            if not r:
                raise HTTPException(404, "student not found in this institute")
            sid = r["id"]
    p = deps.Principal(user_id=u["id"], institute_id=inst["id"], role=body.role, lang=u["lang"], student_id=sid)
    tok, me = deps.make_token(p), _me(p, u)
    return {"token": tok, "access_token": tok, "token_type": "bearer", "me": me,
            "user": {"id": p.user_id, "role": p.role, "name": me["name"], "institute_id": deps.slug_of(p.institute_id), "student_id": sid}}


def _phone_for(cur, user_id: str) -> str:
    cur.execute("SELECT phone FROM users WHERE id=%s", (user_id,))
    return cur.fetchone()["phone"]


@router.get("/me")
def me(p: deps.Principal = Depends(deps.current_principal)):
    with pg.tenant_conn(p.institute_id) as conn:
        cur = pg.tenant_cursor(conn)
        cur.execute("SELECT name FROM users WHERE id=%s", (p.user_id,))
        u = cur.fetchone() or {}
    return _me(p, u)
