# S1 log: demo-chain items

**Date:** 2026-11-05. **Branch:** claude/serene-sagan-8za1vh. **Gate status: NOT MET** (drafted and computationally checked; zero human reviews).

## What was done
| Item | Result |
|---|---|
| Generator | `ml/dataset_pipeline/generate_demo_items.py` (seed 20261105, version demo-templates-v0). Writes `ml/dataset_pipeline/items/demo_chain_v0.json` |
| Items | 60 drafts: 20 on `algebra_complex_argand`, 20 on `roots_nature`, 20 on `equation_formation`. Four options each; one correct |
| Answers | Computed exactly with fractions at generation time, then recomputed in tests with a different method (floating-point complex arithmetic and `cmath` roots) |
| Uniqueness | Question texts unique across the bank (a duplicate was found by the tests and fixed in the generator) |
| Provenance | `original_reviewed`, with a run manifest in each item. No third-party text |
| Checks | `python3 -m pytest ml/dataset_pipeline/tests -q`: **258 passed** (16 rights-gate tests, 242 item checks) |

## Gate: what S1 requires and where it stands
| Requirement (PROTOTYPE_PLAN S1) | Status |
|---|---|
| 60 items on the demo chain | Done (drafts) |
| Each item carries provenance and a verified answer | Done (answer recomputed in tests) |
| Two distinct human reviewers per item | **Not done.** Reviewers list is empty; review_status is `pending` |
| `validate_item` passes for all 60 | **Not met.** Each item fails only on the reviewer requirement (checked by test) |
| Proposed edges flagged | Carried by the engine (S2), not by the items |

## Limits the reviewers must judge
- The items are **templated**, so the wording is mechanical. Reviewers should judge whether each is a fair JEE-style question at the stated level. Most are easier than JEE Main.
- Phrasing to check: "coefficient of x" in the formation items (it means B in x² + Bx + C = 0); the discriminant item prints terms like `(-6)x`; some distractors are not meaningful (for example negative counts).
- Difficulty labels (`easy`, `medium`) are targets, not measured. They are not empirical difficulty.
- No Hindi versions. Hindi needs a reviewer (B12).
- These are not the authentic exam items. Authentic items wait for permission (B15).

## Review (named reviewers: Aditya, Ashray)
- Review sheet: `ml/dataset_pipeline/review/demo_chain_v0_review.csv` (60 rows). Each reviewer fills their own verdict column (`approve`, `edit`, `reject`) and notes.
- Apply: `python3 -m ml.dataset_pipeline.reviews apply <returned.csv>`. An item becomes `approved` only when BOTH reviewers write `approve`. Any `edit` or `reject` blocks approval. Blank verdicts change nothing. The script never records an approval on a reviewer's behalf.
- Edits: reviewers may change the JSON directly, or send suggested wording back. Wording changes made to the generator are re-run from the generator so the manifest stays accurate.
- Current status: **0 of 60 reviewed.** Gate closes when all 60 show `approved` and `validate_item` returns no problems.

## Changes made before review (so reviewers check content, not formatting)
- Polynomials print as `5x^2 - 3x + 4 = 0` (no `(-6)x`; no `1x^2`).
- Formation items ask "find B" and "find C" for x^2 + Bx + C = 0 (replacing "coefficient of x").
- Complex items print `(a+bi)^2`.
- Question texts are unique (tests).

## Recommendations for reviewers
- Several distractors are obviously wrong (for example a negative count of roots or a negative modulus-squared). Replace with plausible mistakes where a student would slip (a sign error, a forgotten cross term, or b instead of -b).
- The nature-of-roots items use 0, 1 or 2 as answers. Check the distractors are plausible counts.
- Decide whether the easy/medium labels fit; they are targets only.

## Status
- Gate status: **NOT MET** (0 of 60 reviewed). 266 tests pass.
