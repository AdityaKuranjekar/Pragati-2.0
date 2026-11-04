import { apiFetch, API_BASE, ApiError } from "./http";
import { GLOBAL_FILES, SCHEMAS, type FileKey, type FileType } from "./types";

export { API_BASE };

// Artifact-shaped reads live at {base}/{institute|global}/{file}. If the FastAPI server uses a
// different path shape for these, change only urlFor.
const ALIAS: Partial<Record<FileKey, string>> = { owner: "/owner/dashboard", datacard: "/datacard", scaling: "/scaling", models: "/models" };
export function urlFor(file: FileKey, institute: string) {
  return ALIAS[file] ?? `/${GLOBAL_FILES.includes(file) ? "global" : institute}/${file}`;
}
export const figureUrl = (path: string) => `${API_BASE}/figures/${path.split("/").pop()}`;

export async function fetchFile<K extends FileKey>(file: K, institute: string): Promise<FileType<K>> {
  const json = await apiFetch<unknown>(urlFor(file, institute));
  const parsed = SCHEMAS[file].safeParse(json);
  if (!parsed.success) {
    const first = parsed.error.issues[0];
    throw new ApiError(502, `${file}: ${first.path.join(".")} ${first.message}`);
  }
  return parsed.data as FileType<K>;
}
