# S3 close log: gaps closed so the API meets E13 and E0

**Date:** 2026-11-05. **Branch:** claude/serene-sagan-8za1vh (already contains origin/main; no merge to main; no pull request). Untouched: `frontend/`, `backend/app/routers/`, the 1.0 console, the engine (`backend/app/intelligence/`, 97 tests still pass).

## ADR-003 status
**Still proposed. Awaiting owner acceptance.** Per the stop condition, the SQL migration and the PostgreSQL repository are written and were run **only against a throw-away database** that the tests create and delete. The migration has not been applied anywhere else and must not be until the owner accepts the ADR.

## What changed, by item
| # | Item | Built |
|---|---|---|
| 1 | Teacher scope by cohort | Cohort membership is the learner's `cohort_id`. `PUT /api/prototype/cohorts/{cohort_id}/teachers/{teacher_user_id}` (owner of the same institute only; idempotent, 201 then 200). A teacher reads a cohort or a learner only if assigned to the cohort. Check order: role, institute (404), cohort (403). Owners have no learner or bottleneck access. Teachers still cannot write attempts. |
| 2 | RLS | `migrations/001_prototype_tables.sql` (six tables, `institute_id`, ENABLE + FORCE RLS, `app_user` policies with `WITH CHECK`, `attempt_events` append-only for `app_user`). `pg_repository.py`: every call is one transaction that runs `SET LOCAL ROLE app_user` and `set_config('app.institute_id', ..., true)`. |
| 3 | Server-side day | `day` query input removed (an extra `?day=` is ignored and tested). Per-learner `day_counter`, +1 per accepted attempt, in the same transaction. Revision schedules are rebuilt from history (`service.py`) on that clock, so rechecks now work (before, schedules were rebuilt at the current day and never fell due). |
| 4 | Served-item check | A learner's own `next-step` call records the returned item (concept, kind) as served. An attempt is accepted only for an item served to that learner for that concept and not yet answered; otherwise 422 with "not served" or "already been answered". Identical repeat of an accepted event stays idempotent (checked first). A teacher viewing next-step does not serve items. |
| 5 | Hardening | Sweep tests: every non-public route depends on `current_principal` (structural) and returns 401 for no, bad or malformed token (behavioural); the public set is exactly health, OpenAPI and docs; a new route that is not covered fails a test; every route called with every foreign principal returns only 403/404 and none of the other side's ids. |

## Counts (268 tests, all pass)
| Set | Tests | In-memory | PostgreSQL |
|---|---|---|---|
| E13 tenancy (all routes, forged institute in body/query/header, cross-institute, student vs student, student on teacher route, cohort scope, owner-only assign, sweeps) | 134 | 67 | 67 |
| E13 RLS (raw SQL as `app_user`: context B sees and changes no A rows in all six tables; no context sees nothing; malformed context fails closed; A-row inserts rejected; `attempt_events` append-only; repository returns nothing across institutes; non-uuid institute matches nothing; `SET LOCAL` does not leak) | 23 | n/a | 23 |
| E0 for the API (idempotent duplicate, conflicting duplicate, 12 rejected fields incl. `day`, served-item check, day counter, client cannot choose the day, revision on the server clock, replay) | 83 | 41 (+1 pure) | 41 |
| Contract (reason and trace equal the engine's on 5 histories, approval gating, demo flag, no item text, no ASSISTments/JEEBench/pending-source text, no timing or hint keys incl. OpenAPI) | 28 | 14 | 14 |

The Postgres run **passed** (23 + 122 repository-backed tests) against a throw-away PostgreSQL 16 cluster started by the tests on a unix socket (no TCP), with `contracts/schema.sql` and the migration applied to it, deleted afterwards.

Mutation checks on the RLS tests: replacing the policy condition with `true` fails 12 of 23; removing `SET LOCAL ROLE app_user` from the repository fails 1 (the id-scoped queries still hold; only the "skip the lookup" test depends on RLS). Both files restored; 268 pass.

## Exact commands
```bash
pip install -r backend/app/api_prototype/requirements.txt
cd backend && python3 -m pytest app/api_prototype/tests -q          # 268 passed with PostgreSQL available
cd backend && python3 -m pytest app/intelligence/tests -q           # 97 passed
```
Where PostgreSQL 16 binaries are at `/usr/lib/postgresql/*/bin` the Postgres tests start their own cluster; otherwise set `PG_BIN` to the directory with `initdb` and `pg_ctl`. As root the server runs as the OS user `postgres`, and `PG_TEST_TMP` must name a parent directory that user can create folders in (this session used `/var/lib/postgresql/pragati_test`). With no PostgreSQL the Postgres tests are **skipped, not passed**: the same command gives `123 passed, 145 skipped`.

## Decisions to review
- **The day is an attempt-count clock**, not a calendar day: "2 days" in the revision policy now means 2 attempts. The engine's own docs say persisting a day number needs an ADR; that ADR is not written. `proto_learners.day_counter` is a prototype column.
- Attempt `seq` is `n` for the n-th event and is made on day `n`; mastery is dated `seq + 1`, a recheck is dated at its `seq`.
- `budget_remaining` is still a client query input (default 50). It affects only the caller's own recommendation, not tenancy.
- The owner role reads no learner data; the owner can assign only teachers that exist in the same institute.
- `next-step` is a GET with a write effect (serving). A teacher's call never writes.
- Stub auth is unchanged and marked NOT FOR PRODUCTION.

## Still open
- ADR-003 acceptance; until then the migration stays off every shared database.
- Real auth (Supabase or Firebase), token expiry, rate limits. `proto_users` and the text ids are stand-ins, not yet joined to `users` and `students` in `contracts/schema.sql`.
- Routes to create learners, cohorts and goals (seeded in code and tests only); revoking a teacher assignment; removing a served item that is never answered (served rows have no expiry).
- The ADR for the day counter; retention and deletion of `attempt_events` and `proto_served_items`.
- A connection pool for the PostgreSQL repository (it opens a connection per call), and a concurrency test of two simultaneous attempts.
- Mounting the app in `backend/app/main.py`, the host decision, UI (S4), load test (E14).
