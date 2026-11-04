# Cleanup log: 2026-11-05 (Pragati 1.0 to 2.0)

## Why
Pragati 2.0 is a different product (adaptive learning paths for JEE aspirants, for the DataNova Global Data-thon 2026). The Case B competition material was no longer needed to start the work. Working code was kept so Phase 0 can audit it.

## Recovery
Everything removed here is still in git history. To look at a removed file:

```
git show 512380d:<old-path>
```

`512380d` is the last commit of 1.0 on `main`. Old paths are the pre-cleanup paths (for example `technical/backend/app/main.py`, `presentation/decks/...`, `financial/model/...`).

## Removed
| Area | What | Why |
|---|---|---|
| `financial/` (all) | Case B financial model v1.0 and v1.1, audit, guides, research R1 to R7 | Business case for Case B; not needed for the hackathon submission |
| `presentation/` (all) | Round 1 decks v1 to v5 and candidates, previews (PNG), source build scripts (Node and Python), legacy build code, flat icons and maps, video HTML and brag output, submission copies | Superseded by the 2.0 presentation; previews and old decks were generated outputs |
| `technical/analysis/` | Feasibility simulations and adversarial verifier cases for Case B | Round 1 evidence, not product code |
| `technical/notebooks/01_synthetic_data.ipynb`, `08_genai_reports.ipynb` | Case B synthetic-data and report notebooks | Case B only. `06_public_validation.ipynb` kept |
| `technical/tests/` | Deck, slide, deck-number and docs-consistency tests | They checked the Case B deck and agent prompts |
| `technical/scripts/deck_numbers.py` | Number tracing for the deck | Case B deck only |
| `technical/docs/agent_prompts/`, `agent_logs/` | Antigravity agent prompts and their reports | Multi-agent build records for Case B |
| `technical/docs/RESEARCH_PROMPTS.md`, `research_results.txt`, `contract_change_requests.md`, `generator_config_draft.yaml`, `PS_COVERAGE.md` | Research prompts, raw research output, contract change log, draft generator config, Case B problem-statement matrix | Case B process records |
| `technical/docs/FINAL_ROUND_PLAN.md`, `ROUND2_PLAN.md`, `BUILD_PLAN_R2.md`, `TAB1_ML_PLAN.md` | Round 1 and Round 2 plans | Superseded by `docs/pragati-2.0/` |
| `technical/web/NOTES.md` | Front-end agent notes | Process record |
| `technical/ml/artifacts/gaya_both`, `kota_large`, `lucknow_neet`, `patna_jee`, `samples`, `figures` | Per-institute model outputs and figures for the Case B synthetic institutes | Generated data; regenerate with `ml/build_artifacts.py` if needed |
| `technical/ml/artifacts/irt_table.csv`, `moat.json`, `scaling.json`, `models.json`, `metrics.json` | Case B summary outputs | Generated data; regenerate if needed |
| Root `README.md`, `CLAUDE.md`, `technical/README.md` | Case B hand-off and folder map | Moved, not deleted, to `docs/legacy-case-b/` |

## Kept and moved (structure)
`technical/` was flattened so each part sits at the repository root. Relative paths between the parts did not change.

| Old path | New path |
|---|---|
| `technical/backend/` | `backend/` |
| `technical/web/` | `frontend/` |
| `technical/ml/` | `ml/` (trained models kept in `ml/artifacts/models/`; public-validation results kept) |
| `technical/datagen/` | `datagen/` |
| `technical/contracts/` | `contracts/` |
| `technical/scripts/` | `scripts/` (public-data download, test runners) |
| `technical/notebooks/06_public_validation.ipynb` | `notebooks/06_public_validation.ipynb` |
| `technical/Makefile`, `technical/requirements-dev.txt` | `Makefile`, `requirements-dev.txt` |
| `technical/docs/*` (kept files), `technical/README.md`, root `README.md`, root `CLAUDE.md` | `docs/legacy-case-b/` |
| `presentation/video/pragati_architecture.html` | `docs/legacy-case-b/pragati_architecture.html` |
| Pragati 2.0 phase blueprint (in the main folder, untracked) | `docs/pragati-2.0/` |
| `PROJECT_DEEP_SUMMARY.md` (in the main folder, untracked) | `docs/legacy-case-b/PROJECT_DEEP_SUMMARY_case_b.md` |

## Path edits made
- Code and comments that named `technical/...` now name the new paths (`backend/app/config.py`, `backend/app/cli.py`, `backend/app/main.py`, `backend/app/ml/train.py`, `backend/app/omr/evaluate.py`, `backend/tests/test_frontend_contract.py`, `frontend/lib/*`, `ml/*`, `datagen/*`, `contracts/*`, `Makefile`, `scripts/*`, `.gitattributes`).
- Two hard-coded default data paths that pointed to a folder outside this repository were replaced by `ROOT/data` (override with `DATA_DIR`).
- `Makefile`: removed the `test-docs` target (its tests were removed) and the agent labels.
- `.gitignore`: removed rules for the deleted `presentation/` and `datamoat/` folders.

## Known effects
- The front-end mock server reads `ml/artifacts/<institute>/*.json`, which were removed. Regenerate with `python ml/build_artifacts.py` after `datagen`, or it will show no data.
- Backend and contract tests that compare with those outputs need the regenerated data.
- Historical documents in `docs/legacy-case-b/` and the contract data dictionary still use Case B agent names and the old paths. They are records, not instructions.

## Not touched
- Anything in the main folder `D:\Professional Work\Business\Pragati 2.0` (its untracked folders `datamoat/`, `institute-intelligence-platform/`, `technical/`, `_archive/`, and the untracked phase and summary files) was not modified. Only read.
