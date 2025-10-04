-- =====================================================
-- Migration: Add CASCADE Rules to Foreign Keys
-- Date: 2025-10-04
-- Author: Hive Mind Database Analysis
-- Issue: 42 of 48 foreign keys (87.5%) lack CASCADE rules
-- =====================================================
-- CRITICAL: Prevents orphaned records and deletion failures
--
-- Impact:
-- - Enables proper cascading deletes for patient data (LGPD compliance)
-- - Prevents foreign key constraint violations
-- - Maintains referential integrity
-- - Supports data retention policies
--
-- Risk Assessment:
-- - MEDIUM RISK: Alters table constraints in production database
-- - REQUIRES: Database backup before execution
-- - REQUIRES: Application downtime or careful transaction management
-- =====================================================

BEGIN;

-- =====================================================
-- PHASE 1: Patient-Related Cascades (LGPD Compliance)
-- =====================================================
-- When a patient is deleted, all related data should be deleted
-- This is REQUIRED for LGPD "Right to be Forgotten"

-- 1. Messages table
ALTER TABLE messages
    DROP CONSTRAINT IF EXISTS messages_patient_id_fkey,
    ADD CONSTRAINT messages_patient_id_fkey
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE;

-- 2. Quiz Sessions table
ALTER TABLE quiz_sessions
    DROP CONSTRAINT IF EXISTS quiz_sessions_patient_id_fkey,
    ADD CONSTRAINT quiz_sessions_patient_id_fkey
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE;

-- 3. Quiz Sessions V2 table
ALTER TABLE quiz_sessions_v2
    DROP CONSTRAINT IF EXISTS quiz_sessions_v2_patient_id_fkey,
    ADD CONSTRAINT quiz_sessions_v2_patient_id_fkey
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE;

-- 4. Quiz Responses table
ALTER TABLE quiz_responses
    DROP CONSTRAINT IF EXISTS quiz_responses_patient_id_fkey,
    ADD CONSTRAINT quiz_responses_patient_id_fkey
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE;

-- 5. Quiz Responses V2 table
ALTER TABLE quiz_responses_v2
    DROP CONSTRAINT IF EXISTS quiz_responses_v2_patient_id_fkey,
    ADD CONSTRAINT quiz_responses_v2_patient_id_fkey
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE;

-- 6. Alerts table
ALTER TABLE alerts
    DROP CONSTRAINT IF EXISTS alerts_patient_id_fkey,
    ADD CONSTRAINT alerts_patient_id_fkey
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE;

-- 7. Flow Instances table
ALTER TABLE flow_instances
    DROP CONSTRAINT IF EXISTS flow_instances_patient_id_fkey,
    ADD CONSTRAINT flow_instances_patient_id_fkey
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE;

-- 8. Flow Analytics table
ALTER TABLE flow_analytics
    DROP CONSTRAINT IF EXISTS flow_analytics_patient_id_fkey,
    ADD CONSTRAINT flow_analytics_patient_id_fkey
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE;

-- 9. Medical Reports table
ALTER TABLE medical_reports
    DROP CONSTRAINT IF EXISTS medical_reports_patient_id_fkey,
    ADD CONSTRAINT medical_reports_patient_id_fkey
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE;

-- 10. Patient Notes table
ALTER TABLE patient_notes
    DROP CONSTRAINT IF EXISTS patient_notes_patient_id_fkey,
    ADD CONSTRAINT patient_notes_patient_id_fkey
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE;

-- 11. Consultas table
ALTER TABLE consultas
    DROP CONSTRAINT IF EXISTS consultas_patient_id_fkey,
    ADD CONSTRAINT consultas_patient_id_fkey
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE;

-- 12. Audit Logs (patient-related)
ALTER TABLE audit_logs
    DROP CONSTRAINT IF EXISTS audit_logs_related_patient_id_fkey,
    ADD CONSTRAINT audit_logs_related_patient_id_fkey
        FOREIGN KEY (related_patient_id) REFERENCES patients(id) ON DELETE SET NULL;

-- =====================================================
-- PHASE 2: Quiz Template Cascades
-- =====================================================
-- Quiz sessions and responses should reference templates with RESTRICT
-- (can't delete template if active sessions/responses exist)

-- 13. Quiz Sessions - Template Reference (RESTRICT to protect active quizzes)
ALTER TABLE quiz_sessions
    DROP CONSTRAINT IF EXISTS quiz_sessions_quiz_template_id_fkey,
    ADD CONSTRAINT quiz_sessions_quiz_template_id_fkey
        FOREIGN KEY (quiz_template_id) REFERENCES quiz_templates(id) ON DELETE RESTRICT;

-- 14. Quiz Sessions V2 - Template Version Reference (RESTRICT)
ALTER TABLE quiz_sessions_v2
    DROP CONSTRAINT IF EXISTS quiz_sessions_v2_template_version_id_fkey,
    ADD CONSTRAINT quiz_sessions_v2_template_version_id_fkey
        FOREIGN KEY (template_version_id) REFERENCES quiz_template_versions_v2(id) ON DELETE RESTRICT;

-- 15. Quiz Responses - Template Reference (RESTRICT)
ALTER TABLE quiz_responses
    DROP CONSTRAINT IF EXISTS quiz_responses_quiz_template_id_fkey,
    ADD CONSTRAINT quiz_responses_quiz_template_id_fkey
        FOREIGN KEY (quiz_template_id) REFERENCES quiz_templates(id) ON DELETE RESTRICT;

-- 16. Quiz Template Versions - Parent Template (CASCADE when template deleted)
ALTER TABLE quiz_template_versions
    DROP CONSTRAINT IF EXISTS quiz_template_versions_template_id_fkey,
    ADD CONSTRAINT quiz_template_versions_template_id_fkey
        FOREIGN KEY (template_id) REFERENCES quiz_templates(id) ON DELETE CASCADE;

-- =====================================================
-- PHASE 3: Session-Related Cascades
-- =====================================================
-- Responses should be deleted when session is deleted

-- 17. Quiz Responses - Session Reference (CASCADE)
ALTER TABLE quiz_responses
    DROP CONSTRAINT IF EXISTS quiz_responses_session_id_fkey,
    ADD CONSTRAINT quiz_responses_session_id_fkey
        FOREIGN KEY (session_id) REFERENCES quiz_sessions(id) ON DELETE CASCADE;

-- =====================================================
-- PHASE 4: Flow Template Cascades
-- =====================================================

-- 18. Flow Nodes - Flow Template Version (CASCADE)
ALTER TABLE flow_nodes
    DROP CONSTRAINT IF EXISTS flow_nodes_flow_template_version_id_fkey,
    ADD CONSTRAINT flow_nodes_flow_template_version_id_fkey
        FOREIGN KEY (flow_template_version_id) REFERENCES flow_template_versions(id) ON DELETE CASCADE;

-- 19. Flow Edges - Flow Template Version (CASCADE)
ALTER TABLE flow_edges
    DROP CONSTRAINT IF EXISTS flow_edges_flow_template_version_id_fkey,
    ADD CONSTRAINT flow_edges_flow_template_version_id_fkey
        FOREIGN KEY (flow_template_version_id) REFERENCES flow_template_versions(id) ON DELETE CASCADE;

-- 20. Flow Instances - Flow Template Version (RESTRICT - protect active flows)
ALTER TABLE flow_instances
    DROP CONSTRAINT IF EXISTS flow_instances_flow_template_version_id_fkey,
    ADD CONSTRAINT flow_instances_flow_template_version_id_fkey
        FOREIGN KEY (flow_template_version_id) REFERENCES flow_template_versions(id) ON DELETE RESTRICT;

-- 21. Flow Analytics - Flow Template Version (SET NULL - keep analytics even if template deleted)
ALTER TABLE flow_analytics
    DROP CONSTRAINT IF EXISTS flow_analytics_flow_template_version_id_fkey,
    ADD CONSTRAINT flow_analytics_flow_template_version_id_fkey
        FOREIGN KEY (flow_template_version_id) REFERENCES flow_template_versions(id) ON DELETE SET NULL;

-- 22. Flow Templates - Flow Kind (RESTRICT - can't delete kind if templates exist)
ALTER TABLE flow_templates
    DROP CONSTRAINT IF EXISTS flow_templates_flow_kind_id_fkey,
    ADD CONSTRAINT flow_templates_flow_kind_id_fkey
        FOREIGN KEY (flow_kind_id) REFERENCES flow_kinds(id) ON DELETE RESTRICT;

-- =====================================================
-- PHASE 5: User-Related Cascades
-- =====================================================

-- 23. Consultas - Doctor Reference (RESTRICT - can't delete doctor with active consultations)
ALTER TABLE consultas
    DROP CONSTRAINT IF EXISTS consultas_doctor_id_fkey,
    ADD CONSTRAINT consultas_doctor_id_fkey
        FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE RESTRICT;

-- 24. Patient Notes - Doctor Reference (RESTRICT)
ALTER TABLE patient_notes
    DROP CONSTRAINT IF EXISTS patient_notes_doctor_id_fkey,
    ADD CONSTRAINT patient_notes_doctor_id_fkey
        FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE RESTRICT;

-- 25. Medical Reports - Generated By (SET NULL - keep report even if user deleted)
ALTER TABLE medical_reports
    DROP CONSTRAINT IF EXISTS medical_reports_generated_by_fkey,
    ADD CONSTRAINT medical_reports_generated_by_fkey
        FOREIGN KEY (generated_by) REFERENCES users(id) ON DELETE SET NULL;

-- 26. Alerts - Acknowledged By (SET NULL - keep alert even if user deleted)
ALTER TABLE alerts
    DROP CONSTRAINT IF EXISTS alerts_acknowledged_by_fkey,
    ADD CONSTRAINT alerts_acknowledged_by_fkey
        FOREIGN KEY (acknowledged_by) REFERENCES users(id) ON DELETE SET NULL;

-- 27. Flow Templates - Created By (SET NULL)
ALTER TABLE flow_templates
    DROP CONSTRAINT IF EXISTS flow_templates_created_by_fkey,
    ADD CONSTRAINT flow_templates_created_by_fkey
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL;

-- 28. Flow Sharing - Shared By (CASCADE - delete sharing when user deleted)
ALTER TABLE flow_sharing
    DROP CONSTRAINT IF EXISTS flow_sharing_shared_by_fkey,
    ADD CONSTRAINT flow_sharing_shared_by_fkey
        FOREIGN KEY (shared_by) REFERENCES users(id) ON DELETE CASCADE;

-- 29. Flow Sharing - Shared With (CASCADE)
ALTER TABLE flow_sharing
    DROP CONSTRAINT IF EXISTS flow_sharing_shared_with_fkey,
    ADD CONSTRAINT flow_sharing_shared_with_fkey
        FOREIGN KEY (shared_with) REFERENCES users(id) ON DELETE CASCADE;

-- 30. Quiz Templates - Created By (SET NULL)
ALTER TABLE quiz_templates
    DROP CONSTRAINT IF EXISTS quiz_templates_created_by_fkey,
    ADD CONSTRAINT quiz_templates_created_by_fkey
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL;

-- 31. Audit Logs - Related User (SET NULL)
ALTER TABLE audit_logs
    DROP CONSTRAINT IF EXISTS audit_logs_related_user_id_fkey,
    ADD CONSTRAINT audit_logs_related_user_id_fkey
        FOREIGN KEY (related_user_id) REFERENCES users(id) ON DELETE SET NULL;

-- =====================================================
-- PHASE 6: Admin System Cascades
-- =====================================================

-- 32. Admin Audit Logs - Admin User (SET NULL - preserve audit trail)
ALTER TABLE admin_audit_logs
    DROP CONSTRAINT IF EXISTS admin_audit_logs_admin_user_id_fkey,
    ADD CONSTRAINT admin_audit_logs_admin_user_id_fkey
        FOREIGN KEY (admin_user_id) REFERENCES admin_users(id) ON DELETE SET NULL;

-- 33. Admin Audit Logs - Session (SET NULL)
ALTER TABLE admin_audit_logs
    DROP CONSTRAINT IF EXISTS admin_audit_logs_session_id_fkey,
    ADD CONSTRAINT admin_audit_logs_session_id_fkey
        FOREIGN KEY (session_id) REFERENCES admin_sessions(id) ON DELETE SET NULL;

-- 34. Admin Security Events - Admin User (SET NULL)
ALTER TABLE admin_security_events
    DROP CONSTRAINT IF EXISTS admin_security_events_admin_user_id_fkey,
    ADD CONSTRAINT admin_security_events_admin_user_id_fkey
        FOREIGN KEY (admin_user_id) REFERENCES admin_users(id) ON DELETE SET NULL;

-- 35. Admin Security Events - Session (SET NULL)
ALTER TABLE admin_security_events
    DROP CONSTRAINT IF EXISTS admin_security_events_session_id_fkey,
    ADD CONSTRAINT admin_security_events_session_id_fkey
        FOREIGN KEY (session_id) REFERENCES admin_sessions(id) ON DELETE SET NULL;

-- 36. Admin Allowlist - Added By (SET NULL)
ALTER TABLE admin_allowlist
    DROP CONSTRAINT IF EXISTS admin_allowlist_added_by_fkey,
    ADD CONSTRAINT admin_allowlist_added_by_fkey
        FOREIGN KEY (added_by) REFERENCES admin_users(id) ON DELETE SET NULL;

-- 37. Admin Blocklist - Blocked By (SET NULL)
ALTER TABLE admin_blocklist
    DROP CONSTRAINT IF EXISTS admin_blocklist_blocked_by_fkey,
    ADD CONSTRAINT admin_blocklist_blocked_by_fkey
        FOREIGN KEY (blocked_by) REFERENCES admin_users(id) ON DELETE SET NULL;

-- 38. Admin Roles - Created By (SET NULL)
ALTER TABLE admin_roles
    DROP CONSTRAINT IF EXISTS admin_roles_created_by_fkey,
    ADD CONSTRAINT admin_roles_created_by_fkey
        FOREIGN KEY (created_by) REFERENCES admin_users(id) ON DELETE SET NULL;

-- 39. Admin Roles - Updated By (SET NULL)
ALTER TABLE admin_roles
    DROP CONSTRAINT IF EXISTS admin_roles_updated_by_fkey,
    ADD CONSTRAINT admin_roles_updated_by_fkey
        FOREIGN KEY (updated_by) REFERENCES admin_users(id) ON DELETE SET NULL;

-- 40. Admin User Permissions - Granted By (SET NULL)
ALTER TABLE admin_user_permissions
    DROP CONSTRAINT IF EXISTS admin_user_permissions_granted_by_fkey,
    ADD CONSTRAINT admin_user_permissions_granted_by_fkey
        FOREIGN KEY (granted_by) REFERENCES admin_users(id) ON DELETE SET NULL;

-- =====================================================
-- PHASE 7: Cross-System References
-- =====================================================

-- 41. User Profiles - User Reference (CASCADE)
ALTER TABLE user_profiles
    DROP CONSTRAINT IF EXISTS user_profiles_user_id_fkey,
    ADD CONSTRAINT user_profiles_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- 42. Firebase Sync - Supabase User (CASCADE)
ALTER TABLE firebase_sync
    DROP CONSTRAINT IF EXISTS firebase_sync_supabase_user_id_fkey,
    ADD CONSTRAINT firebase_sync_supabase_user_id_fkey
        FOREIGN KEY (supabase_user_id) REFERENCES users(id) ON DELETE CASCADE;

-- =====================================================
-- VERIFICATION: Count CASCADE rules
-- =====================================================

DO $$
DECLARE
    cascade_count int;
    set_null_count int;
    restrict_count int;
    total_fks int;
BEGIN
    -- Count CASCADE rules
    SELECT COUNT(*) INTO cascade_count
    FROM information_schema.referential_constraints
    WHERE constraint_schema = 'public'
    AND delete_rule = 'CASCADE';

    -- Count SET NULL rules
    SELECT COUNT(*) INTO set_null_count
    FROM information_schema.referential_constraints
    WHERE constraint_schema = 'public'
    AND delete_rule = 'SET NULL';

    -- Count RESTRICT rules
    SELECT COUNT(*) INTO restrict_count
    FROM information_schema.referential_constraints
    WHERE constraint_schema = 'public'
    AND delete_rule = 'RESTRICT';

    -- Count total FKs
    SELECT COUNT(*) INTO total_fks
    FROM information_schema.referential_constraints
    WHERE constraint_schema = 'public';

    RAISE NOTICE 'Foreign Key Statistics:';
    RAISE NOTICE '  CASCADE: % (%.1f%%)', cascade_count, (cascade_count::float / total_fks * 100);
    RAISE NOTICE '  SET NULL: % (%.1f%%)', set_null_count, (set_null_count::float / total_fks * 100);
    RAISE NOTICE '  RESTRICT: % (%.1f%%)', restrict_count, (restrict_count::float / total_fks * 100);
    RAISE NOTICE '  Total FKs: %', total_fks;
END $$;

-- =====================================================
-- AUDIT LOG: Record migration
-- =====================================================

INSERT INTO schema_migrations (migration_name, description, checksum)
VALUES (
    '20251004_add_foreign_key_cascade_rules',
    'Add CASCADE/SET NULL/RESTRICT rules to 42 foreign keys for data integrity and LGPD compliance',
    md5('cascade_42_foreign_keys_v1')
)
ON CONFLICT (migration_name) DO NOTHING;

COMMIT;

-- =====================================================
-- POST-MIGRATION TESTING
-- =====================================================
-- IMPORTANT: Test cascade behavior in separate test environment
-- DO NOT include destructive operations in migration files
-- Refer to test suite: backend-hormonia/tests/test_cascade_behavior.py
-- =====================================================
