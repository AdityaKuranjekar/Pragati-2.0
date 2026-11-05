import type { Concept, Edge, Item, LearnerBase } from "./types";

// Chain from contracts/topics.yaml, in prerequisite order.
export const CONCEPTS: Concept[] = [
  { id: "jee.math.complex_numbers.algebra_complex_argand", short: "Argand diagram", label: "Complex numbers: Argand diagram", classLevel: 11 },
  { id: "jee.math.quadratic_equations.roots_nature", short: "Nature of roots", label: "Quadratic equations: nature of roots", classLevel: 11 },
  { id: "jee.math.quadratic_equations.equation_formation", short: "Forming equations", label: "Quadratic equations: forming equations", classLevel: 11 },
];
export const conceptById = (id: string) => CONCEPTS.find((c) => c.id === id)!;

// Both edges are proposals awaiting teacher review (prototype plan section 2).
export const EDGES: Edge[] = [
  { id: "e1", from: CONCEPTS[0].id, to: CONCEPTS[1].id, source: "Proposed by the content team" },
  { id: "e2", from: CONCEPTS[1].id, to: CONCEPTS[2].id, source: "Proposed by the content team" },
];

/** Starting attempt counts per fixture learner. They are simulator inputs, not measured outcomes. */
const [C1, C2, C3] = CONCEPTS.map((c) => c.id);
export const FIXTURES: LearnerBase[] = [
  { id: "a", label: "Learner A", group: "fixture", origin: "DEMO FIXTURE", counts: { [C1]: { k: 3, n: 9 }, [C2]: { k: 5, n: 11 }, [C3]: { k: 2, n: 7 } } },
  { id: "b", label: "Learner B", group: "fixture", origin: "DEMO FIXTURE", counts: { [C1]: { k: 11, n: 14 }, [C2]: { k: 4, n: 13 }, [C3]: { k: 0, n: 2 } } },
];

// Simulated cohort. Fixed seed; the generator knows nothing about the estimate function in engine.ts.
export const SIM_SEED = 20261105;
export const SIM_COUNT = 24;
function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function simulate(): LearnerBase[] {
  const r = mulberry32(SIM_SEED);
  const out: LearnerBase[] = [];
  for (let i = 1; i <= SIM_COUNT; i++) {
    const p1 = Math.min(0.95, Math.max(0.15, 0.2 + 0.7 * r()));
    // a learner is unlikely to be far above their prerequisite
    const p2 = Math.min(p1 + 0.05, Math.max(0.1, p1 * 0.85 + (r() - 0.5) * 0.3));
    const p3 = Math.min(p2 + 0.05, Math.max(0.1, p2 * 0.9 + (r() - 0.5) * 0.3));
    const ns = [4 + Math.floor(r() * 13), 2 + Math.floor(r() * 13), Math.floor(r() * 11)];
    const ps = [p1, p2, p3];
    const counts: LearnerBase["counts"] = {};
    CONCEPTS.forEach((c, j) => {
      let k = 0;
      for (let t = 0; t < ns[j]; t++) if (r() < ps[j]) k++;
      counts[c.id] = { k, n: ns[j] };
    });
    out.push({ id: `s${String(i).padStart(2, "0")}`, label: `Sim ${String(i).padStart(2, "0")}`, group: "sim", origin: "SIM", counts });
  }
  return out;
}
export const SIM_LEARNERS: LearnerBase[] = simulate();
export const ALL_LEARNERS: LearnerBase[] = [...FIXTURES, ...SIM_LEARNERS];

// Interface demo items, written for this prototype. They are not reviewed content and not from the item bank.
export const ITEMS: Item[] = [
  { id: "d-arg-1", conceptId: C1, stem: "What is the modulus of 3 + 4i?", options: ["5", "7", "25", "√7"], answer: 0 },
  { id: "d-arg-2", conceptId: C1, stem: "Which point on the Argand plane represents the conjugate of 2 − 3i?", options: ["(2, 3)", "(−2, 3)", "(2, −3)", "(−2, −3)"], answer: 0 },
  { id: "d-arg-3", conceptId: C1, stem: "What is the value of i²?", options: ["1", "−1", "i", "−i"], answer: 1 },
  { id: "d-rts-1", conceptId: C2, stem: "What is the discriminant of x² − 4x + 5?", options: ["−4", "4", "36", "−36"], answer: 0 },
  { id: "d-rts-2", conceptId: C2, stem: "The roots of x² + 6x + 9 = 0 are:", options: ["real and equal", "real and distinct", "non-real", "cannot be determined"], answer: 0 },
  { id: "d-rts-3", conceptId: C2, stem: "The roots of x² + x + 1 = 0 are:", options: ["real and equal", "real and distinct", "non-real complex", "rational"], answer: 2 },
  { id: "d-frm-1", conceptId: C3, stem: "A monic quadratic with roots 2 and 3 is:", options: ["x² − 5x + 6", "x² + 5x + 6", "x² − 6x + 5", "x² − x + 6"], answer: 0 },
  { id: "d-frm-2", conceptId: C3, stem: "The sum of the roots of x² − 7x + 10 = 0 is:", options: ["7", "−7", "10", "−10"], answer: 0 },
  { id: "d-frm-3", conceptId: C3, stem: "The product of the roots of 2x² + 3x − 4 = 0 is:", options: ["−2", "2", "−4", "3/2"], answer: 0 },
];
export const itemsFor = (conceptId: string) => ITEMS.filter((i) => i.conceptId === conceptId);
