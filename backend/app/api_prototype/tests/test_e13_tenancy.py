"""E13: tenant isolation for every route."""
import pytest

from .conftest import A, R, attempt, build, hdr, item_for

LEARNER_ROUTES = [("GET", "/state"), ("GET", "/next-step"), ("POST", "/events")]


def call(client, method, path, token, **kw):
    kw.setdefault("headers", {}).update(hdr(token) if token else {})
    if method == "POST":
        kw.setdefault("json", attempt("ev-x"))
    return client.request(method, path, **kw)


def seed_b(repo):
    repo.append_event("inst-B", "b-stu1", "b-ev-0", R, item_for(R), False)


# ---- unauthenticated -----------------------------------------------------------------------
@pytest.mark.parametrize("method,path", [
    ("GET", "/api/prototype/learners/a-stu1/state"), ("GET", "/api/prototype/learners/a-stu1/next-step"),
    ("POST", "/api/prototype/learners/a-stu1/events"), ("GET", "/api/prototype/cohorts/cohort-A/bottlenecks")])
@pytest.mark.parametrize("token", [None, "wrong-token"])
def test_no_or_bad_token_is_401(env, method, path, token):
    _, c = env
    assert call(c, method, path, token).status_code == 401


# ---- cross-institute, each learner route, each role ---------------------------------------
@pytest.mark.parametrize("method,suffix", LEARNER_ROUTES)
@pytest.mark.parametrize("token,expected", [
    ("tok-a-stu1", {403}), ("tok-a-teacher", {403, 404})])
def test_institute_a_user_cannot_reach_institute_b_learner(env, method, suffix, token, expected):
    repo, c = env
    seed_b(repo)
    r = call(c, method, f"/api/prototype/learners/b-stu1{suffix}", token)
    assert r.status_code in expected
    assert "inst-B" not in r.text and "b-stu1" not in r.text.replace("learner not found", "")


@pytest.mark.parametrize("method,suffix", LEARNER_ROUTES)
def test_institute_b_user_cannot_reach_institute_a_learner(env, method, suffix):
    _, c = env
    assert call(c, method, f"/api/prototype/learners/a-stu1{suffix}", "tok-b-teacher").status_code in {403, 404}
    assert call(c, method, f"/api/prototype/learners/a-stu1{suffix}", "tok-b-stu1").status_code == 403


@pytest.mark.parametrize("token", ["tok-a-teacher", "tok-b-teacher"])
def test_teacher_cannot_read_other_institute_cohort(env, token):
    _, c = env
    other = "cohort-B" if token == "tok-a-teacher" else "cohort-A"
    r = call(c, "GET", f"/api/prototype/cohorts/{other}/bottlenecks", token)
    assert r.status_code in {403, 404}
    assert "learner_count" not in r.text


# ---- forged institute_id: body, query, header --------------------------------------------
FORGE = {
    "query": lambda: {"params": {"institute_id": "inst-B"}},
    "header": lambda: {"headers": {"X-Institute-Id": "inst-B", "X-Tenant": "inst-B", "institute_id": "inst-B"}},
}


@pytest.mark.parametrize("where", ["query", "header"])
@pytest.mark.parametrize("method,suffix", LEARNER_ROUTES)
def test_forged_institute_in_query_or_header_does_not_open_institute_b(env, where, method, suffix):
    repo, c = env
    seed_b(repo)
    r = call(c, method, f"/api/prototype/learners/b-stu1{suffix}", "tok-a-teacher", **FORGE[where]())
    assert r.status_code in {403, 404}
    r = call(c, method, f"/api/prototype/learners/b-stu1{suffix}", "tok-a-stu1", **FORGE[where]())
    assert r.status_code == 403


@pytest.mark.parametrize("where", ["query", "header"])
def test_forged_institute_on_cohort_route(env, where):
    _, c = env
    r = call(c, "GET", "/api/prototype/cohorts/cohort-B/bottlenecks", "tok-a-teacher", **FORGE[where]())
    assert r.status_code in {403, 404}


def test_forged_institute_in_body_is_refused_and_cannot_target_b(env):
    repo, c = env
    body = {**attempt("forged-1"), "institute_id": "inst-B"}
    r = c.post("/api/prototype/learners/b-stu1/events", json=body, headers=hdr("tok-a-stu1"))
    assert r.status_code in {403, 404}
    r = c.post("/api/prototype/learners/a-stu1/events", json=body, headers=hdr("tok-a-stu1"))
    assert r.status_code == 422
    assert repo.events_for("inst-A", "a-stu1") == [] and repo.events_for("inst-B", "b-stu1") == []
    # also with a teacher token on B's learner
    r = c.post("/api/prototype/learners/b-stu1/events", json=body, headers=hdr("tok-a-teacher"))
    assert r.status_code in {403, 404}


@pytest.mark.parametrize("where", ["query", "header"])
def test_forged_institute_on_own_learner_changes_nothing(env, where):
    repo, c = env
    seed_b(repo)
    plain = c.get("/api/prototype/learners/a-stu1/state", headers=hdr("tok-a-stu1")).json()
    kw = ({"params": {"institute_id": "inst-B"}} if where == "query"
          else {"headers": {**hdr("tok-a-stu1"), "X-Institute-Id": "inst-B"}})
    kw.setdefault("headers", hdr("tok-a-stu1"))
    forged = c.get("/api/prototype/learners/a-stu1/state", **kw)
    assert forged.status_code == 200 and forged.json() == plain


def test_forged_header_cannot_reroute_a_write_into_b(env):
    repo, c = env
    r = c.post("/api/prototype/learners/a-stu1/events", json=attempt("hdr-1"),
               headers={**hdr("tok-a-stu1"), "X-Institute-Id": "inst-B"})
    assert r.status_code == 201
    assert len(repo.events_for("inst-A", "a-stu1")) == 1 and repo.events_for("inst-B", "a-stu1") == []


# ---- same institute, student versus student ----------------------------------------------
@pytest.mark.parametrize("method,suffix", LEARNER_ROUTES)
def test_student_cannot_reach_another_student_in_same_institute(env, method, suffix):
    repo, c = env
    repo.append_event("inst-A", "a-stu2", "s2-0", A, item_for(A), True)
    r = call(c, method, f"/api/prototype/learners/a-stu2{suffix}", "tok-a-stu1")
    assert r.status_code == 403
    assert repo.events_for("inst-A", "a-stu1") == []


def test_student_cannot_read_another_student_even_if_unknown_id(env):
    _, c = env
    assert call(c, "GET", "/api/prototype/learners/nobody/state", "tok-a-stu1").status_code == 403


# ---- role: student on the teacher route ---------------------------------------------------
@pytest.mark.parametrize("token", ["tok-a-stu1", "tok-b-stu1"])
def test_student_cannot_call_teacher_route(env, token):
    _, c = env
    for cohort in ("cohort-A", "cohort-B"):
        assert call(c, "GET", f"/api/prototype/cohorts/{cohort}/bottlenecks", token).status_code == 403


def test_teacher_can_read_own_institute_but_not_write_attempts(env):
    _, c = env
    assert call(c, "GET", "/api/prototype/cohorts/cohort-A/bottlenecks", "tok-a-teacher").status_code == 200
    assert call(c, "GET", "/api/prototype/learners/a-stu1/state", "tok-a-teacher").status_code == 200
    assert call(c, "POST", "/api/prototype/learners/a-stu1/events", "tok-a-teacher").status_code == 403


def test_cohort_bottlenecks_use_only_same_institute_learners():
    repo, c = build()
    # mis-seeded cohort in A that names B's learner: B's evidence must not be counted
    from app.api_prototype.repository import CohortRecord
    repo.add_cohort(CohortRecord("inst-A", "cohort-mix", ("a-stu1", "b-stu1")))
    for i in range(3):
        repo.append_event("inst-B", "b-stu1", f"bb-{i}", A, item_for(A), False)
    r = c.get("/api/prototype/cohorts/cohort-mix/bottlenecks", headers=hdr("tok-a-teacher"))
    assert r.status_code == 200 and r.json()["learner_count"] == 1


# ---- health -------------------------------------------------------------------------------
def test_health_is_open_and_carries_no_tenant_data(env):
    repo, c = env
    seed_b(repo)
    r = c.get("/api/prototype/health")
    assert r.status_code == 200
    text = r.text
    for s in ("inst-", "a-stu", "b-stu", "cohort"):
        assert s not in text
