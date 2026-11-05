"""Prototype API routes (PROTOTYPE_PLAN S3). Tenancy rules:

* The institute comes from the authenticated principal only (auth.py). Nothing the client sends in the
  body, query string or headers can change it; unknown query parameters and headers are ignored and
  unknown body fields are a 422.
* Every learner and cohort is looked up under (principal.institute_id, id) before any read or write.
  Another institute's record is indistinguishable from a missing one (404).
* Order of checks: role, then institute (lookup under the principal's institute, 404 if absent), then
  cohort scope. Students reach only their own learner (403 before any lookup, so the existence of
  other students is not revealed). A teacher reads a cohort, or a learner in it, only if assigned to
  that cohort (403 otherwise). Teachers cannot write attempts. The owner role assigns teachers to
  cohorts and reads no learner data.
* The day is a server-side per-learner counter (service.py); the client cannot send one.
* An attempt is accepted only for an item the server served to that learner for that concept, once.
* The demo flag is server configuration, never a request parameter, and is echoed in next-step.
No LLM, no response-time or hint data anywhere.
"""
from __future__ import annotations

import os
from typing import Sequence

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, StrictBool, StrictStr, constr

from app.intelligence.chain import NAMES, demo_graph
from app.intelligence.graph import Graph
from app.intelligence.mastery import POLICY_VERSION, ConceptState, learner_state
from app.intelligence.planner import AdaptiveSession, PlannerConfig
from app.intelligence.policy import cohort_bottlenecks
from app.intelligence.selection import BankItem

from .auth import Principal, StubTokenAuth, current_principal
from .repository import ConflictingEvent, LearnerRecord, NotServed, Repository
from .service import schedules_for

DEFAULT_BUDGET_ITEMS = 50   # demo default for the budget input; the real value will come from the goal


class AttemptIn(BaseModel):
    """ADR-003 v0. learner_id comes from the path and seq is assigned by the server, so neither is
    accepted here. Any other field (response time, hints, institute_id, ...) is a 422."""
    model_config = ConfigDict(extra="forbid", strict=True)
    event_id: constr(strip_whitespace=True, min_length=1, max_length=128)
    concept_id: StrictStr
    item_id: StrictStr
    correct: StrictBool


def _states_json(states: dict[str, ConceptState]) -> list[dict]:
    return [{"concept_id": s.concept_id, "band": s.band, "p_known": s.p_known,
             "uncertainty": round(s.uncertainty, 4), "evidence_count": s.n} for s in states.values()]


def create_app(repo: Repository, auth: StubTokenAuth, bank: Sequence[BankItem],
               graph: Graph | None = None, names: dict[str, str] | None = None,
               demo_allow_unapproved: bool | None = None) -> FastAPI:
    graph = graph or demo_graph()
    names = names or NAMES
    if demo_allow_unapproved is None:
        demo_allow_unapproved = os.environ.get("PRAGATI_DEMO_UNAPPROVED") == "1"
    bank = list(bank)

    app = FastAPI(title="Pragati 2.0 prototype API", version="s3-v0")
    app.state.auth, app.state.repo = auth, repo

    def learner_access(write: bool):
        def dep(learner_id: str, p: Principal = Depends(current_principal)) -> LearnerRecord:
            if p.role == "owner":
                raise HTTPException(403, "this role has no access to learner data")
            if p.role == "student" and p.learner_id != learner_id:
                raise HTTPException(403, "students may reach only their own learner")
            if write and p.role != "student":
                raise HTTPException(403, "only the learner may submit attempts")
            rec = repo.get_learner(p.institute_id, learner_id)          # institute check first
            if rec is None:
                raise HTTPException(404, "learner not found")
            if p.role == "teacher" and not (
                    rec.cohort_id and repo.is_teacher_assigned(p.institute_id, rec.cohort_id, p.user_id)):
                raise HTTPException(403, "teacher is not assigned to this learner's cohort")   # cohort second
            return rec
        return dep

    def teacher_cohort(cohort_id: str, p: Principal = Depends(current_principal)):
        if p.role != "teacher":
            raise HTTPException(403, "teacher only")
        rec = repo.get_cohort(p.institute_id, cohort_id)                # institute check first
        if rec is None:
            raise HTTPException(404, "cohort not found")
        if not repo.is_teacher_assigned(p.institute_id, cohort_id, p.user_id):   # cohort second
            raise HTTPException(403, "teacher is not assigned to this cohort")
        return rec

    def states_of(rec: LearnerRecord) -> dict[str, ConceptState]:
        return learner_state(repo.events_for(rec.institute_id, rec.learner_id), graph.nodes)

    @app.get("/api/prototype/health")
    def health():
        return {"status": "ok", "policy_version": POLICY_VERSION}

    @app.put("/api/prototype/cohorts/{cohort_id}/teachers/{teacher_user_id}")
    def assign_teacher(cohort_id: str, teacher_user_id: str, response: Response,
                       p: Principal = Depends(current_principal)):
        if p.role != "owner":
            raise HTTPException(403, "owner only")
        if repo.get_cohort(p.institute_id, cohort_id) is None:
            raise HTTPException(404, "cohort not found")
        if repo.get_user_role(p.institute_id, teacher_user_id) != "teacher":
            raise HTTPException(404, "teacher not found")
        created = repo.assign_teacher(p.institute_id, cohort_id, teacher_user_id)
        response.status_code = 201 if created else 200
        return {"cohort_id": cohort_id, "teacher_user_id": teacher_user_id, "assigned": True}

    @app.post("/api/prototype/learners/{learner_id}/events")
    def post_event(body: AttemptIn, response: Response,
                   rec: LearnerRecord = Depends(learner_access(write=True))):
        if body.concept_id not in graph.nodes:
            raise HTTPException(422, "unknown concept_id")
        if not any(b.item_id == body.item_id and b.topic_id == body.concept_id for b in bank):
            raise HTTPException(422, "unknown item_id for this concept")
        try:
            ev, created = repo.append_event(rec.institute_id, rec.learner_id, body.event_id,
                                            body.concept_id, body.item_id, body.correct)
        except ConflictingEvent:
            raise HTTPException(409, "event_id already used with different content")
        except NotServed as e:
            raise HTTPException(422, str(e))
        response.status_code = 201 if created else 200
        return {"event_id": ev.event_id, "seq": ev.seq, "duplicate": not created,
                "day": repo.day_of(rec.institute_id, rec.learner_id),
                "concepts": _states_json(states_of(rec)), "policy_version": POLICY_VERSION}

    @app.get("/api/prototype/learners/{learner_id}/state")
    def get_state(rec: LearnerRecord = Depends(learner_access(write=False))):
        return {"learner_id": rec.learner_id, "goal": rec.goal, "concepts": _states_json(states_of(rec)),
                "uncertainty_note": "heuristic 1/sqrt(n+1); not a calibrated interval",
                "policy_version": POLICY_VERSION}

    @app.get("/api/prototype/learners/{learner_id}/next-step")
    def get_next_step(rec: LearnerRecord = Depends(learner_access(write=False)),
                      p: Principal = Depends(current_principal),
                      budget_remaining: int = Query(DEFAULT_BUDGET_ITEMS, ge=0)):
        events = repo.events_for(rec.institute_id, rec.learner_id)
        kinds = {s.item_id: s.kind for s in repo.served_for(rec.institute_id, rec.learner_id)}
        day = repo.day_of(rec.institute_id, rec.learner_id)          # server-side; never from the client
        session = AdaptiveSession(rec.learner_id, graph, rec.goal, bank,
                                  PlannerConfig(allow_unapproved_demo=demo_allow_unapproved), names)
        session.events = events
        session.schedules = schedules_for(events, kinds)
        step = session.next_step(day, budget_remaining)
        if p.role == "student" and step.item_id is not None and step.concept_id is not None:
            # Only the learner's own call counts as serving; a teacher looking does not.
            repo.mark_served(rec.institute_id, rec.learner_id, step.concept_id, step.item_id, step.kind)
        return jsonable_encoder({
            "kind": step.kind, "concept_id": step.concept_id, "item_id": step.item_id,
            "reason": step.reason, "trace": step.trace,
            "recommendation": step.recommendation, "selection": step.selection,
            "demo_unapproved_allowed": demo_allow_unapproved,
            "engine_inputs": {"day": day, "budget_remaining": budget_remaining},
            "policy_version": POLICY_VERSION,
        })

    @app.get("/api/prototype/cohorts/{cohort_id}/bottlenecks")
    def get_bottlenecks(cohort=Depends(teacher_cohort)):
        members = {}
        for lid in repo.cohort_learner_ids(cohort.institute_id, cohort.cohort_id):
            lrec = repo.get_learner(cohort.institute_id, lid)
            if lrec is not None:
                members[lid] = states_of(lrec)
        return {"cohort_id": cohort.cohort_id, "learner_count": len(members),
                "bottlenecks": cohort_bottlenecks(graph, members), "policy_version": POLICY_VERSION}

    return app
