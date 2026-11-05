"""E13: tenant isolation for every route, cohort scope, and role checks. Runs on both repositories."""
import pytest

from .conftest import A, F, INST_A, INST_B, R, attempt, hdr, item_for, serve

LEARNER_ROUTES = [("GET", "/state"), ("GET", "/next-step"), ("POST", "/events")]


def call(client, method, path, token, **kw):
    kw.setdefault("headers", {}).update(hdr(token) if token else {})
    if method == "POST":
        kw.setdefault("json", attempt("ev-x"))
    return client.request(method, path, **kw)


def seed_b(repo):
    serve(repo, "b-stu1", R, inst=INST_B)
    repo.append_event(INST_B, "b-stu1", "b-ev-0", R, item_for(R), False)


# ---- unauthenticated -----------------------------------------------------------------------
@pytest.mark.parametrize("method,path", [
    ("GET", "/api/prototype/learners/a-stu1/state"), ("GET", "/api/prototype/learners/a-stu1/next-step"),
    ("POST", "/api/prototype/learners/a-stu1/events"), ("GET", "/api/prototype/cohorts/cohort-A/bottlenecks"),
    ("PUT", "/api/prototype/cohorts/cohort-A/teachers/u-a-teacher2")])
@pytest.mark.parametrize("token", [None, "wrong-token"])
def test_no_or_bad_token_is_401(env, method, path, token):
    _, c = env
    assert call(c, method, path, token).status_code == 401


# ---- cross-institute, each learner route, each role ---------------------------------------
@pytest.mark.parametrize("method,suffix", LEARNER_ROUTES)
@pytest.mark.parametrize("token,expected", [
    ("tok-a-stu1", {403}), ("tok-a-teacher", {403, 404}), ("tok-a-owner", {403})])
def test_institute_a_user_cannot_reach_institute_b_learner(env, method, suffix, token, expected):
    repo, c = env
    seed_b(repo)
    r = call(c, method, f"/api/prototype/learners/b-stu1{suffix}", token)
    assert r.status_code in expected
    assert INST_B not in r.text and "b-stu1" not in r.text.replace("learner not found", "")


@pytest.mark.parametrize("method,suffix", LEARNER_ROUTES)
def test_institute_b_user_cannot_reach_institute_a_learner(env, method, suffix):
    _, c = env
    assert call(c, method, f"/api/prototype/learners/a-stu1{suffix}", "tok-b-teacher").status_code == (403 if method == "POST" else 404)
    assert call(c, method, f"/api/prototype/learners/a-stu1{suffix}", "tok-b-stu1").status_code == 403
    assert call(c, method, f"/api/prototype/learners/a-stu1{suffix}", "tok-b-owner").status_code == 403


def test_teacher_of_other_institute_gets_404_even_with_same_ids_assigned(env):
    repo, c = env
    # B's teacher is assigned to B's cohort only; A's cohort id does not exist for B
    assert call(c, "GET", "/api/prototype/cohorts/cohort-A/bottlenecks", "tok-b-teacher").status_code == 404


@pytest.mark.parametrize("token", ["tok-a-teacher", "tok-b-teacher"])
def test_teacher_cannot_read_other_institute_cohort(env, token):
    _, c = env
    other = "cohort-B" if token == "tok-a-teacher" else "cohort-A"
    r = call(c, "GET", f"/api/prototype/cohorts/{other}/bottlenecks", token)
    assert r.status_code == 404 and "learner_count" not in r.text


# ---- forged institute_id: body, query, header --------------------------------------------
FORGE = {
    "query": lambda: {"params": {"institute_id": INST_B}},
    "header": lambda: {"headers": {"X-Institute-Id": INST_B, "X-Tenant": INST_B, "institute_id": INST_B}},
}


@pytest.mark.parametrize("where", ["query", "header"])
@pytest.mark.parametrize("method,suffix", LEARNER_ROUTES)
def test_forged_institute_in_query_or_header_does_not_open_institute_b(env, where, method, suffix):
    repo, c = env
    seed_b(repo)
    r = call(c, method, f"/api/prototype/learners/b-stu1{suffix}", "tok-a-teacher", **FORGE[where]())
    assert r.status_code == (403 if method == "POST" else 404)   # POST: teachers never write
    r = call(c, method, f"/api/prototype/learners/b-stu1{suffix}", "tok-a-stu1", **FORGE[where]())
    assert r.status_code == 403


@pytest.mark.parametrize("where", ["query", "header"])
def test_forged_institute_on_cohort_and_assign_routes(env, where):
    _, c = env
    assert call(c, "GET", "/api/prototype/cohorts/cohort-B/bottlenecks", "tok-a-teacher", **FORGE[where]()).status_code == 404
    r = call(c, "PUT", "/api/prototype/cohorts/cohort-B/teachers/u-b-teacher", "tok-a-owner", **FORGE[where]())
    assert r.status_code == 404


def test_forged_institute_in_body_is_refused_and_cannot_target_b(env):
    repo, c = env
    serve(repo, "a-stu1", A)
    body = {**attempt("forged-1"), "institute_id": INST_B}
    assert c.post("/api/prototype/learners/b-stu1/events", json=body, headers=hdr("tok-a-stu1")).status_code == 403
    assert c.post("/api/prototype/learners/b-stu1/events", json=body, headers=hdr("tok-a-teacher")).status_code in {403, 404}
    assert c.post("/api/prototype/learners/a-stu1/events", json=body, headers=hdr("tok-a-stu1")).status_code == 422
    assert repo.events_for(INST_A, "a-stu1") == [] and repo.events_for(INST_B, "b-stu1") == []


def test_forged_institute_in_body_of_assign_route_is_ignored(env):
    repo, c = env
    r = c.put("/api/prototype/cohorts/cohort-B/teachers/u-b-teacher", json={"institute_id": INST_B},
              headers=hdr("tok-a-owner"))
    assert r.status_code == 404


@pytest.mark.parametrize("where", ["query", "header"])
def test_forged_institute_on_own_learner_changes_nothing(env, where):
    repo, c = env
    seed_b(repo)
    plain = c.get("/api/prototype/learners/a-stu1/state", headers=hdr("tok-a-stu1")).json()
    kw = ({"params": {"institute_id": INST_B}} if where == "query"
          else {"headers": {**hdr("tok-a-stu1"), "X-Institute-Id": INST_B}})
    kw.setdefault("headers", hdr("tok-a-stu1"))
    forged = c.get("/api/prototype/learners/a-stu1/state", **kw)
    assert forged.status_code == 200 and forged.json() == plain


def test_forged_header_cannot_reroute_a_write_into_b(env):
    repo, c = env
    serve(repo, "a-stu1", A)
    r = c.post("/api/prototype/learners/a-stu1/events", json=attempt("hdr-1"),
               headers={**hdr("tok-a-stu1"), "X-Institute-Id": INST_B})
    assert r.status_code == 201
    assert len(repo.events_for(INST_A, "a-stu1")) == 1 and repo.events_for(INST_B, "a-stu1") == []


# ---- same institute, student versus student ----------------------------------------------
@pytest.mark.parametrize("method,suffix", LEARNER_ROUTES)
def test_student_cannot_reach_another_student_in_same_institute(env, method, suffix):
    repo, c = env
    serve(repo, "a-stu2", A)
    repo.append_event(INST_A, "a-stu2", "s2-0", A, item_for(A), True)
    assert call(c, method, f"/api/prototype/learners/a-stu2{suffix}", "tok-a-stu1").status_code == 403
    assert repo.events_for(INST_A, "a-stu1") == []


def test_student_cannot_read_another_student_even_if_unknown_id(env):
    _, c = env
    assert call(c, "GET", "/api/prototype/learners/nobody/state", "tok-a-stu1").status_code == 403


def test_next_step_by_another_student_does_not_mark_items_served(env):
    repo, c = env
    call(c, "GET", "/api/prototype/learners/a-stu2/next-step", "tok-a-stu1")
    assert repo.served_for(INST_A, "a-stu2") == []


# ---- role: student on the teacher route ---------------------------------------------------
@pytest.mark.parametrize("token", ["tok-a-stu1", "tok-b-stu1"])
def test_student_cannot_call_teacher_route(env, token):
    _, c = env
    for cohort in ("cohort-A", "cohort-B"):
        assert call(c, "GET", f"/api/prototype/cohorts/{cohort}/bottlenecks", token).status_code == 403


# ---- item 1: teacher scope by cohort, owner assigns --------------------------------------
def test_assigned_teacher_reads_cohort_and_learner(env):
    _, c = env
    assert call(c, "GET", "/api/prototype/cohorts/cohort-A/bottlenecks", "tok-a-teacher").status_code == 200
    for suffix in ("/state", "/next-step"):
        assert call(c, "GET", f"/api/prototype/learners/a-stu1{suffix}", "tok-a-teacher").status_code == 200


def test_assigned_teacher_still_cannot_write_attempts(env):
    _, c = env
    assert call(c, "POST", "/api/prototype/learners/a-stu1/events", "tok-a-teacher").status_code == 403


def test_unassigned_teacher_of_same_institute_gets_403_everywhere(env):
    _, c = env
    assert call(c, "GET", "/api/prototype/cohorts/cohort-A/bottlenecks", "tok-a-teacher2").status_code == 403
    for method, suffix in LEARNER_ROUTES:
        assert call(c, method, f"/api/prototype/learners/a-stu1{suffix}", "tok-a-teacher2").status_code == 403


def test_cohort_check_comes_after_institute_check(env):
    _, c = env
    # unassigned teacher: unknown cohort in own institute is 404 (institute scope), known one is 403
    assert call(c, "GET", "/api/prototype/cohorts/no-such/bottlenecks", "tok-a-teacher2").status_code == 404
    assert call(c, "GET", "/api/prototype/learners/no-such/state", "tok-a-teacher2").status_code == 404


def test_teacher_cannot_read_learner_without_a_cohort(env):
    repo, c = env
    from app.api_prototype.repository import LearnerRecord
    repo.add_learner(LearnerRecord(INST_A, "a-loose", None, F))
    assert call(c, "GET", "/api/prototype/learners/a-loose/state", "tok-a-teacher").status_code == 403


def test_owner_assigns_teacher_and_access_follows(env):
    repo, c = env
    assert call(c, "GET", "/api/prototype/cohorts/cohort-A/bottlenecks", "tok-a-teacher2").status_code == 403
    r = call(c, "PUT", "/api/prototype/cohorts/cohort-A/teachers/u-a-teacher2", "tok-a-owner")
    assert r.status_code == 201 and r.json()["assigned"] is True
    assert call(c, "PUT", "/api/prototype/cohorts/cohort-A/teachers/u-a-teacher2", "tok-a-owner").status_code == 200  # idempotent
    assert call(c, "GET", "/api/prototype/cohorts/cohort-A/bottlenecks", "tok-a-teacher2").status_code == 200
    assert call(c, "GET", "/api/prototype/learners/a-stu1/state", "tok-a-teacher2").status_code == 200


@pytest.mark.parametrize("token", ["tok-a-teacher", "tok-a-teacher2", "tok-a-stu1", "tok-b-owner"])
def test_only_the_owner_of_the_institute_can_assign(env, token):
    repo, c = env
    r = call(c, "PUT", "/api/prototype/cohorts/cohort-A/teachers/u-a-teacher2", token)
    assert r.status_code in ({403} if token != "tok-b-owner" else {404})
    assert not repo.is_teacher_assigned(INST_A, "cohort-A", "u-a-teacher2")


def test_owner_cannot_assign_a_teacher_of_another_institute_or_a_non_teacher(env):
    repo, c = env
    assert call(c, "PUT", "/api/prototype/cohorts/cohort-A/teachers/u-b-teacher", "tok-a-owner").status_code == 404
    assert call(c, "PUT", "/api/prototype/cohorts/cohort-A/teachers/u-a-stu1", "tok-a-owner").status_code == 404
    assert call(c, "PUT", "/api/prototype/cohorts/no-such/teachers/u-a-teacher2", "tok-a-owner").status_code == 404
    assert not repo.is_teacher_assigned(INST_A, "cohort-A", "u-b-teacher")


def test_owner_has_no_learner_or_bottleneck_access(env):
    _, c = env
    assert call(c, "GET", "/api/prototype/cohorts/cohort-A/bottlenecks", "tok-a-owner").status_code == 403
    assert call(c, "GET", "/api/prototype/learners/a-stu1/state", "tok-a-owner").status_code == 403


def test_cohort_members_come_from_the_same_institute_only(env):
    repo, c = env
    from app.api_prototype.repository import LearnerRecord
    # B has a learner whose cohort id equals A's cohort id: still B's cohort, never counted for A
    repo.add_cohort(__import__("app.api_prototype.repository", fromlist=["CohortRecord"]).CohortRecord(INST_B, "cohort-A"))
    repo.add_learner(LearnerRecord(INST_B, "b-in-cohort-A", "cohort-A", F))
    r = c.get("/api/prototype/cohorts/cohort-A/bottlenecks", headers=hdr("tok-a-teacher"))
    assert r.status_code == 200 and r.json()["learner_count"] == 2   # a-stu1, a-stu2 only


# ---- health -------------------------------------------------------------------------------
def test_health_is_open_and_carries_no_tenant_data(env):
    repo, c = env
    seed_b(repo)
    r = c.get("/api/prototype/health")
    assert r.status_code == 200
    for s in (INST_A, INST_B, "a-stu", "b-stu", "cohort"):
        assert s not in r.text


# ---- item 5: every route ------------------------------------------------------------------
PUBLIC = {("GET", "/api/prototype/health"), ("GET", "/openapi.json"), ("GET", "/docs"),
          ("GET", "/docs/oauth2-redirect"), ("GET", "/redoc")}


def _routes(app):
    from fastapi.routing import APIRoute
    out = []
    for r in app.routes:
        for m in getattr(r, "methods", None) or ():
            if m not in ("HEAD", "OPTIONS"):
                out.append((m, r.path, r))
    return out


def _fill(path):
    return (path.replace("{learner_id}", "a-stu1").replace("{cohort_id}", "cohort-A")
            .replace("{teacher_user_id}", "u-a-teacher2"))


def test_every_route_not_listed_public_requires_a_principal(env):
    from app.api_prototype.auth import current_principal
    _, c = env
    non_public = [(m, p, r) for m, p, r in _routes(c.app) if (m, p) not in PUBLIC]
    assert len(non_public) >= 5
    for m, p, r in non_public:
        # structural: the route's dependency tree includes current_principal
        def walks(dep):
            return dep.call is current_principal or any(walks(d) for d in dep.dependencies)
        assert walks(r.dependant), f"{m} {p} does not depend on current_principal"
        # behavioural: no token, bad token, malformed header all give 401 before anything else
        for headers in ({}, hdr("nope"), {"Authorization": "Basic abc"}):
            resp = c.request(m, _fill(p), headers=headers, json={} if m in ("POST", "PUT") else None)
            assert resp.status_code == 401, (m, p, resp.status_code)


def test_public_routes_are_exactly_the_declared_set(env):
    _, c = env
    paths = {(m, p) for m, p, _ in _routes(c.app)}
    declared_public_present = paths & PUBLIC
    assert ("GET", "/api/prototype/health") in declared_public_present
    unexpected = {(m, p) for m, p in paths if (m, p) not in PUBLIC} - {
        ("GET", "/api/prototype/learners/{learner_id}/state"), ("GET", "/api/prototype/learners/{learner_id}/next-step"),
        ("POST", "/api/prototype/learners/{learner_id}/events"), ("GET", "/api/prototype/cohorts/{cohort_id}/bottlenecks"),
        ("PUT", "/api/prototype/cohorts/{cohort_id}/teachers/{teacher_user_id}")}
    assert unexpected == set(), f"new route not covered by the E13 tests: {unexpected}"


LEARNER_PATHS = [(m, p) for m, p in [("GET", "/state"), ("GET", "/next-step"), ("POST", "/events")]]


@pytest.mark.parametrize("token,inst_marker", [("tok-b-stu1", INST_A), ("tok-b-teacher", INST_A), ("tok-b-owner", INST_A),
                                                ("tok-a-stu1", INST_B), ("tok-a-teacher", INST_B), ("tok-a-owner", INST_B)])
def test_no_route_returns_data_to_a_caller_of_another_institute(env, token, inst_marker):
    """Sweep every non-public route with every foreign principal; nothing of the other side may come back."""
    repo, c = env
    seed_b(repo)
    serve(repo, "a-stu1", A)
    repo.append_event(INST_A, "a-stu1", "a-ev-0", A, item_for(A), True)
    own_ids = {"a-stu1", "a-stu2", "cohort-A", "u-a-teacher"} if inst_marker == INST_A else {"b-stu1", "cohort-B", "u-b-teacher"}
    for m, p, r in _routes(c.app):
        if (m, p) in PUBLIC:
            continue
        target = (_fill(p).replace("a-stu1", "b-stu1").replace("cohort-A", "cohort-B").replace("u-a-teacher2", "u-b-teacher")
                  if inst_marker == INST_B else _fill(p))
        resp = c.request(m, target, headers=hdr(token), json=attempt("sweep") if m in ("POST", "PUT") else None)
        assert resp.status_code in {403, 404}, (token, m, target, resp.status_code, resp.text)
        for ident in own_ids:
            assert ident not in resp.text.replace("learner not found", "").replace("cohort not found", ""), (m, target, resp.text)
