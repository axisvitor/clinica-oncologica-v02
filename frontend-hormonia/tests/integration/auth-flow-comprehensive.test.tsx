/**
 * Comprehensive Authentication Flow Integration Tests
 *
 * Tests the complete authentication flow including:
 * - Firebase token verification
 * - Session management
 * - User profile access
 * - Logout and session cleanup
 * - Error scenarios
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { apiClient } from '@/lib/api-client'
import { AuthProvider } from '@/contexts/AuthContext'

// Mock Firebase
vi.mock('@/lib/firebase-client', () => ({
  auth: {
    signInWithEmailAndPassword: vi.fn(),
    signOut: vi.fn(),
    onAuthStateChanged: vi.fn()
  },
  getIdToken: vi.fn()
}))

describe('Authentication Flow Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Clear any existing auth state
    apiClient.setAuthToken(null)
    localStorage.clear()
    sessionStorage.clear()
  })

  afterEach(() => {
    vi.resetAllMocks()
  })

  describe('Complete Login Flow', () => {
    it('should complete full login flow from credentials to authenticated state', async () => {
      const mockFirebaseUser = {
        uid: 'firebase-uid-123',
        email: 'doctor@example.com',
        displayName: 'Dr. Test',
        emailVerified: true
      }

      const mockFirebaseToken = 'mock-firebase-id-token-xyz'

      const mockBackendResponse = {
        valid: true,
        user: {
          id: '123e4567-e89b-12d3-a456-426614174000',
          email: 'doctor@example.com',
          full_name: 'Dr. Test',
          role: 'doctor',
          is_active: true,
          firebase_uid: 'firebase-uid-123',
          firebase_email_verified: true
        },
        session_id: 'session-abc-123',
        message: 'Authentication successful'
      }

      // Step 1: Mock Firebase login
      const { signInWithEmailAndPassword, getIdToken } = await import('@/lib/firebase-client')
      vi.mocked(signInWithEmailAndPassword).mockResolvedValue({
        user: mockFirebaseUser
      } as any)
      vi.mocked(getIdToken).mockResolvedValue(mockFirebaseToken)

      // Step 2: Mock backend token verification
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => mockBackendResponse
      })

      // Step 3: Perform login
      const credentials = {
        email: 'doctor@example.com',
        password: 'SecurePassword123!'
      }

      const result = await apiClient.auth.login(credentials)

      // Step 4: Verify Firebase was called
      expect(signInWithEmailAndPassword).toHaveBeenCalledWith(
        expect.anything(),
        credentials.email,
        credentials.password
      )

      // Step 5: Verify backend was called with Firebase token
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/auth/firebase/verify'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ id_token: mockFirebaseToken })
        })
      )

      // Step 6: Verify response structure
      expect(result).toMatchObject({
        user: {
          id: mockBackendResponse.user.id,
          email: mockBackendResponse.user.email,
          role: mockBackendResponse.user.role
        },
        session_id: mockBackendResponse.session_id
      })

      // Step 7: Verify session is stored
      expect(sessionStorage.getItem('session_id')).toBe(mockBackendResponse.session_id)
    })

    it('should handle login with expired Firebase token', async () => {
      const { signInWithEmailAndPassword, getIdToken } = await import('@/lib/firebase-client')

      vi.mocked(signInWithEmailAndPassword).mockResolvedValue({
        user: { uid: 'test-uid' }
      } as any)

      vi.mocked(getIdToken).mockResolvedValue('expired-token')

      // Mock backend rejecting expired token
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 401,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          detail: 'Invalid Firebase token'
        })
      })

      await expect(
        apiClient.auth.login({
          email: 'test@example.com',
          password: 'password'
        })
      ).rejects.toThrow('Invalid Firebase token')
    })

    it('should handle network errors during login', async () => {
      const { signInWithEmailAndPassword, getIdToken } = await import('@/lib/firebase-client')

      vi.mocked(signInWithEmailAndPassword).mockResolvedValue({
        user: { uid: 'test-uid' }
      } as any)

      vi.mocked(getIdToken).mockResolvedValue('valid-token')

      // Mock network error
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))

      await expect(
        apiClient.auth.login({
          email: 'test@example.com',
          password: 'password'
        })
      ).rejects.toThrow()
    })

    it('should handle invalid credentials', async () => {
      const { signInWithEmailAndPassword } = await import('@/lib/firebase-client')

      vi.mocked(signInWithEmailAndPassword).mockRejectedValueOnce(
        new Error('auth/invalid-credential')
      )

      await expect(
        apiClient.auth.login({
          email: 'wrong@example.com',
          password: 'wrongpassword'
        })
      ).rejects.toThrow('auth/invalid-credential')
    })
  })

  describe('Session Management', () => {
    it('should verify and maintain active session', async () => {
      const mockSession = {
        session_id: 'session-123',
        user_id: 'user-123',
        created_at: new Date().toISOString(),
        expires_at: new Date(Date.now() + 8 * 60 * 60 * 1000).toISOString(),
        is_current: true
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => mockSession
      })

      const result = await apiClient.auth.verifySession()

      expect(result).toMatchObject({
        session_id: mockSession.session_id,
        user_id: mockSession.user_id
      })

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/auth/verify-session'),
        expect.objectContaining({
          method: 'POST'
        })
      )
    })

    it('should handle expired session', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 401,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          detail: 'Session expired'
        })
      })

      await expect(apiClient.auth.verifySession()).rejects.toThrow('Session expired')
    })

    it('should list all active sessions', async () => {
      const mockSessions = {
        sessions: [
          {
            session_id: 'session-1',
            user_id: 'user-123',
            ip_address: '192.168.1.1',
            user_agent: 'Mozilla/5.0...',
            is_current: true,
            created_at: new Date().toISOString()
          },
          {
            session_id: 'session-2',
            user_id: 'user-123',
            ip_address: '10.0.0.1',
            user_agent: 'Mobile Browser',
            is_current: false,
            created_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()
          }
        ],
        total: 2
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => mockSessions
      })

      const result = await apiClient.auth.listSessions()

      expect(result.sessions).toHaveLength(2)
      expect(result.sessions[0].is_current).toBe(true)
      expect(result.total).toBe(2)
    })

    it('should revoke a specific session', async () => {
      const sessionId = 'session-to-revoke'

      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          session_id: sessionId,
          revoked: true,
          message: 'Session revoked successfully'
        })
      })

      const result = await apiClient.auth.revokeSession(sessionId)

      expect(result.revoked).toBe(true)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/auth/sessions/${sessionId}`),
        expect.objectContaining({
          method: 'DELETE'
        })
      )
    })
  })

  describe('User Profile Access', () => {
    it('should fetch current user profile', async () => {
      const mockUser = {
        id: '123e4567-e89b-12d3-a456-426614174000',
        email: 'doctor@example.com',
        full_name: 'Dr. Test',
        role: 'doctor',
        is_active: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        preferences: {
          language: 'pt-BR',
          theme: 'light',
          timezone: 'America/Sao_Paulo'
        },
        patient_count: 15,
        notification_count: 3
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => mockUser
      })

      const result = await apiClient.auth.getCurrentUser()

      expect(result).toMatchObject({
        id: mockUser.id,
        email: mockUser.email,
        role: mockUser.role
      })

      expect(result.preferences).toBeDefined()
      expect(result.patient_count).toBe(15)
    })

    it('should fetch user profile with field selection', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          id: 'user-123',
          email: 'doctor@example.com',
          full_name: 'Dr. Test'
        })
      })

      const result = await apiClient.auth.getCurrentUser({
        fields: ['id', 'email', 'full_name']
      })

      expect(result).toHaveProperty('id')
      expect(result).toHaveProperty('email')
      expect(result).toHaveProperty('full_name')
      expect(result).not.toHaveProperty('preferences')
    })

    it('should handle unauthorized access to profile', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 401,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          detail: 'Not authenticated'
        })
      })

      await expect(apiClient.auth.getCurrentUser()).rejects.toThrow()
    })
  })

  describe('Logout Flow', () => {
    it('should complete full logout flow', async () => {
      const { signOut } = await import('@/lib/firebase-client')

      // Setup: User is logged in
      sessionStorage.setItem('session_id', 'active-session-123')
      apiClient.setAuthToken('auth-token-123')

      // Mock Firebase logout
      vi.mocked(signOut).mockResolvedValue(undefined)

      // Mock backend session cleanup
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          message: 'Logged out successfully'
        })
      })

      await apiClient.auth.logout()

      // Verify Firebase logout was called
      expect(signOut).toHaveBeenCalled()

      // Verify session was cleared
      expect(sessionStorage.getItem('session_id')).toBeNull()

      // Verify auth token was cleared
      // This would need to be verified through the next API call
    })

    it('should handle logout when already logged out', async () => {
      const { signOut } = await import('@/lib/firebase-client')

      vi.mocked(signOut).mockResolvedValue(undefined)

      // No active session
      expect(sessionStorage.getItem('session_id')).toBeNull()

      await apiClient.auth.logout()

      expect(signOut).toHaveBeenCalled()
    })

    it('should handle Firebase logout errors gracefully', async () => {
      const { signOut } = await import('@/lib/firebase-client')

      vi.mocked(signOut).mockRejectedValue(new Error('Firebase error'))

      // Should still clear local state even if Firebase fails
      sessionStorage.setItem('session_id', 'session-123')

      await apiClient.auth.logout()

      expect(sessionStorage.getItem('session_id')).toBeNull()
    })
  })

  describe('User Preferences', () => {
    it('should fetch user preferences', async () => {
      const mockPreferences = {
        user_id: 'user-123',
        preferences: {
          language: 'pt-BR',
          theme: 'dark',
          timezone: 'America/Sao_Paulo',
          notification_email: true,
          notification_sms: false,
          notification_whatsapp: true
        },
        updated_at: new Date().toISOString()
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => mockPreferences
      })

      const result = await apiClient.auth.getPreferences()

      expect(result.preferences.language).toBe('pt-BR')
      expect(result.preferences.theme).toBe('dark')
    })

    it('should update user preferences (full update)', async () => {
      const newPreferences = {
        language: 'en-US',
        theme: 'dark',
        timezone: 'America/New_York',
        notification_email: false,
        notification_sms: true,
        notification_whatsapp: true
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          user_id: 'user-123',
          preferences: newPreferences,
          updated_at: new Date().toISOString()
        })
      })

      const result = await apiClient.auth.updatePreferences(newPreferences)

      expect(result.preferences.language).toBe('en-US')
      expect(result.preferences.theme).toBe('dark')

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/auth/preferences'),
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify(newPreferences)
        })
      )
    })

    it('should partially update preferences', async () => {
      const partialUpdate = {
        theme: 'dark'
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          user_id: 'user-123',
          preferences: {
            language: 'pt-BR', // unchanged
            theme: 'dark', // updated
            timezone: 'America/Sao_Paulo' // unchanged
          },
          updated_at: new Date().toISOString()
        })
      })

      const result = await apiClient.auth.patchPreferences(partialUpdate)

      expect(result.preferences.theme).toBe('dark')

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/auth/preferences'),
        expect.objectContaining({
          method: 'PATCH'
        })
      )
    })
  })

  describe('Notifications', () => {
    it('should fetch user notifications', async () => {
      const mockNotifications = {
        data: [
          {
            id: 'notif-1',
            title: 'New Patient',
            message: 'A new patient was added',
            type: 'info',
            read: false,
            created_at: new Date().toISOString()
          },
          {
            id: 'notif-2',
            title: 'Appointment Reminder',
            message: 'You have an appointment tomorrow',
            type: 'warning',
            read: true,
            created_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()
          }
        ],
        total: 2,
        unread_count: 1,
        has_more: false
      }

      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => mockNotifications
      })

      const result = await apiClient.auth.getNotifications()

      expect(result.data).toHaveLength(2)
      expect(result.unread_count).toBe(1)
      expect(result.data[0].read).toBe(false)
    })

    it('should filter unread notifications', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          data: [
            { id: 'notif-1', read: false },
            { id: 'notif-2', read: false }
          ],
          total: 2,
          unread_count: 2
        })
      })

      const result = await apiClient.auth.getNotifications({ unread_only: true })

      expect(result.data.every(n => !n.read)).toBe(true)

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('unread_only=true'),
        expect.anything()
      )
    })

    it('should mark notifications as read', async () => {
      const notificationIds = ['notif-1', 'notif-2', 'notif-3']

      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          marked_count: 3,
          success: true
        })
      })

      const result = await apiClient.auth.markNotificationsRead(notificationIds)

      expect(result.marked_count).toBe(3)
      expect(result.success).toBe(true)

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/auth/notifications/mark-read'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ notification_ids: notificationIds })
        })
      )
    })

    it('should get unread notification count', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          count: 5
        })
      })

      const result = await apiClient.auth.getUnreadCount()

      expect(result.count).toBe(5)
    })
  })

  describe('Error Recovery', () => {
    it('should retry on network timeout', async () => {
      global.fetch = vi.fn()
        .mockRejectedValueOnce(new Error('Network timeout'))
        .mockRejectedValueOnce(new Error('Network timeout'))
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ success: true })
        })

      const result = await apiClient.auth.getCurrentUser()

      expect(global.fetch).toHaveBeenCalledTimes(3)
      expect(result).toBeDefined()
    })

    it('should not retry on 4xx errors', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 400,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          detail: 'Bad request'
        })
      })

      await expect(apiClient.auth.getCurrentUser()).rejects.toThrow()

      // Should not retry 4xx errors
      expect(global.fetch).toHaveBeenCalledTimes(1)
    })

    it('should handle rate limiting with backoff', async () => {
      global.fetch = vi.fn()
        .mockResolvedValueOnce({
          ok: false,
          status: 429,
          headers: new Headers({
            'content-type': 'application/json',
            'retry-after': '2'
          }),
          json: async () => ({
            detail: 'Too many requests'
          })
        })
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ success: true })
        })

      const result = await apiClient.auth.getCurrentUser()

      expect(global.fetch).toHaveBeenCalledTimes(2)
      expect(result).toBeDefined()
    })
  })

  describe('Concurrent Operations', () => {
    it('should handle multiple concurrent API calls', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ success: true })
      })

      const promises = [
        apiClient.auth.getCurrentUser(),
        apiClient.auth.getPreferences(),
        apiClient.auth.getNotifications(),
        apiClient.auth.listSessions()
      ]

      const results = await Promise.allSettled(promises)

      expect(results.every(r => r.status === 'fulfilled')).toBe(true)
      expect(global.fetch).toHaveBeenCalledTimes(4)
    })

    it('should handle race conditions gracefully', async () => {
      // Simulate race condition where session is revoked during operation
      let callCount = 0
      global.fetch = vi.fn().mockImplementation(() => {
        callCount++
        if (callCount === 2) {
          // Second call fails (session revoked)
          return Promise.resolve({
            ok: false,
            status: 401,
            headers: new Headers({ 'content-type': 'application/json' }),
            json: async () => ({ detail: 'Session expired' })
          })
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ success: true })
        })
      })

      const promises = [
        apiClient.auth.getCurrentUser(),
        apiClient.auth.getPreferences(),
        apiClient.auth.getNotifications()
      ]

      const results = await Promise.allSettled(promises)

      const fulfilled = results.filter(r => r.status === 'fulfilled')
      const rejected = results.filter(r => r.status === 'rejected')

      expect(fulfilled.length).toBeGreaterThan(0)
      expect(rejected.length).toBeGreaterThan(0)
    })
  })
})
