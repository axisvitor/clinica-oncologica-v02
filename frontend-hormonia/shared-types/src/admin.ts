// Shared Admin Types - Admin domain types for frontend and backend

/**
 * Admin role type - matches admin_role_type enum
 */
export enum AdminRoleType {
    SUPER_ADMIN = 'super_admin',
    ADMIN = 'admin',
    MANAGER = 'manager',
    SUPERVISOR = 'supervisor'
}

/**
 * User role - matches user_role enum
 */
export enum UserRole {
    DOCTOR = 'doctor',
    ADMIN = 'admin'
}

/**
 * Core admin user interface - matches admin_users table
 */
export interface AdminUser {
    id: string
    email: string
    first_name?: string | null
    last_name?: string | null
    full_name?: string // Computed field
    role: AdminRoleType | string
    department?: string | null
    phone_number?: string | null
    is_active: boolean
    email_verified: boolean
    two_factor_enabled: boolean
    must_change_password: boolean
    failed_login_attempts: number
    locked_until?: string | null
    last_login_at?: string | null
    last_login_ip?: string | null
    last_password_change?: string | null
    max_concurrent_sessions: number
    metadata?: Record<string, unknown>
    created_at: string
    updated_at: string
    created_by?: string | null
    updated_by?: string | null
}

/**
 * Standard user interface - matches users table
 */
export interface User {
    id: string
    email: string
    full_name?: string | null
    role: UserRole | string
    is_active: boolean
    created_at: string
    updated_at: string
}

/**
 * Admin permission interface - matches admin_permissions table
 */
export interface AdminPermission {
    id: string
    name: string
    description?: string | null
    category?: string | null
    created_at: string
}

/**
 * Admin role interface - matches admin_roles table
 */
export interface AdminRole {
    id: string
    name: string
    description?: string | null
    is_system_role: boolean
    permissions?: string[]
    created_at: string
    updated_at: string
}

/**
 * Create admin user request
 */
export interface CreateAdminUserRequest {
    email: string
    first_name?: string
    last_name?: string
    full_name?: string
    password?: string
    role: AdminRoleType | string
    department?: string
    phone_number?: string
    permissions?: string[]
    two_factor_enabled?: boolean
}

/**
 * Update admin user request
 */
export interface UpdateAdminUserRequest {
    email?: string
    first_name?: string
    last_name?: string
    full_name?: string
    role?: AdminRoleType | string
    department?: string
    phone_number?: string
    permissions?: string[]
    is_active?: boolean
}

/**
 * Reset password request
 */
export interface ResetPasswordRequest {
    new_password: string
    force_change?: boolean
}

/**
 * Admin session interface - matches admin_sessions table
 */
export interface AdminSession {
    id: string
    admin_user_id: string
    session_token: string
    refresh_token?: string | null
    ip_address?: string | null
    user_agent?: string | null
    device_fingerprint?: string | null
    is_active: boolean
    logout_reason?: string | null
    metadata?: Record<string, unknown>
    created_at: string
    last_activity: string
    expires_at: string
}

/**
 * Audit log entry - matches admin_audit_log table
 */
export interface AuditLogEntry {
    id: string
    admin_user_id?: string | null
    session_id?: string | null
    event_type: string
    event_category?: string | null
    action: string
    resource_type?: string | null
    resource_id?: string | null
    ip_address?: string | null
    user_agent?: string | null
    endpoint?: string | null
    http_method?: string | null
    details?: Record<string, unknown>
    changes?: Record<string, unknown>
    success: boolean
    error_message?: string | null
    timestamp: string
    duration_ms?: number | null
    severity?: string | null
}

/**
 * User activity entry
 */
export interface UserActivityEntry {
    id: string
    user_id: string
    action: string
    resource?: string
    ip_address?: string
    user_agent?: string
    timestamp: string
    metadata?: Record<string, unknown>
}

/**
 * Admin user list filters
 */
export interface AdminUserListFilters {
    role?: AdminRoleType | string
    is_active?: boolean
    status?: string
    department?: string
    search?: string
    page?: number
    size?: number
    limit?: number
    cursor?: string
}

/**
 * Audit log filters
 */
export interface AuditLogFilters {
    user_id?: string
    event_type?: string
    event_category?: string
    action?: string
    resource_type?: string
    success?: boolean
    start_date?: string
    end_date?: string
    search?: string
    page?: number
    size?: number
    limit?: number
    cursor?: string
}

/**
 * System health status
 */
export interface SystemHealth {
    status: 'healthy' | 'degraded' | 'down'
    components: Array<{
        name: string
        status: 'up' | 'down' | 'degraded'
        last_check: string
        details?: Record<string, unknown>
    }>
    timestamp: string
}

/**
 * System metrics
 */
export interface SystemMetrics {
    cpu_usage: number
    memory_usage: number
    disk_usage: number
    active_connections: number
    request_rate: number
    error_rate: number
    timestamp: string
}

/**
 * System statistics
 */
export interface SystemStats {
    system: {
        cpu_percent: number
        memory_percent: number
        disk_percent: number
        uptime_seconds: number
    }
    users: {
        total: number
        active_now: number
        by_role: Record<string, number>
    }
    security?: {
        failed_logins?: number
        active_sessions?: number
        blocked_ips?: number
    }
    database: {
        total_records: number
        total_patients: number
        total_users: number
        connections: number
    }
    timestamp: string
}
