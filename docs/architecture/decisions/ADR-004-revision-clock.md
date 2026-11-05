# ADR-004: Revision clock (prototype)

**Status:** Accepted for the prototype only, 2026-11-05 (decision D8). Not for any pilot or real data.

## Context
The revision policy needs a clock. The engine accepts a day number. In the S3 prototype the client could choose the day, and before the close fix, revision schedules were rebuilt on each call and never fell due.

## Decision
1. The clock is an **attempt-count clock**, per learner. It is kept on the server in a `day_counter` that goes up by one for each accepted attempt, in the same transaction as the attempt.
2. Clients cannot send a day. An extra day field is ignored.
3. "2 days" in the revision policy therefore means 2 attempts. Calendar time is not used.

## Consequences
- Deterministic and replayable from the event log.
- Rechecks come due in practice, which they did not before.
- The clock does not measure forgetting. Any claim about retention must wait for a designed study (E8-style) and its own ADR.

## Not decided
- Whether a calendar clock replaces this for a pilot (needs its own ADR and the retention decision, D15).
