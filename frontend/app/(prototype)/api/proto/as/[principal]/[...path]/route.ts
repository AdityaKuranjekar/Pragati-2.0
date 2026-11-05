// Forwards allow-listed calls to the prototype API with the stub token of the named principal. The
// browser never holds a token or the API host. STUB: stands in for real sign-in (not built).
import { NextRequest, NextResponse } from "next/server";
import { apiBase, tokens } from "../../../_env";

export const dynamic = "force-dynamic";

const ID = "[A-Za-z0-9_.-]{1,128}";
const ALLOWED: { method: string; re: RegExp }[] = [
  { method: "GET", re: new RegExp(`^api/prototype/health$`) },
  { method: "GET", re: new RegExp(`^api/prototype/cohorts/${ID}/bottlenecks$`) },
  { method: "GET", re: new RegExp(`^api/prototype/learners/${ID}/(state|next-step)$`) },
  { method: "POST", re: new RegExp(`^api/prototype/learners/${ID}/events$`) },
];

async function forward(req: NextRequest, { params }: { params: { principal: string; path: string[] } }) {
  const rel = params.path.join("/");
  if (!ALLOWED.some((a) => a.method === req.method && a.re.test(rel))) {
    return NextResponse.json({ detail: "route not available in the prototype" }, { status: 404 });
  }
  const base = apiBase();
  if (!base) return NextResponse.json({ detail: "PROTOTYPE_API_URL is not set." }, { status: 503 });
  const token = tokens()[params.principal];
  const isHealth = rel === "api/prototype/health";
  if (!token && !isHealth) return NextResponse.json({ detail: "no stub sign-in is configured for this role" }, { status: 403 });
  const search = req.nextUrl.search;
  let res: Response;
  try {
    res = await fetch(`${base}/${rel}${req.method === "GET" ? search : ""}`, {
      method: req.method,
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), "Content-Type": "application/json" },
      body: req.method === "POST" ? await req.text() : undefined,
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ detail: "The prototype API could not be reached." }, { status: 503 });
  }
  return new NextResponse(await res.text(), { status: res.status, headers: { "Content-Type": res.headers.get("content-type") ?? "application/json" } });
}

export { forward as GET, forward as POST };
