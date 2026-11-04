// In-memory stand-in for the FastAPI server (server side only). Same paths and JSON bodies the real
// server will serve under /api/v1. It reads the ML artifacts for data and keeps edits in memory,
// so a dev-server restart resets every edit and every token. Rules marked MOCK are simulations,
// not the model: the real server recomputes with the saved models.
import fs from "node:fs/promises";
import { findArtifact } from "../server-data";
import { guessMapping, KINDS, ONE_OF, parseCsv, TARGETS, type ColumnGuess, type Kind } from "./csv";

type Role = "owner" | "teacher" | "mentor" | "student" | "parent";
type User = { id: string; role: Role; name: string; institute_id: string; student_id: string | null };
type J = Record<string, any>;
export type MockReq = { method: string; path: string[]; search: URLSearchParams; token: string | null; json?: J; form?: FormData };
export type MockRes = { status: number; body: unknown };

const INSTITUTES = ["patna_jee", "gaya_both", "kota_large", "lucknow_neet"];
const ROLES: Role[] = ["owner", "teacher", "mentor", "student", "parent"];
const ACADEMIC = new Set(["score3", "score_delta", "n_tests"]);

type Job = {
  id: string; kind: Kind; filename: string; institute: string; headers: string[]; rows: string[][];
  mapping: ColumnGuess[]; committedAt: number | null; applied: number; error?: string;
};
type OmrJob = { id: string; institute: string; filename: string; result: J; corrections: Record<string, string>; done: boolean };
type Consent = { consent_id: string; student_id: string; roll_no: string; guardian_display: string; kind: "parental" | "self"; method: string; date: string; status: "active" | "withdrawn" };

type Store = {
  tokens: Map<string, User>;
  attendance: Map<string, number>; // student_id -> percent (edits and uploads)
  fixedKeys: Map<string, { key: string; at: string }>;
  jobs: Map<string, Job>;
  omr: Map<string, OmrJob>;
  consents: Map<string, Consent[]>; // institute -> ledger
  tier: Map<string, "full" | "academic_only">;
  rolls: Map<string, Map<string, string>>; // institute -> roll_no -> student_id (students uploaded this session)
  seq: number;
};
const g = globalThis as unknown as { __pragati_mock?: Store };
const S: Store = (g.__pragati_mock ??= { tokens: new Map(), attendance: new Map(), fixedKeys: new Map(), jobs: new Map(), omr: new Map(), consents: new Map(), tier: new Map(), rolls: new Map(), seq: 1 });

const ok = (body: unknown, status = 200): MockRes => ({ status, body });
const fail = (status: number, detail: string): MockRes => ({ status, body: { detail } });
const invalid = (field: string, msg: string): MockRes => ({ status: 422, body: { detail: [{ loc: ["body", field], msg }] } });
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const id = (p: string) => `${p}_${(S.seq++).toString(36)}${Math.random().toString(36).slice(2, 6)}`;
const hash = (s: string) => {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return h >>> 0;
};
const rng = (seed: number) => () => ((seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) / 2 ** 32);

const cache = new Map<string, J>();
async function art(institute: string | null, file: string): Promise<J | null> {
  const p = await findArtifact(institute, file);
  if (!p) return null;
  const hit = cache.get(p);
  if (hit) return structuredClone(hit);
  const j = JSON.parse(await fs.readFile(p, "utf8")) as J;
  cache.set(p, j);
  return structuredClone(j);
}

/** Attendance on file. MOCK: a stable made-up figure 55..98 until someone edits it. */
const baseAttendance = (sid: string) => 55 + (hash(sid) % 44);
const attendanceOf = (sid: string) => S.attendance.get(sid) ?? baseAttendance(sid);

async function students(inst: string): Promise<J[]> {
  return ((await art(inst, "student"))?.students as J[]) ?? [];
}
async function rollIndex(inst: string): Promise<Map<string, string>> {
  const m = new Map<string, string>();
  for (const s of await students(inst)) m.set(String(s.roll_no).toLowerCase(), s.student_id);
  S.rolls.get(inst)?.forEach((v, k) => m.set(k, v));
  return m;
}

// ---- consents -----------------------------------------------------------------------------------
async function ledger(inst: string): Promise<Consent[]> {
  let l = S.consents.get(inst);
  if (!l) {
    const parents = ((await art(inst, "parent"))?.parents as J[]) ?? [];
    const st = await students(inst);
    const roll = new Map(st.map((s) => [s.student_id, s.roll_no]));
    l = parents.map((p, i) => ({
      consent_id: `c_${inst}_${i + 1}`,
      student_id: p.student_id,
      roll_no: roll.get(p.student_id) ?? "",
      guardian_display: p.guardian_display,
      kind: "parental" as const,
      method: p.consent?.method ?? "in_person_id_check",
      date: p.consent?.date ?? "2026-04-24",
      status: p.consent?.verified === false ? ("withdrawn" as const) : ("active" as const),
    }));
    S.consents.set(inst, l);
  }
  return l;
}
const withdrawn = async (inst: string) => new Set((await ledger(inst)).filter((c) => c.status === "withdrawn").map((c) => c.student_id));

// ---- support list (MOCK recompute) -------------------------------------------------------------
async function supportList(inst: string): Promise<J | null> {
  const r = await art(inst, "risk");
  if (!r) return null;
  const gone = await withdrawn(inst);
  const academicOnly = (S.tier.get(inst) ?? "full") === "academic_only";
  const rows: J[] = [];
  for (const row of r.list as J[]) {
    if (gone.has(row.student_id)) continue;
    const att = S.attendance.get(row.student_id);
    let reasons = [...row.reasons];
    let track = row.track as string;
    if (track === "full" && academicOnly) {
      track = "academic_support";
      reasons = reasons.filter((x) => ACADEMIC.has(x.code));
    }
    if (track === "full" && att !== undefined) {
      if (att >= 85) reasons = reasons.filter((x) => !String(x.code).startsWith("att"));
      else if (att < 75 && !reasons.some((x) => String(x.code).startsWith("att")))
        reasons.unshift({ code: "att30", text_en: `Attendance is ${att}%, under the 75% line`, text_hi: `उपस्थिति ${att}% है, 75% से कम`, weight: 1.5 });
    }
    if (reasons.length === 0) continue;
    rows.push({ ...row, track, reasons, attendance_pct: attendanceOf(row.student_id) });
  }
  // adults whose edited attendance fell under 75 join the list (MOCK rule; students under 18 never do)
  const known = new Set(rows.map((x) => x.student_id));
  for (const [sid, att] of S.attendance) {
    if (known.has(sid) || gone.has(sid) || att >= 75 || academicOnly) continue;
    const orig = (r.list as J[]).find((x) => x.student_id === sid);
    if (!orig || orig.track !== "full") continue;
    rows.push({ ...orig, reasons: [{ code: "att30", text_en: `Attendance is ${att}%, under the 75% line`, text_hi: `उपस्थिति ${att}% है, 75% से कम`, weight: 1.5 }], attendance_pct: att });
  }
  const cap = r.capacity_per_week as number;
  rows.sort((a, b) => a.priority_slot - b.priority_slot);
  r.list = rows.slice(0, cap).map((x, i) => ({ ...x, priority_slot: i + 1 }));
  r.recompute = { simulated: true, tier: S.tier.get(inst) ?? "full", attendance_edits: S.attendance.size };
  return r;
}

// ---- artifact reads with role scoping --------------------------------------------------------------
const STUDENT_FILES = new Set(["student", "percentile", "reports", "parent"]);
const OWNER_ONLY_FILES = new Set(["owner"]);

function scope(body: J, sid: string): J {
  for (const k of Object.keys(body)) {
    const v = body[k];
    if (Array.isArray(v) && v.length && typeof v[0] === "object" && v[0] && "student_id" in v[0]) body[k] = v.filter((x: J) => x.student_id === sid);
  }
  return body;
}

async function readFile(u: User, inst: string, file: string): Promise<MockRes> {
  const global = inst === "global";
  if (!global && inst !== u.institute_id) return fail(403, "That institute belongs to another tenant");
  if ((u.role === "student" || u.role === "parent") && (global || !STUDENT_FILES.has(file))) return fail(403, `The ${u.role} role cannot read ${file}`);
  if (u.role === "student" && file === "parent") return fail(403, "The student role cannot read parent");
  if (u.role !== "owner" && OWNER_ONLY_FILES.has(file)) return fail(403, `Only the owner can read ${file}`);
  let body = file === "risk" && !global ? await supportList(inst) : await art(global ? null : inst, file);
  if (!body) return fail(404, `No data for ${file}`);
  if ((u.role === "student" || u.role === "parent") && u.student_id) body = scope(body, u.student_id);
  if (file === "reports" && !global) {
    const gone = await withdrawn(inst);
    body.reports = (body.reports as J[]).filter((r) => !gone.has(r.student_id));
  }
  return ok(body);
}

// ---- auth -----------------------------------------------------------------------------------------
async function login(json: J | undefined): Promise<MockRes> {
  const role = json?.role as Role;
  const inst = (json?.institute_id as string) ?? "patna_jee";
  if (!ROLES.includes(role)) return invalid("role", "Unknown role");
  if (!INSTITUTES.includes(inst)) return invalid("institute_id", "Unknown institute");
  let sid: string | null = null;
  let name = { owner: "Institute owner", teacher: "Teacher (demo)", mentor: "Mentor (demo)", student: "", parent: "" }[role];
  if (role === "student" || role === "parent") {
    const first = [...(await students(inst))].sort((a, b) => String(a.roll_no).localeCompare(String(b.roll_no)))[0];
    if (!first) return fail(403, "No students are loaded for that institute");
    sid = first.student_id;
    name = role === "student" ? first.display_name : `Parent of ${first.display_name}`;
  }
  const token = `mock.${role}.${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
  const user: User = { id: `demo-${role}-${inst}`, role, name, institute_id: inst, student_id: sid };
  S.tokens.set(token, user);
  return ok({ access_token: token, token_type: "bearer", token, me: { user_id: user.id, name: user.name, role, institute_slug: inst, student_id: sid }, user });
}

// ---- ingest ---------------------------------------------------------------------------------------
const TRUE = new Set(["true", "1", "y", "yes", "p", "present", "हाँ", "हां", "उपस्थित", "हाजिर"]);
const FALSE = new Set(["false", "0", "n", "no", "a", "ab", "absent", "-", "--", "अनुपस्थित", "गैरहाजिर"]);

type RowErr = { row: number; column: string; code: string; severity: "error" | "warning"; value: string; message_en: string; message_hi: string };

async function analyse(j: Job) {
  const idx = await rollIndex(j.institute);
  const col = (t: string) => j.mapping.findIndex((m) => m.target === t);
  const c = Object.fromEntries(TARGETS[j.kind].map((t) => [t.id, col(t.id)]));
  const errors: RowErr[] = [];
  const seen = new Set<string>();
  const bad = new Set<number>();
  const E = (row: number, column: string, code: string, value: string, en: string, hi: string, severity: "error" | "warning" = "error") => {
    errors.push({ row, column, code, severity, value, message_en: en, message_hi: hi });
    if (severity === "error") bad.add(row);
  };
  const num = (v: string) => Number(v.replace(/[%,₹\s]/g, ""));
  j.rows.forEach((r, i) => {
    const row = i + 2; // spreadsheet row number, header is row 1
    const get = (t: string) => (c[t] >= 0 ? (r[c[t]] ?? "").trim() : "");
    const roll = get("roll_no");
    if (c.roll_no >= 0) {
      if (!roll) E(row, "roll_no", "missing", "", "Roll number is empty", "रोल नंबर खाली है");
      else if (j.kind === "students") {
        if (seen.has(roll.toLowerCase())) E(row, "roll_no", "duplicate", roll, `Roll number ${roll} appears twice in this file`, `रोल नंबर ${roll} इस फ़ाइल में दो बार है`);
        seen.add(roll.toLowerCase());
      } else if (!idx.has(roll.toLowerCase())) E(row, "roll_no", "unknown_student", roll, `No student with roll number ${roll}`, `रोल नंबर ${roll} का कोई विद्यार्थी नहीं मिला`);
    }
    if (j.kind === "students") {
      if (c.name >= 0 && !get("name")) E(row, "name", "missing", "", "Name is empty", "नाम खाली है");
      const dob = get("dob");
      if (dob) {
        const d = new Date(dob);
        if (Number.isNaN(+d)) E(row, "dob", "bad_date", dob, "Date of birth is not a valid date (use YYYY-MM-DD)", "जन्म तिथि मान्य नहीं (YYYY-MM-DD लिखें)");
        else {
          const age = (Date.UTC(2026, 9, 25) - +d) / 31557600000;
          if (age < 10 || age > 40) E(row, "dob", "age_range", dob, `Age ${age.toFixed(0)} looks wrong`, `उम्र ${age.toFixed(0)} संदिग्ध लगती है`);
          else if (age < 16) E(row, "dob", "age_under_16", dob, "Under 16: parental consent and the academic-support track only", "16 से कम: अभिभावक की सहमति और केवल शैक्षिक सहयोग", "warning");
        }
      }
    }
    if (j.kind === "attendance") {
      const p = get("attendance_pct");
      if (c.attendance_pct >= 0 && p) {
        const v = num(p);
        if (Number.isNaN(v)) E(row, "attendance_pct", "not_a_number", p, `"${p}" is not a number`, `"${p}" संख्या नहीं है`);
        else if (v < 0 || v > 100) E(row, "attendance_pct", "out_of_range", p, `Attendance must be between 0 and 100 (got ${v})`, `उपस्थिति 0 से 100 के बीच होनी चाहिए (मिला ${v})`);
      }
      const f = get("present_flag").toLowerCase();
      if (c.present_flag >= 0 && f && !TRUE.has(f) && !FALSE.has(f)) E(row, "present_flag", "bad_flag", f, `"${f}" is not yes/no or present/absent`, `"${f}" हाँ/नहीं या उपस्थित/अनुपस्थित नहीं है`);
      const d = get("attendance_date");
      if (c.attendance_date >= 0 && d && Number.isNaN(+new Date(d))) E(row, "attendance_date", "bad_date", d, "Not a valid date", "तिथि मान्य नहीं");
    }
    if (j.kind === "fees") {
      const a = get("amount_paise");
      if (c.amount_paise >= 0) {
        const v = num(a);
        if (!a || Number.isNaN(v)) E(row, "amount_paise", "not_a_number", a, "Amount is not a number", "राशि संख्या नहीं है");
        else if (v < 0) E(row, "amount_paise", "negative", a, "Amount cannot be negative (refunds go in their own column)", "राशि ऋणात्मक नहीं हो सकती");
      }
    }
    if (j.kind === "results") {
      const m = get("raw_score");
      if (c.raw_score >= 0) {
        const absent = TRUE.has(get("absent_flag").toLowerCase());
        if (!m && !absent) E(row, "raw_score", "missing", "", "Marks are empty and the student is not marked absent", "अंक खाली हैं और विद्यार्थी अनुपस्थित नहीं है");
        else if (m && Number.isNaN(num(m))) E(row, "raw_score", "not_a_number", m, `"${m}" is not a number`, `"${m}" संख्या नहीं है`);
      }
      if (c.test_name >= 0 && !get("test_name")) E(row, "test_name", "missing", "", "Test name is empty", "टेस्ट का नाम खाली है");
    }
    if (j.kind === "answer-key") {
      const q = get("question_no");
      if (c.question_no >= 0 && (!/^\d+$/.test(q) || +q < 1 || +q > 300)) E(row, "question_no", "bad_question", q, "Question number must be a whole number from 1 to 300", "प्रश्न संख्या 1 से 300 के बीच पूर्ण संख्या हो");
      const a = get("accepted_answers");
      if (c.accepted_answers >= 0 && !/^([A-Da-d](\|[A-Da-d])*|-?\d+(\.\d+)?)$/.test(a)) E(row, "accepted_answers", "bad_answer", a, "Answer must be A to D (or A|C for several) or a number", "उत्तर A से D (या A|C) या संख्या होना चाहिए");
    }
  });
  const missingReq = TARGETS[j.kind].filter((t) => t.required && c[t.id] < 0).map((t) => t.id);
  const oneOf = ONE_OF[j.kind];
  const oneOfMissing = !!oneOf && oneOf.every((t) => c[t] < 0);
  return { errors, bad, missingReq, oneOfMissing, oneOf, c, idx };
}

const STAGES = [
  ["reading", 0.25],
  ["cleaning", 0.5],
  ["scoring", 0.75],
  ["recompute", 1],
] as const;

async function jobView(j: Job): Promise<J> {
  const a = await analyse(j);
  const rowsN = j.rows.length;
  const accepted = rowsN - a.bad.size;
  let status: "preview" | "running" | "done" | "failed" = "preview";
  let progress = 0;
  let stage = "preview";
  if (j.error) status = "failed";
  else if (j.committedAt) {
    progress = Math.min(1, (Date.now() - j.committedAt) / 1600);
    status = progress >= 1 ? "done" : "running";
    stage = progress >= 1 ? "done" : (STAGES.find(([, t]) => progress < t) ?? STAGES[3])[0];
    if (status === "done" && j.applied === 0 && j.kind === "attendance") await applyJob(j, a);
  }
  const t = TARGETS[j.kind];
  return {
    job_id: j.id, kind: j.kind, filename: j.filename, status, stage, progress: +progress.toFixed(2), error: j.error ?? null,
    row_count: rowsN, accepted_count: accepted, error_count: a.errors.filter((e) => e.severity === "error").length, warning_count: a.errors.filter((e) => e.severity === "warning").length,
    rejected_rows: a.bad.size,
    columns: j.mapping,
    targets: t.map((x) => ({ id: x.id, required: x.required, label_en: x.label_en, label_hi: x.label_hi })),
    missing_required: a.missingReq, one_of: a.oneOf ?? null, one_of_missing: a.oneOfMissing,
    can_commit: status === "preview" && a.missingReq.length === 0 && !a.oneOfMissing && accepted > 0,
    errors: a.errors.slice(0, 200), errors_truncated: a.errors.length > 200,
    sample_rows: j.rows.slice(0, 5).map((r) => Object.fromEntries(j.headers.map((h, i) => [h, r[i] ?? ""]))),
    redirect: status === "done" ? "/teacher" : null,
    simulated: true,
  };
}

async function applyJob(j: Job, a: Awaited<ReturnType<typeof analyse>>) {
  j.applied = 1;
  if (j.kind !== "attendance") return;
  const sums = new Map<string, { p: number; n: number; pct?: number }>();
  j.rows.forEach((r, i) => {
    if (a.bad.has(i + 2)) return;
    const sid = a.idx.get((r[a.c.roll_no] ?? "").trim().toLowerCase());
    if (!sid) return;
    const e = sums.get(sid) ?? { p: 0, n: 0 };
    const flag = a.c.present_flag >= 0 ? (r[a.c.present_flag] ?? "").trim().toLowerCase() : "";
    if (flag) {
      e.n++;
      if (TRUE.has(flag)) e.p++;
    }
    const pct = a.c.attendance_pct >= 0 ? (r[a.c.attendance_pct] ?? "").trim() : "";
    if (pct) e.pct = Number(pct.replace(/[%\s]/g, ""));
    sums.set(sid, e);
  });
  sums.forEach((e, sid) => S.attendance.set(sid, Math.round(e.pct ?? (e.n ? (100 * e.p) / e.n : attendanceOf(sid)))));
}

async function startIngest(u: User, kind: Kind, req: MockReq): Promise<MockRes> {
  const f = req.form?.get("file");
  if (!(f instanceof File)) return invalid("file", "Attach a file in the 'file' field");
  const name = f.name || "upload";
  if (/\.xlsx?$/i.test(name)) return fail(415, "The mock server reads CSV only. Excel files are parsed by the real server; save this sheet as CSV to try the mock.");
  if (!/\.(csv|tsv|txt)$/i.test(name)) return fail(415, "Only CSV or Excel files can be uploaded here");
  if (f.size === 0) return invalid("file", "The file is empty");
  if (f.size > 20 * 1024 * 1024) return fail(413, "File is larger than 20 MB");
  const table = parseCsv(await f.text());
  if (table.length < 2) return invalid("file", "The file needs a header row and at least one data row");
  const j: Job = { id: id("job"), kind, filename: name, institute: u.institute_id, headers: table[0].map((h) => h.trim()), rows: table.slice(1), mapping: [], committedAt: null, applied: 0 };
  j.mapping = guessMapping(kind, j.headers);
  S.jobs.set(j.id, j);
  await sleep(300);
  return ok(await jobView(j), 201);
}

// ---- OMR --------------------------------------------------------------------------------------------
async function startOmr(u: User, req: MockReq): Promise<MockRes> {
  const f = req.form?.get("file") ?? req.form?.get("image");
  if (!(f instanceof File)) return invalid("file", "Attach a photo in the 'file' field");
  if (!/^image\//.test(f.type) && !/\.(png|jpe?g|heic|webp)$/i.test(f.name)) return fail(415, "Only photos (JPG or PNG) can be read");
  const rnd = rng(hash(f.name + f.size));
  const idx = [...(await rollIndex(u.institute_id)).entries()];
  const [roll] = idx.length ? idx[Math.floor(rnd() * idx.length)] : ["unknown"];
  const quality = f.size < 20_000 ? { ok: false, retake: true, reason: "Photo is too small or blurry to read. Retake it flat, in good light, with all four corner marks visible." } : { ok: true, retake: false, reason: null };
  const N = 75;
  const letters = ["A", "B", "C", "D"];
  const questions: J = {};
  for (let q = 1; q <= N; q++) {
    const blank = rnd() < 0.08;
    questions[q] = { question_no: q, status: blank ? "blank" : "answered", answer: blank ? null : letters[Math.floor(rnd() * 4)], confidence: +(0.93 + rnd() * 0.07).toFixed(3) };
  }
  const uncertain: J[] = [];
  const reasons = ["faint_mark", "double_mark", "ambiguous"];
  const picks = new Set<number>();
  while (quality.ok && picks.size < 6) picks.add(1 + Math.floor(rnd() * N));
  [...picks].sort((a, b) => a - b).forEach((q) => {
    const reason = reasons[Math.floor(rnd() * 3)];
    const a = letters[Math.floor(rnd() * 4)];
    const b = letters[(letters.indexOf(a) + 1 + Math.floor(rnd() * 3)) % 4];
    questions[q] = { question_no: q, status: reason === "double_mark" ? "multi_marked" : "answered", answer: reason === "double_mark" ? `${a}|${b}` : a, confidence: +(0.4 + rnd() * 0.25).toFixed(3), marked_options: reason === "double_mark" ? [a, b] : [a] };
    uncertain.push({ question_no: q, label: reason === "double_mark" ? `${a}|${b}` : a, reason, fill: +(0.35 + rnd() * 0.3).toFixed(2), options: letters });
  });
  const result = { layout_name: "jee_75", test_id: null, roll_no: roll, roll_confidence: 0.98, questions, uncertain, quality };
  const job: OmrJob = { id: id("omr"), institute: u.institute_id, filename: f.name, result, corrections: {}, done: false };
  S.omr.set(job.id, job);
  await sleep(500);
  return ok({ job_id: job.id, status: quality.ok ? "review" : "retake", filename: f.name, result, simulated: true }, 201);
}

async function confirmOmr(u: User, jobId: string, req: MockReq): Promise<MockRes> {
  const job = S.omr.get(jobId);
  if (!job || job.institute !== u.institute_id) return fail(404, "No such OMR job");
  if (job.done) return fail(409, "This sheet was already confirmed");
  const corr = (req.json?.corrections ?? {}) as Record<string, string>;
  const open = (job.result.uncertain as J[]).filter((x) => !corr[String(x.question_no)] || !/^[A-D]?$/.test(corr[String(x.question_no)]));
  if (open.length) return fail(422, `${open.length} uncertain bubble(s) still need a decision (questions ${open.map((x) => x.question_no).join(", ")})`);
  job.corrections = corr;
  job.done = true;
  await sleep(400);
  const qs = job.result.questions as J;
  const rnd = rng(hash(job.id));
  let right = 0, wrong = 0, blank = 0;
  for (const k of Object.keys(qs)) {
    const ans = corr[k] ?? qs[k].answer;
    if (!ans) blank++;
    else if (rnd() < 0.62) right++;
    else wrong++;
  }
  return ok({ job_id: jobId, status: "done", roll_no: job.result.roll_no, scored: { correct: right, wrong, blank, marks: right * 4 - wrong, max_marks: 300 }, redirect: "/teacher", simulated: true });
}

// ---- tests, flagged questions, answer keys -------------------------------------------------------
async function testsFor(inst: string, batch: string): Promise<J[]> {
  const m = await art(inst, "mastery");
  const b = (m?.batches as J[] | undefined)?.find((x) => x.batch_id === batch);
  if (!b) return [];
  return [1, 2, 3].map((n) => ({ test_id: `${batch}-T${n}`, name: `Part test ${n}`, date: `2026-0${6 + n}-1${n}`, question_count: 75 }));
}
function flaggedFor(testId: string): J[] {
  // MOCK: the last test of each batch has two suspect keys. Real server derives these from response patterns.
  if (!testId.endsWith("-T3")) return [];
  return [
    { question_no: 17, subject: "Physics", current_key: "B", suggested_key: "C", reason_code: "wrong_key_suspected", share_top_group_chose_suggested: 0.81, share_chose_current_key: 0.09, n_students: 64 },
    { question_no: 52, subject: "Chemistry", current_key: "A", suggested_key: "D", reason_code: "wrong_key_suspected", share_top_group_chose_suggested: 0.74, share_chose_current_key: 0.14, n_students: 64 },
  ].map((f) => {
    const fx = S.fixedKeys.get(`${testId}|${f.question_no}`);
    return { ...f, status: fx ? "fixed" : "open", current_key: fx ? fx.key : f.current_key, fixed_at: fx?.at ?? null };
  });
}

// ---- reports ------------------------------------------------------------------------------------------
const CHECKS = [
  ["numbers_match", "Every number comes from the data"],
  ["topics_allowed", "Only real syllabus topics are named"],
  ["placeholders", "Student and institute names inserted after writing"],
  ["no_ranking_shaming", "No ranking, comparison or shaming words"],
  ["tone_supportive", "Supportive wording only"],
  ["length_ok", "Length between 80 and 180 words"],
  ["trend_consistent", "Trend wording matches the numbers"],
  ["home_tips_ok", "Home tips are safe and simple"],
] as const;

async function makeReport(u: User, sid: string, req: MockReq): Promise<MockRes> {
  const inst = u.institute_id;
  if ((u.role === "student" || u.role === "parent") && sid !== u.student_id) return fail(403, "You can only create reports for your own record");
  const lang = req.json?.language;
  if (lang !== "hi" && lang !== "en") return invalid("language", "Language must be 'hi' or 'en'");
  if ((await withdrawn(inst)).has(sid)) return fail(409, "Consent was withdrawn for this student; processing is halted");
  const reports = ((await art(inst, "reports"))?.reports as J[]) ?? [];
  const r = reports.find((x) => x.student_id === sid && x.language === lang);
  if (!r) return fail(404, "No report data for this student yet");
  const wantLlm = req.json?.use_llm === true;
  await sleep(wantLlm ? 900 : 350);
  const passed = r.verified === true;
  return ok({
    student_id: sid, language: lang, month: r.month, body: r.body, numbers: r.numbers_json ?? null,
    verified: passed,
    checks: CHECKS.map(([cid, label]) => ({ id: cid, label, passed })),
    source: "template", llm_requested: wantLlm, llm_available: false,
    fallback_used: wantLlm, fallback_reason: wantLlm ? "local_model_not_running" : null,
    hi_reviewed: false, latency_ms: wantLlm ? 900 : 350, simulated: true,
  });
}

// ---- privacy tier -----------------------------------------------------------------------------------
async function tierView(inst: string): Promise<J> {
  const m = await art(null, "metrics");
  const v = (k: string) => (m?.results as J[] | undefined)?.find((x) => x.metric_key === k)?.value as number | undefined;
  const pick = (p: string) => ({ auc: v(`${p}_auc`) ?? null, precision: v(`${p}_precision`) ?? null, recall: v(`${p}_recall`) ?? null, lead_time_days: v(`${p}_lead_time_days`) ?? null });
  const list = await supportList(inst);
  return {
    tier: S.tier.get(inst) ?? "full",
    options: [
      { tier: "full", label_en: "Full (adults only, with their own consent)", label_hi: "पूर्ण (केवल वयस्क, स्वयं की सहमति से)", metrics: pick("risk_full_lgbm") },
      { tier: "academic_only", label_en: "Academic only (tests, no attendance or engagement)", label_hi: "केवल शैक्षिक (टेस्ट, उपस्थिति या सक्रियता नहीं)", metrics: pick("risk_academic_lgbm") },
    ],
    minors_always_academic: true,
    list_size: (list?.list as J[] | undefined)?.length ?? 0,
    capacity_per_week: list?.capacity_per_week ?? null,
    origin: "synthetic",
    note: "Numbers are from the synthetic 2026 test cohort (3 snapshots, 45-day horizon, capacity 5% of active students). Students under 18 are always on the academic track; this switch changes adults only.",
    simulated: true,
  };
}


// ---- real-server-shaped reads, composed from the artifact files -------------------------------------
async function batchList(inst: string): Promise<J[]> {
  return ((await art(inst, "mastery"))?.batches as J[]) ?? [];
}
async function batchPeople(inst: string, ids: string[]): Promise<J[]> {
  const st = new Map((await students(inst)).map((x) => [x.student_id, x]));
  const adults = new Set((((await art(inst, "risk"))?.list as J[]) ?? []).filter((x) => x.track === "full").map((x) => x.student_id));
  return ids.map((sid) => {
    const x = st.get(sid);
    return {
      student_id: sid,
      roll_no: x?.roll_no ?? `ID-${sid.slice(0, 4)}`,
      name: x?.display_name ?? `Student ${sid.slice(0, 4)}`,
      status: "active",
      dob: x ? (x.age_class === "minor" ? "2010-06-01" : "2000-06-01") : adults.has(sid) ? "2004-01-01" : "2010-06-01",
    };
  });
}
async function liveRead(inst: string, p: string[]): Promise<MockRes | null> {
  const [a, b, c] = p;
  if (a === "batches" && !b) {
    const risk = await art(inst, "risk");
    const bs = await batchList(inst);
    return ok({ institute_slug: inst, batches: bs.map((x) => ({ id: x.batch_id, name: x.name, exam: x.exam, class_level: x.class_level, academic_year: 2026, mentor_capacity_per_week: Math.max(1, Math.round(((risk?.capacity_per_week as number) ?? 4) / Math.max(1, bs.length))), students: x.student_ids.length, active_students: x.student_ids.length })) });
  }
  if (a === "batches" && b && (c === "students" || c === "heatmap" || c === "support-list")) {
    const bt = (await batchList(inst)).find((x) => x.batch_id === b);
    if (!bt) return fail(404, "Unknown batch");
    if (c === "students") return ok({ batch_id: b, students: await batchPeople(inst, bt.student_ids) });
    if (c === "heatmap") {
      const m = (await art(inst, "mastery")) as J;
      const ids = new Set<string>(bt.student_ids);
      m.batches = [bt];
      m.cells = (m.cells as J[]).filter((x) => ids.has(x.student_id));
      m.students = (await batchPeople(inst, bt.student_ids)).map((x) => ({ student_id: x.student_id, roll_no: x.roll_no, name: x.name }));
      return ok(m);
    }
    const r = await supportList(inst);
    if (!r) return fail(404, "No support list");
    const ids = new Set<string>(bt.student_ids);
    r.list = (r.list as J[]).filter((x) => ids.has(x.student_id)).map((x, i) => ({ ...x, priority_slot: i + 1 }));
    return ok(r);
  }
  if (a === "students" && b && (c === "profile" || c === "parent-view" || c === "percentile")) {
    const file = c === "profile" ? "student" : c === "parent-view" ? "parent" : "percentile";
    const body = await art(inst, file);
    if (!body) return fail(404, "No data");
    const key = file === "parent" ? "parents" : "students";
    const rows = (body[key] as J[]).filter((x) => x.student_id === b);
    if (!rows.length) return fail(404, "Not enough data for this student yet");
    body[key] = rows;
    return ok(body);
  }
  return null;
}

// ---- router ---------------------------------------------------------------------------------------------
function can(u: User, method: string, p: string[]): string | null {
  const [a, b] = p;
  const staff = u.role === "owner" || u.role === "teacher" || u.role === "mentor";
  if (a === "ingest") return u.role === "owner" || u.role === "teacher" ? null : `The ${u.role} role cannot upload data`;
  if (a === "answer-keys" || (a === "tests" && !staff)) return u.role === "owner" || u.role === "teacher" ? null : `The ${u.role} role cannot change answer keys`;
  if (a === "consents") {
    if (!staff) return `The ${u.role} role cannot see the consent ledger`;
    return method === "GET" || u.role === "owner" ? null : "Only the owner can record or withdraw consent";
  }
  if (a === "settings") return method === "GET" ? (staff ? null : `The ${u.role} role cannot see settings`) : u.role === "owner" ? null : "Only the owner can change the privacy tier";
  if (a === "students" && p[2] === "attendance") return staff ? null : `The ${u.role} role cannot edit attendance`;
  if (a === "batches" || a === "tests") return staff ? null : `The ${u.role} role cannot read batch data`;
  void b;
  return null;
}

export async function handle(req: MockReq): Promise<MockRes> {
  const { method, path: p } = req;
  const [a, b, c] = p;
  if (a === "auth" && b === "login" && method === "POST") return login(req.json);
  if (a === "dev" && b === "reset" && method === "POST") {
    // test helper: forget every edit, upload and consent change (tokens survive)
    S.attendance.clear(); S.fixedKeys.clear(); S.jobs.clear(); S.omr.clear(); S.consents.clear(); S.tier.clear(); S.rolls.clear();
    return ok({ reset: true });
  }
  if (a === "health") return ok({ status: "ok", db: "mock", ollama: "mock", mock: true });
  if (a === "version") return ok({ api: "mock", model_version: "v1.1.0" });
  const u = req.token ? S.tokens.get(req.token) : undefined;
  if (!u) return fail(401, "Not signed in, or the session ended");
  if (a === "me") return ok(u);
  const denied = can(u, method, p);
  if (denied) return fail(403, denied);
  const inst = u.institute_id;

  // ingest
  if (a === "ingest") {
    if (b === "omr" && !c && method === "POST") return startOmr(u, req);
    if (b === "omr" && c && p[3] === "confirm" && method === "POST") return confirmOmr(u, c, req);
    if (b === "omr" && c && method === "GET") {
      const j = S.omr.get(c);
      return j && j.institute === inst ? ok({ job_id: j.id, status: j.done ? "done" : "review", filename: j.filename, result: j.result }) : fail(404, "No such OMR job");
    }
    if (b === "jobs" && c) {
      const j = S.jobs.get(c);
      if (!j || j.institute !== inst) return fail(404, "No such job");
      if (p[3] === "mapping" && method === "POST") {
        if (j.committedAt) return fail(409, "This job was already committed");
        const m = (req.json?.mapping ?? {}) as Record<string, string | null>;
        const targets = Object.values(m).filter((x): x is string => !!x);
        if (new Set(targets).size !== targets.length) return invalid("mapping", "Two columns are mapped to the same field");
        j.mapping = j.mapping.map((x) => (x.source in m ? { ...x, target: m[x.source] || null, confidence: m[x.source] ? 1 : 0 } : x));
        return ok(await jobView(j));
      }
      if (p[3] === "commit" && method === "POST") {
        const v = await jobView(j);
        if (j.committedAt) return ok(v);
        if (!v.can_commit) return fail(422, v.missing_required.length ? `Map the required columns first: ${v.missing_required.join(", ")}` : v.one_of_missing ? `Map at least one of: ${v.one_of.join(", ")}` : "No valid rows to commit");
        j.committedAt = Date.now();
        return ok(await jobView(j), 202);
      }
      if (!p[3] && method === "GET") return ok(await jobView(j));
    }
    if (KINDS.includes(b as Kind) && method === "POST") return startIngest(u, b as Kind, req);
    return fail(404, "Unknown ingest path");
  }

  if (a === "batches" && b && c === "tests" && method === "GET") return ok({ batch_id: b, tests: await testsFor(inst, b), simulated: true });
  if (a === "tests" && b && c === "flagged-questions" && method === "GET") return ok({ test_id: b, flagged: flaggedFor(b), origin: "synthetic", simulated: true });
  if (a === "answer-keys" && b && c && method === "POST") {
    const key = String(req.json?.key ?? "").trim().toUpperCase();
    if (!/^[A-D](\|[A-D])*$/.test(key)) return invalid("key", "Answer must be A, B, C or D (or A|C for several)");
    if (!flaggedFor(b).some((f) => String(f.question_no) === c)) return fail(404, "That question is not on this test's flagged list");
    S.fixedKeys.set(`${b}|${c}`, { key, at: new Date().toISOString() });
    await sleep(500);
    return ok({ test_id: b, question_no: +c, key, rescored_students: 64, recompute_ms: 480, flagged: flaggedFor(b), simulated: true });
  }

  if (a === "students" && b && c === "attendance" && method === "PATCH") {
    const v = req.json?.attendance_pct;
    if (typeof v !== "number" || Number.isNaN(v)) return invalid("attendance_pct", "Attendance must be a number");
    if (v < 0 || v > 100) return invalid("attendance_pct", `Attendance must be between 0 and 100 (got ${v})`);
    const risk = await art(inst, "risk");
    const st = (await students(inst)).find((x) => x.student_id === b);
    const row = (risk?.list as J[] | undefined)?.find((x) => x.student_id === b);
    if (!st && !row) return fail(404, "Unknown student for this institute");
    S.attendance.set(b, Math.round(v * 10) / 10);
    await sleep(350);
    const adult = row?.track === "full";
    const list = await supportList(inst);
    const onList = !!(list?.list as J[]).find((x) => x.student_id === b);
    return ok({
      student_id: b, attendance_pct: S.attendance.get(b), track: adult ? "full" : "academic_support",
      effect: adult ? "model" : "rule_only", on_support_list: onList, recompute_ms: 350,
      message_en: adult ? (onList ? "Saved. The support list was recomputed and this student is on it." : "Saved. The support list was recomputed; this student is not on it.") : v < 75 ? "Saved. Under 18: attendance is not used by the model. Shown only as your own 75% rule." : "Saved. Under 18: attendance is not used by the model.",
      message_hi: adult ? (onList ? "सहेजा गया। सहयोग सूची दोबारा बनी और यह विद्यार्थी उसमें है।" : "सहेजा गया। सहयोग सूची दोबारा बनी; यह विद्यार्थी उसमें नहीं है।") : v < 75 ? "सहेजा गया। 18 से कम उम्र: मॉडल उपस्थिति इस्तेमाल नहीं करता। केवल आपके 75% नियम के रूप में दिखेगा।" : "सहेजा गया। 18 से कम उम्र: मॉडल उपस्थिति इस्तेमाल नहीं करता।",
      support_list: list, simulated: true,
    });
  }
  if (a === "students" && b && c === "reports" && method === "POST") return makeReport(u, b, req);

  if (a === "consents") {
    const l = await ledger(inst);
    if (method === "GET") {
      const q = (req.search.get("q") ?? "").toLowerCase();
      const items = l.filter((x) => !q || `${x.roll_no} ${x.guardian_display}`.toLowerCase().includes(q)).sort((x, y) => x.roll_no.localeCompare(y.roll_no));
      return ok({ items, summary: { total: l.length, active: l.filter((x) => x.status === "active").length, withdrawn: l.filter((x) => x.status === "withdrawn").length }, simulated: true });
    }
    if (method === "POST") {
      const roll = String(req.json?.roll_no ?? "").trim();
      const guardian = String(req.json?.guardian_name ?? "").trim();
      if (!roll) return invalid("roll_no", "Roll number is required");
      if (!guardian) return invalid("guardian_name", "Guardian name is required");
      const sid = (await rollIndex(inst)).get(roll.toLowerCase());
      if (!sid) return invalid("roll_no", `No student with roll number ${roll}`);
      if (l.some((x) => x.student_id === sid && x.status === "active")) return fail(409, "This student already has an active consent");
      const row: Consent = { consent_id: id("c"), student_id: sid, roll_no: roll, guardian_display: guardian, kind: "parental", method: req.json?.method === "digilocker" ? "digilocker" : "in_person_id_check", date: new Date().toISOString().slice(0, 10), status: "active" };
      l.push(row);
      return ok(row, 201);
    }
    if (method === "DELETE" && b) {
      const row = l.find((x) => x.consent_id === b);
      if (!row) return fail(404, "No such consent");
      row.status = "withdrawn";
      return ok({ ...row, effect: "Processing halted: this student is removed from the support list and reports." });
    }
  }
  if (a === "settings" && b === "privacy-tier") {
    if (method === "GET") return ok(await tierView(inst));
    if (method === "PUT") {
      const t = req.json?.tier;
      if (t !== "full" && t !== "academic_only") return invalid("tier", "Tier must be 'full' or 'academic_only'");
      S.tier.set(inst, t);
      await sleep(400);
      return ok(await tierView(inst));
    }
  }

  if (method === "GET") {
    const live = await liveRead(inst, p);
    if (live) return live;
    if (a === "owner" && b === "dashboard") return readFile(u, inst, "owner");
    if (!b && (a === "datacard" || a === "scaling" || a === "models")) return readFile(u, a === "datacard" ? inst : "global", a);
  }
  // artifact-shaped reads: /{institute|global}/{file}
  if (a && b && !c && method === "GET" && /^[a-z0-9_]+$/.test(a) && /^[a-z0-9_]+$/.test(b)) return readFile(u, a, b);
  return fail(404, `No route for ${method} /${p.join("/")}`);
}
