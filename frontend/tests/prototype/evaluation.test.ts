import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { buildEvaluation, verdictFor, type ResultFile } from "@/lib/prototype/evaluation";
import { EvaluationSchema } from "@/lib/prototype/schemas";

const dir = path.join(__dirname, "..", "..", "..", "ml", "evaluation", "results");
const load = (f: string) => JSON.parse(readFileSync(path.join(dir, f), "utf8")) as ResultFile;
const ev = buildEvaluation(load("e9_sim_v1_registered.json"), load("e9_sim_v1_1_posthoc.json"));

describe("verdictFor follows the pre-registered rule", () => {
  it("higher is better", () => {
    expect(verdictFor("higher", { mean: 1, lo: 0.2, hi: 1.5 }).verdict).toBe("pass");
    expect(verdictFor("higher", { mean: 0.1, lo: -0.2, hi: 0.4 }).verdict).toBe("miss");
    expect(verdictFor("higher", { mean: -1, lo: -1.5, hi: -0.2 }).verdict).toBe("miss");
  });
  it("lower is better", () => {
    expect(verdictFor("lower", { mean: -1, lo: -1.5, hi: -0.2 }).verdict).toBe("pass");
    expect(verdictFor("lower", { mean: 0.4, lo: 0.17, hi: 0.62 }).verdict).toBe("miss");
  });
});

describe("rows built from the committed result files", () => {
  it("match the schema and carry the SIM origin", () => {
    expect(EvaluationSchema.safeParse(ev).success).toBe(true);
    expect(ev.rows.length).toBe(32);
    expect(new Set(ev.rows.map((r) => r.origin))).toEqual(new Set(["SIM"]));
  });
  it("the two numbers the S2 log names as misses are present and marked miss (post-hoc, primary setting)", () => {
    const reached = ev.rows.find((r) => r.id === "posthoc:P_primary_neutral:reached_goal")!;
    const items = ev.rows.find((r) => r.id === "posthoc:P_primary_neutral:items_to_goal")!;
    expect(reached.verdict).toBe("miss");
    expect(reached.result).toContain("difference −0.12");
    expect(reached.interval).toBe("Difference 95% interval [−0.17, −0.07]");
    expect(reached.named_miss).toBe(true);
    expect(items.verdict).toBe("miss");
    expect(items.result).toContain("difference +0.40");
    expect(items.interval).toBe("Difference 95% interval [+0.17, +0.62]");
    expect(items.named_miss).toBe(true);
  });
  it("the primary claim passes in both runs and is flagged as primary", () => {
    for (const run of ["registered", "posthoc"]) {
      const r = ev.rows.find((x) => x.id === `${run}:P_primary_neutral:final_mastered`)!;
      expect(r.primary).toBe(true);
      expect(r.verdict).toBe("pass");
    }
  });
  it("both passes and misses exist, and nothing is dropped for being a miss", () => {
    expect(ev.rows.filter((r) => r.verdict === "miss").length).toBeGreaterThan(0);
    expect(ev.rows.filter((r) => r.verdict === "pass").length).toBeGreaterThan(0);
  });
});
