import { readFile } from "node:fs/promises";
import path from "node:path";
import { NextResponse } from "next/server";
import { buildEvaluation, type ResultFile } from "@/lib/prototype/evaluation";

export const dynamic = "force-dynamic";

// Reads the committed result files. process.cwd() is frontend/ for next dev and next start.
const DIR = process.env.PROTOTYPE_RESULTS_DIR ?? path.join(process.cwd(), "..", "ml", "evaluation", "results");

export async function GET() {
  try {
    const read = async (f: string) => JSON.parse(await readFile(path.join(DIR, f), "utf8")) as ResultFile;
    const [registered, posthoc] = await Promise.all([read("e9_sim_v1_registered.json"), read("e9_sim_v1_1_posthoc.json")]);
    return NextResponse.json(buildEvaluation(registered, posthoc));
  } catch {
    return NextResponse.json({ detail: "The result files could not be read." }, { status: 503 });
  }
}
