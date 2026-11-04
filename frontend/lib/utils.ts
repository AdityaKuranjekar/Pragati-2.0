import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export const cn = (...a: ClassValue[]) => twMerge(clsx(a));
export const pct = (v: number, d = 0) => `${(v * 100).toFixed(d)}%`;
export const byName = <T,>(get: (x: T) => string) => (a: T, b: T) => get(a).localeCompare(get(b));
export const fmtMonth = (m: string) => {
  const d = new Date(m.length === 7 ? `${m}-01` : m);
  return isNaN(+d) ? m : d.toLocaleDateString("en-IN", { month: "short", year: "numeric" });
};
