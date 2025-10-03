-- ============================================================================
-- SUPABASE ADMIN SYSTEM COMPLETE MIGRATION
-- ============================================================================
-- Description: Complete admin authentication and management system for Supabase
-- Version: 1.0.0
-- Created: 2025-09-23
--
-- This migration includes:
-- 1. All admin tables with proper constraints
-- 2. RLS (Row Level Security) policies
-- 3. Performance indexes
-- 4. Authentication functions
-- 5. Audit logging system
-- 6. Session management
-- 7. Security monitoring
-- ============================================================================

-- ============================================================================
-- SECTION 1: EXTENSIONS
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- SECTION 2: CUSTOM TYPES
-- ============================================================================

-- Admin role enum
DO $$ BEGIN
    CREATE TYPE admin_role_type AS ENUM ('super_admin', 'admin', 'manager', 'supervisor');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Event severity enum
DO $$ BEGIN
    CREATE TYPE severity_type AS ENUM ('low', 'medium', 'high', 'critical');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- HTTP method enum
DO $$ BEGIN
    CREATE TYPE http_method_type AS ENUM ('GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ============================================================================
-- SECTION 3: ADMIN TABLES
-- ============================================================================

-- Create admin_users table
CREATE TABLE IF NOT EXISTS admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    role admin_role_type NOT NULL DEFAULT 'supervisor',
    department VARCHAR(100),
    phone_number VARCHAR(20),

    -- Security fields
    is_active BOOLEAN DEFAULT true,
    email_verified BOOLEAN DEFAULT false,
    two_factor_enabled BOOLEAN DEFAULT false,
    two_factor_secret VARCHAR(255),
    must_change_password BOOLEAN DEFAULT true,

    -- Login tracking
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP WITH TIME ZONE,
    last_login_at TIMESTAMP WITH TIME ZONE,
    last_login_ip INET,
    last_password_change TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Session management
    max_concurrent_sessions INTEGER DEFAULT 3,

    -- Audit fields
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES admin_users(id),
    updated_by UUID REFERENCES admin_users(id),

    -- Metadata
    metadata JSONB DEFAULT '{}',

    -- Constraints
    CONSTRAINT valid_email CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    CONSTRAINT positive_max_sessions CHECK (max_concurrent_sessions > 0),
    CONSTRAINT valid_failed_attempts CHECK (failed_login_attempts >= 0)
);

-- Create admin_permissions table
CREATE TABLE IF NOT EXISTS admin_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_permission_name CHECK (name ~ '^[a-z0-9_]+\.[a-z0-9_]+$')
);

-- Create admin_roles table
CREATE TABLE IF NOT EXISTS admin_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    is_system_role BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_role_name CHECK (name ~ '^[a-z0-9_]+$')
);

-- Create admin_user_permissions table (many-to-many)
CREATE TABLE IF NOT EXISTS admin_user_permissions (
    admin_user_id UUID NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES admin_permissions(id) ON DELETE CASCADE,
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    granted_by UUID REFERENCES admin_users(id),

    PRIMARY KEY (admin_user_id, permission_id)
);

-- Create admin_role_permissions table (many-to-many)
CREATE TABLE IF NOT EXISTS admin_role_permissions (
    role_id UUID NOT NULL REFERENCES admin_roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES admin_permissions(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (role_id, permission_id)
);

-- Create admin_sessions table
CREATE TABLE IF NOT EXISTS admin_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_user_id UUID NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    refresh_token VARCHAR(255) UNIQUE,
    ip_address INET,
    user_agent TEXT,
    device_fingerprint VARCHAR(255),

    -- Session tracking
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Session metadata
    is_active BOOLEAN DEFAULT true,
    logout_reason VARCHAR(100),
    metadata JSONB DEFAULT '{}',

    CONSTRAINT valid_session_duration CHECK (expires_at > created_at)
);

-- Create admin_audit_log table
CREATE TABLE IF NOT EXISTS admin_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_user_id UUID REFERENCES admin_users(id),
    session_id UUID REFERENCES admin_sessions(id),

    -- Event details
    event_type VARCHAR(100) NOT NULL,
    event_category VARCHAR(50) NOT NULL,
    action VARCHAR(255) NOT NULL,
    resource_type VARCHAR(100),
    resource_id VARCHAR(255),

    -- Request details
    ip_address INET,
    user_agent TEXT,
    endpoint VARCHAR(500),
    http_method http_method_type,

    -- Event metadata
    details JSONB DEFAULT '{}',
    changes JSONB,
    success BOOLEAN DEFAULT true,
    error_message TEXT,

    -- Timing
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    duration_ms INTEGER,

    -- Security classification
    severity severity_type DEFAULT 'low'
);

-- Create admin_security_events table
CREATE TABLE IF NOT EXISTS admin_security_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100) NOT NULL,
    severity severity_type NOT NULL DEFAULT 'medium',

    -- Source information
    ip_address INET,
    user_agent TEXT,
    admin_user_id UUID REFERENCES admin_users(id),
    session_id UUID REFERENCES admin_sessions(id),

    -- Event details
    description TEXT,
    details JSONB DEFAULT '{}',
    endpoint VARCHAR(500),

    -- Detection and response
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT,
    auto_resolved BOOLEAN DEFAULT false,

    -- Risk assessment
    risk_score INTEGER DEFAULT 0,
    threat_level severity_type DEFAULT 'low',

    CONSTRAINT valid_risk_score CHECK (risk_score >= 0 AND risk_score <= 100)
);

-- Create admin_ip_whitelist table
CREATE TABLE IF NOT EXISTS admin_ip_whitelist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ip_address INET,
    ip_range CIDR,
    description TEXT,

    -- Management
    added_by UUID REFERENCES admin_users(id),
    added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    expires_at TIMESTAMP WITH TIME ZONE,

    -- Usage tracking
    last_used_at TIMESTAMP WITH TIME ZONE,
    usage_count INTEGER DEFAULT 0,

    CONSTRAINT unique_ip_or_range UNIQUE (ip_address, ip_range),
    CONSTRAINT ip_or_range_required CHECK (ip_address IS NOT NULL OR ip_range IS NOT NULL)
);

-- Create admin_ip_blacklist table
CREATE TABLE IF NOT EXISTS admin_ip_blacklist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ip_address INET NOT NULL UNIQUE,
    reason VARCHAR(255) NOT NULL,

    -- Blacklist details
    blocked_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    blocked_by UUID REFERENCES admin_users(id),
    expires_at TIMESTAMP WITH TIME ZONE,
    is_permanent BOOLEAN DEFAULT false,

    -- Incident tracking
    incident_id UUID,
    threat_level severity_type DEFAULT 'medium',
    block_count INTEGER DEFAULT 1,

    -- Metadata
    details JSONB DEFAULT '{}',
    notes TEXT
);

-- ============================================================================
-- SECTION 4: INDEXES FOR PERFORMANCE
-- ============================================================================

-- Admin users indexes
CREATE INDEX IF NOT EXISTS idx_admin_users_email ON admin_users(email);
CREATE INDEX IF NOT EXISTS idx_admin_users_role ON admin_users(role);
CREATE INDEX IF NOT EXISTS idx_admin_users_active ON admin_users(is_active);
CREATE INDEX IF NOT EXISTS idx_admin_users_locked ON admin_users(locked_until) WHERE locked_until IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_admin_users_last_login ON admin_users(last_login_at);

-- Admin sessions indexes
CREATE INDEX IF NOT EXISTS idx_admin_sessions_user_id ON admin_sessions(admin_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_sessions_token ON admin_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_admin_sessions_active ON admin_sessions(is_active, last_activity);
CREATE INDEX IF NOT EXISTS idx_admin_sessions_expires ON admin_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_admin_sessions_ip ON admin_sessions(ip_address);

-- Audit log indexes
CREATE INDEX IF NOT EXISTS idx_admin_audit_user_id ON admin_audit_log(admin_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_audit_timestamp ON admin_audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_admin_audit_event_type ON admin_audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_admin_audit_ip ON admin_audit_log(ip_address);
CREATE INDEX IF NOT EXISTS idx_admin_audit_resource ON admin_audit_log(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_admin_audit_severity ON admin_audit_log(severity);

-- Security events indexes
CREATE INDEX IF NOT EXISTS idx_security_events_timestamp ON admin_security_events(detected_at);
CREATE INDEX IF NOT EXISTS idx_security_events_severity ON admin_security_events(severity);
CREATE INDEX IF NOT EXISTS idx_security_events_ip ON admin_security_events(ip_address);
CREATE INDEX IF NOT EXISTS idx_security_events_user_id ON admin_security_events(admin_user_id);
CREATE INDEX IF NOT EXISTS idx_security_events_resolved ON admin_security_events(resolved_at) WHERE resolved_at IS NOT NULL;

-- IP management indexes
CREATE INDEX IF NOT EXISTS idx_ip_whitelist_active ON admin_ip_whitelist(is_active, ip_address);
CREATE INDEX IF NOT EXISTS idx_ip_whitelist_range ON admin_ip_whitelist USING gist(ip_range);
CREATE INDEX IF NOT EXISTS idx_ip_blacklist_active ON admin_ip_blacklist(ip_address, expires_at);

-- Permissions indexes
CREATE INDEX IF NOT EXISTS idx_admin_permissions_category ON admin_permissions(category);
CREATE INDEX IF NOT EXISTS idx_admin_user_permissions_user ON admin_user_permissions(admin_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_role_permissions_role ON admin_role_permissions(role_id);

-- ============================================================================
-- SECTION 5: TRIGGERS AND FUNCTIONS
-- ============================================================================

-- Update timestamp trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at trigger to admin_users
DROP TRIGGER IF EXISTS trigger_admin_users_updated_at ON admin_users;
CREATE TRIGGER trigger_admin_users_updated_at
    BEFORE UPDATE ON admin_users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Apply updated_at trigger to admin_roles
DROP TRIGGER IF EXISTS trigger_admin_roles_updated_at ON admin_roles;
CREATE TRIGGER trigger_admin_roles_updated_at
    BEFORE UPDATE ON admin_roles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function to clean expired sessions
CREATE OR REPLACE FUNCTION clean_expired_admin_sessions()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM admin_sessions
    WHERE expires_at < CURRENT_TIMESTAMP
       OR (last_activity < CURRENT_TIMESTAMP - INTERVAL '4 hours' AND is_active = true);

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to clean old audit logs (keep last 90 days)
CREATE OR REPLACE FUNCTION clean_old_audit_logs()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM admin_audit_log
    WHERE timestamp < CURRENT_TIMESTAMP - INTERVAL '90 days';

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to clean resolved security events (keep last 30 days)
CREATE OR REPLACE FUNCTION clean_old_security_events()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM admin_security_events
    WHERE resolved_at IS NOT NULL
      AND resolved_at < CURRENT_TIMESTAMP - INTERVAL '30 days';

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to check if admin is locked
CREATE OR REPLACE FUNCTION is_admin_locked(p_admin_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    v_locked_until TIMESTAMP WITH TIME ZONE;
BEGIN
    SELECT locked_until INTO v_locked_until
    FROM admin_users
    WHERE id = p_admin_id;

    RETURN v_locked_until IS NOT NULL AND v_locked_until > CURRENT_TIMESTAMP;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to unlock admin account
CREATE OR REPLACE FUNCTION unlock_admin_account(p_admin_id UUID)
RETURNS VOID AS $$
BEGIN
    UPDATE admin_users
    SET locked_until = NULL,
        failed_login_attempts = 0
    WHERE id = p_admin_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to record failed login
CREATE OR REPLACE FUNCTION record_failed_login(
    p_admin_id UUID,
    p_ip_address INET,
    p_user_agent TEXT
)
RETURNS VOID AS $$
DECLARE
    v_attempts INTEGER;
BEGIN
    -- Increment failed attempts
    UPDATE admin_users
    SET failed_login_attempts = failed_login_attempts + 1
    WHERE id = p_admin_id
    RETURNING failed_login_attempts INTO v_attempts;

    -- Lock account if 5 or more failed attempts
    IF v_attempts >= 5 THEN
        UPDATE admin_users
        SET locked_until = CURRENT_TIMESTAMP + INTERVAL '30 minutes'
        WHERE id = p_admin_id;

        -- Log security event
        INSERT INTO admin_security_events (
            event_type, severity, ip_address, user_agent,
            admin_user_id, description, threat_level, risk_score
        ) VALUES (
            'account_locked', 'high', p_ip_address, p_user_agent,
            p_admin_id, 'Account locked due to multiple failed login attempts',
            'high', 75
        );
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to record successful login
CREATE OR REPLACE FUNCTION record_successful_login(
    p_admin_id UUID,
    p_ip_address INET,
    p_session_id UUID
)
RETURNS VOID AS $$
BEGIN
    UPDATE admin_users
    SET last_login_at = CURRENT_TIMESTAMP,
        last_login_ip = p_ip_address,
        failed_login_attempts = 0,
        locked_until = NULL
    WHERE id = p_admin_id;

    -- Log audit event
    INSERT INTO admin_audit_log (
        admin_user_id, session_id, event_type, event_category,
        action, ip_address, severity
    ) VALUES (
        p_admin_id, p_session_id, 'admin_login', 'authentication',
        'successful_login', p_ip_address, 'low'
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get admin permissions
CREATE OR REPLACE FUNCTION get_admin_permissions(p_admin_id UUID)
RETURNS TABLE(permission_name VARCHAR, permission_category VARCHAR) AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT p.name, p.category
    FROM admin_permissions p
    INNER JOIN admin_user_permissions up ON p.id = up.permission_id
    WHERE up.admin_user_id = p_admin_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- SECTION 6: ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================

-- Enable RLS on all admin tables
ALTER TABLE admin_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_user_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_role_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_security_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_ip_whitelist ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_ip_blacklist ENABLE ROW LEVEL SECURITY;

-- Admin Users Policies
DROP POLICY IF EXISTS admin_users_select_policy ON admin_users;
CREATE POLICY admin_users_select_policy ON admin_users
    FOR SELECT
    USING (
        auth.role() = 'authenticated' AND
        (
            id = auth.uid() OR
            EXISTS (
                SELECT 1 FROM admin_users
                WHERE id = auth.uid() AND role IN ('super_admin', 'admin')
            )
        )
    );

DROP POLICY IF EXISTS admin_users_insert_policy ON admin_users;
CREATE POLICY admin_users_insert_policy ON admin_users
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM admin_users
            WHERE id = auth.uid() AND role IN ('super_admin', 'admin')
        )
    );

DROP POLICY IF EXISTS admin_users_update_policy ON admin_users;
CREATE POLICY admin_users_update_policy ON admin_users
    FOR UPDATE
    USING (
        id = auth.uid() OR
        EXISTS (
            SELECT 1 FROM admin_users
            WHERE id = auth.uid() AND role = 'super_admin'
        )
    );

DROP POLICY IF EXISTS admin_users_delete_policy ON admin_users;
CREATE POLICY admin_users_delete_policy ON admin_users
    FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM admin_users
            WHERE id = auth.uid() AND role = 'super_admin'
        )
    );

-- Admin Sessions Policies
DROP POLICY IF EXISTS admin_sessions_select_policy ON admin_sessions;
CREATE POLICY admin_sessions_select_policy ON admin_sessions
    FOR SELECT
    USING (
        admin_user_id = auth.uid() OR
        EXISTS (
            SELECT 1 FROM admin_users
            WHERE id = auth.uid() AND role IN ('super_admin', 'admin')
        )
    );

DROP POLICY IF EXISTS admin_sessions_insert_policy ON admin_sessions;
CREATE POLICY admin_sessions_insert_policy ON admin_sessions
    FOR INSERT
    WITH CHECK (admin_user_id = auth.uid());

DROP POLICY IF EXISTS admin_sessions_update_policy ON admin_sessions;
CREATE POLICY admin_sessions_update_policy ON admin_sessions
    FOR UPDATE
    USING (admin_user_id = auth.uid());

DROP POLICY IF EXISTS admin_sessions_delete_policy ON admin_sessions;
CREATE POLICY admin_sessions_delete_policy ON admin_sessions
    FOR DELETE
    USING (admin_user_id = auth.uid());

-- Admin Audit Log Policies (read-only for most, full access for super_admin)
DROP POLICY IF EXISTS admin_audit_log_select_policy ON admin_audit_log;
CREATE POLICY admin_audit_log_select_policy ON admin_audit_log
    FOR SELECT
    USING (
        admin_user_id = auth.uid() OR
        EXISTS (
            SELECT 1 FROM admin_users
            WHERE id = auth.uid() AND role IN ('super_admin', 'admin', 'manager')
        )
    );

DROP POLICY IF EXISTS admin_audit_log_insert_policy ON admin_audit_log;
CREATE POLICY admin_audit_log_insert_policy ON admin_audit_log
    FOR INSERT
    WITH CHECK (auth.role() = 'authenticated');

-- Security Events Policies (super_admin and admin only)
DROP POLICY IF EXISTS admin_security_events_select_policy ON admin_security_events;
CREATE POLICY admin_security_events_select_policy ON admin_security_events
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM admin_users
            WHERE id = auth.uid() AND role IN ('super_admin', 'admin')
        )
    );

DROP POLICY IF EXISTS admin_security_events_insert_policy ON admin_security_events;
CREATE POLICY admin_security_events_insert_policy ON admin_security_events
    FOR INSERT
    WITH CHECK (auth.role() = 'authenticated');

-- Permissions Policies (read for all authenticated, write for super_admin)
DROP POLICY IF EXISTS admin_permissions_select_policy ON admin_permissions;
CREATE POLICY admin_permissions_select_policy ON admin_permissions
    FOR SELECT
    USING (auth.role() = 'authenticated');

DROP POLICY IF EXISTS admin_permissions_insert_policy ON admin_permissions;
CREATE POLICY admin_permissions_insert_policy ON admin_permissions
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM admin_users
            WHERE id = auth.uid() AND role = 'super_admin'
        )
    );

-- IP Whitelist/Blacklist Policies (super_admin only)
DROP POLICY IF EXISTS admin_ip_whitelist_policy ON admin_ip_whitelist;
CREATE POLICY admin_ip_whitelist_policy ON admin_ip_whitelist
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM admin_users
            WHERE id = auth.uid() AND role = 'super_admin'
        )
    );

DROP POLICY IF EXISTS admin_ip_blacklist_policy ON admin_ip_blacklist;
CREATE POLICY admin_ip_blacklist_policy ON admin_ip_blacklist
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM admin_users
            WHERE id = auth.uid() AND role = 'super_admin'
        )
    );

-- ============================================================================
-- SECTION 7: VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Active admin sessions view
CREATE OR REPLACE VIEW active_admin_sessions AS
SELECT
    s.*,
    u.email,
    u.first_name,
    u.last_name,
    u.role,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - s.last_activity)) as seconds_since_activity
FROM admin_sessions s
JOIN admin_users u ON s.admin_user_id = u.id
WHERE s.is_active = true
  AND s.expires_at > CURRENT_TIMESTAMP;

-- Admin security summary view
CREATE OR REPLACE VIEW admin_security_summary AS
SELECT
    u.id,
    u.email,
    u.first_name,
    u.last_name,
    u.role,
    u.is_active,
    u.failed_login_attempts,
    u.locked_until,
    u.last_login_at,
    u.last_login_ip,
    u.two_factor_enabled,
    COUNT(s.id) as active_sessions,
    MAX(s.last_activity) as last_session_activity
FROM admin_users u
LEFT JOIN admin_sessions s ON u.id = s.admin_user_id AND s.is_active = true
GROUP BY u.id, u.email, u.first_name, u.last_name, u.role, u.is_active,
         u.failed_login_attempts, u.locked_until, u.last_login_at,
         u.last_login_ip, u.two_factor_enabled;

-- Recent security events view
CREATE OR REPLACE VIEW recent_security_events AS
SELECT
    se.*,
    u.email as admin_email,
    u.first_name || ' ' || u.last_name as admin_name
FROM admin_security_events se
LEFT JOIN admin_users u ON se.admin_user_id = u.id
WHERE se.detected_at > CURRENT_TIMESTAMP - INTERVAL '24 hours'
ORDER BY se.detected_at DESC;

-- ============================================================================
-- SECTION 8: INITIAL DATA - PERMISSIONS
-- ============================================================================

-- Insert default permissions
INSERT INTO admin_permissions (name, description, category) VALUES
-- User management
('users.view', 'View user information', 'users'),
('users.create', 'Create new users', 'users'),
('users.update', 'Update user information', 'users'),
('users.delete', 'Delete users', 'users'),

-- Admin management
('admins.view', 'View admin information', 'admins'),
('admins.create', 'Create new admins', 'admins'),
('admins.update', 'Update admin information', 'admins'),
('admins.delete', 'Delete admins', 'admins'),

-- Patient management
('patients.view', 'View patient information', 'patients'),
('patients.create', 'Create patient records', 'patients'),
('patients.update', 'Update patient records', 'patients'),
('patients.delete', 'Delete patient records', 'patients'),

-- System configuration
('system.config', 'Configure system settings', 'system'),
('system.security', 'Manage security settings', 'system'),
('system.audit', 'Access audit logs', 'system'),
('system.reports', 'Generate system reports', 'system'),

-- Analytics
('analytics.view', 'View analytics dashboards', 'analytics'),
('analytics.export', 'Export analytics data', 'analytics')

ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- SECTION 9: INITIAL DATA - ROLES
-- ============================================================================

-- Insert default roles
INSERT INTO admin_roles (name, description, is_system_role) VALUES
('super_admin', 'Full system access with all permissions', true),
('admin', 'Administrative access with most permissions', true),
('manager', 'Management access with limited permissions', true),
('supervisor', 'Supervisory access with read-only permissions', true)
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- SECTION 10: GRANT PERMISSIONS TO SERVICE ROLE
-- ============================================================================

-- Grant necessary permissions to service role for API access
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO service_role;

-- Grant select on views
GRANT SELECT ON active_admin_sessions TO service_role;
GRANT SELECT ON admin_security_summary TO service_role;
GRANT SELECT ON recent_security_events TO service_role;

-- ============================================================================
-- SECTION 11: SCHEDULED CLEANUP JOBS (OPTIONAL - REQUIRES pg_cron)
-- ============================================================================

-- Note: Uncomment these if pg_cron extension is available in your Supabase project
--
-- -- Clean expired sessions daily at 2 AM
-- SELECT cron.schedule(
--     'clean-expired-sessions',
--     '0 2 * * *',
--     $$SELECT clean_expired_admin_sessions();$$
-- );
--
-- -- Clean old audit logs weekly on Sunday at 3 AM
-- SELECT cron.schedule(
--     'clean-old-audit-logs',
--     '0 3 * * 0',
--     $$SELECT clean_old_audit_logs();$$
-- );
--
-- -- Clean old security events daily at 4 AM
-- SELECT cron.schedule(
--     'clean-old-security-events',
--     '0 4 * * *',
--     $$SELECT clean_old_security_events();$$
-- );

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================

-- Log migration completion
DO $$
BEGIN
    RAISE NOTICE 'Admin system migration completed successfully!';
    RAISE NOTICE 'Tables created: admin_users, admin_permissions, admin_roles, admin_sessions, admin_audit_log, admin_security_events, admin_ip_whitelist, admin_ip_blacklist';
    RAISE NOTICE 'RLS policies enabled on all tables';
    RAISE NOTICE 'Performance indexes created';
    RAISE NOTICE 'Authentication and security functions deployed';
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '1. Create your first admin user using Supabase dashboard or API';
    RAISE NOTICE '2. Configure JWT secrets in environment variables';
    RAISE NOTICE '3. Test authentication endpoints';
    RAISE NOTICE '4. Enable scheduled cleanup jobs if pg_cron is available';
END $$;