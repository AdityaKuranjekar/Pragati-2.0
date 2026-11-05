import path from "node:path";
import { NextResponse } from "next/server";
import { loadEvaluation } from "@/lib/prototype/evaluation-files";

export const dynamic = "force-dynamic";

// Reads the committed result files. process.cwd() is frontend/ for next dev and next start.
const DIR = process.env.PROTOTYPE_RESULTS_DIR ?? path.join(process.cwd(), "..", "ml", "evaluation", "results");

// A missing or unreadable file shows as "not computed" in the response; the route itself still answers 200.
export async function GET() {
  try {
    return NextResponse.json(await loadEvaluation(DIR));
  } catch {
    return NextResponse.json({ detail: "The evaluation could not be assembled." }, { status: 503 });
  }
}
