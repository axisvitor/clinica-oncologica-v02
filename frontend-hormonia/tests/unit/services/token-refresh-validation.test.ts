/**
 * Token Refresh Validation Tests
 *
 * Tests the security improvement that validates tokens with the backend
 * after each automatic refresh to prevent use after account deactivation.
 *
 * Test scenarios:
 * 1. Successful token refresh with valid backend validation
 * 2. Token refresh with backend validation failure (force logout)
 * 3. Token refresh when account is deactivated (force logout)
 * 4. Token refresh when no Firebase user exists (stop refresh)
 * 5. Multiple refresh cycles with validation
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import {
  setupTokenRefresh,
  stopTokenRefresh,
  loginUser,
  logoutUser
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
      me: vi.fn(),
      createSession: vi.fn()
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

// Mock window.location
const mockLocationHref = vi.fn()
delete (window as any).location
window.location = {
  href: '',
  pathname: '/dashboard',
  assign: mockLocationHref,
  reload: vi.fn(),
  replace: vi.fn()
} as any

// Override href setter
Object.defineProperty(window.location, 'href', {
  set: mockLocationHref,
  get: () => ''
})

// =============================================================================
// TEST FIXTURES
// =============================================================================

const mockFirebaseUser = {
  uid: 'test_firebase_uid_123',
  email: 'test@example.com',
  getIdToken: vi.fn(async (forceRefresh?: boolean) => {
    // Simulate different tokens for refresh
    return forceRefresh ? 'refreshed_token_xyz789' : 'original_token_abc123'
  })
}

const mockActiveUserResponse = {
  data: {
    id: 'user_123',
    email: 'test@example.com',
    full_name: 'Test User',
    role: 'doctor',
    is_active: true, // Active account
    permissions: ['patients:read', 'patients:write'],
    created_at: new Date().toISOString()
  }
}

const mockDeactivatedUserResponse = {
  data: {
    id: 'user_123',
    email: 'test@example.com',
    full_name: 'Test User',
    role: 'doctor',
    is_active: false, // Deactivated account
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
  vi.useFakeTimers()

  // Reset location mock
  mockLocationHref.mockClear()

  // Setup default mock behaviors
  vi.mocked(firebaseAuth.getCurrentUser).mockResolvedValue(mockFirebaseUser as any)
  vi.mocked(apiClient.auth.me).mockResolvedValue(mockActiveUserResponse)
})

afterEach(() => {
  stopTokenRefresh()
  vi.useRealTimers()
})

// =============================================================================
// TEST SUCCESSFUL TOKEN REFRESH WITH VALIDATION
// =============================================================================

describe('setupTokenRefresh - Successful Validation', () => {
  it('should refresh token and validate with backend successfully', async () => {
    setupTokenRefresh()

    // Fast-forward to trigger refresh (55 minutes)
    await vi.advanceTimersByTimeAsync(55 * 60 * 1000)

    // Verify token was refreshed
    expect(mockFirebaseUser.getIdToken).toHaveBeenCalledWith(true)

    // Verify new token was set in API client
    expect(apiClient.setAuthToken).toHaveBeenCalledWith('refreshed_token_xyz789')

    // Verify backend validation was called
    expect(apiClient.auth.me).toHaveBeenCalled()

    // Verify no logout occurred (validation passed)
    expect(global.fetch).not.toHaveBeenCalledWith(
      expect.stringContaining('/session/logout'),
      expect.anything()
    )

    // Verify no redirect occurred
    expect(mockLocationHref).not.toHaveBeenCalled()
  }, 15000) // Increase timeout

  it('should continue refreshing after successful validation', async () => {
    setupTokenRefresh()

    // First refresh cycle
    await vi.advanceTimersByTimeAsync(55 * 60 * 1000)

    const firstCallCount = vi.mocked(apiClient.auth.me).mock.calls.length

    // Second refresh cycle
    await vi.advanceTimersByTimeAsync(55 * 60 * 1000)

    const secondCallCount = vi.mocked(apiClient.auth.me).mock.calls.length

    // Verify multiple refresh cycles occurred
    expect(secondCallCount).toBeGreaterThan(firstCallCount)
  }, 15000) // Increase timeout
})

// =============================================================================
// TEST TOKEN REFRESH WITH BACKEND VALIDATION FAILURE
// =============================================================================

describe('setupTokenRefresh - Validation Failure', () => {
  it('should force logout when backend validation fails', async () => {
    // Mock validation failure
    vi.mocked(apiClient.auth.me).mockRejectedValueOnce(new Error('Unauthorized'))

    // Mock logout endpoint
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true, message: 'Logged out' })
    } as Response)

    setupTokenRefresh()

    // Trigger refresh
    await vi.advanceTimersByTimeAsync(55 * 60 * 1000)

    // Verify logout was called
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/session/logout',
      expect.objectContaining({
        method: 'DELETE'
      })
    )

    // Verify redirect to login page
    expect(mockLocationHref).toHaveBeenCalledWith('/login?session_invalid=true')
  })

  it('should force logout when validation returns no data', async () => {
    // Mock validation returning null/invalid response
    vi.mocked(apiClient.auth.me).mockResolvedValueOnce({ data: null } as any)

    // Mock logout endpoint
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true })
    } as Response)

    setupTokenRefresh()

    // Trigger refresh
    await vi.advanceTimersByTimeAsync(55 * 60 * 1000)

    // Verify logout was called
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/session/logout'),
      expect.anything()
    )
  }, 15000)

  it('should handle logout failure gracefully during validation failure', async () => {
    // Mock validation failure
    vi.mocked(apiClient.auth.me).mockRejectedValueOnce(new Error('Unauthorized'))

    // Mock logout endpoint failure
    vi.mocked(global.fetch).mockRejectedValueOnce(new Error('Network error'))

    setupTokenRefresh()

    // Trigger refresh
    await vi.advanceTimersByTimeAsync(55 * 60 * 1000)

    // Should still redirect even if logout fails
    expect(mockLocationHref).toHaveBeenCalledWith('/login?session_invalid=true')
  }, 15000)
})

// =============================================================================
// TEST ACCOUNT DEACTIVATION DETECTION
// =============================================================================

describe('setupTokenRefresh - Account Deactivation', () => {
  it('should force logout when account is deactivated', async () => {
    // Mock validation returning deactivated account
    vi.mocked(apiClient.auth.me).mockResolvedValueOnce(mockDeactivatedUserResponse)

    // Mock logout endpoint
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true })
    } as Response)

    setupTokenRefresh()

    // Trigger refresh
    await vi.advanceTimersByTimeAsync(55 * 60 * 1000)

    // Verify logout was called
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/session/logout'),
      expect.anything()
    )

    // Verify redirect to login page
    expect(mockLocationHref).toHaveBeenCalledWith('/login?session_invalid=true')
  }, 15000)

  it('should stop refresh interval after account deactivation', async () => {
    // Mock validation returning deactivated account
    vi.mocked(apiClient.auth.me).mockResolvedValueOnce(mockDeactivatedUserResponse)

    // Mock logout
    vi.mocked(global.fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ success: true })
    } as Response)

    setupTokenRefresh()

    // Trigger first refresh (should detect deactivation)
    await vi.advanceTimersByTimeAsync(55 * 60 * 1000)

    const firstLogoutCallCount = vi.mocked(global.fetch).mock.calls.filter(
      call => call[0]?.toString().includes('/session/logout')
    ).length

    // Try to trigger second refresh
    await vi.advanceTimersByTimeAsync(55 * 60 * 1000)

    const secondLogoutCallCount = vi.mocked(global.fetch).mock.calls.filter(
      call => call[0]?.toString().includes('/session/logout')
    ).length

    // Verify refresh interval was stopped (no second logout call)
    expect(secondLogoutCallCount).toBe(firstLogoutCallCount)
  }, 15000)
})

// =============================================================================
// TEST NO FIREBASE USER (STOP REFRESH)
// =============================================================================

describe('setupTokenRefresh - No Firebase User', () => {
  it('should stop refresh interval when no Firebase user exists', async () => {
    // Mock no Firebase user
    vi.mocked(firebaseAuth.getCurrentUser).mockResolvedValueOnce(null)

    setupTokenRefresh()

    // Trigger refresh
    await vi.advanceTimersByTimeAsync(55 * 60 * 1000)

    // Verify token refresh was NOT attempted
    expect(mockFirebaseUser.getIdToken).not.toHaveBeenCalled()

    // Verify backend validation was NOT called
    expect(apiClient.auth.me).not.toHaveBeenCalled()

    // Try second refresh cycle
    await vi.advanceTimersByTimeAsync(55 * 60 * 1000)

    // Verify still not called (interval stopped)
    expect(mockFirebaseUser.getIdToken).not.toHaveBeenCalled()
  }, 15000)
})

// =============================================================================
// TEST REFRESH INTERVAL MANAGEMENT
// =============================================================================

describe('setupTokenRefresh - Interval Management', () => {
  it('should clear existing interval when setting up new one', async () => {
    // Setup first interval
    setupTokenRefresh()

    // Trigger first refresh
    await vi.advanceTimersByTimeAsync(55 * 60 * 1000)

    const firstCallCount = vi.mocked(apiClient.auth.me).mock.calls.length

    // Setup second interval (should clear first)
    setupTokenRefresh()

    // Advance time again
    await vi.advanceTimersByTimeAsync(55 * 60 * 1000)

    const secondCallCount = vi.mocked(apiClient.auth.me).mock.calls.length

    // Verify only one refresh occurred in second interval
    expect(secondCallCount).toBe(firstCallCount + 1)
  }, 15000)

  it('should stop refresh interval via stopTokenRefresh()', async () => {
    setupTokenRefresh()

    // Stop refresh
    stopTokenRefresh()

    // Try to trigger refresh
    await vi.advanceTimersByTimeAsync(55 * 60 * 1000)

    // Verify no refresh occurred
    expect(mockFirebaseUser.getIdToken).not.toHaveBeenCalled()
  }, 15000)
})

// =============================================================================
// TEST EDGE CASES
// =============================================================================

describe('setupTokenRefresh - Edge Cases', () => {
  it('should handle Firebase token refresh failure gracefully', async () => {
    // Mock token refresh failure
    vi.mocked(mockFirebaseUser.getIdToken).mockRejectedValueOnce(
      new Error('Token refresh failed')
    )

    setupTokenRefresh()

    // Trigger refresh
    await vi.advanceTimersByTimeAsync(55 * 60 * 1000)

    // Verify backend validation was NOT called (token refresh failed first)
    expect(apiClient.auth.me).not.toHaveBeenCalled()

    // Verify no logout/redirect occurred
    expect(mockLocationHref).not.toHaveBeenCalled()
  }, 15000)

  it('should handle network errors during validation', async () => {
    // Mock network error during validation
    vi.mocked(apiClient.auth.me).mockRejectedValueOnce(
      new Error('Network connection failed')
    )

    // Mock logout
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true })
    } as Response)

    setupTokenRefresh()

    // Trigger refresh
    await vi.advanceTimersByTimeAsync(55 * 60 * 1000)

    // Should force logout even on network error
    expect(mockLocationHref).toHaveBeenCalledWith('/login?session_invalid=true')
  }, 15000)
})
