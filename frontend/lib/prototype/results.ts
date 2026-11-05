import type { Origin } from "./types";

export type ResultRow = {
  id: string;
  test: string;
  how: string; // one sentence on how to read the score
  origin: Origin;
  comparedWith: string;
  result: string;
  uncertainty: string;
  target: string;
  verdict: "Meets target" | "Below target" | "Not judged yet";
  note: string;
};
export type NotRun = { id: string; question: string; origin: Origin; reason: string };

// Figures recorded in the repository from the 1.0 work (docs/pragati-2.0/evaluation/EVAL_PLAN.md section 3), shown as recorded.
// Public-dataset rows carry no dataset name, by the prototype plan.
export const RESULTS: ResultRow[] = [
  {
    id: "r-next",
    test: "Predicting whether a learner answers the next question correctly",
    how: "Score from 0.5 (no better than guessing) to 1 (always right). Higher is better.",
    origin: "PUB",
    comparedWith: "An older method scored 0.7135",
    result: "0.7633",
    uncertainty: "Not reported",
    target: "Beat a simple baseline by a margin that holds up statistically",
    verdict: "Not judged yet",
    note: "This is an earlier result from a different model than the one the product runs. It has to be re-tested under the 2.0 plan.",
  },
  {
    id: "r-ret",
    test: "Spotting students likely to drop out of an online course by day 28",
    how: "Same 0.5 to 1 score. Higher is better.",
    origin: "PUB",
    comparedWith: "Not recorded here",
    result: "0.706",
    uncertainty: "0.699 to 0.714",
    target: "0.794, the published figure for this task",
    verdict: "Below target",
    note: "Short of the target by 0.088. The repository's own minimum is 0.70, which this meets. This is not a school-maths task and is not used for JEE learners.",
  },
  {
    id: "r-abil",
    test: "Recovering each learner's true ability from simulated answers",
    how: "Correlation from 0 to 1. 1 means the estimate matches the truth exactly.",
    origin: "SIM",
    comparedWith: "Not recorded here",
    result: "0.53",
    uncertainty: "Not reported",
    target: "0.80 or higher, with at least 10 questions per topic",
    verdict: "Not judged yet",
    note: "Tested with fewer questions per topic than the target assumes, on an earlier simulator. To be re-run with the independent one.",
  },
  {
    id: "r-diff",
    test: "Recovering how hard each question is, from simulated answers",
    how: "Correlation from 0 to 1. Higher is better.",
    origin: "SIM",
    comparedWith: "Not recorded here",
    result: "0.79",
    uncertainty: "Not reported",
    target: "No target set yet",
    verdict: "Not judged yet",
    note: "Sample size to be reported when it is re-run.",
  },
];

export const NOT_RUN: NotRun[] = [
  { id: "n-e4", question: "Does the system name the real root-cause prerequisite for a learner?", origin: "EXP", reason: "Needs examples labelled by experts, which do not exist yet" },
  { id: "n-e5", question: "Is each question tagged to the right topic?", origin: "EXP", reason: "Needs questions annotated by two people, which do not exist yet" },
  { id: "n-e6", question: "Do teachers find the recommendations relevant, compared with a fixed path?", origin: "EXP", reason: "Needs a panel of teachers rating blind, which has not been set up" },
  { id: "n-e7", question: "Does the recommender ever skip a prerequisite?", origin: "SIM", reason: "The recommendation engine is not built yet" },
  { id: "n-e9", question: "Does an adaptive path beat a fixed path in simulation?", origin: "SIM", reason: "The recommendation engine is not built yet" },
];
