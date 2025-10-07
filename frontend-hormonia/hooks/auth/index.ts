// Main authentication hook
export { useAuth } from '../useAuth'

// Specialized authentication hooks
/**
 * @deprecated Supabase auth is deprecated after migration to Firebase + AWS RDS (2025-10-07)
 * Use useApiAuth (Firebase) instead. This hook is kept for backward compatibility only.
 */
export { useSupabaseAuth } from './useSupabaseAuth'
export { useApiAuth } from './useApiAuth'
export { useSessionManagement } from './useSessionManagement'
export { usePermissions } from './usePermissions'
export { useAuthRetry } from './useAuthRetry'

// Types
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
  AuthEventType,
  AuthEvent,
  AuthEventListener
} from './types'

// Re-export for convenience
export type { User as SupabaseUser, Session as SupabaseSession } from '@supabase/supabase-js'