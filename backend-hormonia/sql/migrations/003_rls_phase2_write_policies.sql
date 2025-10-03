-- ================================================================
-- RLS PHASE 2: WRITE POLICIES (INSERT/UPDATE/DELETE)
-- ================================================================
-- Date: 2025-09-29
-- Version: 2.0.0
-- Prerequisites: 002_incremental_rls_rollout.sql must be applied first
--
-- This migration adds write policies to complement the read-only
-- policies from Phase 1. It allows controlled data modification
-- while maintaining security.
-- ================================================================

-- Start transaction
BEGIN;

-- ================================================================
-- VERIFICATION: Check Phase 1 is complete
-- ================================================================
DO $$
DECLARE
    v_phase1_tables INTEGER;
    v_phase1_policies INTEGER;
BEGIN
    -- Count tables with RLS enabled
    SELECT COUNT(*) INTO v_phase1_tables
    FROM pg_tables
    WHERE schemaname = 'public'
    AND rowsecurity = true
    AND tablename IN ('users', 'patients', 'messages', 'medical_reports',
                      'flow_states', 'quiz_sessions', 'quiz_responses');

    -- Count existing read policies
    SELECT COUNT(*) INTO v_phase1_policies
    FROM pg_policies
    WHERE schemaname = 'public'
    AND cmd = 'SELECT';

    -- Verify Phase 1 is complete
    IF v_phase1_tables < 7 THEN
        RAISE EXCEPTION 'Phase 1 incomplete: Only % tables have RLS enabled (expected 7)', v_phase1_tables;
    END IF;

    IF v_phase1_policies < 7 THEN
        RAISE EXCEPTION 'Phase 1 incomplete: Only % SELECT policies found (expected at least 7)', v_phase1_policies;
    END IF;

    RAISE NOTICE 'Phase 1 verification passed: % tables with RLS, % SELECT policies', v_phase1_tables, v_phase1_policies;
END $$;

-- ================================================================
-- PHASE 2 POLICIES: INSERT POLICIES
-- ================================================================

-- Users table: Only admins can insert new users
DROP POLICY IF EXISTS "users_insert_admin_only" ON public.users;
CREATE POLICY "users_insert_admin_only" ON public.users
FOR INSERT TO authenticated
WITH CHECK (
    auth.role() = 'admin'
);

-- Patients table: Doctors can create patients (assigned to themselves)
DROP POLICY IF EXISTS "patients_insert_doctor" ON public.patients;
CREATE POLICY "patients_insert_doctor" ON public.patients
FOR INSERT TO authenticated
WITH CHECK (
    -- Doctors can only create patients assigned to themselves
    (auth.role() = 'doctor' AND doctor_id = auth.uid())
    -- Admins can create any patient
    OR auth.role() = 'admin'
);

-- Messages table: Users can create messages for their patients
DROP POLICY IF EXISTS "messages_insert_authorized" ON public.messages;
CREATE POLICY "messages_insert_authorized" ON public.messages
FOR INSERT TO authenticated
WITH CHECK (
    EXISTS (
        SELECT 1 FROM public.patients p
        WHERE p.id = patient_id
        AND (p.doctor_id = auth.uid() OR auth.role() = 'admin')
    )
);

-- Medical reports: Doctors can create reports for their patients
DROP POLICY IF EXISTS "medical_reports_insert_authorized" ON public.medical_reports;
CREATE POLICY "medical_reports_insert_authorized" ON public.medical_reports
FOR INSERT TO authenticated
WITH CHECK (
    -- Check if patient_id column exists
    CASE
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'medical_reports'
            AND column_name = 'patient_id'
        )
        THEN EXISTS (
            SELECT 1 FROM public.patients p
            WHERE p.id = patient_id
            AND (p.doctor_id = auth.uid() OR auth.role() = 'admin')
        )
        ELSE auth.role() IN ('admin', 'doctor')
    END
);

-- Flow states: Can create flow states for authorized patients
DROP POLICY IF EXISTS "flow_states_insert_authorized" ON public.flow_states;
CREATE POLICY "flow_states_insert_authorized" ON public.flow_states
FOR INSERT TO authenticated
WITH CHECK (
    EXISTS (
        SELECT 1 FROM public.patients p
        WHERE p.id = patient_id
        AND (p.doctor_id = auth.uid() OR auth.role() = 'admin')
    )
);

-- Quiz sessions: Can create sessions for authorized patients
DROP POLICY IF EXISTS "quiz_sessions_insert_authorized" ON public.quiz_sessions;
CREATE POLICY "quiz_sessions_insert_authorized" ON public.quiz_sessions
FOR INSERT TO authenticated
WITH CHECK (
    EXISTS (
        SELECT 1 FROM public.patients p
        WHERE p.id = patient_id
        AND (p.doctor_id = auth.uid() OR auth.role() = 'admin')
    )
);

-- Quiz responses: Can create responses for authorized sessions
DROP POLICY IF EXISTS "quiz_responses_insert_authorized" ON public.quiz_responses;
CREATE POLICY "quiz_responses_insert_authorized" ON public.quiz_responses
FOR INSERT TO authenticated
WITH CHECK (
    EXISTS (
        SELECT 1 FROM public.quiz_sessions qs
        JOIN public.patients p ON p.id = qs.patient_id
        WHERE qs.id = session_id
        AND (p.doctor_id = auth.uid() OR auth.role() = 'admin')
    )
);

-- ================================================================
-- PHASE 2 POLICIES: UPDATE POLICIES
-- ================================================================

-- Users table: Users can update their own profile, admins can update anyone
DROP POLICY IF EXISTS "users_update_own_or_admin" ON public.users;
CREATE POLICY "users_update_own_or_admin" ON public.users
FOR UPDATE TO authenticated
USING (
    id = auth.uid()
    OR auth.role() = 'admin'
)
WITH CHECK (
    -- Can't change own role unless admin
    (id = auth.uid() AND role = (SELECT role FROM public.users WHERE id = auth.uid()))
    OR auth.role() = 'admin'
);

-- Patients table: Doctors can update their patients
DROP POLICY IF EXISTS "patients_update_authorized" ON public.patients;
CREATE POLICY "patients_update_authorized" ON public.patients
FOR UPDATE TO authenticated
USING (
    doctor_id = auth.uid()
    OR auth.role() = 'admin'
)
WITH CHECK (
    -- Doctors can't reassign patients to other doctors
    (doctor_id = auth.uid() AND doctor_id = (SELECT doctor_id FROM public.patients WHERE id = patients.id))
    OR auth.role() = 'admin'
);

-- Messages table: Can update messages for authorized patients
DROP POLICY IF EXISTS "messages_update_authorized" ON public.messages;
CREATE POLICY "messages_update_authorized" ON public.messages
FOR UPDATE TO authenticated
USING (
    EXISTS (
        SELECT 1 FROM public.patients p
        WHERE p.id = patient_id
        AND (p.doctor_id = auth.uid() OR auth.role() = 'admin')
    )
)
WITH CHECK (
    -- Can't change patient_id
    patient_id = (SELECT patient_id FROM public.messages WHERE id = messages.id)
);

-- Medical reports: Can update reports for authorized patients
DROP POLICY IF EXISTS "medical_reports_update_authorized" ON public.medical_reports;
CREATE POLICY "medical_reports_update_authorized" ON public.medical_reports
FOR UPDATE TO authenticated
USING (
    auth.role() IN ('admin', 'doctor')
    -- Add patient check if patient_id exists
    AND (
        NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'medical_reports'
            AND column_name = 'patient_id'
        )
        OR EXISTS (
            SELECT 1 FROM public.patients p
            WHERE p.id = patient_id
            AND (p.doctor_id = auth.uid() OR auth.role() = 'admin')
        )
    )
)
WITH CHECK (
    auth.role() IN ('admin', 'doctor')
);

-- Flow states: Can update flow states for authorized patients
DROP POLICY IF EXISTS "flow_states_update_authorized" ON public.flow_states;
CREATE POLICY "flow_states_update_authorized" ON public.flow_states
FOR UPDATE TO authenticated
USING (
    EXISTS (
        SELECT 1 FROM public.patients p
        WHERE p.id = patient_id
        AND (p.doctor_id = auth.uid() OR auth.role() = 'admin')
    )
)
WITH CHECK (
    -- Can't change patient_id
    patient_id = (SELECT patient_id FROM public.flow_states WHERE id = flow_states.id)
);

-- Quiz sessions: Can update sessions for authorized patients
DROP POLICY IF EXISTS "quiz_sessions_update_authorized" ON public.quiz_sessions;
CREATE POLICY "quiz_sessions_update_authorized" ON public.quiz_sessions
FOR UPDATE TO authenticated
USING (
    EXISTS (
        SELECT 1 FROM public.patients p
        WHERE p.id = patient_id
        AND (p.doctor_id = auth.uid() OR auth.role() = 'admin')
    )
)
WITH CHECK (
    -- Can't change patient_id
    patient_id = (SELECT patient_id FROM public.quiz_sessions WHERE id = quiz_sessions.id)
);

-- Quiz responses: Can update responses for authorized sessions
DROP POLICY IF EXISTS "quiz_responses_update_authorized" ON public.quiz_responses;
CREATE POLICY "quiz_responses_update_authorized" ON public.quiz_responses
FOR UPDATE TO authenticated
USING (
    EXISTS (
        SELECT 1 FROM public.quiz_sessions qs
        JOIN public.patients p ON p.id = qs.patient_id
        WHERE qs.id = session_id
        AND (p.doctor_id = auth.uid() OR auth.role() = 'admin')
    )
)
WITH CHECK (
    -- Can't change session_id
    session_id = (SELECT session_id FROM public.quiz_responses WHERE id = quiz_responses.id)
);

-- ================================================================
-- PHASE 2 POLICIES: DELETE POLICIES
-- ================================================================

-- Users table: Only admins can delete users
DROP POLICY IF EXISTS "users_delete_admin_only" ON public.users;
CREATE POLICY "users_delete_admin_only" ON public.users
FOR DELETE TO authenticated
USING (
    auth.role() = 'admin'
);

-- Patients table: Only admins can delete patients (soft delete preferred)
DROP POLICY IF EXISTS "patients_delete_admin_only" ON public.patients;
CREATE POLICY "patients_delete_admin_only" ON public.patients
FOR DELETE TO authenticated
USING (
    auth.role() = 'admin'
);

-- Messages table: Admins and message owners can delete
DROP POLICY IF EXISTS "messages_delete_authorized" ON public.messages;
CREATE POLICY "messages_delete_authorized" ON public.messages
FOR DELETE TO authenticated
USING (
    auth.role() = 'admin'
    OR EXISTS (
        SELECT 1 FROM public.patients p
        WHERE p.id = patient_id
        AND p.doctor_id = auth.uid()
    )
);

-- Medical reports: Only admins can delete reports
DROP POLICY IF EXISTS "medical_reports_delete_admin_only" ON public.medical_reports;
CREATE POLICY "medical_reports_delete_admin_only" ON public.medical_reports
FOR DELETE TO authenticated
USING (
    auth.role() = 'admin'
);

-- Flow states: Admins and flow owners can delete
DROP POLICY IF EXISTS "flow_states_delete_authorized" ON public.flow_states;
CREATE POLICY "flow_states_delete_authorized" ON public.flow_states
FOR DELETE TO authenticated
USING (
    auth.role() = 'admin'
    OR EXISTS (
        SELECT 1 FROM public.patients p
        WHERE p.id = patient_id
        AND p.doctor_id = auth.uid()
    )
);

-- Quiz sessions: Only admins can delete sessions
DROP POLICY IF EXISTS "quiz_sessions_delete_admin_only" ON public.quiz_sessions;
CREATE POLICY "quiz_sessions_delete_admin_only" ON public.quiz_sessions
FOR DELETE TO authenticated
USING (
    auth.role() = 'admin'
);

-- Quiz responses: Only admins can delete responses
DROP POLICY IF EXISTS "quiz_responses_delete_admin_only" ON public.quiz_responses;
CREATE POLICY "quiz_responses_delete_admin_only" ON public.quiz_responses
FOR DELETE TO authenticated
USING (
    auth.role() = 'admin'
);

-- ================================================================
-- AUDIT POLICIES FOR PHASE 2
-- ================================================================

-- Create audit log table if not exists
CREATE TABLE IF NOT EXISTS public.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    event_type VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100),
    entity_id UUID,
    old_values JSONB,
    new_values JSONB,
    metadata JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS on audit logs
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

-- Audit log policies
DROP POLICY IF EXISTS "audit_logs_insert_all" ON public.audit_logs;
CREATE POLICY "audit_logs_insert_all" ON public.audit_logs
FOR INSERT TO authenticated
WITH CHECK (true);  -- Everyone can write audit logs

DROP POLICY IF EXISTS "audit_logs_select_authorized" ON public.audit_logs;
CREATE POLICY "audit_logs_select_authorized" ON public.audit_logs
FOR SELECT TO authenticated
USING (
    -- Users can see their own audit logs
    user_id = auth.uid()
    -- Admins can see all audit logs
    OR auth.role() = 'admin'
    -- Doctors can see audit logs for their patients
    OR (
        entity_type = 'patient'
        AND EXISTS (
            SELECT 1 FROM public.patients p
            WHERE p.id = entity_id
            AND p.doctor_id = auth.uid()
        )
    )
);

-- ================================================================
-- PERFORMANCE OPTIMIZATION FOR PHASE 2
-- ================================================================

-- Create additional indexes for write operations
CREATE INDEX IF NOT EXISTS idx_users_role ON public.users(role);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON public.messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_flow_states_current_state ON public.flow_states(current_state);
CREATE INDEX IF NOT EXISTS idx_quiz_sessions_status ON public.quiz_sessions(status);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON public.audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON public.audit_logs(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON public.audit_logs(created_at DESC);

-- ================================================================
-- MONITORING VIEW FOR PHASE 2
-- ================================================================

CREATE OR REPLACE VIEW public.rls_phase2_status AS
SELECT
    'Phase 2' as phase,
    NOW() as check_time,
    (SELECT COUNT(*) FROM pg_policies WHERE schemaname = 'public' AND cmd = 'INSERT') as insert_policies,
    (SELECT COUNT(*) FROM pg_policies WHERE schemaname = 'public' AND cmd = 'UPDATE') as update_policies,
    (SELECT COUNT(*) FROM pg_policies WHERE schemaname = 'public' AND cmd = 'DELETE') as delete_policies,
    (SELECT COUNT(*) FROM pg_policies WHERE schemaname = 'public' AND cmd = 'SELECT') as select_policies,
    (SELECT COUNT(*) FROM pg_policies WHERE schemaname = 'public') as total_policies,
    (SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public' AND rowsecurity = true) as rls_enabled_tables,
    CASE
        WHEN (SELECT COUNT(*) FROM pg_policies WHERE schemaname = 'public' AND cmd IN ('INSERT', 'UPDATE', 'DELETE')) < 15 THEN 'INCOMPLETE'
        ELSE 'COMPLETE'
    END as phase_status;

-- Grant access to monitoring view
GRANT SELECT ON public.rls_phase2_status TO authenticated;

-- ================================================================
-- VERIFICATION
-- ================================================================

-- Display Phase 2 status
SELECT * FROM public.rls_phase2_status;

-- List all policies by operation
SELECT
    tablename,
    policyname,
    cmd as operation,
    roles,
    CASE cmd
        WHEN 'SELECT' THEN 'Read'
        WHEN 'INSERT' THEN 'Create'
        WHEN 'UPDATE' THEN 'Modify'
        WHEN 'DELETE' THEN 'Remove'
        ELSE cmd
    END as operation_type
FROM pg_policies
WHERE schemaname = 'public'
ORDER BY tablename, cmd;

-- ================================================================
-- ROLLBACK PREPARATION (commented out, use only if needed)
-- ================================================================

/*
-- To rollback Phase 2 only (keeping Phase 1), run this:
BEGIN;

-- Drop all INSERT policies
DROP POLICY IF EXISTS "users_insert_admin_only" ON public.users;
DROP POLICY IF EXISTS "patients_insert_doctor" ON public.patients;
DROP POLICY IF EXISTS "messages_insert_authorized" ON public.messages;
DROP POLICY IF EXISTS "medical_reports_insert_authorized" ON public.medical_reports;
DROP POLICY IF EXISTS "flow_states_insert_authorized" ON public.flow_states;
DROP POLICY IF EXISTS "quiz_sessions_insert_authorized" ON public.quiz_sessions;
DROP POLICY IF EXISTS "quiz_responses_insert_authorized" ON public.quiz_responses;

-- Drop all UPDATE policies
DROP POLICY IF EXISTS "users_update_own_or_admin" ON public.users;
DROP POLICY IF EXISTS "patients_update_authorized" ON public.patients;
DROP POLICY IF EXISTS "messages_update_authorized" ON public.messages;
DROP POLICY IF EXISTS "medical_reports_update_authorized" ON public.medical_reports;
DROP POLICY IF EXISTS "flow_states_update_authorized" ON public.flow_states;
DROP POLICY IF EXISTS "quiz_sessions_update_authorized" ON public.quiz_sessions;
DROP POLICY IF EXISTS "quiz_responses_update_authorized" ON public.quiz_responses;

-- Drop all DELETE policies
DROP POLICY IF EXISTS "users_delete_admin_only" ON public.users;
DROP POLICY IF EXISTS "patients_delete_admin_only" ON public.patients;
DROP POLICY IF EXISTS "messages_delete_authorized" ON public.messages;
DROP POLICY IF EXISTS "medical_reports_delete_admin_only" ON public.medical_reports;
DROP POLICY IF EXISTS "flow_states_delete_authorized" ON public.flow_states;
DROP POLICY IF EXISTS "quiz_sessions_delete_admin_only" ON public.quiz_sessions;
DROP POLICY IF EXISTS "quiz_responses_delete_admin_only" ON public.quiz_responses;

-- Drop audit log policies
DROP POLICY IF EXISTS "audit_logs_insert_all" ON public.audit_logs;
DROP POLICY IF EXISTS "audit_logs_select_authorized" ON public.audit_logs;

-- Keep Phase 1 SELECT policies intact

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

1. Test write operations with different user roles:
   - Admin creating/updating/deleting users
   - Doctor creating/updating patients
   - Doctor creating messages for their patients
   - Admin performing any operation

2. Verify audit logging:
   - Check that all write operations create audit log entries
   - Verify doctors can only see relevant audit logs
   - Confirm admins can see all audit logs

3. Performance monitoring:
   - Check query times for INSERT/UPDATE/DELETE operations
   - Monitor for any deadlocks or lock contention
   - Verify indexes are being used

4. Security testing:
   - Attempt unauthorized operations (should fail)
   - Try to bypass policies with crafted queries
   - Verify data isolation between doctors

5. Before proceeding to Phase 3:
   - All write operations working correctly
   - Performance degradation < 20%
   - No security violations detected
   - Audit trail complete and accurate

Phase 3 will add:
- More complex policies (time-based, conditional)
- Cross-table policy coordination
- Performance optimizations
- Advanced audit features
*/

-- ================================================================
-- END OF PHASE 2 MIGRATION
-- ================================================================