// Contract test: every field the UI reads (lib/prototype/schemas.ts) is present in the real API's
// responses. Starts the S3 API locally with demo data (e2e/api/serve_demo_api.py) and parses real
// responses with the UI's own schemas. If the API cannot start, this test FAILS; it is never skipped.
import { spawn, type ChildProcess } from "node:child_process";
import path from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import {
  AttemptResultSchema, BottlenecksSchema, LearnerStateSchema, NextStepSchema,
} from "@/lib/prototype/schemas";

const PORT = Number(process.env.CONTRACT_API_PORT ?? 8791);
const BASE = `http://127.0.0.1:${PORT}/api/prototype`;
const T = { teacher: "demo-teacher", a: "demo-learner-a", b: "demo-learner-b" };
const H = (tok: string) => ({ Authorization: `Bearer ${tok}` });
let proc: ChildProcess;

async function get(p: string, tok: string) {
  const r = await fetch(`${BASE}/${p}`, { headers: H(tok) });
  return { status: r.status, body: await r.json() };
}

beforeAll(async () => {
  proc = spawn("python3", [path.join(__dirname, "..", "..", "e2e", "api", "serve_demo_api.py"), String(PORT)], { stdio: "inherit" });
  for (let i = 0; i < 60; i++) {
    try { if ((await fetch(`${BASE}/health`)).ok) return; } catch { /* not up yet */ }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error("The prototype API did not start; run: pip install -r backend/app/api_prototype/requirements.txt uvicorn");
});
afterAll(() => { proc?.kill(); });

describe("API response shapes carry every field the UI reads", () => {
  it("health", async () => {
    const r = await get("health", "");
    expect(r.body).toMatchObject({ status: "ok", policy_version: expect.any(String) });
  });
  it("cohort bottlenecks (teacher)", async () => {
    const r = await get("cohorts/cohort-demo/bottlenecks", T.teacher);
    expect(r.status).toBe(200);
    const p = BottlenecksSchema.parse(r.body);
    expect(p.bottlenecks.length).toBeGreaterThan(0);
    for (const b of p.bottlenecks) expect(b.edge_review).toHaveLength(b.dependents.length);
  });
  it.each(["demo-a", "demo-b", "sim-01", "sim-02", "sim-03", "sim-04", "sim-05", "sim-06"])("state of %s (teacher)", async (id) => {
    const r = await get(`learners/${id}/state`, T.teacher);
    expect(r.status).toBe(200);
    expect(LearnerStateSchema.parse(r.body).concepts.length).toBeGreaterThan(0);
  });
  it.each([["demo-a", T.a], ["demo-b", T.b]])("next-step of %s (learner)", async (id, tok) => {
    const r = await get(`learners/${id}/next-step`, tok);
    expect(r.status).toBe(200);
    const p = NextStepSchema.parse(r.body);
    expect(p.recommendation).not.toBeNull();
    expect(p.recommendation!.trace.chain.length).toBeGreaterThan(0);
    expect(p.item_id).toBeNull();                       // the bank is not approved: nothing is served
    expect(p.selection!.trace.approved_in_pool).toBe(0);
  });
  it("next-step read by a teacher has the same shape", async () => {
    const r = await get("learners/demo-a/next-step", T.teacher);
    expect(NextStepSchema.safeParse(r.body).success).toBe(true);
  });
  it("an attempt is refused, with the detail string the UI shows", async () => {
    const r = await fetch(`${BASE}/learners/demo-a/events`, {
      method: "POST", headers: { ...H(T.a), "Content-Type": "application/json" },
      body: JSON.stringify({ event_id: "contract-1", concept_id: "jee.math.quadratic_equations.roots_nature", item_id: "roots_nature-easy-0", correct: true }),
    });
    expect(r.status).toBe(422);
    expect(typeof (await r.json()).detail).toBe("string");
  });
  it("the accepted-attempt shape the client parses is a subset of what the engine tests assert", () => {
    expect(AttemptResultSchema.safeParse({ event_id: "e", seq: 1, duplicate: false, day: 1, concepts: [], policy_version: "x" }).success).toBe(true);
  });
  it("a teacher cannot write: 403 with a detail string", async () => {
    const r = await fetch(`${BASE}/learners/demo-a/events`, {
      method: "POST", headers: { ...H(T.teacher), "Content-Type": "application/json" },
      body: JSON.stringify({ event_id: "contract-2", concept_id: "x", item_id: "y", correct: true }),
    });
    expect(r.status).toBe(403);
    expect(typeof (await r.json()).detail).toBe("string");
  });
  it("401 without a token", async () => {
    expect((await fetch(`${BASE}/learners/demo-a/state`)).status).toBe(401);
  });
});
