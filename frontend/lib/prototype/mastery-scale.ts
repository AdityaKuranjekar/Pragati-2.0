import type { Step } from "./types";
/** Placeholder cut-offs; they must follow the engine's real output range (PROPOSAL section 7). */
export const stepOf = (v: number): Step => (v < 0.2 ? 1 : v < 0.4 ? 2 : v < 0.6 ? 3 : v < 0.8 ? 4 : 5);
export const STEPS: Step[] = [1, 2, 3, 4, 5];
/** Plain words for each level. */
export const STEP_WORD: Record<Step, string> = { 1: "Just starting", 2: "Needs practice", 3: "Getting there", 4: "Mostly secure", 5: "Secure" };
export const NO_ESTIMATE_WORD = "Too early";
export const NO_ESTIMATE_LONG = "Too little practice to judge";
/** Numeric band, shown only under "Show the numbers". */
export const STEP_RANGE: Record<Step, string> = { 1: "0.0 to 0.2", 2: "0.2 to 0.4", 3: "0.4 to 0.6", 4: "0.6 to 0.8", 5: "0.8 to 1.0" };
