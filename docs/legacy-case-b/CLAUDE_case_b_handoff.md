# CLAUDE.md — Project handoff (read this first)
Last updated: 2026-10-22 (folder cleanup: technical / financial / presentation) · Owner: adityak12work@gmail.com

If you are an AI assistant (Claude, Gemini, etc.) or a teammate opening this folder or zip: this page is enough to get up to speed in 2 minutes. Then read the files in the order listed in §3.

## 1. What this is
- **Competition:** Nextute Edtech × Finance Club IIT Patna, **Case B "The Data Moat"**. Case brief: `1792441177680_Case_B_The_Data_Moat.pdf`.
- **Product:** an AI "Institute Intelligence Platform" for small and mid-sized JEE/NEET coaching institutes in Tier-2/3 India. It captures OMR photos, Excel and WhatsApp data, and produces a topic-mastery heatmap, early warning with reasons and *supportive* actions, a predicted percentile **range**, and verified Hindi/English parent reports. The aim is also to sell it for real afterwards.
- **Scoring:** 70 % technology (architecture 25 / ML rigour 25 / feasibility-privacy-safety 20), 30 % business.
- **Rounds:**
  - R1 (online): ≤ 12-slide deck + financial model + bonus GitHub/Colab notebook with real validation metrics.
  - R2 (offline finale): a working prototype demoed live (judges change inputs), a 2–4 page model & system report, and a 60-min curveball (expected to be mildly technical).

## 2. Hard constraints (decided by the owner — don't change without saying why)
- **Everything free. Fully local first** (laptop RTX 4060 8 GB + Colab). Hosting gets decided later.
- Stack: Next.js (TS, Tailwind, shadcn/ui, ECharts) · FastAPI (Py 3.11) · PostgreSQL 16 · LightGBM · NumPy/PyTorch IRT · SHAP · conformal prediction · OpenCV · Ollama (local LLM). **No Streamlit/Gradio.**
- No real institute data. Student data is **synthetic**, from a seeded generator with ground truth. Methods are validated on public data (OULAD, ASSISTments2009 under the pyKT protocol).
- Built by **parallel Google Antigravity agents** against frozen `contracts/`.

## 3. File map (read in this order)
Repo root = this folder. Three work folders plus a local `_archive/` (backups, not in git).
| File | What it is |
|---|---|
| `README.md` | Folder map, progress table, quick commands |
| `technical/README.md` | What each technical folder holds, status, how to run tests |
| `technical/docs/TECH_PLAN.md` | **Source of truth** for the technical side (v2): architecture, data model, ML methods + acceptance bars, privacy/DPDP design, tests, agent plan, research log (section 24). Index of all technical docs: `technical/docs/README.md` |
| `technical/docs/agent_prompts/` | Antigravity prompts (P0, P0b, R1_A to R1_F); `agent_logs/` hold what each agent reported |
| `technical/docs/FEASIBILITY_CHECK.md`, `PS_COVERAGE.md`, `CITATIONS.md`, `ROUND2_PLAN.md` | Analyst review of the bars, problem-statement matrix, sources and AI-use disclosure, Round 2 plan |
| `financial/README.md` | **Finance hand-off**: headline numbers with cell refs, deck story, do-not-claim list |
| `financial/docs/MODEL_AUDIT.md`, `DECK_NUMBER_UPDATES.md`, `FINANCE_PLAN.md` | CFO review (18 findings), old to new numbers, the plan |
| `financial/model/DataMoat_Financial_Model_CURRENT_v1.1.xlsx` | The model (live formulas). Rebuild `python build_model.py` in `financial/model`; check `python verify_model.py --all` |
| `financial/docs/*.pdf`, `financial/research/` | Plain-English guide, preparation report, raw research R1 to R7 |
| `presentation/README.md`, `presentation/VERSIONS.md` | Deck folders, rebuild steps, version history (v1 to v4; **v4 is current**) |
| `presentation/docs/SLIDES_BRIEF.md`, `DESIGN_SYSTEM.md`, `BLUEPRINTS.md`, `PRESENTER_NOTES_v4.md` | Slide map and verified numbers, design rules, psychology-led design intent |

## 4. Key decisions so far (details in TECH_PLAN §1 and §24)
1. **Local-first** docker-compose (db, api, web, ollama). Templates guarantee reports even with no LLM.
2. **Purpose- and age-aware routing (most important legal design).** DPDP s.9(3) bans tracking/behavioural monitoring of children *even with consent*. Under-18s therefore get ML only for **academic support** (test-based "falling behind"; basis: 4th Schedule "educational activities" + MoE 2024 cl. 10.2(xi)). Retention/fee ML for minors runs only as **transparent rules**. 18+ (droppers) get full ML with their own consent. Engagement tracking is never used for minors.
3. Verifiable parental consent for every minor: in-person ID check by the institute (Rule 10(1)(a)) + OTP record; DigiLocker in production. We are the **Data Processor**, so there is no cross-tenant training on real minors' data.
4. IRT: hierarchical 2PL with a guessing *prior* (negative marking makes guessing optional); Rasch fallback for small n; wrong-answer-key detection.
5. Early warning is compared against the institute's current rule ("attendance < 75 %"), with the operating point set by mentor capacity. Percentile = conformal band + editable NTA mapping table (labelled as an assumption).
6. GenAI: numbers come from `numbers_json` only, names are inserted after generation, a verifier checks every number, and a template is the fallback. Models to benchmark: `qwen3:4b` vs `gemma3:4b`; IndicTrans2 as backup.
7. Verified regulation (primary text): MoE 2024 — results not public (10.2(xi)), no performance-based batches (12(vii)), weekly off and no test the day after (10.1), pro-rata refund within 10 days (8(iv)). Rajasthan Act 16/2025 — ≥ 4 equal instalments, published batch size, penalties ₹50k/₹2L.
8. Public baselines to compare against (verified): OULAD withdrawal AUC 0.727 @ d14 / 0.794 @ d28 (PLOS ONE 2026); pyKT ASSISTments2009 AUC DKT 0.754 / SAKT 0.725 / AKT 0.785.

## 5. Status (2026-10-22)
- OK **Contracts** frozen at `contracts-v1.0.0` (31 tables, 23 endpoints, 380 topics; tenant isolation tested on live PostgreSQL 16). `metrics_bars.yaml` amended, pending tag v1.0.1 after the NEET 2026 check.
- OK **Wave 1** (verified): datagen (4 institutes, 3,450 students, 1.98M responses), public validation (OULAD day-28 AUC 0.706 vs published 0.794; ASSISTments AUC 0.763 vs pyKT DKT 0.754 / AKT 0.785; academic-only costs 0.008 AUC), report pipeline (20 templates, 8 checks). 116 tests pass.
- WARN **Review findings** (details in `technical/docs/FEASIBILITY_CHECK.md`): cohort sizes are 10/25/65 % per year (fix `R1_A2`); simple model beats the ranked attendance rule by only +4 to 7 % at fixed top-k (report honestly: baselines B1, B2); verifier gaps found by an independent attack (fix `R1_E2`); PS schema gaps for contracts v1.0.1.
- OK **Finance model v1.1** (CFO audit, `financial/docs/MODEL_AUDIT.md`): effective dropout reduction 4.0 % (guide 25 %), owner return 1.7x all benefits / 0.55x fees + staff time / 0.35x fees only, LTV÷CAC 3.6x (4.8x undiscounted), payback 5.7 months, margin 78 %, year-3 revenue ₹65 L, EBITDA ₹12 L, funding ₹45 L, break-even month 16. Willingness to pay is untested.
- OK **Deck** v4 in `presentation/decks/` (22 slides: title + 12 content + appendix + AI-use slide), all on finance v1.1. Amber PENDING tags remain on the learning-analytics and validation slides until agents B and C deliver. Product name Pragati, team AlphaQ.
- TODO **Next, in order:** run `R1_A2` and `R1_E2`; then B (IRT, mastery), C (risk, bands) and F (tagging; user labels 150 questions; `ollama pull qwen3:4b`); NEET 2026 check and contracts v1.0.1 tag; Wave 3 (backend, frontend, OMR reader); owner interviews and price survey; native-Hindi review of `technical/docs/topics_hi_review_for_excel.csv` and `genai_hindi_review.csv`; fill deck PENDING items, add logo, export PDF `AlphaQ_CaseB_Round1.pdf`.
- WARN **Docker is not installed** on the owner's laptop; the compose plan needs it or a native fallback (Postgres + uvicorn + npm run dev).
- NOTE Round 1 deadline is "to be announced": check email. File name must be `TeamName_Case_Round.pdf`; the final slide must disclose AI use.

## 6. How the owner wants the AI to work
- Act as **technical co-founder + lead ML/systems engineer**. Challenge the plan like a hostile judge *and* a Patna institute owner.
- **Never guess external facts.** Write precise research prompts (Perplexity / Gemini Deep Research) naming primary sources and an output format. When results come back, extract the decisions, update the plan, and list what is unverified.
- For buildable modules, write **self-contained Antigravity agent prompts**: goal, inputs, contracts, file paths, acceptance criteria, tests, and a DO NOT list.
- Think about edge cases and real deployment, not just the demo. Be precise; use tables and checklists. State limitations before the judges do.
- Every number on a slide must trace to `metrics.json`. Label each number synthetic, public, or real-photo.
