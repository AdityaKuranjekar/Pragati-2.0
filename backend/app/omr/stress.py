"""Harsher, phone-like augmentations applied to the clean synthetic sheets (our own, not the renderer's).

Run: python -m app.omr.stress   -> accuracy per condition. Conditions: perspective (+-12 deg tilt, table
background, margin), low_light_shadow, crease_shadow, whatsapp_recompressed (downscale + JPEG q25),
faint_pencil (lower ink contrast), combined.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict

import cv2
import numpy as np

from .evaluate import compare, data_dir
from .reader import read_sheet


def _perspective(img: np.ndarray, rng: np.random.Generator, mag: float = 0.06) -> np.ndarray:
    h, w = img.shape[:2]
    pad = 90
    canvas = np.full((h + 2 * pad, w + 2 * pad, 3), (70, 90, 110), np.uint8)  # table
    canvas[pad:pad + h, pad:pad + w] = img
    src = np.float32([[pad, pad], [pad + w, pad], [pad + w, pad + h], [pad, pad + h]])
    dst = src + rng.uniform(-mag, mag, (4, 2)).astype(np.float32) * np.float32([w, h])
    dst = (dst - dst.mean(0)) * 0.9 + np.float32([canvas.shape[1] / 2, canvas.shape[0] / 2])
    M = cv2.getPerspectiveTransform(src, dst.astype(np.float32))
    return cv2.warpPerspective(canvas, M, (canvas.shape[1], canvas.shape[0]), borderValue=(70, 90, 110))


def _shadow(img: np.ndarray, rng: np.random.Generator, low_light: bool) -> np.ndarray:
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    ang = rng.uniform(0, np.pi)
    g = (xx * np.cos(ang) + yy * np.sin(ang)) / max(h, w)
    shade = 0.45 + 0.55 * np.clip((g - g.min()) / (g.max() - g.min()), 0, 1)
    out = img.astype(np.float32) * shade[..., None]
    if low_light:
        out *= 0.55
    return np.clip(out, 0, 255).astype(np.uint8)


def _crease(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    h, w = img.shape[:2]
    out = img.astype(np.float32)
    for _ in range(2):
        x = rng.integers(w // 6, 5 * w // 6)
        k = rng.uniform(0.6, 0.8)
        xs = np.arange(w, dtype=np.float32)
        prof = 1 - (1 - k) * np.exp(-((xs - x) ** 2) / (2 * 5.0 ** 2))
        out *= prof[None, :, None]
        cv2.line(out, (int(x), 0), (int(x + rng.integers(-20, 20)), h), (200, 200, 200), 1)
    return np.clip(out, 0, 255).astype(np.uint8)


def _jpeg(img: np.ndarray, q: int, scale: float = 1.0) -> np.ndarray:
    if scale != 1.0:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), q])
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def _up(img: np.ndarray) -> np.ndarray:
    # phone photos have far more pixels than the 840 px synthetic sheet; simulate that before recompressing
    return cv2.resize(img, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)


def _faint(img: np.ndarray) -> np.ndarray:
    # compress contrast toward paper: pencil that is light grey rather than dark
    return np.clip(255 - (255 - img.astype(np.float32)) * 0.75, 0, 255).astype(np.uint8)


CONDITIONS = {
    "s_perspective": lambda im, r: _jpeg(_perspective(im, r), 70),
    "s_low_light_shadow": lambda im, r: _jpeg(_shadow(_perspective(im, r, 0.03), r, True), 60),
    "s_crease_shadow": lambda im, r: _jpeg(_crease(_shadow(_perspective(im, r, 0.03), r, False), r), 60),
    "s_whatsapp_recompressed": lambda im, r: _jpeg(_jpeg(_perspective(_up(im), r, 0.03), 40, 0.8), 25, 0.8),
    "s_faint_pencil": lambda im, r: _jpeg(_faint(_perspective(im, r, 0.03)), 70),
    "s_combined": lambda im, r: _jpeg(_faint(_crease(_shadow(_perspective(_up(im), r), r, True), r)), 35, 0.8),
}


def main() -> int:
    d = data_dir()
    truth = json.loads((d / "truth.json").read_text(encoding="utf-8"))["sheets"]
    clean = [t for t in truth if t["augmentation_condition"] == "clean_scan"][:24]
    per = defaultdict(lambda: [0, 0, 0, 0])
    rng = np.random.default_rng(7)
    times = []
    for rec in clean:
        base = cv2.imdecode(np.fromfile(str(d / rec["image_filename"]), np.uint8), cv2.IMREAD_COLOR)
        for name, fn in CONDITIONS.items():
            img = fn(base, rng)
            t0 = time.perf_counter()
            res = read_sheet(img)
            times.append(time.perf_counter() - t0)
            c = per[name]
            c[2] += 1
            if res.quality.retake:
                c[3] += 1
                c[1] += len(rec["responses"])
                continue
            ok, tot, _ = compare(rec, res)
            c[0] += ok
            c[1] += tot
    print(f"{'condition':26s} sheets  acc     retake")
    for k, (ok, tot, n, rt) in per.items():
        print(f"{k:26s} {n:5d}  {ok / tot:.4f}  {rt}")
    print(f"latency ms median {sorted(times)[len(times) // 2] * 1000:.0f} max {max(times) * 1000:.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
