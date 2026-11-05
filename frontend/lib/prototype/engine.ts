// UI stand-in for the Pragati engine (stage S2). Deterministic and small on purpose:
// share-correct with a Beta(1,1) prior, an 80% range, and a chain-order rule for the next step.
// It is NOT the engine and its numbers are not evidence.
import type { Attempt, Concept, Counts, Estimate, LearnerBase, NextStep } from "./types";
import { stepOf } from "./mastery-scale";
import { f2 } from "./format";

export const MIN_EVIDENCE = 5; // fewer attempts than this: no estimate shown
export const EARLY_EVIDENCE = 15; // fewer attempts than this: "early estimate"
export const MASTERED_AT = 0.6; // estimate at or above this counts as met
export const POLICY_VERSION = "ui-standin-0.1";
const Z80 = 1.2816;

export function estimateOf(conceptId: string, { k, n }: Counts): Estimate {
  const a = k + 1;
  const b = n - k + 1;
  const mean = a / (a + b);
  const sd = Math.sqrt((a * b) / ((a + b) * (a + b) * (a + b + 1)));
  return {
    conceptId,
    k,
    n,
    mean,
    lo: Math.max(0, mean - Z80 * sd),
    hi: Math.min(1, mean + Z80 * sd),
    insufficient: n < MIN_EVIDENCE,
    early: n >= MIN_EVIDENCE && n < EARLY_EVIDENCE,
    step: stepOf(mean),
  };
}

export function estimatesFor(learner: LearnerBase, concepts: Concept[], attempts: Attempt[]): Estimate[] {
  return concepts.map((c) => {
    const base = learner.counts[c.id] ?? { k: 0, n: 0 };
    const mine = attempts.filter((a) => a.learnerId === learner.id && a.conceptId === c.id);
    return estimateOf(c.id, { k: base.k + mine.filter((a) => a.correct).length, n: base.n + mine.length });
  });
}

const unmet = (e: Estimate) => e.insufficient || e.mean < MASTERED_AT;

/** First concept in chain order that is not met. The chain is ordered by prerequisite, so this is prerequisite-first. */
export function firstUnmet(est: Estimate[]): Estimate | null {
  return est.find(unmet) ?? null;
}

export function nextStepFor(est: Estimate[], concepts: Concept[]): NextStep | null {
  const target = firstUnmet(est);
  if (!target) return null;
  const idx = est.indexOf(target);
  const c = concepts[idx];
  const prev = idx > 0 ? { e: est[idx - 1], c: concepts[idx - 1] } : null;
  const next = concepts[idx + 1];
  let reason: string;
  if (target.insufficient) {
    reason = `${c.label} has ${target.n} recorded attempt${target.n === 1 ? "" : "s"}; at least ${MIN_EVIDENCE} are needed before an estimate is shown. Diagnostic questions come first.`;
  } else {
    reason = `${c.label}: estimate ${f2(target.mean)} (range ${f2(target.lo)} to ${f2(target.hi)}) from ${target.n} attempts, below the ${f2(MASTERED_AT)} set for this prototype.`;
    if (!prev) reason += next ? ` It is a prerequisite of ${next.label}, so it comes first.` : "";
    else reason += ` Its prerequisite ${prev.c.label} is at ${f2(prev.e.mean)}, so the gap is in this concept.`;
  }
  return {
    action: target.insufficient ? "diagnostic" : "practise",
    conceptId: c.id,
    title: `${target.insufficient ? "Diagnostic questions" : "Practise"}: ${c.label}`,
    reason,
    evidence: [...(prev ? [prev] : []), { e: target, c }].map(({ e, c: cc }) => ({ conceptId: cc.id, label: cc.label, attempts: e.n })),
    policyVersion: POLICY_VERSION,
  };
}
