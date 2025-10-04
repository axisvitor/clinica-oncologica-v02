-- =====================================================
-- Migration: Add RLS Policies to Admin Tables
-- Date: 2025-10-04
-- Author: Hive Mind Database Analysis
-- Issue: 10 admin tables lack Row Level Security policies
-- =====================================================
-- CRITICAL SECURITY FIX: OWASP A01, CWE-284
--
-- Vulnerability: Horizontal privilege escalation
-- - Admin users can access other admins' sessions
-- - Non-superadmins can view audit logs
-- - Admins can modify permissions without authorization
--
-- Impact:
-- - Prevents unauthorized access to admin data
-- - Enforces role-based access control at database level
-- - Complies with security best practices
-- - Passes security audits
--
-- Risk Assessment:
-- - HIGH RISK: Security vulnerability in production
-- - REQUIRES: Immediate deployment
-- - REQUIRES: Application restart to clear cached connections
-- =====================================================

BEGIN;

-- =====================================================
-- PREREQUISITES: Helper Functions
-- =====================================================
-- These functions extract admin claims from JWT tokens

-- Get current admin user ID from JWT
CREATE OR REPLACE FUNCTION auth.admin_uid()
RETURNS uuid AS $$
    SELECT CASE
        WHEN current_setting('request.jwt.claims', true) IS NOT NULL
        THEN (current_setting('request.jwt.claims', true)::json->>'admin_uid')::uuid
        ELSE NULL
    END;
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Check if current admin is superadmin
CREATE OR REPLACE FUNCTION auth.is_superadmin()
RETURNS boolean AS $$
    SELECT CASE
        WHEN current_setting('request.jwt.claims', true) IS NOT NULL
        THEN (current_setting('request.jwt.claims', true)::json->>'is_superadmin')::boolean
        ELSE false
    END;
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Get current admin role
CREATE OR REPLACE FUNCTION auth.admin_role()
RETURNS text AS $$
    SELECT CASE
        WHEN current_setting('request.jwt.claims', true) IS NOT NULL
        THEN current_setting('request.jwt.claims', true)::json->>'admin_role'
        ELSE NULL
    END;
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- =====================================================
-- PHASE 1: Admin Users Table
-- =====================================================
-- Admins can see their own profile, superadmins can see all

ALTER TABLE admin_users ENABLE ROW LEVEL SECURITY;

-- Superadmins can SELECT all admin users
CREATE POLICY "admin_users_superadmin_select" ON admin_users
FOR SELECT TO authenticated
USING (auth.is_superadmin() = true);

-- Regular admins can SELECT only themselves
CREATE POLICY "admin_users_self_select" ON admin_users
FOR SELECT TO authenticated
USING (id = auth.admin_uid());

-- Superadmins can INSERT new admin users
CREATE POLICY "admin_users_superadmin_insert" ON admin_users
FOR INSERT TO authenticated
WITH CHECK (auth.is_superadmin() = true);

-- Superadmins can UPDATE any admin user
CREATE POLICY "admin_users_superadmin_update" ON admin_users
FOR UPDATE TO authenticated
USING (auth.is_superadmin() = true);

-- Regular admins can UPDATE only themselves (profile, password)
CREATE POLICY "admin_users_self_update" ON admin_users
FOR UPDATE TO authenticated
USING (id = auth.admin_uid());

-- Only superadmins can DELETE admin users
CREATE POLICY "admin_users_superadmin_delete" ON admin_users
FOR DELETE TO authenticated
USING (auth.is_superadmin() = true);

-- =====================================================
-- PHASE 2: Admin Sessions Table
-- =====================================================
-- Admins can only see their own sessions

ALTER TABLE admin_sessions ENABLE ROW LEVEL SECURITY;

-- Admins can SELECT only their own sessions
CREATE POLICY "admin_sessions_self_select" ON admin_sessions
FOR SELECT TO authenticated
USING (admin_user_id = auth.admin_uid());

-- Superadmins can SELECT all sessions (for monitoring)
CREATE POLICY "admin_sessions_superadmin_select" ON admin_sessions
FOR SELECT TO authenticated
USING (auth.is_superadmin() = true);

-- Admins can INSERT their own sessions
CREATE POLICY "admin_sessions_self_insert" ON admin_sessions
FOR INSERT TO authenticated
WITH CHECK (admin_user_id = auth.admin_uid());

-- Admins can UPDATE their own sessions
CREATE POLICY "admin_sessions_self_update" ON admin_sessions
FOR UPDATE TO authenticated
USING (admin_user_id = auth.admin_uid());

-- Admins can DELETE their own sessions (logout)
CREATE POLICY "admin_sessions_self_delete" ON admin_sessions
FOR DELETE TO authenticated
USING (admin_user_id = auth.admin_uid());

-- Superadmins can DELETE any session (force logout)
CREATE POLICY "admin_sessions_superadmin_delete" ON admin_sessions
FOR DELETE TO authenticated
USING (auth.is_superadmin() = true);

-- =====================================================
-- PHASE 3: Admin Roles Table
-- =====================================================
-- Only superadmins can manage roles

ALTER TABLE admin_roles ENABLE ROW LEVEL SECURITY;

-- All admins can SELECT roles (to see available roles)
CREATE POLICY "admin_roles_all_select" ON admin_roles
FOR SELECT TO authenticated
USING (true);

-- Only superadmins can INSERT/UPDATE/DELETE roles
CREATE POLICY "admin_roles_superadmin_write" ON admin_roles
FOR ALL TO authenticated
USING (auth.is_superadmin() = true)
WITH CHECK (auth.is_superadmin() = true);

-- =====================================================
-- PHASE 4: Admin Permissions Table
-- =====================================================
-- Only superadmins can manage permissions

ALTER TABLE admin_permissions ENABLE ROW LEVEL SECURITY;

-- All admins can SELECT permissions (to see what permissions exist)
CREATE POLICY "admin_permissions_all_select" ON admin_permissions
FOR SELECT TO authenticated
USING (true);

-- Only superadmins can INSERT/UPDATE/DELETE permissions
CREATE POLICY "admin_permissions_superadmin_write" ON admin_permissions
FOR ALL TO authenticated
USING (auth.is_superadmin() = true)
WITH CHECK (auth.is_superadmin() = true);

-- =====================================================
-- PHASE 5: Admin User Permissions Table
-- =====================================================
-- Admins can see their own permissions, superadmins can see all

ALTER TABLE admin_user_permissions ENABLE ROW LEVEL SECURITY;

-- Admins can SELECT their own permissions
CREATE POLICY "admin_user_permissions_self_select" ON admin_user_permissions
FOR SELECT TO authenticated
USING (admin_user_id = auth.admin_uid());

-- Superadmins can SELECT all permissions
CREATE POLICY "admin_user_permissions_superadmin_select" ON admin_user_permissions
FOR SELECT TO authenticated
USING (auth.is_superadmin() = true);

-- Only superadmins can INSERT/UPDATE/DELETE user permissions
CREATE POLICY "admin_user_permissions_superadmin_write" ON admin_user_permissions
FOR ALL TO authenticated
USING (auth.is_superadmin() = true)
WITH CHECK (auth.is_superadmin() = true);

-- =====================================================
-- PHASE 6: Admin Role Permissions Table
-- =====================================================
-- Only superadmins can manage role permissions

ALTER TABLE admin_role_permissions ENABLE ROW LEVEL SECURITY;

-- All admins can SELECT role permissions (to understand role capabilities)
CREATE POLICY "admin_role_permissions_all_select" ON admin_role_permissions
FOR SELECT TO authenticated
USING (true);

-- Only superadmins can INSERT/UPDATE/DELETE role permissions
CREATE POLICY "admin_role_permissions_superadmin_write" ON admin_role_permissions
FOR ALL TO authenticated
USING (auth.is_superadmin() = true)
WITH CHECK (auth.is_superadmin() = true);

-- =====================================================
-- PHASE 7: Admin Audit Log Table
-- =====================================================
-- Only superadmins can access audit logs

ALTER TABLE admin_audit_log ENABLE ROW LEVEL SECURITY;

-- Only superadmins can SELECT audit logs
CREATE POLICY "admin_audit_log_superadmin_select" ON admin_audit_log
FOR SELECT TO authenticated
USING (auth.is_superadmin() = true);

-- System can INSERT audit logs (service role)
-- Note: INSERT policy allows backend to write logs without JWT
CREATE POLICY "admin_audit_log_system_insert" ON admin_audit_log
FOR INSERT TO authenticated
WITH CHECK (true);

-- No UPDATE or DELETE allowed (audit logs are immutable)

-- =====================================================
-- PHASE 8: Admin Security Events Table
-- =====================================================
-- Only superadmins can access security events

ALTER TABLE admin_security_events ENABLE ROW LEVEL SECURITY;

-- Only superadmins can SELECT security events
CREATE POLICY "admin_security_events_superadmin_select" ON admin_security_events
FOR SELECT TO authenticated
USING (auth.is_superadmin() = true);

-- System can INSERT security events (service role)
CREATE POLICY "admin_security_events_system_insert" ON admin_security_events
FOR INSERT TO authenticated
WITH CHECK (true);

-- No UPDATE or DELETE allowed (security events are immutable)

-- =====================================================
-- PHASE 9: Admin IP Whitelist Table
-- =====================================================
-- Only superadmins can manage IP whitelist

ALTER TABLE admin_ip_whitelist ENABLE ROW LEVEL SECURITY;

-- Superadmins can SELECT all whitelist entries
CREATE POLICY "admin_ip_whitelist_superadmin_select" ON admin_ip_whitelist
FOR SELECT TO authenticated
USING (auth.is_superadmin() = true);

-- Only superadmins can INSERT/UPDATE/DELETE whitelist entries
CREATE POLICY "admin_ip_whitelist_superadmin_write" ON admin_ip_whitelist
FOR ALL TO authenticated
USING (auth.is_superadmin() = true)
WITH CHECK (auth.is_superadmin() = true);

-- =====================================================
-- PHASE 10: Admin IP Blacklist Table
-- =====================================================
-- Only superadmins can manage IP blacklist

ALTER TABLE admin_ip_blacklist ENABLE ROW LEVEL SECURITY;

-- Superadmins can SELECT all blacklist entries
CREATE POLICY "admin_ip_blacklist_superadmin_select" ON admin_ip_blacklist
FOR SELECT TO authenticated
USING (auth.is_superadmin() = true);

-- Only superadmins can INSERT/UPDATE/DELETE blacklist entries
CREATE POLICY "admin_ip_blacklist_superadmin_write" ON admin_ip_blacklist
FOR ALL TO authenticated
USING (auth.is_superadmin() = true)
WITH CHECK (auth.is_superadmin() = true);

-- =====================================================
-- PHASE 11: Active Admin Sessions Table (Legacy)
-- =====================================================
-- Same policies as admin_sessions

ALTER TABLE active_admin_sessions ENABLE ROW LEVEL SECURITY;

-- Admins can SELECT only their own sessions
CREATE POLICY "active_admin_sessions_self_select" ON active_admin_sessions
FOR SELECT TO authenticated
USING (admin_user_id = auth.admin_uid());

-- Superadmins can SELECT all sessions (for monitoring)
CREATE POLICY "active_admin_sessions_superadmin_select" ON active_admin_sessions
FOR SELECT TO authenticated
USING (auth.is_superadmin() = true);

-- Admins can INSERT their own sessions
CREATE POLICY "active_admin_sessions_self_insert" ON active_admin_sessions
FOR INSERT TO authenticated
WITH CHECK (admin_user_id = auth.admin_uid());

-- Admins can UPDATE their own sessions
CREATE POLICY "active_admin_sessions_self_update" ON active_admin_sessions
FOR UPDATE TO authenticated
USING (admin_user_id = auth.admin_uid());

-- Admins can DELETE their own sessions (logout)
CREATE POLICY "active_admin_sessions_self_delete" ON active_admin_sessions
FOR DELETE TO authenticated
USING (admin_user_id = auth.admin_uid());

-- Superadmins can DELETE any session (force logout)
CREATE POLICY "active_admin_sessions_superadmin_delete" ON active_admin_sessions
FOR DELETE TO authenticated
USING (auth.is_superadmin() = true);

-- =====================================================
-- VERIFICATION: Check RLS is enabled
-- =====================================================

DO $$
DECLARE
    admin_tables text[] := ARRAY[
        'admin_users',
        'admin_sessions',
        'active_admin_sessions',
        'admin_roles',
        'admin_permissions',
        'admin_user_permissions',
        'admin_role_permissions',
        'admin_audit_log',
        'admin_security_events',
        'admin_ip_whitelist',
        'admin_ip_blacklist'
    ];
    table_name text;
    rls_enabled boolean;
    policy_count int;
    total_policies int := 0;
BEGIN
    RAISE NOTICE 'Admin RLS Status:';

    FOREACH table_name IN ARRAY admin_tables LOOP
        -- Check if RLS is enabled
        SELECT relrowsecurity INTO rls_enabled
        FROM pg_class
        WHERE relname = table_name;

        -- Count policies
        SELECT COUNT(*) INTO policy_count
        FROM pg_policies
        WHERE tablename = table_name;

        total_policies := total_policies + policy_count;

        RAISE NOTICE '  %: RLS=% Policies=%', table_name, rls_enabled, policy_count;
    END LOOP;

    RAISE NOTICE 'Total admin policies created: %', total_policies;
END $$;

-- =====================================================
-- AUDIT LOG: Record migration
-- =====================================================

INSERT INTO schema_migrations (migration_name, description, checksum)
VALUES (
    '20251004_add_admin_rls_policies',
    'Add Row Level Security policies to 10 admin tables for OWASP A01 compliance',
    md5('admin_rls_policies_v1')
)
ON CONFLICT (migration_name) DO NOTHING;

COMMIT;

-- =====================================================
-- POST-MIGRATION SECURITY TESTING
-- =====================================================
-- Test RLS policies with different admin roles:
--
-- -- As regular admin (should only see own data):
-- SET request.jwt.claims TO '{"admin_uid": "uuid-here", "is_superadmin": false}';
-- SELECT * FROM admin_sessions;  -- Should only see own sessions
-- SELECT * FROM admin_users;     -- Should only see own profile
--
-- -- As superadmin (should see all data):
-- SET request.jwt.claims TO '{"admin_uid": "uuid-here", "is_superadmin": true}';
-- SELECT * FROM admin_sessions;  -- Should see all sessions
-- SELECT * FROM admin_audit_logs; -- Should see all logs
--
-- -- Without JWT (should see nothing):
-- RESET request.jwt.claims;
-- SELECT * FROM admin_sessions;  -- Should return 0 rows
-- =====================================================
