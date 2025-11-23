-- Admin Permissions Seed Data
-- File: 001_admin_permissions.sql
-- Description: Seed admin permissions and roles for the oncology clinic system

-- Insert admin permissions
INSERT INTO admin_permissions (id, name, description, category) VALUES
-- User Management Permissions
(gen_random_uuid(), 'users.create', 'Create new users', 'user_management'),
(gen_random_uuid(), 'users.read', 'View user information', 'user_management'),
(gen_random_uuid(), 'users.update', 'Update user information', 'user_management'),
(gen_random_uuid(), 'users.delete', 'Delete users', 'user_management'),
(gen_random_uuid(), 'users.manage_roles', 'Manage user roles and permissions', 'user_management'),

-- Admin Management Permissions
(gen_random_uuid(), 'admins.create', 'Create new admin users', 'admin_management'),
(gen_random_uuid(), 'admins.read', 'View admin information', 'admin_management'),
(gen_random_uuid(), 'admins.update', 'Update admin information', 'admin_management'),
(gen_random_uuid(), 'admins.delete', 'Delete admin users', 'admin_management'),
(gen_random_uuid(), 'admins.manage_permissions', 'Manage admin permissions', 'admin_management'),

-- Patient Data Permissions
(gen_random_uuid(), 'patients.read', 'View patient data', 'patient_data'),
(gen_random_uuid(), 'patients.write', 'Modify patient data', 'patient_data'),
(gen_random_uuid(), 'patients.delete', 'Delete patient records', 'patient_data'),
(gen_random_uuid(), 'patients.export', 'Export patient data', 'patient_data'),
(gen_random_uuid(), 'patients.import', 'Import patient data', 'patient_data'),

-- Medical Records Permissions
(gen_random_uuid(), 'medical_records.read', 'View medical records', 'medical_records'),
(gen_random_uuid(), 'medical_records.write', 'Create and update medical records', 'medical_records'),
(gen_random_uuid(), 'medical_records.delete', 'Delete medical records', 'medical_records'),
(gen_random_uuid(), 'medical_records.archive', 'Archive medical records', 'medical_records'),

-- Treatment Permissions
(gen_random_uuid(), 'treatments.read', 'View treatment information', 'treatments'),
(gen_random_uuid(), 'treatments.write', 'Create and update treatments', 'treatments'),
(gen_random_uuid(), 'treatments.delete', 'Delete treatment records', 'treatments'),
(gen_random_uuid(), 'treatments.schedule', 'Schedule treatments', 'treatments'),

-- Appointment Permissions
(gen_random_uuid(), 'appointments.read', 'View appointments', 'appointments'),
(gen_random_uuid(), 'appointments.write', 'Create and update appointments', 'appointments'),
(gen_random_uuid(), 'appointments.delete', 'Cancel/delete appointments', 'appointments'),
(gen_random_uuid(), 'appointments.schedule', 'Schedule appointments', 'appointments'),

-- Laboratory Permissions
(gen_random_uuid(), 'laboratory.read', 'View laboratory results', 'laboratory'),
(gen_random_uuid(), 'laboratory.write', 'Create and update lab results', 'laboratory'),
(gen_random_uuid(), 'laboratory.delete', 'Delete laboratory records', 'laboratory'),
(gen_random_uuid(), 'laboratory.approve', 'Approve laboratory results', 'laboratory'),

-- Pharmacy Permissions
(gen_random_uuid(), 'pharmacy.read', 'View medication information', 'pharmacy'),
(gen_random_uuid(), 'pharmacy.write', 'Manage medication prescriptions', 'pharmacy'),
(gen_random_uuid(), 'pharmacy.dispense', 'Dispense medications', 'pharmacy'),
(gen_random_uuid(), 'pharmacy.inventory', 'Manage pharmacy inventory', 'pharmacy'),

-- Financial Permissions
(gen_random_uuid(), 'billing.read', 'View billing information', 'financial'),
(gen_random_uuid(), 'billing.write', 'Create and update billing', 'financial'),
(gen_random_uuid(), 'billing.process', 'Process payments', 'financial'),
(gen_random_uuid(), 'insurance.read', 'View insurance information', 'financial'),
(gen_random_uuid(), 'insurance.write', 'Manage insurance claims', 'financial'),

-- Reporting Permissions
(gen_random_uuid(), 'reports.patient', 'Generate patient reports', 'reporting'),
(gen_random_uuid(), 'reports.financial', 'Generate financial reports', 'reporting'),
(gen_random_uuid(), 'reports.operational', 'Generate operational reports', 'reporting'),
(gen_random_uuid(), 'reports.compliance', 'Generate compliance reports', 'reporting'),

-- System Management Permissions
(gen_random_uuid(), 'system.analytics', 'View system analytics', 'system_management'),
(gen_random_uuid(), 'system.reports', 'Generate system reports', 'system_management'),
(gen_random_uuid(), 'system.audit', 'View audit logs', 'system_management'),
(gen_random_uuid(), 'system.settings', 'Modify system settings', 'system_management'),
(gen_random_uuid(), 'system.backup', 'Perform system backups', 'system_management'),
(gen_random_uuid(), 'system.maintenance', 'Perform system maintenance', 'system_management'),

-- Security Permissions
(gen_random_uuid(), 'security.logs', 'View security logs', 'security'),
(gen_random_uuid(), 'security.settings', 'Modify security settings', 'security'),
(gen_random_uuid(), 'security.incidents', 'Manage security incidents', 'security'),
(gen_random_uuid(), 'security.monitoring', 'Monitor security events', 'security'),
(gen_random_uuid(), 'security.ip_management', 'Manage IP whitelist/blacklist', 'security'),

-- Communication Permissions
(gen_random_uuid(), 'communications.send', 'Send communications to patients', 'communications'),
(gen_random_uuid(), 'communications.receive', 'Receive patient communications', 'communications'),
(gen_random_uuid(), 'communications.templates', 'Manage communication templates', 'communications'),
(gen_random_uuid(), 'communications.notifications', 'Manage system notifications', 'communications'),

-- Integration Permissions
(gen_random_uuid(), 'integrations.read', 'View integration status', 'integrations'),
(gen_random_uuid(), 'integrations.manage', 'Manage system integrations', 'integrations'),
(gen_random_uuid(), 'api.access', 'Access API endpoints', 'integrations'),
(gen_random_uuid(), 'api.manage', 'Manage API configurations', 'integrations')

ON CONFLICT (name) DO NOTHING;

-- Insert admin roles
INSERT INTO admin_roles (id, name, description, is_system_role) VALUES
(gen_random_uuid(), 'super_admin', 'Super Administrator with full system access', true),
(gen_random_uuid(), 'admin', 'Administrator with extensive permissions', true),
(gen_random_uuid(), 'manager', 'Manager with departmental permissions', true),
(gen_random_uuid(), 'supervisor', 'Supervisor with limited permissions', true),
(gen_random_uuid(), 'doctor', 'Medical doctor with clinical permissions', false),
(gen_random_uuid(), 'nurse', 'Nurse with patient care permissions', false),
(gen_random_uuid(), 'receptionist', 'Reception staff with scheduling permissions', false),
(gen_random_uuid(), 'lab_tech', 'Laboratory technician permissions', false),
(gen_random_uuid(), 'pharmacist', 'Pharmacy staff permissions', false),
(gen_random_uuid(), 'billing_clerk', 'Billing and insurance permissions', false)
ON CONFLICT (name) DO NOTHING;

-- Assign permissions to super_admin role (all permissions)
INSERT INTO admin_role_permissions (role_id, permission_id)
SELECT
    (SELECT id FROM admin_roles WHERE name = 'super_admin'),
    p.id
FROM admin_permissions p
ON CONFLICT DO NOTHING;

-- Assign permissions to admin role
INSERT INTO admin_role_permissions (role_id, permission_id)
SELECT
    (SELECT id FROM admin_roles WHERE name = 'admin'),
    p.id
FROM admin_permissions p
WHERE p.name IN (
    'users.create', 'users.read', 'users.update', 'users.delete',
    'admins.read', 'admins.update',
    'patients.read', 'patients.write', 'patients.export',
    'medical_records.read', 'medical_records.write',
    'treatments.read', 'treatments.write', 'treatments.schedule',
    'appointments.read', 'appointments.write', 'appointments.schedule',
    'laboratory.read', 'laboratory.write', 'laboratory.approve',
    'pharmacy.read', 'pharmacy.write',
    'billing.read', 'billing.write', 'insurance.read',
    'reports.patient', 'reports.financial', 'reports.operational',
    'system.analytics', 'system.reports', 'system.settings',
    'security.logs', 'security.monitoring',
    'communications.send', 'communications.receive',
    'integrations.read'
)
ON CONFLICT DO NOTHING;

-- Assign permissions to manager role
INSERT INTO admin_role_permissions (role_id, permission_id)
SELECT
    (SELECT id FROM admin_roles WHERE name = 'manager'),
    p.id
FROM admin_permissions p
WHERE p.name IN (
    'users.read', 'users.update',
    'patients.read', 'patients.write',
    'medical_records.read', 'medical_records.write',
    'treatments.read', 'treatments.write', 'treatments.schedule',
    'appointments.read', 'appointments.write', 'appointments.schedule',
    'laboratory.read', 'laboratory.write',
    'pharmacy.read', 'pharmacy.write',
    'billing.read', 'billing.write', 'insurance.read',
    'reports.patient', 'reports.operational',
    'system.analytics',
    'communications.send', 'communications.receive'
)
ON CONFLICT DO NOTHING;

-- Assign permissions to supervisor role
INSERT INTO admin_role_permissions (role_id, permission_id)
SELECT
    (SELECT id FROM admin_roles WHERE name = 'supervisor'),
    p.id
FROM admin_permissions p
WHERE p.name IN (
    'users.read',
    'patients.read',
    'medical_records.read',
    'treatments.read',
    'appointments.read', 'appointments.write', 'appointments.schedule',
    'laboratory.read',
    'pharmacy.read',
    'billing.read',
    'reports.patient',
    'system.analytics',
    'communications.receive'
)
ON CONFLICT DO NOTHING;

-- Assign permissions to doctor role
INSERT INTO admin_role_permissions (role_id, permission_id)
SELECT
    (SELECT id FROM admin_roles WHERE name = 'doctor'),
    p.id
FROM admin_permissions p
WHERE p.name IN (
    'patients.read', 'patients.write',
    'medical_records.read', 'medical_records.write',
    'treatments.read', 'treatments.write', 'treatments.schedule',
    'appointments.read', 'appointments.write', 'appointments.schedule',
    'laboratory.read', 'laboratory.write', 'laboratory.approve',
    'pharmacy.read', 'pharmacy.write',
    'reports.patient',
    'communications.send', 'communications.receive'
)
ON CONFLICT DO NOTHING;

-- Assign permissions to nurse role
INSERT INTO admin_role_permissions (role_id, permission_id)
SELECT
    (SELECT id FROM admin_roles WHERE name = 'nurse'),
    p.id
FROM admin_permissions p
WHERE p.name IN (
    'patients.read', 'patients.write',
    'medical_records.read', 'medical_records.write',
    'treatments.read', 'treatments.write',
    'appointments.read', 'appointments.write',
    'laboratory.read',
    'pharmacy.read',
    'communications.send', 'communications.receive'
)
ON CONFLICT DO NOTHING;

-- Assign permissions to receptionist role
INSERT INTO admin_role_permissions (role_id, permission_id)
SELECT
    (SELECT id FROM admin_roles WHERE name = 'receptionist'),
    p.id
FROM admin_permissions p
WHERE p.name IN (
    'patients.read', 'patients.write',
    'appointments.read', 'appointments.write', 'appointments.schedule',
    'billing.read', 'insurance.read',
    'communications.send', 'communications.receive'
)
ON CONFLICT DO NOTHING;

-- Assign permissions to lab_tech role
INSERT INTO admin_role_permissions (role_id, permission_id)
SELECT
    (SELECT id FROM admin_roles WHERE name = 'lab_tech'),
    p.id
FROM admin_permissions p
WHERE p.name IN (
    'patients.read',
    'laboratory.read', 'laboratory.write',
    'communications.receive'
)
ON CONFLICT DO NOTHING;

-- Assign permissions to pharmacist role
INSERT INTO admin_role_permissions (role_id, permission_id)
SELECT
    (SELECT id FROM admin_roles WHERE name = 'pharmacist'),
    p.id
FROM admin_permissions p
WHERE p.name IN (
    'patients.read',
    'pharmacy.read', 'pharmacy.write', 'pharmacy.dispense', 'pharmacy.inventory',
    'communications.receive'
)
ON CONFLICT DO NOTHING;

-- Assign permissions to billing_clerk role
INSERT INTO admin_role_permissions (role_id, permission_id)
SELECT
    (SELECT id FROM admin_roles WHERE name = 'billing_clerk'),
    p.id
FROM admin_permissions p
WHERE p.name IN (
    'patients.read',
    'billing.read', 'billing.write', 'billing.process',
    'insurance.read', 'insurance.write',
    'reports.financial',
    'communications.send', 'communications.receive'
)
ON CONFLICT DO NOTHING;

-- Insert some default IP addresses to whitelist (adjust as needed)
INSERT INTO admin_ip_whitelist (ip_address, description, added_at) VALUES
('127.0.0.1', 'Localhost IPv4', CURRENT_TIMESTAMP),
('::1', 'Localhost IPv6', CURRENT_TIMESTAMP)
ON CONFLICT DO NOTHING;