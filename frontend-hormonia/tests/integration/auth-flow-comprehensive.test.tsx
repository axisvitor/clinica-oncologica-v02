/**
 * Authentication API integration tests for the Firebase session flow.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { apiClient } from '@/lib/api-client'

const mockFetch = vi.fn()
global.fetch = mockFetch

const setCsrfToken = (token: string | null) => {
  ;(apiClient as any).csrfToken = token
  ;(apiClient as any).csrfTokenPromise = null
}

const createMockResponse = (data: unknown, status = 200, ok = true) => ({
  ok,
  status,
  headers: { get: () => null },
  json: async () => data
})

describe('Authentication API (Firebase-based)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiClient.setBaseURL('http://localhost:8000')
    apiClient.setAuthToken(null)
    setCsrfToken('csrf-token')
  })

  afterEach(() => {
    setCsrfToken(null)
  })

  it('creates a session from a Firebase token', async () => {
    const mockResponse = {
      valid: true,
      session_id: 'session-123',
      message: 'Login successful'
    }

    mockFetch.mockResolvedValueOnce(createMockResponse(mockResponse))

    const result = await apiClient.auth.createSession('firebase-token-123')

    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/v2/auth/firebase/verify',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ id_token: 'firebase-token-123' })
      })
    )
    expect(result.valid).toBe(true)
    expect(result.session_id).toBe('session-123')
    expect(apiClient.getAuthToken()).toBe('session-123')
  })

  it('gets current user from a valid session', async () => {
    const mockSessionResponse = {
      user: {
        id: 'user-123',
        email: 'test@example.com',
        full_name: 'Test User',
        role: 'doctor',
        permissions: ['patient:read'],
        is_active: true,
        created_at: '2024-01-01T00:00:00Z'
      },
      session: {
        last_activity: '2024-01-15T10:00:00Z'
      },
      session_id: 'session-123'
    }

    mockFetch.mockResolvedValueOnce(createMockResponse(mockSessionResponse))

    const user = await apiClient.auth.getCurrentUser()

    expect(user.id).toBe('user-123')
    expect(user.email).toBe('test@example.com')
    expect(user.role).toBe('doctor')
  })

  it('returns unauthenticated when session is invalid', async () => {
    mockFetch.mockResolvedValueOnce(createMockResponse({ detail: 'Unauthorized' }, 401, false))

    const result = await apiClient.auth.checkAuth()

    expect(result.authenticated).toBe(false)
    expect(result.user).toBeUndefined()
  })

  it('throws when current user is missing', async () => {
    mockFetch.mockResolvedValueOnce(createMockResponse({ detail: 'Unauthorized' }, 401, false))

    await expect(apiClient.auth.getCurrentUser()).rejects.toThrow('Not authenticated')
  })

  it('logs out and clears auth token', async () => {
    apiClient.setAuthToken('session-123')

    mockFetch.mockResolvedValueOnce(createMockResponse({
      success: true,
      sessions_deleted: 1,
      message: 'Logged out successfully'
    }))

    const result = await apiClient.auth.logout()

    expect(result.success).toBe(true)
    expect(apiClient.getAuthToken()).toBeNull()
  })

  it('invalidates all sessions and clears auth token', async () => {
    apiClient.setAuthToken('session-123')

    mockFetch.mockResolvedValueOnce(createMockResponse({
      success: true,
      sessions_deleted: 2,
      message: 'Logged out from all devices'
    }))

    const result = await apiClient.auth.invalidateAllSessions()

    expect(result.sessions_deleted).toBe(2)
    expect(apiClient.getAuthToken()).toBeNull()
  })

  it('rejects unsupported auth methods', async () => {
    const unsupportedCalls = [
      () => apiClient.auth.login({ email: 'test@example.com', password: 'password' }),
      () => apiClient.auth.register({ email: 'test@example.com', password: 'password', name: 'Test' }),
      () => apiClient.auth.requestPasswordReset({ email: 'test@example.com' }),
      () => apiClient.auth.confirmPasswordReset({ token: 'token', new_password: 'password' }),
      () => apiClient.auth.changePassword({ old_password: 'old', new_password: 'new' }),
      () => apiClient.auth.refreshToken('refresh-token'),
      () => apiClient.auth.verifyEmail('token'),
      () => apiClient.auth.resendVerificationEmail(),
      () => apiClient.auth.updateProfile({ full_name: 'Test User' } as any)
    ]

    for (const call of unsupportedCalls) {
      await expect(call()).rejects.toThrow(/not supported/i)
    }
  })
})
