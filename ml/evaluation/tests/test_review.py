"""E4 and E6 [SIM]: sheets carry no truth, no policy label and no rater entry; the sheet generator never reads a key;
keys point at real frontier concepts; rater columns are blank."""
import ast
import builtins
import csv
import json
from pathlib import Path

import pytest

from ml.evaluation.review import cases as cs
from ml.evaluation.review import keys as ks
from ml.evaluation.review import sheets as sh

REVIEW = Path(__file__).resolve().parents[1] / "review"
ROOT = Path(__file__).resolve().parents[3]


def _imports(path: Path) -> set[str]:
    out = set()
    for n in ast.walk(ast.parse(path.read_text())):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            out.add(("." * n.level) + (n.module or ""))
    return out


def test_sheet_generator_does_not_import_keys_or_the_engine_or_the_simulator():
    mods = _imports(REVIEW / "sheets.py")
    for m in mods:
        assert "keys" not in m and "intelligence" not in m and "backend" not in m and "sim" not in m and not m.startswith("app"), m
    tree = ast.parse((REVIEW / "sheets.py").read_text())
    body = tree.body[1:]                                    # skip the module docstring
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert "key" not in node.value.lower(), node.value


def test_sheet_generator_never_opens_the_key_files(monkeypatch, tmp_path):
    """Runs the sheet writers with every open() of a key path forbidden. They must still succeed."""
    real_open = builtins.open

    def guarded(file, *a, **k):
        if "key" in str(file):
            raise AssertionError(f"sheet generator opened {file}")
        return real_open(file, *a, **k)

    monkeypatch.setattr(builtins, "open", guarded)
    e4 = [cs.visible_view(c) for c in cs.e4_cases(per_course=3)]
    out = tmp_path / "e4_check.csv"
    assert sh.export_e4(e4, out) == len(e4)
    assert len(list(csv.DictReader(out.open()))) == len(e4)


def test_visible_view_carries_no_truth():
    c = cs.e4_cases(per_course=2)[0]
    v = cs.visible_view(c)
    assert set(v) == {"case_id", "concepts", "prereqs", "goal", "correct", "attempts"}
    flat = json.dumps(v, default=str)
    assert '"m"' not in flat and "truth" not in flat and "seq" not in flat


@pytest.mark.parametrize("name", ["e4_root_cause_sheet.csv", "e6_relevance_sheet.csv"])
def test_committed_sheets_have_blank_rater_columns(name):
    rows = list(csv.DictReader((REVIEW / name).open(encoding="utf-8")))
    assert rows
    for r in rows:
        for col, val in r.items():
            if col.startswith(("Rater_", "Teacher_", "Adjudicator")):
                assert val == "", (col, val)


def test_committed_sheets_carry_no_truth_or_policy_label():
    e4_head = (REVIEW / "e4_root_cause_sheet.csv").read_text(encoding="utf-8").splitlines()[0].lower()
    assert "truth" not in e4_head and "policy" not in e4_head and "m_" not in e4_head
    e6_text = (REVIEW / "e6_relevance_sheet.csv").read_text(encoding="utf-8").lower()
    for label in ("adaptive", "fixed", "random", "policy", "truth"):
        assert label not in e6_text, label


def test_e6_sheet_has_three_slots_and_three_ranks_for_each_profile():
    rows = list(csv.DictReader((REVIEW / "e6_relevance_sheet.csv").open(encoding="utf-8")))
    by_profile = {}
    for r in rows:
        by_profile.setdefault(r["profile_id"], []).append(r)
    assert len(by_profile) == 50
    for pid, rs in by_profile.items():
        assert len(rs) == 9
        assert sorted({(r["row_id"].split("-")[-2], r["rank"]) for r in rs}) == sorted(
            (s, str(k)) for s in "ABC" for k in (1, 2, 3))


def test_e4_key_points_at_a_real_frontier_concept():
    cases = cs.e4_cases()
    key = ks.e4_key(cases)
    assert len(key) == 40
    for c in cases:
        root = key[c.case_id]["root_cause"]
        assert not c.M[root]
        assert all(c.M[p] for p in c.prereqs[root])
        assert root in (ks.ancestors(c.prereqs, c.goal) | {c.goal})
        assert not c.M[c.goal]


def test_keys_directory_is_git_ignored():
    import subprocess
    out = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "ml/evaluation/review/keys/e4_key.json"],
                         capture_output=True, text=True)
    assert out.stdout.strip() == "ml/evaluation/review/keys/e4_key.json"


def test_manifest_matches_the_committed_sheets():
    import hashlib
    man = json.loads((REVIEW / "manifest.json").read_text())
    for name, digest in man["sheet_sha256"].items():
        assert hashlib.sha256((REVIEW / name).read_bytes()).hexdigest() == digest
    assert man["e4"]["cases"] == 40 and man["e6"]["rows"] == 450 and man["e6"]["profiles"] == 50
