# S3 log: prototype API over the engine

**Date:** 2026-11-05. **Branch:** claude/serene-sagan-8za1vh (synced to origin/main first). **Owner review:** pending. No pull request opened.

## ADR-003 status
**Still proposed. Awaiting owner acceptance.** The routes implement it as written (idempotency on `event_id`, server-assigned `seq`, every field outside the allowed set rejected). Because it is not accepted, there is **no PostgreSQL repository and no migration**.

## Routes (`backend/app/api_prototype/app.py`)
| Route | Who | Notes |
|---|---|---|
| `POST /api/prototype/learners/{learner_id}/events` | the learner (student) only | Body: `event_id`, `concept_id`, `item_id`, `correct`. 201 new, 200 identical repeat (`duplicate: true`), 409 conflicting repeat, 422 any other field or an unknown concept/item. `learner_id` comes from the path and `seq` from the server, so a client sending either gets 422. Teachers get 403. |
| `GET .../learners/{learner_id}/state` | the learner; teachers of the same institute | Per concept: band, `p_known`, uncertainty, `evidence_count`. Uncertainty is the engine heuristic 1/sqrt(n+1) and the response says so. |
| `GET .../learners/{learner_id}/next-step` | same as state | Planner output: kind, concept, item, reason, trace, recommendation, selection. `demo_unapproved_allowed` is in the response. Query inputs `day` and `budget_remaining` (defaults 0 and 50) are the engine's explicit inputs; they are not tenant inputs. |
| `GET .../cohorts/{cohort_id}/bottlenecks` | teacher only | `cohort_bottlenecks` output, with the learner count; no learner ids. Counts only learners that exist in the same institute. |
| `GET .../health` | anyone | No tenant data. |

Tenancy: institute comes only from the principal. Learner and cohort are looked up under `(principal.institute_id, id)`; another institute's record reads as 404. A student asking for any learner but their own gets 403 before any lookup (so other students' existence is not revealed). Teachers may read any learner or cohort in their own institute (decision of this stage: not restricted to assigned cohorts). The demo flag is server configuration (`create_app(demo_allow_unapproved=...)` or `PRAGATI_DEMO_UNAPPROVED=1`), never a request parameter.

## Tests (83, all pass)
| Set | Count | File |
|---|---|---|
| E13 tenancy (every route; forged `institute_id` in body, query and header; cross-institute both ways; student vs student; student on teacher route; missing/bad token; mixed-cohort leak; health) | 40 | `test_e13_tenancy.py` |
| E0 for the API (idempotent duplicate, conflicting duplicate, per-tenant `event_id`, 11 rejected fields, malformed values, replay determinism, cold start) | 30 | `test_e0_api.py` |
| Contract (reason and trace identical to the engine on 5 histories, approved-only gating, demo flag in response and not client-settable, no item text, no ASSISTments/JEEBench/pending-source text or timing/hint keys in any response incl. OpenAPI, bottleneck equals engine output) | 13 | `test_contract.py` |

Mutation check: removing the student own-learner check fails 16 tests; removing the teacher-only check fails 2. The restored code passes all 83. Engine tests (`app/intelligence/tests`) still pass (97).

## Commands
```bash
pip install -r backend/app/api_prototype/requirements.txt
cd backend && python3 -m pytest app/api_prototype/tests -q      # 83 passed
cd backend && python3 -m pytest app/intelligence/tests -q       # 97 passed
```
Pinned in `backend/app/api_prototype/requirements.txt`: fastapi 0.162.0, starlette 1.7.0, pydantic 2.13.5, httpx 0.28.1, pytest 9.2.0 (the versions tested). The repo's `requirements-dev.txt` pins pytest 7.4.2; I did not change it.

## Stub versus real
| Stub | Real |
|---|---|
| Auth (`auth.py`): bearer token to (user, institute, role, learner) from an in-memory map. **Not for production.** | The engine calls, the event contract, idempotency, tenancy checks in the route layer, the response shapes |
| Storage: in-memory repository only; learners and cohorts are seeded in code (no route creates them) | The repository interface (`repository.py`), written so a SQL version sets `app.institute_id` per transaction |
| Bank, graph: caller supplies them; tests use fixtures. The 60-item demo bank is all `pending`, so with the flag off nothing is served | |

## Host decision
**Still open** (Render or Vercel functions for the API; Neon for the database). Nothing here depends on it.

## Not built
- PostgreSQL repository, `attempt_events` migration, RLS test with a different `app.institute_id` (needs ADR-003 accepted). The RLS half of E13 is therefore not covered.
- Real auth (Supabase or Firebase), token expiry, rate limits.
- Routes to create learners, cohorts or goals; teacher-to-cohort assignment; edge review route.
- Persistence of revision schedules: ADR-003 has no day on events, so each next-step call rebuilds schedules from the `day` query input.
- No server check that a submitted item was the one served; any known item of the concept is accepted.
- Mounting in `backend/app/main.py`: not done on purpose (1.0 code untouched). `create_app(...)` returns a separate app.
- No UI, no hosting, no load test (E14).
