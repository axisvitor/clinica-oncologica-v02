-- ================================================================
-- INCREMENTAL RLS ROLLOUT - PHASE 1
-- Safe, idempotent migration for Row Level Security
-- ================================================================
-- Date: 2025-09-29
-- Version: 1.0.0
--
-- This script implements RLS incrementally, starting with read-only
-- policies for core tables. It's safe to run multiple times.
-- ================================================================

-- Start transaction
BEGIN;

-- ================================================================
-- HELPER FUNCTIONS
-- ================================================================

-- Create auth schema if not exists (for Supabase compatibility)
CREATE SCHEMA IF NOT EXISTS auth;

-- Create auth.uid() function if not exists
CREATE OR REPLACE FUNCTION auth.uid()
RETURNS uuid
LANGUAGE sql
STABLE
AS $$
    SELECT
        CASE
            WHEN current_setting('request.jwt.claims', true) IS NOT NULL
            THEN (current_setting('request.jwt.claims', true)::json->>'sub')::uuid
            ELSE NULL
        END;
$$;

-- Create auth.role() function if not exists
CREATE OR REPLACE FUNCTION auth.role()
RETURNS text
LANGUAGE sql
STABLE
AS $$
    SELECT
        CASE
            WHEN current_setting('request.jwt.claims', true) IS NOT NULL
            THEN current_setting('request.jwt.claims', true)::json->>'role'
            ELSE NULL
        END;
$$;

-- Create auth.email() function if not exists
CREATE OR REPLACE FUNCTION auth.email()
RETURNS text
LANGUAGE sql
STABLE
AS $$
    SELECT
        CASE
            WHEN current_setting('request.jwt.claims', true) IS NOT NULL
            THEN current_setting('request.jwt.claims', true)::json->>'email'
            ELSE NULL
        END;
$$;

-- ================================================================
-- PHASE 1: Enable RLS on core tables (without breaking anything)
-- ================================================================

-- Enable RLS on tables that should have it (idempotent)
DO $$
DECLARE
    v_table_name TEXT;
    v_tables TEXT[] := ARRAY[
        'users',
        'patients',
        'messages',
        'medical_reports',
        'flow_states',
        'quiz_sessions',
        'quiz_responses'
    ];
BEGIN
    FOREACH v_table_name IN ARRAY v_tables
    LOOP
        -- Check if table exists and enable RLS
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = v_table_name
        ) THEN
            -- Enable RLS (idempotent)
            EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', v_table_name);
            RAISE NOTICE 'RLS enabled on table: %', v_table_name;
        END IF;
    END LOOP;
END $$;

-- ================================================================
-- PHASE 1 POLICIES: Read-only policies first
-- ================================================================

-- Drop existing policies if they exist (for clean slate)
DROP POLICY IF EXISTS "users_select_own_or_admin" ON public.users;
DROP POLICY IF EXISTS "patients_select_doctor_or_admin" ON public.patients;
DROP POLICY IF EXISTS "messages_select_doctor_or_admin" ON public.messages;
DROP POLICY IF EXISTS "medical_reports_select_doctor_or_admin" ON public.medical_reports;
DROP POLICY IF EXISTS "flow_states_select_doctor_or_admin" ON public.flow_states;
DROP POLICY IF EXISTS "quiz_sessions_select_doctor_or_admin" ON public.quiz_sessions;
DROP POLICY IF EXISTS "quiz_responses_select_doctor_or_admin" ON public.quiz_responses;

-- Users table: Users can see their own profile, admins see all
CREATE POLICY "users_select_own_or_admin" ON public.users
FOR SELECT TO authenticated
USING (
    id = auth.uid()
    OR auth.role() = 'admin'
);

-- Patients table: Doctors see their patients, admins see all
CREATE POLICY "patients_select_doctor_or_admin" ON public.patients
FOR SELECT TO authenticated
USING (
    doctor_id = auth.uid()
    OR auth.role() = 'admin'
);

-- Messages table: See messages for your patients
CREATE POLICY "messages_select_doctor_or_admin" ON public.messages
FOR SELECT TO authenticated
USING (
    EXISTS (
        SELECT 1 FROM public.patients p
        WHERE p.id = messages.patient_id
        AND (p.doctor_id = auth.uid() OR auth.role() = 'admin')
    )
);

-- Medical reports: See reports for your patients
-- Note: Check if 'patient_id' column exists first
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'medical_reports'
        AND column_name = 'patient_id'
    ) THEN
        CREATE POLICY "medical_reports_select_doctor_or_admin" ON public.medical_reports
        FOR SELECT TO authenticated
        USING (
            EXISTS (
                SELECT 1 FROM public.patients p
                WHERE p.id = medical_reports.patient_id
                AND (p.doctor_id = auth.uid() OR auth.role() = 'admin')
            )
        );
        RAISE NOTICE 'Policy created for medical_reports with patient_id';
    ELSE
        -- If no patient_id, create a simpler policy
        CREATE POLICY "medical_reports_select_doctor_or_admin" ON public.medical_reports
        FOR SELECT TO authenticated
        USING (auth.role() IN ('admin', 'doctor'));
        RAISE NOTICE 'Policy created for medical_reports without patient_id';
    END IF;
END $$;

-- Flow states: See flow states for your patients
CREATE POLICY "flow_states_select_doctor_or_admin" ON public.flow_states
FOR SELECT TO authenticated
USING (
    EXISTS (
        SELECT 1 FROM public.patients p
        WHERE p.id = flow_states.patient_id
        AND (p.doctor_id = auth.uid() OR auth.role() = 'admin')
    )
);

-- Quiz sessions: See quiz sessions for your patients
CREATE POLICY "quiz_sessions_select_doctor_or_admin" ON public.quiz_sessions
FOR SELECT TO authenticated
USING (
    EXISTS (
        SELECT 1 FROM public.patients p
        WHERE p.id = quiz_sessions.patient_id
        AND (p.doctor_id = auth.uid() OR auth.role() = 'admin')
    )
);

-- Quiz responses: See quiz responses for sessions you can access
CREATE POLICY "quiz_responses_select_doctor_or_admin" ON public.quiz_responses
FOR SELECT TO authenticated
USING (
    EXISTS (
        SELECT 1 FROM public.quiz_sessions qs
        JOIN public.patients p ON p.id = qs.patient_id
        WHERE qs.id = quiz_responses.session_id
        AND (p.doctor_id = auth.uid() OR auth.role() = 'admin')
    )
);

-- ================================================================
-- CREATE INDEXES FOR PERFORMANCE
-- ================================================================

-- Create indexes if they don't exist
CREATE INDEX IF NOT EXISTS idx_patients_doctor_id ON public.patients(doctor_id);
CREATE INDEX IF NOT EXISTS idx_messages_patient_id ON public.messages(patient_id);
CREATE INDEX IF NOT EXISTS idx_flow_states_patient_id ON public.flow_states(patient_id);
CREATE INDEX IF NOT EXISTS idx_quiz_sessions_patient_id ON public.quiz_sessions(patient_id);
CREATE INDEX IF NOT EXISTS idx_quiz_responses_session_id ON public.quiz_responses(session_id);

-- Create index on medical_reports if patient_id exists
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'medical_reports'
        AND column_name = 'patient_id'
    ) THEN
        CREATE INDEX IF NOT EXISTS idx_medical_reports_patient_id ON public.medical_reports(patient_id);
    END IF;
END $$;

-- ================================================================
-- MONITORING VIEW
-- ================================================================

-- Create or replace RLS status monitoring view
CREATE OR REPLACE VIEW public.rls_rollout_status AS
SELECT
    t.schemaname,
    t.tablename,
    t.rowsecurity as rls_enabled,
    COUNT(p.policyname) as policy_count,
    ARRAY_AGG(p.policyname) as policies,
    CASE
        WHEN t.tablename = 'alembic_version' THEN 'SKIP - System Table'
        WHEN t.rowsecurity = false THEN '❌ RLS Disabled'
        WHEN t.rowsecurity = true AND COUNT(p.policyname) = 0 THEN '⚠️ RLS Enabled but No Policies'
        WHEN t.rowsecurity = true AND COUNT(p.policyname) > 0 THEN '✅ Protected'
        ELSE 'Unknown'
    END as status
FROM pg_tables t
LEFT JOIN pg_policies p ON t.tablename = p.tablename AND t.schemaname = p.schemaname
WHERE t.schemaname = 'public'
AND t.tablename IN (
    'users', 'patients', 'messages', 'medical_reports',
    'flow_states', 'quiz_sessions', 'quiz_responses'
)
GROUP BY t.schemaname, t.tablename, t.rowsecurity
ORDER BY t.tablename;

-- Grant select on monitoring view
GRANT SELECT ON public.rls_rollout_status TO authenticated;

-- ================================================================
-- VERIFICATION
-- ================================================================

-- Display the current RLS status
SELECT * FROM public.rls_rollout_status;

-- ================================================================
-- ROLLBACK PREPARATION (commented out, use only if needed)
-- ================================================================

/*
-- To rollback Phase 1, run this:
BEGIN;

-- Drop policies
DROP POLICY IF EXISTS "users_select_own_or_admin" ON public.users;
DROP POLICY IF EXISTS "patients_select_doctor_or_admin" ON public.patients;
DROP POLICY IF EXISTS "messages_select_doctor_or_admin" ON public.messages;
DROP POLICY IF EXISTS "medical_reports_select_doctor_or_admin" ON public.medical_reports;
DROP POLICY IF EXISTS "flow_states_select_doctor_or_admin" ON public.flow_states;
DROP POLICY IF EXISTS "quiz_sessions_select_doctor_or_admin" ON public.quiz_sessions;
DROP POLICY IF EXISTS "quiz_responses_select_doctor_or_admin" ON public.quiz_responses;

-- Disable RLS
ALTER TABLE public.users DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.patients DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.medical_reports DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.flow_states DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.quiz_sessions DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.quiz_responses DISABLE ROW LEVEL SECURITY;

COMMIT;
*/

-- ================================================================
-- COMMIT TRANSACTION
-- ================================================================

COMMIT;

-- ================================================================
-- POST-MIGRATION NOTES
-- ================================================================

/*
After running this migration:

1. Test read-only endpoints with the new RLS dependency:
   - GET /api/v1/patients
   - GET /api/v1/messages
   - GET /api/v1/quiz/sessions

2. Monitor for any permission errors in logs

3. If everything works, proceed to Phase 2:
   - Add INSERT/UPDATE/DELETE policies
   - Migrate more endpoints to RLS-aware dependency

4. To verify RLS is working:
   - Login as a doctor and check you only see your patients
   - Login as admin and check you see all patients

5. Performance monitoring:
   - Check query times haven't degraded significantly
   - Monitor index usage with pg_stat_user_indexes
*/