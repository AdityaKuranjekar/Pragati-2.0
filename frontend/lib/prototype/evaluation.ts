// Turns the committed result files (ml/evaluation/results/*.json) into table rows. Server side only.
// Verdict = the pre-registered decision rule (ml/evaluation/PREREGISTRATION.md): the paired difference
// (adaptive minus fixed) with its 95% interval. Better-direction interval excludes 0: pass. Interval
// contains 0 or the worse direction excludes 0: miss. Nothing is hidden or reworded to look better.
import type { EvalRow, Evaluation } from "./schemas";

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
  };
}
