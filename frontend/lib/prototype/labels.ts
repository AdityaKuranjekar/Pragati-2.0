// Display text only. Nothing here decides a band, an action or a recommendation: the API does.
import type { Band, Origin } from "./schemas";

export const BAND_LABEL: Record<Band, string> = {
  mastered: "Mastered",
  uncertain: "Uncertain",
  unmastered: "Not mastered",
  insufficient: "Insufficient evidence",
};
export const BAND_ORDER: Band[] = ["mastered", "uncertain", "unmastered", "insufficient"];

export const ORIGIN_MEANING: Record<Origin, string> = {
  "DEMO FIXTURE": "Example learners whose starting answers were chosen for the demo.",
  SIM: "Learners made up by a program with a fixed seed. They say nothing about real students.",
  PUB: "Result on a public dataset.",
  EXP: "Result checked against expert labels.",
};
export const originText = (o: Origin) => `[${o}]`;

/** Action codes the engine returns, as plain labels. An unknown code is shown as returned. */
export const ACTION_LABEL: Record<string, string> = {
  diagnostic: "Answer diagnostic questions",
  gather_evidence: "Answer more questions",
  review_prerequisite: "Review prerequisite",
  practice_target: "Practise",
  goal_mastered: "Goal mastered on current evidence",
};
export const STEP_LABEL: Record<string, string> = { recheck: "Recheck", practice: "Practise" };

// Names for the demo concepts (contracts/topics.yaml ids). Unknown ids fall back to the last id segment.
const NAMES: Record<string, string> = {
  "jee.math.complex_numbers.algebra_complex_argand": "Algebra of complex numbers",
  "jee.math.quadratic_equations.roots_nature": "Nature of roots and discriminant",
  "jee.math.quadratic_equations.equation_formation": "Formation of quadratic equations",
};
export const conceptName = (id: string) => NAMES[id] ?? id.split(".").pop()!.replace(/_/g, " ");

export const f2 = (v: number) => v.toFixed(2);
