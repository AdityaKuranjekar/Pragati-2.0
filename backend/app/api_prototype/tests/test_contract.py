"""Contract: the API serves the engine's reason and trace unchanged; gating; no source text."""
import json
import re
from pathlib import Path

import pytest
from fastapi.encoders import jsonable_encoder

from app.intelligence.chain import NAMES, demo_graph
from app.intelligence.planner import AdaptiveSession, PlannerConfig
from app.intelligence.selection import bank_from_records

from .conftest import A, F, INST_A, R, attempt, hdr, item_for, make_bank, post_script, serve

T = hdr("tok-a-stu1")
URL = "/api/prototype/learners/a-stu1"
REPO_ROOT = Path(__file__).resolve().parents[4]
FORBIDDEN = re.compile(r"assistments|jeebench|pending[ _-]source", re.I)


def engine_step(events, day=0, budget=50, demo=False, bank=None, kinds=None):
    """The engine called directly, the way the API is specified to call it."""
    from app.api_prototype.service import schedules_for
    s = AdaptiveSession("a-stu1", demo_graph(), F, bank or make_bank(), PlannerConfig(allow_unapproved_demo=demo), NAMES)
    s.events = events
    s.schedules = schedules_for(events, kinds or {})
    return s.next_step(day, budget)


@pytest.mark.parametrize("script,budget", [
    ([], 50),
    ([(A, True)] * 5 + [(R, False)] * 3, 50),
    ([(A, False)] * 3, 50),
    ([(A, True)] * 5 + [(R, False)] * 3, 3),      # short budget
    ([(A, True)] * 5 + [(R, True)] * 5 + [(F, True)] * 5, 50),
])
def test_next_step_reproduces_engine_reason_and_trace(env_factory, script, budget):
    repo, c = env_factory()
    post_script(repo, c, "a-stu1", "tok-a-stu1", script)
    body = c.get(f"{URL}/next-step", params={"budget_remaining": budget}, headers=T).json()
    day = repo.day_of(INST_A, "a-stu1")
    assert body["engine_inputs"]["day"] == day == len(script)
    events = repo.events_for(INST_A, "a-stu1")
    kinds = {s.item_id: s.kind for s in repo.served_for(INST_A, "a-stu1")}
    step = engine_step(events, day, budget, kinds=kinds)
    assert body["reason"] == step.reason and body["reason"]
    assert body["trace"] == jsonable_encoder(step.trace)
    assert body["kind"] == step.kind and body["item_id"] == step.item_id
    if step.recommendation is not None:
        assert body["recommendation"]["reason"] == step.recommendation.reason
        assert body["recommendation"]["trace"] == jsonable_encoder(step.recommendation.trace)
    if step.selection is not None:
        assert body["selection"]["reason"] == step.selection.reason
        assert body["selection"]["trace"] == jsonable_encoder(step.selection.trace)


def test_different_evidence_gives_different_next_steps(env):
    repo, c = env
    # day 6 < the recheck of A (due day 7), so the gap on R is the next step
    post_script(repo, c, "a-stu1", "tok-a-stu1", [(A, True)] * 5 + [(R, False)])
    a = c.get(f"{URL}/next-step", headers=T).json()
    post_script(repo, c, "a-stu2", "tok-a-stu2", [(A, False)] * 3, prefix="x")
    b = c.get("/api/prototype/learners/a-stu2/next-step", headers=hdr("tok-a-stu2")).json()
    assert a["concept_id"] == R and b["concept_id"] == A


def test_only_approved_items_served_without_demo_flag_and_flag_is_in_response(env_factory):
    _, c = env_factory(bank=make_bank({A: "pending", R: "pending", F: "pending"}), demo=False)
    body = c.get(f"{URL}/next-step", headers=T).json()
    assert body["demo_unapproved_allowed"] is False
    assert body["item_id"] is None and body["kind"] == "none"
    assert "pending" not in json.dumps(body)


def test_demo_flag_serves_unapproved_and_says_so(env_factory):
    _, c = env_factory(bank=make_bank({A: "pending", R: "pending", F: "pending"}), demo=True)
    body = c.get(f"{URL}/next-step", headers=T).json()
    assert body["demo_unapproved_allowed"] is True
    assert body["item_id"] and body["selection"]["item_status"] == "pending"
    assert "DEMO ONLY" in body["reason"]


def test_demo_flag_cannot_be_set_by_the_client(env_factory):
    _, c = env_factory(bank=make_bank({A: "pending", R: "pending", F: "pending"}), demo=False)
    for kw in ({"params": {"demo": "1", "allow_unapproved_demo": "true"}},
               {"headers": {**T, "X-Demo": "1", "X-Allow-Unapproved-Demo": "true"}}):
        kw.setdefault("headers", T)
        body = c.get(f"{URL}/next-step", **kw).json()
        assert body["demo_unapproved_allowed"] is False and body["item_id"] is None


def test_real_demo_bank_serves_nothing_by_default_and_never_serves_item_text(env_factory):
    data = json.loads((REPO_ROOT / "ml/dataset_pipeline/items/demo_chain_v0.json").read_text())
    bank = bank_from_records(data["items"])
    texts = [i["text"] for i in data["items"]]
    for demo in (False, True):
        _, c = env_factory(bank=bank, demo=demo)
        body = c.get(f"{URL}/next-step", headers=T)
        assert (body.json()["item_id"] is None) == (not demo)
        assert not any(t in body.text for t in texts)


@pytest.mark.parametrize("demo", [False, True])
def test_no_response_contains_source_names_or_timing_or_hint_fields(env_factory, demo):
    data = json.loads((REPO_ROOT / "ml/dataset_pipeline/items/demo_chain_v0.json").read_text())
    repo, c = env_factory(bank=bank_from_records(data["items"]) + make_bank(), demo=demo)
    texts = []
    texts.append(c.get("/api/prototype/health").text)
    post_script(repo, c, "a-stu1", "tok-a-stu1", [(A, True)] * 5 + [(R, False)] * 3)
    serve(repo, "a-stu1", A, item_for(A, "hard", 3))
    for path, tok in ((f"{URL}/state", T), (f"{URL}/next-step", T),
                      ("/api/prototype/cohorts/cohort-A/bottlenecks", hdr("tok-a-teacher"))):
        texts.append(c.get(path, headers=tok).text)
    texts.append(c.post(f"{URL}/events", json=attempt("zz", A, item_for(A, "hard", 3)), headers=T).text)
    texts.append(c.post(f"{URL}/events", json=attempt("zq", A), headers=T).text)   # 422 not served
    texts.append(c.post(f"{URL}/events", json={**attempt("zy", A), "hints_used": 1}, headers=T).text)  # 422 body
    texts.append(c.get("/openapi.json").text)
    for t in texts:
        assert not FORBIDDEN.search(t), FORBIDDEN.search(t).group(0)
        assert not re.search(r'"(response_time|hint)[a-z_]*"\s*:', t)


def test_bottleneck_output_is_the_engine_output(env):
    from app.intelligence.mastery import learner_state
    from app.intelligence.policy import cohort_bottlenecks
    repo, c = env
    post_script(repo, c, "a-stu1", "tok-a-stu1", [(A, False)] * 3)
    post_script(repo, c, "a-stu2", "tok-a-stu2", [(R, False)], prefix="q")
    g = demo_graph()
    expect = cohort_bottlenecks(g, {l: learner_state(repo.events_for(INST_A, l), g.nodes) for l in ("a-stu1", "a-stu2")})
    body = c.get("/api/prototype/cohorts/cohort-A/bottlenecks", headers=hdr("tok-a-teacher")).json()
    assert body["bottlenecks"] == jsonable_encoder(expect) and body["learner_count"] == 2
    assert all(set(r["edge_review"]) == {"proposed"} for r in body["bottlenecks"])
    assert "a-stu" not in json.dumps(body)   # aggregates only: no learner ids


def test_a_recheck_of_a_mastered_concept_comes_before_the_gap_once_it_is_due(env):
    """Same learner as above, two answers later (day 8 >= due day 7): the server's clock makes the recheck due."""
    repo, c = env
    post_script(repo, c, "a-stu1", "tok-a-stu1", [(A, True)] * 5 + [(R, False)] * 3)
    body = c.get(f"{URL}/next-step", headers=T).json()
    assert body["kind"] == "recheck" and body["concept_id"] == A and body["engine_inputs"]["day"] == 8
    assert body["reason"].startswith("Recheck of")
