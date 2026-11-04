// The one place that talks HTTP. Token handling and the silent re-login on 401 live here.
// Switch the whole app between the mock and the FastAPI server with NEXT_PUBLIC_API_BASE
// (default "/api/mock"; real server: "http://127.0.0.1:8000/api/v1").
export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "/api/mock").replace(/\/$/, "");

export type Session = { token: string; institute: string; role: string; name: string };

const KEY = "pragati.session.v2";
let memory: Session | null = null;
let reauth: (() => Promise<void>) | null = null;

export function loadSession(): Session | null {
  if (memory) return memory;
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) memory = JSON.parse(raw) as Session;
  } catch {}
  return memory;
}
export function saveSession(s: Session | null) {
  memory = s;
  try {
    if (s) localStorage.setItem(KEY, JSON.stringify(s));
    else localStorage.removeItem(KEY);
  } catch {}
}
/** The auth provider registers how to get a fresh demo token; apiFetch calls it once on a 401. */
export function setReauth(fn: (() => Promise<void>) | null) {
  reauth = fn;
}

export class ApiError extends Error {
  constructor(public status: number, message: string, public fields?: Record<string, string>) {
    super(message);
  }
}

/** FastAPI sends {detail: string | [{loc, msg}]}; the mock sends the same. */
function detailOf(body: unknown, fallback: string): { message: string; fields?: Record<string, string> } {
  const d = (body as { detail?: unknown; error?: unknown } | null)?.detail ?? (body as { error?: unknown } | null)?.error;
  if (typeof d === "string") return { message: d };
  if (d && typeof d === "object" && !Array.isArray(d)) {
    const m = (d as { message?: unknown; msg?: unknown }).message ?? (d as { msg?: unknown }).msg;
    if (typeof m === "string") return { message: m };
  }
  if (Array.isArray(d)) {
    const fields: Record<string, string> = {};
    const parts = d.map((x: { loc?: unknown[]; msg?: string }) => {
      const key = String(x.loc?.[x.loc.length - 1] ?? "");
      if (key) fields[key] = x.msg ?? "invalid";
      return x.msg ?? "invalid";
    });
    return { message: parts.join("; "), fields };
  }
  return { message: fallback };
}

type Init = { method?: string; json?: unknown; form?: FormData; signal?: AbortSignal; auth?: boolean };

export async function apiFetch<T>(path: string, init: Init = {}, retried = false): Promise<T> {
  const headers: Record<string, string> = { accept: "application/json" };
  const s = loadSession();
  if (init.auth !== false && s) headers.authorization = `Bearer ${s.token}`;
  let body: BodyInit | undefined;
  if (init.form) body = init.form;
  else if (init.json !== undefined) {
    headers["content-type"] = "application/json";
    body = JSON.stringify(init.json);
  }
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { method: init.method ?? "GET", headers, body, signal: init.signal, cache: "no-store" });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, "Cannot reach the server");
  }
  const text = await res.text();
  let json: unknown = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {}
  if (!res.ok) {
    // demo token expired or the server restarted: get a new one silently and try once more
    if (res.status === 401 && init.auth !== false && !retried && reauth) {
      await reauth();
      return apiFetch<T>(path, init, true);
    }
    const d = detailOf(json, `HTTP ${res.status}`);
    throw new ApiError(res.status, d.message, d.fields);
  }
  return json as T;
}
