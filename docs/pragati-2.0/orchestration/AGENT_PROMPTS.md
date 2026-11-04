# Agent prompts (ready to paste into a new session)

Each prompt is self-contained. Paste it as the first message of a session on the repository `AdityaKuranjekar/Pragati-2.0`, branch `claude/serene-sagan-8za1vh`. Shared rules are at the end and apply to all of them.

---

## P1. Phase 0 audit (WP1), cloud

**Goal.** Produce the Phase 0 audit outputs that gate every schema and model change: repository map, feature inventory, database audit, baseline test report.

**Inputs.** Repo root. `docs/pragati-2.0/phases/PHASE_0_CODEBASE_AUDIT_AND_PRODUCT_FOUNDATION.md` §3 and §5. `CLAUDE.md` §2 (reading order). `contracts/schema.sql` (31 tables), `contracts/openapi.yaml`, `backend/app/main.py`, `backend/app/routers/*.py`, `frontend/app/**`, `ml/`, `datagen/`.

**Outputs (create these files):**
- `docs/audit/repository_map.md`: every top-level folder, entry point, package manager, and how to run it.
- `docs/audit/feature_inventory.md`: the table from Phase 0 §3.2, with one row per capability and a verdict of verified / partial / absent. A capability is "verified" only with code, a test and a working path. Add rows for: attempt capture, question text, learner event log, prerequisite graph use in diagnosis, collaborative filtering (absent), graph algorithms beyond traversal (absent).
- `docs/audit/database_audit.md`: one row per table with purpose, owner module, PII class, tenant key, retention need, indexes. Add the data-flow map: OMR or CSV → `responses` → `mastery` → analytics. Flag any table with no timestamp that would need one for knowledge tracing.
- `docs/audit/model_audit.md`: one row per model or rule (Rasch, risk LightGBM tiers, percentile point model, BKT in `ml/public_validation`, GenAI verifier) with the Phase 0 §3.4 fields. Mark the origin of each figure.
- `docs/audit/baseline_test_report.md`: run `python -m pytest contracts/tests -q`, `python -m pytest datagen/tests -q`, `cd backend && python -m pytest tests -q`, `python -m pytest backend/app/genai/tests -q` and `cd frontend && npm ci && npm run lint && npm run typecheck` if the environment allows. Record exact pass, fail and skip counts, the command, and the commit hash. Do not fix failures in this session.

**Acceptance criteria.**
- Every table in `schema.sql` appears in `database_audit.md` (count must be 31).
- Every route in the backend appears in `repository_map.md` or `feature_inventory.md`.
- Every number in the audit has a source path or a command.
- The report states what could not be run and why.

**Tests.** None to write. Verify the table count with a script and paste the output into the report.

**DO NOT.**
- Change any file outside `docs/audit/` (no schema, model, route or test edits).
- Read `data/` (not in git and not in this session).
- Accept Phase 0 §2's "reported" features as verified without a file.
- Copy numbers from `docs/legacy-case-b/` as 2.0 results.

---

## P2. Research R1 and R2, legal and licences (WP2), cloud

**Goal.** Establish, from primary sources, the legal position on learning analytics for minors under the DPDP Act, and the licence for every dataset and content source.

**Inputs.** `docs/pragati-2.0/research/RESEARCH_PROMPTS.md` sections R1 and R2 (copy them verbatim as your brief). `contracts/routing_policy.yaml`, `docs/legacy-case-b/CITATIONS.md`, `contracts/datasets.yaml`.

**Outputs.**
- `docs/pragati-2.0/research/findings/R1_dpdp_minors.md`: quoted s.9(1) and s.9(3); quoted Fourth Schedule clause; a yes/no/unclear answer for (a) per-question correctness logs, (b) response-time and hint-use features, (c) "needs support" lists, for a coaching institute and for an educational institution; commencement date; the questions only counsel can answer. Label it "not legal advice".
- `docs/pragati-2.0/research/findings/R2_licences.md`: one table per source (ASSISTments 2009, OULAD, JEEBench, EdNet, PSLC DataShop, OpenStax, NCERT, NTA papers, state CET papers) with licence name and version, URL, access date, permitted purposes, redistribution, attribution, and a "safe for public demo?" flag.

**Acceptance criteria.**
- Every claim cites a URL and an access date, and carries `verified` or `secondary-only` or `not found`.
- Each source that is `not found` is listed under "still unverified" with the exact page that would settle it.
- No statement of law is written as fact unless the Gazette or official rules text is quoted.

**Tests.** None.

**DO NOT.**
- Download any dataset or paper. Read licence pages only.
- Copy long passages of copyrighted text. Paraphrase and link.
- Edit `contracts/datasets.yaml` or any code. Findings only.
- Name or guess the pronouns of any person in the documents.

---

## P3. Re-run public validation with the 2.0 protocol (WP5), on computer

**Goal.** Re-run the next-response (ASSISTments) and retention (OULAD) evaluations with a pre-registration written before the run, so the numbers in the repo can be confirmed or corrected.

**Where.** The Windows laptop, repository root. `data/public/` holds the downloads. Do not copy these files anywhere else.

**Inputs.** `docs/pragati-2.0/evaluation/EVAL_PLAN.md` sections E1, E2, §0 and §6. `ml/public_validation/assistments.py`, `ml/public_validation/oulad.py`, `ml/public_validation/evaluate.py`, `ml/public_validation/tests/`. `ml/public_validation/artifacts/v1.0.0/`.

**Steps.**
1. Create `ml/evaluation/PREREGISTRATION.md` using the template in EVAL_PLAN §6 for E1 and E2. Commit it before running anything. Pass bars must be the ones in EVAL_PLAN, not new ones.
2. Record SHA-256 of each input file and the pyKT split seed (1024).
3. Run the existing pipeline with the same seeds: `python -m pytest ml/public_validation/tests -m "not data" -v` first, then the data tests with `-m data` on the laptop.
4. Produce `ml/evaluation/results/E1_assistments.json` and `E2_oulad.json`. Every metric has: value, bootstrap 95% CI over students, baseline value, origin `[PUB]`, task name, seed, and commit hash.
5. Report, in `docs/pragati-2.0/evaluation/RESULTS.md` under a "Re-run 2026-11" heading: the same number as the repo (confirm or differ), and whether the proposed bar was met.

**Acceptance criteria.**
- The pre-registration commit is earlier in history than the results commit.
- E1 reports the hierarchical Rasch (0.7633 claim) AND the 1PL runtime model on the same protocol. If they differ, say so.
- E2 reports the miss against the 0.794 anchor without rounding it away.
- Any number that does not reproduce is reported as not reproduced, with the diff.

**Tests.** Existing `ml/public_validation/tests` must pass or the failure must be reported as is.

**DO NOT.**
- Change the split, the seed, the preprocessing or the bar after seeing results.
- Commit anything under `data/` or any raw dataset file. `data/` is git-ignored; keep it that way.
- Quote published DKT or SAKT numbers as if they used this pipeline.
- Claim a result for JEE questions from ASSISTments.

---

## P4. Engine design: event model and exam scope (WP4), cloud

**Goal.** Write two architecture decision records (no migration yet): the learner event model (fixes B2) and the exam-scope extension (fixes B5). They gate the adaptive engine.

**Inputs.** `contracts/schema.sql` (tables `responses`, `questions`, `topics`, `topic_prereqs`, `tests`, `test_questions`), `contracts/topics.yaml`, `contracts/exam_patterns.yaml`, `docs/pragati-2.0/phases/PHASE_0_*.md` §6 and §7, `docs/pragati-2.0/phases/PHASE_2_*.md` §3 and §10, and `docs/audit/database_audit.md` (from P1, if present; if not, read the schema directly and say so).

**Outputs.**
- `docs/architecture/decisions/ADR-003-learner-event-model.md`: proposed append-only `attempt_events` table. Fields: id (UUID), institute_id, learner_id, item_id (reference to `questions`), concept_id (reference to `topics`), question_text_version, selected_option or numeric response, is_correct, received_at (server time), client_time (optional, **not used as a feature for under-18s**), idempotency_key (unique per tenant), source (diagnostic / practice / test), model_version_at_write. State the retention rule and the minors rule (R1 pending). Include the replay rule: state = fold over events ordered by `received_at, id`.
- `docs/architecture/decisions/ADR-004-exam-scope.md`: the `topics.exam` CHECK and `class_level` CHECK need new values (`jee_advanced`, `state_cet`) or a separate `exam_id` table. Recommend one; give a reversible migration outline; list the rows affected; do not write the SQL.
- Both ADRs list alternatives considered and their reasons for rejection.

**Acceptance criteria.**
- Each ADR has: context, decision, alternatives, consequences, reversibility, and the gate it satisfies (G1).
- No file under `contracts/schema.sql`, `backend/` or `frontend/` is changed.
- The ADR says plainly that `responses` cannot be replayed in order.

**Tests.** None. Check that the ADRs link to the schema line numbers they rely on.

**DO NOT.**
- Add a migration, a model or a route. Phase 0 gate applies.
- Add a message broker, vector database or microservice (CLAUDE.md §3).
- Use a student's response time as a feature in the design for under-18s.

---

## P5. Simulator and fixtures for E0, E3 and E7 (WP6), cloud

**Goal.** Write a learner simulator that is independent of the estimator, and the E0 invariant tests and E7 prerequisite tests that use it. No real data.

**Inputs.** `docs/pragati-2.0/evaluation/EVAL_PLAN.md` sections E0, E3, E7 and E10. `contracts/topics.yaml` (prerequisite edges via `parent_id` and `topic_prereqs`). `ml/public_validation/assistments.py` for the BKT form (for reference only; do not import the estimator into the simulator).

**Outputs.**
- `ml/evaluation/sim/simulator.py`: generates learners with latent concept mastery θ, respecting prerequisites (a dependent concept's θ is capped by its prerequisites' θ plus a margin), item difficulty spread, 4-option guessing at 0.25, slip 0.05, and learning per practice opportunity. Seeded; the same seed gives byte-identical output (write a test).
- `ml/evaluation/sim/tests/test_simulator.py`: determinism, prerequisite cap, guessing rate within tolerance on 10,000 draws.
- `ml/evaluation/sim/tests/test_invariants.py`: E0 checks on a small synthetic graph (acyclic, every edge points to an existing concept, replay gives the same state).
- Design-factor generator for E3 (items per concept: 3, 6, 10, 20; concepts: 10, 30; prerequisite depth: 1, 3).

**Acceptance criteria.**
- `pytest ml/evaluation/sim/tests -q` passes.
- The simulator's module imports nothing from `backend/app/ml/` or `ml/public_validation/` (grep check, paste the output).
- The README at `ml/evaluation/sim/README.md` says the simulator is `[SIM]` and what it cannot show.

**Tests.** As listed above. Report exact counts.

**DO NOT.**
- Read `data/` or any real student record.
- Use the 1.0 generator in `datagen/` (its parameters are shared with the estimator, which makes recovery circular).
- Put demo-learner values (85/35 etc.) into the simulator as outputs to match.

---

## Shared rules (apply to every prompt above)

1. Work on branch `claude/serene-sagan-8za1vh`. Create it locally from the remote if missing. Do not push to any other branch.
2. Commit with clear messages. Push with `git push -u origin claude/serene-sagan-8za1vh`. Retry network failures up to 4 times with backoff (2, 4, 8, 16 seconds).
3. Do not open a pull request unless the owner asks for one.
4. Commit message footer, exactly:
   ```text
   Co-Authored-By: Claude <noreply@anthropic.com>
   Claude-Session: https://claude.ai/code/session_01KJWtns5nxaGLDkb97p7YLj
   ```
   Do not put any model name in commit messages, PR text, code comments or files.
5. Never commit `.env`, secrets, student data, raw licensed datasets, or anything under `data/`.
6. Label every number with its origin (`[SIM]`, `[PUB]`, `[EXP]`, `[PILOT]`, `[code]`) and its task.
7. Report honestly: failing tests, missed bars and unverified facts go in the final message, not hidden.
8. At the end, list what you did not do and why, and what the next session needs.
