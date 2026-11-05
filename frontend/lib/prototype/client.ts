// Fetch wrapper. The browser talks only to this app's own routes (/api/proto/...), which forward to the
// prototype API with the stub token of the chosen principal. No host and no token is in browser code.
import type { ZodType } from "zod";
import {
  AttemptResultSchema, BottlenecksSchema, ConfigSchema, EvaluationSchema, LearnerStateSchema, NextStepSchema,
} from "./schemas";

export type ErrorKind = "denied" | "notfound" | "refused" | "unavailable" | "shape";
export class ProtoError extends Error {
  constructor(public kind: ErrorKind, message: string, public status = 0) {
    super(message);
  }
}

const BASE = "/api/proto";

async function call<T>(url: string, schema: ZodType<T>, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, { cache: "no-store", ...init });
  } catch {
    throw new ProtoError("unavailable", "The service could not be reached.");
  }
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) {
    const detail = typeof (body as { detail?: unknown })?.detail === "string" ? (body as { detail: string }).detail : `Request failed (${res.status}).`;
    if (res.status === 401 || res.status === 403) throw new ProtoError("denied", detail, res.status);
    if (res.status === 404) throw new ProtoError("notfound", detail, res.status);
    if (res.status === 409 || res.status === 422) throw new ProtoError("refused", detail, res.status);
    throw new ProtoError("unavailable", detail, res.status);
  }
  const parsed = schema.safeParse(body);
  if (!parsed.success) throw new ProtoError("shape", "The service returned data in an unexpected shape.", res.status);
  return parsed.data;
}

const api = (principal: string, path: string) => `${BASE}/as/${encodeURIComponent(principal)}/api/prototype/${path}`;

export const getConfig = () => call(`${BASE}/config`, ConfigSchema);
export const getEvaluation = () => call(`${BASE}/evaluation`, EvaluationSchema);
export const getBottlenecks = (principal: string, cohortId: string) =>
  call(api(principal, `cohorts/${encodeURIComponent(cohortId)}/bottlenecks`), BottlenecksSchema);
export const getState = (principal: string, learnerId: string) =>
  call(api(principal, `learners/${encodeURIComponent(learnerId)}/state`), LearnerStateSchema);
export const getNextStep = (principal: string, learnerId: string) =>
  call(api(principal, `learners/${encodeURIComponent(learnerId)}/next-step`), NextStepSchema);

export function newEventId(): string {
  const c = globalThis.crypto as Crypto | undefined;
  return c?.randomUUID ? c.randomUUID() : `ev-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
export const postAttempt = (principal: string, learnerId: string, a: { event_id: string; concept_id: string; item_id: string; correct: boolean }) =>
  call(api(principal, `learners/${encodeURIComponent(learnerId)}/events`), AttemptResultSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(a),
  });
