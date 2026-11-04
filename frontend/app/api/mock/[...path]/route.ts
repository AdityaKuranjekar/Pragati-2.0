import { NextResponse, type NextRequest } from "next/server";
import { handle } from "@/lib/mock/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

async function run(req: NextRequest, { params }: { params: { path: string[] } }) {
  const token = req.headers.get("authorization")?.replace(/^Bearer\s+/i, "") ?? null;
  const ct = req.headers.get("content-type") ?? "";
  let json: Record<string, unknown> | undefined;
  let form: FormData | undefined;
  try {
    if (ct.includes("multipart/form-data")) form = await req.formData();
    else if (ct.includes("json")) json = (await req.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ detail: "Could not read the request body" }, { status: 400 });
  }
  try {
    const r = await handle({ method: req.method, path: params.path, search: req.nextUrl.searchParams, token, json, form });
    return NextResponse.json(r.body, { status: r.status });
  } catch (e) {
    return NextResponse.json({ detail: `Mock server error: ${(e as Error).message}` }, { status: 500 });
  }
}
export { run as GET, run as POST, run as PUT, run as PATCH, run as DELETE };
