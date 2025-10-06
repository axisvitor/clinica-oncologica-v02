/**
 * Authentication Types - Consolidated and optimized auth interfaces
 * Combines Supabase and API auth patterns with enhanced type safety
 */

import type { BaseEntity, BaseError, BaseEvent } from './shared'
import { UserRole } from './shared'
// Removed Supabase imports - now using Firebase exclusively

// ============================================================================
// CORE AUTH TYPES
// ============================================================================

/** Unified user interface combining all auth sources */
export interface User extends BaseEntity {
  readonly email: string
  readonly full_name: string
  readonly name?: string
  readonly role: UserRole
  readonly is_active: boolean
  readonly permissions: readonly string[]
  readonly avatar_url?: string
  readonly last_login?: string
  readonly metadata?: Record<string, unknown>
  
  // Optional fields for different auth sources
  readonly token?: string
  readonly access_token?: string
  readonly phone?: string
  readonly email_verified?: boolean
}

/** Authentication tokens */
export interface AuthTokens {
  readonly access_token: string
  readonly refresh_token: string
  readonly token_type: 'bearer'
  readonly expires_in: number
  readonly expires_at?: number
}

/** Login response */
export interface LoginResponse extends AuthTokens {
  readonly user: User
  readonly session?: any  // Generic session type (Firebase handles this)
}

/** Login credentials */
export interface LoginCredentials {
  readonly email: string
  readonly password: string
  readonly remember_me?: boolean
}

/** Registration data */
export interface RegisterData {
  readonly email: string
  readonly password: string
  readonly full_name: string
  readonly role?: UserRole
  readonly metadata?: Record<string, unknown>
}

// ============================================================================
// AUTH STATE MANAGEMENT
// ============================================================================

/** Complete authentication state */
export interface AuthState {
  readonly user: User | null
  readonly token: string | null
  readonly refreshToken: string | null
  readonly isAuthenticated: boolean
  readonly isLoading: boolean
  readonly sessionExpiry: number | null
  readonly lastActivity: number | null
  readonly preferSupabase: boolean
}

/** Session data and expiry information */
export interface SessionData {
  readonly expiry: number | null
  readonly isExpiring: boolean
  readonly timeToExpiry: number
  readonly lastRefresh: number | null
  readonly autoRefresh: boolean
}

/** Supabase-specific auth data (deprecated - kept for backward compatibility) */
export interface SupabaseAuthData {
  readonly user: any | null
  readonly session: any | null
  readonly loading: boolean
  readonly isAuthenticated: boolean
}

// ============================================================================
// PERMISSIONS & AUTHORIZATION
// ============================================================================

/** Permission configuration */
export interface PermissionConfig {
  readonly permissions: readonly string[]
  readonly role: UserRole
  readonly hierarchical_roles?: readonly UserRole[]
  readonly resource_permissions?: Record<string, readonly string[]>
}

/** Permission check result */
export interface PermissionResult {
  readonly hasPermission: boolean
  readonly reason?: string
  readonly level?: 'read' | 'write' | 'admin'
}

/** Resource access control */
export interface ResourceAccess {
  readonly resource: string
  readonly actions: readonly string[]
  readonly conditions?: Record<string, unknown>
}

/** Permission summary */
export interface PermissionSummary {
  readonly totalPermissions: number
  readonly directPermissions: readonly string[]
  readonly inheritedPermissions: readonly string[]
  readonly roleHierarchy: readonly UserRole[]
  readonly accessLevel: 'basic' | 'advanced' | 'admin' | 'super_admin'
}

// ============================================================================
// AUTH ERRORS & EVENTS
// ============================================================================

/** Authentication-specific error */
export interface AuthError extends BaseError {
  readonly code: AuthErrorCode
  readonly retryable: boolean
  readonly retryAfter?: number
  readonly context?: Record<string, unknown>
}

/** Auth error codes */
export enum AuthErrorCode {
  INVALID_CREDENTIALS = 'invalid_credentials',
  SESSION_EXPIRED = 'session_expired',
  TOKEN_INVALID = 'token_invalid',
  TOKEN_EXPIRED = 'token_expired',
  REFRESH_FAILED = 'refresh_failed',
  PERMISSION_DENIED = 'permission_denied',
  ACCOUNT_LOCKED = 'account_locked',
  ACCOUNT_DISABLED = 'account_disabled',
  RATE_LIMITED = 'rate_limited',
  NETWORK_ERROR = 'network_error',
  UNKNOWN_ERROR = 'unknown_error',
  MFA_REQUIRED = 'mfa_required',
  EMAIL_NOT_VERIFIED = 'email_not_verified',
  WEAK_PASSWORD = 'weak_password',
  USER_NOT_FOUND = 'user_not_found',
  EMAIL_ALREADY_EXISTS = 'email_already_exists'
}

/** Authentication events */
export enum AuthEventType {
  SIGNED_IN = 'signed_in',
  SIGNED_OUT = 'signed_out',
  TOKEN_REFRESHED = 'token_refreshed',
  SESSION_EXPIRED = 'session_expired',
  PERMISSION_CHANGED = 'permission_changed',
  PROFILE_UPDATED = 'profile_updated',
  PASSWORD_CHANGED = 'password_changed',
  EMAIL_VERIFIED = 'email_verified',
  MFA_ENABLED = 'mfa_enabled',
  MFA_DISABLED = 'mfa_disabled',
  RETRY_FAILED = 'retry_failed',
  SECURITY_ALERT = 'security_alert'
}

/** Auth event data */
export interface AuthEvent extends BaseEvent<unknown> {
  readonly type: AuthEventType
  readonly user?: User
  readonly error?: AuthError
  readonly metadata?: Record<string, unknown>
}

/** Auth event listener */
export type AuthEventListener = (event: AuthEvent) => void | Promise<void>

// ============================================================================
// RETRY & RECOVERY
// ============================================================================

/** Auth retry configuration */
export interface AuthRetryConfig {
  readonly maxRetries: number
  readonly retryDelay: number
  readonly exponentialBackoff: boolean
  readonly retryableErrors: readonly AuthErrorCode[]
  readonly jitterMs?: number
}

/** Auth retry state */
export interface AuthRetryState {
  readonly isRetrying: boolean
  readonly retryCount: number
  readonly lastError: AuthError | null
  readonly nextRetryAt: number | null
}

// ============================================================================
// HOOKS & CONFIGURATION
// ============================================================================

/** Main auth hook options */
export interface UseAuthOptions {
  readonly preferSupabase?: boolean
  readonly onAuthEvent?: AuthEventListener
  readonly autoConnectWebSocket?: boolean
  readonly persistTokens?: boolean
  readonly retryConfig?: Partial<AuthRetryConfig>
  readonly sessionTimeout?: number
  readonly refreshThreshold?: number
}

/** API auth hook options */
export interface UseApiAuthOptions {
  readonly autoConnectWebSocket?: boolean
  readonly persistTokens?: boolean
  readonly baseURL?: string
}

/** Supabase auth hook options */
export interface UseSupabaseAuthOptions {
  readonly autoRefresh?: boolean
  readonly persistSession?: boolean
  readonly detectSessionInUrl?: boolean
}

/** Session management options */
export interface UseSessionManagementOptions {
  readonly onRefreshNeeded?: () => Promise<void>
  readonly onSessionExpired?: () => void
  readonly autoRefresh?: boolean
  readonly refreshThreshold?: number
  readonly warningThreshold?: number
}

/** Permission hook options */
export interface UsePermissionsOptions {
  readonly user: User | null
  readonly refreshInterval?: number
  readonly enableCaching?: boolean
}

// ============================================================================
// AUTH HOOK RETURN TYPES
// ============================================================================

/** Main auth hook return type */
export interface UseAuthReturn {
  // User and auth state
  readonly user: User | null
  readonly token: string | null
  readonly refreshToken: string | null
  readonly isAuthenticated: boolean
  readonly isLoading: boolean
  readonly error: AuthError | null

  // Session data
  readonly sessionData: SessionData
  readonly isSessionExpiring: boolean

  // Auth methods
  readonly login: (email: string, password: string) => Promise<LoginResponse>
  readonly logout: () => Promise<void>
  readonly refreshAuth: () => Promise<LoginResponse>
  readonly signUp: (data: RegisterData) => Promise<void>
  readonly resetPassword: (email: string) => Promise<void>
  readonly updatePassword: (newPassword: string) => Promise<void>
  readonly restoreSession: () => Promise<boolean>
  readonly updateProfile: (data: Partial<User>) => Promise<User>

  // Permission methods
  readonly hasPermission: (permission: string) => boolean
  readonly hasRole: (role: UserRole) => boolean
  readonly hasAnyRole: (roles: UserRole[]) => boolean
  readonly hasAllPermissions: (permissions: string[]) => boolean
  readonly hasAnyPermission: (permissions: string[]) => boolean
  readonly isAdmin: () => boolean
  readonly isSuperAdmin: () => boolean
  readonly canAccessResource: (resource: string, action?: string) => PermissionResult
  readonly getPermissionLevel: (resource: string) => 'read' | 'write' | 'admin' | 'none'

  // Permission data
  readonly permissionConfig: PermissionConfig | null
  readonly permissionSummary: PermissionSummary | null

  // Retry state
  readonly isRetrying: boolean
  readonly retryCount: number
  readonly resetRetryState: () => void

  // Raw auth providers (for advanced use cases)
  readonly supabaseAuth: SupabaseAuthData
  readonly apiAuth: {
    readonly user: User | null
    readonly token: string | null
    readonly loading: boolean
    readonly error: AuthError | null
  }

  // Configuration
  readonly preferSupabase: boolean
}

/** API auth hook return type */
export interface UseApiAuthReturn {
  readonly user: User | null
  readonly token: string | null
  readonly refreshToken: string | null
  readonly loading: boolean
  readonly error: AuthError | null
  readonly isAuthenticated: boolean

  readonly login: (credentials: LoginCredentials) => Promise<LoginResponse>
  readonly logout: () => Promise<void>
  readonly refreshAuth: (refreshToken?: string) => Promise<LoginResponse>
  readonly loadUser: () => Promise<User>
  readonly restoreSession: () => Promise<boolean>

  readonly setAuthToken: (token: string | null) => void
  readonly clearTokens: () => void
  readonly storeTokens: (tokens: AuthTokens) => void
}

/** Supabase auth hook return type (deprecated - kept for backward compatibility) */
export interface UseSupabaseAuthReturn {
  readonly authData: SupabaseAuthData
  readonly user: any | null
  readonly session: any | null
  readonly loading: boolean
  readonly error: AuthError | null
  readonly isAuthenticated: boolean
  readonly accessToken: string | null
  readonly refreshToken: string | null

  readonly signIn: (email: string, password: string) => Promise<LoginResponse>
  readonly signUp: (email: string, password: string, metadata?: Record<string, unknown>) => Promise<void>
  readonly signOut: () => Promise<void>
  readonly refreshSession: () => Promise<void>
  readonly resetPassword: (email: string) => Promise<void>
  readonly updatePassword: (newPassword: string) => Promise<void>
  readonly convertToAppUser: (supabaseUser: any) => User
}

/** Session management hook return type */
export interface UseSessionManagementReturn {
  readonly sessionData: SessionData
  readonly isSessionExpiring: boolean
  readonly timeToExpiry: number
  readonly setupSession: (expiresIn: number) => void
  readonly clearSession: () => void
  readonly updateSessionFromTokens: (tokens: AuthTokens) => void
  readonly restoreSessionFromStorage: () => boolean
  readonly refreshSession: () => Promise<void>
}

/** Permissions hook return type */
export interface UsePermissionsReturn {
  readonly permissionConfig: PermissionConfig | null
  readonly permissionSummary: PermissionSummary | null
  readonly loading: boolean
  readonly error: Error | null

  readonly hasPermission: (permission: string) => boolean
  readonly hasRole: (role: UserRole) => boolean
  readonly hasAnyRole: (roles: UserRole[]) => boolean
  readonly hasAllPermissions: (permissions: string[]) => boolean
  readonly hasAnyPermission: (permissions: string[]) => boolean
  readonly isAdmin: () => boolean
  readonly isSuperAdmin: () => boolean
  readonly canAccessResource: (resource: string, action?: string) => PermissionResult
  readonly getPermissionLevel: (resource: string) => 'read' | 'write' | 'admin' | 'none'
  readonly refreshPermissions: () => Promise<void>
}

/** Auth retry hook return type */
export interface UseAuthRetryReturn {
  readonly isRetrying: boolean
  readonly retryCount: number
  readonly retryState: AuthRetryState
  readonly executeWithRetry: <T>(fn: () => Promise<T>, context?: string) => Promise<T>
  readonly createAuthError: (message: string, code: AuthErrorCode, retryable?: boolean) => AuthError
  readonly resetRetryState: () => void
}

// ============================================================================
// MFA (Multi-Factor Authentication)
// ============================================================================

/** MFA challenge types */
export enum MFAChallengeType {
  TOTP = 'totp',
  SMS = 'sms',
  EMAIL = 'email',
  PHONE = 'phone'
}

/** MFA challenge */
export interface MFAChallenge {
  readonly id: string
  readonly type: MFAChallengeType
  readonly created_at: string
  readonly expires_at: string
  readonly verified: boolean
}

/** MFA verification */
export interface MFAVerification {
  readonly challenge_id: string
  readonly code: string
  readonly remember_device?: boolean
}

// ============================================================================
// SECURITY & AUDIT
// ============================================================================

/** Security event types */
export enum SecurityEventType {
  LOGIN_SUCCESS = 'login_success',
  LOGIN_FAILED = 'login_failed',
  LOGOUT = 'logout',
  PASSWORD_CHANGED = 'password_changed',
  EMAIL_CHANGED = 'email_changed',
  MFA_ENABLED = 'mfa_enabled',
  MFA_DISABLED = 'mfa_disabled',
  SUSPICIOUS_ACTIVITY = 'suspicious_activity',
  ACCOUNT_LOCKED = 'account_locked',
  ACCOUNT_UNLOCKED = 'account_unlocked'
}

/** Security event */
export interface SecurityEvent extends BaseEntity {
  readonly user_id: string
  readonly event_type: SecurityEventType
  readonly ip_address?: string
  readonly user_agent?: string
  readonly location?: string
  readonly success: boolean
  readonly metadata?: Record<string, unknown>
}

/** Session info */
export interface SessionInfo {
  readonly id: string
  readonly user_id: string
  readonly ip_address: string
  readonly user_agent: string
  readonly location?: string
  readonly created_at: string
  readonly last_activity: string
  readonly expires_at: string
  readonly is_current: boolean
}

// ============================================================================
// CONSTANTS
// ============================================================================

/** Default auth retry configuration */
export const DEFAULT_AUTH_RETRY_CONFIG: AuthRetryConfig = {
  maxRetries: 3,
  retryDelay: 1000,
  exponentialBackoff: true,
  retryableErrors: [
    AuthErrorCode.NETWORK_ERROR,
    AuthErrorCode.TOKEN_EXPIRED,
    AuthErrorCode.REFRESH_FAILED
  ],
  jitterMs: 100
} as const

/** Token expiry warning thresholds */
export const TOKEN_EXPIRY_THRESHOLDS = {
  REFRESH_THRESHOLD: 5 * 60 * 1000, // 5 minutes
  WARNING_THRESHOLD: 2 * 60 * 1000,  // 2 minutes
  CRITICAL_THRESHOLD: 30 * 1000       // 30 seconds
} as const

/** Permission levels */
export const PERMISSION_LEVELS = {
  READ: ['read', 'view', 'list', 'get'],
  WRITE: ['write', 'create', 'update', 'modify', 'edit'],
  ADMIN: ['admin', 'delete', 'manage', 'configure']
} as const

/** Role hierarchy (higher index = more permissions) */
export const ROLE_HIERARCHY: readonly UserRole[] = [
  UserRole.ASSISTANT,
  UserRole.NURSE,
  UserRole.DOCTOR,
  UserRole.ADMIN,
  UserRole.SUPER_ADMIN
] as const