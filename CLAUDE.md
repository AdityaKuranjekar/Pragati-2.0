# CLAUDE.md: Pragati 2.0 hand-off

Last updated: 2026-11-05 (folder cleanup for Pragati 2.0). Owner: AlphaQ team.

## 1. What we are building
Pragati 2.0 is an adaptive learning-path recommendation platform for JEE aspirants (Classes 11 and 12; Physics, Chemistry, Mathematics). For each learner it:
1. estimates concept-level mastery, uncertainty, pace and goal progress from a diagnostic and from practice;
2. diagnoses gaps, including prerequisite gaps rather than the lowest percentage;
3. recommends the next module or activity and states the reason;
4. updates the learner state from new evidence and changes the next step only when justified;
5. shows the teacher cohort gaps, with review and override.

The hackathon submission is for DataNova Global Data-thon 2026 (problem: "Adaptive Learning Path Recommendation"). It needs code, documentation, an evaluation and a presentation. Problem statement: suggested technologies Python, collaborative filtering and graph algorithms; data is anonymised interaction logs, assessment scores and content metadata.

## 2. Read in this order
1. `README.md`: folder map and commands.
2. `docs/pragati-2.0/README.md`: product north star, phase index, target structure, dataset table, principles.
3. `docs/pragati-2.0/phases/PHASE_0_*.md`: the audit comes first. Nothing may change a schema or a model before Phase 0 is done.
4. The phase in progress, then the remaining phases as needed.
5. `docs/CLEANUP_LOG.md`: what was removed in the cleanup, and where to recover it.
6. `docs/legacy-case-b/`: Pragati 1.0 decisions and evidence. Reference only; do not treat its numbers as 2.0 results.

## 3. Hard constraints
- Free and local first. Hosting per Phase 0: Vercel (frontend), Render (FastAPI), Neon or Supabase (PostgreSQL), Supabase or Firebase (auth).
- Stack: Next.js (TypeScript, Tailwind, ECharts) · FastAPI (Python 3.11+) · PostgreSQL 16 · NumPy/SciPy, LightGBM where justified · scikit-learn baselines · OpenCV only for the OMR module. No Streamlit or Gradio.
- Modular monolith. Do not add a broker, a vector database or microservices without a measured need.
- Public datasets: ASSISTments (behavioural and knowledge-tracing source; not the source of JEE questions), OULAD (a separate retention experiment; not a school-maths dataset). Check licence and terms before every download, and never merge incompatible datasets without a harmonisation plan.
- JEE content only from NCERT or official material, rights-reviewed JEEBench items, official NTA papers, or original reviewed questions. Never assume a coaching-institute or public PDF can be redistributed.
- Privacy by design: minimise data, protect minors (DPDP Act s.9(3): no behavioural tracking of children, even with consent), no invasive engagement tracking, tenant isolation on every query.
- Never commit student data, raw licensed datasets, `.env` files or secrets. `data/` is git-ignored.

## 4. Working rules
- Audit before editing. Map existing routes, tables, models and screens before proposing changes (Phase 0 §3).
- Keep a thin vertical slice running at every phase.
- Core mastery and recommendation logic must work without any generative AI; the LLM only explains.
- Every recommendation has a human-readable reason (the explainability contract in Phase 2).
- Evaluate the adaptive policy against a fixed-path baseline and simple rules. Report honest misses.
- Keep synthetic, public-dataset and pilot evidence separate; label every number with its origin.
- Record dataset versions, splits, seeds, model versions and evaluation scripts for reproducibility.
- Never guess an external fact: write a research prompt, check a primary source, and list what is still unverified.

## 5. Status (2026-11-05)
- Pragati 1.0 code kept: backend (FastAPI, ingestion, Rasch mastery, early-warning models, OMR reader, report pipeline), frontend (Next.js console), ML validation (OULAD, ASSISTments), synthetic generator, contracts.
- Removed in the cleanup: financial model, decks, Round 1 and 2 plans, agent logs, Case B institute outputs. See `docs/CLEANUP_LOG.md`.
- Phase 0 has not started. Its outputs go in `docs/audit/` (feature inventory, database audit, model audit, baseline test report) and `docs/architecture/decisions/`.
- Still open from 1.0 (carry-over, not verified for 2.0): hierarchical 2PL IRT, the 150-question tagging model, real phone-photo OMR accuracy, Hindi review by a native speaker.

## 6. How the owner wants the AI to work
- Act as technical co-founder and lead ML and systems engineer. Challenge the plan like a hostile judge and like a teacher who will use it.
- Be precise: use tables and checklists; state limitations before the judges do.
- For buildable modules, write self-contained agent prompts: goal, inputs, contracts, file paths, acceptance criteria, tests and a DO NOT list.
- Think about edge cases and real deployment, not only the demo.
