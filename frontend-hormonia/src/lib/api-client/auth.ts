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
import { normalizeUser } from './normalizers'
import type { BackendUser, FrontendUser } from './normalizers'

export interface LoginCredentials {
  email: string
  password: string
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
  user: User
  access_token: string
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

export interface PasswordChange {
  old_password: string
  new_password: string
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

  const fetchSession = async (): Promise<SessionValidationResponse> => {
    return client.get<SessionValidationResponse>('/api/v2/auth/verify-session')
  }

  const unsupported = (method: string): never => {
    throw new Error(`${method} is not supported in the Firebase-based authentication flow`)
  }

  return {
    login: async (_credentials: LoginCredentials): Promise<AuthResponse> =>
      unsupported('login'),
    register: async (_data: RegisterData): Promise<AuthResponse> =>
      unsupported('register'),
    requestPasswordReset: async (_data: PasswordResetRequest): Promise<{ message: string }> =>
      unsupported('requestPasswordReset'),
    confirmPasswordReset: async (_data: PasswordResetConfirm): Promise<{ message: string }> =>
      unsupported('confirmPasswordReset'),
    changePassword: async (_data: PasswordChange): Promise<{ message: string }> =>
      unsupported('changePassword'),
    refreshToken: async (_refreshToken: string): Promise<AuthResponse> =>
      unsupported('refreshToken'),
    verifyEmail: async (_token: string): Promise<{ message: string }> =>
      unsupported('verifyEmail'),
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

    updateProfile: async (_data: Partial<User>): Promise<User> =>
      unsupported('updateProfile'),

    checkAuth: async (): Promise<{ authenticated: boolean; user?: User }> => {
      const session = await fetchSession()
      if (session.valid && session.user) {
        return { authenticated: true, user: mapSessionUser(session.user) }
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
      deviceInfo?: { user_agent?: string; timestamp?: string }
    ): Promise<{
      status: string
      expires_at: string
      user: {
        id: string
        email: string
        full_name: string
        role: string
        is_active: boolean
      }
    }> => {
      // Map to backend expected payload
      return client.post('/api/v2/auth/firebase/verify', {
        id_token: firebaseToken
      })
    },

    me: async (): Promise<{ data: User | null; session?: Record<string, unknown> | undefined }> => {
      const session = await fetchSession()
      if (!session.valid || !session.user) {
        return { data: null, session: session.session_data }
      }
      return {
        data: mapSessionUser(session.user),
        session: session.session_data
      }
    },
  }
}

// Export types
export type AuthApi = ReturnType<typeof createAuthApi>
