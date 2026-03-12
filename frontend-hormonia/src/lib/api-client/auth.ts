/**
 * Authentication API Module
 *
 * Handles all authentication-related API calls:
 * - Login/Logout
 * - Registration
 * - Password management
 * - User profile
 * - Session management
 */

import type { ApiClientCore } from './core'
import { ApiError } from './core'
import { normalizeUser } from './normalizers'
import type { BackendUser, FrontendUser } from './normalizers'

export interface LoginCredentials {
  email: string
  password: string
  remember_me?: boolean
}

export interface RegisterData {
  email: string
  password: string
  name: string
  role?: string
}

/**
 * User type - uses FrontendUser from normalizers
 * This ensures consistent typing across the application
 */
export type User = FrontendUser

export interface SessionValidationResponse {
  valid: boolean
  user?: {
    id: string
    email: string
    full_name?: string
    name?: string
    role?: string
    permissions?: string[]
    is_active?: boolean
    created_at?: string
    updated_at?: string
  }
  session_data?: Record<string, unknown>
}

interface LogoutResponse {
  success: boolean
  sessions_deleted: number
  message: string
}

export interface AuthResponse {
  valid: boolean
  message: string
  session_id: string
  user_id: string
  expires_at: string
  remember_me: boolean
  user: User
  access_token?: string
  refresh_token?: string
  expires_in?: number
}

export interface PasswordResetRequest {
  email: string
}

export interface PasswordResetConfirm {
  token: string
  new_password: string
}

export interface PasswordResetResponse {
  success?: boolean
  message: string
}

export interface PasswordChange {
  old_password: string
  new_password: string
}

export interface AuthDiagnostics {
  message: string
  error?: string
  request_id?: string
  status?: number
  data?: Record<string, unknown>
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const pickString = (value: unknown): string | undefined =>
  typeof value === 'string' && value.trim().length > 0 ? value : undefined

const extractAuthDiagnostics = (
  payload: unknown,
  fallbackMessage: string,
  status?: number
): AuthDiagnostics => {
  const record = isRecord(payload) ? payload : {}
  const nestedError = isRecord(record['error']) ? record['error'] : null

  const errorCode =
    pickString(record['error']) ??
    pickString(nestedError?.['code']) ??
    pickString(record['code']) ??
    undefined

  const requestId = pickString(record['request_id']) ?? pickString(record['requestId']) ?? undefined

  const message =
    pickString(record['message']) ??
    pickString(record['detail']) ??
    pickString(record['user_message']) ??
    pickString(nestedError?.['message']) ??
    pickString(nestedError?.['details']) ??
    fallbackMessage

  const data: Record<string, unknown> = {
    ...(record || {}),
    ...(errorCode ? { error: errorCode } : {}),
    ...(requestId ? { request_id: requestId } : {}),
    message,
  }

  return {
    message,
    error: errorCode,
    request_id: requestId,
    status,
    data,
  }
}

const normalizeApiError = (error: unknown, fallbackMessage: string): ApiError => {
  if (error instanceof ApiError) {
    const diagnostics = extractAuthDiagnostics(
      error.data,
      error.userFriendlyMessage || error.message || fallbackMessage,
      error.status
    )

    return new ApiError(error.status, diagnostics.data ?? error.data, diagnostics.message, diagnostics.message)
  }

  const diagnostics = extractAuthDiagnostics(undefined, fallbackMessage)
  return new ApiError(0, diagnostics.data ?? {}, diagnostics.message, diagnostics.message)
}

export function toUserSafeAuthError(
  error: unknown,
  fallbackMessage = 'Authentication request failed.'
): Error & {
  status?: number
  data?: Record<string, unknown>
  request_id?: string
  error?: string
} {
  const apiError = normalizeApiError(error, fallbackMessage)
  const diagnostics = extractAuthDiagnostics(apiError.data, apiError.message, apiError.status)
  const safeError = new Error(diagnostics.message) as Error & {
    status?: number
    data?: Record<string, unknown>
    request_id?: string
    error?: string
  }

  safeError.name = 'AuthError'
  safeError.status = diagnostics.status
  safeError.data = diagnostics.data
  safeError.request_id = diagnostics.request_id
  safeError.error = diagnostics.error

  return safeError
}

/**
 * Authentication API methods
 */
export function createAuthApi(client: ApiClientCore) {
  /**
   * Maps session user data to normalized User object
   * Uses normalizeUser from normalizers module for consistent field mapping
   */
  const mapSessionUser = (sessionUser?: SessionValidationResponse['user']): User => {
    if (!sessionUser || !sessionUser.id || !sessionUser.email) {
      throw new Error('Invalid session user payload')
    }

    // Convert to BackendUser shape then normalize
    const backendUser: BackendUser = {
      id: sessionUser.id,
      email: sessionUser.email,
      full_name: sessionUser.full_name ?? sessionUser.name,
      name: sessionUser.name,
      role: sessionUser.role ?? 'doctor',
      permissions: sessionUser.permissions ?? [],
      is_active: sessionUser.is_active ?? true,
      created_at: sessionUser.created_at ?? new Date().toISOString(),
      updated_at: sessionUser.updated_at,
    }

    return normalizeUser(backendUser)
  }

  const fetchSession = async (): Promise<SessionValidationResponse & { session_id?: string }> => {
    const baseURL = client.getBaseURL()

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }

    const token = client.getAuthToken()
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
      headers['X-Session-ID'] = token
    }

    const response = await fetch(`${baseURL}/api/v2/auth/verify-session`, {
      method: 'GET',
      credentials: 'include',
      headers,
    })

    if (!response.ok) {
      return { valid: false }
    }

    const data = await response.json()
    return {
      valid: true,
      user: data.user,
      session_data: data.session,
      session_id: data.session_id,
    }
  }

  const unsupported = (method: string): never => {
    throw new Error(`${method} is not supported in the first-party session authentication flow`)
  }

  return {
    login: async (credentials: LoginCredentials): Promise<AuthResponse> => {
      try {
        const response = await client.post<AuthResponse, LoginCredentials>('/api/v2/auth/login', {
          email: credentials.email,
          password: credentials.password,
          remember_me: Boolean(credentials.remember_me),
        })

        if (response.session_id) {
          client.setAuthToken(response.session_id)
        }

        return {
          ...response,
          user: mapSessionUser(response.user),
          access_token: response.access_token ?? response.session_id,
        }
      } catch (error) {
        throw normalizeApiError(error, 'Unable to complete login.')
      }
    },

    register: async (_data: RegisterData): Promise<AuthResponse> => unsupported('register'),

    requestPasswordReset: async (data: PasswordResetRequest): Promise<PasswordResetResponse> => {
      try {
        return await client.post<PasswordResetResponse, PasswordResetRequest>(
          '/api/v2/auth/password/reset-request',
          data
        )
      } catch (error) {
        throw normalizeApiError(error, 'Unable to request password reset.')
      }
    },

    confirmPasswordReset: async (data: PasswordResetConfirm): Promise<PasswordResetResponse> => {
      try {
        return await client.post<PasswordResetResponse, PasswordResetConfirm>(
          '/api/v2/auth/password/reset-confirm',
          data
        )
      } catch (error) {
        throw normalizeApiError(error, 'Unable to reset password.')
      }
    },

    changePassword: async (_data: PasswordChange): Promise<{ message: string }> =>
      unsupported('changePassword'),
    refreshToken: async (_refreshToken: string): Promise<AuthResponse> => unsupported('refreshToken'),
    verifyEmail: async (_token: string): Promise<{ message: string }> => unsupported('verifyEmail'),
    resendVerificationEmail: async (): Promise<{ message: string }> =>
      unsupported('resendVerificationEmail'),

    logout: async (): Promise<LogoutResponse> => {
      const response = await client.delete<LogoutResponse>('/api/v2/auth/logout')
      client.setAuthToken(null)
      return response
    },

    getCurrentUser: async (): Promise<User> => {
      const session = await fetchSession()
      if (!session.valid || !session.user) {
        throw new Error('Not authenticated')
      }
      return mapSessionUser(session.user)
    },

    updateProfile: async (_data: Partial<User>): Promise<User> => unsupported('updateProfile'),

    checkAuth: async (): Promise<{ authenticated: boolean; user?: User; sessionId?: string }> => {
      const session = await fetchSession()
      if (session.valid && session.user) {
        const sessionId = session.session_id
        return {
          authenticated: true,
          user: mapSessionUser(session.user),
          sessionId,
        }
      }
      return { authenticated: false }
    },

    getSession: async (): Promise<SessionValidationResponse> => {
      return fetchSession()
    },

    invalidateAllSessions: async (): Promise<LogoutResponse> => {
      const response = await client.delete<LogoutResponse>('/api/v2/auth/logout-all')
      client.setAuthToken(null)
      return response
    },

    createSession: async (
      firebaseToken: string,
      _deviceInfo?: { user_agent?: string; timestamp?: string }
    ): Promise<{
      valid: boolean
      session_id?: string
      message?: string
    }> => {
      const response = await client.post<{
        valid: boolean
        session_id?: string
        message?: string
        user?: User
      }>('/api/v2/auth/firebase/verify', {
        id_token: firebaseToken,
      })

      if (response.valid && response.session_id) {
        client.setAuthToken(response.session_id)
      }

      return response
    },

    me: async (): Promise<{ data: User | null; session?: Record<string, unknown> | undefined }> => {
      const session = await fetchSession()
      if (!session.valid || !session.user) {
        return { data: null, session: session.session_data }
      }
      return {
        data: mapSessionUser(session.user),
        session: session.session_data,
      }
    },
  }
}

// Export types
export type AuthApi = ReturnType<typeof createAuthApi>
