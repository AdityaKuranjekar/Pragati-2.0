"""Figures, datacards, scaling.json. Run after build_artifacts.py: python ml/build_datacard.py"""
import json
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "ml" / "artifacts"
FIG = OUT / "figures"
FIG.mkdir(exist_ok=True)
SLUG = {"Patna": "patna_jee", "Lucknow": "lucknow_neet", "Gaya": "gaya_both", "Kota": "kota_large"}
C = lambda n, cols=None: pd.read_parquet(DATA / "clean" / f"{n}.parquet", columns=cols)
T = lambda n: pd.read_parquet(DATA / "truth" / f"{n}.parquet")
inst = C("institutes")
inst["slug"] = inst.city.map(SLUG)
stu = C("students")
drop = T("dropout_events")
drop["dropout_date"] = pd.to_datetime(drop.dropout_date)
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})

# 1 marginals vs guide
g = (stu.groupby("institute_id").size().rename("n").to_frame()
     .join(drop.groupby("institute_id").dropped_out.mean().rename("drop")).join(inst.set_index("id").slug))
fig, ax = plt.subplots(1, 2, figsize=(9, 3.2))
ax[0].bar(g.slug, g.n / 3, color="#3B82A0")
ax[0].set_title("Students per cohort-year")
ax[0].tick_params(axis="x", rotation=20)
ax[1].bar(g.slug, g["drop"] * 100, color="#7AA95C")
ax[1].axhspan(8, 15, color="#F2C14E", alpha=.3, label="Guide: 8-15%")
ax[1].set_title("Dropout % (all cohorts)")
ax[1].legend()
ax[1].tick_params(axis="x", rotation=20)
fig.tight_layout()
fig.savefig(FIG / "marginals_vs_guide.png", dpi=130)
plt.close()

# 2 planted ability vs observed share correct (Gaya)
r = C("responses", ["institute_id", "student_id", "question_id", "is_correct", "status"])
gid = inst[inst.slug == "gaya_both"].id.iloc[0]
r = r[(r.institute_id == gid) & (r.status == "answered")]
qt = C("question_topics", ["institute_id", "question_id", "topic_id"])
r = r.merge(qt, on=["institute_id", "question_id"])
r["y"] = r.is_correct.astype(float)
pc = r.groupby(["student_id", "topic_id"]).y.agg(["mean", "count"]).reset_index()
tt = T("true_theta_topic")
tt = tt[tt.institute_id == gid].groupby(["student_id", "topic_id"]).true_theta.mean().reset_index()
m = pc.merge(tt).query("count >= 5")
if len(m) > 1500:
    m = m.sample(1500, random_state=1)
fig, ax = plt.subplots(figsize=(4.2, 3.8))
ax.scatter(m.true_theta, m["mean"], s=5, alpha=.35, color="#3B82A0")
ax.set_xlabel("Planted ability (truth)")
ax.set_ylabel("Share correct (observed)")
ax.set_title(f"Truth vs observed, r={np.corrcoef(m.true_theta, m['mean'])[0, 1]:.2f}")
fig.tight_layout()
fig.savefig(FIG / "truth_vs_recovered.png", dpi=130)
plt.close()

# 3 dropout by month since join
d = drop.merge(stu[["id", "join_date"]], left_on="student_id", right_on="id")
d = d[d.dropped_out]
d["mo"] = (d.dropout_date - pd.to_datetime(d.join_date)).dt.days // 30
vc = d.mo.value_counts().sort_index()
vc = vc[(vc.index >= 0) & (vc.index <= 12)]
fig, ax = plt.subplots(figsize=(5.5, 3.2))
ax.bar(vc.index, vc.values, color="#7AA95C")
ax.set_xlabel("Months since joining")
ax.set_ylabel("Dropouts")
ax.set_title("Dropouts by month since joining")
fig.tight_layout()
fig.savefig(FIG / "dropout_by_month.png", dpi=130)
plt.close()

# 4 attendance heatmap
pid = inst[inst.slug == "patna_jee"].id.iloc[0]
ids = stu[(stu.institute_id == pid) & (stu.academic_year == 2026)].sort_values("roll_no").id.head(60)
a = C("attendance")
a = a[a.student_id.isin(ids)]
a["attendance_date"] = pd.to_datetime(a.attendance_date)
a["present_flag"] = a.present_flag.astype(float)
w = a.groupby(["student_id", pd.Grouper(key="attendance_date", freq="W")]).present_flag.mean().unstack()
fig, ax = plt.subplots(figsize=(7, 3.5))
im = ax.imshow(w.values.astype(float), aspect="auto", cmap="YlGnBu", vmin=0, vmax=1)
ax.set_xlabel("Week")
ax.set_ylabel("Student (by roll no.)")
ax.set_title("Weekly attendance, 60 synthetic students")
fig.colorbar(im, label="share present")
fig.tight_layout()
fig.savefig(FIG / "attendance_heatmap.png", dpi=130)
plt.close()

# 5 moat curve
mo = json.load(open(OUT / "moat.json", encoding="utf-8"))["points"]
fig, ax = plt.subplots(figsize=(4.5, 3.2))
ax.errorbar([p["n_institutes"] for p in mo], [p["calibration_error"] for p in mo],
            yerr=[[p["calibration_error"] - p["ci_low"] for p in mo], [p["ci_high"] - p["calibration_error"] for p in mo]],
            marker="o", color="#3B82A0")
ax.set_xscale("log")
ax.set_xlabel("Institutes pooling item statistics")
ax.set_ylabel("Difficulty error (RMSE, logit)")
ax.set_title("The data moat (simulation)")
fig.tight_layout()
fig.savefig(FIG / "moat_curve.png", dpi=130)
plt.close()

ATTR = [
    ("name, roll_no, batch_id", "students", "Admission register (Excel)", "Identify the student in lists and reports", "all", "administrative"),
    ("dob", "students", "Admission form", "Age routing: minors get academic-only ML (DPDP s.9)", "risk routing", "administrative"),
    ("is_correct, response, status", "responses", "OMR sheets", "Topic mastery heatmap", "irt, mastery", "academic"),
    ("raw_score, subject scores, absent_flag", "test_totals", "Test result Excel", "Score trend, percentile band, early warning", "risk, percentile", "academic"),
    ("topic_id per question", "question_topics", "Teacher tagging", "Maps answers to the 380-topic syllabus", "mastery", "academic"),
    ("a, b, c (item parameters)", "item_params", "Estimated from responses", "Weak-question and wrong-key detection; shared across institutes", "irt, moat", "academic"),
    ("present_flag", "attendance", "Attendance register (Excel or WhatsApp)", "Early warning; the institute's 75% rule is the baseline", "risk (18+ full track)", "behavioural"),
    ("doubts_asked, homework_submitted, app_logins", "engagement", "App or WhatsApp activity", "Engagement signal for adults only", "risk (18+ only)", "behavioural"),
    ("instalment due and paid dates", "fees", "Fee ledger", "Fee delay reason; supportive counsellor action", "risk (rules for minors)", "administrative"),
    ("guardian lang_pref, phone", "guardians", "Admission form", "WhatsApp report language and delivery", "reports", "administrative"),
    ("consents (purpose, verified_at)", "consents", "In-person ID check plus OTP", "Consent gate before any parent message or ML track", "routing", "administrative"),
    ("dropout date and reason, true ability, true percentile", "truth tables", "Generator only (never in production)", "Ground truth to measure the models", "evaluation only", "synthetic truth"),
]
CHECK = [
    ("Annual dropout rate", "about 18% (12-25% range)", "Guide 8-15%; research R4 15-25%", "medium"),
    ("Dropout peak", "months 4-5", "Research R4 (Aug-Sep)", "medium"),
    ("Sudden (unpredictable) dropouts", "25% of dropouts", "Assumption", "assumption"),
    ("Students per year, per institute", "200 / 450 / 600 / 2,200", "Guide: about 400 typical", "medium"),
    ("Tests", "chapter test weekly, full mock every 14 days", "Guide 2-4 tests a month; inferred", "medium"),
    ("Fees", "INR 60k-150k a year, 35% upfront, instalments", "Research R4 range", "medium"),
    ("Attendance base rate", "0.82 with festival and board-exam dips", "Inferred", "medium"),
    ("Item difficulty, discrimination, guessing", "normal b, lognormal a, beta guess", "Standard IRT practice", "assumption"),
    ("Weekly off, no test the day after", "enforced", "MoE 2024 guidelines", "high"),
    ("Minimum age at enrolment", "16", "MoE 2024 guidelines", "high"),
]
STORY = [
    "Institute and batch settings: city tier, size, exam focus, mentor capacity",
    "Each student gets a latent ability, per topic, from a shared base plus topic offsets",
    "Each question gets difficulty, discrimination and guessing",
    "Responses depend on ability, difficulty, guessing, negative marking and optional blanks",
    "Engagement drives attendance and doubts; household fee stress drives instalment delays",
    "Dropout hazard depends on score trend, engagement, fee delay and shocks; 25% are sudden",
    "Final percentile comes from latent ability plus noise and exam-shift difficulty",
    "Messy exports (typos, merged cells, missing rows) are created and cleaned by a reference parser",
]
LIMITS = [
    "It shows that the pipeline works and that methods recover the truth we planted. It does not show that real institutes behave this way.",
    "Parameters such as dropout peaks, sudden-dropout share and fee behaviour are assumptions or inferred; each is tagged with confidence.",
    "No real student data was used. Results on real institutes can differ; a pilot is the test.",
    "Public-data checks (OULAD, ASSISTments) are separate and are reported as public, not synthetic.",
]
FIGS = [
    ("figures/marginals_vs_guide.png", "Cohort sizes and dropout vs the guide's 8-15% band"),
    ("figures/truth_vs_recovered.png", "Planted ability vs what the data shows"),
    ("figures/dropout_by_month.png", "When students leave"),
    ("figures/attendance_heatmap.png", "Attendance pattern for 60 students"),
    ("figures/moat_curve.png", "Pooling item statistics lowers difficulty error"),
]
for _, I in inst.iterrows():
    gen = json.load(open(OUT / I.slug / "owner.json", encoding="utf-8"))["generated_at"]
    card = {"schema": "datacard/1", "model_version": "v1.1.0", "generated_at": gen, "generator_seed": 42,
            "institute_id": I.slug, "origin": "synthetic",
            "story_steps": [{"id": i + 1, "title": t.split(":")[0], "text": t} for i, t in enumerate(STORY)],
            "attributes": [dict(zip(["name", "entity", "real_world_source", "decision", "model", "privacy_class"], x)) for x in ATTR],
            "checklist": [dict(zip(["parameter", "our_value", "source", "confidence"], x)) for x in CHECK],
            "figures": [{"path": p, "caption": c, "origin": "synthetic"} for p, c in FIGS],
            "cleaning": {"rate": None, "examples": [{"raw": "Aarva Kumar", "clean": "Aarav Kumar"}, {"raw": "RAHUL  singh", "clean": "Rahul Singh"}],
                         "note": "Illustrative examples only; measured cleaning rate was not computed in this build"},
            "limits": LIMITS}
    (OUT / I.slug / "datacard.json").write_text(json.dumps(card, ensure_ascii=False, indent=1), encoding="utf-8")

scal = {"schema": "scaling/1", "origin": "assumption",
        "stages": [{"name": "Pilot", "students": "up to 1,000", "stack": "One laptop or VM, local models, PostgreSQL"},
                   {"name": "Seed", "students": "1,000-10,000", "stack": "Managed PostgreSQL with row-level security, object store, job queue, one region"},
                   {"name": "Scale", "students": "10,000-100,000+", "stack": "Stateless API replicas, autoscaled workers, read replicas, per-tenant keys, nightly retrain"}],
        "cost_per_student": [
            {"students": 1000, "inr": 3.6, "lines": {"compute": 1.0, "whatsapp": 1.4, "storage": 0.2, "ai_reports": 0.6, "support": 0.4}},
            {"students": 10000, "inr": 2.6, "lines": {"compute": 0.5, "whatsapp": 1.4, "storage": 0.15, "ai_reports": 0.4, "support": 0.15}},
            {"students": 100000, "inr": 2.2, "lines": {"compute": 0.3, "whatsapp": 1.4, "storage": 0.1, "ai_reports": 0.3, "support": 0.1}}],
        "cost_note": "The 1,000-student point is the finance model's INR 3.6. The 10k and 100k points are projections by line item (fixed lines shrink, WhatsApp does not). WhatsApp price per message is unverified.",
        "failure_modes": [
            {"case": "No internet", "response": "Phone app queues scans and attendance, syncs later"},
            {"case": "Bad scan", "response": "Quality check asks for a retake; manual entry fallback"},
            {"case": "Wrong answer key", "response": "Flagged by item statistics; teacher confirms"},
            {"case": "Too little data", "response": "Shows 'not enough data', never a number"},
            {"case": "Local AI model down", "response": "Verified template report is sent instead"}]}
(OUT / "scaling.json").write_text(json.dumps(scal, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok")
