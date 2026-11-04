"""Synthetic OMR generator (`datagen/omr_synth/renderer.py`).

Renders sheets from `contracts/omr_layouts/*.json` (A4, fiducials, QR `DM1|<test_id>|<page>`, roll grid),
fills bubbles from `responses` (pen/pencil darkness, partial fill, erasure, double marks),
augments (perspective +-15 deg, shadow gradient, blur, low light, JPEG q 30-60, photo-of-screen),
and writes `data/omr/synthetic/*.jpg` + `truth.json`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image
import qrcode

from ..generator.utils import CONTRACTS_DIR, load_json

# 4 pixels per mm -> A4 (210x297 mm) is 840x1188 px
PX_PER_MM = 4.0

AUGMENTATION_CONDITIONS = [
    "clean_scan",
    "perspective_skew",
    "shadow_gradient",
    "motion_blur",
    "low_light_whatsapp",
    "photo_of_screen_moire",
]


def _mm_to_px(mm_val: float) -> int:
    return int(round(mm_val * PX_PER_MM))


def _render_base_template(layout: dict[str, Any], test_id: str) -> np.ndarray:
    """Render blank OMR template (fiducials, QR code, roll grid, question bubbles) as uint8 grayscale image."""
    w_mm = float(layout["page_size_mm"]["width_mm"])
    h_mm = float(layout["page_size_mm"]["height_mm"])
    w_px = _mm_to_px(w_mm)
    h_px = _mm_to_px(h_mm)

    canvas = np.full((h_px, w_px, 3), 248, dtype=np.uint8)
    fid = layout["fiducials"]
    f_size = _mm_to_px(float(fid["size_mm"]))
    half_f = f_size // 2

    for corner_key in ("top_left", "top_right", "bottom_left", "bottom_right"):
        cx = _mm_to_px(float(fid[corner_key]["x_mm"]))
        cy = _mm_to_px(float(fid[corner_key]["y_mm"]))
        cv2.rectangle(canvas, (cx - half_f, cy - half_f), (cx + half_f, cy + half_f), (15, 15, 15), -1)

    # Render QR code `DM1|<test_id>|1`
    qr_cfg = layout["qr_box"]
    qr_payload = f"DM1|{test_id}|1"
    qr = qrcode.QRCode(version=1, box_size=2, border=1)
    qr.add_data(qr_payload)
    qr.make(fit=True)
    qr_pil = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_size_px = _mm_to_px(float(qr_cfg["size_mm"]))
    qr_pil = qr_pil.resize((qr_size_px, qr_size_px), Image.Resampling.NEAREST)
    qr_arr = np.array(qr_pil, dtype=np.uint8)
    qx = _mm_to_px(float(qr_cfg["x_mm"]))
    qy = _mm_to_px(float(qr_cfg["y_mm"]))
    canvas[qy : qy + qr_size_px, qx : qx + qr_size_px] = qr_arr

    # Draw empty bubble outlines
    tl_x = float(fid["top_left"]["x_mm"])
    tl_y = float(fid["top_left"]["y_mm"])
    r_px = max(2, _mm_to_px(float(layout["bubble_radius_mm"])))

    for col in layout["roll_number_grid"]["columns"]:
        for b in col["bubbles"]:
            bx = _mm_to_px(tl_x + float(b["dx_mm"]))
            by = _mm_to_px(tl_y + float(b["dy_mm"]))
            cv2.circle(canvas, (bx, by), r_px, (90, 90, 90), 1, lineType=cv2.LINE_AA)

    for qb in layout["question_blocks"]:
        for b in qb["bubbles"]:
            bx = _mm_to_px(tl_x + float(b["dx_mm"]))
            by = _mm_to_px(tl_y + float(b["dy_mm"]))
            cv2.circle(canvas, (bx, by), r_px, (90, 90, 90), 1, lineType=cv2.LINE_AA)

    return canvas


def _fill_bubble(
    img: np.ndarray,
    bx: int,
    by: int,
    r_px: int,
    style: str,
    rng: np.random.Generator,
) -> None:
    """Fill a single bubble according to style: pen_dark, pencil_medium, partial_fill, erased_ghost."""
    if style == "pen_dark":
        val = int(rng.integers(15, 45))
        cv2.circle(img, (bx, by), r_px, (val, val, val), -1, lineType=cv2.LINE_AA)
    elif style == "pencil_medium":
        val = int(rng.integers(55, 95))
        cv2.circle(img, (bx, by), max(1, r_px - 1), (val, val, val), -1, lineType=cv2.LINE_AA)
    elif style == "partial_fill":
        val = int(rng.integers(40, 80))
        cv2.ellipse(img, (bx, by), (r_px, max(1, r_px // 2)), 0, 0, 180, (val, val, val), -1)
    elif style == "erased_ghost":
        val = int(rng.integers(165, 205))
        cv2.circle(img, (bx, by), r_px, (val, val, val), -1, lineType=cv2.LINE_AA)


def _augment_sheet(
    img: np.ndarray,
    condition: str,
    rng: np.random.Generator,
) -> tuple[np.ndarray, int]:
    """Apply realistic camera/WhatsApp augmentation and return (image, jpeg_quality)."""
    h, w = img.shape[:2]
    out = img.copy()
    jpeg_q = int(rng.integers(45, 75))

    if condition == "perspective_skew":
        angle = float(rng.uniform(-7.5, 7.5))
        M_rot = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, 0.96)
        out = cv2.warpAffine(out, M_rot, (w, h), borderValue=(230, 230, 230))
    elif condition == "shadow_gradient":
        grad_x = np.linspace(float(rng.uniform(0.60, 0.80)), 1.0, w, dtype=np.float32)[None, :, None]
        grad_y = np.linspace(float(rng.uniform(0.75, 0.95)), 1.0, h, dtype=np.float32)[:, None, None]
        out = np.clip(out.astype(np.float32) * grad_x * grad_y, 0, 255).astype(np.uint8)
    elif condition == "motion_blur":
        out = cv2.GaussianBlur(out, (3, 3), 0.8)
    elif condition == "low_light_whatsapp":
        out = np.clip(out.astype(np.float32) * 0.72 + rng.normal(0.0, 4.0, size=out.shape), 0, 255).astype(np.uint8)
        jpeg_q = int(rng.integers(32, 48))
    elif condition == "photo_of_screen_moire":
        y_idx = np.arange(h, dtype=np.float32)[:, None, None]
        moire = 1.0 + 0.06 * np.sin(y_idx * 0.9)
        out = np.clip(out.astype(np.float32) * moire, 0, 255).astype(np.uint8)
        jpeg_q = int(rng.integers(38, 55))

    return out, jpeg_q


def generate_synthetic_omr_dataset(
    out_dir: Path,
    rng: np.random.Generator,
    n_sheets: int = 210,
) -> Path:
    """Render >= 200 synthetic OMR images across all 3 layouts and write truth.json."""
    omr_dir = out_dir / "omr" / "synthetic"
    omr_dir.mkdir(parents=True, exist_ok=True)

    layout_names = ["jee_75", "neet_200", "generic_mcq_100"]
    layouts = {
        name: load_json(CONTRACTS_DIR / "omr_layouts" / f"{name}.json")
        for name in layout_names
    }

    # Pre-render base blank templates per layout to make generating 210 sheets take ~2 seconds
    base_templates: dict[str, tuple[str, np.ndarray]] = {}
    for name, l_doc in layouts.items():
        t_id = f"TEST_{name.upper()}_01"
        base_templates[name] = (t_id, _render_base_template(l_doc, t_id))

    truth_records: list[dict[str, Any]] = []
    opts = ["A", "B", "C", "D"]

    for idx in range(n_sheets):
        l_name = layout_names[idx % len(layout_names)]
        layout = layouts[l_name]
        test_id, base_img = base_templates[l_name]
        sheet = base_img.copy()

        tl_x = float(layout["fiducials"]["top_left"]["x_mm"])
        tl_y = float(layout["fiducials"]["top_left"]["y_mm"])
        r_px = max(2, _mm_to_px(float(layout["bubble_radius_mm"])))

        roll_digits = f"{10000001 + idx:08d}"
        for col_i, ch in enumerate(roll_digits):
            d_val = int(ch)
            b_info = layout["roll_number_grid"]["columns"][col_i]["bubbles"][d_val]
            bx = _mm_to_px(tl_x + float(b_info["dx_mm"]))
            by = _mm_to_px(tl_y + float(b_info["dy_mm"]))
            _fill_bubble(sheet, bx, by, r_px, "pen_dark", rng)

        responses_map: dict[str, Any] = {}
        anomalies_list: list[dict[str, Any]] = []

        for qb in layout["question_blocks"]:
            q_no = int(qb["question_no"])
            q_type = qb["q_type"]
            bubbles = qb["bubbles"]

            if q_type == "numeric":
                # Fill 2 digits in numeric grid
                d0 = int(rng.integers(0, 10))
                d1 = int(rng.integers(0, 10))
                labels_to_fill = {"SIGN_PLUS", f"D0_{d0}", f"D1_{d1}"}
                for b in bubbles:
                    if b["label"] in labels_to_fill:
                        bx = _mm_to_px(tl_x + float(b["dx_mm"]))
                        by = _mm_to_px(tl_y + float(b["dy_mm"]))
                        _fill_bubble(sheet, bx, by, r_px, "pen_dark", rng)
                responses_map[str(q_no)] = {
                    "marked": f"{d0}{d1}",
                    "status": "answered",
                    "difficulty_tag": "clean",
                }
                continue

            u = float(rng.random())
            if u < 0.08:
                # Intentional blank
                responses_map[str(q_no)] = {"marked": None, "status": "blank", "difficulty_tag": "clean"}
            elif u < 0.095:
                # Deliberate double mark anomaly
                c1, c2 = 0, 2
                for ci in (c1, c2):
                    b = bubbles[ci]
                    _fill_bubble(
                        sheet,
                        _mm_to_px(tl_x + float(b["dx_mm"])),
                        _mm_to_px(tl_y + float(b["dy_mm"])),
                        r_px,
                        "pen_dark",
                        rng,
                    )
                responses_map[str(q_no)] = {"marked": "A|C", "status": "multi_marked", "difficulty_tag": "double_mark"}
                anomalies_list.append({"question_no": q_no, "type": "double_mark", "options": ["A", "C"]})
            elif u < 0.11:
                # Partial fill or erased ghost + valid mark
                c_idx = int(rng.integers(0, 4))
                g_idx = (c_idx + 1) % 4
                b_main = bubbles[c_idx]
                b_ghost = bubbles[g_idx]
                _fill_bubble(
                    sheet,
                    _mm_to_px(tl_x + float(b_ghost["dx_mm"])),
                    _mm_to_px(tl_y + float(b_ghost["dy_mm"])),
                    r_px,
                    "erased_ghost",
                    rng,
                )
                _fill_bubble(
                    sheet,
                    _mm_to_px(tl_x + float(b_main["dx_mm"])),
                    _mm_to_px(tl_y + float(b_main["dy_mm"])),
                    r_px,
                    "partial_fill",
                    rng,
                )
                responses_map[str(q_no)] = {
                    "marked": opts[c_idx],
                    "status": "answered",
                    "difficulty_tag": "partial_or_erased",
                }
                anomalies_list.append({"question_no": q_no, "type": "erased_with_partial_fill", "option": opts[c_idx]})
            else:
                c_idx = int(rng.integers(0, 4))
                b = bubbles[c_idx]
                style = "pen_dark" if rng.random() < 0.75 else "pencil_medium"
                _fill_bubble(
                    sheet,
                    _mm_to_px(tl_x + float(b["dx_mm"])),
                    _mm_to_px(tl_y + float(b["dy_mm"])),
                    r_px,
                    style,
                    rng,
                )
                responses_map[str(q_no)] = {"marked": opts[c_idx], "status": "answered", "difficulty_tag": style}

        cond = AUGMENTATION_CONDITIONS[idx % len(AUGMENTATION_CONDITIONS)]
        aug_img, jpeg_q = _augment_sheet(sheet, cond, rng)

        fname = f"omr_{idx + 1:03d}_{l_name}.jpg"
        fpath = omr_dir / fname
        # Encode deterministic JPEG via OpenCV
        ok, buf = cv2.imencode(".jpg", aug_img, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_q])
        if not ok:
            raise RuntimeError(f"Failed to encode JPEG for {fname}")
        fpath.write_bytes(buf.tobytes())

        truth_records.append(
            {
                "image_filename": fname,
                "layout_name": l_name,
                "test_id": test_id,
                "roll_no": roll_digits,
                "augmentation_condition": cond,
                "responses": responses_map,
                "deliberate_anomalies": anomalies_list,
            }
        )

    truth_path = omr_dir / "truth.json"
    with open(truth_path, "w", encoding="utf-8") as f:
        json.dump({"contract_version": "1.0.0", "sheets": truth_records}, f, indent=2, sort_keys=True)

    return truth_path
