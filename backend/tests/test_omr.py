"""OMR reader tests. Sheets come from OMR_DATA_DIR (default: main checkout data/omr/synthetic); skipped if absent."""
import json
import numpy as np
import cv2
import pytest

from app.omr import read_sheet, render_overlay, score
from app.omr.evaluate import compare, data_dir

D = data_dir()
needs_data = pytest.mark.skipif(not (D / "truth.json").exists(), reason="synthetic OMR data not present")


def _pick(cond, layout=None, n=2):
    t = json.loads((D / "truth.json").read_text(encoding="utf-8"))["sheets"]
    return [r for r in t if r["augmentation_condition"] == cond and (layout is None or r["layout_name"] == layout)][:n]


@needs_data
@pytest.mark.parametrize("cond", ["clean_scan", "perspective_skew", "shadow_gradient", "low_light_whatsapp", "photo_of_screen_moire", "motion_blur"])
def test_accuracy_per_condition(cond):
    ok = tot = 0
    for rec in _pick(cond, n=4):
        res = read_sheet(D / rec["image_filename"])
        assert not res.quality.retake, res.quality.reason
        assert res.layout_name == rec["layout_name"] and res.test_id == rec["test_id"]
        assert res.roll_no == rec["roll_no"]
        o, t, _ = compare(rec, res)
        ok, tot = ok + o, tot + t
    assert ok / tot >= 0.98


@needs_data
def test_all_layouts_bytes_input_and_overlay():
    for layout in ("jee_75", "neet_200", "generic_mcq_100"):
        rec = [r for r in json.loads((D / "truth.json").read_text(encoding="utf-8"))["sheets"] if r["layout_name"] == layout][:1]
        res = read_sheet((D / rec[0]["image_filename"]).read_bytes())
        assert len(res.questions) == {"jee_75": 75, "neet_200": 200, "generic_mcq_100": 100}[layout]
        ov = render_overlay(res)
        assert ov is not None and ov.shape[2] == 3
        assert res.elapsed_ms < 2000


@needs_data
def test_statuses_and_uncertain_for_multi_mark():
    for rec in _pick("clean_scan", None, 6):
        res = read_sheet(D / rec["image_filename"])
        for qn, t in rec["responses"].items():
            if t["status"] == "multi_marked":
                assert res.questions[int(qn)].status == "multi_marked"
                assert any(u.question_no == int(qn) and u.reason == "double_mark" for u in res.uncertain)
            if t["status"] == "blank":
                assert res.questions[int(qn)].status == "blank"


@needs_data
def test_score_helper():
    rec = _pick("clean_scan", "jee_75", 1)[0]
    res = read_sheet(D / rec["image_filename"])
    key = {int(q): (t["marked"] if t["status"] == "answered" else "A") for q, t in rec["responses"].items() if len(t["marked"] or "") == 1}
    out = score(res, key, "jee_main")
    n_ok = sum(1 for q, t in rec["responses"].items() if int(q) in key and t["status"] == "answered")
    assert out["correct"] == n_ok
    assert out["marks"] == 4 * out["correct"] - out["wrong"]


def test_unusable_photos_ask_for_retake():
    blank = np.full((1200, 900, 3), 240, np.uint8)
    r = read_sheet(blank)
    assert r.quality.retake and "corner" in r.quality.reason
    dark = np.full((1200, 900, 3), 10, np.uint8)
    assert read_sheet(dark).quality.retake


@needs_data
def test_blurry_photo_flagged():
    rec = _pick("clean_scan", "jee_75", 1)[0]
    img = cv2.imdecode(np.fromfile(str(D / rec["image_filename"]), np.uint8), 1)
    r = read_sheet(cv2.GaussianBlur(img, (0, 0), 6))
    assert r.quality.retake and "blur" in r.quality.reason.lower()
