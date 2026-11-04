# Phase 3 — Adaptive Learning Experience (Student, Teacher & Admin)

## 1. Purpose

Turn the intelligence engine into a coherent product. The interface must make the next action obvious, explain the reason and close the learning feedback loop.

**Outcome:** a usable student learning journey and a teacher view that demonstrates measurable instructional value.

### Required prototype journeys

Students begin with a diagnostic, then see a subject/chapter mastery profile, next learning activity, reason for recommendation and anticipated improvement. Practice sessions follow the ladder **foundation → guided practice → current-level practice → slightly harder challenge → revision**, with explanations after errors and spaced rechecks. Teachers see class and individual concept mastery, learning pace, engagement, hint reliance, risk of delay, revision completion and recommended interventions. The three-step flow is: student profile, personalized goal-aware learning path, then continuously updated progress dashboards.

## 2. Student experience

### 2.1 Home / learning journey

Show:
- Current course and curriculum.
- Today's recommended next step.
- Why it is recommended.
- Estimated time only when grounded in content metadata.
- Progress by learning objective.
- Upcoming revision and pending assessments.
- Continue-learning action.

Avoid overwhelming students with every chart and metric. The primary action should be the next useful learning activity.

### 2.2 Concept detail

Show:
- What the concept means and its learning objective.
- Prerequisites and readiness.
- Mastery estimate with a plain-language evidence label (e.g. “early estimate”).
- Recommended resource(s).
- Worked example and practice.
- “I need help” or “This recommendation doesn't fit” feedback.

### 2.3 Practice and assessment

- Render question types supported by the item bank.
- Capture answer, correctness, attempt context and timestamp.
- Explain answers after submission according to assessment rules.
- Prevent accidental duplicate submissions.
- Provide accessible keyboard and mobile interactions.
- Update the learner's next step only after the backend confirms the event.

### 2.4 Learning path

Display ordered activities with statuses:
- Recommended.
- Ready.
- In progress.
- Completed.
- Needs review.

Allow a learner to understand why a prerequisite appears before the target concept. Do not let students arbitrarily bypass a teacher-mandated assessment or prerequisite if policy disallows it.

## 3. Teacher dashboard

Core panels:

1. **Cohort overview:** learners, recent assessment coverage and broad mastery distribution.
2. **Concept heatmap:** concepts by learner or cohort, with evidence counts and uncertainty cues.
3. **Needs-support queue:** learners with a defined reason for review, not a black-box risk label.
4. **Prerequisite bottlenecks:** concepts blocking multiple downstream objectives.
5. **Intervention suggestions:** recommended group revision, targeted practice or individual follow-up.
6. **Progress over time:** comparable assessment windows and cohort trends.
7. **Review and override:** teacher can accept, modify or dismiss a suggestion with a reason.

Do not rank or stigmatize students publicly. Restrict individual records to authorized staff.

## 4. Institute admin experience

For MVP:
- Manage course/curriculum assignment.
- Manage cohorts, classes and teacher access.
- Import learners and assessment data.
- Configure assessment rules and content visibility.
- View high-level usage and learning outcomes.
- Review data access and export permissions.

Commercial billing and subscription management can wait until after the hackathon unless already implemented.

## 5. Parent reports

Retain existing Hindi/English reporting capability if verified. Reports should:
- Explain strengths and areas to support in plain language.
- Give concrete next steps.
- Avoid unsupported predictions or diagnostic labels.
- Show the reporting period and evidence source.
- Respect consent, guardian authorization and student privacy settings.

## 6. GenAI: useful, bounded features

GenAI can add product polish, but should not own the learning state or make unverified claims.

Good use cases:
- Explain a concept using approved curriculum resources.
- Generate a hint, then a worked explanation after an attempt.
- Rewrite teacher-approved feedback in simpler language or Hindi/English.
- Summarize cohort-level patterns without exposing unnecessary personal data.
- Draft question variants for teacher review.

Required safeguards:
- Ground explanations in approved material and include source references internally.
- Validate generated questions and answers before publication.
- Enforce grade/curriculum boundaries.
- Do not expose private student data to an external provider without appropriate authorization.
- Record provider/model version and failures.
- Provide deterministic fallback content.

## 7. UI design direction

Product should feel like a modern learning product, not a dense analytics admin panel.

- Student: calm, focused, encouraging, one primary next action.
- Teacher: information-dense but scannable, filters and drill-down.
- Admin: operational tables and configuration.
- Use consistent tokens, spacing, accessible contrast and responsive layouts.
- Use charts only where they help a decision.
- Distinguish measured data, model estimates and synthetic demo data.

## 8. Frontend target structure

Adapt to existing Next.js route groups; do not create separate applications without a deployment reason.

```text
frontend/
├── app/
│   ├── (auth)/
│   ├── (student)/
│   │   ├── dashboard/
│   │   ├── learning-path/
│   │   ├── concepts/[conceptId]/
│   │   └── practice/[activityId]/
│   ├── (teacher)/
│   │   ├── dashboard/
│   │   ├── cohorts/[cohortId]/
│   │   ├── learners/[learnerId]/
│   │   └── interventions/
│   ├── (admin)/
│   │   ├── curriculum/
│   │   ├── users/
│   │   └── imports/
│   └── layout.tsx
├── components/
│   ├── ui/
│   ├── charts/
│   ├── learning/
│   └── dashboards/
├── features/
│   ├── learner-state/
│   ├── adaptive-path/
│   ├── practice/
│   ├── cohort-analytics/
│   └── interventions/
├── lib/
│   ├── api-client.ts
│   ├── auth.ts
│   └── permissions.ts
└── tests/
```

## 9. End-to-end user journeys

### Journey A — learner

1. Sign in and open assigned course.
2. Complete diagnostic assessment.
3. View mastery profile with evidence caveat.
4. Receive a recommended activity with a reason.
5. Study an explanation or resource.
6. Attempt practice.
7. Receive feedback.
8. See updated path and progress.

### Journey B — teacher

1. Open assigned cohort.
2. Identify a concept bottleneck.
3. Inspect the evidence behind the pattern.
4. Review a group or learner intervention suggestion.
5. Accept or override it.
6. Review progress after a subsequent assessment.

## 10. API integration and UI states

For every page, design:
- Loading state.
- Empty state.
- Error/retry state.
- Permission-denied state.
- Stale-data state.
- Successful state.

Frontend must not calculate authoritative mastery or recommendation policy itself. It renders backend decisions and may perform harmless presentation calculations.

## 11. Testing

- Component tests for learning path and attempt flows.
- API contract tests.
- End-to-end tests for both journeys.
- Role and tenant permission tests.
- Mobile/responsive and accessibility checks.
- Duplicate attempt and network retry tests.
- LLM timeout and unavailable-provider tests.
- Verify synthetic demo labels remain visible in demo mode.

## 12. Exit criteria

- [ ] Student completes the full adaptive loop without manual database edits.
- [ ] Different learner states produce visibly different paths.
- [ ] Teacher can inspect evidence and review an intervention.
- [ ] Recommendation rationale is visible and understandable.
- [ ] Role-based access is enforced server-side.
- [ ] Loading, empty and failure states are handled.
- [ ] The product is usable on laptop and mobile-sized screens.

**Gate:** do not polish isolated dashboard screenshots before the end-to-end student journey works.
