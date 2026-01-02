import { UserRole, AuthProvider } from './rbac'

/**
 * Complete Admin User interface matching backend User model
 * Backend: app/models/user.py User class
 * Backend Schema: app/schemas/admin_users.py UserResponse
 */
export interface AdminUser {
  // Core fields from backend User model
  id: string
  email: string
  full_name: string | null
  role: UserRole // ONLY 'admin' or 'doctor'
  is_active: boolean

  // Firebase authentication fields
  firebase_uid: string | null
  auth_provider: AuthProvider
  firebase_last_sign_in: string | null
  firebase_created_at: string | null
  firebase_email_verified: boolean
  firebase_display_name: string | null
  firebase_photo_url: string | null
  firebase_custom_claims: Record<string, unknown>
  last_firebase_sync: string | null

  // Account security fields
  failed_login_attempts: number
  is_locked: boolean
  locked_until: string | null
  force_change_password: boolean
  last_password_change: string | null
  two_factor_enabled?: boolean // Added to fix TS2339 errors

  // Timestamps
  created_at: string
  updated_at: string

  // Computed/Additional fields from UserResponse schema
  total_patients?: number
  last_login: string | null

  // Frontend-only fields for RBAC UI
  permissions: string[] // Permission enum values as strings

  // Optional for password operations
  password?: string
  phone_number?: string | null
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
  details: Record<string, unknown>
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
export interface AdminApiResponse<T = unknown> {
  success: boolean
  data?: T
  error?: string
  message?: string
  status?: number
}

// Paginated Response for Admin components
export interface AdminPaginatedData<T = unknown> {
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

export interface AdminPaginatedResponse<T = unknown> {
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
  details: Record<string, unknown>
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
  details?: Record<string, unknown>
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

// ============================================================================
// USER SCHEMAS - Matches backend Pydantic schemas
// ============================================================================

/**
 * User creation request
 * Backend: app/schemas/admin_users.py UserCreate
 */
export interface UserCreateRequest {
  name: string // min 2, max 255
  email: string // EmailStr
  password: string // min 8, max 128
  role?: UserRole // defaults to DOCTOR
  phone_number?: string | null // max 20
}

/**
 * User update request
 * Backend: app/schemas/admin_users.py UserUpdate
 */
export interface UserUpdateRequest {
  name?: string | null
  email?: string | null
  role?: UserRole | null
  phone_number?: string | null
  is_active?: boolean | null
  two_factor_enabled?: boolean | null
  password?: string // For password updates
}

/**
 * Role update request
 * Backend: app/schemas/admin_users.py RoleUpdate
 */
export interface RoleUpdateRequest {
  role: UserRole
}

/**
 * Permissions update request
 * Backend: app/schemas/admin_users.py PermissionsUpdate
 */
export interface PermissionsUpdateRequest {
  permissions: string[] // Permission enum values
}

/**
 * Password reset request
 * Backend: app/schemas/admin_users.py PasswordReset
 */
export interface PasswordResetRequest {
  new_password: string // min 8, max 128
}

/**
 * User filter parameters
 * Backend: app/schemas/admin_users.py UserFilter
 */
export interface UserFilterParams {
  name?: string | null
  email?: string | null
  role?: UserRole | null
  is_active?: boolean | null
  phone_number?: string | null
  created_after?: string | null // ISO datetime
  created_before?: string | null // ISO datetime
  has_patients?: boolean | null
}

/**
 * User statistics response
 * Backend: app/schemas/admin_users.py UserStatsResponse
 */
export interface UserStatsResponse {
  total_users: number
  active_users: number
  inactive_users: number
  users_by_role: Record<string, number>
  recent_registrations: number
  recent_logins: number
}

/**
 * User activity response
 * Backend: app/schemas/admin_users.py UserActivityResponse
 */
export interface UserActivityResponse {
  user_id: string
  last_login: string | null
  login_count: number
  last_activity: string | null
  active_sessions: number
}

/**
 * Bulk user operation request
 * Backend: app/schemas/admin_users.py BulkUserOperation
 */
export interface BulkUserOperationRequest {
  user_ids: string[] // min 1, max 100
  operation: 'activate' | 'deactivate' | 'delete'
}

/**
 * Bulk operation result
 * Backend: app/schemas/admin_users.py BulkOperationResult
 */
export interface BulkOperationResult {
  successful: string[]
  failed: Array<{
    user_id: string
    error: string
  }>
  total_processed: number
}

// ============================================================================
// RBAC Types - Import from rbac.ts
// ============================================================================

// Re-export RBAC types for convenience
export { UserRole, Permission, AuthProvider, SecurityLevel } from './rbac'
export type {
  RoleDefinition,
  PermissionResource,
  PermissionAction,
  PermissionCheckRequest,
  PermissionCheckResponse,
  RoleAssignmentRequest,
  RoleAssignmentResponse,
  RoleAssignmentValidation
} from './rbac'

// ============================================================================
// Admin Dashboard Extended Types
// ============================================================================

/**
 * Extended admin dashboard statistics
 */
export interface ExtendedAdminDashboardStats extends AdminDashboardStats {
  roles: {
    total: number
    system_roles: number
    custom_roles: number
  }
  permissions: {
    total: number
    active_grants: number
    expired_grants: number
  }
  rbac: {
    users_with_roles: number
    users_without_roles: number
    average_permissions_per_user: number
  }
}

// ============================================================================
// Patient Data Types (Frontend Representation)
// ============================================================================

/**
 * Patient flow state enumeration
 * Must match backend FlowState enum
 */
export type PatientFlowState =
  | 'onboarding'
  | 'active'
  | 'paused'
  | 'completed'
  | 'cancelled'

/**
 * Complete Patient interface with all fields
 * Matches backend Patient model exactly
 */
export interface Patient {
  id: string
  doctor_id: string // UUID as string
  phone: string
  name: string
  email: string | null
  birth_date: string | null
  treatment_type: string | null
  treatment_start_date: string | null
  flow_state: PatientFlowState // ADDED: Missing field
  current_day: number
  cpf: string | null
  diagnosis: string | null
  treatment_phase: string | null
  doctor_notes: string | null
  patient_data: Record<string, unknown> | null // Renamed from metadata
  created_at: string
  updated_at: string
  deleted_at?: string | null
}

/**
 * Patient creation request
 */
export interface PatientCreateRequest {
  phone: string
  name: string
  email?: string
  birth_date?: string
  treatment_type?: string
  treatment_start_date?: string
  cpf?: string
  diagnosis?: string
  treatment_phase?: string
  doctor_notes?: string
  patient_data?: Record<string, unknown>
}

/**
 * Patient update request
 */
export interface PatientUpdateRequest {
  phone?: string
  name?: string
  email?: string | null
  birth_date?: string | null
  treatment_type?: string | null
  treatment_start_date?: string | null
  flow_state?: PatientFlowState
  current_day?: number
  cpf?: string | null
  diagnosis?: string | null
  treatment_phase?: string | null
  doctor_notes?: string | null
  patient_data?: Record<string, unknown> | null
}

// ============================================================================
// Quiz Types (Frontend Representation)
// ============================================================================

/**
 * Quiz response value type
 * Backend uses Union[str, int, float, bool, List, Dict]
 */
export type QuizResponseValue =
  | string
  | number
  | boolean
  | Array<string | number | boolean>
  | Record<string, unknown>

/**
 * Quiz question response
 */
export interface QuizQuestionResponse {
  question_id: string
  question_text: string
  response_value: QuizResponseValue // FIXED: Union type instead of any
  response_type: 'text' | 'number' | 'boolean' | 'choice' | 'multi_choice' | 'scale'
  answered_at: string
}

/**
 * Quiz session
 */
export interface QuizSession {
  id: string
  patient_id: string
  quiz_template_id: string
  started_at: string
  completed_at: string | null
  responses: QuizQuestionResponse[]
  score?: number
  is_complete: boolean
}

// ============================================================================
// Admin Configuration Types
// ============================================================================

/**
 * System configuration
 */
export interface SystemConfiguration {
  id: string
  key: string
  value: string | number | boolean | Record<string, unknown> | unknown[]
  value_type: 'string' | 'number' | 'boolean' | 'json'
  description: string
  is_public: boolean
  updated_by: string
  updated_at: string
}

/**
 * Feature flags
 */
export interface FeatureFlag {
  id: string
  name: string
  key: string
  enabled: boolean
  description: string
  rollout_percentage: number
  target_users?: string[]
  created_at: string
  updated_at: string
}