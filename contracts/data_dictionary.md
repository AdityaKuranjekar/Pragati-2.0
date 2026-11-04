<!--
Purpose: Comprehensive data dictionary for all PostgreSQL tables, enumerations, CSV templates, and synthetic parquet files.
contract_version: 1.0.0
Implements: TECH_PLAN §8 (Data model), §9 (Synthetic data generator), §10 (ML & routing), §12 (Data capture), and §15 (Privacy & DPDP).
-->

# DataMoat Data Dictionary (`contract_version: 1.0.0`)

## 1. Global Rules & Legal Derivations

- **Naming:** `snake_case` everywhere. Singular enum values.
- **Identifiers:** `uuid` (`gen_random_uuid()`) for entity primary keys, except human-facing `roll_no` (`text`, unique per `(institute_id, academic_year)`) and hierarchical `topics.id` slugs (e.g., `jee.phy.kinematics.projectile`).
- **Time & Timezone:** Calendar dates use ISO `YYYY-MM-DD` (`DATE`); instants use ISO-8601 with offset (`timestamptz`); business logic operates in `Asia/Kolkata` (IST).
- **Currency:** All monetary amounts are stored in integer **paise** (`amount_paise`, `paid_amount_paise`, `refund_due_paise`; `1 INR = 100 paise`), never floating-point numbers.
- **Dynamic `is_minor` Derivation & Re-Consent Rule at Age 18:**
  - `is_minor` is **not** a static boolean column; it is dynamically derived from `students.dob` at each evaluation date `as_of`:
    $$\text{is\_minor}(\text{dob}, \text{as\_of}) = (\text{age\_years}(\text{dob}, \text{as\_of}) < 18)$$
  - Under **DPDP Act 2023 s.9(1), s.9(3)**, and **DPDP Rules 2025 Rule 10**, while `is_minor` is `true`, processing requires verifiable parental consent (`verification_method` $\in$ `{in_person_id_check, otp_known_parent, digilocker_token}`) and model routing follows the minor rows of `contracts/routing_policy.yaml` (ML allowed only for `academic_support` on Tier A test features; `retention` and `fee` use transparent rules; Tier D engagement is strictly forbidden).
  - **18th Birthday Re-Consent Transition:** When a student reaches age 18 (`as_of >= dob + INTERVAL '18 years'`), guardian-granted minor consent no longer suffices for adult-tier processing. The student must grant personal consent (`guardian_id = NULL`, `verification_method = 'self_adult'`) before adult ML routing (`routing_policy.yaml` rows with `is_minor = false`) is activated.
- **Deliberately Excluded Data:** No counselling clinical notes, mental-health records, caste/religion attributes, government ID document images, student photographs, or public rank/leaderboard columns exist anywhere in the schema.

---

## 2. Canonical Enumerations (`contracts/enums.yaml`)

The table below is mechanically verified against `contracts/enums.yaml`, `contracts/schema.sql`, and `contracts/openapi.yaml`.

| Enum Key | Allowed Values | Description |
|---|---|---|
| `role` | `owner`, `admin`, `teacher`, `mentor`, `parent`, `student` | User role within an institute controlling RBAC and response field filtering. |
| `class_level` | `class_11`, `class_12`, `dropper` | Student academic cohort or class level. |
| `exam` | `jee_main`, `neet_ug` | Target competitive entrance examination. |
| `institute_exam_focus` | `jee_main`, `neet_ug`, `mix` | Primary entrance exam focus of a coaching institute. |
| `city_tier` | `tier_1`, `tier_2`, `tier_3` | Indian urban tier classification of the institute's city. |
| `institute_plan` | `starter`, `standard`, `pro` | Subscription plan tier of the coaching institute. |
| `student_status` | `active`, `left`, `transferred` | Current enrolment lifecycle status of a student. |
| `gender` | `female`, `male`, `other`, `prefer_not_to_say` | Student gender for fairness slice reporting. |
| `fee_plan` | `upfront_full`, `standard_3_instalment`, `rajasthan_4_equal`, `custom_scholarship` | Tuition fee payment schedule plan chosen at admission. |
| `guardian_relation` | `father`, `mother`, `legal_guardian`, `self` | Relationship of the consenting adult guardian to the student. |
| `response_status` | `answered`, `blank`, `multi_marked`, `unreadable` | Capture and grading state of an individual question response. |
| `q_type` | `mcq_single`, `mcq_multi`, `numeric` | Question format type. |
| `partial_rule` | `none`, `full_marks_if_any_accepted`, `proportional_no_negative` | Rule for awarding marks on multi-correct or dropped questions. |
| `dropped_question_rule` | `full_marks_all`, `full_marks_attempted_only` | Scoring policy when an item is officially dropped from a test. |
| `test_source` | `omr`, `csv`, `online` | Data ingestion channel through which test responses or marks arrived. |
| `attendance_source` | `csv`, `manual`, `biometric` | Source channel for daily student attendance records. |
| `consent_purpose` | `analytics`, `risk_alerts`, `parent_reports`, `benchmarking`, `engagement_tracking` | Granular DPDP Act processing purpose requiring verifiable consent. |
| `verification_method` | `in_person_id_check`, `otp_known_parent`, `digilocker_token`, `self_adult` | DPDP Rule 10 identity and age verification method for consent. |
| `intervention_type` | `mentoring`, `counselling_referral`, `remedial_session`, `fee_plan_discussion`, `parent_call` | Supportive mentor action triggered by an early-warning alert. |
| `intervention_outcome` | `pending`, `completed_improved`, `completed_no_change`, `escalated_to_counsellor`, `parent_unreachable`, `declined` | Logged outcome of a completed supportive intervention. |
| `risk_target` | `academic_support`, `retention`, `fee` | Early-warning prediction or rule evaluation target. |
| `risk_band` | `low`, `watch`, `needs_support` | Supportive triage band assigned to a student. |
| `mastery_band` | `not_enough_data`, `building`, `steady`, `strong` | Categorical topic mastery band displayed when standard error is sufficiently small. |
| `trend_direction` | `improving`, `steady`, `declining` | Overall academic trajectory direction over the reporting window. |
| `feature_tier` | `A`, `B`, `C`, `D` | Privacy tier classification of model features (A=tests, B=attendance, C=fees, D=engagement). |
| `batch_change_reason` | `timing`, `subject_change`, `relocation`, `other` | Permitted administrative reason for transferring a student between batches (performance is deliberately absent per MoE cl. 12(vii)). |
| `ingest_type` | `students`, `guardians`, `results_responses`, `results_marks_only`, `answer_key`, `attendance`, `fees`, `omr_photos` | Category of data uploaded in an ingestion job. |
| `ingest_status` | `pending_mapping`, `preview_ready`, `awaiting_review`, `confirmed`, `failed` | Processing status of an upload ingestion job. |
| `report_path` | `llm`, `template` | Generation pathway used to produce a verified parent report. |
| `report_channel` | `none`, `whatsapp_preview`, `pdf_download`, `portal_view` | Delivery channel for parent progress reports. |
| `lang` | `en`, `hi` | ISO 639-1 language code supported by user interfaces and templates. |
| `tagger_source` | `human`, `embedding_llm`, `keyword_rule` | Origin of a question-to-topic mapping tag. |
| `item_fit_flag` | `ok`, `suspect_wrong_key`, `low_discrimination`, `too_few_responses` | IRT calibration diagnostic flag for a question item. |
| `day_of_week` | `monday`, `tuesday`, `wednesday`, `thursday`, `friday`, `saturday`, `sunday` | Day of the week in Asia/Kolkata calendar. |
| `routing_method` | `ml`, `rules`, `none` | Execution method permitted by purpose- and age-aware legal routing. |
| `audit_action` | `view_risk_scores`, `view_student_profile`, `export_register`, `update_legal_settings`, `update_privacy_tier`, `grant_consent`, `revoke_consent`, `update_answer_key`, `create_intervention`, `generate_report` | Audited security or privacy event type (retained >= 1 year per DPDP Rule 6). |

---

## 3. PostgreSQL 16 Database Tables (`contracts/schema.sql`)

### 3.1 Table: `institutes`
- **Produced by:** Agent A (DataGen), Agent J (Seed)
- **Consumed by:** Agent G (Backend), Agent H (Frontend)

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `id` | `uuid` | NO | UUID v4 | Primary key (tenant ID) | `99999999-8888-7777-6666-555555555555` |
| `name` | `text` | NO | Non-empty text | Institute display name | `Patna JEE Academy (Synthetic)` |
| `city` | `text` | NO | City name | Operating city | `Patna` |
| `city_tier` | `text` | NO | Enum `city_tier` | Urban tier classification | `tier_2` |
| `exam_focus` | `text` | NO | Enum `institute_exam_focus` | Primary entrance exam focus | `jee_main` |
| `plan` | `text` | NO | Enum `institute_plan` | SaaS subscription tier | `standard` |
| `weekly_off_day` | `text` | NO | Enum `day_of_week` | Mandatory weekly off day (MoE cl. 10.1(v)) | `sunday` |
| `counsellor_name` | `text` | YES | Free text | Name of onboarded psychologist/counsellor | `Dr. Meera Test` |
| `counsellor_contact` | `text` | YES | Phone/email | Helpline or contact info (MoE cl. 11(ii)) | `+91-9000000099` |
| `created_at` | `timestamptz` | NO | ISO-8601 | Creation timestamp | `2026-04-01T09:00:00+05:30` |

### 3.2 Table: `users`
- **Produced by:** Agent J (Seed), Agent G (Backend)
- **Consumed by:** Agent G (Backend), Agent H (Frontend)

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `id` | `uuid` | NO | UUID v4 | User primary key | `22222222-3333-4444-5555-666666666666` |
| `institute_id` | `uuid` | NO | FK `institutes.id` | Tenant identifier (RLS enforced) | `99999999-8888-7777-6666-555555555555` |
| `role` | `text` | NO | Enum `role` | RBAC role | `owner` |
| `phone` | `text` | NO | 10-digit string | Login phone number | `9000000000` |
| `name` | `text` | NO | Non-empty text | Full name | `Vikram Demo Owner` |
| `lang` | `text` | NO | Enum `lang` | Preferred UI language | `en` |
| `active` | `boolean` | NO | `true`/`false` | Whether user account is active | `true` |
| `created_at` | `timestamptz` | NO | ISO-8601 | Creation timestamp | `2026-04-01T09:00:00+05:30` |

### 3.3 Table: `legal_settings`
- **Produced by:** Agent G (Backend)
- **Consumed by:** Agent C (Risk), Agent G (Backend)

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `institute_id` | `uuid` | NO | PK / FK `institutes.id` | Tenant identifier (RLS enforced) | `99999999-8888-7777-6666-555555555555` |
| `minor_ml_risk_enabled` | `boolean` | NO | `true`/`false` | Legal flag enabling Tier A-B retention ML for minors | `false` |
| `active_feature_tier` | `text` | NO | Enum `feature_tier` | Highest feature privacy tier enabled by owner | `C` |
| `legal_opinion_ref` | `text` | YES | Document ref | Citation for legal counsel sign-off | `NULL` |
| `retention_months_after_leaving` | `integer` | NO | `1..84` | Months to retain student data after leaving | `12` |
| `updated_by` | `uuid` | YES | FK `users.id` | Actor who last updated settings | `22222222-3333-4444-5555-666666666666` |
| `updated_at` | `timestamptz` | NO | ISO-8601 | Last update timestamp | `2026-04-01T09:00:00+05:30` |

### 3.4 Table: `batches`
- **Produced by:** Agent A (DataGen), Agent G (Backend)
- **Consumed by:** Agent B, Agent C, Agent G, Agent H

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `id` | `uuid` | NO | UUID v4 | Batch primary key | `44444444-5555-6666-7777-888888888888` |
| `institute_id` | `uuid` | NO | FK `institutes.id` | Tenant identifier (RLS enforced) | `99999999-8888-7777-6666-555555555555` |
| `name` | `text` | NO | Non-empty text | Batch name (admission-order only) | `JEE-11-Morning-A` |
| `class_level` | `text` | NO | Enum `class_level` | Academic cohort | `class_11` |
| `exam` | `text` | NO | Enum `exam` | Target exam | `jee_main` |
| `academic_year` | `integer` | NO | `2020..2100` | Academic year start | `2026` |
| `start_date` | `date` | NO | `YYYY-MM-DD` | Course start date | `2026-04-15` |
| `published_capacity` | `integer` | NO | `> 0` | Published batch size cap (Rajasthan Act s.12(i)) | `60` |
| `mentor_capacity_per_week` | `integer` | NO | `> 0` | Weekly mentor check-in capacity k | `8` |
| `created_at` | `timestamptz` | NO | ISO-8601 | Creation timestamp | `2026-04-01T09:00:00+05:30` |

### 3.5 Table: `students`
- **Produced by:** Agent A (DataGen), Agent G (Ingest)
- **Consumed by:** All ML & Backend Agents

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `id` | `uuid` | NO | UUID v4 | Student primary key | `11111111-2222-3333-4444-555555555555` |
| `institute_id` | `uuid` | NO | FK `institutes.id` | Tenant identifier (RLS enforced) | `99999999-8888-7777-6666-555555555555` |
| `batch_id` | `uuid` | NO | FK `batches.id` | Assigned batch ID | `44444444-5555-6666-7777-888888888888` |
| `academic_year` | `integer` | NO | `2020..2100` | Academic year for roll_no uniqueness | `2026` |
| `roll_no` | `text` | NO | Non-empty text | Human-facing roll number | `PAT26-001` |
| `name` | `text` | NO | Non-empty text | Student name (Latin) | `Aarav Test` |
| `name_alt` | `text` | YES | Devanagari/alt text | Alternate/Devanagari student name | `आरव टेस्ट` |
| `dob` | `date` | NO | `YYYY-MM-DD` | Date of birth (used to derive `is_minor` at `as_of`) | `2009-05-14` |
| `gender` | `text` | NO | Enum `gender` | Student gender (for fairness auditing) | `male` |
| `join_date` | `date` | NO | `YYYY-MM-DD` | Enrolment date (checked for age >= 16) | `2026-04-15` |
| `status` | `text` | NO | Enum `student_status` | Enrolment status | `active` |
| `left_date` | `date` | YES | `YYYY-MM-DD` | Date of withdrawal if `status = 'left'` | `NULL` |
| `fee_plan` | `text` | NO | Enum `fee_plan` | Selected tuition instalment plan | `standard_3_instalment` |
| `out_of_town` | `boolean` | NO | `true`/`false` | Whether student is from outside the institute city | `false` |
| `created_at` | `timestamptz` | NO | ISO-8601 | Record creation timestamp | `2026-04-15T10:00:00+05:30` |

### 3.6 Table: `batch_changes`
- **Produced by:** Agent G (Backend)
- **Consumed by:** Agent C (Features), Agent G (Audit)

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `id` | `uuid` | NO | UUID v4 | Primary key | `12121212-3434-5656-7878-909090909090` |
| `institute_id` | `uuid` | NO | FK `institutes.id` | Tenant identifier (RLS enforced) | `99999999-8888-7777-6666-555555555555` |
| `student_id` | `uuid` | NO | FK `students.id` | Transferred student | `11111111-2222-3333-4444-555555555555` |
| `from_batch` | `uuid` | NO | FK `batches.id` | Origin batch | `44444444-5555-6666-7777-888888888888` |
| `to_batch` | `uuid` | NO | FK `batches.id` | Destination batch | `44444444-5555-6666-7777-888888888889` |
| `changed_at` | `timestamptz` | NO | ISO-8601 | Transfer timestamp | `2026-06-01T11:00:00+05:30` |
| `reason` | `text` | NO | Enum `batch_change_reason` | Non-performance transfer reason (MoE cl. 12(vii)) | `timing` |
| `by_user` | `uuid` | NO | FK `users.id` | Admin/owner who authorized transfer | `22222222-3333-4444-5555-666666666666` |

### 3.7 Table: `guardians`
- **Produced by:** Agent A (DataGen), Agent G (Ingest)
- **Consumed by:** Agent G (Backend), Agent E (GenAI)

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `id` | `uuid` | NO | UUID v4 | Guardian primary key | `77777777-6666-5555-4444-333333333333` |
| `institute_id` | `uuid` | NO | FK `institutes.id` | Tenant identifier (RLS enforced) | `99999999-8888-7777-6666-555555555555` |
| `student_id` | `uuid` | NO | FK `students.id` | Linked student (one phone can link to siblings) | `11111111-2222-3333-4444-555555555555` |
| `name` | `text` | NO | Non-empty text | Guardian full name | `Rajesh Test` |
| `phone` | `text` | NO | 10-digit string | Guardian phone number | `9000000001` |
| `relation` | `text` | NO | Enum `guardian_relation` | Relationship to student | `father` |
| `lang_pref` | `text` | NO | Enum `lang` | Preferred report language | `hi` |
| `created_at` | `timestamptz` | NO | ISO-8601 | Creation timestamp | `2026-04-15T10:00:00+05:30` |

### 3.8 Table: `consents`
- **Produced by:** Agent A (DataGen), Agent G (Backend)
- **Consumed by:** Agent G (Backend), Agent I (QA)

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `id` | `uuid` | NO | UUID v4 | Consent record primary key | `88888888-9999-0000-1111-222222222222` |
| `institute_id` | `uuid` | NO | FK `institutes.id` | Tenant identifier (RLS enforced) | `99999999-8888-7777-6666-555555555555` |
| `student_id` | `uuid` | NO | FK `students.id` | Student covered by consent | `11111111-2222-3333-4444-555555555555` |
| `guardian_id` | `uuid` | YES | FK `guardians.id` | Consenting parent (null if 18+ self-consent) | `77777777-6666-5555-4444-333333333333` |
| `purpose` | `text` | NO | Enum `consent_purpose` | Specific processing purpose | `parent_reports` |
| `verification_method` | `text` | NO | Enum `verification_method` | DPDP Rule 10 verification pathway | `in_person_id_check` |
| `verified_by_user_id` | `uuid` | YES | FK `users.id` | Staff member who checked ID at admission | `22222222-3333-4444-5555-666666666666` |
| `verified_at` | `timestamptz` | NO | ISO-8601 | Timestamp consent was verified | `2026-04-15T10:15:00+05:30` |
| `revoked_at` | `timestamptz` | YES | ISO-8601 | Timestamp consent was withdrawn (null if active) | `NULL` |
| `notice_version` | `text` | NO | Version string | Itemised DPDP Rule 3 notice version shown | `2026.1` |
| `notice_lang` | `text` | NO | Enum `lang` | Language in which notice was presented | `hi` |

### 3.9 Table: `topics`
- **Produced by:** Phase 0 Contracts (`topics.yaml`)
- **Consumed by:** All Agents

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `id` | `text` | NO | Hierarchical slug | Primary key slug | `jee.phy.kinematics.projectile` |
| `exam` | `text` | NO | Enum `exam` | Primary exam namespace | `jee_main` |
| `subject` | `text` | NO | Subject name | Subject (`Physics`, `Chemistry`, `Mathematics`, `Botany`, `Zoology`) | `Physics` |
| `chapter` | `text` | NO | Chapter name | Unit/chapter title | `Kinematics` |
| `topic` | `text` | NO | Topic name | Granular topic title | `Projectile Motion` |
| `name_en` | `text` | NO | English text | English display name | `Projectile Motion` |
| `name_hi` | `text` | NO | Devanagari text | Hindi display name | `प्रक्षेप्य गति` |
| `name_hi_reviewed` | `boolean` | NO | `true`/`false` | Whether native-Hindi educator reviewed `name_hi` against NCERT Hindi edition | `false` |
| `parent_id` | `text` | YES | FK `topics.id` | Parent node in taxonomy tree | `jee.phy.kinematics` |
| `class_level` | `text` | NO | Enum `class_level` | Standard syllabus class level | `class_11` |
| `syllabus_year` | `integer` | NO | `2026` | NTA syllabus year | `2026` |
| `weightage` | `double precision` | YES | `[0, 1]` or `NULL` | Exam weightage (null unless sourced) | `NULL` |
| `verified` | `boolean` | NO | `true`/`false` | Whether checked against official NTA PDF | `false` |

### 3.10 Table: `topic_prereqs`
- **Produced by:** Phase 0 Contracts (`topics.yaml`)
- **Consumed by:** Agent E (Study Plan), Agent B (Mastery)

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `topic_id` | `text` | NO | FK `topics.id` | Dependent chapter/topic slug | `jee.phy.laws_of_motion` |
| `prereq_topic_id` | `text` | NO | FK `topics.id` | Prerequisite chapter/topic slug | `jee.phy.kinematics` |

### 3.11 Table: `model_registry`
- **Produced by:** Agent B, Agent C, Agent J
- **Consumed by:** Agent G (Backend)

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `version` | `text` | NO | `vX.Y.Z` | Model bundle semantic version | `v1.0.0` |
| `trained_at` | `timestamptz` | NO | ISO-8601 | Training completion timestamp | `2026-10-20T18:00:00+05:30` |
| `data_version` | `text` | NO | Seed + hash | Training dataset provenance | `seed42_sha256_a1b2c3` |
| `metrics` | `jsonb` | NO | JSON (`metrics.schema.json`) | Embedded evaluation summary | `{}` |

### 3.12 Table: `marking_schemes`
- **Produced by:** Phase 0 Contracts (`marking_schemes.yaml`)
- **Consumed by:** Agent A, Agent G (Scoring)

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `id` | `text` | NO | Slug | Scheme identifier | `jee_main` |
| `name` | `text` | NO | Display name | Human-readable name | `JEE Main Official (+4 / -1 / 0)` |
| `correct` | `double precision` | NO | Marks | Marks awarded for correct response | `4.0` |
| `wrong` | `double precision` | NO | Marks | Penalty marks for wrong response | `-1.0` |
| `blank` | `double precision` | NO | Marks | Marks for unattempted question | `0.0` |
| `partial_rule` | `text` | NO | Enum `partial_rule` | Multi-correct scoring rule | `full_marks_if_any_accepted` |
| `dropped_rule` | `text` | NO | Enum `dropped_question_rule` | Dropped-question bonus rule | `full_marks_all` |

### 3.13 Table: `questions`
- **Produced by:** Agent A (DataGen), Agent G (Ingest)
- **Consumed by:** Agent B (IRT), Agent G

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `id` | `uuid` | NO | UUID v4 | Question primary key | `77777777-8888-9999-0000-111111111111` |
| `institute_id` | `uuid` | YES | FK `institutes.id` or `NULL` | `NULL` for shared public pool; UUID for tenant-private item (RLS enforced) | `NULL` |
| `subject` | `text` | NO | Subject name | Subject discipline | `Physics` |
| `text_hash` | `text` | NO | SHA-256 hex | Normalized question stem hash | `a1b2c3...` |
| `q_type` | `text` | NO | Enum `q_type` | Question format | `mcq_single` |
| `options_n` | `integer` | NO | `0..10` | Number of choices (`4` for MCQ, `0` for numeric) | `4` |
| `created_at` | `timestamptz` | NO | ISO-8601 | Creation timestamp | `2026-04-15T10:00:00+05:30` |

### 3.14 Table: `question_topics`
- **Produced by:** Agent A, Tagging Prep
- **Consumed by:** Agent B (IRT/Mastery), Agent G

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `institute_id` | `uuid` | YES | FK `institutes.id` or `NULL` | Must equal parent `questions.institute_id` (trigger + RLS enforced) | `NULL` |
| `question_id` | `uuid` | NO | FK `questions.id` | Question ID | `77777777-8888-9999-0000-111111111111` |
| `topic_id` | `text` | NO | FK `topics.id` | Mapped syllabus topic ID | `jee.phy.kinematics.projectile` |
| `weight` | `double precision` | NO | `(0, 1]` | Topic relevance weight | `1.0` |
| `tagged_by` | `text` | NO | Enum `tagger_source` | Provenance of topic tag | `human` |
| `confidence` | `double precision` | NO | `[0, 1]` | Tagging confidence score | `0.98` |
| `reviewed_by` | `uuid` | YES | FK `users.id` | Reviewer user ID if human-verified | `NULL` |

### 3.15 Table: `item_params`
- **Produced by:** Agent B (IRT)
- **Consumed by:** Agent B (Mastery), Agent G (Backend)

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `institute_id` | `uuid` | YES | FK `institutes.id` or `NULL` | Must equal parent `questions.institute_id` (trigger + RLS enforced) | `NULL` |
| `question_id` | `uuid` | NO | FK `questions.id` | Question ID | `77777777-8888-9999-0000-111111111111` |
| `model_version` | `text` | NO | FK `model_registry.version` | Calibration model version | `v1.0.0` |
| `a` | `double precision` | NO | `> 0` | Discrimination parameter (`1.0` for Rasch fallback) | `1.15` |
| `b` | `double precision` | NO | Logit scale | Difficulty parameter | `0.45` |
| `g` | `double precision` | NO | `[0, 0.5]` | Guessing floor (`Beta(2,18)` prior for MCQ, `0` for numeric) | `0.10` |
| `se_b` | `double precision` | NO | `>= 0` | Posterior standard error of difficulty `b` | `0.18` |
| `n_responses` | `integer` | NO | `>= 0` | Sample size used for calibration | `240` |
| `fit_flag` | `text` | NO | Enum `item_fit_flag` | Diagnostic flag (`suspect_wrong_key` if negative discrimination) | `ok` |

### 3.16 Table: `tests`
- **Produced by:** Agent A (DataGen), Agent G (Ingest)
- **Consumed by:** Agent B, Agent C, Agent G, Agent H

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `id` | `uuid` | NO | UUID v4 | Test primary key | `33333333-4444-5555-6666-777777777777` |
| `institute_id` | `uuid` | NO | FK `institutes.id` | Tenant identifier (RLS enforced) | `99999999-8888-7777-6666-555555555555` |
| `batch_id` | `uuid` | NO | FK `batches.id` | Target batch | `44444444-5555-6666-7777-888888888888` |
| `name` | `text` | NO | Non-empty text | Assessment title | `FT-01-JEE` |
| `test_date` | `date` | NO | `YYYY-MM-DD` | Administration date | `2026-05-03` |
| `exam_pattern_code` | `text` | NO | Key in `exam_patterns.yaml` | Exam structure pattern | `jee_main_2026` |
| `marking_scheme_id` | `text` | NO | FK `marking_schemes.id` | Scoring rule reference | `jee_main` |
| `max_marks` | `double precision` | NO | `> 0` | Maximum achievable marks | `300.0` |
| `source` | `text` | NO | Enum `test_source` | Capture channel (`omr`, `csv`, `online`) | `csv` |
| `day_after_off_warning` | `boolean` | NO | `true`/`false` | MoE cl. 10.1(vi) schedule warning flag | `false` |
| `created_at` | `timestamptz` | NO | ISO-8601 | Creation timestamp | `2026-05-03T18:00:00+05:30` |

### 3.17 Table: `test_questions`
- **Produced by:** Agent A, Agent G
- **Consumed by:** Agent B, Agent G

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `institute_id` | `uuid` | NO | FK `institutes.id` | Tenant identifier (RLS enforced) | `99999999-8888-7777-6666-555555555555` |
| `test_id` | `uuid` | NO | FK `tests.id` | Test ID | `33333333-4444-5555-6666-777777777777` |
| `question_id` | `uuid` | NO | FK `questions.id` | Question ID | `77777777-8888-9999-0000-111111111111` |
| `position` | `integer` | NO | `>= 1` | 1-based question number on paper | `1` |
| `section` | `text` | NO | `A` or `B` | Paper section identifier | `A` |

### 3.18 Table: `answer_keys`
- **Produced by:** Agent A, Agent G
- **Consumed by:** Agent B, Agent G (Scoring)

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `id` | `uuid` | NO | UUID v4 | Answer key version primary key | `abababab-cdcd-efef-1212-343434343434` |
| `institute_id` | `uuid` | NO | FK `institutes.id` | Tenant identifier (RLS enforced) | `99999999-8888-7777-6666-555555555555` |
| `test_id` | `uuid` | NO | FK `tests.id` | Test ID | `33333333-4444-5555-6666-777777777777` |
| `question_id` | `uuid` | NO | FK `questions.id` | Question ID | `77777777-8888-9999-0000-111111111111` |
| `accepted_answers` | `text[]` | NO | Array of strings | Accepted options (e.g. `{'A','C'}`) or numeric value | `{'A'}` |
| `numeric_tolerance` | `double precision` | NO | `>= 0` | Allowed absolute tolerance for numeric answers | `0.0` |
| `dropped` | `boolean` | NO | `true`/`false` | Whether question is officially dropped (bonus) | `false` |
| `version` | `integer` | NO | `>= 1` | Monotone key version number | `1` |
| `created_by` | `uuid` | YES | FK `users.id` | User who published key version | `22222222-3333-4444-5555-666666666666` |
| `created_at` | `timestamptz` | NO | ISO-8601 | Version creation timestamp | `2026-05-03T18:00:00+05:30` |

### 3.19 Table: `responses`
- **Produced by:** Agent A, Agent F (OMR), Agent G
- **Consumed by:** Agent B (IRT/Mastery), Agent C

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `institute_id` | `uuid` | NO | FK `institutes.id` | Tenant identifier (RLS enforced) | `99999999-8888-7777-6666-555555555555` |
| `test_id` | `uuid` | NO | FK `tests.id` | Test ID | `33333333-4444-5555-6666-777777777777` |
| `student_id` | `uuid` | NO | FK `students.id` | Student ID | `11111111-2222-3333-4444-555555555555` |
| `question_id` | `uuid` | NO | FK `questions.id` | Question ID | `77777777-8888-9999-0000-111111111111` |
| `response` | `text` | YES | Option or number string | Recorded student answer (`NULL` if blank/unreadable) | `A` |
| `is_correct` | `boolean` | NO | `true`/`false` | Whether response is scored as correct (blanks = `false`) | `true` |
| `marks_awarded` | `double precision` | NO | Float marks | Marks awarded under test marking scheme | `4.0` |
| `status` | `text` | NO | Enum `response_status` | Capture state (`answered`, `blank`, `multi_marked`, `unreadable`) | `answered` |
| `confidence` | `double precision` | NO | `[0, 1]` | OMR bubble detection confidence (`1.0` for CSV) | `0.99` |

### 3.20 Table: `test_totals`
- **Produced by:** Agent A, Agent G
- **Consumed by:** Agent B, Agent C, Agent G

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `institute_id` | `uuid` | NO | FK `institutes.id` | Tenant identifier (RLS enforced) | `99999999-8888-7777-6666-555555555555` |
| `test_id` | `uuid` | NO | FK `tests.id` | Test ID | `33333333-4444-5555-6666-777777777777` |
| `student_id` | `uuid` | NO | FK `students.id` | Student ID | `11111111-2222-3333-4444-555555555555` |
| `raw_score` | `double precision` | YES | Float marks | Total marks obtained (`NULL` if absent) | `184.0` |
| `physics_score` | `double precision` | YES | Float marks | Physics section subtotal | `68.0` |
| `chemistry_score` | `double precision` | YES | Float marks | Chemistry section subtotal | `62.0` |
| `math_or_bio_score` | `double precision` | YES | Float marks | Mathematics or Biology subtotal | `54.0` |
| `absent_flag` | `boolean` | NO | `true`/`false` | True if student was absent from the test | `false` |

### 3.21 Table: `attendance`
- **Produced by:** Agent A, Agent G
- **Consumed by:** Agent C (Features), Agent E, Agent G

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `institute_id` | `uuid` | NO | FK `institutes.id` | Tenant identifier (RLS enforced) | `99999999-8888-7777-6666-555555555555` |
| `student_id` | `uuid` | NO | FK `students.id` | Student ID | `11111111-2222-3333-4444-555555555555` |
| `attendance_date` | `date` | NO | `YYYY-MM-DD` | Class date | `2026-05-04` |
| `present_flag` | `boolean` | NO | `true`/`false` | True if present, false if absent | `true` |
| `source` | `text` | NO | Enum `attendance_source` | Capture channel (`csv`, `manual`, `biometric`) | `csv` |

### 3.22 Table: `fees`
- **Produced by:** Agent A, Agent G
- **Consumed by:** Agent C (Features), Agent G (Refunds)

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `id` | `uuid` | NO | UUID v4 | Fee instalment primary key | `cdcdcdcd-efef-1212-3434-565656565656` |
| `institute_id` | `uuid` | NO | FK `institutes.id` | Tenant identifier (RLS enforced) | `99999999-8888-7777-6666-555555555555` |
| `student_id` | `uuid` | NO | FK `students.id` | Student ID | `11111111-2222-3333-4444-555555555555` |
| `instalment_no` | `integer` | NO | `1..12` | Sequential instalment number | `1` |
| `due_date` | `date` | NO | `YYYY-MM-DD` | Scheduled due date | `2026-04-15` |
| `amount_paise` | `bigint` | NO | `>= 0` (integer paise) | Scheduled instalment amount in paise | `3500000` |
| `paid_date` | `date` | YES | `YYYY-MM-DD` | Settlement date (`NULL` if unpaid) | `2026-04-15` |
| `paid_amount_paise` | `bigint` | NO | `>= 0` (integer paise) | Amount actually paid in paise | `3500000` |
| `refund_due_paise` | `bigint` | NO | `>= 0` (integer paise) | Pro-rata refund due on withdrawal (MoE cl. 8(iv)) | `0` |
| `refund_paid_date` | `date` | YES | `YYYY-MM-DD` | Date pro-rata refund was disbursed | `NULL` |

### 3.23 Table: `engagement`
- **Produced by:** Agent A (DataGen)
- **Consumed by:** Agent C (Tier D ablation only)

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `institute_id` | `uuid` | NO | FK `institutes.id` | Tenant identifier (RLS enforced) | `99999999-8888-7777-6666-555555555555` |
| `student_id` | `uuid` | NO | FK `students.id` | Student ID | `11111111-2222-3333-4444-555555555555` |
| `activity_date` | `date` | NO | `YYYY-MM-DD` | Activity date | `2026-05-04` |
| `doubts_asked` | `integer` | NO | `>= 0` | Number of doubts asked | `2` |
| `homework_submitted` | `boolean` | NO | `true`/`false` | Whether assigned homework was submitted | `true` |
| `app_logins` | `integer` | NO | `>= 0` | Daily app login count | `1` |

### 3.24 Table: `mastery_snapshots`
- **Produced by:** Agent B (Mastery), Agent G
- **Consumed by:** Agent C, Agent E, Agent G, Agent H

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `institute_id` | `uuid` | NO | FK `institutes.id` | Tenant identifier (RLS enforced) | `99999999-8888-7777-6666-555555555555` |
| `student_id` | `uuid` | NO | FK `students.id` | Student ID | `11111111-2222-3333-4444-555555555555` |
| `topic_id` | `text` | NO | FK `topics.id` | Syllabus topic ID | `jee.phy.kinematics.projectile` |
| `theta` | `double precision` | NO | Logit scale | Shrunk EAP ability estimate | `0.65` |
| `se` | `double precision` | NO | `>= 0` | Posterior standard error | `0.22` |
| `band` | `text` | NO | Enum `mastery_band` | Categorical band (`not_enough_data` if `se >= tau`) | `steady` |
| `n_items` | `integer` | NO | `>= 0` | Cumulative items attempted in topic | `14` |
| `computed_at` | `timestamptz` | NO | ISO-8601 | Snapshot computation timestamp | `2026-08-15T18:00:00+05:30` |
| `model_version` | `text` | NO | FK `model_registry.version` | Model version | `v1.0.0` |

### 3.25 Table: `risk_scores`
- **Produced by:** Agent C (Risk), Agent G
- **Consumed by:** Agent G (Backend), Agent H (Frontend)

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `institute_id` | `uuid` | NO | FK `institutes.id` | Tenant identifier (RLS enforced) | `99999999-8888-7777-6666-555555555555` |
| `student_id` | `uuid` | NO | FK `students.id` | Student ID | `11111111-2222-3333-4444-555555555555` |
| `as_of` | `date` | NO | `YYYY-MM-DD` | Strict evaluation cutoff date | `2026-08-15` |
| `target` | `text` | NO | Enum `risk_target` | Prediction target (`academic_support`, `retention`, `fee`) | `academic_support` |
| `routing_method` | `text` | NO | Enum `routing_method` | Method executed per `routing_policy.yaml` (`ml`, `rules`, `none`) | `ml` |
| `p` | `double precision` | YES | `[0, 1]` or `NULL` | Calibrated probability (`NULL` when `routing_method = 'rules'`) | `0.68` |
| `band` | `text` | NO | Enum `risk_band` | Supportive triage band (`low`, `watch`, `needs_support`) | `needs_support` |
| `reasons` | `jsonb` | NO | JSON array | Rendered bilingual reasons and actions from `reason_templates.yaml` | `[...]` |
| `feature_tier` | `text` | NO | Enum `feature_tier` | Highest feature tier used (`A`..`D`) | `A` |
| `model_version` | `text` | NO | FK `model_registry.version` | Model version | `v1.0.0` |

### 3.26 Table: `predictions`
- **Produced by:** Agent C (Band), Agent G
- **Consumed by:** Agent G (Backend), Agent H (Frontend)

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `institute_id` | `uuid` | NO | FK `institutes.id` | Tenant identifier (RLS enforced) | `99999999-8888-7777-6666-555555555555` |
| `student_id` | `uuid` | NO | FK `students.id` | Student ID | `11111111-2222-3333-4444-555555555555` |
| `as_of` | `date` | NO | `YYYY-MM-DD` | Prediction cutoff date | `2026-08-15` |
| `q10` | `double precision` | NO | Internal score | Conformalized 10th percentile internal score bound | `135.0` |
| `q50` | `double precision` | NO | Internal score | Median internal score estimate | `162.0` |
| `q90` | `double precision` | NO | Internal score | Conformalized 90th percentile internal score bound | `188.0` |
| `mapped_low` | `double precision` | NO | `[0, 100]` | Lower bound of mapped NTA percentile range | `94.5` |
| `mapped_high` | `double precision` | NO | `[0, 100]` | Upper bound of mapped NTA percentile range | `98.8` |
| `coverage_level` | `double precision` | NO | `(0, 1)` | Target conformal coverage level | `0.80` |
| `model_version` | `text` | NO | FK `model_registry.version` | Model version | `v1.0.0` |

### 3.27 Table: `interventions`
- **Produced by:** Agent G (Backend)
- **Consumed by:** Agent G, Agent H (Frontend)

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `id` | `uuid` | NO | UUID v4 | Intervention primary key | `55555555-6666-7777-8888-999999999999` |
| `institute_id` | `uuid` | NO | FK `institutes.id` | Tenant identifier (RLS enforced) | `99999999-8888-7777-6666-555555555555` |
| `student_id` | `uuid` | NO | FK `students.id` | Target student | `11111111-2222-3333-4444-555555555555` |
| `type` | `text` | NO | Enum `intervention_type` | Supportive action category | `remedial_session` |
| `owner_user_id` | `uuid` | NO | FK `users.id` | Assigned mentor or teacher | `22222222-3333-4444-5555-666666666666` |
| `due_date` | `date` | NO | `YYYY-MM-DD` | Target completion date | `2026-08-22` |
| `done_at` | `timestamptz` | YES | ISO-8601 | Completion timestamp | `NULL` |
| `outcome` | `text` | NO | Enum `intervention_outcome` | Structured outcome code | `pending` |
| `created_at` | `timestamptz` | NO | ISO-8601 | Creation timestamp | `2026-08-15T18:30:00+05:30` |

### 3.28 Table: `reports`
- **Produced by:** Agent E (GenAI), Agent G
- **Consumed by:** Agent G, Agent H (Frontend)

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `id` | `uuid` | NO | UUID v4 | Report primary key | `66666666-7777-8888-9999-000000000000` |
| `institute_id` | `uuid` | NO | FK `institutes.id` | Tenant identifier (RLS enforced) | `99999999-8888-7777-6666-555555555555` |
| `student_id` | `uuid` | NO | FK `students.id` | Student ID | `11111111-2222-3333-4444-555555555555` |
| `period` | `text` | NO | Period label | Reporting period | `2026-08` |
| `lang` | `text` | NO | Enum `lang` | Report language (`en` or `hi`) | `hi` |
| `numbers_json` | `jsonb` | NO | `report_numbers.schema.json` | Deterministic fact payload with `{STUDENT}` placeholder | `{...}` |
| `content` | `text` | NO | 80-180 words | Verified report prose after name substitution | `नमस्ते अभिभावक...` |
| `verified` | `boolean` | NO | `true`/`false` | Verifier pass status (only verified reports are delivered) | `true` |
| `path` | `text` | NO | Enum `report_path` | Generation pathway (`llm` or `template`) | `llm` |
| `model_version` | `text` | NO | FK `model_registry.version` | Model version | `v1.0.0` |
| `sent_via` | `text` | NO | Enum `report_channel` | Delivery channel | `whatsapp_preview` |
| `sent_at` | `timestamptz` | YES | ISO-8601 | Delivery timestamp | `2026-08-15T19:00:00+05:30` |
| `created_at` | `timestamptz` | NO | ISO-8601 | Creation timestamp | `2026-08-15T19:00:00+05:30` |

### 3.29 Table: `ingest_jobs`
- **Produced by:** Agent G (Ingest)
- **Consumed by:** Agent G, Agent H (Frontend)

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `id` | `uuid` | NO | UUID v4 | Job primary key | `aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee` |
| `institute_id` | `uuid` | NO | FK `institutes.id` | Tenant identifier (RLS enforced) | `99999999-8888-7777-6666-555555555555` |
| `file_hash` | `text` | NO | SHA-256 hex | File digest (unique per `institute_id` for idempotency) | `e3b0c442...` |
| `type` | `text` | NO | Enum `ingest_type` | Upload category | `students` |
| `status` | `text` | NO | Enum `ingest_status` | Job lifecycle state | `confirmed` |
| `mapping` | `jsonb` | NO | JSON object | Resolved header mapping | `{"R.No": "roll_no"}` |
| `errors` | `jsonb` | NO | JSON array | Row-level validation errors | `[]` |
| `rows_ok` | `integer` | NO | `>= 0` | Count of valid rows | `58` |
| `rows_failed` | `integer` | NO | `>= 0` | Count of rejected rows | `0` |
| `created_at` | `timestamptz` | NO | ISO-8601 | Upload timestamp | `2026-05-03T18:00:00+05:30` |

### 3.30 Table: `omr_templates`
- **Produced by:** Phase 0 Contracts, Agent F
- **Consumed by:** Agent F (OMR), Agent G

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `id` | `uuid` | NO | UUID v4 | Template primary key | `dededede-fafa-1212-3434-565656565656` |
| `institute_id` | `uuid` | NO | FK `institutes.id` | Tenant identifier (RLS enforced) | `99999999-8888-7777-6666-555555555555` |
| `name` | `text` | NO | Layout name | Layout identifier | `jee_75` |
| `layout` | `jsonb` | NO | `omr_template.schema.json` | Physical geometry specification in mm | `{...}` |
| `created_at` | `timestamptz` | NO | ISO-8601 | Registration timestamp | `2026-04-01T09:00:00+05:30` |

### 3.31 Table: `audit_log`
- **Produced by:** Agent G (Backend)
- **Consumed by:** Agent G (Owner Dashboard), Agent I (QA)

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `id` | `uuid` | NO | UUID v4 | Audit entry primary key | `ffffffff-1111-2222-3333-444444444444` |
| `actor` | `uuid` | NO | FK `users.id` | User who performed the action | `22222222-3333-4444-5555-666666666666` |
| `institute_id` | `uuid` | NO | FK `institutes.id` | Tenant identifier (RLS enforced) | `99999999-8888-7777-6666-555555555555` |
| `action` | `text` | NO | Enum `audit_action` | Audited event type | `view_risk_scores` |
| `entity` | `text` | NO | Table/resource name | Target entity type | `batches` |
| `entity_id` | `text` | NO | Identifier string | Target entity ID (no PII stored) | `44444444-5555-6666-7777-888888888888` |
| `occurred_at` | `timestamptz` | NO | ISO-8601 | Event timestamp (retained >= 1 year per DPDP Rule 6) | `2026-08-15T19:05:00+05:30` |

---

## 4. Canonical CSV Upload Templates (`contracts/csv_templates/`)

### 4.1 CSV Template: `students.csv`
- **Produced by:** Agent A (Messy/Clean), Institute Admin
- **Consumed by:** Agent G (`/ingest/students`)

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `roll_no` | `string` | NO | Non-empty text | Unique student roll number within academic year | `PAT26-001` |
| `name` | `string` | NO | Non-empty text | Student full name in Latin script | `Aarav Test` |
| `name_alt` | `string` | YES | Text | Optional Devanagari name | `आरव टेस्ट` |
| `dob` | `date` | NO | `YYYY-MM-DD` | Date of birth | `2009-05-14` |
| `gender` | `string` | NO | Enum `gender` | Student gender | `male` |
| `class_level` | `string` | NO | Enum `class_level` | Cohort class level | `class_11` |
| `exam` | `string` | NO | Enum `exam` | Target entrance exam | `jee_main` |
| `batch_name` | `string` | NO | Non-empty text | Assigned batch name | `JEE-11-Morning-A` |
| `join_date` | `date` | NO | `YYYY-MM-DD` | Admission date | `2026-04-15` |
| `fee_plan` | `string` | NO | Enum `fee_plan` | Tuition payment plan | `standard_3_instalment` |
| `out_of_town` | `boolean` | NO | `true`/`false` | Outstation/hostel indicator | `false` |

### 4.2 CSV Template: `guardians.csv`
- **Produced by:** Agent A, Institute Admin
- **Consumed by:** Agent G (`/ingest/students`)

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `roll_no` | `string` | NO | FK `students.roll_no` | Student roll number | `PAT26-001` |
| `guardian_name` | `string` | NO | Non-empty text | Parent or guardian full name | `Rajesh Test` |
| `phone` | `string` | NO | 10-digit phone | Contact mobile number (shared across siblings) | `9000000001` |
| `relation` | `string` | NO | Enum `guardian_relation` | Relationship to student | `father` |
| `lang_pref` | `string` | NO | Enum `lang` | Preferred report language | `hi` |

### 4.3 CSV Template: `results_responses_wide.csv`
- **Produced by:** Agent A, Institute Teacher
- **Consumed by:** Agent G (`/ingest/results`)

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `test_name` | `string` | NO | Non-empty text | Test identifier | `FT-01-JEE` |
| `test_date` | `date` | NO | `YYYY-MM-DD` | Date of assessment | `2026-05-03` |
| `roll_no` | `string` | NO | FK `students.roll_no` | Student roll number | `PAT26-001` |
| `q1` | `string` | YES | Option `A..D` or number | Response to Question 1 (empty = blank) | `A` |
| `q2` | `string` | YES | Option `A..D` or number | Response to Question 2 | `C` |
| `q3` | `string` | YES | Option `A..D` or number | Response to Question 3 | `` |
| `q4` | `string` | YES | Option `A..D` or number | Response to Question 4 | `B` |
| `q5` | `string` | YES | Option `A..D` or number | Response to Question 5 | `42.5` |

### 4.4 CSV Template: `results_marks_only.csv`
- **Produced by:** Agent A, Marks-Only Institute
- **Consumed by:** Agent G (`/ingest/results`)

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `test_name` | `string` | NO | Non-empty text | Test identifier | `FT-01-JEE` |
| `test_date` | `date` | NO | `YYYY-MM-DD` | Date of assessment | `2026-05-03` |
| `roll_no` | `string` | NO | FK `students.roll_no` | Student roll number | `PAT26-001` |
| `raw_score` | `float` | YES | Float marks | Total marks obtained (empty if absent) | `184.0` |
| `physics_score` | `float` | YES | Float marks | Physics section marks | `68.0` |
| `chemistry_score` | `float` | YES | Float marks | Chemistry section marks | `62.0` |
| `math_or_bio_score` | `float` | YES | Float marks | Mathematics or Biology section marks | `54.0` |
| `absent_flag` | `boolean` | NO | `true`/`false` | Whether student was absent | `false` |

### 4.5 CSV Template: `answer_key.csv`
- **Produced by:** Agent A, Institute Teacher
- **Consumed by:** Agent G (`/ingest/results`)

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `question_no` | `integer` | NO | `>= 1` | 1-based question number | `1` |
| `q_type` | `string` | NO | Enum `q_type` | Question format | `mcq_single` |
| `subject` | `string` | NO | Subject name | Subject discipline | `Physics` |
| `topic_id` | `string` | NO | FK `topics.id` | Syllabus topic slug | `jee.phy.kinematics.projectile` |
| `accepted_answers` | `string` | NO | Pipe-separated (`A|C`) | Accepted option(s) or target numeric value | `A` |
| `numeric_tolerance` | `float` | NO | `>= 0.0` | Allowed numeric error margin | `0.0` |
| `dropped` | `boolean` | NO | `true`/`false` | Whether item is officially dropped | `false` |

### 4.6 CSV Template: `attendance.csv`
- **Produced by:** Agent A, Institute Staff
- **Consumed by:** Agent G (`/ingest/students`)

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `roll_no` | `string` | NO | FK `students.roll_no` | Student roll number | `PAT26-001` |
| `attendance_date` | `date` | NO | `YYYY-MM-DD` | Class date | `2026-05-04` |
| `present_flag` | `boolean` | NO | `true`/`false` | Attendance indicator | `true` |
| `source` | `string` | NO | Enum `attendance_source` | Capture source | `csv` |

### 4.7 CSV Template: `fees.csv`
- **Produced by:** Agent A, Accounts Desk
- **Consumed by:** Agent G (`/ingest/students`)

| Column | Type | Nullable | Allowed Values / Range | Meaning | Example |
|---|---|---|---|---|---|
| `roll_no` | `string` | NO | FK `students.roll_no` | Student roll number | `PAT26-001` |
| `instalment_no` | `integer` | NO | `1..12` | Instalment sequence number | `1` |
| `due_date` | `date` | NO | `YYYY-MM-DD` | Instalment due date | `2026-04-15` |
| `amount_paise` | `integer` | NO | `>= 0` | Scheduled fee in integer paise | `3500000` |
| `paid_date` | `date` | YES | `YYYY-MM-DD` | Payment receipt date | `2026-04-15` |
| `paid_amount_paise` | `integer` | NO | `>= 0` | Paid amount in integer paise | `3500000` |
| `refund_due_paise` | `integer` | NO | `>= 0` | Pro-rata refund due in integer paise | `0` |
| `refund_paid_date` | `date` | YES | `YYYY-MM-DD` | Date refund was settled | `` |

---

## 5. Synthetic Ground-Truth Parquet Files (`contracts/datasets.yaml`)

- **Produced by:** Agent A (DataGen)
- **Consumed by:** Agent B (IRT/Mastery evaluation), Agent C (Risk/Band evaluation) — **never** loaded into PostgreSQL or Backend.
- **`data/truth/true_theta_topic.parquet`:** `(student_id, institute_id, topic_id, month_index, true_g, true_theta, risk_aversion_tau)`
- **`data/truth/true_item_params.parquet`:** `(question_id, topic_id, true_a, true_b, true_g, is_injected_wrong_key, true_correct_answer)`
- **`data/truth/dropout_events.parquet`:** `(student_id, institute_id, dropped_out, dropout_date, fade_start_date, dropout_type, dropout_reason)`
- **`data/truth/true_final_outcomes.parquet`:** `(student_id, institute_id, exam, shift_difficulty_delta_marks, true_final_score, true_final_percentile)`
