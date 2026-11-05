// What the prototype UI reads from the S3 API, as zod schemas. Every field the UI touches is listed
// here, and the contract test (tests/prototype/contract.test.ts) parses real API responses with
// these same schemas, so a field the API does not return fails the test. Unknown fields are allowed.
import { z } from "zod";

export const BANDS = ["insufficient", "mastered", "uncertain", "unmastered"] as const;
export const BandSchema = z.enum(BANDS);

export const ConceptStateSchema = z.object({
  concept_id: z.string(),
  band: BandSchema,
  p_known: z.number(),
  uncertainty: z.number(),
  evidence_count: z.number().int(),
});

export const LearnerStateSchema = z.object({
  learner_id: z.string(),
  goal: z.string(),
  concepts: z.array(ConceptStateSchema),
  uncertainty_note: z.string(),
  policy_version: z.string(),
});

export const BottleneckSchema = z.object({
  concept_id: z.string(),
  learners_blocked: z.number().int(),
  dependents: z.array(z.string()),
  edge_review: z.array(z.string()),
});

export const BottlenecksSchema = z.object({
  cohort_id: z.string(),
  learner_count: z.number().int(),
  bottlenecks: z.array(BottleneckSchema),
  policy_version: z.string(),
});

export const RecommendationSchema = z.object({
  action: z.string(),
  concept_id: z.string().nullable(),
  reason: z.string(),
  trace: z.object({
    chain: z.array(z.string()),
    n: z.record(z.number()),
    edge_review_status: z.string().optional(),
  }),
  policy_version: z.string(),
});

export const NextStepSchema = z.object({
  kind: z.string(),
  concept_id: z.string().nullable(),
  item_id: z.string().nullable(),
  reason: z.string(),
  recommendation: RecommendationSchema.nullable(),
  selection: z
    .object({ trace: z.object({ approved_in_pool: z.number().optional() }).passthrough() })
    .passthrough()
    .nullable(),
  demo_unapproved_allowed: z.boolean(),
  policy_version: z.string(),
});

export const AttemptResultSchema = z.object({
  event_id: z.string(),
  seq: z.number().int(),
  duplicate: z.boolean(),
});

// Served by the UI's own server routes (app/(prototype)/api/proto/config and /evaluation).
export const ORIGINS = ["DEMO FIXTURE", "SIM", "PUB", "EXP"] as const;
export const OriginSchema = z.enum(ORIGINS);
export const ConfigSchema = z.object({
  cohort_id: z.string(),
  roster: z.array(z.object({ id: z.string(), label: z.string(), origin: OriginSchema })),
  principals: z.array(z.string()),
});

export const EvalRowSchema = z.object({
  id: z.string(),
  run: z.string(),
  setting: z.string(),
  metric: z.string(),
  better: z.enum(["higher", "lower"]),
  primary: z.boolean(),
  task: z.string(),
  origin: OriginSchema,
  baseline: z.string(),
  result: z.string(),
  interval: z.string(),
  verdict: z.enum(["pass", "miss"]),
  verdict_detail: z.string(),
  named_miss: z.boolean(),
});
export const EvaluationSchema = z.object({
  runs: z.array(z.object({ id: z.string(), title: z.string(), note: z.string() })),
  rows: z.array(EvalRowSchema),
});

export type Band = z.infer<typeof BandSchema>;
export type ConceptState = z.infer<typeof ConceptStateSchema>;
export type LearnerState = z.infer<typeof LearnerStateSchema>;
export type Bottlenecks = z.infer<typeof BottlenecksSchema>;
export type NextStep = z.infer<typeof NextStepSchema>;
export type Config = z.infer<typeof ConfigSchema>;
export type Origin = z.infer<typeof OriginSchema>;
export type EvalRow = z.infer<typeof EvalRowSchema>;
export type Evaluation = z.infer<typeof EvaluationSchema>;
