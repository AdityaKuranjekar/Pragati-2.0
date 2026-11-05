import { readFileSync } from "node:fs";
import path from "node:path";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SetsTable, E3Table } from "@/components/prototype/evaluation";
import { E3_FILE, E9_FILES, composeEvaluation, e3Verdict, parseResultText, type LoadedFiles } from "@/lib/prototype/evaluation";
import { loadEvaluation } from "@/lib/prototype/evaluation-files";
import { EvaluationSchema } from "@/lib/prototype/schemas";

const RESULTS = path.join(__dirname, "..", "..", "..", "ml", "evaluation", "results");
const committed = (name: string) => ({ status: "ok" as const, data: JSON.parse(readFileSync(path.join(RESULTS, name), "utf8").replace(/\bNaN\b/g, "null")) });
const allMissing = (): LoadedFiles => ({});

describe("a missing file is 'not computed', never zero", () => {
  it("every set reads not computed when no file exists", () => {
    const ev = composeEvaluation(allMissing());
    expect(EvaluationSchema.safeParse(ev).success).toBe(true);
    expect(ev.sets.map((s) => s.id)).toEqual(["E1", "E2", "E3", "E4", "E6", "E9"]);
    for (const s of ev.sets) {
      expect(s.status).toBe("not computed");
      expect(s.rows).toEqual([]);
      expect(s.reason.length).toBeGreaterThan(10);
    }
    expect(ev.rows).toEqual([]);
  });

  it("E3 missing: the reason says the run has not happened, and no number is produced", () => {
    const e3 = composeEvaluation(allMissing()).sets.find((s) => s.id === "E3")!;
    expect(e3.status).toBe("not computed");
    expect(e3.reason).toMatch(/No result file/);
    expect(e3.rows.length).toBe(0);
  });

  it("E1, E2, E4 and E6 stay not computed even when nothing is missing from the E9 files", () => {
    const files: LoadedFiles = { [E9_FILES.registered]: committed(E9_FILES.registered), [E9_FILES.posthoc]: committed(E9_FILES.posthoc) };
    const ev = composeEvaluation(files);
    for (const id of ["E1", "E2", "E4", "E6"]) {
      const s = ev.sets.find((x) => x.id === id)!;
      expect(s.status).toBe("not computed");
      expect(s.rows).toEqual([]);
    }
    expect(ev.sets.find((s) => s.id === "E9")!.status).toBe("computed");
  });

  it("an unreadable E3 file says so; it does not show a result", () => {
    const ev = composeEvaluation({ [E3_FILE]: { status: "unreadable", error: "not valid JSON" } });
    const e3 = ev.sets.find((s) => s.id === "E3")!;
    expect(e3.status).toBe("not computed");
    expect(e3.reason).toMatch(/could not be read/);
  });

  it("a file with the wrong shape is refused, not shown", () => {
    const ev = composeEvaluation({ [E3_FILE]: { status: "ok", data: { nonsense: 1 } } });
    const e3 = ev.sets.find((s) => s.id === "E3")!;
    expect(e3.status).toBe("not computed");
    expect(e3.reason).toMatch(/expected shape/);
  });

  it("a file for a set with no reader in this build is not shown as a result", () => {
    const ev = composeEvaluation({ "e1_assistments_v1.json": { status: "ok", data: { anything: true } } });
    const e1 = ev.sets.find((s) => s.id === "E1")!;
    expect(e1.status).toBe("not computed");
    expect(e1.reason).toMatch(/no reader/);
  });
});

describe("the committed E3 file is read into rows with the pre-registered verdicts", () => {
  const ev = composeEvaluation({ [E3_FILE]: committed(E3_FILE) });
  const e3 = ev.sets.find((s) => s.id === "E3")!;

  it("is computed with one row per setting (32), all tagged SIM", () => {
    expect(e3.status).toBe("computed");
    expect(e3.origin).toBe("SIM");
    expect(e3.rows.length).toBe(32);
    expect(EvaluationSchema.safeParse(ev).success).toBe(true);
  });

  it("the 3-item rows are misses because a band is shown below 10 items", () => {
    const k3 = e3.rows.filter((r) => r.setting.endsWith("3 items per concept"));
    expect(k3.length).toBe(8);
    for (const r of k3) {
      expect(r.verdict).toBe("miss");
      expect(r.detail).toMatch(/band is shown with fewer than 10 items/);
    }
  });

  it("every 10- and 20-item row misses the r bar, and the engine is worse than the raw share baseline", () => {
    const big = e3.rows.filter((r) => /(10|20) items per concept/.test(r.setting));
    expect(big.length).toBe(16);
    for (const r of big) {
      expect(r.verdict).toBe("miss");
      expect(r.detail).toMatch(/^The r interval does not reach 0\.80/);
    }
    const first = big.find((r) => r.setting.startsWith("10 concepts, prerequisite depth 1, guessing 0.25, 10"))!;
    expect(first.result).toMatch(/^r 0\.67 \[0\.65, 0\.69\]/);
    expect(first.baseline).toMatch(/^Raw share correct: r 0\.82/);
  });

  it("renders the E3 table with the verdict text and no zero standing in for a missing value", () => {
    render(<E3Table rows={e3.rows} />);
    expect(screen.getAllByTestId("e3-row").length).toBe(32);
    expect(screen.getAllByTestId("e3-verdict").every((n) => /Miss|Pass|Descriptive/.test(n.textContent ?? ""))).toBe(true);
    expect(screen.getByRole("region", { name: "E3 mastery recovery results" })).toBeInTheDocument();
    expect(screen.getAllByText(/not defined/).length).toBeGreaterThan(0);   // precision at 3 items
  });
});

describe("rendering: not computed is written out, in the set table", () => {
  it("shows the status and the reason for each set, and no numeric result", () => {
    const ev = composeEvaluation(allMissing());
    render(<SetsTable sets={ev.sets} />);
    const rows = screen.getAllByTestId("set-row");
    expect(rows.length).toBe(6);
    for (const row of rows) {
      expect(within(row).getByTestId("set-status").textContent).toBe("not computed");
      expect(row.textContent ?? "").not.toMatch(/\b0\.00\b/);
    }
  });
});

describe("parsing and the verdict rule", () => {
  it("maps Python's NaN token to null so the file parses", () => {
    expect(parseResultText('{"a": {"mean": NaN, "lo": 0.5}}')).toEqual({ a: { mean: null, lo: 0.5 } });
  });

  it("applies the pre-registered coverage and r rules", () => {
    expect(e3Verdict(10, { mean: 0.9, lo: 0.85, hi: 0.95 }, { mean: 0.8, lo: 0.77, hi: 0.83 }, 1).verdict).toBe("pass");
    expect(e3Verdict(10, { mean: 0.9, lo: 0.85, hi: 0.95 }, { mean: 0.6, lo: 0.5, hi: 0.7 }, 1).verdict).toBe("miss");
    expect(e3Verdict(20, { mean: 0.7, lo: 0.6, hi: 0.8 }, { mean: 0.8, lo: 0.77, hi: 0.83 }, 1).verdict).toBe("miss");
    expect(e3Verdict(6, { mean: 0.9, lo: 0.85, hi: 0.95 }, { mean: 0.8, lo: 0.77, hi: 0.83 }, 0).verdict).toBe("descriptive");
  });
});

describe("the server loader reads only the named files", () => {
  it("a directory with no result files gives all sets not computed (no error)", async () => {
    const ev = await loadEvaluation(path.join(RESULTS, "does-not-exist"));
    expect(EvaluationSchema.safeParse(ev).success).toBe(true);
    expect(ev.sets.every((s) => s.status === "not computed")).toBe(true);
  });

  it("the real results folder gives E3 and E9 computed, and the rest not computed", async () => {
    const ev = await loadEvaluation(RESULTS);
    const status = Object.fromEntries(ev.sets.map((s) => [s.id, s.status]));
    expect(status).toEqual({ E1: "not computed", E2: "not computed", E3: "computed", E4: "not computed", E6: "not computed", E9: "computed" });
    expect(ev.rows.length).toBe(32);
  });
});
