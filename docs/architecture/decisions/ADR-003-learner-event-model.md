# ADR-003: Learner attempt event model

**Status:** Proposed, implemented in engine v0 (`backend/app/intelligence/events.py`). Owner to accept.
**Date:** 2026-11-05. **Gate:** G1 (Phase 0 / PROTOTYPE_PLAN S2).

## Context
`contracts/schema.sql` stores `responses` with primary key (test, student, question) and no timestamp. It cannot be replayed in order, so knowledge tracing and the adaptive loop have no ordered history (BLOCKERS B2). Phase 2 proposes response time and hints as features, which DPDP s.9(3) makes doubtful for under-18 learners (B1).

## Decision
1. Add an append-only `attempt_events` log, one row per attempt. v0 engine fields: `event_id` (idempotency key, unique per tenant), `learner_id`, `concept_id`, `item_id`, `correct`, `seq` (server-assigned, unique per learner and concept).
2. State is a fold over events in `seq` order. Replaying the same events gives the same state.
3. A repeated `event_id` with identical content is ignored; with different content it is rejected.
4. v0 rejects every field outside the allowed set. Response time, hint counts and similar fields cannot be submitted to the engine. Adding one requires a new ADR and counsel's answer (B1).
5. `item_text_version` is not in v0 (item text is not yet in the database; B3). It is added when the item store exists.

## Alternatives considered
- **Add timestamp columns to `responses`.** Rejected: `responses` holds the latest answer per test, not the history; a log is clearer and keeps retries auditable.
- **Store raw telemetry and decide later.** Rejected: it records behaviour that s.9(3) may prohibit for minors before the legal question is answered.

## Consequences
- Migration: a new table, no change to `responses`. Reversible (drop table) until used in production.
- Tenancy: the table needs `institute_id` and an RLS policy like the other tenant tables. E13 tests apply to its routes.
- The event `seq` must be assigned by the server to avoid client-side ordering tricks.

## Not decided here
Retention period for the log; deletion on request; whether `client_time` is ever stored (default: no).
