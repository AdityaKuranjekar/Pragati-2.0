import { z } from "zod";

// One schema per artifact file. Mirrors ml/artifacts/<institute>/*.json.
// Unknown extra fields are allowed (passthrough) so Tab 1 can add fields safely.
const base = {
  schema: z.string(),
  model_version: z.string().optional(),
  generated_at: z.string().optional(),
  institute_id: z.string().optional(),
  origin: z.string().optional(),
};
const bi = { text_en: z.string(), text_hi: z.string() };
const num = z.number();

export const MasterySchema = z
  .object({
    ...base,
    topics: z.array(
      z.object({
        topic_id: z.string(),
        name_en: z.string(),
        name_hi: z.string(),
        subject: z.string(),
        probably_untaught: z.boolean(),
      })
    ),
    batches: z.array(
      z.object({
        batch_id: z.string(),
        name: z.string(),
        exam: z.string(),
        class_level: z.string(),
        student_ids: z.array(z.string()),
      })
    ),
    cells: z.array(
      z.object({
        student_id: z.string(),
        topic_id: z.string(),
        theta: num,
        se: num,
        band: z.string(),
      })
    ),
    wrong_key_flags: z.array(z.record(z.unknown())),
  })
  .passthrough();
export type Mastery = z.infer<typeof MasterySchema>;

export const RiskSchema = z
  .object({
    ...base,
    capacity_per_week: num,
    operating_point: z.object({ precision: num, recall: num, lead_time_days: num }),
    list: z.array(
      z.object({
        student_id: z.string(),
        week: z.string(),
        priority_slot: num,
        track: z.string(),
        reasons: z.array(z.object({ code: z.string(), text_en: z.string(), text_hi: z.string(), weight: num })),
        supportive_action: z.object({ code: z.string(), ...bi }),
        consent_ok: z.boolean(),
        attendance_pct: num.optional(),
      })
    ),
    baselines: z.record(z.object({ precision: num, recall: num })),
    note: z.string().optional(),
  })
  .passthrough();
export type Risk = z.infer<typeof RiskSchema>;

export const PercentileSchema = z
  .object({
    ...base,
    coverage_target: num,
    students: z.array(
      z.object({ student_id: z.string(), exam: z.string(), low: num, mid: num, high: num, assumption: z.boolean() })
    ),
    mapping_table: z.array(z.object({ marks: num, percentile: num })).optional(),
    calibration: z.object({ empirical_coverage: num, mean_width: num }).optional(),
    note: z.string().optional(),
  })
  .passthrough();
export type Percentile = z.infer<typeof PercentileSchema>;

export const ReportsSchema = z
  .object({
    ...base,
    hi_reviewed: z.boolean(),
    reports: z.array(
      z.object({
        student_id: z.string(),
        language: z.string(),
        month: z.string(),
        body: z.string(),
        checks: z.array(z.object({ id: z.string(), passed: z.boolean() })),
        source: z.string().optional(),
        verified: z.boolean(),
      })
    ),
    summary: z.record(z.unknown()).optional(),
  })
  .passthrough();
export type Reports = z.infer<typeof ReportsSchema>;

const MetricCI = z.object({
  batch_id: z.string(),
  metric: z.string(),
  value: num,
  ci_low: num,
  ci_high: num,
  n: num,
  enough_data: z.boolean(),
});
export const OwnerSchema = z
  .object({
    ...base,
    batch_compare: z.array(MetricCI),
    faculty_compare: z.array(MetricCI.extend({ faculty_id: z.string().optional() }).passthrough()),
    faculty_note: z.string().optional(),
    retention: z.object({
      monthly: z.array(z.object({ month: z.string(), enrolled: num, dropped: num })),
      by_reason: z.record(num),
    }),
    roi: z.object({
      ratio_low: num,
      ratio_base: num,
      ratio_high: num,
      origin: z.string().optional(),
      note: z.string().optional(),
    }),
  })
  .passthrough();
export type Owner = z.infer<typeof OwnerSchema>;

export const StudentSchema = z
  .object({
    ...base,
    students: z.array(
      z.object({
        student_id: z.string(),
        display_name: z.string(),
        roll_no: z.string(),
        age_class: z.string(),
        exam: z.string(),
        language_pref: z.string(),
        streak_weeks: num,
        headline: z.object(bi),
        mastery_by_subject: z.array(z.object({ subject: z.string(), theta: num, trend: z.array(num) })),
        strengths: z.array(z.object({ topic_id: z.string(), name_en: z.string(), name_hi: z.string() })),
        focus_topics: z.array(
          z.object({
            topic_id: z.string(),
            name_en: z.string(),
            name_hi: z.string(),
            why_en: z.string().optional(),
            why_hi: z.string().optional(),
            est_minutes: num,
          })
        ),
        study_plan: z.array(
          z.object({ day: z.string(), task_en: z.string(), task_hi: z.string(), minutes: num })
        ),
        score_trend: z.array(z.object({ test: z.string(), marks: num })),
        percentile_range: z.object({ low: num, mid: num, high: num, assumption: z.boolean() }).nullable().optional(),
        milestones: z.array(z.object({ id: z.string(), ...bi })),
        support_contact: z.object({ counsellor_available: z.boolean(), ...bi }),
        trend_note: z.string().optional(),
      })
    ),
  })
  .passthrough();
export type StudentFile = z.infer<typeof StudentSchema>;
export type Student = StudentFile["students"][number];

export const ParentSchema = z
  .object({
    ...base,
    parents: z.array(
      z.object({
        student_id: z.string(),
        guardian_display: z.string(),
        language: z.string(),
        channel: z.string(),
        consent: z.object({ verified: z.boolean(), method: z.string(), date: z.string() }),
        monthly_summary: z.object({
          month: z.string(),
          attendance_pct: num,
          tests_taken: num,
          marks_trend: z.array(num),
          strongest_topic: z.string().nullable().optional(),
          focus_topic: z.string().nullable().optional(),
          fee: z.object({
            next_due_date: z.string().nullable(),
            amount_inr: num.nullable(),
            status: z.string(),
          }),
          what_you_can_do: z.array(z.object(bi)),
          next_meeting: z.unknown().nullable().optional(),
        }),
        whatsapp_messages: z.array(
          z
            .object({
              id: z.string(),
              type: z.string(),
              sent_at: z.string(),
              status: z.string(),
              body_en: z.string().optional(),
              body_hi: z.string().optional(),
            })
            .passthrough()
        ),
        notification_prefs: z.object({
          monthly_report: z.boolean(),
          fee_reminder: z.boolean(),
          meeting_invite: z.boolean(),
          quiet_hours: z.string().optional(),
        }),
        faq: z.array(z.record(z.unknown())),
      })
    ),
  })
  .passthrough();
export type ParentFile = z.infer<typeof ParentSchema>;
export type Parent = ParentFile["parents"][number];

export const DatacardSchema = z
  .object({
    ...base,
    story_steps: z.array(z.object({ id: num, title: z.string(), text: z.string() })),
    attributes: z.array(
      z.object({
        name: z.string(),
        entity: z.string(),
        real_world_source: z.string(),
        decision: z.string(),
        model: z.string(),
        privacy_class: z.string(),
      })
    ),
    checklist: z.array(
      z.object({ parameter: z.string(), our_value: z.string(), source: z.string(), confidence: z.string() })
    ),
    figures: z.array(z.object({ path: z.string(), caption: z.string(), origin: z.string() })),
    cleaning: z.object({
      rate: num.nullable(),
      examples: z.array(z.object({ raw: z.string(), clean: z.string() })),
      note: z.string().optional(),
    }),
    limits: z.array(z.string()),
  })
  .passthrough();
export type Datacard = z.infer<typeof DatacardSchema>;

export const MoatSchema = z
  .object({
    ...base,
    points: z.array(z.object({ n_institutes: num, calibration_error: num, ci_low: num, ci_high: num })),
    note: z.string().optional(),
  })
  .passthrough();
export type Moat = z.infer<typeof MoatSchema>;

export const ScalingSchema = z
  .object({
    ...base,
    stages: z.array(z.object({ name: z.string(), students: z.string(), stack: z.string() })),
    cost_per_student: z.array(z.object({ students: num, inr: num, lines: z.record(num) })),
    cost_note: z.string().optional(),
    failure_modes: z.array(z.object({ case: z.string(), response: z.string() })),
  })
  .passthrough();
export type Scaling = z.infer<typeof ScalingSchema>;

const RiskStat = z.object({ precision: num, recall: num }).passthrough();
export const ModelsSchema = z
  .object({
    ...base,
    irt: z.array(
      z
        .object({
          institute: z.string(),
          n_cells: num,
          theta_r_rasch: num,
          theta_r_rawpct: num,
          b_r: num,
          wrongkey_recall: num,
          wrongkey_precision: num,
          wrong_keys: num,
          flagged: num,
        })
        .passthrough()
    ),
    risk: z
      .object({
        academic_lgbm: RiskStat.extend({ auc: num, lead_time_days: num }),
        full_lgbm: RiskStat.extend({ auc: num, lead_time_days: num }),
        b2_ranked_attendance: RiskStat.extend({ auc: num, lead_time_days: num }),
        b1_attendance_rule: RiskStat,
        base_rate: num,
        ece_full: num,
      })
      .passthrough(),
  })
  .passthrough();
export type Models = z.infer<typeof ModelsSchema>;

export const MetricsSchema = z
  .object({
    model_version: z.string().optional(),
    results: z.array(
      z.object({
        metric_key: z.string(),
        module: z.string(),
        dataset_origin: z.string(),
        value: num,
        ci_low: num.nullable().optional(),
        ci_high: num.nullable().optional(),
        passed_bar: z.boolean().nullable().optional(),
        notes: z.string().nullable().optional(),
      })
    ),
  })
  .passthrough();
export type Metrics = z.infer<typeof MetricsSchema>;

export const SCHEMAS = {
  mastery: MasterySchema,
  risk: RiskSchema,
  percentile: PercentileSchema,
  reports: ReportsSchema,
  owner: OwnerSchema,
  student: StudentSchema,
  parent: ParentSchema,
  datacard: DatacardSchema,
  moat: MoatSchema,
  scaling: ScalingSchema,
  models: ModelsSchema,
  metrics: MetricsSchema,
} as const;
export type FileKey = keyof typeof SCHEMAS;
export type FileType<K extends FileKey> = z.infer<(typeof SCHEMAS)[K]>;
export const GLOBAL_FILES: FileKey[] = ["moat", "scaling", "models", "metrics"];

export const INSTITUTES = [
  { id: "patna_jee", label: "Patna JEE" },
  { id: "lucknow_neet", label: "Lucknow NEET" },
  { id: "gaya_both", label: "Gaya JEE+NEET" },
  { id: "kota_large", label: "Kota (large)" },
] as const;
