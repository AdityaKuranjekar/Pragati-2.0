import { z } from "zod";
import { apiFetch } from "./http";

const Metrics = z.object({ auc: z.number().nullable(), precision: z.number().nullable(), recall: z.number().nullable(), lead_time_days: z.number().nullable() });
export const TierSchema = z
  .object({
    tier: z.enum(["full", "academic_only"]),
    options: z.array(z.object({ tier: z.enum(["full", "academic_only"]), label_en: z.string(), label_hi: z.string().optional(), metrics: Metrics })),
    minors_always_academic: z.boolean(),
    list_size: z.number(),
    capacity_per_week: z.number().nullable(),
    origin: z.string().optional(),
    note: z.string().optional(),
  })
  .passthrough();
export type Tier = z.infer<typeof TierSchema>;

export const ConsentSchema = z.object({
  consent_id: z.string(),
  student_id: z.string(),
  roll_no: z.string(),
  guardian_display: z.string(),
  kind: z.enum(["parental", "self"]),
  method: z.string(),
  date: z.string(),
  status: z.enum(["active", "withdrawn"]),
});
export type Consent = z.infer<typeof ConsentSchema>;
export const LedgerSchema = z.object({ items: z.array(ConsentSchema), summary: z.object({ total: z.number(), active: z.number(), withdrawn: z.number() }) });

export const getTier = async () => TierSchema.parse(await apiFetch("/settings/privacy-tier"));
export const putTier = async (tier: Tier["tier"]) => TierSchema.parse(await apiFetch("/settings/privacy-tier", { method: "PUT", json: { tier } }));
export const getConsents = async (q = "") => LedgerSchema.parse(await apiFetch(`/consents${q ? `?q=${encodeURIComponent(q)}` : ""}`));
export const addConsent = async (roll_no: string, guardian_name: string, method: string) =>
  ConsentSchema.parse(await apiFetch("/consents", { method: "POST", json: { roll_no, guardian_name, method } }));
export const withdrawConsent = async (id: string) =>
  z.object({ effect: z.string() }).passthrough().parse(await apiFetch(`/consents/${encodeURIComponent(id)}`, { method: "DELETE" }));
