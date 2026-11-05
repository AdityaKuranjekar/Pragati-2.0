// Turns the committed result files (ml/evaluation/results/*.json) into table rows. Server side only.
// Verdict = the pre-registered decision rule (ml/evaluation/PREREGISTRATION.md): the paired difference
// (adaptive minus fixed) with its 95% interval. Better-direction interval excludes 0: pass. Interval
// contains 0 or the worse direction excludes 0: miss. Nothing is hidden or reworded to look better.
import type { EvalRow, EvalSet, Evaluation, SetRow } from "./schemas";

type Stat = { mean: number; lo: number; hi: number };
type Setting = {
  label?: string;
  task?: string;
  paths: Record<string, Record<string, Stat>>;
  paired_differences: { adaptive_minus_fixed: Record<string, Stat> };
};
export type ResultFile = Record<string, Setting | Record<string, unknown>>;

const METRICS: { key: string; name: string; better: "higher" | "lower"; primary?: (s: string) => boolean }[] = [
  { key: "final_mastered", name: "Concepts mastered at the end (of 8)", better: "higher", primary: (s) => s === "P_primary_neutral" },
  { key: "reached_goal", name: "Share of learners who reached the goal concept", better: "higher" },
  { key: "items_to_goal", name: "Items used to reach the goal concept (capped at the budget)", better: "lower" },
  { key: "violations", name: "Items served on a concept with an unmastered prerequisite", better: "lower" },
];
// The S2 log names the goal-reach shortfall (and the extra items it took) as the misses to show.
const NAMED_MISS = new Set(["reached_goal", "items_to_goal"]);

const fmt = (v: number, _key = "") => v.toFixed(2);
const sgn = (v: number) => (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(2);
const range = (s: Stat) => `[${fmt(s.lo, "")}, ${fmt(s.hi, "")}]`;

export function verdictFor(better: "higher" | "lower", d: Stat): { verdict: "pass" | "miss"; detail: string } {
  const good = better === "higher" ? d.lo > 0 : d.hi < 0;
  const bad = better === "higher" ? d.hi < 0 : d.lo > 0;
  if (good) return { verdict: "pass", detail: "Better than the fixed path; the interval excludes 0." };
  if (bad) return { verdict: "miss", detail: "Worse than the fixed path; the interval excludes 0." };
  return { verdict: "miss", detail: "No evidence of a difference; the interval contains 0." };
}

export function buildRows(runId: string, file: ResultFile): EvalRow[] {
  const rows: EvalRow[] = [];
  for (const [setting, raw] of Object.entries(file)) {
    if (setting.startsWith("_")) continue;
    const s = raw as Setting;
    if (!s.paths || !s.paired_differences) continue;
    for (const m of METRICS) {
      const fixed = s.paths.fixed?.[m.key];
      const adaptive = s.paths.adaptive?.[m.key];
      const diff = s.paired_differences.adaptive_minus_fixed?.[m.key];
      if (!fixed || !adaptive || !diff) continue;
      const v = verdictFor(m.better, diff);
      rows.push({
        id: `${runId}:${setting}:${m.key}`,
        run: runId,
        setting,
        metric: m.name,
        better: m.better,
        primary: !!m.primary?.(setting),
        task: s.task ?? "simulated mastery under equal item budget",
        origin: "SIM",
        baseline: `Fixed path ${fmt(fixed.mean, m.key)} ${range(fixed)}`,
        result: `Adaptive ${fmt(adaptive.mean, m.key)} ${range(adaptive)}; difference ${sgn(diff.mean)}`,
        interval: `Difference 95% interval [${sgn(diff.lo)}, ${sgn(diff.hi)}]`,
        verdict: v.verdict,
        verdict_detail: v.detail,
        named_miss: NAMED_MISS.has(m.key) && v.verdict === "miss",
      });
    }
  }
  return rows;
}

export function buildEvaluation(registered: ResultFile, posthoc: ResultFile): Evaluation {
  return {
    runs: [
      { id: "registered", title: "Run 1: pre-registered", note: "Run exactly as pre-registered, with a planner defect present (found afterwards). Kept as the registered result." },
      { id: "posthoc", title: "Run 2: post-hoc, not pre-registered", note: "Same suite after the defect fix. Read as a corrected implementation, not as a new finding." },
    ],
    rows: [...buildRows("registered", registered), ...buildRows("posthoc", posthoc)],
    sets: [],
  };
}

// ---- Every evaluation set in EVAL_PLAN §1, computed or not. ---------------------------------------------
// A set is "computed" only when its result file exists, parses and has the expected shape. Otherwise it is
// "not computed" and carries the reason. A missing file is never read as zero.

export const E3_FILE = "e3_recovery_v1.json";
export const E9_FILES = { registered: "e9_sim_v1_registered.json", posthoc: "e9_sim_v1_1_posthoc.json" } as const;
export const E3_TASK = "mastery recovery on simulated learners (latent continuous mastery and binary state at 0.85)";

type SetDef = { id: string; name: string; origin: EvalSet["origin"]; task: string; expected_file: string; not_computed: string };
export const EVAL_SETS: SetDef[] = [
  { id: "E1", name: "Next-response prediction (ASSISTments 2009)", origin: "PUB", task: "Next-response correctness, one step ahead, on K-12 skill-builder data", expected_file: "e1_assistments_v1.json",
    not_computed: "Pre-registered; to be run on the owner's laptop (docs/pragati-2.0/orchestration/LAPTOP_RUN.md). No result file in this build." },
  { id: "E2", name: "Day-28 withdrawal (OULAD)", origin: "PUB", task: "Withdrawal risk at day 28 of a distance-learning course. Not a mastery task", expected_file: "e2_oulad_v1.json",
    not_computed: "Pre-registered; to be run on the owner's laptop (LAPTOP_RUN.md). The only result in the repo is the 1.0 run, which misses the 0.794 anchor and is not this run." },
  { id: "E3", name: "Mastery recovery (simulated learners)", origin: "SIM", task: E3_TASK, expected_file: E3_FILE,
    not_computed: "No result file. The registered E3 run has not been made in this build." },
  { id: "E4", name: "Root-cause diagnosis (expert labels)", origin: "EXP", task: "Name the root-cause concept a teacher would target first", expected_file: "e4_root_cause_v1.json",
    not_computed: "Sheets and answer key written (ml/evaluation/review). No expert has labelled them, so nothing is computed." },
  { id: "E6", name: "Recommendation relevance (teacher ratings)", origin: "EXP", task: "Teacher ratings of the top-3 recommendations, policy label hidden", expected_file: "e6_relevance_v1.json",
    not_computed: "Sheets and answer key written (ml/evaluation/review). No teacher has rated them, so nothing is computed." },
  { id: "E9", name: "Simulated adaptive vs fixed path", origin: "SIM", task: "Simulated mastery under an equal item budget. Not evidence of learning outcomes", expected_file: "e9_sim_v1_*.json",
    not_computed: "Result files missing." },
];

export type LoadedFile = { status: "ok"; data: unknown } | { status: "missing" } | { status: "unreadable"; error: string };
export type LoadedFiles = Record<string, LoadedFile>;

/** Python's json writes undefined numbers as the bare token NaN, which JSON.parse rejects. Map it to null. */
export function parseResultText(text: string): unknown {
  return JSON.parse(text.replace(/\bNaN\b/g, "null"));
}

const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const fmtOrNot = (v: number | null | undefined) => (isNum(v) ? v.toFixed(2) : "not defined");
const rng = (s: Stat3 | null | undefined) => (s && isNum(s.lo) && isNum(s.hi) ? `[${s.lo.toFixed(2)}, ${s.hi.toFixed(2)}]` : "");
type Stat3 = { mean: number | null; lo: number | null; hi: number | null };

/** Checks the shape E3 needs. Returns the setting keys, or null if the file is not an E3 result. */
export function e3Settings(file: unknown): string[] | null {
  if (!file || typeof file !== "object") return null;
  const keys = Object.keys(file as object).filter((k) => !k.startsWith("_"));
  if (keys.length === 0) return null;
  for (const k of keys) {
    const s = (file as Record<string, { paths?: { estimator?: Record<string, unknown> } }>)[k];
    if (!s?.paths?.estimator?.pearson_r) return null;
  }
  return keys;
}

export function e3Verdict(k: number, r: Stat3, cov: Stat3, bandShare: number): { verdict: "pass" | "miss" | "descriptive"; detail: string } {
  if (k < 10) {
    if (bandShare > 0) return { verdict: "miss", detail: "A band is shown with fewer than 10 items. EVAL_PLAN requires 'not enough evidence' there." };
    return { verdict: "descriptive", detail: "Below 10 items; no band shown." };
  }
  const rOk = isNum(r.lo) && r.lo >= 0.8;
  const covOk = isNum(cov.lo) && isNum(cov.hi) && cov.lo >= 0.75 && cov.hi <= 0.85;
  if (rOk && covOk) return { verdict: "pass", detail: "r interval at or above 0.80; coverage interval inside 0.75 to 0.85." };
  const parts = [!rOk ? "the r interval does not reach 0.80" : "", !covOk ? "the coverage interval is not inside 0.75 to 0.85" : ""].filter(Boolean);
  const sentence = parts.length === 2 ? `${parts[0]}, and ${parts[1]}` : parts[0];
  return { verdict: "miss", detail: `${sentence[0].toUpperCase()}${sentence.slice(1)}.` };
}

/** One row per setting of the E3 result file, with the pre-registered verdict worked out from the numbers. */
export function buildE3Rows(file: Record<string, unknown>, keys: string[]): SetRow[] {
  return keys.map((key) => {
    const s = file[key] as {
      config: { n_concepts: number; depth: number; guess: number; items_per_concept: number };
      share_shown_as_band: number;
      paths: { estimator: Record<string, Stat3>; baseline_share_correct: Record<string, Stat3> };
    };
    const c = s.config;
    const e = s.paths.estimator;
    const b = s.paths.baseline_share_correct;
    const v = e3Verdict(c.items_per_concept, e.pearson_r, e.coverage80, s.share_shown_as_band);
    return {
      id: `E3:${key}`,
      setting: `${c.n_concepts} concepts, prerequisite depth ${c.depth}, guessing ${c.guess.toFixed(2)}, ${c.items_per_concept} items per concept`,
      metric: "Estimate against latent mastery",
      result: `r ${fmtOrNot(e.pearson_r.mean)} ${rng(e.pearson_r)}; coverage ${fmtOrNot(e.coverage80.mean)} ${rng(e.coverage80)}; state precision ${fmtOrNot(e.state_precision.mean)}, recall ${fmtOrNot(e.state_recall.mean)}`,
      baseline: `Raw share correct: r ${fmtOrNot(b.pearson_r.mean)} ${rng(b.pearson_r)}`,
      interval: `Estimate r 95% interval ${rng(e.pearson_r)}`,
      verdict: v.verdict,
      detail: v.detail,
    };
  });
}

export function composeEvaluation(files: LoadedFiles): Evaluation {
  const ok = (name: string) => (files[name]?.status === "ok" ? (files[name] as { data: unknown }).data : null);
  const reg = (ok(E9_FILES.registered) as ResultFile | null) ?? {};
  const post = (ok(E9_FILES.posthoc) as ResultFile | null) ?? {};
  const base = buildEvaluation(reg, post);
  const e9Present = ok(E9_FILES.registered) !== null || ok(E9_FILES.posthoc) !== null;
  const sets: EvalSet[] = EVAL_SETS.map((def) => {
    const common = { id: def.id, name: def.name, origin: def.origin, task: def.task, expected_file: def.expected_file, rows: [] as SetRow[] };
    if (def.id === "E9") {
      return { ...common, status: e9Present ? "computed" : "not computed", reason: e9Present ? "Computed from the result files in the Evaluation section below." : def.not_computed };
    }
    if (def.id === "E3") {
      const f = files[E3_FILE];
      if (f?.status === "ok") {
        const keys = e3Settings(f.data);
        if (keys) return { ...common, status: "computed", reason: `Computed from ${E3_FILE}.`, rows: buildE3Rows(f.data as Record<string, unknown>, keys) };
        return { ...common, status: "not computed", reason: `${E3_FILE} is present but does not have the expected shape. Not shown as a result.` };
      }
      if (f?.status === "unreadable") return { ...common, status: "not computed", reason: `${E3_FILE} could not be read: ${f.error}` };
      return { ...common, status: "not computed", reason: def.not_computed };
    }
    const f = files[def.expected_file];
    if (f && f.status !== "missing") {
      return { ...common, status: "not computed", reason: "A result file exists, but this build has no reader for it. Not shown as a result." };
    }
    return { ...common, status: "not computed", reason: def.not_computed };
  });
  return { ...base, sets };
}
