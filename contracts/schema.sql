-- Purpose: PostgreSQL 16 DDL for all application and analytics tables with Row-Level Security (RLS) multi-tenancy.
-- contract_version: 1.0.0
-- Implements: TECH_PLAN §8 (Data model) and §15 (Privacy, DPDP, well-being).
--
-- DELIBERATELY NOT STORED (per TECH_PLAN §8 & §15):
--   1. Counselling clinical notes or mental-health information (out of scope; never a model feature; prevents sensitive data exposure).
--   2. Government ID document images or copies (DPDP Rule 10 compliance stores only verification_method and verified_by_user_id).
--   3. Student photographs (prevents non-consensual marketing use per UP Coaching Regulation Act 2002 / MoE 2024 guidelines).
--   4. Public ranks or performance-based batch assignments (prohibited by MoE 2024 cl. 10.2(xi), cl. 12(vii) and Rajasthan Act 2025 s.12(ix)).
--   5. Synthetic ground-truth schema (`truth`): ground-truth latent traits live strictly in offline parquet files (`data/truth/*.parquet`), never in the application database.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    END IF;
END
$$;

-- 1. institutes (root tenant registry)
CREATE TABLE institutes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    city text NOT NULL,
    city_tier text NOT NULL CHECK (city_tier IN ('tier_1', 'tier_2', 'tier_3')),
    exam_focus text NOT NULL CHECK (exam_focus IN ('jee_main', 'neet_ug', 'mix')),
    plan text NOT NULL DEFAULT 'standard' CHECK (plan IN ('starter', 'standard', 'pro')),
    weekly_off_day text NOT NULL DEFAULT 'sunday' CHECK (weekly_off_day IN ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')),
    counsellor_name text,
    counsellor_contact text,
    created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE institutes IS 'Registered coaching institute tenants (Data Fiduciaries under DPDP Act 2023).';
COMMENT ON COLUMN institutes.city_tier IS 'Urban tier classification driving fee and operational benchmarks.';
COMMENT ON COLUMN institutes.weekly_off_day IS 'Mandatory weekly rest day per MoE 2024 cl. 10.1(v); tests on the following day are flagged.';
COMMENT ON COLUMN institutes.counsellor_contact IS 'Contact details for the institute counselling system per MoE 2024 cl. 11(ii) and Rajasthan Act s.14(2).';

ALTER TABLE institutes ENABLE ROW LEVEL SECURITY;
ALTER TABLE institutes FORCE ROW LEVEL SECURITY;
CREATE POLICY institutes_tenant_isolation ON institutes
    FOR ALL TO app_user
    USING (id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- 2. users
CREATE TABLE users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    institute_id uuid NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
    role text NOT NULL CHECK (role IN ('owner', 'admin', 'teacher', 'mentor', 'parent', 'student')),
    phone text NOT NULL,
    name text NOT NULL,
    lang text NOT NULL DEFAULT 'en' CHECK (lang IN ('en', 'hi')),
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (institute_id, role, phone)
);

COMMENT ON TABLE users IS 'Authenticated platform users scoped to an institute tenant.';
COMMENT ON COLUMN users.role IS 'RBAC role controlling endpoint access and field-level privacy filtering.';
COMMENT ON COLUMN users.lang IS 'Preferred UI and notification language (ISO 639-1).';

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
CREATE POLICY users_tenant_isolation ON users
    FOR ALL TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- 3. legal_settings
CREATE TABLE legal_settings (
    institute_id uuid PRIMARY KEY REFERENCES institutes(id) ON DELETE CASCADE,
    minor_ml_risk_enabled boolean NOT NULL DEFAULT false,
    active_feature_tier text NOT NULL DEFAULT 'C' CHECK (active_feature_tier IN ('A', 'B', 'C', 'D')),
    legal_opinion_ref text,
    retention_months_after_leaving integer NOT NULL DEFAULT 12 CHECK (retention_months_after_leaving >= 1 AND retention_months_after_leaving <= 84),
    updated_by uuid REFERENCES users(id),
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE legal_settings IS 'Per-institute DPDP legal routing configuration and active feature privacy tier.';
COMMENT ON COLUMN legal_settings.minor_ml_risk_enabled IS 'When false (default), under-18 students receive ML only for academic_support (tier A) and transparent rules for retention/fee.';
COMMENT ON COLUMN legal_settings.active_feature_tier IS 'Maximum feature privacy tier enabled by the institute owner (tier D is never used for minors).';
COMMENT ON COLUMN legal_settings.legal_opinion_ref IS 'Document reference for external legal opinion required before enabling minor_ml_risk_enabled.';

ALTER TABLE legal_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE legal_settings FORCE ROW LEVEL SECURITY;
CREATE POLICY legal_settings_tenant_isolation ON legal_settings
    FOR ALL TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- 4. batches
CREATE TABLE batches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    institute_id uuid NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
    name text NOT NULL,
    class_level text NOT NULL CHECK (class_level IN ('class_11', 'class_12', 'dropper')),
    exam text NOT NULL CHECK (exam IN ('jee_main', 'neet_ug')),
    academic_year integer NOT NULL CHECK (academic_year >= 2020 AND academic_year <= 2100),
    start_date date NOT NULL,
    published_capacity integer NOT NULL DEFAULT 60 CHECK (published_capacity > 0),
    mentor_capacity_per_week integer NOT NULL DEFAULT 8 CHECK (mentor_capacity_per_week > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (institute_id, academic_year, name)
);

COMMENT ON TABLE batches IS 'Teaching cohorts formed strictly by admission order, never academic performance (MoE cl. 12(vii)).';
COMMENT ON COLUMN batches.published_capacity IS 'Published maximum batch size per Rajasthan Act 2025 s.12(i).';
COMMENT ON COLUMN batches.mentor_capacity_per_week IS 'Weekly check-in bandwidth k setting the top-k early-warning operating point.';

ALTER TABLE batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE batches FORCE ROW LEVEL SECURITY;
CREATE POLICY batches_tenant_isolation ON batches
    FOR ALL TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- 5. students
CREATE TABLE students (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    institute_id uuid NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
    batch_id uuid NOT NULL REFERENCES batches(id) ON DELETE RESTRICT,
    academic_year integer NOT NULL CHECK (academic_year >= 2020 AND academic_year <= 2100),
    roll_no text NOT NULL,
    name text NOT NULL,
    name_alt text,
    dob date NOT NULL,
    gender text NOT NULL CHECK (gender IN ('female', 'male', 'other', 'prefer_not_to_say')),
    join_date date NOT NULL,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'left', 'transferred')),
    left_date date,
    fee_plan text NOT NULL DEFAULT 'standard_3_instalment' CHECK (fee_plan IN ('upfront_full', 'standard_3_instalment', 'rajasthan_4_equal', 'custom_scholarship')),
    out_of_town boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (institute_id, academic_year, roll_no)
);

COMMENT ON TABLE students IS 'Enrolled students. is_minor is dynamically derived from dob at each as_of date (age < 18 years).';
COMMENT ON COLUMN students.roll_no IS 'Human-facing roll number, unique within (institute_id, academic_year) to allow reuse across years.';
COMMENT ON COLUMN students.name_alt IS 'Optional Devanagari or transliterated student name variant.';
COMMENT ON COLUMN students.dob IS 'Date of birth used to check minimum age >= 16 at enrolment (MoE 2024) and derive is_minor for DPDP s.9 routing.';

CREATE INDEX idx_students_institute_batch ON students(institute_id, batch_id);
CREATE INDEX idx_students_institute_roll ON students(institute_id, academic_year, roll_no);

ALTER TABLE students ENABLE ROW LEVEL SECURITY;
ALTER TABLE students FORCE ROW LEVEL SECURITY;
CREATE POLICY students_tenant_isolation ON students
    FOR ALL TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- 6. batch_changes
CREATE TABLE batch_changes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    institute_id uuid NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
    student_id uuid NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    from_batch uuid NOT NULL REFERENCES batches(id) ON DELETE RESTRICT,
    to_batch uuid NOT NULL REFERENCES batches(id) ON DELETE RESTRICT,
    changed_at timestamptz NOT NULL DEFAULT now(),
    reason text NOT NULL CHECK (reason IN ('timing', 'subject_change', 'relocation', 'other')),
    by_user uuid NOT NULL REFERENCES users(id)
);

COMMENT ON TABLE batch_changes IS 'Audit log of batch transfers. Performance-based transfers are prohibited by MoE 2024 cl. 12(vii) and Rajasthan Act s.12(ix).';
COMMENT ON COLUMN batch_changes.reason IS 'Permitted non-performance reason for batch transfer.';

ALTER TABLE batch_changes ENABLE ROW LEVEL SECURITY;
ALTER TABLE batch_changes FORCE ROW LEVEL SECURITY;
CREATE POLICY batch_changes_tenant_isolation ON batch_changes
    FOR ALL TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- 7. guardians
CREATE TABLE guardians (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    institute_id uuid NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
    student_id uuid NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    name text NOT NULL,
    phone text NOT NULL,
    relation text NOT NULL CHECK (relation IN ('father', 'mother', 'legal_guardian', 'self')),
    lang_pref text NOT NULL DEFAULT 'hi' CHECK (lang_pref IN ('en', 'hi')),
    created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE guardians IS 'Parent or lawful guardian records per student. One phone number may map to multiple sibling students.';
COMMENT ON COLUMN guardians.phone IS 'Phone number for OTP consent verification and parent report delivery (non-unique across siblings).';

CREATE INDEX idx_guardians_institute_student ON guardians(institute_id, student_id);
CREATE INDEX idx_guardians_institute_phone ON guardians(institute_id, phone);

ALTER TABLE guardians ENABLE ROW LEVEL SECURITY;
ALTER TABLE guardians FORCE ROW LEVEL SECURITY;
CREATE POLICY guardians_tenant_isolation ON guardians
    FOR ALL TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- 8. consents
CREATE TABLE consents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    institute_id uuid NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
    student_id uuid NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    guardian_id uuid REFERENCES guardians(id) ON DELETE SET NULL,
    purpose text NOT NULL CHECK (purpose IN ('analytics', 'risk_alerts', 'parent_reports', 'benchmarking', 'engagement_tracking')),
    verification_method text NOT NULL CHECK (verification_method IN ('in_person_id_check', 'otp_known_parent', 'digilocker_token', 'self_adult')),
    verified_by_user_id uuid REFERENCES users(id),
    verified_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz,
    notice_version text NOT NULL,
    notice_lang text NOT NULL CHECK (notice_lang IN ('en', 'hi'))
);

COMMENT ON TABLE consents IS 'Purpose-wise verifiable parental or adult student consent ledger under DPDP Act s.9(1) and Rule 10. No ID document copies are stored.';
COMMENT ON COLUMN consents.guardian_id IS 'Null when the student is 18+ and provides personal consent (verification_method = self_adult).';
COMMENT ON COLUMN consents.verification_method IS 'How adulthood and identity were verified under DPDP Rule 10(1).';
COMMENT ON COLUMN consents.revoked_at IS 'When non-null, processing for this purpose halts immediately and derived scores are purged.';

CREATE INDEX idx_consents_student_purpose ON consents(institute_id, student_id, purpose);

ALTER TABLE consents ENABLE ROW LEVEL SECURITY;
ALTER TABLE consents FORCE ROW LEVEL SECURITY;
CREATE POLICY consents_tenant_isolation ON consents
    FOR ALL TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- 9. topics (shared global read-only reference table)
CREATE TABLE topics (
    id text PRIMARY KEY,
    exam text NOT NULL CHECK (exam IN ('jee_main', 'neet_ug')),
    subject text NOT NULL,
    chapter text NOT NULL,
    topic text NOT NULL,
    name_en text NOT NULL,
    name_hi text NOT NULL,
    name_hi_reviewed boolean NOT NULL DEFAULT false,
    parent_id text REFERENCES topics(id) ON DELETE RESTRICT,
    class_level text NOT NULL CHECK (class_level IN ('class_11', 'class_12', 'dropper')),
    syllabus_year integer NOT NULL DEFAULT 2026,
    weightage double precision CHECK (weightage IS NULL OR (weightage >= 0.0 AND weightage <= 1.0)),
    verified boolean NOT NULL DEFAULT false
);

COMMENT ON TABLE topics IS 'Global read-only bilingual syllabus taxonomy (subject -> chapter -> topic) for JEE Main and NEET-UG.';
COMMENT ON COLUMN topics.id IS 'Stable hierarchical slug (e.g. jee.phy.kinematics.projectile).';
COMMENT ON COLUMN topics.name_hi IS 'Devanagari topic title used in bilingual heatmaps and verified Hindi parent reports.';
COMMENT ON COLUMN topics.name_hi_reviewed IS 'True only after a Hindi-native reviewer has verified name_hi in topics_hi_review.csv.';
COMMENT ON COLUMN topics.weightage IS 'Historical exam weightage fraction; null unless verified from primary sources.';

ALTER TABLE topics ENABLE ROW LEVEL SECURITY;
CREATE POLICY topics_read_all ON topics
    FOR SELECT TO app_user
    USING (true);

-- 10. topic_prereqs (shared global read-only DAG)
CREATE TABLE topic_prereqs (
    topic_id text NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    prereq_topic_id text NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    PRIMARY KEY (topic_id, prereq_topic_id),
    CHECK (topic_id <> prereq_topic_id)
);

COMMENT ON TABLE topic_prereqs IS 'Global read-only directed acyclic graph (DAG) of chapter/topic prerequisites for study-plan recommendations.';

ALTER TABLE topic_prereqs ENABLE ROW LEVEL SECURITY;
CREATE POLICY topic_prereqs_read_all ON topic_prereqs
    FOR SELECT TO app_user
    USING (true);

-- 11. model_registry (shared global read-only metadata)
CREATE TABLE model_registry (
    version text PRIMARY KEY,
    trained_at timestamptz NOT NULL,
    data_version text NOT NULL,
    metrics jsonb NOT NULL DEFAULT '{}'::jsonb
);

COMMENT ON TABLE model_registry IS 'Global read-only versioned offline ML artifacts and evaluation metrics exposed via GET /version.';

ALTER TABLE model_registry ENABLE ROW LEVEL SECURITY;
CREATE POLICY model_registry_read_all ON model_registry
    FOR SELECT TO app_user
    USING (true);

-- 12. marking_schemes (shared global read-only reference table)
CREATE TABLE marking_schemes (
    id text PRIMARY KEY,
    name text NOT NULL,
    correct double precision NOT NULL,
    wrong double precision NOT NULL,
    blank double precision NOT NULL DEFAULT 0.0,
    partial_rule text NOT NULL DEFAULT 'full_marks_if_any_accepted' CHECK (partial_rule IN ('none', 'full_marks_if_any_accepted', 'proportional_no_negative')),
    dropped_rule text NOT NULL DEFAULT 'full_marks_all' CHECK (dropped_rule IN ('full_marks_all', 'full_marks_attempted_only'))
);

COMMENT ON TABLE marking_schemes IS 'Global read-only scoring rules for JEE Main, NEET-UG, and common internal test schemes.';
COMMENT ON COLUMN marking_schemes.partial_rule IS 'How multi-correct questions are scored (NTA rule: full marks if any accepted option is marked).';
COMMENT ON COLUMN marking_schemes.dropped_rule IS 'How dropped questions are scored (NTA rule: full marks to all or attempted only).';

ALTER TABLE marking_schemes ENABLE ROW LEVEL SECURITY;
CREATE POLICY marking_schemes_read_all ON marking_schemes
    FOR SELECT TO app_user
    USING (true);

-- 13. questions (institute_id NULL = shared public question bank; non-NULL = tenant-private item)
CREATE TABLE questions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    institute_id uuid REFERENCES institutes(id) ON DELETE CASCADE,
    subject text NOT NULL,
    text_hash text NOT NULL,
    q_type text NOT NULL CHECK (q_type IN ('mcq_single', 'mcq_multi', 'numeric')),
    options_n integer NOT NULL DEFAULT 4 CHECK (options_n >= 0 AND options_n <= 10),
    created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE questions IS 'Question item bank. Rows with institute_id IS NULL belong to the shared public pool (writable only by admin/training role, read-only for app_user).';
COMMENT ON COLUMN questions.text_hash IS 'SHA-256 hash of normalized question stem for deduplication and anchor item matching.';

CREATE INDEX idx_questions_institute ON questions(institute_id);

ALTER TABLE questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE questions FORCE ROW LEVEL SECURITY;
CREATE POLICY questions_tenant_or_shared_select ON questions
    FOR SELECT TO app_user
    USING (institute_id IS NULL OR institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);
CREATE POLICY questions_tenant_insert ON questions
    FOR INSERT TO app_user
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);
CREATE POLICY questions_tenant_update ON questions
    FOR UPDATE TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);
CREATE POLICY questions_tenant_delete ON questions
    FOR DELETE TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- Trigger function to enforce that child tables of questions (question_topics, item_params)
-- always carry the exact same institute_id (including NULL for shared items) as their parent question.
CREATE OR REPLACE FUNCTION enforce_question_child_institute_id()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent_inst_id uuid;
BEGIN
    SELECT q.institute_id INTO parent_inst_id
    FROM questions q
    WHERE q.id = NEW.question_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Parent question % does not exist', NEW.question_id;
    END IF;

    IF NEW.institute_id IS DISTINCT FROM parent_inst_id THEN
        RAISE EXCEPTION 'Child institute_id (%) must match parent questions.institute_id (%) for question %',
            NEW.institute_id, parent_inst_id, NEW.question_id;
    END IF;

    RETURN NEW;
END;
$$;

-- 14. question_topics (institute_id copied from parent question; NULL = shared, non-NULL = tenant-private)
CREATE TABLE question_topics (
    question_id uuid NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    institute_id uuid REFERENCES institutes(id) ON DELETE CASCADE,
    topic_id text NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    weight double precision NOT NULL DEFAULT 1.0 CHECK (weight > 0.0 AND weight <= 1.0),
    tagged_by text NOT NULL CHECK (tagged_by IN ('human', 'embedding_llm', 'keyword_rule')),
    confidence double precision NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    reviewed_by uuid REFERENCES users(id),
    PRIMARY KEY (question_id, topic_id)
);

COMMENT ON TABLE question_topics IS 'Mapping of questions to syllabus topics. institute_id mirrors questions.institute_id via trigger to prevent cross-tenant metadata leaks.';
COMMENT ON COLUMN question_topics.institute_id IS 'Null for shared public questions; tenant UUID for private institute questions (must equal questions.institute_id).';

CREATE INDEX idx_question_topics_institute ON question_topics(institute_id);

CREATE TRIGGER trg_question_topics_match_institute
    BEFORE INSERT OR UPDATE ON question_topics
    FOR EACH ROW EXECUTE FUNCTION enforce_question_child_institute_id();

ALTER TABLE question_topics ENABLE ROW LEVEL SECURITY;
ALTER TABLE question_topics FORCE ROW LEVEL SECURITY;
CREATE POLICY question_topics_tenant_or_shared_select ON question_topics
    FOR SELECT TO app_user
    USING (institute_id IS NULL OR institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);
CREATE POLICY question_topics_tenant_insert ON question_topics
    FOR INSERT TO app_user
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);
CREATE POLICY question_topics_tenant_update ON question_topics
    FOR UPDATE TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);
CREATE POLICY question_topics_tenant_delete ON question_topics
    FOR DELETE TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- 15. item_params (institute_id copied from parent question; NULL = shared pool, non-NULL = tenant-private)
CREATE TABLE item_params (
    question_id uuid NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    institute_id uuid REFERENCES institutes(id) ON DELETE CASCADE,
    model_version text NOT NULL REFERENCES model_registry(version) ON DELETE CASCADE,
    a double precision NOT NULL CHECK (a > 0.0),
    b double precision NOT NULL,
    g double precision NOT NULL DEFAULT 0.0 CHECK (g >= 0.0 AND g <= 0.5),
    se_b double precision NOT NULL CHECK (se_b >= 0.0),
    n_responses integer NOT NULL CHECK (n_responses >= 0),
    fit_flag text NOT NULL DEFAULT 'ok' CHECK (fit_flag IN ('ok', 'suspect_wrong_key', 'low_discrimination', 'too_few_responses')),
    PRIMARY KEY (question_id, model_version)
);

COMMENT ON TABLE item_params IS 'Calibrated IRT item parameters. Private question parameters and suspect_wrong_key flags are isolated to their owning institute via RLS.';
COMMENT ON COLUMN item_params.institute_id IS 'Null for shared public questions (k-anonymous pool); tenant UUID for private questions (must equal questions.institute_id).';
COMMENT ON COLUMN item_params.a IS 'Item discrimination parameter (fixed to 1.0 under Rasch fallback when n_responses < 50).';
COMMENT ON COLUMN item_params.b IS 'Item difficulty on the logit scale.';
COMMENT ON COLUMN item_params.g IS 'Guessing floor parameter (prior Beta(2,18) for MCQ, 0 for numeric).';
COMMENT ON COLUMN item_params.fit_flag IS 'Diagnostic flag; negative point-biserial or poor fit sets suspect_wrong_key.';

CREATE INDEX idx_item_params_institute ON item_params(institute_id);

CREATE TRIGGER trg_item_params_match_institute
    BEFORE INSERT OR UPDATE ON item_params
    FOR EACH ROW EXECUTE FUNCTION enforce_question_child_institute_id();

ALTER TABLE item_params ENABLE ROW LEVEL SECURITY;
ALTER TABLE item_params FORCE ROW LEVEL SECURITY;
CREATE POLICY item_params_tenant_or_shared_select ON item_params
    FOR SELECT TO app_user
    USING (institute_id IS NULL OR institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);
CREATE POLICY item_params_tenant_insert ON item_params
    FOR INSERT TO app_user
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);
CREATE POLICY item_params_tenant_update ON item_params
    FOR UPDATE TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);
CREATE POLICY item_params_tenant_delete ON item_params
    FOR DELETE TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- 16. tests
CREATE TABLE tests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    institute_id uuid NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
    batch_id uuid NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    name text NOT NULL,
    test_date date NOT NULL,
    exam_pattern_code text NOT NULL,
    marking_scheme_id text NOT NULL REFERENCES marking_schemes(id),
    max_marks double precision NOT NULL CHECK (max_marks > 0.0),
    source text NOT NULL CHECK (source IN ('omr', 'csv', 'online')),
    day_after_off_warning boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE tests IS 'Internal mock or chapter assessments administered to a batch.';
COMMENT ON COLUMN tests.day_after_off_warning IS 'True if test_date falls immediately after the institute weekly_off_day (MoE 2024 cl. 10.1(vi) check).';

CREATE INDEX idx_tests_institute_batch_date ON tests(institute_id, batch_id, test_date);

ALTER TABLE tests ENABLE ROW LEVEL SECURITY;
ALTER TABLE tests FORCE ROW LEVEL SECURITY;
CREATE POLICY tests_tenant_isolation ON tests
    FOR ALL TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- 17. test_questions
CREATE TABLE test_questions (
    institute_id uuid NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
    test_id uuid NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    question_id uuid NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
    position integer NOT NULL CHECK (position >= 1),
    section text NOT NULL DEFAULT 'A',
    PRIMARY KEY (test_id, question_id),
    UNIQUE (test_id, position)
);

COMMENT ON TABLE test_questions IS 'Ordered list of questions included in a specific test paper.';

ALTER TABLE test_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE test_questions FORCE ROW LEVEL SECURITY;
CREATE POLICY test_questions_tenant_isolation ON test_questions
    FOR ALL TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- 18. answer_keys
CREATE TABLE answer_keys (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    institute_id uuid NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
    test_id uuid NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    question_id uuid NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
    accepted_answers text[] NOT NULL,
    numeric_tolerance double precision NOT NULL DEFAULT 0.0 CHECK (numeric_tolerance >= 0.0),
    dropped boolean NOT NULL DEFAULT false,
    version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_by uuid REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (test_id, question_id, version)
);

COMMENT ON TABLE answer_keys IS 'Versioned answer keys supporting multi-correct arrays, numeric tolerances, and dropped-question bonus re-scoring.';
COMMENT ON COLUMN answer_keys.accepted_answers IS 'Set of valid options (e.g. {A,C}) or target numeric value as text.';
COMMENT ON COLUMN answer_keys.dropped IS 'When true, question is officially dropped and scored per marking_schemes.dropped_rule.';

CREATE INDEX idx_answer_keys_test_q ON answer_keys(institute_id, test_id, question_id, version DESC);

ALTER TABLE answer_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE answer_keys FORCE ROW LEVEL SECURITY;
CREATE POLICY answer_keys_tenant_isolation ON answer_keys
    FOR ALL TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- 19. responses
CREATE TABLE responses (
    institute_id uuid NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
    test_id uuid NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    student_id uuid NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    question_id uuid NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
    response text,
    is_correct boolean NOT NULL,
    marks_awarded double precision NOT NULL,
    status text NOT NULL CHECK (status IN ('answered', 'blank', 'multi_marked', 'unreadable')),
    confidence double precision NOT NULL DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    PRIMARY KEY (test_id, student_id, question_id)
);

COMMENT ON TABLE responses IS 'Item-level student responses from OMR, CSV, or online tests. Blanks are scored as incorrect in IRT.';
COMMENT ON COLUMN responses.status IS 'Distinguishes intentional blanks from OMR multi_marked or unreadable bubbles.';
COMMENT ON COLUMN responses.confidence IS 'OMR bubble read confidence in [0, 1]; low confidence triggers human review before confirmation.';

CREATE INDEX idx_responses_student_test ON responses(institute_id, student_id, test_id);

ALTER TABLE responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE responses FORCE ROW LEVEL SECURITY;
CREATE POLICY responses_tenant_isolation ON responses
    FOR ALL TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- 20. test_totals
CREATE TABLE test_totals (
    institute_id uuid NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
    test_id uuid NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    student_id uuid NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    raw_score double precision,
    physics_score double precision,
    chemistry_score double precision,
    math_or_bio_score double precision,
    absent_flag boolean NOT NULL DEFAULT false,
    PRIMARY KEY (test_id, student_id)
);

COMMENT ON TABLE test_totals IS 'Aggregate test scores per student. Supports marks-only institutes that do not upload question-level responses.';

CREATE INDEX idx_test_totals_student ON test_totals(institute_id, student_id);

ALTER TABLE test_totals ENABLE ROW LEVEL SECURITY;
ALTER TABLE test_totals FORCE ROW LEVEL SECURITY;
CREATE POLICY test_totals_tenant_isolation ON test_totals
    FOR ALL TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- 21. attendance
CREATE TABLE attendance (
    institute_id uuid NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
    student_id uuid NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    attendance_date date NOT NULL,
    present_flag boolean NOT NULL,
    source text NOT NULL DEFAULT 'csv' CHECK (source IN ('csv', 'manual', 'biometric')),
    PRIMARY KEY (student_id, attendance_date)
);

COMMENT ON TABLE attendance IS 'Daily class attendance register (Feature Tier B).';

CREATE INDEX idx_attendance_institute_student_date ON attendance(institute_id, student_id, attendance_date DESC);

ALTER TABLE attendance ENABLE ROW LEVEL SECURITY;
ALTER TABLE attendance FORCE ROW LEVEL SECURITY;
CREATE POLICY attendance_tenant_isolation ON attendance
    FOR ALL TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- 22. fees
CREATE TABLE fees (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    institute_id uuid NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
    student_id uuid NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    instalment_no integer NOT NULL CHECK (instalment_no >= 1 AND instalment_no <= 12),
    due_date date NOT NULL,
    amount_paise bigint NOT NULL CHECK (amount_paise >= 0),
    paid_date date,
    paid_amount_paise bigint NOT NULL DEFAULT 0 CHECK (paid_amount_paise >= 0),
    refund_due_paise bigint NOT NULL DEFAULT 0 CHECK (refund_due_paise >= 0),
    refund_paid_date date,
    UNIQUE (student_id, instalment_no)
);

COMMENT ON TABLE fees IS 'Tuition fee instalment ledger in integer paise (Feature Tier C). Supports 10-day pro-rata refund tracking per MoE cl. 8(iv).';
COMMENT ON COLUMN fees.amount_paise IS 'Scheduled instalment amount in integer paise (1 INR = 100 paise).';
COMMENT ON COLUMN fees.refund_due_paise IS 'Calculated pro-rata refund due upon mid-course withdrawal.';

CREATE INDEX idx_fees_institute_student_due ON fees(institute_id, student_id, due_date);

ALTER TABLE fees ENABLE ROW LEVEL SECURITY;
ALTER TABLE fees FORCE ROW LEVEL SECURITY;
CREATE POLICY fees_tenant_isolation ON fees
    FOR ALL TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- 23. engagement
CREATE TABLE engagement (
    institute_id uuid NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
    student_id uuid NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    activity_date date NOT NULL,
    doubts_asked integer NOT NULL DEFAULT 0 CHECK (doubts_asked >= 0),
    homework_submitted boolean NOT NULL DEFAULT false,
    app_logins integer NOT NULL DEFAULT 0 CHECK (app_logins >= 0),
    PRIMARY KEY (student_id, activity_date)
);

COMMENT ON TABLE engagement IS 'Digital engagement signals (Feature Tier D). Strictly off by default and never used for minors under DPDP s.9(3).';

ALTER TABLE engagement ENABLE ROW LEVEL SECURITY;
ALTER TABLE engagement FORCE ROW LEVEL SECURITY;
CREATE POLICY engagement_tenant_isolation ON engagement
    FOR ALL TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- 24. mastery_snapshots
CREATE TABLE mastery_snapshots (
    institute_id uuid NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
    student_id uuid NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    topic_id text NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    theta double precision NOT NULL,
    se double precision NOT NULL CHECK (se >= 0.0),
    band text NOT NULL CHECK (band IN ('not_enough_data', 'building', 'steady', 'strong')),
    n_items integer NOT NULL CHECK (n_items >= 0),
    computed_at timestamptz NOT NULL DEFAULT now(),
    model_version text NOT NULL REFERENCES model_registry(version),
    PRIMARY KEY (student_id, topic_id, computed_at)
);

COMMENT ON TABLE mastery_snapshots IS 'Per-topic EAP ability estimates shrunk toward student overall ability and batch mean.';
COMMENT ON COLUMN mastery_snapshots.band IS 'Categorical mastery band; set to not_enough_data whenever se exceeds threshold tau.';

CREATE INDEX idx_mastery_student_latest ON mastery_snapshots(institute_id, student_id, computed_at DESC);

ALTER TABLE mastery_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE mastery_snapshots FORCE ROW LEVEL SECURITY;
CREATE POLICY mastery_snapshots_tenant_isolation ON mastery_snapshots
    FOR ALL TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- 25. risk_scores
CREATE TABLE risk_scores (
    institute_id uuid NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
    student_id uuid NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    as_of date NOT NULL,
    target text NOT NULL CHECK (target IN ('academic_support', 'retention', 'fee')),
    routing_method text NOT NULL CHECK (routing_method IN ('ml', 'rules', 'none')),
    p double precision CHECK (p IS NULL OR (p >= 0.0 AND p <= 1.0)),
    band text NOT NULL CHECK (band IN ('low', 'watch', 'needs_support')),
    reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
    feature_tier text NOT NULL CHECK (feature_tier IN ('A', 'B', 'C', 'D')),
    model_version text NOT NULL REFERENCES model_registry(version),
    PRIMARY KEY (student_id, as_of, target)
);

COMMENT ON TABLE risk_scores IS 'Purpose- and age-routed early-warning scores and plain-language supportive reasons.';
COMMENT ON COLUMN risk_scores.routing_method IS 'Records whether score was produced by ML or transparent rules per routing_policy.yaml.';
COMMENT ON COLUMN risk_scores.p IS 'Calibrated probability in [0, 1] when routing_method = ml; null or rule indicator when routing_method = rules.';

CREATE INDEX idx_risk_scores_batch_lookup ON risk_scores(institute_id, as_of DESC, target, band);

ALTER TABLE risk_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_scores FORCE ROW LEVEL SECURITY;
CREATE POLICY risk_scores_tenant_isolation ON risk_scores
    FOR ALL TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- 26. predictions
CREATE TABLE predictions (
    institute_id uuid NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
    student_id uuid NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    as_of date NOT NULL,
    q10 double precision NOT NULL,
    q50 double precision NOT NULL,
    q90 double precision NOT NULL,
    mapped_low double precision NOT NULL CHECK (mapped_low >= 0.0 AND mapped_low <= 100.0),
    mapped_high double precision NOT NULL CHECK (mapped_high >= 0.0 AND mapped_high <= 100.0),
    coverage_level double precision NOT NULL DEFAULT 0.80 CHECK (coverage_level > 0.0 AND coverage_level < 1.0),
    model_version text NOT NULL REFERENCES model_registry(version),
    PRIMARY KEY (student_id, as_of),
    CHECK (q10 <= q50 AND q50 <= q90),
    CHECK (mapped_low <= mapped_high)
);

COMMENT ON TABLE predictions IS 'Two-stage conformalized quantile regression (CQR) internal score band and mapped NTA percentile range.';
COMMENT ON COLUMN predictions.mapped_low IS 'Lower bound of predicted NTA percentile range (never a single point estimate).';
COMMENT ON COLUMN predictions.mapped_high IS 'Upper bound of predicted NTA percentile range including shift-difficulty uncertainty.';

ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions FORCE ROW LEVEL SECURITY;
CREATE POLICY predictions_tenant_isolation ON predictions
    FOR ALL TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- 27. interventions
CREATE TABLE interventions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    institute_id uuid NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
    student_id uuid NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    type text NOT NULL CHECK (type IN ('mentoring', 'counselling_referral', 'remedial_session', 'fee_plan_discussion', 'parent_call')),
    owner_user_id uuid NOT NULL REFERENCES users(id),
    due_date date NOT NULL,
    done_at timestamptz,
    outcome text NOT NULL DEFAULT 'pending' CHECK (outcome IN ('pending', 'completed_improved', 'completed_no_change', 'escalated_to_counsellor', 'parent_unreachable', 'declined')),
    created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE interventions IS 'Supportive mentor actions and outcomes. No clinical or mental-health notes are permitted.';

CREATE INDEX idx_interventions_institute_student ON interventions(institute_id, student_id, due_date);

ALTER TABLE interventions ENABLE ROW LEVEL SECURITY;
ALTER TABLE interventions FORCE ROW LEVEL SECURITY;
CREATE POLICY interventions_tenant_isolation ON interventions
    FOR ALL TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- 28. reports
CREATE TABLE reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    institute_id uuid NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
    student_id uuid NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    period text NOT NULL,
    lang text NOT NULL CHECK (lang IN ('en', 'hi')),
    numbers_json jsonb NOT NULL,
    content text NOT NULL,
    verified boolean NOT NULL,
    path text NOT NULL CHECK (path IN ('llm', 'template')),
    model_version text NOT NULL REFERENCES model_registry(version),
    sent_via text NOT NULL DEFAULT 'none' CHECK (sent_via IN ('none', 'whatsapp_preview', 'pdf_download', 'portal_view')),
    sent_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE reports IS 'Bilingual parent progress reports verified against numbers_json with zero unverified numbers.';
COMMENT ON COLUMN reports.numbers_json IS 'Deterministic fact payload containing {STUDENT} and {INSTITUTE} placeholders (never raw PII).';
COMMENT ON COLUMN reports.path IS 'Whether final text came from verified local LLM output or deterministic human template.';

CREATE INDEX idx_reports_institute_student ON reports(institute_id, student_id, created_at DESC);

ALTER TABLE reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports FORCE ROW LEVEL SECURITY;
CREATE POLICY reports_tenant_isolation ON reports
    FOR ALL TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- 29. ingest_jobs
CREATE TABLE ingest_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    institute_id uuid NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
    file_hash text NOT NULL,
    type text NOT NULL CHECK (type IN ('students', 'guardians', 'results_responses', 'results_marks_only', 'answer_key', 'attendance', 'fees', 'omr_photos')),
    status text NOT NULL CHECK (status IN ('pending_mapping', 'preview_ready', 'awaiting_review', 'confirmed', 'failed')),
    mapping jsonb NOT NULL DEFAULT '{}'::jsonb,
    errors jsonb NOT NULL DEFAULT '[]'::jsonb,
    rows_ok integer NOT NULL DEFAULT 0 CHECK (rows_ok >= 0),
    rows_failed integer NOT NULL DEFAULT 0 CHECK (rows_failed >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (institute_id, file_hash)
);

COMMENT ON TABLE ingest_jobs IS 'Idempotent data upload jobs tracked by SHA-256 file_hash per institute.';

ALTER TABLE ingest_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE ingest_jobs FORCE ROW LEVEL SECURITY;
CREATE POLICY ingest_jobs_tenant_isolation ON ingest_jobs
    FOR ALL TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- 30. omr_templates
CREATE TABLE omr_templates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    institute_id uuid NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
    name text NOT NULL,
    layout jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (institute_id, name)
);

COMMENT ON TABLE omr_templates IS 'Registered OMR sheet geometry layouts conforming to omr_template.schema.json.';

ALTER TABLE omr_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE omr_templates FORCE ROW LEVEL SECURITY;
CREATE POLICY omr_templates_tenant_isolation ON omr_templates
    FOR ALL TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- 31. audit_log
CREATE TABLE audit_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor uuid NOT NULL REFERENCES users(id),
    institute_id uuid NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
    action text NOT NULL CHECK (action IN ('view_risk_scores', 'view_student_profile', 'export_register', 'update_legal_settings', 'update_privacy_tier', 'grant_consent', 'revoke_consent', 'update_answer_key', 'create_intervention', 'generate_report')),
    entity text NOT NULL,
    entity_id text NOT NULL,
    occurred_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE audit_log IS 'Immutable security and privacy access log retained >= 1 year per DPDP Rule 6(1)(e). Contains no PII payload.';

CREATE INDEX idx_audit_log_institute_time ON audit_log(institute_id, occurred_at DESC);

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log FORCE ROW LEVEL SECURITY;
CREATE POLICY audit_log_tenant_isolation ON audit_log
    FOR ALL TO app_user
    USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
    WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid);

-- Privilege grants for app_user:
-- Global read-only reference tables receive SELECT only; tenant tables receive SELECT, INSERT, UPDATE, DELETE (gated by forced RLS).
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM app_user;
GRANT SELECT ON topics, topic_prereqs, model_registry, marking_schemes TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON
    institutes, users, legal_settings, batches, students, batch_changes,
    guardians, consents, questions, question_topics, item_params, tests,
    test_questions, answer_keys, responses, test_totals, attendance,
    fees, engagement, mastery_snapshots, risk_scores, predictions,
    interventions, reports, ingest_jobs, omr_templates, audit_log
TO app_user;
