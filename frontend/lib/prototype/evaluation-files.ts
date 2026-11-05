// Server side only: reads the committed result files from ml/evaluation/results/. A missing or unreadable
// file is reported as such and shows as "not computed"; it is never read as zero.
import { readFile } from "node:fs/promises";
import path from "node:path";
import { composeEvaluation, parseResultText, type LoadedFile, type LoadedFiles } from "./evaluation";
import type { Evaluation } from "./schemas";

export const RESULT_FILES = [
  "e9_sim_v1_registered.json",
  "e9_sim_v1_1_posthoc.json",
  "e3_recovery_v1.json",
  "e1_assistments_v1.json",
  "e2_oulad_v1.json",
  "e4_root_cause_v1.json",
  "e6_relevance_v1.json",
];

export async function readResultFile(dir: string, name: string): Promise<LoadedFile> {
  let text: string;
  try {
    text = await readFile(path.join(dir, name), "utf8");
  } catch (err) {
    const code = (err as NodeJS.ErrnoException).code;
    return code === "ENOENT" ? { status: "missing" } : { status: "unreadable", error: code ?? "read error" };
  }
  try {
    return { status: "ok", data: parseResultText(text) };
  } catch {
    return { status: "unreadable", error: "not valid JSON" };
  }
}

export async function loadEvaluation(dir: string): Promise<Evaluation> {
  const files: LoadedFiles = {};
  await Promise.all(RESULT_FILES.map(async (f) => { files[f] = await readResultFile(dir, f); }));
  return composeEvaluation(files);
}
