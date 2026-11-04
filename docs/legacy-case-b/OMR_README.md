# OMR reader (phase P7)

Offline, pure Python (`opencv-python`, `numpy`, `pyyaml`; QR via `cv2.QRCodeDetector`). Code: `technical/backend/app/omr/`.

## API (what the backend calls)

```python
from app.omr import read_sheet, score, render_overlay

read_sheet(image, layout_name=None, debug=False) -> OmrResult
#  image: path | bytes (upload) | numpy BGR/gray array. Never raises on a bad photo.
#  layout_name: optional override; otherwise taken from the QR "DM1|<test_id>|<page>"
#  (the layout name must appear in test_id, e.g. TEST_JEE_75_01), else guessed from the bubble grid.
score(result, answer_key: {qno: "B" | "A|C" | "37"}, marking_scheme: "jee_main" | dict) -> dict
render_overlay(result, scale=1.0) -> BGR ndarray | None   # flattened page, marks ringed, review dots
result.to_dict()  # JSON-safe (no image)
```

`OmrResult`: `layout_name, test_id, qr_payload, roll_no (None if any digit unreadable), roll_confidence,
questions{qno: QuestionRead}, uncertain[UncertainCell], quality, elapsed_ms, warped`.

- `QuestionRead`: `answer` ("B", "37", "A|C" for multi, None), `status` in `answered | blank | multi_marked | unreadable`
  (the `datasets.yaml` values), `confidence` 0..1, `marked_options`, `fills` (per-cell darkness 0..1).
- `uncertain`: cells for one-tap review. reason is `faint_mark`, `double_mark`, `ambiguous`, `unreadable`, `roll_column`.
- `quality`: `retake` (bool), `reason` (human text, show it to the teacher), `sharpness, page_fraction, brightness, notes`.
  Retake when: no four corner marks / sheet too small in frame / too dark / too blurry / more than 20 % of questions unreadable.
- `score`: correct/wrong/blank from the scheme; `multi_marked` counts as wrong, `unreadable` as blank; `needs_review` lists
  questions with uncertain cells. Numeric answers compare as numbers.

## Method
1. Find the four solid black squares (adaptive + Otsu threshold, contour filters). Squares clipped by the photo edge are
   rebuilt from their inner vertex. Perspective-warp to a flat 4 px/mm page.
2. QR decode on the warped crop (several preprocessings) selects the layout; fallback = ring-match score over all layouts.
3. Divide by a local paper-level estimate (max filter) to remove shadows; per bubble darkness = 1 - mean inner disc (±1 px search).
   Subtract the sheet baseline (median of all cells), then the row minimum (numeric: column median) to cancel creases.
4. Decision per row: mark if fill ≥ 0.22; second mark counts only if ≥ 0.35 and ≥ 60 % of the strongest.
   Faint (0.07–0.22) and weak (<0.45) marks are flagged for review.

## Accuracy (synthetic only)
Unit = one question row (answer/blank/multi status all must match). `python -m app.omr.evaluate` (set `OMR_DATA_DIR`).

| condition (renderer's names) | sheets | accuracy |
|---|---|---|
| clean_scan | 35 | 1.0000 |
| perspective_skew (rotation ±7.5°, corners often clipped) | 35 | 0.999 |
| shadow_gradient | 35 | 1.0000 |
| motion_blur | 35 | 1.0000 |
| low_light_whatsapp | 35 | 1.0000 |
| photo_of_screen_moire | 35 | 1.0000 |
| **overall** | 210 | **0.9997** (roll number 210/210) |

Of the 6 wrong rows, 5 were flagged for review, 1 was silent. Latency: median ~0.25 s, p95 ~0.35 s per sheet.

Harder, phone-like conditions made by `python -m app.omr.stress` (our own augmentations on 24 clean sheets: real homography,
table background, 2x upscale + JPEG q25–40, shadow, crease lines, faint ink):

| condition | accuracy |
|---|---|
| s_perspective (strong tilt) | 1.000 |
| s_low_light_shadow | 1.000 |
| s_crease_shadow | 0.997 |
| s_whatsapp_recompressed | 1.000 |
| s_faint_pencil (ink contrast ×0.75) | 1.000 |
| s_combined (faint + crease + heavy shadow + recompress) | 0.918 (most misses are flagged faint marks) |

## Known limits (be honest with judges)
- **No real phone photo has ever been tested.** All numbers are synthetic; the synthetic sheet is 840 px wide, so bubbles are 7–8 px across.
  Real photos with glare, curled paper, or a finger over a corner are untested. Uncertain cells are surfaced, not guessed.
- Partial fills (half-filled bubble) and erased ghosts overlap in darkness (0.2–0.27); a light partial mark may read as blank and is flagged `faint_mark`.
  A ghost with no real mark could read as answered but is flagged `ambiguous`.
- Renderer condition names differ from the brief (`perspective_skew`, `shadow_gradient`, `motion_blur`, `low_light_whatsapp`, `photo_of_screen_moire`); crease and faint pencil are covered only by our stress script.
- Combined extreme conditions (faint + crease + shadow) can lose ~8 % of rows; a blurry-but-sharp-enough page is not detected.
- The layout from the QR is matched by name inside `test_id`; real QR payloads need the layout name in them (or pass `layout_name`).
- Fiducials need ≥ 2 fully visible squares; a corner square hidden by a finger gives "retake".
- Only 4-option MCQ and numeric (sign + digit columns) are read; the decimal-point bubbles of numeric questions are ignored.
- A skewed sheet where the table/background is the same dark colour as the marks may fail corner detection (retake).
