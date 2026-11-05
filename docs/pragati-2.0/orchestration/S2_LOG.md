# S2 log: engine v0

**Date:** 2026-11-05. **Branch:** claude/serene-sagan-8za1vh. **Owner review:** pending.

## What was built
| File | Role |
|---|---|
| `backend/app/intelligence/events.py` | Event contract; rejects timing and hint fields (minor safety) |
| `backend/app/intelligence/mastery.py` | Fixed-parameter BKT fold per concept; bands; 5-answer guard for "mastered" |
| `backend/app/intelligence/graph.py` | Prerequisite DAG: cycle, unknown-node and duplicate checks; ancestors; sensitivity removal |
| `backend/app/intelligence/policy.py` | Deterministic recommendation with reason and trace; cohort bottleneck count |
| `backend/app/intelligence/chain.py` | Demo chain (taxonomy-valid JEE nodes), both edges proposed; fixtures labelled `[DEMO FIXTURE]` |
| `docs/architecture/decisions/ADR-003-learner-event-model.md` | Event model decision (proposed) |

## Gate results (run on 2026-11-05)
Command: `cd backend && python3 -m pytest app/intelligence/tests -q`

| Set | Tests | Result |
|---|---|---|
| E0 invariants, determinism, idempotency, input contract, graph validity | 19 | pass |
| E7 no prerequisite violation across 300 random graphs and histories (over 100 checked); order is topological; removing an edge changes the path; proposed edges named in the reason | 6 | pass |
| E10 cold start, one or two answers, contradictory evidence, lucky guess run, missing concept, unknown goal, goal mastered, cohort bottleneck | 9 | pass |
| Demo flow (wow sequence) | 3 | pass |
| **Total** | **36** | **36 pass** |

Mutation check: reversing the chain order makes 8 tests fail. The restored code passes all 36.

## Known limits (state them on stage)
- BKT parameters are fixed defaults, not fitted. Fitting waits for E1 on the served model.
- "Uncertainty" is 1/sqrt(n+1), a heuristic, not a calibrated interval.
- A "mastered" label needs 5 answers (guessing guard). Three lucky answers show as uncertain.
- Cohort bottleneck is a count, not PageRank. Personalised PageRank is deferred.
- The graph has two proposed edges. Until a teacher reviews them, the reason text says so.
- No database, no API and no UI yet. Those are S3 and S4.
- E3 (independent simulator) is not yet run; it is WP6 and is required before any mastery-recovery claim.

## Not done in S2 (and why)
- ADR-003 is proposed, not accepted. The owner accepts it; the event table is not migrated yet.
- No item text, so items are referred to by id only.
- Hosting (S0) was not started in this stage.

## Next
S3 (API with tenancy tests) once ADR-003 is accepted; S1 (60 reviewed items) runs in parallel.
