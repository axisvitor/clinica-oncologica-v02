// Import and re-export centralized types
import type { User as ApiUser, AuthTokens as ApiAuthTokens, LoginResponse as ApiLoginResponse } from '@/types/api'

export type User = ApiUser
export type AuthTokens = ApiAuthTokens
export type LoginResponse = ApiLoginResponse

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
  user: ApiUser | null
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