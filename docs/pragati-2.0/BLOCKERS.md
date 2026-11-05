# Blockers and risk register (Pragati 2.0)

**Status:** 2026-11-04. Scored before the hackathon build. Likelihood (L) and impact (I) are 1 to 5. Score = L × I. "Decision owner" is who must decide, not who must fix. Items with **B** IDs block a phase; items with **R** IDs are risks to manage.

Each blocker says what would unblock it and which session should work on it (see `orchestration/ORCHESTRATOR.md`).

## Blockers (must be resolved before the named phase or claim)

| ID | Blocker | Blocks | L | I | Score | Unblock by | Decision owner |
|---|---|---|---:|---:|---:|---|---|
| B1 | **Minors and behavioural monitoring (update 2026-11-05).** Secondary sources say the Fourth Schedule exempts educational institutions for educational activities, which suggests in-institute use can proceed. Open: whether a coaching centre qualifies; whether the vendor is a processor; cross-institute model training is probably outside the exemption. Phase 2 uses response time and hint reliance. DPDP s.9(3) bars tracking or behavioural monitoring of children; the repo already gates ML risk for minors (`contracts/routing_policy.yaml`). Coaching students in Classes 11 and 12 are often under 18. Whether the learning analytics fall under s.9(3), and whether any Fourth Schedule exemption covers a coaching centre, is not established. | Phase 2 features, Phase 3 teacher views, E8 pilot, E12 | 4 | 5 | **20** | Legal opinion (R1). Until then: no response-time or hint features for under-18s; correctness-only evidence; no pilot with minors | Institute owner with counsel |
| B2 | **No learner-level event log.** `responses` has primary key (test, student, question) and no timestamp, so there is no ordered history to replay or to train knowledge tracing. There is also no learner-facing attempt endpoint in `openapi.yaml`. | Phase 1 gate, Phase 2 core loop, E0, E1 | 5 | 5 | **25** | ADR-003: append-only `attempt_events` table with learner, item, concept, timestamp, idempotency key, model version. Design in Phase 0 | Tech lead (this repo) |
| B3 | **No question text in the database.** `questions` stores `text_hash`, subject, type and options count only. A learner cannot be shown a question from the product. | Phase 3 practice flow, the whole demo | 5 | 5 | **25** | Content plan: 100 to 300 reviewed items with rights records (R2); `item_content` table or files under `data/question_bank/` (not git); provenance for each row | Academic lead + content reviewer |
| B4 | **Dataset licences partly known (update 2026-11-05).** OpenStax is CC BY-NC-SA (checked), EdNet is CC BY-NC (checked): both excluded from the commercial path. ASSISTments terms not found. JEEBench, OULAD licence files and NCERT/NTA reuse still to check. | E1, E5, any item import, any public demo | 4 | 4 | **16** | R2 findings; keep ASSISTments server-side and do not redistribute; use only original or verified items on the public demo | Tech lead with counsel |
| B5 | **Exam scope and schema.** `topics.exam` allows only `jee_main` and `neet_ug`. JEE Advanced, state CETs and olympiads have no value, and `class_level` allows only class_11, class_12, dropper. Adding them is a migration. | Scope decision, Phase 1 curriculum | 5 | 3 | **15** | R3 decides scope. Recommend: JEE Main and Advanced first (one concept graph, two patterns); one CET after that. Migration as a reversible step (Phase 0 gate) | Product owner |
| B6 | **Demo curriculum choice conflicts with the taxonomy.** Phase 0 proposes Class 10 Quadratic Equations, but `contracts/topics.yaml` has no Class 10 nodes and `class_level` does not allow them. | Phase 1 deliverable | 4 | 3 | **12** | Recommended: the in-graph JEE chain: `jee.math.complex_numbers.algebra_complex_argand` → `jee.math.quadratic_equations.roots_nature` (complex roots when the discriminant is negative) → `jee.math.quadratic_equations.equation_formation`. These edges do not exist yet and need teacher review (B14). Confirm with an academic reviewer | Academic lead |
| B14 | **Sparse prerequisite graph.** `contracts/topics.yaml` has 380 nodes and 33 prerequisite edges. No edge links quadratic equations to complex numbers, so the demo's prerequisite story is not supported by the graph yet. | Phase 2 diagnosis, E4, E7, demo | 5 | 4 | **20** | WP7: add proposed edges with a source and `review_status`; teacher review; E7 sensitivity test to show how paths change when an edge is removed | Academic lead |
| B7 | **Collaborative filtering and graph algorithms are missing from the plan.** The problem statement names them as suggested technologies. Phase 2 has a prerequisite graph but no CF module and no graph algorithm beyond traversal. | Judging against the brief | 4 | 4 | **16** | Add to Phase 2: (a) item-item or matrix-factorisation CF on ASSISTments as a benchmark and a cold-start fallback; (b) personalised PageRank or a similar graph score over the prerequisite DAG to find bottleneck concepts for teachers. See `PHASE_2` update | Tech lead |
| B8 | **Hackathon rules unknown (urgent).** Research report dates (Round 1 on 10 Nov 2026) and rubric weights could not be found online; no official source in the repo. | Phase 5 and every priority call | 4 | 5 | **20** | R4 | Team lead |
| B9 | **Existing headline numbers mismatch the served model and their gates.** 0.7633 comes from a hierarchical Rasch model in `ml/public_validation`; the product runtime uses 1PL (`backend/app/ml/irt.py`). OULAD 0.706 is below the 0.794 anchor the repo cites, but its gate in `contracts/metrics_bars.yaml` is 0.70 (`gate: report`), so it is recorded as passed. The ASSISTments gate is 0.65 against a DKT anchor of 0.7541. | Any slide or claim | 5 | 4 | **20** | Re-run with the 2.0 protocol (E1, E2). Label each figure (task and origin). Remove "passed" where the anchor was missed | Tech lead |
| B10 | **Mastery claims are circular on synthetic data.** The 1.0 generator and estimator share assumptions, so recovery r = 0.53 to 0.79 says little about real learners. | Pitch claims, E3 | 4 | 4 | **16** | E3 simulator written independently; report the design-factor curve; no real-learner claim until E8 | Tech lead |
| B11 | **Teacher panel and expert labels not secured.** E4, E5 and E6 need 2 to 3 subject experts and teachers. | Evaluation claims | 4 | 4 | **16** | Name the reviewers before running; pre-register; pay or credit reviewers as the institute allows | Product owner |
| B12 | **Hindi review not done.** `name_hi_reviewed` is false for all topics (`contracts/topics.yaml` `name_hi_reviewed: false`). Hindi parent reports are unreviewed. | Bilingual demo, Phase 3 | 3 | 3 | **9** | R9; native-speaker review before showing Hindi in public | Academic lead |
| B13 | **No verified topic data.** `verified: true` appears zero times in `contracts/topics.yaml`; weightage is null everywhere. | Curriculum claims, teacher trust | 5 | 3 | **15** | Verify demo chapters against NCERT / official syllabus; set `verified` per topic with a source | Academic lead |

## Risks (managed, not blocking)

| ID | Risk | L | I | Score | Mitigation |
|---|---|---:|---:|---:|---|
| R-1 | Free-tier cold start on Render breaks the live demo | 4 | 4 | 16 | Visible loading state; prewarm before judging; recorded backup; a cached read-only mode (R7 to confirm limits) |
| R-2 | Free-tier database pauses or hits limits during judging | 3 | 5 | 15 | Seed script; second database target; export snapshot; check limits (R7) |
| R-3 | Question quality: a wrong answer key or solution reaches a learner | 3 | 5 | 15 | Two-person review; answer verification; wrong-key detector (E10); learner feedback flag |
| R-4 | Over-claiming: a judge finds a number that does not match its task | 4 | 5 | 20 | Origin and task tags (EVAL_PLAN §0); "what this does not show" slide |
| R-5 | Easy-question lock-in: policy keeps giving easy items | 3 | 4 | 12 | Guided ladder with a target difficulty; E6 check; test that difficulty rises after 3 correct answers when evidence supports it |
| R-6 | Labels stigmatise learners ("weak student") | 3 | 4 | 12 | Store concept states, not person labels; copy review; no public ranking |
| R-7 | LLM provider unavailable or outputs unverified text | 3 | 3 | 9 | Template fallback (already in `backend/app/genai`); core engine does not need an LLM |
| R-8 | Tenant leak in a new endpoint | 3 | 5 | 15 | E13 on every new route; RLS; forged-ID tests; release blocked on failure |
| R-9 | Scope creep to CET, Olympiad, parent app, LMS, billing before the loop works | 5 | 4 | 20 | Freeze scope (Phase 0 §4.3); Olympiad and LMS deferred; CET after the loop passes E0 to E7 |
| R-10 | Over-fitting the demo to two chosen learners | 3 | 4 | 12 | Use 20 simulated learners plus E4 cases; show a held-out learner in the demo |
| R-11 | Single-person bus factor and laptop-only data (`data/` is git-ignored and local) | 4 | 3 | 12 | Keep `data/` reproducible from scripts; checksum manifest; backup to an encrypted drive |
| R-12 | Judges compare against published KT numbers on different pipelines | 3 | 3 | 9 | Only compare on the same protocol; show published numbers as context |
| R-13 | Teacher trust: override rate read as model failure | 3 | 3 | 9 | Log overrides with reason; report override rate with the caveat in EVAL_PLAN E6 |
| R-14 | Mixed-origin data in one table (synthetic, public, pilot) | 3 | 4 | 12 | `origin` column on every results table; CI check that rejects untagged metrics |
| R-15 | Windows (local) and Linux (cloud) differences break scripts | 3 | 2 | 6 | Scripts are Python with pinned requirements; test on both before a session hand-off |

## Assumptions that must be checked (not blockers yet)

| ID | Assumption in plan | Check |
|---|---|---|
| A-1 | Coaching centres can process learner data under school-style rules | R1 |
| A-2 | A hosted demo is acceptable to the hackathon | R4 |
| A-3 | NTA and NCERT content can be used as reference with attribution | R2 |
| A-4 | 100 to 300 reviewed items are enough for the demo | Content plan; E5 |
| A-5 | Effect size d = 0.3 and ICC = 0.05 for a pilot | R8 |
| A-6 | Teachers will rate 100 profiles in the time available | B11 |

## Decisions the user must make (short list)

1. **Minors:** accept correctness-only evidence for under-18s until counsel answers B1? (Recommended: yes.)
2. **Exam scope for the hackathon:** JEE Main and JEE Advanced only, with CET as a stated next step? (Recommended: yes.)
3. **Demo curriculum:** the in-graph JEE chain (complex-number algebra → quadratic roots → formation of equations), with its new edges teacher-reviewed (B6, B14)? (Recommended: yes.)
4. **Hosted demo:** keep the Phase 0 free-tier stack, or use a local demo with a recorded backup only? (Depends on R4 and R7.)
