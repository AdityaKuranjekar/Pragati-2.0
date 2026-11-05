import type { Step } from "./types";
/** Placeholder cut-offs; they must follow the engine's real output range (PROPOSAL section 7). */
export const STEP_EDGES = [0.2, 0.4, 0.6, 0.8] as const;
export const stepOf = (v: number): Step => (v < 0.2 ? 1 : v < 0.4 ? 2 : v < 0.6 ? 3 : v < 0.8 ? 4 : 5);
export const STEP_LABEL: Record<Step, string> = { 1: "0.0 to 0.2", 2: "0.2 to 0.4", 3: "0.4 to 0.6", 4: "0.6 to 0.8", 5: "0.8 to 1.0" };
export const STEPS: Step[] = [1, 2, 3, 4, 5];
