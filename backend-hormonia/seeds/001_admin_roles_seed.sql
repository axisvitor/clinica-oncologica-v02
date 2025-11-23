-- Admin Roles Seed Data
-- Creates the default admin roles with appropriate permissions

-- Insert default admin roles
INSERT INTO admin_roles (name, description, permissions, is_system_role, is_active) VALUES

-- Super Admin Role (all permissions)
('super_admin', 'Super Administrator with full system access',
 ARRAY['super_admin'::admin_permission],
 true, true),

-- System Admin Role (system management without user data access)
('system_admin', 'System Administrator for infrastructure and settings',
 ARRAY[
    'system_settings'::admin_permission,
    'audit_logs'::admin_permission,
    'user_management'::admin_permission,
    'users_read'::admin_permission,
    'users_write'::admin_permission,
    'reports_read'::admin_permission
 ]::admin_permission[],
 true, true),

-- User Manager Role (user and patient management)
('user_manager', 'User Manager for healthcare provider and patient management',
 ARRAY[
    'users_read'::admin_permission,
    'users_write'::admin_permission,
    'users_delete'::admin_permission,
    'patients_read'::admin_permission,
    'patients_write'::admin_permission,
    'patients_delete'::admin_permission,
    'audit_logs'::admin_permission
 ]::admin_permission[],
 true, true),

-- Communication Manager Role (message and communication management)
('communication_manager', 'Communication Manager for messaging and reports',
 ARRAY[
    'patients_read'::admin_permission,
    'messages_read'::admin_permission,
    'messages_write'::admin_permission,
    'messages_delete'::admin_permission,
    'reports_read'::admin_permission,
    'reports_write'::admin_permission,
    'audit_logs'::admin_permission
 ]::admin_permission[],
 true, true),

-- Report Analyst Role (read-only access for reporting)
('report_analyst', 'Report Analyst with read-only access for data analysis',
 ARRAY[
    'users_read'::admin_permission,
    'patients_read'::admin_permission,
    'messages_read'::admin_permission,
    'reports_read'::admin_permission,
    'reports_write'::admin_permission,
    'audit_logs'::admin_permission
 ]::admin_permission[],
 true, true),

-- Support Agent Role (limited access for customer support)
('support_agent', 'Support Agent with limited access for customer assistance',
 ARRAY[
    'patients_read'::admin_permission,
    'messages_read'::admin_permission,
    'messages_write'::admin_permission
 ]::admin_permission[],
 true, true),

-- Auditor Role (read-only access for auditing purposes)
('auditor', 'Auditor with read-only access for compliance and auditing',
 ARRAY[
    'users_read'::admin_permission,
    'patients_read'::admin_permission,
    'messages_read'::admin_permission,
    'reports_read'::admin_permission,
    'audit_logs'::admin_permission
 ]::admin_permission[],
 true, true);

-- Success message
SELECT 'Admin roles seed data inserted successfully! Created 7 default roles.' as status;