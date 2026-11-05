// Server-side configuration for the prototype routes. Nothing here reaches the browser.
//   PROTOTYPE_API_URL     base URL of the prototype API (for example http://127.0.0.1:8000). No default.
//   PROTOTYPE_TOKENS      JSON {"teacher": "<stub token>", "<learner id>": "<stub token>", ...}
//   PROTOTYPE_COHORT_ID   the cohort the teacher view reads
//   PROTOTYPE_ROSTER      JSON [{"id": "...", "label": "...", "origin": "DEMO FIXTURE" | "SIM"}]
// The API has no route that lists a cohort's learners, so the roster is configuration (see S4_LOG.md).
import { ConfigSchema } from "@/lib/prototype/schemas";

function json<T>(name: string): T | null {
  const raw = process.env[name];
  if (!raw) return null;
  try { return JSON.parse(raw) as T; } catch { return null; }
}

export function apiBase(): string | null {
  const u = process.env.PROTOTYPE_API_URL;
  return u ? u.replace(/\/+$/, "") : null;
}
export const tokens = () => json<Record<string, string>>("PROTOTYPE_TOKENS") ?? {};

export function readConfig() {
  const cohort = process.env.PROTOTYPE_COHORT_ID;
  const roster = json<unknown>("PROTOTYPE_ROSTER");
  if (!cohort || !roster) return null;
  const parsed = ConfigSchema.safeParse({ cohort_id: cohort, roster, principals: Object.keys(tokens()) });
  return parsed.success ? parsed.data : null;
}
