export type Origin = "DEMO FIXTURE" | "SIM" | "PUB" | "EXP";
export type Step = 1 | 2 | 3 | 4 | 5;
export type Counts = { k: number; n: number };
export type Concept = { id: string; short: string; label: string; classLevel: 11 | 12 };
export type LearnerBase = {
  id: string;
  label: string;
  group: "fixture" | "sim";
  origin: Origin;
  counts: Record<string, Counts>;
};
export type Estimate = {
  conceptId: string;
  k: number;
  n: number;
  mean: number;
  lo: number;
  hi: number;
  insufficient: boolean;
  early: boolean;
  step: Step;
};
export type Attempt = { id: string; learnerId: string; itemId: string; conceptId: string; answer: number; correct: boolean };
export type EdgeState = "proposed" | "accepted" | "modified" | "dismissed";
export type Edge = { id: string; from: string; to: string; source: string };
export type Decision = { id: string; edgeId: string; decision: "accepted" | "modified" | "dismissed"; reason: string; decidedAt: string; decidedBy: string };
export type Item = { id: string; conceptId: string; stem: string; options: string[]; answer: number };
export type NextStep = {
  action: "diagnostic" | "practise";
  conceptId: string;
  title: string;
  reason: string;
  evidence: { conceptId: string; label: string; attempts: number }[];
  rule: string;
  policyVersion: string;
};
