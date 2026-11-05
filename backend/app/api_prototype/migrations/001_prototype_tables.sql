-- Prototype API tables (PROTOTYPE_PLAN S3). contract: tenant pattern of contracts/schema.sql.
--
-- *** NOT FOR ANY SHARED OR PRODUCTION DATABASE. ***
-- attempt_events is ADR-003, which is still PROPOSED. Apply only to a throw-away database that
-- already holds contracts/schema.sql (these tables reference institutes). Reversible: see the end.
--
-- Same RLS pattern as contracts/schema.sql: institute_id column, ENABLE + FORCE ROW LEVEL SECURITY,
-- a policy FOR ALL TO app_user keyed on current_setting('app.institute_id', true) with WITH CHECK.
-- ids other than institute_id are text: the prototype uses stand-in learner, cohort and user ids and
-- is not yet joined to students/users (open item).
-- attempt_events is append-only for app_user (no UPDATE, no DELETE grant).

CREATE TABLE proto_users (
    institute_id uuid NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
    user_id text NOT NULL,
    role text NOT NULL CHECK (role IN ('student', 'teacher', 'owner')),
    PRIMARY KEY (institute_id, user_id)
);

CREATE TABLE proto_cohorts (
    institute_id uuid NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
    cohort_id text NOT NULL,
    PRIMARY KEY (institute_id, cohort_id)
);

CREATE TABLE proto_cohort_teachers (
    institute_id uuid NOT NULL,
    cohort_id text NOT NULL,
    user_id text NOT NULL,
    PRIMARY KEY (institute_id, cohort_id, user_id),
    FOREIGN KEY (institute_id, cohort_id) REFERENCES proto_cohorts(institute_id, cohort_id) ON DELETE CASCADE,
    FOREIGN KEY (institute_id, user_id) REFERENCES proto_users(institute_id, user_id) ON DELETE CASCADE
);

CREATE TABLE proto_learners (
    institute_id uuid NOT NULL REFERENCES institutes(id) ON DELETE CASCADE,
    learner_id text NOT NULL,
    cohort_id text,
    goal text NOT NULL,
    day_counter integer NOT NULL DEFAULT 0 CHECK (day_counter >= 0),
    PRIMARY KEY (institute_id, learner_id),
    FOREIGN KEY (institute_id, cohort_id) REFERENCES proto_cohorts(institute_id, cohort_id)
);
COMMENT ON COLUMN proto_learners.day_counter IS
    'Attempt-count clock: +1 per accepted attempt, in the same transaction. Not a calendar day, not a time measurement.';

CREATE TABLE attempt_events (
    institute_id uuid NOT NULL,
    event_id text NOT NULL,
    learner_id text NOT NULL,
    concept_id text NOT NULL,
    item_id text NOT NULL,
    correct boolean NOT NULL,
    seq integer NOT NULL CHECK (seq >= 0),
    PRIMARY KEY (institute_id, event_id),
    UNIQUE (institute_id, learner_id, seq),
    FOREIGN KEY (institute_id, learner_id) REFERENCES proto_learners(institute_id, learner_id) ON DELETE CASCADE
);
COMMENT ON TABLE attempt_events IS 'ADR-003 (proposed): append-only attempt log. No response time, no hint fields.';

CREATE TABLE proto_served_items (
    institute_id uuid NOT NULL,
    learner_id text NOT NULL,
    item_id text NOT NULL,
    concept_id text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('practice', 'recheck')),
    answered_event_id text,
    PRIMARY KEY (institute_id, learner_id, item_id),
    FOREIGN KEY (institute_id, learner_id) REFERENCES proto_learners(institute_id, learner_id) ON DELETE CASCADE,
    FOREIGN KEY (institute_id, answered_event_id) REFERENCES attempt_events(institute_id, event_id)
        DEFERRABLE INITIALLY DEFERRED
);

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['proto_users', 'proto_cohorts', 'proto_cohort_teachers', 'proto_learners',
                             'attempt_events', 'proto_served_items']
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format($p$CREATE POLICY %I ON %I FOR ALL TO app_user
            USING (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)
            WITH CHECK (institute_id = NULLIF(current_setting('app.institute_id', true), '')::uuid)$p$,
            t || '_tenant_isolation', t);
    END LOOP;
END
$$;

GRANT SELECT, INSERT, UPDATE, DELETE ON proto_users, proto_cohorts, proto_cohort_teachers,
    proto_learners, proto_served_items TO app_user;
GRANT SELECT, INSERT ON attempt_events TO app_user;
GRANT SELECT ON institutes TO app_user;

-- Rollback (throw-away databases only):
--   DROP TABLE proto_served_items, attempt_events, proto_learners, proto_cohort_teachers,
--              proto_cohorts, proto_users;
