import { z } from "zod";
import { apiFetch } from "./http";

export const ReportSchema = z
  .object({
    student_id: z.string(),
    language: z.enum(["hi", "en"]),
    month: z.string(),
    body: z.string(),
    verified: z.boolean(),
    checks: z.array(z.object({ id: z.string(), label: z.string().optional(), passed: z.boolean() })),
    source: z.string(),
    llm_requested: z.boolean().nullish(),
    llm_available: z.boolean().nullish(),
    fallback_used: z.boolean().nullish(),
    fallback_reason: z.string().nullable().optional(),
    hi_reviewed: z.boolean().nullish(),
    latency_ms: z.number().nullish(),
  })
  .passthrough();
export type GeneratedReport = z.infer<typeof ReportSchema>;

export const generateReport = async (studentId: string, language: "hi" | "en", use_llm: boolean) =>
  ReportSchema.parse(await apiFetch(`/students/${studentId}/reports`, { method: "POST", json: { language, use_llm } }));
