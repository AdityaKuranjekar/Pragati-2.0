import type { Origin } from "./types";
/** The literal bracketed string, listed under "About these numbers" so a search over the page text can check it. */
export const originText = (o: Origin) => `[${o}]`;
/** What people see on a chip. */
export const ORIGIN_WORD: Record<Origin, string> = { "DEMO FIXTURE": "Demo data", SIM: "Simulated", PUB: "Public data", EXP: "Expert-labelled" };
export const ORIGIN_MEANING: Record<Origin, string> = {
  "DEMO FIXTURE": "Example learners whose starting answers were chosen for this demo.",
  SIM: "Learners made up by a program with a fixed seed. They say nothing about real students.",
  PUB: "Results on public datasets, recorded in the repository from earlier work.",
  EXP: "Results checked against labels from teachers or other experts (none yet).",
};
