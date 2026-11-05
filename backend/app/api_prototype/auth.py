"""STUB authentication. NOT FOR PRODUCTION.

A bearer token maps to (user, institute, role, learner). The map is configuration held in memory.
It stands in for the real provider (Supabase or Firebase, Phase 0) so that tenancy is enforced from
a principal and never from anything else the client sends. The institute id is read ONLY from the
principal; the body, query string and headers other than Authorization are never consulted.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from fastapi import Header, HTTPException, Request

ROLES = frozenset({"student", "teacher", "owner"})


@dataclass(frozen=True)
class Principal:
    user_id: str
    institute_id: str
    role: str
    learner_id: str | None = None   # set for a student: the one learner record this user may touch


class StubTokenAuth:
    def __init__(self, tokens: Mapping[str, Principal]):
        for p in tokens.values():
            if p.role not in ROLES:
                raise ValueError(f"unknown role {p.role}")
            if p.role == "student" and not p.learner_id:
                raise ValueError("a student principal needs a learner_id")
        self._tokens = dict(tokens)

    def resolve(self, authorization: str | None) -> Principal:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(401, "missing bearer token")
        principal = self._tokens.get(authorization[7:].strip())
        if principal is None:
            raise HTTPException(401, "invalid token")
        return principal


def current_principal(request: Request, authorization: str | None = Header(default=None)) -> Principal:
    return request.app.state.auth.resolve(authorization)
