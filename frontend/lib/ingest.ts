import { z } from "zod";
import { apiFetch } from "./http";

export type Kind = "students" | "attendance" | "fees" | "results" | "answer-key";
export const KINDS: { id: Kind; en: string; hi: string; hint_en: string; hint_hi: string }[] = [
  { id: "students", en: "Students", hi: "विद्यार्थी", hint_en: "roll_no, name, dob, batch", hint_hi: "रोल नंबर, नाम, जन्म तिथि, बैच" },
  { id: "attendance", en: "Attendance", hi: "उपस्थिति", hint_en: "roll_no, date, present or %", hint_hi: "रोल नंबर, तिथि, उपस्थित या %" },
  { id: "fees", en: "Fees", hi: "फ़ीस", hint_en: "roll_no, amount, due date", hint_hi: "रोल नंबर, राशि, देय तिथि" },
  { id: "results", en: "Test results", hi: "टेस्ट परिणाम", hint_en: "roll_no, test, marks", hint_hi: "रोल नंबर, टेस्ट, अंक" },
  { id: "answer-key", en: "Answer key", hi: "उत्तर-कुंजी", hint_en: "question, answer", hint_hi: "प्रश्न, उत्तर" },
];

const Column = z.object({
  source: z.string(),
  target: z.string().nullable(),
  confidence: z.number(),
  alternatives: z.array(z.object({ target: z.string(), confidence: z.number() })).default([]),
});
const RowError = z.object({
  row: z.number(),
  column: z.string(),
  code: z.string(),
  severity: z.enum(["error", "warning"]),
  value: z.string(),
  message_en: z.string(),
  message_hi: z.string().optional(),
});
export const JobSchema = z
  .object({
    job_id: z.string(),
    kind: z.string(),
    filename: z.string(),
    status: z.enum(["preview", "running", "done", "failed"]),
    stage: z.string(),
    progress: z.number(),
    error: z.string().nullable().optional(),
    row_count: z.number(),
    accepted_count: z.number(),
    error_count: z.number(),
    warning_count: z.number().default(0),
    rejected_rows: z.number().default(0),
    columns: z.array(Column),
    targets: z.array(z.object({ id: z.string(), required: z.boolean(), label_en: z.string(), label_hi: z.string().optional() })),
    missing_required: z.array(z.string()).default([]),
    one_of: z.array(z.string()).nullable().optional(),
    one_of_missing: z.boolean().default(false),
    can_commit: z.boolean(),
    errors: z.array(RowError),
    errors_truncated: z.boolean().default(false),
    sample_rows: z.array(z.record(z.string())).default([]),
    redirect: z.string().nullable().optional(),
  })
  .passthrough();
export type Job = z.infer<typeof JobSchema>;

const parse = <S extends z.ZodTypeAny>(s: S, x: unknown): z.output<S> => s.parse(x);

export async function uploadFile(kind: Kind, file: File): Promise<Job> {
  const form = new FormData();
  form.append("file", file);
  return parse(JobSchema, await apiFetch(`/ingest/${kind}`, { method: "POST", form }));
}
export async function getJob(id: string): Promise<Job> {
  return parse(JobSchema, await apiFetch(`/ingest/jobs/${id}`));
}
export async function setMapping(id: string, mapping: Record<string, string | null>): Promise<Job> {
  return parse(JobSchema, await apiFetch(`/ingest/jobs/${id}/mapping`, { method: "POST", json: { mapping } }));
}
export async function commitJob(id: string): Promise<Job> {
  return parse(JobSchema, await apiFetch(`/ingest/jobs/${id}/commit`, { method: "POST", json: {} }));
}

// ---- OMR (shapes follow backend/app/omr/reader.py OmrResult.to_dict) ----
export const OmrSchema = z
  .object({
    job_id: z.string(),
    status: z.enum(["review", "retake", "done"]),
    filename: z.string(),
    result: z
      .object({
        layout_name: z.string().nullable(),
        roll_no: z.string().nullable(),
        roll_confidence: z.number(),
        quality: z.object({ ok: z.boolean(), retake: z.boolean(), reason: z.string().nullable() }).passthrough(),
        questions: z.record(z.object({ question_no: z.number(), answer: z.string().nullable(), status: z.string(), confidence: z.number() }).passthrough()),
        uncertain: z.array(z.object({ question_no: z.number().nullable(), label: z.string(), reason: z.string(), fill: z.number() }).passthrough()),
      })
      .passthrough(),
  })
  .passthrough();
export type OmrJob = z.infer<typeof OmrSchema>;
export const OmrDone = z.object({
  status: z.literal("done"),
  roll_no: z.string().nullable(),
  scored: z.record(z.number()),
  redirect: z.string().nullable().optional(),
});
export type OmrDoneT = z.infer<typeof OmrDone>;

export const uploadOmr = async (file: File): Promise<OmrJob> => {
  const form = new FormData();
  form.append("file", file);
  return parse(OmrSchema, await apiFetch("/ingest/omr", { method: "POST", form }));
};
export const confirmOmr = async (id: string, corrections: Record<string, string>): Promise<OmrDoneT> =>
  parse(OmrDone, await apiFetch(`/ingest/omr/${id}/confirm`, { method: "POST", json: { corrections } }));
