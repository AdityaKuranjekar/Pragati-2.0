import { NextResponse } from "next/server";
import { readConfig } from "../_env";

export const dynamic = "force-dynamic";

export function GET() {
  const cfg = readConfig();
  if (!cfg) return NextResponse.json({ detail: "The prototype is not configured: set PROTOTYPE_COHORT_ID, PROTOTYPE_ROSTER and PROTOTYPE_TOKENS." }, { status: 503 });
  return NextResponse.json(cfg);
}
