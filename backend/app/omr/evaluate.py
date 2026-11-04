"""Measure bubble accuracy per imaging condition on the synthetic set.

Run: python -m app.omr.evaluate   (from backend; OMR_DATA_DIR overrides the data folder)
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

from .reader import read_sheet

DEFAULT_DIR = Path(__file__).resolve().parents[3] / "data" / "omr" / "synthetic"  # repo root / data


def data_dir() -> Path:
    return Path(os.environ.get("OMR_DATA_DIR", DEFAULT_DIR))


def compare(rec: dict, res) -> tuple[int, int, list[str]]:
    """Return (correct_questions, total_questions, error strings). Unit = question (bubble row)."""
    ok, tot, errs, flagged = 0, 0, [], set()
    for qn, t in rec["responses"].items():
        tot += 1
        r = res.questions.get(int(qn))
        if r is None:
            errs.append(f"q{qn}: missing")
            continue
        if t["status"] == "answered":
            good = r.status == "answered" and r.answer == t["marked"]
        elif t["status"] == "multi_marked":
            good = r.status == "multi_marked"
        else:
            good = r.status == t["status"]
        ok += good
        if not good:
            flagged.add(int(qn)) if any(u.question_no == int(qn) for u in res.uncertain) else None
            errs.append(f"q{qn}: truth={t['marked']}/{t['status']} got={r.answer}/{r.status} fills={r.fills}")
    compare.silent_errors += len(errs) - len(flagged)
    compare.flagged_errors += len(flagged)
    return ok, tot, errs


compare.silent_errors = 0
compare.flagged_errors = 0


def main() -> int:
    d = data_dir()
    truth = json.loads((d / "truth.json").read_text(encoding="utf-8"))["sheets"]
    per = defaultdict(lambda: [0, 0, 0, 0, 0])  # ok, total, sheets, roll_ok, retake
    times, shown = [], 0
    for rec in truth:
        t0 = time.perf_counter()
        res = read_sheet(d / rec["image_filename"])
        times.append(time.perf_counter() - t0)
        c = per[rec["augmentation_condition"]]
        c[2] += 1
        if res.quality.retake:
            c[4] += 1
            c[1] += len(rec["responses"])
            print("RETAKE", rec["image_filename"], res.quality.reason)
            continue
        ok, tot, errs = compare(rec, res)
        c[0] += ok
        c[1] += tot
        c[3] += res.roll_no == rec["roll_no"]
        if "-v" in sys.argv and errs and shown < 40:
            shown += 1
            print(rec["image_filename"], rec["augmentation_condition"], errs[:4])
    print(f"{'condition':26s} sheets  acc     roll_ok retake")
    to = tt = 0
    for k, (ok, tot, n, rl, rt) in per.items():
        print(f"{k:26s} {n:5d}  {ok / tot:.4f}  {rl}/{n}    {rt}")
        to += ok
        tt += tot
    print(f"{'OVERALL':26s} {sum(v[2] for v in per.values()):5d}  {to / tt:.4f}")
    print(f"wrong rows: {compare.flagged_errors} flagged for review, {compare.silent_errors} silent")
    times.sort()
    print(f"latency ms: median {times[len(times) // 2] * 1000:.0f}  p95 {times[int(len(times) * .95)] * 1000:.0f}  max {times[-1] * 1000:.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
