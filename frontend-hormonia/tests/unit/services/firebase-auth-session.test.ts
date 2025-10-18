/**
 * Integration Tests for Firebase Authentication Service with Session Management
 *
 * Tests the complete frontend authentication workflow:
 * 1. Login with Firebase → Backend session creation
 * 2. Session ID storage in httpOnly cookie
 * 3. auth.me() called AFTER session creation
 * 4. Logout clears session
 * 5. Logout-all invalidates all sessions
 *
 * [P0 FIXES] Applied:
 * - mockSessionResponse includes status: 'authenticated'
 * - mockSessionResponse.session_id is 'cookie' placeholder
 * - Tests updated to match httpOnly cookie flow
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
} from '../../../src/services/firebase-auth'
import { firebaseAuth } from '../../../src/lib/firebase-client'
import { apiClient } from '../../../src/lib/api-client'

// =============================================================================
// MOCKS
// =============================================================================

// Mock firebase-client
vi.mock('../../../src/lib/firebase-client', () => ({
  auth: {},
  firebaseAuth: {
    signInWithPassword: vi.fn(),
    signOut: vi.fn(),
    getCurrentUser: vi.fn(),
    setPersistence: vi.fn()
  }
}))

// Mock api-client
vi.mock('../../../src/lib/api-client', () => ({
  apiClient: {
    setAuthToken: vi.fn(),
    auth: {
      me: vi.fn()
    },
    getCsrfToken: vi.fn(() => 'mock-csrf-token'),
    getBaseURL: vi.fn(() => 'http://localhost:8000')
  }
}))

// Mock logger
vi.mock('../../../src/lib/logger', () => ({
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
  status: 'authenticated', // [P0 FIX] Required by loginUser validation
  session_id: 'cookie', // Placeholder - actual session_id is in httpOnly cookie
  user: {
    id: 'user_123',
    email: 'test@example.com',
    full_name: 'Test User',
    role: 'doctor',
    is_active: true,
    permissions: ['patients:read', 'patients:write'],
    created_at: new Date().toISOString()
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
    permissions: ['patients:read', 'patients:write'],
    created_at: new Date().toISOString()
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
      'http://localhost:8000/session',
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        headers: expect.objectContaining({
          'Content-Type': 'application/json'
        }),
        body: expect.stringContaining('firebase_token')
      })
    )

    // [P0 FIX] Verify result - session_id is now 'cookie' placeholder
    expect(result.session_id).toBe('cookie') // Actual session_id is in httpOnly cookie
    expect(result.user).toEqual(mockUserResponse.data)
  })

  it('should NOT store session_id in localStorage (httpOnly cookie)', async () => {
    // Mock successful session creation
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSessionResponse
    } as Response)

    await loginUser('test@example.com', 'password123')

    // SECURITY FIX: session_id is now in httpOnly cookie (not localStorage)
    // JavaScript cannot access httpOnly cookies
    const storedSessionId = localStorage.getItem('session_id')
    expect(storedSessionId).toBeNull() // No longer stored in localStorage

    // Verify Firebase token is still stored for WebSocket/API auth
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

  it('should throw error if backend does not return authenticated status', async () => {
    // Mock session creation with invalid status
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: 'error', // Invalid status (should be 'authenticated')
        session_id: 'cookie'
      })
    } as Response)

    await expect(
      loginUser('test@example.com', 'password123')
    ).rejects.toThrow('Session creation failed - invalid status')
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
    ).rejects.toThrow('Invalid credentials')
  })

  it('should include CSRF token in session creation request', async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSessionResponse
    } as Response)

    await loginUser('test@example.com', 'password123')

    // Verify CSRF token is sent
    expect(global.fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({
          'X-CSRF-Token': 'mock-csrf-token'
        })
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

    // Verify logout endpoint was called
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/session/logout',
      expect.objectContaining({
        method: 'DELETE',
        credentials: 'include'
      })
    )
  })

  it('should clear localStorage on logout', async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true })
    } as Response)

    await logoutUser()

    // Verify localStorage is cleared
    expect(localStorage.getItem('firebase_token')).toBeNull()
  })
})
