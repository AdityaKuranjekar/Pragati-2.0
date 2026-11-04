# Phase 6 — Commercialization, Multi-Tenancy & Scale

## 1. Purpose

Evolve the hackathon MVP into a configurable product that can be sold to institutions and integrated into online coaching platforms—without creating separate products or duplicating the intelligence engine.

**Outcome:** a validated initial market, tenant-safe SaaS foundation, partner API design and staged commercial roadmap.

### Initial commercialization hypothesis

Begin with JEE coaching institutes serving Classes 11 and 12. The validated product must personalize diagnostic-to-target plans, run realistic difficulty progression, integrate institute schedules and question banks, and give teachers actionable cohorts/interventions. Commercial pricing or redistribution must follow a separate rights review of all question content and interaction data; free-tier prototype source agreements do not automatically become production licences. ASSISTments and NTA/coaching content require permissions or restricted research use where documented terms are unclear.

## 2. Go-to-market focus

The long-term platform can support schools, colleges, coaching institutes and online providers. The first customer segment should be narrower.

Suggested sequence:
1. JEE/NEET coaching and structured test-prep institutes — closest fit to existing question, assessment and mastery foundations.
2. School coaching and tuition networks — adjacent curriculum and teacher workflows.
3. Online coaching providers — API/embedded intelligence after stable contracts.
4. Schools and colleges with varied curricula and governance — expand after configuration and onboarding mature.

This is a prioritization hypothesis, not validated market research. Interview institute owners, academic heads, teachers and online-platform operators before committing pricing or roadmap.

## 3. Product packaging

### Pragati Institutional

- Organization workspace.
- Curriculum and cohort setup.
- Teacher and student accounts.
- Assessment and question bank.
- Student adaptive journey.
- Teacher analytics and interventions.
- Parent reports where enabled.
- CSV/OMR and supported LMS imports.

### Pragati Adaptive API

For online coaching/EdTech providers:
- Learner event ingestion.
- Mastery and learner-state retrieval.
- Next-step recommendations.
- Adaptive assessment selection.
- Learning-path retrieval.
- Recommendation feedback and webhooks.
- Optional white-label/embedded student UI.

Keep both packages on the same domain model and intelligence services.

## 4. Multi-tenant architecture

Every tenant-owned record must have a tenant boundary. Decide whether the current schema uses shared tables with `tenant_id`, separate schemas or another strategy. For most early SaaS products, shared tables with rigorous tenant scoping can be practical, but it must be implemented consistently.

Requirements:
- Tenant context derived from authenticated identity, not trusted from arbitrary request body.
- Server-side tenant filters in repositories/services.
- Database constraints and row-level security where appropriate.
- Cross-tenant access tests for every sensitive resource.
- Tenant-aware background jobs and file paths.
- Tenant-aware cache keys.
- Audit logs for sensitive actions and exports.
- Separate secrets and integration credentials per organization.
- Clear data deletion/export process.

## 5. API product design

Proposed contracts (version and adapt to the existing API):

```http
POST /api/v1/learners/{learner_id}/events
GET  /api/v1/learners/{learner_id}/mastery
GET  /api/v1/learners/{learner_id}/next-step
GET  /api/v1/learners/{learner_id}/learning-path
POST /api/v1/assessments/adaptive
POST /api/v1/recommendations/{recommendation_id}/feedback
```

API requirements:
- OAuth2/client credentials or another suitable partner authentication scheme.
- Scoped API keys and rotation.
- Rate limits and quotas.
- Idempotency for event ingestion.
- Pagination and filtering.
- Versioned schemas and deprecation policy.
- Webhook signing, retries and replay protection.
- Partner sandbox and synthetic test tenant.
- Clear data ownership and processor/controller responsibilities in contracts.

## 6. Configuration rather than forks

Represent differences through configuration:
- Education type.
- Curriculum and version.
- Grade/class/semester.
- Subject and learning objectives.
- Assessment blueprint and question types.
- Mastery thresholds and recommendation policy.
- Language and accessibility.
- Institution-specific roles and workflows.

Avoid branching the codebase into separate “school engine”, “college engine” and “coaching engine”. Add domain adapters only where real workflows differ.

## 7. Reliability and operations

Before scaling:
- Centralized structured logs and correlation IDs.
- Metrics for API latency, error rates, model latency and queue/job health.
- Model registry and rollback.
- Database backup, restore and migration discipline.
- Background processing for large imports and report generation.
- Object storage for uploaded files and generated reports.
- Rate limiting and abuse protection.
- Cost monitoring for LLM calls.
- Feature flags for new recommendation policies.
- Tenant-level usage and quota reporting.

Keep the core learning decision available without an LLM. LLM calls should be bounded, observable and optional.

## 8. Commercial validation

Conduct structured discovery:
- What systems do institutes currently use?
- How are tests, marks, question banks and student records stored?
- What decisions do teachers make after an assessment?
- What is the current cost of identifying and supporting weak learners?
- Who approves and pays for software?
- What onboarding and data migration burden is acceptable?
- What evidence would justify renewal?
- What integrations are mandatory?
- What data can the institute lawfully share?

Pilot success measures should include teacher time saved, intervention adoption, learner progress and renewal intent—not only logins or dashboard views.

## 9. Pricing hypotheses

Potential models to test, not established pricing:
- Per active learner per month.
- Institute tier based on learner count and feature set.
- Annual institution license.
- API usage tier for online providers.
- Enterprise/white-label agreement.

Do not publish pricing until interviews, willingness-to-pay tests, support costs and infrastructure costs are understood.

## 10. Target structure additions

```text
backend/app/
├── core/
│   ├── tenant_context.py
│   ├── permissions.py
│   └── audit.py
├── modules/
│   ├── organizations/
│   ├── subscriptions/          # Add only when billing is in scope
│   ├── integrations/
│   └── partner_api/
└── analytics/
    ├── usage/
    └── outcomes/

integrations/
├── lms/
├── partner_sdk_examples/
├── webhooks/
└── importers/

docs/
├── commercial/
│   ├── customer_discovery.md
│   ├── packaging_hypotheses.md
│   └── pilot_success_plan.md
└── operations/
    ├── tenant_isolation.md
    ├── incident_response.md
    └── model_release_process.md
```

## 11. Exit criteria

- [ ] Initial customer segment is supported by discovery evidence.
- [ ] Tenant isolation passes automated cross-tenant tests.
- [ ] One institution onboarding workflow is repeatable.
- [ ] Partner API has authentication, scopes, idempotency and versioning.
- [ ] Usage and infrastructure costs can be measured.
- [ ] Pilot outcomes and renewal criteria are defined.
- [ ] Product packaging is based on actual customer workflows.
- [ ] Operational support and data governance responsibilities are documented.

**Gate:** do not scale sales or ingest real student records broadly until security, privacy, onboarding and support processes are ready.
