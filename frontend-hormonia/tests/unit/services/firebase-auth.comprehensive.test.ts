import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  loginUser,
  logoutUser,
  logoutAllDevices,
  getCurrentUser,
  checkSession,
  setupTokenRefresh,
  stopTokenRefresh
} from '@/services/firebase-auth'

// Mock dependencies
const mockFirebaseAuth = {
  signInWithPassword: vi.fn(),
  signOut: vi.fn(),
  getCurrentUser: vi.fn(),
  isConfigured: vi.fn().mockReturnValue(true)
}

const mockApiClient = {
  getBaseURL: vi.fn().mockReturnValue('https://api.example.com'),
  getCsrfToken: vi.fn().mockReturnValue('csrf-token'),
  fetchCsrfToken: vi.fn(),
  setAuthToken: vi.fn(),
  auth: {
    createSession: vi.fn(),
    me: vi.fn()
  }
}

const mockLogger = {
  log: vi.fn(),
  warn: vi.fn(),
  error: vi.fn()
}

// Mock modules
vi.mock('@/lib/firebase-client', () => ({
  firebaseAuth: mockFirebaseAuth
}))

vi.mock('@/lib/api-client', () => ({
  apiClient: mockApiClient
}))

vi.mock('@/lib/logger', () => ({
  createLogger: () => mockLogger
}))

// Mock global fetch
global.fetch = vi.fn()

// Mock window.navigator
Object.defineProperty(window, 'navigator', {
  value: {
    userAgent: 'test-user-agent'
  },
  writable: true
})

const mockFirebaseUser = {
  uid: 'firebase-uid',
  email: 'test@example.com',
  getIdToken: vi.fn().mockResolvedValue('firebase-token')
}

const mockAppUser = {
  id: 'user-id',
  email: 'test@example.com',
  full_name: 'Test User',
  role: 'admin',
  is_active: true,
  permissions: ['read:patients', 'write:patients'],
  created_at: '2023-01-01T00:00:00Z'
}

describe('Firebase Auth Service - Comprehensive Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.clearAllTimers()
    vi.useFakeTimers()

    // Setup default mocks
    mockApiClient.fetchCsrfToken.mockResolvedValue(undefined)
    mockApiClient.auth.createSession.mockResolvedValue({
      status: 'authenticated'
    })
    mockApiClient.auth.me.mockResolvedValue({
      data: mockAppUser
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.clearAllTimers()
    vi.useRealTimers()
    stopTokenRefresh()
  })

  describe('loginUser', () => {
    it('should successfully login with valid credentials', async () => {
      mockFirebaseAuth.signInWithPassword.mockResolvedValue({
        user: mockFirebaseUser,
        session: { access_token: 'session-token' },
        error: null
      })

      mockFirebaseAuth.getCurrentUser.mockResolvedValue(mockFirebaseUser)

      const result = await loginUser('test@example.com', 'password123')

      expect(result).toEqual({
        user: mockAppUser,
        session_id: 'cookie'
      })

      expect(mockFirebaseAuth.signInWithPassword).toHaveBeenCalledWith({
        email: 'test@example.com',
        password: 'password123'
      })

      expect(mockApiClient.auth.createSession).toHaveBeenCalledWith(
        'firebase-token',
        {
          user_agent: 'test-user-agent',
          timestamp: expect.any(String)
        }
      )
    })

    it('should validate API base URL before login', async () => {
      mockApiClient.getBaseURL.mockReturnValue('')

      await expect(loginUser('test@example.com', 'password123'))
        .rejects.toThrow('API not initialized. Please refresh the page and try again.')
    })

    it('should enforce HTTPS in production environment', async () => {
      // Mock HTTPS page
      Object.defineProperty(window, 'location', {
        value: { protocol: 'https:' },
        writable: true
      })

      mockApiClient.getBaseURL.mockReturnValue('http://api.example.com')

      await expect(loginUser('test@example.com', 'password123'))
        .rejects.toThrow('Security error: Cannot connect to insecure backend from secure page. Please contact support.')
    })

    it('should fetch CSRF token if not available', async () => {
      mockApiClient.getCsrfToken.mockReturnValue(null)
      mockApiClient.fetchCsrfToken.mockResolvedValue(undefined)

      mockFirebaseAuth.signInWithPassword.mockResolvedValue({
        user: mockFirebaseUser,
        session: { access_token: 'session-token' },
        error: null
      })

      mockFirebaseAuth.getCurrentUser.mockResolvedValue(mockFirebaseUser)

      await loginUser('test@example.com', 'password123')

      expect(mockApiClient.fetchCsrfToken).toHaveBeenCalled()
    })

    it('should handle CSRF token fetch failure', async () => {
      mockApiClient.getCsrfToken.mockReturnValue(null)
      mockApiClient.fetchCsrfToken.mockRejectedValue(new Error('CSRF fetch failed'))

      await expect(loginUser('test@example.com', 'password123'))
        .rejects.toThrow('Security validation failed. Please refresh the page and try again.')
    })

    it('should handle Firebase authentication failure', async () => {
      mockFirebaseAuth.signInWithPassword.mockResolvedValue({
        error: new Error('Invalid credentials'),
        user: null,
        session: null
      })

      await expect(loginUser('test@example.com', 'wrongpassword'))
        .rejects.toThrow('Invalid credentials')
    })

    it('should handle session creation failure with helpful error messages', async () => {
      mockFirebaseAuth.signInWithPassword.mockResolvedValue({
        user: mockFirebaseUser,
        session: { access_token: 'session-token' },
        error: null
      })

      mockApiClient.auth.createSession.mockRejectedValue(new Error('Failed to fetch'))

      await expect(loginUser('test@example.com', 'password123'))
        .rejects.toThrow('Cannot connect to server. Please check your internet connection and try again.')
    })

    it('should handle CORS errors with specific message', async () => {
      mockFirebaseAuth.signInWithPassword.mockResolvedValue({
        user: mockFirebaseUser,
        session: { access_token: 'session-token' },
        error: null
      })

      mockApiClient.auth.createSession.mockRejectedValue(new Error('CORS blocked'))

      await expect(loginUser('test@example.com', 'password123'))
        .rejects.toThrow('Security error: Connection blocked. Please contact support.')
    })

    it('should handle session status validation failure', async () => {
      mockFirebaseAuth.signInWithPassword.mockResolvedValue({
        user: mockFirebaseUser,
        session: { access_token: 'session-token' },
        error: null
      })

      mockApiClient.auth.createSession.mockResolvedValue({
        status: 'failed'
      })

      await expect(loginUser('test@example.com', 'password123'))
        .rejects.toThrow('Session creation failed - invalid status')
    })

    it('should handle user data fetch failure', async () => {
      mockFirebaseAuth.signInWithPassword.mockResolvedValue({
        user: mockFirebaseUser,
        session: { access_token: 'session-token' },
        error: null
      })

      mockFirebaseAuth.getCurrentUser.mockResolvedValue(mockFirebaseUser)
      mockApiClient.auth.me.mockResolvedValue(null)

      await expect(loginUser('test@example.com', 'password123'))
        .rejects.toThrow('Failed to fetch user data from backend')
    })

    it('should setup token refresh after successful login', async () => {
      mockFirebaseAuth.signInWithPassword.mockResolvedValue({
        user: mockFirebaseUser,
        session: { access_token: 'session-token' },
        error: null
      })

      mockFirebaseAuth.getCurrentUser.mockResolvedValue(mockFirebaseUser)

      await loginUser('test@example.com', 'password123')

      // Verify token refresh is set up (we'll test this in the token refresh section)
      expect(mockLogger.log).toHaveBeenCalledWith('Login successful, session created')
    })
  })

  describe('logoutUser', () => {
    it('should successfully logout and clear session', async () => {
      const mockFetch = vi.mocked(global.fetch)
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ message: 'Logged out successfully' })
      } as Response)

      await logoutUser()

      expect(mockFetch).toHaveBeenCalledWith(
        'https://api.example.com/api/v1/session/logout',
        {
          method: 'DELETE',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': 'csrf-token'
          }
        }
      )

      expect(mockFirebaseAuth.signOut).toHaveBeenCalled()
    })

    it('should handle backend logout failure gracefully', async () => {
      const mockFetch = vi.mocked(global.fetch)
      mockFetch.mockRejectedValue(new Error('Network error'))

      await logoutUser()

      expect(mockFirebaseAuth.signOut).toHaveBeenCalled()
      expect(mockLogger.warn).toHaveBeenCalledWith(
        'Backend logout request failed, continuing with cleanup:',
        expect.any(Error)
      )
    })

    it('should handle logout errors and force cleanup', async () => {
      mockFirebaseAuth.signOut.mockRejectedValue(new Error('Firebase error'))

      await expect(logoutUser()).rejects.toThrow('Firebase error')

      expect(mockLogger.error).toHaveBeenCalledWith('Logout failed:', expect.any(Error))
    })

    it('should clear token refresh interval on logout', async () => {
      // First setup token refresh
      setupTokenRefresh()

      const mockFetch = vi.mocked(global.fetch)
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ message: 'Logged out' })
      } as Response)

      await logoutUser()

      expect(mockLogger.log).toHaveBeenCalledWith('Logout successful')
    })
  })

  describe('logoutAllDevices', () => {
    it('should logout from all devices successfully', async () => {
      mockFirebaseAuth.getCurrentUser.mockResolvedValue(mockFirebaseUser)

      const mockFetch = vi.mocked(global.fetch)
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ sessions_deleted: 3 })
      } as Response)

      const result = await logoutAllDevices()

      expect(result).toEqual({ sessions_deleted: 3 })

      expect(mockFetch).toHaveBeenCalledWith(
        'https://api.example.com/api/v1/session/logout-all',
        {
          method: 'DELETE',
          credentials: 'include',
          headers: {
            'Authorization': 'Bearer firebase-token',
            'Content-Type': 'application/json',
            'X-CSRF-Token': 'csrf-token'
          }
        }
      )

      expect(mockFirebaseAuth.signOut).toHaveBeenCalled()
    })

    it('should handle no Firebase user gracefully', async () => {
      mockFirebaseAuth.getCurrentUser.mockResolvedValue(null)

      const result = await logoutAllDevices()

      expect(result).toEqual({ sessions_deleted: 1 })
      expect(mockLogger.warn).toHaveBeenCalledWith(
        'No Firebase user found, performing local logout only'
      )
    })

    it('should fallback to single logout on backend failure', async () => {
      mockFirebaseAuth.getCurrentUser.mockResolvedValue(mockFirebaseUser)

      const mockFetch = vi.mocked(global.fetch)
      mockFetch.mockResolvedValue({
        ok: false,
        status: 500
      } as Response)

      const result = await logoutAllDevices()

      expect(result).toEqual({ sessions_deleted: 1 })
      expect(mockLogger.warn).toHaveBeenCalledWith(
        'Backend logout-all failed, falling back to single session logout'
      )
    })

    it('should handle network errors gracefully', async () => {
      mockFirebaseAuth.getCurrentUser.mockResolvedValue(mockFirebaseUser)

      const mockFetch = vi.mocked(global.fetch)
      mockFetch.mockRejectedValue(new Error('Network error'))

      const result = await logoutAllDevices()

      expect(result).toEqual({ sessions_deleted: 1 })
      expect(mockLogger.error).toHaveBeenCalledWith(
        'Logout all request failed, falling back to single session logout:',
        expect.any(Error)
      )
    })
  })

  describe('getCurrentUser', () => {
    it('should return current user when authenticated', async () => {
      mockFirebaseAuth.getCurrentUser.mockResolvedValue(mockFirebaseUser)

      const user = await getCurrentUser()

      expect(user).toEqual({
        ...mockAppUser,
        session_id: 'cookie'
      })

      expect(mockApiClient.setAuthToken).toHaveBeenCalledWith('firebase-token')
      expect(mockApiClient.auth.me).toHaveBeenCalled()
    })

    it('should return null when no Firebase user', async () => {
      mockFirebaseAuth.getCurrentUser.mockResolvedValue(null)

      const user = await getCurrentUser()

      expect(user).toBe(null)
      expect(mockLogger.log).toHaveBeenCalledWith('No Firebase user, session cleared')
    })

    it('should return null when backend validation fails', async () => {
      mockFirebaseAuth.getCurrentUser.mockResolvedValue(mockFirebaseUser)
      mockApiClient.auth.me.mockResolvedValue(null)

      const user = await getCurrentUser()

      expect(user).toBe(null)
      expect(mockLogger.log).toHaveBeenCalledWith('Backend session invalid, clearing')
    })

    it('should handle errors gracefully', async () => {
      mockFirebaseAuth.getCurrentUser.mockRejectedValue(new Error('Firebase error'))

      const user = await getCurrentUser()

      expect(user).toBe(null)
      expect(mockLogger.error).toHaveBeenCalledWith(
        'Get current user failed:',
        expect.any(Error)
      )
    })
  })

  describe('checkSession', () => {
    it('should return true for valid session', async () => {
      mockFirebaseAuth.getCurrentUser.mockResolvedValue(mockFirebaseUser)

      const isValid = await checkSession()

      expect(isValid).toBe(true)
    })

    it('should return false for invalid session', async () => {
      mockFirebaseAuth.getCurrentUser.mockResolvedValue(null)

      const isValid = await checkSession()

      expect(isValid).toBe(false)
    })

    it('should return false on errors', async () => {
      mockFirebaseAuth.getCurrentUser.mockRejectedValue(new Error('Session check failed'))

      const isValid = await checkSession()

      expect(isValid).toBe(false)
      expect(mockLogger.error).toHaveBeenCalledWith(
        'Session check failed:',
        expect.any(Error)
      )
    })
  })

  describe('Token Refresh', () => {
    it('should setup automatic token refresh', () => {
      setupTokenRefresh()

      expect(mockLogger.log).toHaveBeenCalledWith(
        'Token refresh with validation scheduled every 55 minutes'
      )
    })

    it('should refresh token automatically', async () => {
      mockFirebaseAuth.getCurrentUser.mockResolvedValue(mockFirebaseUser)
      mockFirebaseUser.getIdToken.mockResolvedValue('new-firebase-token')

      setupTokenRefresh()

      // Fast-forward 55 minutes
      vi.advanceTimersByTime(55 * 60 * 1000)

      await vi.runAllTimersAsync()

      expect(mockFirebaseUser.getIdToken).toHaveBeenCalledWith(true)
      expect(mockApiClient.setAuthToken).toHaveBeenCalledWith('new-firebase-token')
      expect(mockApiClient.auth.me).toHaveBeenCalled()
    })

    it('should validate token with backend after refresh', async () => {
      mockFirebaseAuth.getCurrentUser.mockResolvedValue(mockFirebaseUser)
      mockFirebaseUser.getIdToken.mockResolvedValue('new-firebase-token')

      setupTokenRefresh()

      vi.advanceTimersByTime(55 * 60 * 1000)
      await vi.runAllTimersAsync()

      expect(mockApiClient.auth.me).toHaveBeenCalled()
      expect(mockLogger.log).toHaveBeenCalledWith(
        'Backend validation successful after token refresh'
      )
    })

    it('should force logout on validation failure', async () => {
      mockFirebaseAuth.getCurrentUser.mockResolvedValue(mockFirebaseUser)
      mockFirebaseUser.getIdToken.mockResolvedValue('new-firebase-token')
      mockApiClient.auth.me.mockRejectedValue(new Error('Validation failed'))

      // Mock window.location
      delete (window as any).location
      window.location = { href: '' } as any

      setupTokenRefresh()

      vi.advanceTimersByTime(55 * 60 * 1000)
      await vi.runAllTimersAsync()

      expect(mockLogger.error).toHaveBeenCalledWith(
        'Token validation failed, forcing logout:',
        expect.any(Error)
      )
      expect(window.location.href).toBe('/login?session_invalid=true')
    })

    it('should force logout on inactive account', async () => {
      mockFirebaseAuth.getCurrentUser.mockResolvedValue(mockFirebaseUser)
      mockFirebaseUser.getIdToken.mockResolvedValue('new-firebase-token')
      mockApiClient.auth.me.mockResolvedValue({
        data: { ...mockAppUser, is_active: false }
      })

      delete (window as any).location
      window.location = { href: '' } as any

      setupTokenRefresh()

      vi.advanceTimersByTime(55 * 60 * 1000)
      await vi.runAllTimersAsync()

      expect(mockLogger.error).toHaveBeenCalledWith(
        'Account deactivated - forcing logout'
      )
      expect(window.location.href).toBe('/login?session_invalid=true')
    })

    it('should clear interval when no Firebase user', async () => {
      mockFirebaseAuth.getCurrentUser.mockResolvedValue(null)

      setupTokenRefresh()

      vi.advanceTimersByTime(55 * 60 * 1000)
      await vi.runAllTimersAsync()

      expect(mockLogger.warn).toHaveBeenCalledWith(
        'No Firebase user for token refresh'
      )
    })

    it('should stop token refresh', () => {
      setupTokenRefresh()
      stopTokenRefresh()

      expect(mockLogger.log).toHaveBeenCalledWith('Token refresh stopped')
    })

    it('should handle token refresh errors gracefully', async () => {
      mockFirebaseAuth.getCurrentUser.mockRejectedValue(new Error('Firebase error'))

      setupTokenRefresh()

      vi.advanceTimersByTime(55 * 60 * 1000)
      await vi.runAllTimersAsync()

      expect(mockLogger.error).toHaveBeenCalledWith(
        'Token refresh failed:',
        expect.any(Error)
      )
    })

    it('should clear existing interval before setting new one', () => {
      setupTokenRefresh()
      setupTokenRefresh() // Call again

      expect(mockLogger.log).toHaveBeenCalledWith(
        'Token refresh with validation scheduled every 55 minutes'
      )
    })
  })

  describe('Error Handling Edge Cases', () => {
    it('should handle malformed session response', async () => {
      mockFirebaseAuth.signInWithPassword.mockResolvedValue({
        user: mockFirebaseUser,
        session: { access_token: 'session-token' },
        error: null
      })

      mockApiClient.auth.createSession.mockResolvedValue(undefined)

      await expect(loginUser('test@example.com', 'password123'))
        .rejects.toThrow('Session creation failed - invalid status')
    })

    it('should handle network timeouts gracefully', async () => {
      mockFirebaseAuth.signInWithPassword.mockResolvedValue({
        user: mockFirebaseUser,
        session: { access_token: 'session-token' },
        error: null
      })

      mockApiClient.auth.createSession.mockImplementation(
        () => new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), 100))
      )

      await expect(loginUser('test@example.com', 'password123'))
        .rejects.toThrow('timeout')
    })
  })
})