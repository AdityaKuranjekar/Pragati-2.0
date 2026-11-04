import fs from "node:fs/promises";
import path from "node:path";

// Where the mock API finds the ML artifacts. Order: ARTIFACTS_DIR env, ../ml/artifacts, ../../ml/artifacts.
function roots(): string[] {
  const out: string[] = [];
  if (process.env.ARTIFACTS_DIR) out.push(process.env.ARTIFACTS_DIR);
  out.push(path.resolve(process.cwd(), "..", "ml", "artifacts"));
  return out;
}

async function exists(p: string) {
  try {
    await fs.access(p);
    return true;
  } catch {
    return false;
  }
}

/** institute = null for global files (moat, scaling, models, metrics). Falls back to samples/. */
export async function findArtifact(institute: string | null, file: string): Promise<string | null> {
  for (const root of roots()) {
    const real = institute ? path.join(root, institute, `${file}.json`) : path.join(root, `${file}.json`);
    if (await exists(real)) return real;
    const sample = institute
      ? path.join(root, "samples", institute, `${file}.json`)
      : path.join(root, "samples", `${file}.json`);
    if (await exists(sample)) return sample;
  }
  return null;
}

export async function findFigure(name: string): Promise<string | null> {
  for (const root of roots()) {
    const p = path.join(root, "figures", name);
    if (await exists(p)) return p;
  }
  return null;
}
