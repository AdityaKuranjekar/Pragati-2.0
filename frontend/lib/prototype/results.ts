import type { Origin } from "./types";

export type ResultRow = {
  id: string;
  metric: string;
  task: string;
  origin: Origin;
  baseline: string;
  result: string;
  ci: string;
  bar: string;
  outcome: "Met" | "Missed" | "Not assessed";
  note: string;
};
export type NotRun = { id: string; set: string; task: string; origin: Origin; reason: string };

// Figures recorded in the repository from the 1.0 work (docs/pragati-2.0/evaluation/EVAL_PLAN.md section 3).
// Public-dataset rows carry no dataset name in the UI, by the prototype plan.
export const RESULTS: ResultRow[] = [
  {
    id: "r-next",
    metric: "AUC",
    task: "Next-response prediction, hierarchical Rasch",
    origin: "PUB",
    baseline: "0.7135 (4-parameter BKT)",
    result: "0.7633",
    ci: "Not reported",
    bar: "Beat the additive logistic baseline with a bootstrap CI that excludes zero",
    outcome: "Not assessed",
    note: "1.0 figure. The served model is 1PL, not this one. Re-run on the 2.0 protocol is pending.",
  },
  {
    id: "r-ret",
    metric: "AUC",
    task: "Withdrawal at day 28, gradient-boosted trees with isotonic calibration",
    origin: "PUB",
    baseline: "Not recorded here",
    result: "0.706",
    ci: "0.699 to 0.714",
    bar: "0.794 (published anchor)",
    outcome: "Missed",
    note: "Misses the anchor by 0.088. The repository's own gate is 0.70, which this result meets. Not a school-maths task and not used for JEE learners.",
  },
  {
    id: "r-abil",
    metric: "Pearson r",
    task: "Ability recovery, Rasch, 1.0 synthetic data",
    origin: "SIM",
    baseline: "Not recorded here",
    result: "0.53",
    ci: "Not reported",
    bar: "0.80 at 10 or more items per concept",
    outcome: "Not assessed",
    note: "Measured at few answers per cell, below the 10-item condition of the bar. Circular-risk simulator; re-run with the independent one.",
  },
  {
    id: "r-diff",
    metric: "Pearson r",
    task: "Item difficulty recovery, 1.0 synthetic data",
    origin: "SIM",
    baseline: "Not recorded here",
    result: "0.79",
    ci: "Not reported",
    bar: "No bar set",
    outcome: "Not assessed",
    note: "Sample size to be reported on re-run.",
  },
];

export const NOT_RUN: NotRun[] = [
  { id: "n-e4", set: "E4", task: "Root-cause diagnosis against expert labels", origin: "EXP", reason: "No expert labels yet" },
  { id: "n-e5", set: "E5", task: "Question-to-concept tagging", origin: "EXP", reason: "No annotated items yet" },
  { id: "n-e6", set: "E6", task: "Recommendation relevance, blinded teacher raters", origin: "EXP", reason: "No rater panel yet" },
  { id: "n-e7", set: "E7", task: "Prerequisite violations by the recommender", origin: "SIM", reason: "Engine not built" },
  { id: "n-e9", set: "E9", task: "Adaptive against fixed path under the simulator", origin: "SIM", reason: "Engine not built" },
];
