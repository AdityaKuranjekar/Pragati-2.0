# Pragati 2.0: pitch and defining user

**Status:** draft, 2026-11-04. No figure in this document has been verified yet; each one that needs a source is marked `[verify: R#]`. Claims are limited to what the evidence supports (see §4).

---

## 1. One line

**Pragati tells a JEE teacher what each student should learn next, why, and whether it worked.**

## 2. Defining user

**The academic head of a JEE coaching centre** who runs a few hundred Class 11 and 12 students across batches (illustrative size; confirm in a pilot interview), has a test every week, and decides each week which concept to re-teach to which group.

| | |
|---|---|
| Job to be done | Turn each test into a short, correct list: which concept is blocking which student, what to re-teach this week, and who needs one-to-one help |
| What they have today | Marks, rank lists, an answer key, and a hunch from the teacher who marks the test |
| What goes wrong | A low total is treated as a single weakness. The real cause is often a prerequisite (for example factorisation behind quadratic equations), so the re-teach lands on the wrong topic |
| What they will not accept | A black-box "risk score" for a child; a public ranking; a tool that replaces the teacher |
| What makes them buy | Less time spent working out who needs what; a reason they can check in one line; evidence that the intervention changed something |

**Why this user, not the student.** The student is a minor for most of the cohort. A product that starts with teacher-owned decisions and correctness-only evidence for under-18s is the route that does not depend on the open legal question in `BLOCKERS.md` B1. The student still gets a path, shown through the teacher's assignment.

**Secondary user (later):** the learner, once B1 is resolved and the practice loop has passed E8.

## 3. The problem, in the teacher's words

> "I know who scored badly. I do not know what to teach on Monday, or which five children will actually improve if I spend the next twenty minutes with them."

Evidence to collect before the pitch (R6): how many JEE and CET candidates there are per cycle `[verify: R6]`; how many students a mid-sized coaching centre teaches per cohort `[verify: pilot interview]`; how many hours a teacher spends on test analysis per week `[verify: pilot interview]`.

## 4. The product, and what each part does and does not claim

| Part | What it does | What it does **not** claim |
|---|---|---|
| Concept profile | Estimates mastery per concept with an uncertainty band and an evidence count | A true mastery score; "73.42%" precision |
| Prerequisite diagnosis | Names the root-cause concept given the graph | That the graph is right for every board or teacher (teacher review of edges is part of the product) |
| Next step | One recommended activity, with a reason in plain language | That it raises marks (until E8) |
| Path | Ordered activities that change when new evidence arrives | That it beats every human plan |
| Teacher panel | Concept bottlenecks across a cohort; reviewable suggestions; override with a reason | That it removes the need for judgement |
| Explanation (optional GenAI) | Phrases a verified reason in English or Hindi | That an LLM decides anything. Core logic runs without it |

## 5. Why this can win (and where it is weak)

**Strengths**
- The problem brief names collaborative filtering and graph algorithms. The product uses a prerequisite graph and a graph-based bottleneck score (B7), so the method choice is visible.
- Every recommendation carries a reason traced to the policy's own inputs (E11), so a judge can check it.
- The evaluation is pre-registered and reports misses. A judge who opens the evaluation report finds an honest report, not a sales page.
- The product works without an LLM and keeps minors' data to correctness-only evidence until counsel says otherwise.

**Weak points, stated before judges do**
- No learning-outcome evidence yet. The only real-learner test is a pilot (E8) that may not run in time.
- The public benchmark is K-12 maths skill-builder data, not JEE content. Domain transfer is not shown.
- The mastery estimator is validated on simulation and on a 2009 US dataset, not on JEE students.
- Question content for the demo is small (100 to 300 items) and must be rights-cleared.
- The 0.7633 AUC figure is from a hierarchical model; the served product model is 1PL. The pitch uses the served model's number after re-run (E1), or none.

## 6. Moat (honest version)

The algorithms are not the moat; most are published. What is harder to copy:
1. A **reviewed, rights-cleared item bank** with concept tags and a measured tagging error rate (E5).
2. A **prerequisite graph** for each exam, reviewed by teachers, with edge-level evidence.
3. A **teacher-override log** that shows where the model and experts disagree; this improves the graph and the bank (only with consent and tenant isolation, E13).
4. **Evaluation discipline**: a pre-registered pipeline that a new institute can re-run.

## 7. Exam path

| Stage | Exam | Why in this order | Gate |
|---|---|---|---|
| 1 | JEE Main and JEE Advanced | One concept graph, two patterns; the largest cohort of Class 11 and 12 students `[verify: R3, R6]` | G1 (ADR-004) |
| 2 | One state CET (PCM) | Syllabus and item rights are per state; one state first `[verify: R3]` | Stage 1 passes E4 to E6 |
| 3 | Olympiad | Rare cohorts, unclear rights for past problems; a separate track | R10 recommendation |

## 8. Claims we can make now, and what would change them

| Claim | Status | Evidence label | What would change it |
|---|---|---|---|
| "The system reads the prerequisite graph and names a root cause" | To be built | `[code]` | E0, E7 pass |
| "Next-response prediction on K-12 skill-builder data is 0.76 AUC" | **Do not use** until re-run on the served model (E1) | `[PUB]`, hierarchical model | E1 re-run and pre-registered |
| "Retention prediction on OULAD is 0.71 AUC, below the published 0.79 anchor" | Usable as a miss, not as a strength | `[PUB]`, retention | Only relevant to the retention experiment, not to JEE |
| "Mastery recovery r = 0.53 to 0.79" | **Do not use** as a product claim | `[SIM]`, 1.0 data | E3 with an independent simulator |
| "Adaptive paths improve learning" | **Do not claim** | `[PILOT]` none | E8 |
| "Teachers rate adaptive recommendations higher than fixed paths" | **Do not claim** until run | `[EXP]` none | E6 |
| "No minor's response times are used" | Design commitment | Code and ADR-003 | Counsel answer (B1) |

## 9. Judge questions (prepared answers)

| Question | Answer | Evidence to show |
|---|---|---|
| Why not just a dashboard? | The dashboard shows who scored low. The engine names the prerequisite that explains it and recommends the next step with a reason. | Learner A and B side by side (fixture, labelled) |
| Is this just an LLM wrapper? | No. The learning decisions are deterministic code with tests. An LLM, if used, only phrases a verified reason; the template works without it. | E0, E11 |
| Did it improve learning? | Not yet. We have not run a pilot. The evaluation shows what we can and cannot claim. | EVAL_PLAN §1, RESULTS (honest) |
| Why these datasets? | ASSISTments is the only public dataset with skill-level interaction data; we use it to test the model, not as JEE content. OULAD is a different task and is kept separate. | Dataset table with licence status |
| How do you protect children? | Under-18s: correctness-only evidence until counsel approves more; no ranking; teacher-owned decisions; tenant isolation tested on every route. | B1, E13 |
| How do you know the graph is right? | Edges are teacher-reviewed; the engine flags an edge as unverified until reviewed; a sensitivity test shows how often paths change. | E7 sensitivity |
| What if the question bank is wrong? | Every item has a rights record and an answer check; a wrong-key detector flags suspicious items; learners can flag an item. | E5, E10 |
| Why JEE and not NEET? | JEE Main and Advanced share one concept graph and the demo needs one exam first. NEET is supported by the same schema (`topics.exam` includes `neet_ug`) but is not the pilot. | ADR-004 |
| What happens with no data? | The system shows a diagnostic, not a path, and says "not enough evidence yet". | E10 |
| Can this scale commercially? | Phase 6 is after the hackathon. Pricing is a hypothesis and not claimed. | Phase 6 §9 |

## 10. Slide outline (Phase 5 §5, filled in)

1. **Problem.** The teacher's Monday question (§3). One number: `[verify: R6]`.
2. **Insight.** Same total, different missing prerequisite (fixture, labelled `[DEMO FIXTURE]`).
3. **Product.** Three steps: profile → path → progress. One screenshot per step.
4. **Live demo.** Learner A and B; a new attempt changes B's next step. Backup recording ready.
5. **Architecture.** One diagram: events → state → diagnosis → ranking → reason; teacher panel on the same records.
6. **Method and data.** Table: task, origin, split, baseline, result, limit. Every row tagged.
7. **Results and misses.** E1, E2, E3, E4, E6 as run. Honest: say which missed.
8. **Limits and next steps.** B1 (minors), E8 pilot, exam expansion, item-bank rights.

## 11. Demo script (reuse Phase 5 §3, with these labels)

- Every simulated learner and every demo number is labelled `[DEMO FIXTURE]` on screen.
- The live step is the new attempt → changed next step. If the live system is slow, play the backup.
- Show the teacher panel only after the learner step is shown, so the record is the same one.

## 12. Things to decide before the pitch

1. Confirm the defining user (teacher, not student).
2. Confirm D1 to D3 in `orchestration/ORCHESTRATOR.md` §5.
3. Get the DataNova rubric (R4) and rewrite §5 against it.
4. Decide whether to show E8-style results at all if no pilot runs; if not, say so on slide 7.
