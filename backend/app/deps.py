"""Auth token, principal, role checks and the tenant-scoped DB dependency."""
from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Iterator

from fastapi import Depends, Header, HTTPException
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from . import config
from .db import pg

_ser = URLSafeTimedSerializer(config.SECRET_KEY, salt="pragati-demo-token")

ROLES = ("owner", "admin", "teacher", "mentor", "parent", "student")
STAFF = ("owner", "admin", "teacher", "mentor")
MANAGERS = ("owner", "admin", "teacher")


@dataclass
class Principal:
    user_id: str
    institute_id: str
    role: str
    lang: str
    student_id: str | None = None

    @property
    def is_family(self) -> bool:
        return self.role in ("parent", "student")


def make_token(p: Principal) -> str:
    return _ser.dumps({"u": p.user_id, "i": p.institute_id, "r": p.role, "l": p.lang, "s": p.student_id})


def current_principal(authorization: str | None = Header(default=None)) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing bearer token")
    try:
        d = _ser.loads(authorization.split(" ", 1)[1].strip(), max_age=config.TOKEN_MAX_AGE_S)
    except SignatureExpired:
        raise HTTPException(401, "token expired")
    except BadSignature:
        raise HTTPException(401, "invalid token")
    return Principal(user_id=d["u"], institute_id=d["i"], role=d["r"], lang=d["l"], student_id=d.get("s"))


def require(*roles: str):
    def dep(p: Principal = Depends(current_principal)) -> Principal:
        if p.role not in roles:
            raise HTTPException(403, f"role '{p.role}' may not do this")
        return p

    return dep


def tenant(p: Principal = Depends(current_principal)) -> Iterator:
    """Yield a connection locked to the caller's institute (row-level security)."""
    with pg.tenant_conn(p.institute_id) as conn:
        yield conn


@functools.lru_cache(maxsize=1)
def institutes_by_slug() -> dict[str, dict]:
    from . import config as c

    with pg.admin_cursor(commit=False) as cur:
        cur.execute("SELECT id::text, name, city, weekly_off_day, counsellor_name, counsellor_contact, exam_focus, plan FROM institutes")
        rows = cur.fetchall()
    return {c.SLUG.get(r["city"], r["city"].lower()): dict(r) for r in rows}


def slug_of(institute_id: str) -> str:
    for s, r in institutes_by_slug().items():
        if r["id"] == str(institute_id):
            return s
    return "unknown"


def guard_student(p: Principal, student_id: str) -> None:
    """Family roles may only touch their own child; everyone else is limited to their tenant by RLS."""
    if p.is_family and p.student_id != str(student_id):
        raise HTTPException(403, "you may only view your own record")
