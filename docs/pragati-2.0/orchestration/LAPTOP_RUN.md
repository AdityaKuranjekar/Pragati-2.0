# Laptop run: E1 (ASSISTments) and E2 (OULAD)

**Status:** instructions only. Nothing in this file has been run by the build agent: there is no public data in the build environment. Both pre-registrations are in `ml/evaluation/PREREGISTRATION.md` (sections "E1" and "E2"). Read them first.

**Rules for this run**
- Do **not** commit anything from `data/`. It is git-ignored. Do not send the data back.
- Do **not** run `python -m ml.public_validation.evaluate` in the main checkout. It writes into `ml/public_validation/artifacts/v1.0.0/`, the committed 1.0 results, and would overwrite them. The steps below use a separate git worktree.
- **Check the licence before each download** (`CLAUDE.md` §3). ASSISTments is marked "research use only" by the download script. Its licence status is still open under R2. If you have not cleared it, stop before step 2.
- Do not change any code in `ml/public_validation/`. If a step fails, send the traceback and stop.

## 0. Preconditions
- Python 3.11 or newer, git, and about 2 GB of free disk for the data and the venv.
- The commit to run: the **`claude/s5-evidence` HEAD named in `docs/pragati-2.0/orchestration/S5_LOG.md`** (after it is pushed). Use that commit, not a later one.

## 1. Separate worktree and environment
```bash
cd ~/Pragati-2.0                                   # your main checkout
git fetch origin claude/s5-evidence
git worktree add ~/pragati-e1-e2 <commit-from-S5_LOG>
cd ~/pragati-e1-e2
python3 -m venv ml/public_validation/.venv
ml/public_validation/.venv/bin/pip install -r ml/public_validation/requirements.txt
mkdir -p ~/pragati_e1e2_out
git rev-parse HEAD | tee ~/pragati_e1e2_out/commit.txt
```
On Windows PowerShell, use `.\ml\public_validation\.venv\Scripts\pip` and `.\ml\public_validation\.venv\Scripts\python` for the same commands.

## 2. Download and verify (about 130 MB)
```bash
ml/public_validation/.venv/bin/python scripts/download_public_data.py
ls -la data/public/assistments2009/skill_builder_data.csv data/public/oulad
```
The script verifies MD5 and SHA-256 and writes `data/public/README.txt`. **Copy the SHA-256 lines from `data/public/README.txt` into `~/pragati_e1e2_out/digests.txt`.** Do not send the data. If the ASSISTments CSV is not at the path above, stop and send the directory listing.

## 3. E1: ASSISTments next-response (pre-registered: pyKT split, seed 1024)
```bash
ml/public_validation/.venv/bin/python -c "
import json, pathlib
from ml.public_validation.assistments import evaluate_assistments_pykt
res = evaluate_assistments_pykt(pathlib.Path('data/public/assistments2009/skill_builder_data.csv'), n_bootstrap=500, seed=42)
out = pathlib.Path.home() / 'pragati_e1e2_out' / 'e1_assistments_raw.json'
out.write_text(json.dumps(res, indent=2, default=str))
print('models:', sorted(res['models']))
print('wrote', out)
"
```
Expected: a console line listing `irt_online_eap`, `rasch_1pl_global`, `bkt_em`, `logistic_baseline`, then the file.

Primary row for the pass bar: `rasch_1pl_global` minus `logistic_baseline`, with a student-level bootstrap CI for the difference. **The build agent has not checked what this function writes.** Check the file for a per-model CI and for a paired difference. If the paired difference is not in the file, send the file back anyway. Without it the E1 pass bar cannot be judged, and the evaluation page will show E1 as not computed for the paired row.

## 4. E2: OULAD day-28 retention (pre-registered: student-grouped CV, seed 42)
```bash
ml/public_validation/.venv/bin/python -c "
import json, pathlib, dataclasses
from ml.public_validation.oulad import run_oulad_suite
res = run_oulad_suite(pathlib.Path('data/public/oulad'), cutoffs=(14, 28, 42, 60), n_bootstrap=500, seed=42)
out = pathlib.Path.home() / 'pragati_e1e2_out' / 'e2_oulad_raw.json'
out.write_text(json.dumps({str(d): dataclasses.asdict(r) for d, r in res.items()}, indent=2, default=str))
print('day-28 models:', sorted(res[28].models))
print('wrote', out)
"
```
Expected: about 3 to 4 minutes on a laptop. The console lists the day-28 models, including `lgbm_academic_only_student_cv`, `lgbm_acad_behav_student_cv`, `logreg_*`, `rule_no_assessment` and `rule_zero_vle_7d` (the names may differ slightly; send the list).

**Read the academic-only row.** The pipeline's own headline (`evaluate.py`) uses `lgbm_acad_behav_student_cv`, which includes VLE clicks. VLE clicks are behavioural tracking and not usable for minors (DPDP s.9(3)). The pre-registered row is `lgbm_academic_only_student_cv`.

## 5. Return to the build agent
Send back, and nothing else:
1. `~/pragati_e1e2_out/e1_assistments_raw.json`
2. `~/pragati_e1e2_out/e2_oulad_raw.json`
3. `~/pragati_e1e2_out/commit.txt` and `~/pragati_e1e2_out/digests.txt`
4. `ml/public_validation/.venv/bin/pip freeze > ~/pragati_e1e2_out/pip_freeze.txt`, then send it
5. The console output of steps 2 to 4, including any warnings

Do **not** send `data/`, the venv, or any student-level file. If a step fails, send the traceback and the command you ran.

## 6. Afterwards
Remove the worktree when done (`git worktree remove ~/pragati-e1-e2`). The results are not compared with the registered bars until the build agent has the files, the commit hash, and the digests.

## Known gaps (stated before the run)
- The 1.0 pipeline has no global-mean, per-student-mean or per-item-mean baselines (EVAL_PLAN E1 baselines 1 to 3). They are **not computed**. The evaluation page will show them as not computed.
- ASSISTments is K-12 maths skill-builder data with hints. It cannot show JEE item difficulty, mastery or learning gain.
- The OULAD result is a UK distance-learning task. It does not show any mastery or JEE effect.
