# Handoff prompt: make the adaptive engine complete through S2 (for a separate working session)

Paste the block below into a new session on `AdityaKuranjekar/Pragati-2.0`, branch `claude/serene-sagan-8za1vh`. Do not open a pull request. Do not push to `main`.

Scope assumption: "fully functional through S2" means the adaptive engine can run the complete demo loop and the evidence for it is generated. The API (S3) and UI (S4) are out of scope for this session.

```text
You are working in repo AdityaKuranjekar/Pragati-2.0, branch claude/serene-sagan-8za1vh. Do not open a pull request. Do not push to main.

Read first, in this order:
1. docs/pragati-2.0/README.md, section "The USP". The engine's USP is rows 3 to 7 of that table, which are not built yet.
2. docs/pragati-2.0/PROTOTYPE_PLAN.md (stages S1 and S2).
3. docs/pragati-2.0/evaluation/EVAL_PLAN.md (E0, E3, E7, E9, E10).
4. docs/pragati-2.0/orchestration/S2_LOG.md and docs/architecture/decisions/ADR-003-learner-event-model.md.
5. backend/app/intelligence/ (the existing v0 engine: events.py, mastery.py, graph.py, policy.py, chain.py) and its tests.
6. ml/dataset_pipeline/items/demo_chain_v0.json and docs/pragati-2.0/research/findings/REPORT_2026-11-05.md.

Current state: engine v0 passes 36 tests (E0, E7, E10, demo flow). It chooses the concept and explains it, but it has no item difficulty, no challenge ladder, no revision, no time or goal. The 60 demo items are drafts (review_status pending); only approved items may be served to learners.

Build, in this order:

A. Item selection (USP row 3). Add backend/app/intelligence/selection.py. Given the learner's state for the target concept and the item bank (items with topic_id, difficulty_target, and item_id):
   - Map difficulty_target easy/medium/hard to a numeric difficulty scale, documented in the module.
   - Guided entry: a learner with p_known < 0.5 starts one band easier than the target. Never offer only easy items when the target is medium or hard (test this).
   - Step up toward the target after evidence, and do not repeat an item already answered by that learner.
   - Return the chosen item_id with a reason and the trace.
   - Use only status approved items unless an explicit demo flag is set; the flag must appear in the output.

B. Challenge rule (USP row 4). Raise difficulty only when the last k answers on the concept are correct, with k = 3, and never on a single correct answer. Lower it after two wrong answers. Test that one lucky correct answer does not raise difficulty, and that contradictory runs hold the level.

C. Revision (USP row 5). Add backend/app/intelligence/revision.py: a concept whose estimate was mastered is scheduled for a recheck after an interval that grows with each successful recheck, and shortens after an error. Time is an explicit input (a day number, not wall-clock time) so replay stays deterministic. Keep the interval rule as a documented, configurable policy, not a claim about forgetting curves.

D. Time, goal and pace (USP row 6). Add a budget input (items available before the goal date) to the policy. When the budget is short, the policy recommends the fewest items that reach the goal estimate, and says so in the reason. Do not use response time for under-18 learners.

E. Simulator and comparison harness (USP row 7, E9). Add ml/evaluation/sim/ with a learner simulator that is independent of the estimator (no import from backend/app/intelligence). It must generate learners with latent concept mastery, respecting prerequisites, with guessing 0.25 for 4-option items and slips 0.10. Compare, at equal item budgets:
   - a fixed curriculum-order path,
   - the adaptive path (A to D),
   - ablations: no prerequisite graph; no challenge rule; no revision.
   Report items-to-mastery, final mastery count, and prerequisite violations, with bootstrap CIs over simulated learners, and label every number [SIM].
   Pre-register the comparison in ml/evaluation/PREREGISTRATION.md before running it: write the metric, the budget, the number of learners, and the seed.

F. Tests. Keep all 36 existing tests passing. Add tests for A to D, and for E: determinism with a fixed seed, and that the simulator never imports the estimator.

G. Report. Write docs/pragati-2.0/orchestration/S2_FULL_LOG.md with, for each USP row, status (built, tested, evaluated), the exact command, the test count, and every number labelled [SIM] with its task. Report honestly any comparison in which the adaptive path does not beat the fixed path. Negative results are required reporting, not something to hide.

Constraints:
- Pure Python in backend/app/intelligence; no database; no LLM in any decision.
- No response time or hint fields for any learner (ADR-003 rejects them).
- Do not change the BKT parameters based on simulator results. Fitting waits for E1 on the served model.
- Do not mark any item approved. Review is by Aditya and Ashray (ml/dataset_pipeline/reviews.py).
- Do not claim the adaptive path improves learning. The only allowed claims are simulated and labelled.
- No model names in commits, code, docs or comments.
- Commit footer:
  Co-Authored-By: Claude <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01KJWtns5nxaGLDkb97p7YLj
- Push with: git push -u origin claude/serene-sagan-8za1vh (retry network failures up to 4 times with 2, 4, 8, 16 seconds of backoff).
- Use the scratchpad directory for temporary files, not /tmp.

Done when: rows 3 to 6 are built and tested; the simulated comparison (row 7) is pre-registered, run, and reported with its misses; all tests pass; the log is written and pushed. Then stop and list what is still not built.
```
