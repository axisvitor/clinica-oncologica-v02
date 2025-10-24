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

export interface User {
  id: string
  email: string
  full_name: string
  role: string
  is_active: boolean
  permissions: string[]
  created_at: string
  name?: string
  updated_at?: string
  firebase_uid?: string
  session_id?: string
  token?: string
  avatar_url?: string
}

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
  session_data?: Record<string, any>
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
  const mapSessionUser = (sessionUser?: SessionValidationResponse['user']): User => {
    if (!sessionUser || !sessionUser.id || !sessionUser.email) {
      throw new Error('Invalid session user payload')
    }

    const displayName = sessionUser.full_name ?? sessionUser.name ?? sessionUser.email

    const user: User = {
      id: sessionUser.id,
      email: sessionUser.email,
      name: displayName,
      full_name: sessionUser.full_name ?? sessionUser.name ?? displayName,
      role: sessionUser.role ?? 'doctor',
      permissions: sessionUser.permissions ?? [],
      is_active: sessionUser.is_active ?? true,
      created_at: sessionUser.created_at ?? new Date().toISOString(),
    }
    if (sessionUser.updated_at) user.updated_at = sessionUser.updated_at
    return user
  }

  const fetchSession = async (): Promise<SessionValidationResponse> => {
    return client.get<SessionValidationResponse>('/session/validate')
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
      const response = await client.delete<LogoutResponse>('/session/logout')
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
      const response = await client.delete<LogoutResponse>('/session/logout-all')
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
      return client.post('/session', {
        firebase_token: firebaseToken,
        device_info: deviceInfo
      })
    },

    me: async (): Promise<{ data: User | null; session?: Record<string, any> | undefined }> => {
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
