export interface User {
  id: string
  email: string
  full_name: string
  role: string
  is_active: boolean
  permissions: string[]
  token?: string  // Token property for WebSocket usage and API auth
  avatar_url?: string  // Add avatar_url property for profile picture
  created_at: string
}

export interface AuthTokens {
  access_token: string
  refresh_token?: string
  expires_in?: number
}

export interface LoginResponse extends AuthTokens {
  user: User
}

export interface SupabaseAuthData {
  user: any | null  // Removed Supabase dependency
  session: any | null  // Removed Supabase dependency
  loading: boolean
}

export interface SessionData {
  expiry: number | null
  isExpiring: boolean
  timeToExpiry: number
}

export interface PermissionConfig {
  permissions: string[]
  role: string
}

export interface AuthState {
  user: User | null
  token: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  isLoading: boolean
  sessionExpiry: number | null
}

export interface AuthRetryConfig {
  maxRetries: number
  retryDelay: number
  exponentialBackoff: boolean
}

export interface AuthError extends Error {
  code?: string
  retryable?: boolean
  retryAfter?: number
}

export type AuthEventType = 'SIGNED_IN' | 'SIGNED_OUT' | 'TOKEN_REFRESHED' | 'SESSION_EXPIRED' | 'RETRY_FAILED'

export interface AuthEvent {
  type: AuthEventType
  data?: any
  error?: AuthError
}

export type AuthEventListener = (event: AuthEvent) => void