# Pragati: The Data Moat (Case B, Nextute × Finance Club IIT Patna)

**Team AlphaQ.** An AI platform that turns a coaching institute's messy data (OMR sheets, Excel, WhatsApp) into a topic-by-topic view of every student, a short weekly support list for mentors with plain reasons, an honest percentile range, and checked Hindi and English parent reports. Built to win the case (70 % technology, 30 % business) and to be sold afterwards. Everything is free to run, local first, and uses synthetic student data validated on public datasets.

```
FC_Case_Dhruvi/
  technical/      the product: contracts, data generator, models, report generator, tests, plan
  financial/      the financial model (v1.1), audit, guides and research
  presentation/   the Round 1 deck in four versions, its build tooling and design docs
  CLAUDE.md       hand-off for an AI assistant or a teammate (read first)
  _archive/       local backups of superseded copies (not in git; safe to delete)
```

## Where we are (22 Oct 2026)
| Area | Progress | Next |
|---|---|---|
| **Technical** | Contracts frozen (31 tables, 23 endpoints, 380 topics). Synthetic data generator, public-data validation (OULAD AUC 0.706, ASSISTments 0.763), parent-report pipeline with 8 checks. 116 tests pass | Fix cohort sizes and verifier gaps (`R1_A2`, `R1_E2`); then IRT, risk and tagging agents (B, C, F); backend, frontend, OMR reader |
| **Financial** | Model v1.1 after a CFO audit: 0 formula errors, independent rebuild matches. Base: LTV÷CAC 3.6x, payback 5.7 months, owner return 1.7x (0.55x on fees and staff time), year-3 revenue ₹65 L, funding ₹45 L | Owner interviews and price survey (willingness to pay is the weakest input); Round 2 sheets |
| **Presentation** | Round 1 deck v4 (22 slides: title, 12 content, appendix, AI-use slide); v1 to v3 kept | Fill the PENDING gates from agent results, add logo, export PDF, practise the pitch |

## How the pieces connect
`technical` produces measured numbers (`metrics.json`) → `presentation` quotes them with an origin label (public, synthetic, model, mock-up). `financial` produces the business numbers → `presentation` quotes them as model output. Nothing on a slide is typed from memory.

## Quick commands
```
cd technical && python -m pytest tests -q                    # 68 document, deck and number tests
cd presentation/source/build && python build_all.py v4       # rebuild a deck and its previews
cd financial/model && python verify_model.py --all           # recalculate the workbook without Excel (about 3 minutes)
```

## Tracking progress
- **Decks:** `presentation/VERSIONS.md` lists every version, what changed and why. Open `presentation/decks/AlphaQ_CaseB_Round1_CURRENT_v5.pptx`; earlier decks sit beside it (earlier-1, earlier-2, earlier-3).
- **Finance:** `financial/VERSIONS.md` (v1.0 and CURRENT v1.1), `financial/docs/MODEL_AUDIT.md` and `DECK_NUMBER_UPDATES.md` record each change to the numbers.
- **Technical:** `technical/docs/agent_logs/` and `contract_change_requests.md` record what each agent did and every contract change.
- **Git history** is the audit trail; commit per version.

## Ground rules
Never guess an external fact (write a research prompt instead); label every number by origin; state limitations before the judges do; no paid services; no Streamlit or Gradio.
