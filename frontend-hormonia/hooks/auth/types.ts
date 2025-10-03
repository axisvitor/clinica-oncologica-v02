/**
 * Legacy Auth Types - Deprecated, use types from /types/auth.ts instead
 * @deprecated Import from '/types/auth' for the latest type definitions
 */

// Re-export types from the centralized auth types module
export type {
  User,
  AuthTokens,
  LoginResponse,
  SupabaseAuthData,
  SessionData,
  PermissionConfig,
  AuthState,
  AuthRetryConfig,
  AuthError,
  AuthEvent,
  AuthEventListener
} from '../../types/auth'

export {
  AuthErrorCode,
  AuthEventType
} from '../../types/auth'

// Legacy type aliases for backward compatibility
export type { AuthEventType as AuthEventTypeLegacy } from '../../types/auth'