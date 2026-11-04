<!--
Purpose: Human and agent guide to the frozen DataMoat contracts directory, consumer matrix, change-request process, and contract test runner.
contract_version: 1.0.0
Implements: TECH_PLAN §7 (Repository layout), §18 (Testing strategy), §19 (Processes), and §20 (Agent plan).
-->

# DataMoat Frozen Contracts (`contract_version: 1.0.0`)

This folder (`contracts/`) is the **single, machine-checkable source of truth** for the DataMoat monorepo. Nine downstream agents build in parallel against these specifications. **Do not modify any file in `contracts/` without following the change-request protocol in §3.**

---

## 1. File Inventory & Consumer Matrix

| File / Directory | Purpose | Produced By | Consumed By (Agents) |
|---|---|---|---|
| `CONTRACT_VERSION` | Semantic version string (`1.0.0`) matched by every contract file header | P0 Contracts | All Agents (`A`–`J`) |
| `enums.yaml` | Single source of truth for all enumerations (`snake_case`, singular) | P0 Contracts | `A`, `B`, `C`, `E`, `F`, `G`, `H`, `I` |
| `schema.sql` | PostgreSQL 16 DDL for all 31 tables, CHECK constraints, indexes, and forced Row-Level Security (RLS) | P0 Contracts | `G` (Backend DB), `I` (QA Isolation), `J` (DevOps Seed) |
| `openapi.yaml` | OpenAPI 3.1 REST specification with JWT claims, RBAC role filtering, multipart limits, and RFC 7807 errors | P0 Contracts | `G` (FastAPI), `H` (Next.js TS client), `I` (Schemathesis/E2E) |
| `data_dictionary.md` | Field-by-field documentation for every SQL table, CSV template, parquet file, and the `is_minor` legal derivation | P0 Contracts | All Agents (`A`–`J`) |
| `csv_templates/*.csv` | Canonical clean CSV upload templates (`students`, `guardians`, `results_responses_wide`, `results_marks_only`, `answer_key`, `attendance`, `fees`) | P0 Contracts | `A` (Messy/Clean DataGen), `G` (Ingest), `H` (UI Downloads), `I` (Golden Tests) |
| `csv_templates/header_synonyms.yaml` | 5–10 English, Hinglish, and Devanagari header variants per canonical column + absent/present markers | P0 Contracts | `A` (Messy Injector), `G` (Fuzzy Column Mapper) |
| `datasets.yaml` | Parquet schemas (`data/clean/*.parquet`, `data/truth/*.parquet`), OMR `truth.json` schema, and seed byte-identity rule | P0 Contracts | `A` (DataGen), `B` (IRT/Mastery), `C` (Risk/Band) |
| `topics.yaml` | Bilingual (EN/HI) syllabus topic graph and prerequisite DAG (`topic_prereqs`) for JEE Main and NEET-UG (`name_hi_reviewed: false`) | P0 Contracts | `A` (DataGen), `B` (IRT/Mastery), `E` (GenAI/Study Plan), `G`, `H` |
| `topics_hi_review.csv` | Native-Hindi educator review worksheet (`id,name_en,name_hi,reviewer,status,corrected_name_hi`) for all 380 topics | P0b Contracts | Human Hindi Reviewer, `A`, `E`, `H` |
| `exam_patterns.yaml` | Year-versioned structures (`jee_main_2026`, `neet_ug_2026` with both variants `verified: false`, `internal_chapter_test`) | P0 Contracts | `A` (DataGen), `B` (IRT), `G` (Scoring) |
| `marking_schemes.yaml` | Official JEE/NEET (+4/−1/0) and custom internal marking schemes with multi-correct and dropped-question rules | P0 Contracts | `A` (DataGen), `G` (Scoring) |
| `percentile_tables.csv` | Monotone score-to-percentile/rank tables (JEE 2024 easy/tough shifts, JEE 2026 avg, NEET 2024, NEET 2026 projected) | P0 Contracts | `A` (DataGen), `C` (Percentile Band), `G`, `H` |
| `features.yaml` | Model feature definitions across Privacy Tiers `A`–`D`, `as_of` leakage rules, and `reason_template_key` links | P0 Contracts | `C` (Feature Builder & Risk), `G` (Live What-If), `I` (Leakage Tests) |
| `routing_policy.yaml` | Purpose- and age-aware DPDP s.9(3) / MoE cl. 10.2(xi) routing matrix and deterministic fallback rules | P0 Contracts | `C` (Risk Evaluation), `G` (Runtime Scoring), `I` (Privacy Tests) |
| `reason_templates.yaml` | Bilingual (EN/HI) supportive reason templates, suggested actions, and the banned shaming/ranking lexicon | P0 Contracts | `C` (SHAP -> Reasons), `E` (GenAI Verifier), `G`, `H`, `I` |
| `report_numbers.schema.json` | JSON Schema (2020-12) for the PII-free `numbers_json` payload (`{STUDENT}`, `{INSTITUTE}` placeholders) | P0 Contracts | `E` (GenAI), `G` (Report Service), `I` (Privacy Tests) |
| `report_output.schema.json` | JSON Schema (2020-12) for structured LLM output (`title`, `body`, `word_count` in 80–180) | P0 Contracts | `E` (GenAI), `G` (Report Service) |
| `omr_template.schema.json` & `omr_layouts/*.json` | Physical OMR geometry schema (mm) and layouts (`generic_mcq_100`, `neet_200`, `jee_75`) | P0 Contracts | `A` (OMR Synth), `F` (OpenCV OMR PoC), `G` (OMR Ingest) |
| `artifact_manifest.schema.json` | JSON Schema for `ml/artifacts/vX/manifest.json` | P0 Contracts | `B`, `C`, `G`, `J` |
| `metrics.schema.json` & `metrics_bars.yaml` | Schema for `metrics.json` and acceptance bars (`blocking` vs `report` gates) | P0 Contracts | `B`, `C`, `D`, `E`, `F`, `I`, `scripts/deck_numbers.py` |
| `schemas/*.schema.json` | JSON Schemas validating every YAML contract file in this directory | P0 Contracts | `contracts/tests/` |

---

## 2. How to Run the Contract Test Suite

Every commit or PR that touches data, models, backend, or frontend must keep the 14 contract tests green.

### On Windows (PowerShell)
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test_contracts.ps1
```

### Via Make (Linux / macOS / WSL / Git Bash)
```bash
make test-contracts
```

### Real-Postgres 16 Smoke & RLS Isolation Tests (`-m db`)
Tests 1b, 2b, and 3 run live PostgreSQL 16 verification (applying `schema.sql`, checking `pg_class.relrowsecurity`/`relforcerowsecurity`, verifying global read-only tables vs tenant tables, and proving cross-tenant isolation under `app_user` with `SET app.institute_id` including `item_params` and `question_topics`). They run automatically without Docker using embedded `pgserver` (PostgreSQL 16.2), or can be invoked explicitly:
```bash
pytest contracts/tests -m db
```

---

## 3. How to Propose Contract Changes

Once tagged `contracts-v1.0.0`, all files in `contracts/` are **frozen**. If a downstream agent discovers an ambiguity, contradiction, or missing field:

1. **Do NOT edit `contracts/` or `docs/legacy-case-b/TECH_PLAN.md` directly.**
2. Append a structured entry to [`docs/contract_change_requests.md`](../docs/contract_change_requests.md) specifying:
   - **Requester Agent & Date**
   - **Affected Contract File(s) & Section**
   - **Problem / Contradiction Observed**
   - **Proposed Resolution & Impact on Other Agents**
3. Continue working against the conservative interpretation until the project owner approves the request, bumps `contracts/CONTRACT_VERSION`, and re-tags.
