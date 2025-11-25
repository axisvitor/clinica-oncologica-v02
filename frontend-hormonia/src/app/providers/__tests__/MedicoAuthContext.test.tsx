/**
 * Test Suite for MedicoAuthContext
 *
 * Tests:
 * - signIn calls apiClient.setAuthToken
 * - signOut calls firebaseAuth.signOut
 * - Token persistence in localStorage
 */

import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { MedicoAuthProvider, useMedicoAuth } from '../MedicoAuthContext'
import { firebaseAuth } from '../../src/lib/firebase-client'
import { apiClient } from '../../src/lib/api-client'
import type { User as FirebaseUser } from 'firebase/auth'

// Mock firebase-client
vi.mock('../../src/lib/firebase-client', () => ({
  firebaseAuth: {
    signInWithPassword: vi.fn(),
    signOut: vi.fn(),
    getCurrentUser: vi.fn(),
    setPersistence: vi.fn(),
    onAuthStateChange: vi.fn(() => () => {}),
    refreshSession: vi.fn()
  }
}))

// Mock api-client
vi.mock('../../src/lib/api-client', () => ({
  apiClient: {
    setAuthToken: vi.fn(),
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn()
  }
}))

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}

  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key]
    }),
    clear: vi.fn(() => {
      store = {}
    })
  }
})()

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock
})

describe('MedicoAuthContext', () => {
  const mockFirebaseUser: FirebaseUser = {
    uid: 'test-uid-123',
    email: '12345@medico.local',
    displayName: 'Dr. Test',
    metadata: {
      creationTime: new Date().toISOString(),
      lastSignInTime: new Date().toISOString()
    },
    getIdTokenResult: vi.fn().mockResolvedValue({
      claims: {
        role: 'medico',
        crm: '12345',
        especialidade: 'Oncologia',
        conselho_regional: 'CRM-SC',
        pacientes_atribuidos: []
      }
    })
  } as any

  beforeEach(() => {
    vi.clearAllMocks()
    localStorageMock.clear()

    // Default mock implementations
    vi.mocked(firebaseAuth.getCurrentUser).mockResolvedValue(null)
    vi.mocked(firebaseAuth.setPersistence).mockResolvedValue(undefined)
    vi.mocked(firebaseAuth.onAuthStateChange).mockReturnValue(() => {})
  })

  afterEach(() => {
    vi.clearAllTimers()
  })

  describe('signIn', () => {
    it('should call apiClient.setAuthToken with access token on successful signIn', async () => {
      // Setup
      const mockSession = {
        access_token: 'test-access-token-abc123',
        refresh_token: 'test-refresh-token-xyz789',
        expires_in: 3600
      }

      vi.mocked(firebaseAuth.signInWithPassword).mockResolvedValue({
        user: mockFirebaseUser,
        session: mockSession,
        error: null
      })

      // Render hook
      const { result } = renderHook(() => useMedicoAuth(), {
        wrapper: MedicoAuthProvider
      })

      // Wait for initialization
      await waitFor(() => {
        expect(result.current.state.isLoading).toBe(false)
      })

      // Execute signIn
      let signInResult: any
      await act(async () => {
        signInResult = await result.current.signIn('12345@medico.local', 'password123', false)
      })

      // Verify apiClient.setAuthToken was called with access token
      expect(apiClient.setAuthToken).toHaveBeenCalledWith('test-access-token-abc123')
      expect(apiClient.setAuthToken).toHaveBeenCalledTimes(1)

      // Verify signIn was successful
      expect(signInResult.success).toBe(true)
      expect(signInResult.token).toBe('test-access-token-abc123')
    })

    it('should persist token in localStorage on successful signIn', async () => {
      // Setup
      const mockSession = {
        access_token: 'persisted-access-token',
        refresh_token: 'persisted-refresh-token',
        expires_in: 3600
      }

      vi.mocked(firebaseAuth.signInWithPassword).mockResolvedValue({
        user: mockFirebaseUser,
        session: mockSession,
        error: null
      })

      // Render hook
      const { result } = renderHook(() => useMedicoAuth(), {
        wrapper: MedicoAuthProvider
      })

      await waitFor(() => {
        expect(result.current.state.isLoading).toBe(false)
      })

      // Execute signIn
      await act(async () => {
        await result.current.signIn('12345@medico.local', 'password123', true)
      })

      // Verify localStorage was called with correct tokens
      expect(localStorageMock.setItem).toHaveBeenCalledWith('medico_auth_token', 'persisted-access-token')
      expect(localStorageMock.setItem).toHaveBeenCalledWith('medico_refresh_token', 'persisted-refresh-token')
      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        'medico_session_expiry',
        expect.stringMatching(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/)
      )
    })

    it('should restore token from localStorage to apiClient on initialization', async () => {
      // Setup - simulate persisted token
      localStorageMock.getItem.mockImplementation((key: string) => {
        if (key === 'medico_auth_token') return 'stored-token-from-localstorage'
        return null
      })

      vi.mocked(firebaseAuth.getCurrentUser).mockResolvedValue(mockFirebaseUser)

      // Render hook - triggers initialization
      renderHook(() => useMedicoAuth(), {
        wrapper: MedicoAuthProvider
      })

      // Wait for initialization to complete
      await waitFor(() => {
        expect(apiClient.setAuthToken).toHaveBeenCalledWith('stored-token-from-localstorage')
      })

      // Verify token was restored from localStorage
      expect(localStorageMock.getItem).toHaveBeenCalledWith('medico_auth_token')
    })

    it('should set Firebase persistence based on rememberMe parameter', async () => {
      // Setup
      vi.mocked(firebaseAuth.signInWithPassword).mockResolvedValue({
        user: mockFirebaseUser,
        session: { access_token: 'token', refresh_token: 'refresh' },
        error: null
      })

      const { result } = renderHook(() => useMedicoAuth(), {
        wrapper: MedicoAuthProvider
      })

      await waitFor(() => {
        expect(result.current.state.isLoading).toBe(false)
      })

      // Execute signIn with rememberMe=true
      await act(async () => {
        await result.current.signIn('12345@medico.local', 'password123', true)
      })

      // Verify setPersistence was called with rememberMe value
      expect(firebaseAuth.setPersistence).toHaveBeenCalledWith(true)
    })

    it('should return error on failed signIn without calling apiClient.setAuthToken', async () => {
      // Setup - simulate auth failure
      vi.mocked(firebaseAuth.signInWithPassword).mockResolvedValue({
        user: null,
        session: null,
        error: new Error('Invalid credentials')
      })

      const { result } = renderHook(() => useMedicoAuth(), {
        wrapper: MedicoAuthProvider
      })

      await waitFor(() => {
        expect(result.current.state.isLoading).toBe(false)
      })

      // Execute signIn
      let signInResult: any
      await act(async () => {
        signInResult = await result.current.signIn('wrong@medico.local', 'wrongpass', false)
      })

      // Verify apiClient.setAuthToken was NOT called
      expect(apiClient.setAuthToken).not.toHaveBeenCalled()

      // Verify error was returned
      expect(signInResult.success).toBe(false)
      expect(signInResult.error).toBeDefined()
    })
  })

  describe('signOut', () => {
    it('should call firebaseAuth.signOut on signOut', async () => {
      // Setup
      vi.mocked(firebaseAuth.signOut).mockResolvedValue({ error: null })

      const { result } = renderHook(() => useMedicoAuth(), {
        wrapper: MedicoAuthProvider
      })

      await waitFor(() => {
        expect(result.current.state.isLoading).toBe(false)
      })

      // Execute signOut
      await act(async () => {
        await result.current.signOut()
      })

      // Verify firebaseAuth.signOut was called
      expect(firebaseAuth.signOut).toHaveBeenCalledTimes(1)
    })

    it('should clear tokens from localStorage on signOut', async () => {
      // Setup
      vi.mocked(firebaseAuth.signOut).mockResolvedValue({ error: null })

      // Set initial tokens
      localStorageMock.setItem('medico_auth_token', 'token-to-clear')
      localStorageMock.setItem('medico_refresh_token', 'refresh-to-clear')
      localStorageMock.setItem('medico_session_expiry', new Date().toISOString())

      const { result } = renderHook(() => useMedicoAuth(), {
        wrapper: MedicoAuthProvider
      })

      await waitFor(() => {
        expect(result.current.state.isLoading).toBe(false)
      })

      // Execute signOut
      await act(async () => {
        await result.current.signOut()
      })

      // Verify localStorage tokens were removed
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('medico_auth_token')
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('medico_refresh_token')
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('medico_session_expiry')
    })

    it('should call apiClient.setAuthToken(null) on signOut', async () => {
      // Setup
      vi.mocked(firebaseAuth.signOut).mockResolvedValue({ error: null })

      const { result } = renderHook(() => useMedicoAuth(), {
        wrapper: MedicoAuthProvider
      })

      await waitFor(() => {
        expect(result.current.state.isLoading).toBe(false)
      })

      // Execute signOut
      await act(async () => {
        await result.current.signOut()
      })

      // Verify apiClient.setAuthToken was called with null to clear token
      expect(apiClient.setAuthToken).toHaveBeenCalledWith(null)
    })

    it('should clear local state even if firebaseAuth.signOut fails', async () => {
      // Setup - simulate signOut error
      vi.mocked(firebaseAuth.signOut).mockResolvedValue({
        error: new Error('Network error')
      })

      const { result } = renderHook(() => useMedicoAuth(), {
        wrapper: MedicoAuthProvider
      })

      await waitFor(() => {
        expect(result.current.state.isLoading).toBe(false)
      })

      // Execute signOut
      await act(async () => {
        try {
          await result.current.signOut()
        } catch (e) {
          // Expected to throw
        }
      })

      // Verify local cleanup still occurred
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('medico_auth_token')
      expect(apiClient.setAuthToken).toHaveBeenCalledWith(null)
      expect(result.current.state.isAuthenticated).toBe(false)
    })
  })

  describe('Token Refresh', () => {
    it('should refresh token and update apiClient', async () => {
      // Setup
      vi.mocked(firebaseAuth.getCurrentUser).mockResolvedValue(mockFirebaseUser)
      vi.mocked(firebaseAuth.refreshSession).mockResolvedValue({
        access_token: 'refreshed-token',
        refresh_token: 'new-refresh-token'
      })

      const { result } = renderHook(() => useMedicoAuth(), {
        wrapper: MedicoAuthProvider
      })

      await waitFor(() => {
        expect(result.current.state.isLoading).toBe(false)
      })

      // Execute token refresh
      await act(async () => {
        await result.current.refreshToken()
      })

      // Verify session was refreshed
      expect(firebaseAuth.refreshSession).toHaveBeenCalled()
      expect(firebaseAuth.getCurrentUser).toHaveBeenCalled()
    })
  })

  describe('Backward Compatibility', () => {
    it('should provide login alias for signIn', async () => {
      // Setup
      vi.mocked(firebaseAuth.signInWithPassword).mockResolvedValue({
        user: mockFirebaseUser,
        session: { access_token: 'token', refresh_token: 'refresh' },
        error: null
      })

      const { result } = renderHook(() => useMedicoAuth(), {
        wrapper: MedicoAuthProvider
      })

      await waitFor(() => {
        expect(result.current.state.isLoading).toBe(false)
      })

      // Verify login function exists and works
      expect(result.current.login).toBeDefined()
      expect(typeof result.current.login).toBe('function')

      // Execute login (should work same as signIn)
      let loginResult: any
      await act(async () => {
        loginResult = await result.current.login('12345@medico.local', 'password123')
      })

      expect(loginResult.success).toBe(true)
    })

    it('should provide logout alias for signOut', async () => {
      // Setup
      vi.mocked(firebaseAuth.signOut).mockResolvedValue({ error: null })

      const { result } = renderHook(() => useMedicoAuth(), {
        wrapper: MedicoAuthProvider
      })

      await waitFor(() => {
        expect(result.current.state.isLoading).toBe(false)
      })

      // Verify logout function exists
      expect(result.current.logout).toBeDefined()
      expect(typeof result.current.logout).toBe('function')

      // Execute logout (should work same as signOut)
      await act(async () => {
        await result.current.logout()
      })

      expect(firebaseAuth.signOut).toHaveBeenCalled()
    })
  })
})
