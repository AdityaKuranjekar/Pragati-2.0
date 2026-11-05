// Shapes copied from real API responses (see contract.test.ts, which checks them against the live API).
import type { Bottlenecks, Config, LearnerState, NextStep } from "@/lib/prototype/schemas";

export const A = "jee.math.complex_numbers.algebra_complex_argand";
export const R = "jee.math.quadratic_equations.roots_nature";
export const F = "jee.math.quadratic_equations.equation_formation";

export const config: Config = {
  cohort_id: "cohort-demo",
  roster: [
    { id: "demo-a", label: "Learner A", origin: "DEMO FIXTURE" },
    { id: "demo-b", label: "Learner B", origin: "DEMO FIXTURE" },
    { id: "sim-01", label: "Sim 01", origin: "SIM" },
    { id: "sim-02", label: "Sim 02", origin: "SIM" },
  ],
  principals: ["teacher", "demo-a", "demo-b"],
};

export const state = (id: string, cells: [string, LearnerState["concepts"][number]["band"], number, number][]): LearnerState => ({
  learner_id: id, goal: F, uncertainty_note: "heuristic 1/sqrt(n+1); not a calibrated interval", policy_version: "policy-v0.1",
  concepts: cells.map(([concept_id, band, p_known, n]) => ({ concept_id, band, p_known, uncertainty: Math.round(10000 / Math.sqrt(n + 1)) / 10000, evidence_count: n })),
});

export const states = {
  "demo-a": state("demo-a", [[A, "mastered", 0.997, 5], [R, "unmastered", 0.2303, 3], [F, "insufficient", 0.1, 0]]),
  "demo-b": state("demo-b", [[A, "unmastered", 0.12, 3], [R, "insufficient", 0.1, 0], [F, "insufficient", 0.1, 0]]),
  "sim-01": state("sim-01", [[A, "uncertain", 0.62, 4], [R, "insufficient", 0.1, 1], [F, "insufficient", 0.1, 0]]),
  "sim-02": state("sim-02", [[A, "mastered", 0.95, 6], [R, "mastered", 0.9, 5], [F, "uncertain", 0.6, 3]]),
};

export const bottlenecks = (review = "proposed"): Bottlenecks => ({
  cohort_id: "cohort-demo", learner_count: 4, policy_version: "policy-v0.1",
  bottlenecks: [
    { concept_id: R, learners_blocked: 3, dependents: [F], edge_review: [review] },
    { concept_id: A, learners_blocked: 2, dependents: [R], edge_review: [review] },
  ],
});

export const nextStep = (over: Partial<NextStep> = {}): NextStep => ({
  kind: "none", concept_id: R, item_id: null,
  reason: "No unanswered approved items for this concept.",
  recommendation: {
    action: "review_prerequisite", concept_id: R, policy_version: "policy-v0.1",
    reason: "Nature of roots and discriminant is not yet mastered (23%, unmastered), and it is needed for Formation of quadratic equations. Review it first. This prerequisite link is proposed and not yet teacher-reviewed.",
    trace: { chain: [A, R, F], n: { [A]: 5, [R]: 3, [F]: 0 }, edge_review_status: "proposed" },
  },
  selection: { trace: { approved_in_pool: 0 } },
  demo_unapproved_allowed: false, policy_version: "policy-v0.1", ...over,
});

/** A fetch stub routing by URL suffix. Records every call. */
export function stubFetch(routes: Record<string, (init?: RequestInit) => { status?: number; body: unknown }>) {
  const calls: { url: string; method: string }[] = [];
  const fn = async (url: string, init?: RequestInit) => {
    calls.push({ url, method: init?.method ?? "GET" });
    const key = Object.keys(routes).find((k) => url.endsWith(k));
    if (!key) return new Response(JSON.stringify({ detail: `no stub for ${url}` }), { status: 500 });
    const r = routes[key](init);
    return new Response(JSON.stringify(r.body), { status: r.status ?? 200, headers: { "Content-Type": "application/json" } });
  };
  return { fn, calls };
}
