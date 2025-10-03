// Main authentication hook
export { useAuth } from '../useAuth'

// Specialized authentication hooks
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