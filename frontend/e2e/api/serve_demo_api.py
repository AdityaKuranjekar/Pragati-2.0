"""Local demo API for the prototype UI tests. Seeds [DEMO FIXTURE] data with the stub auth tokens
(NOT FOR PRODUCTION). Uses the in-memory repository and a bank whose items are all 'pending', so
the API serves no item. Usage: python3 serve_demo_api.py PORT"""
import os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "backend")))
import uvicorn
from app.api_prototype.app import create_app
from app.api_prototype.auth import Principal, StubTokenAuth
from app.api_prototype.repository import CohortRecord, InMemoryRepository, LearnerRecord
from app.intelligence.chain import A, F, R, LEARNER_A, LEARNER_B
from app.intelligence.selection import BankItem

INST = "aaaaaaaa-0000-4000-8000-00000000000a"
COHORT = "cohort-demo"
TOKENS = {
    "demo-teacher": Principal("u-teacher", INST, "teacher"),
    "demo-learner-a": Principal("u-a", INST, "student", "demo-a"),
    "demo-learner-b": Principal("u-b", INST, "student", "demo-b"),
}
repo = InMemoryRepository()
for t, p in TOKENS.items():
    repo.add_user(p.institute_id, p.user_id, p.role)
repo.add_cohort(CohortRecord(INST, COHORT))


def seed(lid, script):
    """Seed history through the same path as a real attempt: serve, then append."""
    repo.add_learner(LearnerRecord(INST, lid, COHORT, F))
    for i, (cid, ok) in enumerate(script):
        item = f"seed-{lid}-{i}"
        repo.mark_served(INST, lid, cid, item, "practice")
        repo.append_event(INST, lid, f"seed-{lid}-{i}", cid, item, ok)


seed("demo-a", LEARNER_A)       # [DEMO FIXTURE]
seed("demo-b", LEARNER_B)       # [DEMO FIXTURE]
rng = random.Random(20261105)   # [SIM] six simulated learners, fixed seed
for k in range(1, 7):
    pa, pr = rng.uniform(0.3, 0.95), rng.uniform(0.1, 0.8)
    script = [(A, rng.random() < pa) for _ in range(rng.randint(0, 7))] + \
             [(R, rng.random() < pr) for _ in range(rng.randint(0, 6))]
    seed(f"sim-{k:02d}", script)
repo.assign_teacher(INST, COHORT, "u-teacher")
bank = [BankItem(f"{c.split('.')[-1]}-{lvl}-{i}", c, lvl, "pending")
        for c in (A, R, F) for lvl in ("easy", "medium") for i in range(4)]
app = create_app(repo, StubTokenAuth(TOKENS), bank)
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8765, log_level="warning")
