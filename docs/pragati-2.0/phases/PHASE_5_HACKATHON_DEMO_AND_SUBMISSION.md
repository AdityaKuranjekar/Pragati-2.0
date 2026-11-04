# Phase 5 — Hackathon Demo, Storytelling & Submission

> **Update 2026-11-04 (orchestrator pass).**
> - **Demo chain (D1):** in-graph JEE chain: `jee.math.complex_numbers.algebra_complex_argand` → `jee.math.quadratic_equations.roots_nature` (complex roots when the discriminant is negative) → `jee.math.quadratic_equations.equation_formation`. These edges do not exist yet and need teacher review (B14).
> - **Rubric unknown (B8, R4):** the presentation structure below is a default. Rewrite it against the official criteria before building slides.
> - **Pitch and claims:** `PITCH.md` (defining user, claim table, judge questions). A claim without a re-run (E1, E3) or a pilot (E8) is not used on a slide.
> - **Hosting (R7):** free-tier limits must be checked before the cold-start plan is final.
> - **Honesty slide:** slide 7 must show which evaluation sets missed their bars.
> - **Submission checklist:** see `BLOCKERS.md` (B8) and `orchestration/ORCHESTRATOR.md` §3 (G5).

## 1. Purpose

Package the working product and its evidence into a memorable demonstration. The goal is not to show the largest feature count; it is to make judges understand the problem, see the adaptive intelligence work and trust the results.

**Outcome:** a reliable live demo, backup recording, concise technical narrative, architecture visuals and submission-ready documentation.

### JEE prototype hosting plan

The free prototype uses a Next.js frontend on Vercel, FastAPI on Render, PostgreSQL on Neon or Supabase, and Firebase/Supabase authentication. Render's cold start requires a visible loading state or a backup recording. The demo should use 100–300 verified questions and 20 synthetic/anonymized learners, not the unprocessed 61 MB ASSISTments CSV. Demonstrate initial diagnostic, concept mastery profile, adaptive progression, explanation and teacher intervention. ASSISTments and any restricted source remain server-side and are never surfaced as student-facing JEE content.

## 2. The central story

**Problem:** conventional learning dashboards often tell a teacher who scored poorly, but do not reliably tell each learner what to do next.

**Insight:** learners in the same class do not have the same prerequisite gaps or mastery state.

**Solution:** Pragati combines learner intelligence with an adaptive learning loop. It estimates concept mastery, diagnoses prerequisite gaps, recommends a next activity with a reason, then updates the path from new evidence.

**Differentiator:** explainable, prerequisite-aware personalization—not merely an AI chatbot or a dashboard.

## 3. Recommended demo scenario

Class 10 Mathematics — Quadratic Equations.

Use two synthetic demo learners:
- Learner A: stronger factorisation, moderate quadratic-equation understanding, weaker discriminant.
- Learner B: weak factorisation and quadratic-equation foundations.

Do not hard-code different final paths as screenshots. Run the actual recommendation policy over the learners' event histories so the judges can see the system derive different recommendations.

### Demo sequence

1. Open teacher cohort dashboard and show the two learners.
2. Open Learner A and Learner B side by side or in separate tabs.
3. Run diagnostic attempts for each learner.
4. Show the learner state and evidence count.
5. Show prerequisite-aware diagnosis.
6. Show distinct next-step recommendations and reasons.
7. Complete a learning activity and practice question for one learner.
8. Refresh/re-query the learner state.
9. Show how the next recommendation changes because new evidence was recorded.
10. Return to teacher view and show cohort-level bottleneck and intervention.
11. Show the evaluation comparison and limitations.

### The “wow” moment

The most important moment is not the heatmap. It is this sequence:

**different evidence → different learner models → different next steps → new evidence → changed recommendation.**

## 4. Demo reliability

- Seed a clean demo tenant and synthetic learner accounts.
- Include a one-command seed/reset script.
- Verify the complete flow from a fresh database snapshot.
- Cache non-essential external content, but do not fake core adaptive decisions.
- Have a local/offline fallback if the network or LLM provider fails.
- Keep a short recorded demo ready.
- Avoid relying on external APIs for critical steps.
- Ensure all synthetic data is visibly labelled.
- Prepare a fallback path if login, import or OMR fails.

## 5. Presentation structure

A concise deck can follow:

1. Problem and who experiences it.
2. Why existing dashboards or generic content recommendations are insufficient.
3. Pragati 2.0 product concept and target users.
4. Live adaptive workflow.
5. Architecture and technical depth.
6. Dataset, model and evaluation methodology.
7. Results, limitations and what has not yet been validated.
8. Deployment/commercial path and next steps.

Use one clear architecture diagram and one clear adaptive-loop diagram. Avoid dense slides filled with framework logos.

## 6. Technical documentation checklist

```text
docs/
├── README.md
├── product/
│   ├── problem_statement.md
│   ├── product_overview.md
│   └── user_journeys.md
├── architecture/
│   ├── system_architecture.md
│   ├── adaptive_workflow.md
│   └── database_erd.md
├── data/
│   ├── dataset_provenance.md
│   └── curriculum_and_question_quality.md
├── models/
│   ├── model_cards/
│   ├── evaluation_report.md
│   └── limitations.md
├── api/
│   └── openapi_or_endpoint_reference.md
├── privacy/
│   └── privacy_and_security.md
└── demo/
    ├── demo_script.md
    ├── seed_instructions.md
    └── backup_plan.md
```

README should include:
- Problem and solution.
- Feature summary.
- Architecture.
- Tech stack.
- Setup instructions.
- Environment variables (names only, never values).
- Database migration and seed steps.
- Tests.
- Demo instructions.
- Dataset and license notes.
- Known limitations.

## 7. Demo script template

**Opening:** “Two students can receive the same score and still need different support. Pragati models the concepts behind their answers, not just their total marks.”

**Show:** diagnostic attempt and learner state.

**Explain:** “The system detects that this learner needs a prerequisite before the chapter's advanced concept.”

**Demonstrate:** next-step recommendation, rationale and practice.

**Update:** submit a new attempt and show the updated recommendation.

**Teacher value:** show the cohort bottleneck and reviewable intervention.

**Evidence:** show benchmark results and clearly label what is public-dataset evaluation, simulation or pilot evidence.

**Close:** “Pragati turns assessment data into an explainable next learning action, then measures what changes.”

## 8. Judge-facing technical depth

Be ready to explain:
- Why BKT/IRT/rule baselines were chosen.
- How concept tags and prerequisite edges are validated.
- How the system avoids leakage in sequential data.
- How recommendation ranking works.
- How uncertainty and cold-start cases are handled.
- What GenAI does and what it deliberately does not do.
- How tenant isolation and minor privacy are enforced.
- What the metrics prove and do not prove.

## 9. Exit criteria

- [ ] Fresh setup instructions work.
- [ ] Seed/reset script works.
- [ ] Two learner journeys complete live.
- [ ] Recommendations are generated by actual policy code.
- [ ] A new attempt changes learner state and can change the next step.
- [ ] Teacher view is connected to the same underlying records.
- [ ] Evaluation results are reproducible and honestly labelled.
- [ ] Backup recording and offline fallback are ready.
- [ ] README, architecture, data and model documentation are complete.
- [ ] Submission assets are checked against event rules and deadlines.
