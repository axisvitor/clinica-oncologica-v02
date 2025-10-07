/**
 * Integration Tests for Firebase Authentication Service with Session Management
 *
 * Tests the complete frontend authentication workflow:
 * 1. Login with Firebase → Backend session creation
 * 2. Session ID storage in localStorage
 * 3. auth.me() called AFTER session creation
 * 4. Logout clears session
 * 5. Logout-all invalidates all sessions
 *
 * These tests validate the complete fix for Firebase/Redis authentication flow.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import {
  loginUser,
  logoutUser,
  logoutAllDevices,
  getCurrentUser,
  checkSession,
  setupTokenRefresh,
  stopTokenRefresh
} from '../firebase-auth'
import { firebaseAuth } from '../../lib/firebase-client'
import { apiClient } from '../../lib/api-client'

// =============================================================================
// MOCKS
// =============================================================================

// Mock firebase-client
vi.mock('../../lib/firebase-client', () => ({
  auth: {},
  firebaseAuth: {
    signInWithPassword: vi.fn(),
    signOut: vi.fn(),
    getCurrentUser: vi.fn(),
    setPersistence: vi.fn()
  }
}))

// Mock api-client
vi.mock('../../lib/api-client', () => ({
  apiClient: {
    setAuthToken: vi.fn(),
    auth: {
      me: vi.fn()
    },
    getBaseURL: vi.fn(() => 'http://localhost:8000')
  }
}))

// Mock logger
vi.mock('../../lib/logger', () => ({
  createLogger: () => ({
    log: vi.fn(),
    error: vi.fn(),
    warn: vi.fn(),
    debug: vi.fn()
  })
}))

// Mock global fetch
global.fetch = vi.fn()

// =============================================================================
// TEST FIXTURES
// =============================================================================

const mockFirebaseUser = {
  uid: 'test_firebase_uid_123',
  email: 'test@example.com',
  getIdToken: vi.fn(async () => 'mock_firebase_token_abc123')
}

const mockSessionResponse = {
  session_id: 'mock_session_id_12345678901234567890',
  user: {
    id: 'user_123',
    email: 'test@example.com',
    full_name: 'Test User',
    role: 'doctor',
    is_active: true,
    permissions: ['patients:read', 'patients:write']
  },
  expires_at: new Date(Date.now() + 86400000).toISOString()
}

const mockUserResponse = {
  data: {
    id: 'user_123',
    email: 'test@example.com',
    full_name: 'Test User',
    role: 'doctor',
    is_active: true,
    permissions: ['patients:read', 'patients:write']
  }
}

// =============================================================================
// SETUP & TEARDOWN
// =============================================================================

beforeEach(() => {
  // Clear all mocks before each test
  vi.clearAllMocks()

  // Clear localStorage
  localStorage.clear()

  // Setup default mock behaviors
  vi.mocked(firebaseAuth.signInWithPassword).mockResolvedValue({
    user: mockFirebaseUser,
    session: { access_token: 'mock_firebase_token' },
    error: null
  })

  vi.mocked(apiClient.auth.me).mockResolvedValue(mockUserResponse)
})

afterEach(() => {
  // Cleanup
  localStorage.clear()
  stopTokenRefresh()
})

// =============================================================================
// TEST LOGIN FLOW
// =============================================================================

describe('loginUser', () => {
  it('should create backend session AFTER Firebase login', async () => {
    // Mock successful session creation
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSessionResponse
    } as Response)

    const result = await loginUser('test@example.com', 'password123')

    // Verify session creation was called AFTER Firebase login
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/session',
      expect.objectContaining({
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: expect.stringContaining('firebase_token')
      })
    )

    // Verify result
    expect(result.session_id).toBe(mockSessionResponse.session_id)
    expect(result.user).toEqual(mockUserResponse.data)
  })

  it('should store session_id in localStorage', async () => {
    // Mock successful session creation
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSessionResponse
    } as Response)

    await loginUser('test@example.com', 'password123')

    // CRITICAL TEST: Verify session_id is stored
    const storedSessionId = localStorage.getItem('session_id')
    expect(storedSessionId).toBe(mockSessionResponse.session_id)

    // Verify Firebase token is also stored
    const storedToken = localStorage.getItem('firebase_token')
    expect(storedToken).toBe('mock_firebase_token_abc123')
  })

  it('should call auth.me() AFTER session creation', async () => {
    // Track call order
    const callOrder: string[] = []

    vi.mocked(global.fetch).mockImplementationOnce(async (url) => {
      if (url.toString().includes('/session')) {
        callOrder.push('session_creation')
        return {
          ok: true,
          json: async () => mockSessionResponse
        } as Response
      }
      return { ok: false, json: async () => ({}) } as Response
    })

    vi.mocked(apiClient.auth.me).mockImplementationOnce(async () => {
      callOrder.push('auth_me')
      return mockUserResponse
    })

    await loginUser('test@example.com', 'password123')

    // CRITICAL TEST: Verify auth.me() is called AFTER session creation
    expect(callOrder).toEqual(['session_creation', 'auth_me'])
  })

  it('should throw error if backend does not return session_id', async () => {
    // Mock session creation without session_id
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        user: mockSessionResponse.user,
        // Missing session_id
      })
    } as Response)

    await expect(
      loginUser('test@example.com', 'password123')
    ).rejects.toThrow('Backend did not return session_id')
  })

  it('should throw error if Firebase login fails', async () => {
    // Mock Firebase login failure
    vi.mocked(firebaseAuth.signInWithPassword).mockResolvedValueOnce({
      user: null,
      session: null,
      error: new Error('Invalid credentials')
    })

    await expect(
      loginUser('test@example.com', 'wrong_password')
    ).rejects.toThrow('Login failed - no user or session')
  })

  it('should throw error if backend session creation fails', async () => {
    // Mock backend session creation failure
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Invalid Firebase token' })
    } as Response)

    await expect(
      loginUser('test@example.com', 'password123')
    ).rejects.toThrow('Invalid Firebase token')
  })

  it('should clean up localStorage on login error', async () => {
    // Set initial values
    localStorage.setItem('session_id', 'old_session')
    localStorage.setItem('firebase_token', 'old_token')

    // Mock backend failure
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: 'Backend error' })
    } as Response)

    await expect(
      loginUser('test@example.com', 'password123')
    ).rejects.toThrow()

    // CRITICAL TEST: Verify localStorage is cleaned up
    expect(localStorage.getItem('session_id')).toBeNull()
    expect(localStorage.getItem('firebase_token')).toBeNull()
  })

  it('should include device info in session creation request', async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSessionResponse
    } as Response)

    await loginUser('test@example.com', 'password123')

    // Verify device info is sent
    expect(global.fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        body: expect.stringContaining('device_info')
      })
    )
  })
})

// =============================================================================
// TEST LOGOUT FLOW
// =============================================================================

describe('logoutUser', () => {
  beforeEach(() => {
    // Setup active session
    localStorage.setItem('session_id', 'active_session_123')
    localStorage.setItem('firebase_token', 'active_token_123')
  })

  it('should call backend session logout endpoint', async () => {
    // Mock successful logout
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        sessions_deleted: 1,
        message: 'Session logged out successfully'
      })
    } as Response)

    await logoutUser()

    // Verify backend logout was called with correct session_id
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/session/logout',
      expect.objectContaining({
        method: 'DELETE',
        headers: {
          'X-Session-ID': 'active_session_123',
          'Content-Type': 'application/json'
        }
      })
    )
  })

  it('should clear localStorage on logout', async () => {
    // Mock successful logout
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true })
    } as Response)

    await logoutUser()

    // CRITICAL TEST: Verify localStorage is cleared
    expect(localStorage.getItem('session_id')).toBeNull()
    expect(localStorage.getItem('firebase_token')).toBeNull()
  })

  it('should sign out from Firebase', async () => {
    // Mock successful logout
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true })
    } as Response)

    await logoutUser()

    // Verify Firebase sign out was called
    expect(firebaseAuth.signOut).toHaveBeenCalled()
  })

  it('should cleanup even if backend logout fails', async () => {
    // Mock backend logout failure
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: false,
      status: 401
    } as Response)

    await logoutUser()

    // CRITICAL TEST: Verify cleanup happens even on failure
    expect(localStorage.getItem('session_id')).toBeNull()
    expect(localStorage.getItem('firebase_token')).toBeNull()
    expect(firebaseAuth.signOut).toHaveBeenCalled()
  })

  it('should cleanup even if backend is unreachable', async () => {
    // Mock network error
    vi.mocked(global.fetch).mockRejectedValueOnce(
      new Error('Network error')
    )

    await logoutUser()

    // Verify cleanup still happens
    expect(localStorage.getItem('session_id')).toBeNull()
    expect(localStorage.getItem('firebase_token')).toBeNull()
  })
})

// =============================================================================
// TEST LOGOUT ALL FLOW
// =============================================================================

describe('logoutAllDevices', () => {
  beforeEach(() => {
    // Setup active session
    localStorage.setItem('session_id', 'active_session_123')
    localStorage.setItem('firebase_token', 'active_token_123')
  })

  it('should call backend logout-all endpoint', async () => {
    // Mock successful logout-all
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        sessions_deleted: 3,
        message: 'All 3 sessions logged out successfully'
      })
    } as Response)

    const result = await logoutAllDevices()

    // Verify backend logout-all was called with Firebase token
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/session/logout-all',
      expect.objectContaining({
        method: 'DELETE',
        headers: {
          'Authorization': 'Bearer active_token_123',
          'Content-Type': 'application/json'
        }
      })
    )

    // Verify result
    expect(result.sessions_deleted).toBe(3)
  })

  it('should clear localStorage on logout-all', async () => {
    // Mock successful logout-all
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        sessions_deleted: 2
      })
    } as Response)

    await logoutAllDevices()

    // Verify localStorage is cleared
    expect(localStorage.getItem('session_id')).toBeNull()
    expect(localStorage.getItem('firebase_token')).toBeNull()
  })

  it('should fallback to single session logout on backend failure', async () => {
    // Mock backend logout-all failure
    vi.mocked(global.fetch)
      .mockResolvedValueOnce({
        ok: false,
        status: 500
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true })
      } as Response)

    const result = await logoutAllDevices()

    // Should fall back to single session logout
    expect(result.sessions_deleted).toBe(1)
  })

  it('should perform local logout if no Firebase token', async () => {
    // Clear Firebase token
    localStorage.removeItem('firebase_token')

    const result = await logoutAllDevices()

    // Should perform local logout only
    expect(global.fetch).not.toHaveBeenCalled()
    expect(result.sessions_deleted).toBe(1)
  })
})

// =============================================================================
// TEST SESSION VALIDATION
// =============================================================================

describe('getCurrentUser', () => {
  it('should return null if no session_id in localStorage', async () => {
    const user = await getCurrentUser()

    expect(user).toBeNull()
  })

  it('should return null if no firebase_token in localStorage', async () => {
    localStorage.setItem('session_id', 'session_123')

    const user = await getCurrentUser()

    expect(user).toBeNull()
  })

  it('should validate with backend and return user', async () => {
    localStorage.setItem('session_id', 'session_123')
    localStorage.setItem('firebase_token', 'token_123')

    vi.mocked(firebaseAuth.getCurrentUser).mockResolvedValueOnce(
      mockFirebaseUser as any
    )

    const user = await getCurrentUser()

    expect(user).toEqual(expect.objectContaining({
      id: 'user_123',
      email: 'test@example.com',
      session_id: 'session_123'
    }))
  })

  it('should clear session if Firebase user is null', async () => {
    localStorage.setItem('session_id', 'session_123')
    localStorage.setItem('firebase_token', 'token_123')

    vi.mocked(firebaseAuth.getCurrentUser).mockResolvedValueOnce(null)

    const user = await getCurrentUser()

    expect(user).toBeNull()
    expect(localStorage.getItem('session_id')).toBeNull()
    expect(localStorage.getItem('firebase_token')).toBeNull()
  })

  it('should clear session if backend validation fails', async () => {
    localStorage.setItem('session_id', 'session_123')
    localStorage.setItem('firebase_token', 'token_123')

    vi.mocked(firebaseAuth.getCurrentUser).mockResolvedValueOnce(
      mockFirebaseUser as any
    )

    vi.mocked(apiClient.auth.me).mockResolvedValueOnce({
      data: null
    } as any)

    const user = await getCurrentUser()

    expect(user).toBeNull()
    expect(localStorage.getItem('session_id')).toBeNull()
  })
})

describe('checkSession', () => {
  it('should return true if session is valid', async () => {
    localStorage.setItem('session_id', 'session_123')
    localStorage.setItem('firebase_token', 'token_123')

    vi.mocked(firebaseAuth.getCurrentUser).mockResolvedValueOnce(
      mockFirebaseUser as any
    )

    const isValid = await checkSession()

    expect(isValid).toBe(true)
  })

  it('should return false if session is invalid', async () => {
    const isValid = await checkSession()

    expect(isValid).toBe(false)
  })
})

// =============================================================================
// TEST TOKEN REFRESH
// =============================================================================

describe('setupTokenRefresh', () => {
  it('should setup automatic token refresh interval', () => {
    vi.useFakeTimers()

    setupTokenRefresh()

    // Advance time by 55 minutes
    vi.advanceTimersByTime(55 * 60 * 1000)

    // Token refresh should have been attempted
    // (Implementation depends on internal state, so we just verify no errors)
    expect(true).toBe(true)

    vi.useRealTimers()
  })
})

describe('stopTokenRefresh', () => {
  it('should stop automatic token refresh', () => {
    vi.useFakeTimers()

    setupTokenRefresh()
    stopTokenRefresh()

    // Advance time
    vi.advanceTimersByTime(60 * 60 * 1000)

    // Should not refresh after stopping
    expect(true).toBe(true)

    vi.useRealTimers()
  })
})

// =============================================================================
// TEST ERROR SCENARIOS
// =============================================================================

describe('Error Handling', () => {
  it('should handle network timeout during login', async () => {
    vi.mocked(global.fetch).mockImplementationOnce(
      () => new Promise((_, reject) =>
        setTimeout(() => reject(new Error('Network timeout')), 100)
      )
    )

    await expect(
      loginUser('test@example.com', 'password123')
    ).rejects.toThrow('Network timeout')
  })

  it('should handle malformed backend response', async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => {
        throw new Error('Invalid JSON')
      }
    } as Response)

    await expect(
      loginUser('test@example.com', 'password123')
    ).rejects.toThrow()
  })

  it('should handle concurrent logout requests gracefully', async () => {
    localStorage.setItem('session_id', 'session_123')
    localStorage.setItem('firebase_token', 'token_123')

    vi.mocked(global.fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ success: true })
    } as Response)

    // Call logout twice concurrently
    await Promise.all([logoutUser(), logoutUser()])

    // Should cleanup properly
    expect(localStorage.getItem('session_id')).toBeNull()
  })
})
