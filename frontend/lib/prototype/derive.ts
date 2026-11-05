"use client";
import { useMemo } from "react";
import { ALL_LEARNERS, CONCEPTS } from "./data";
import { estimatesFor, firstUnmet } from "./engine";
import { useDemoState } from "./store";
import type { Estimate, LearnerBase } from "./types";

export type Row = { learner: LearnerBase; est: Estimate[] };
export type Group = "fixture" | "sim";

export function useRows(): Row[] {
  const { attempts } = useDemoState();
  return useMemo(() => ALL_LEARNERS.map((learner) => ({ learner, est: estimatesFor(learner, CONCEPTS, attempts) })), [attempts]);
}

export function groupRows(rows: Row[], g: Group) {
  return rows.filter((r) => r.learner.group === g);
}

export function coverage(rows: Row[]) {
  const total = rows.length * CONCEPTS.length;
  const withEvidence = rows.reduce((s, r) => s + r.est.filter((e) => !e.insufficient).length, 0);
  return { total, withEvidence };
}

/** Per concept: how many learners have it as their first unmet concept in chain order. */
export function blockerCounts(rows: Row[]) {
  return CONCEPTS.map((c) => rows.filter((r) => firstUnmet(r.est)?.conceptId === c.id).length);
}

export function bottleneck(rows: Row[]) {
  const sim = groupRows(rows, "sim");
  const fix = groupRows(rows, "fixture");
  const simCounts = blockerCounts(sim);
  const fixCounts = blockerCounts(fix);
  const max = Math.max(...simCounts);
  if (max <= 0) return null;
  const idx = simCounts.indexOf(max); // ties go to the earlier concept in the chain
  return {
    concept: CONCEPTS[idx],
    index: idx,
    downstream: CONCEPTS.length - idx - 1,
    simCount: simCounts[idx],
    simTotal: sim.length,
    fixCount: fixCounts[idx],
    fixTotal: fix.length,
    simCounts,
    fixCounts,
  };
}
