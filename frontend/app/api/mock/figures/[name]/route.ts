import fs from "node:fs/promises";
import { NextResponse } from "next/server";
import { findFigure } from "@/lib/server-data";

export const dynamic = "force-dynamic";

export async function GET(_req: Request, { params }: { params: { name: string } }) {
  if (!/^[a-z0-9_]+\.png$/.test(params.name)) return NextResponse.json({ error: "bad name" }, { status: 400 });
  const p = await findFigure(params.name);
  if (!p) return NextResponse.json({ error: "not found" }, { status: 404 });
  const buf = await fs.readFile(p);
  return new NextResponse(new Uint8Array(buf), { headers: { "content-type": "image/png" } });
}
