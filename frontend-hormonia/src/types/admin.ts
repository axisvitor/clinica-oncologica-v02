import { UserRole } from './shared'

export interface AdminUser {
  id: string
  email: string
  full_name: string
  role: UserRole | 'doctor' | 'admin' | 'nurse' | 'patient' | 'researcher' | 'coordinator' | 'super_admin'
  is_active: boolean
  permissions: string[]
  created_at: string
  updated_at: string
  last_login: string | null
  login_count: number
  two_factor_enabled: boolean
  failed_login_attempts: number
  locked_until: string | null
  password?: string  // Optional for password updates
}

export interface LoginAttempt {
  id: string
  email: string
  ip_address: string
  user_agent: string
  success: boolean
  timestamp: string
  failure_reason?: string
}

export interface AuditLogEntry {
  id: string
  user_id: string
  user_email: string
  action: string
  resource: string
  resource_id?: string
  details: Record<string, any>
  ip_address: string
  user_agent: string
  timestamp: string
}

export interface SystemSettings {
  ai_enabled: boolean
  auto_reply: boolean
  maintenance_mode: boolean
  debug_mode: boolean
  session_timeout: number
  max_failed_logins: number
  account_lockout_duration: number
  password_policy: {
    min_length: number
    require_uppercase: boolean
    require_lowercase: boolean
    require_numbers: boolean
    require_symbols: boolean
  }
}

export interface SecurityMetrics {
  total_users: number
  active_sessions: number
  failed_logins_24h: number
  blocked_ips: number
  last_backup: string | null
  system_uptime: number
}

export interface TwoFactorSetup {
  secret: string
  qr_code_url: string
  backup_codes: string[]
}

export interface PasswordStrength {
  score: 0 | 1 | 2 | 3 | 4
  feedback: string[]
  suggestions: string[]
  isValid: boolean
}

export interface SessionWarning {
  type: 'expiring' | 'expired' | 'concurrent'
  message: string
  timeRemaining?: number
  action?: 'extend' | 'logout'
}

export interface AdminDashboardStats {
  users: {
    total: number
    active: number
    locked: number
    new_today: number
  }
  security: {
    failed_logins: number
    active_sessions: number
    blocked_ips: number
  }
  system: {
    uptime: number
    memory_usage: number
    cpu_usage: number
    disk_usage: number
  }
  audit: {
    total_logs: number
    critical_events: number
    warnings: number
  }
}

// Authentication Types
export interface AdminLoginCredentials {
  email: string
  password: string
  twoFactorCode?: string
  rememberMe?: boolean
}

export interface AdminLoginResponse {
  success: boolean
  user?: AdminUser
  token?: string
  refreshToken?: string
  requiresTwoFactor?: boolean
  error?: string
}

export interface AdminAuthState {
  user: AdminUser | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  sessionExpiry: Date | null
}

export interface AdminSession {
  id: string
  user_id: string
  token: string
  refresh_token: string
  expires_at: string
  created_at: string
  ip_address: string
  user_agent: string
  is_active: boolean
}

// API Response Types
export interface AdminApiResponse<T = any> {
  success: boolean
  data?: T
  error?: string
  message?: string
  status?: number
}

// Paginated Response for Admin components
export interface AdminPaginatedData<T = any> {
  items: T[]
  total: number
  pages: number
  current_page: number
  page_size: number
  // Also support standard format
  data?: T[]
  page?: number
  size?: number
  limit?: number
  has_more?: boolean
}

export interface AdminPaginatedResponse<T = any> {
  success: boolean
  data: T[]
  pagination: {
    page: number
    limit: number
    total: number
    totalPages: number
  }
  error?: string
}

// Form Validation Types
export interface AdminFormError {
  field: string
  message: string
}

export interface AdminFormValidation {
  isValid: boolean
  errors: AdminFormError[]
}

// Route Protection Types
export interface AdminRoute {
  path: string
  component: React.ComponentType
  requiredPermissions?: string[]
  requiresTwoFactor?: boolean
}

export interface AdminNavItem {
  id: string
  label: string
  path: string
  icon?: string
  requiredPermissions?: string[]
  children?: AdminNavItem[]
}

// Activity Monitoring Types
export interface AdminUserActivity {
  id: string
  user_id: string
  user_email?: string  // Optional to support existing data
  action: string
  resource: string
  resource_id?: string  // Added missing property (aliased as resource in some components)
  details: Record<string, any>
  timestamp: string
  ip_address: string
  user_agent: string
  session_id: string
}

export interface AdminActivityFilter {
  userId?: string
  action?: string
  resource?: string
  dateFrom?: Date
  dateTo?: Date
  ipAddress?: string
}

// Toast/Notification Types
export interface AdminNotification {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  title: string
  message: string
  duration?: number
  action?: {
    label: string
    onClick: () => void
  }
}

// Error Types
export interface AdminError extends Error {
  code?: string
  statusCode?: number
  details?: Record<string, any>
}

export class AdminAuthError extends Error {
  constructor(
    message: string,
    public code: string = 'AUTH_ERROR',
    public statusCode: number = 401
  ) {
    super(message)
    this.name = 'AdminAuthError'
  }
}

export class AdminSessionExpiredError extends AdminAuthError {
  constructor() {
    super('Session has expired', 'SESSION_EXPIRED', 401)
    this.name = 'AdminSessionExpiredError'
  }
}

export class AdminPermissionError extends AdminAuthError {
  constructor(action: string) {
    super(`Insufficient permissions for action: ${action}`, 'PERMISSION_DENIED', 403)
    this.name = 'AdminPermissionError'
  }
}