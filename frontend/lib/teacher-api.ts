import { z } from "zod";
import { apiFetch } from "./http";
import { RiskSchema } from "./types";

const Test = z.object({ test_id: z.string(), name: z.string(), date: z.string().optional(), question_count: z.number().optional() });
export const TestsSchema = z.object({ batch_id: z.string(), tests: z.array(Test) });

export const FlaggedSchema = z.object({
  test_id: z.string(),
  flagged: z.array(
    z
      .object({
        question_no: z.number(),
        subject: z.string().optional(),
        current_key: z.string(),
        suggested_key: z.string(),
        reason_code: z.string(),
        share_top_group_chose_suggested: z.number().optional(),
        share_chose_current_key: z.number().optional(),
        n_students: z.number().optional(),
        status: z.enum(["open", "fixed"]),
        fixed_at: z.string().nullable().optional(),
      })
      .passthrough()
  ),
});
export type Flagged = z.infer<typeof FlaggedSchema>["flagged"][number];

const FixResult = z.object({ test_id: z.string(), question_no: z.number(), key: z.string(), rescored_students: z.number(), recompute_ms: z.number(), flagged: FlaggedSchema.shape.flagged });

const AttendanceResult = z
  .object({
    student_id: z.string(),
    attendance_pct: z.number(),
    track: z.string(),
    effect: z.enum(["model", "rule_only", "none"]),
    on_support_list: z.boolean().optional(),
    recompute_ms: z.number().optional(),
    message_en: z.string(),
    message_hi: z.string().optional(),
    support_list: RiskSchema.optional(),
  })
  .passthrough();
export type AttendanceResult = z.infer<typeof AttendanceResult>;

export const getTests = async (batch: string) => TestsSchema.parse(await apiFetch(`/batches/${encodeURIComponent(batch)}/tests`));
export const getFlagged = async (test: string) => FlaggedSchema.parse(await apiFetch(`/tests/${encodeURIComponent(test)}/flagged-questions`));
export const fixKey = async (test: string, q: number, key: string) =>
  FixResult.parse(await apiFetch(`/answer-keys/${encodeURIComponent(test)}/${q}`, { method: "POST", json: { key } }));
export const patchAttendance = async (studentId: string, attendance_pct: number) =>
  AttendanceResult.parse(await apiFetch(`/students/${studentId}/attendance`, { method: "PATCH", json: { attendance_pct } }));
