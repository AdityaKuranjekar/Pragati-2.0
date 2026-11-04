"""Offline OMR reader: corner marks -> warp -> QR layout -> bubble read -> quality verdict.

Public API: read_sheet(image, layout_name=None) -> OmrResult, score(...), render_overlay(...).
Only numpy + opencv are required (QR via cv2.QRCodeDetector).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np

PX_PER_MM = 4.0  # canonical warped page scale (matches the synthetic renderer)
MAX_SIDE = 2000  # photos are shrunk to this before analysis

# tunables (calibrated on synthetic sheets, see OMR_README.md)
FILL_MARK = 0.22       # baseline-corrected fill >= this counts as a mark
FILL_FAINT = 0.07      # fill in [FAINT, MARK) is "maybe" -> flagged for review
MULTI_REL = 0.60       # second mark must reach this share of the strongest ...
MULTI_ABS = 0.35       # ... and at least this much absolute fill (erased ghosts stay below)
MIN_SHARP = 25.0       # Laplacian variance of the warped page below this => too blurry
MIN_PAGE_FRAC = 0.30   # fiducial quad must cover this share of the photo


def _contracts_dir() -> Path:
    env = os.environ.get("OMR_CONTRACTS_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3] / "contracts"


@lru_cache(maxsize=None)
def load_layout(name: str) -> dict[str, Any]:
    p = _contracts_dir() / "omr_layouts" / f"{name}.json"
    if not p.exists():
        raise ValueError(f"unknown OMR layout '{name}'")
    return json.loads(p.read_text(encoding="utf-8"))


def available_layouts() -> list[str]:
    return sorted(p.stem for p in (_contracts_dir() / "omr_layouts").glob("*.json"))


@dataclass
class CellRead:
    question_no: int
    label: str
    fill: float          # 0 (paper) .. 1 (solid ink)
    marked: bool


@dataclass
class QuestionRead:
    question_no: int
    q_type: str
    answer: str | None          # "B", "37", "A|C" for multi, None for blank/unreadable
    status: str                 # answered | blank | multi_marked | unreadable
    confidence: float           # 0..1
    marked_options: list[str] = field(default_factory=list)
    fills: dict[str, float] = field(default_factory=dict)


@dataclass
class UncertainCell:
    question_no: int | None     # None => roll number
    label: str
    reason: str                 # faint_mark | double_mark | ambiguous | unreadable | roll_column
    fill: float


@dataclass
class Quality:
    ok: bool
    retake: bool
    reason: str | None
    sharpness: float = 0.0
    page_fraction: float = 0.0
    brightness: float = 0.0
    corners_found: int = 0
    notes: list[str] = field(default_factory=list)


@dataclass
class OmrResult:
    layout_name: str | None
    test_id: str | None
    qr_payload: str | None
    roll_no: str | None
    roll_confidence: float
    questions: dict[int, QuestionRead]
    uncertain: list[UncertainCell]
    quality: Quality
    elapsed_ms: float = 0.0
    warped: np.ndarray | None = field(default=None, repr=False)  # canonical grayscale page, for overlay

    def answers(self) -> dict[int, str | None]:
        return {q: r.answer for q, r in self.questions.items()}

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("warped", None)
        d["questions"] = {str(k): v for k, v in d["questions"].items()}
        return d


# ----------------------------------------------------------------------------- image helpers

def _load_gray_bgr(image: Any) -> np.ndarray:
    if isinstance(image, np.ndarray):
        img = image
    elif isinstance(image, (bytes, bytearray, memoryview)):
        img = cv2.imdecode(np.frombuffer(bytes(image), np.uint8), cv2.IMREAD_COLOR)
    else:
        data = Path(image).read_bytes()  # unicode-safe on Windows
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("could not decode image")
    return img


def _to_gray(img: np.ndarray) -> np.ndarray:
    return img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _order_corners(pts: np.ndarray) -> np.ndarray:
    """tl, tr, br, bl from 4 points."""
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]], np.float32)


def _find_fiducials(gray: np.ndarray) -> list[tuple[float, float]] | None:
    """Return 4 centres (tl,tr,br,bl) of the solid black corner squares, or None.

    Squares clipped by the photo edge are accepted when at least two full squares give the
    square size and rotation: the clipped square's centre is rebuilt from its visible inner vertex.
    """
    h, w = gray.shape
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    bsz = max(31, (min(h, w) // 12) | 1)
    masks = [
        cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, bsz, 25),
        cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1],
        cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, bsz, 10),
    ]
    page_area = h * w
    best: tuple[list, list] = ([], [])
    for m in masks:
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        cnts, _ = cv2.findContours(m, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        full, clipped = [], []
        for c in cnts:
            a = cv2.contourArea(c)
            if a < page_area * 0.0002 or a > page_area * 0.02:
                continue
            x, y, bw, bh = cv2.boundingRect(c)
            hull = cv2.convexHull(c)
            ha = cv2.contourArea(hull)
            if ha <= 0 or a / ha < 0.9:
                continue
            touches = x <= 1 or y <= 1 or x + bw >= w - 1 or y + bh >= h - 1
            if touches:
                clipped.append(hull)
                continue
            if not (0.6 < bw / bh < 1.6):
                continue
            rect = cv2.minAreaRect(c)
            ra = rect[1][0] * rect[1][1]
            if ra <= 0 or a / ra < 0.85:
                continue
            full.append((rect[0][0], rect[0][1], a, rect[1], rect[2]))
        if full:  # drop small look-alikes (QR finder squares, bubbles) relative to the larger blobs
            ref = float(np.percentile([f[2] for f in full], 75))
            full = [f for f in full if f[2] >= 0.5 * ref]
        quads = {(f[0] > w / 2, f[1] > h / 2) for f in full}
        if len(quads) >= 4:
            best = (full, clipped)
            break
        if len(full) > len(best[0]):
            best = (full, clipped)
    full, clipped = best
    if len(full) < 2:
        return None
    med = float(np.median([f[2] for f in full]))
    full = [f for f in full if 0.4 * med < f[2] < 2.5 * med]
    if len(full) < 2:
        return None
    side = float(np.sqrt(med))
    ang = float(np.median([((f[4] + 45) % 90) - 45 for f in full]))
    t = np.deg2rad(ang)
    u = np.array([np.cos(t), np.sin(t)])
    v = np.array([-np.sin(t), np.cos(t)])
    cands = [(np.array([f[0], f[1]], np.float32), False) for f in full]
    centre = np.array([w / 2, h / 2])
    for hull in clipped:
        pts = hull[:, 0, :].astype(np.float64)
        pts = pts[(pts[:, 0] > 1) & (pts[:, 1] > 1) & (pts[:, 0] < w - 2) & (pts[:, 1] < h - 2)]
        if len(pts) == 0 or cv2.contourArea(hull) < 0.2 * med:
            continue
        # outward direction = away from the page centre; inner vertex = the point nearest the centre side
        far = pts[np.argmin(((pts - centre) ** 2).sum(axis=1))]
        away = (hull[:, 0, :].mean(axis=0) - centre)
        a = np.sign(np.dot(u, away)) or 1.0
        b = np.sign(np.dot(v, away)) or 1.0
        cands.append((np.array(far + side / 2 * (a * u + b * v), np.float32), True))
    corners = np.array([[0, 0], [w, 0], [w, h], [0, h]], np.float32)
    chosen = []
    for cx in corners:
        i = int(np.argmin([((c[0] - cx) ** 2).sum() for c in cands]))
        chosen.append(cands[i][0])
    if len({tuple(np.round(p, 1)) for p in chosen}) < 4:
        return None
    quad = _order_corners(np.array(chosen, np.float32))
    return [tuple(map(float, p)) for p in quad]


def _decode_qr(gray: np.ndarray, warped: np.ndarray | None, layout: dict | None) -> str | None:
    det = cv2.QRCodeDetector()
    tries: list[np.ndarray] = []
    if warped is not None:
        # QR box for any layout is in the top right; crop generously from the canonical page
        x0, y0 = int(150 * PX_PER_MM), int(8 * PX_PER_MM)
        crop = warped[y0:int(44 * PX_PER_MM), x0:int(205 * PX_PER_MM)]
        tries.append(crop)
        tries.append(cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC))
        tries.append(cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1])
    tries.append(gray)
    for t in tries:
        for pad in (0, 24):
            tt = cv2.copyMakeBorder(t, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=255) if pad else t
            try:
                txt, _, _ = det.detectAndDecode(tt)
            except cv2.error:
                txt = ""
            if txt:
                return txt
    return None


def _layout_from_qr(payload: str | None, names: list[str]) -> str | None:
    if not payload:
        return None
    low = payload.lower()
    for n in sorted(names, key=len, reverse=True):
        if n.lower() in low:
            return n
    return None


def _px(layout: dict, dx: float, dy: float) -> tuple[float, float]:
    f = layout["fiducials"]["top_left"]
    return (f["x_mm"] + dx) * PX_PER_MM, (f["y_mm"] + dy) * PX_PER_MM


def _flatten(warped: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (paper-normalised 0..1 where 1 = paper, background estimate in grey levels)."""
    # background = local paper level: a max filter wider than any bubble mark (but narrower than a
    # crease or shadow edge) removes ink and keeps lighting; blur smooths JPEG noise.
    k = max(9, int(round(3.6 * PX_PER_MM)) | 1)
    bg = cv2.dilate(cv2.GaussianBlur(warped, (3, 3), 0), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    bg = cv2.GaussianBlur(bg, (0, 0), 3)
    bg = np.maximum(bg.astype(np.float32), 1.0)
    norm = np.clip(warped.astype(np.float32) / bg, 0, 1.2)
    return norm, bg


def _bubble_fill(norm: np.ndarray, cx: float, cy: float, r: float, search: int = 1) -> tuple[float, float, float]:
    """Darkness of the bubble interior. Searches +-search px so small warp errors do not matter.

    Returns (fill, cx, cy). fill = 1 - mean(inner disc) of paper-normalised image.
    """
    h, w = norm.shape
    ri = max(1.8, r * 0.7)
    best = (-1.0, cx, cy)
    for oy in range(-search, search + 1):
        for ox in range(-search, search + 1):
            x, y = cx + ox, cy + oy
            x0, x1 = int(np.floor(x - ri)) - 1, int(np.ceil(x + ri)) + 2
            y0, y1 = int(np.floor(y - ri)) - 1, int(np.ceil(y + ri)) + 2
            if x0 < 0 or y0 < 0 or x1 > w or y1 > h:
                return -1.0, cx, cy
            yy, xx = np.mgrid[y0:y1, x0:x1]
            wgt = np.clip(ri + 0.5 - np.hypot(xx - x, yy - y), 0, 1)
            val = 1.0 - float((norm[y0:y1, x0:x1] * wgt).sum() / wgt.sum())
            if val > best[0]:
                best = (val, x, y)
    return best


def _guess_layout(warped: np.ndarray, names: list[str]) -> str:
    """Pick the layout whose bubble rings best match the page (used when the QR cannot be read)."""
    norm, _ = _flatten(warped)
    best, best_s = names[0], -9.0
    for n in names:
        lay = load_layout(n)
        r = lay["bubble_radius_mm"] * PX_PER_MM
        vals = []
        for qb in lay["question_blocks"][::2]:
            for b in qb["bubbles"]:
                cx, cy = _px(lay, b["dx_mm"], b["dy_mm"])
                f = _bubble_fill(norm, cx, cy, r, search=1)[0]
                # outline ring should be darker than the surrounding paper
                x, y = int(cx), int(cy)
                if 8 <= x < norm.shape[1] - 8 and 8 <= y < norm.shape[0] - 8:
                    ring = norm[y - int(r) - 1:y + int(r) + 2, x - int(r) - 1:x + int(r) + 2].min()
                    vals.append(1.0 - ring)
        sc = float(np.mean(vals)) if vals else -9.0
        if sc > best_s:
            best, best_s = n, sc
    return best


def _sharpness(warped: np.ndarray) -> float:
    return float(cv2.Laplacian(warped, cv2.CV_64F).var())


# ----------------------------------------------------------------------------- main

def read_sheet(image: Any, layout_name: str | None = None, debug: bool = False) -> OmrResult:
    """Read an OMR sheet photo/scan.

    image: path (str/Path), raw bytes (e.g. an upload), or a BGR/gray numpy array.
    layout_name: force a layout; otherwise it is chosen from the QR payload (DM1|<test_id>|<page>)
    and falls back to 'generic_mcq_100'. Never raises on a bad photo: returns quality.retake=True.
    """
    import time
    t0 = time.perf_counter()
    img = _load_gray_bgr(image)
    gray = _to_gray(img)
    h0, w0 = gray.shape
    if max(h0, w0) > MAX_SIDE:
        s = MAX_SIDE / max(h0, w0)
        gray = cv2.resize(gray, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    h, w = gray.shape
    brightness = float(np.median(gray))
    q = Quality(ok=False, retake=True, reason=None, brightness=brightness)

    def fail(reason: str) -> OmrResult:
        q.reason = reason
        return OmrResult(layout_name, None, None, None, 0.0, {}, [], q, (time.perf_counter() - t0) * 1000)

    if brightness < 35:
        return fail("The photo is too dark. Retake with more light.")
    if min(h, w) < 400:
        return fail("The photo resolution is too low. Retake closer to the sheet.")

    quad = _find_fiducials(gray)
    if quad is None:
        return fail("Could not find the four black corner marks. Keep the whole sheet in view, flat, with all four corners visible.")
    q.corners_found = 4
    quad_np = np.array(quad, np.float32)
    q.page_fraction = float(cv2.contourArea(quad_np) / (h * w))
    if q.page_fraction < MIN_PAGE_FRAC:
        return fail("The sheet fills too little of the photo. Move closer.")

    # first pass with a default layout just to get the page geometry (all layouts share A4 + fiducials)
    names = available_layouts()
    ref = load_layout(layout_name or "generic_mcq_100")
    fid = ref["fiducials"]
    dst = np.array(
        [[fid[k]["x_mm"] * PX_PER_MM, fid[k]["y_mm"] * PX_PER_MM] for k in ("top_left", "top_right", "bottom_right", "bottom_left")],
        np.float32,
    )
    W = int(round(ref["page_size_mm"]["width_mm"] * PX_PER_MM))
    H = int(round(ref["page_size_mm"]["height_mm"] * PX_PER_MM))
    M = cv2.getPerspectiveTransform(quad_np, dst)
    warped = cv2.warpPerspective(gray, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=255)

    qr = _decode_qr(gray, warped, ref)
    lname = layout_name or _layout_from_qr(qr, names)
    test_id = None
    if qr and qr.startswith("DM1|"):
        parts = qr.split("|")
        test_id = parts[1] if len(parts) > 1 else None
    if lname is None:
        lname = _guess_layout(warped, names)
        q.notes.append(f"QR not read; layout guessed from bubble grid: {lname}")
    layout = load_layout(lname)
    if lname != (layout_name or "generic_mcq_100") and layout["fiducials"] != ref["fiducials"]:
        # different corner geometry: redo the warp
        fid = layout["fiducials"]
        dst = np.array([[fid[k]["x_mm"] * PX_PER_MM, fid[k]["y_mm"] * PX_PER_MM] for k in ("top_left", "top_right", "bottom_right", "bottom_left")], np.float32)
        M = cv2.getPerspectiveTransform(quad_np, dst)
        warped = cv2.warpPerspective(gray, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=255)

    q.sharpness = _sharpness(warped)
    if q.sharpness < MIN_SHARP:
        q.reason = "The photo is blurry. Hold the phone steady and retake."
        res = OmrResult(lname, test_id, qr, None, 0.0, {}, [], q, (time.perf_counter() - t0) * 1000, warped)
        return res

    norm, bg = _flatten(warped)
    r = layout["bubble_radius_mm"] * PX_PER_MM
    uncertain: list[UncertainCell] = []

    # roll number: one column per digit, the darkest bubble wins
    roll_digits, roll_conf = [], 1.0
    for col in layout["roll_number_grid"]["columns"]:
        fills = []
        for b in col["bubbles"]:
            cx, cy = _px(layout, b["dx_mm"], b["dy_mm"])
            fills.append(_bubble_fill(norm, cx, cy, r)[0])
        fills = [f - float(np.median(fills)) for f in fills]  # remove outline/blur baseline
        order = np.argsort(fills)[::-1]
        f1, f2 = fills[order[0]], fills[order[1]]
        if f1 < FILL_MARK or (f2 >= MULTI_REL * f1 and f2 >= MULTI_ABS):
            roll_digits.append("?")
            roll_conf = min(roll_conf, 0.3)
            uncertain.append(UncertainCell(None, f"digit{col['digit_index']}", "roll_column", float(f1)))
        else:
            roll_digits.append(str(col["bubbles"][int(order[0])]["label"]))
            roll_conf = min(roll_conf, float(min(1.0, (f1 - f2) / max(f1, 1e-6))))
    roll_no = "".join(roll_digits)
    if "?" in roll_no:
        roll_no_out = None
    else:
        roll_no_out = roll_no

    # pass 1: raw darkness of every bubble; pass 2 subtracts the sheet baseline (outline ring + blur
    # leak ~0.1-0.2 into every empty bubble and varies by photo) so thresholds are comparable.
    raw: dict[int, tuple[dict[str, float], bool, float]] = {}
    for qb in layout["question_blocks"]:
        qn = int(qb["question_no"])
        fills: dict[str, float] = {}
        oob = False
        for b in qb["bubbles"]:
            cx, cy = _px(layout, b["dx_mm"], b["dy_mm"])
            f, _, _ = _bubble_fill(norm, cx, cy, r)
            if f < 0:
                oob = True
                f = 0.0
            fills[b["label"]] = float(f)
        cy0 = _px(layout, qb["bubbles"][0]["dx_mm"], qb["bubbles"][0]["dy_mm"])
        bgl = float(bg[int(min(max(cy0[1], 0), H - 1)), int(min(max(cy0[0], 0), W - 1))])
        raw[qn] = (fills, oob, bgl)
    allv = [f for fl, oob, _ in raw.values() if not oob for f in fl.values()]
    base = float(np.median(allv)) if allv else 0.0
    q.notes.append(f"baseline={base:.3f}")

    questions: dict[int, QuestionRead] = {}
    for qb in layout["question_blocks"]:
        qn = int(qb["question_no"])
        fills, oob, bgl = raw[qn]
        fills = {k: round((v - base) / (1 - base), 3) for k, v in fills.items()}
        if oob or bgl < 40:
            questions[qn] = QuestionRead(qn, qb["q_type"], None, "unreadable", 0.0, [], fills)
            uncertain.append(UncertainCell(qn, "*", "unreadable", 0.0))
            continue

        if qb["q_type"] == "numeric":
            questions[qn] = _read_numeric(qb, fills, uncertain)
            continue

        # local lighting (crease, shadow edge) lifts every bubble of a row: remove the row minimum
        lo = min(fills.values())
        if lo > 0.08:
            fills = {k: round(v - lo, 3) for k, v in fills.items()}
        order = sorted(fills.items(), key=lambda kv: -kv[1])
        (l1, f1), (l2, f2) = order[0], order[1]
        marked = [l for l, f in fills.items() if f >= FILL_MARK and (l == l1 or (f >= MULTI_ABS and f >= MULTI_REL * f1))]
        if f1 < FILL_MARK:
            status, ans, conf, mo = "blank", None, 1.0 - f1 / FILL_MARK, []
            if f1 >= FILL_FAINT:
                conf = 0.4
                uncertain.append(UncertainCell(qn, l1, "faint_mark", f1))
        elif len(marked) >= 2:
            status, ans, mo = "multi_marked", "|".join(sorted(marked)), sorted(marked)
            conf = float(min(1.0, min(fills[m] for m in marked)))
            uncertain.append(UncertainCell(qn, "|".join(sorted(marked)), "double_mark", f2))
        else:
            status, ans, mo = "answered", l1, [l1]
            conf = float(min(1.0, (f1 - f2) / max(f1, 1e-6)))
            if f1 < 0.45 or (f2 >= 0.5 * f1 and f2 >= FILL_FAINT * 1.6):
                uncertain.append(UncertainCell(qn, l1, "ambiguous", f1))
                conf = min(conf, 0.5)
        questions[qn] = QuestionRead(qn, qb["q_type"], ans, status, round(conf, 3), mo, fills)

    n_unread = sum(1 for v in questions.values() if v.status == "unreadable")
    q.ok = True
    q.retake = False
    if n_unread > 0.2 * max(1, len(questions)):
        q.ok, q.retake = False, True
        q.reason = "Too many questions are unreadable (part of the sheet is cut off or too dark). Retake."
    elif uncertain:
        q.notes.append(f"{len(uncertain)} cells need a one-tap review")
    return OmrResult(
        lname, test_id, qr, roll_no_out, round(roll_conf, 3), questions, uncertain, q,
        (time.perf_counter() - t0) * 1000, warped,
    )


def _read_numeric(qb: dict, fills: dict[str, float], uncertain: list[UncertainCell]) -> QuestionRead:
    qn = int(qb["question_no"])
    cols: dict[int, dict[str, float]] = {}
    for lab, f in fills.items():
        if lab.startswith("D") and "_" in lab and lab[1].isdigit():
            ci, dv = lab[1:].split("_")
            cols.setdefault(int(ci), {})[dv] = f
    for ci, cf in cols.items():  # a crease/shadow lifts a whole digit column: remove its median
        med = float(np.median(list(cf.values())))
        if med > 0.08:
            for dv in cf:
                cf[dv] = round(cf[dv] - med, 3)
                fills[f"D{ci}_{dv}"] = cf[dv]
    digits, conf, bad = [], 1.0, False
    for ci in sorted(cols):
        order = sorted(cols[ci].items(), key=lambda kv: -kv[1])
        (d1, f1), (_, f2) = order[0], order[1]
        if f1 < FILL_MARK:
            continue  # empty column (unused digit)
        if f2 >= MULTI_REL * f1 and f2 >= MULTI_ABS:
            bad = True
            uncertain.append(UncertainCell(qn, f"D{ci}", "double_mark", f2))
            continue
        digits.append(d1)
        conf = min(conf, (f1 - f2) / max(f1, 1e-6))
        if f1 < 0.45:
            uncertain.append(UncertainCell(qn, f"D{ci}_{d1}", "ambiguous", f1))
    if bad:
        return QuestionRead(qn, "numeric", None, "multi_marked", 0.0, [], fills)
    if not digits:
        return QuestionRead(qn, "numeric", None, "blank", 0.9, [], fills)
    sign = "-" if fills.get("SIGN_MINUS", 0) >= FILL_MARK and fills.get("SIGN_MINUS", 0) > fills.get("SIGN_PLUS", 0) else ""
    return QuestionRead(qn, "numeric", sign + "".join(digits), "answered", round(float(conf), 3), [], fills)


# ----------------------------------------------------------------------------- overlay

_COL = {"answered": (0, 160, 0), "blank": (170, 170, 170), "multi_marked": (0, 140, 255), "unreadable": (0, 0, 220)}


def render_overlay(result: OmrResult, scale: float = 1.0) -> np.ndarray | None:
    """BGR debug image of the flattened page: detected marks green, double orange, uncertain red ring.

    Returns None if the page could not be warped (retake verdict before warp)."""
    if result.warped is None or result.layout_name is None:
        return None
    layout = load_layout(result.layout_name)
    vis = cv2.cvtColor(result.warped, cv2.COLOR_GRAY2BGR)
    r = int(round(layout["bubble_radius_mm"] * PX_PER_MM)) + 3
    bad = {(u.question_no, u.label) for u in result.uncertain}
    bad_q = {u.question_no for u in result.uncertain}
    for qb in layout["question_blocks"]:
        qn = int(qb["question_no"])
        qr = result.questions.get(qn)
        if qr is None:
            continue
        for b in qb["bubbles"]:
            cx, cy = _px(layout, b["dx_mm"], b["dy_mm"])
            is_marked = b["label"] in qr.marked_options or (qr.q_type == "numeric" and qr.fills.get(b["label"], 0) >= FILL_MARK)
            if is_marked:
                cv2.circle(vis, (int(cx), int(cy)), r, _COL[qr.status], 2, cv2.LINE_AA)
        if qn in bad_q:
            x, y = _px(layout, qb["bubbles"][0]["dx_mm"] - 4, qb["bubbles"][0]["dy_mm"])
            cv2.circle(vis, (int(x), int(y)), 4, (0, 0, 255), -1, cv2.LINE_AA)
    txt = f"{result.layout_name} roll={result.roll_no} uncertain={len(result.uncertain)}"
    cv2.putText(vis, txt, (20, vis.shape[0] - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 0, 0), 2, cv2.LINE_AA)
    if scale != 1.0:
        vis = cv2.resize(vis, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return vis
