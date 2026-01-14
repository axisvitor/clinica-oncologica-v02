import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { AuthProvider, useAuth } from '@/contexts/AuthContext'
import { createAuthLock, AUTH_LOCK_TIMEOUT_MS, type AuthLockState } from '@/app/providers/AuthContext'
import { auth } from '@/lib/firebase'
import { signInWithEmailAndPassword, signOut, User as FirebaseUser } from 'firebase/auth'
import React from 'react'

// Mock Firebase auth
vi.mock('@/lib/firebase', () => ({
  auth: {
    currentUser: null,
    onAuthStateChanged: vi.fn(),
  },
}))

vi.mock('firebase/auth', () => ({
  signInWithEmailAndPassword: vi.fn(),
  signOut: vi.fn(),
  onAuthStateChanged: vi.fn(),
}))

// Mock logger
vi.mock('@/lib/logger', () => ({
  createLogger: () => ({
    log: vi.fn(),
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
  }),
}))

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <AuthProvider>{children}</AuthProvider>
)

describe('AuthContext', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Mock localStorage
    const localStorageMock = {
      getItem: vi.fn(),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
    }
    global.localStorage = localStorageMock as any
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('useAuth hook', () => {
    it('should provide initial auth state', () => {
      const { result } = renderHook(() => useAuth(), { wrapper })

      expect(result.current.user).toBeNull()
      expect(result.current.isAuthenticated).toBe(false)
      expect(result.current.isLoading).toBe(true)
      expect(result.current.isAdmin).toBe(false)
    })

    it('should throw error when used outside AuthProvider', () => {
      // Suppress console errors for this test
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      expect(() => {
        renderHook(() => useAuth())
      }).toThrow('useAuth must be used within an AuthProvider')

      consoleSpy.mockRestore()
    })
  })

  describe('login functionality', () => {
    it('should login user successfully', async () => {
      const mockUser = {
        uid: 'test-uid',
        email: 'test@example.com',
        displayName: 'Test User',
      } as FirebaseUser

      vi.mocked(signInWithEmailAndPassword).mockResolvedValueOnce({
        user: mockUser,
      } as any)

      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await result.current.login('test@example.com', 'password123')
      })

      await waitFor(() => {
        expect(signInWithEmailAndPassword).toHaveBeenCalledWith(
          auth,
          'test@example.com',
          'password123'
        )
      })
    })

    it('should handle login failure', async () => {
      const loginError = new Error('Invalid credentials')
      vi.mocked(signInWithEmailAndPassword).mockRejectedValueOnce(loginError)

      const { result } = renderHook(() => useAuth(), { wrapper })

      await expect(async () => {
        await act(async () => {
          await result.current.login('test@example.com', 'wrongpassword')
        })
      }).rejects.toThrow('Invalid credentials')
    })

    it('should store rememberMe preference', async () => {
      const mockUser = {
        uid: 'test-uid',
        email: 'test@example.com',
      } as FirebaseUser

      vi.mocked(signInWithEmailAndPassword).mockResolvedValueOnce({
        user: mockUser,
      } as any)

      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await result.current.login('test@example.com', 'password123', true)
      })

      await waitFor(() => {
        expect(localStorage.setItem).toHaveBeenCalledWith('rememberMe', 'true')
      })
    })
  })

  describe('logout functionality', () => {
    it('should logout user successfully', async () => {
      vi.mocked(signOut).mockResolvedValueOnce(undefined)

      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        result.current.logout()
      })

      await waitFor(() => {
        expect(signOut).toHaveBeenCalledWith(auth)
        expect(localStorage.removeItem).toHaveBeenCalledWith('rememberMe')
      })
    })

    it('should handle logout errors', async () => {
      const logoutError = new Error('Logout failed')
      vi.mocked(signOut).mockRejectedValueOnce(logoutError)

      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        result.current.logout()
      })

      // Should still clear localStorage even if signOut fails
      await waitFor(() => {
        expect(localStorage.removeItem).toHaveBeenCalledWith('rememberMe')
      })
    })
  })

  describe('admin role detection', () => {
    it('should detect admin user from email claims', async () => {
      const mockAdminUser = {
        uid: 'admin-uid',
        email: 'admin@hormonia.com',
        displayName: 'Admin User',
        getIdTokenResult: vi.fn().mockResolvedValue({
          claims: { admin: true },
        }),
      } as any

      const { result } = renderHook(() => useAuth(), { wrapper })

      // Simulate auth state change with admin user
      const onAuthStateChangedCallback = vi.mocked(auth.onAuthStateChanged).mock.calls[0]?.[0]
      if (onAuthStateChangedCallback) {
        await act(async () => {
          await onAuthStateChangedCallback(mockAdminUser)
        })
      }

      await waitFor(() => {
        expect(result.current.isAdmin).toBe(true)
      })
    })

    it('should detect non-admin user', async () => {
      const mockUser = {
        uid: 'user-uid',
        email: 'user@example.com',
        displayName: 'Regular User',
        getIdTokenResult: vi.fn().mockResolvedValue({
          claims: {},
        }),
      } as any

      const { result } = renderHook(() => useAuth(), { wrapper })

      // Simulate auth state change with regular user
      const onAuthStateChangedCallback = vi.mocked(auth.onAuthStateChanged).mock.calls[0]?.[0]
      if (onAuthStateChangedCallback) {
        await act(async () => {
          await onAuthStateChangedCallback(mockUser)
        })
      }

      await waitFor(() => {
        expect(result.current.isAdmin).toBe(false)
      })
    })
  })

  describe('session management', () => {
    it('should restore session from localStorage on mount', () => {
      vi.mocked(localStorage.getItem).mockReturnValueOnce('true')

      const { result } = renderHook(() => useAuth(), { wrapper })

      expect(localStorage.getItem).toHaveBeenCalledWith('rememberMe')
    })

    it('should clear session data on logout', async () => {
      vi.mocked(signOut).mockResolvedValueOnce(undefined)

      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        result.current.logout()
      })

      await waitFor(() => {
        expect(localStorage.removeItem).toHaveBeenCalledWith('rememberMe')
      })
    })
  })

  describe('auth state persistence', () => {
    it('should update state when Firebase auth state changes', async () => {
      const mockUser = {
        uid: 'test-uid',
        email: 'test@example.com',
        displayName: 'Test User',
        getIdTokenResult: vi.fn().mockResolvedValue({ claims: {} }),
      } as any

      const { result } = renderHook(() => useAuth(), { wrapper })

      // Get the onAuthStateChanged callback
      const onAuthStateChangedCallback = vi.mocked(auth.onAuthStateChanged).mock.calls[0]?.[0]

      if (onAuthStateChangedCallback) {
        await act(async () => {
          await onAuthStateChangedCallback(mockUser)
        })
      }

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true)
        expect(result.current.user).toBeTruthy()
        expect(result.current.isLoading).toBe(false)
      })
    })

    it('should clear state when user signs out', async () => {
      const { result } = renderHook(() => useAuth(), { wrapper })

      // Get the onAuthStateChanged callback
      const onAuthStateChangedCallback = vi.mocked(auth.onAuthStateChanged).mock.calls[0]?.[0]

      if (onAuthStateChangedCallback) {
        await act(async () => {
          await onAuthStateChangedCallback(null)
        })
      }

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(false)
        expect(result.current.user).toBeNull()
        expect(result.current.isLoading).toBe(false)
      })
    })
  })

  describe('error handling', () => {
    it('should handle Firebase auth errors gracefully', async () => {
      const firebaseError = {
        code: 'auth/user-not-found',
        message: 'User not found',
      }

      vi.mocked(signInWithEmailAndPassword).mockRejectedValueOnce(firebaseError)

      const { result } = renderHook(() => useAuth(), { wrapper })

      await expect(async () => {
        await act(async () => {
          await result.current.login('nonexistent@example.com', 'password')
        })
      }).rejects.toMatchObject(firebaseError)
    })

    it('should handle network errors during login', async () => {
      const networkError = new Error('Network error')
      vi.mocked(signInWithEmailAndPassword).mockRejectedValueOnce(networkError)

      const { result } = renderHook(() => useAuth(), { wrapper })

      await expect(async () => {
        await act(async () => {
          await result.current.login('test@example.com', 'password')
        })
      }).rejects.toThrow('Network error')
    })
  })

  describe('auth lock', () => {
    const createLockRef = (state: Partial<AuthLockState> = {}) => ({
      current: {
        locked: false,
        timestamp: 0,
        operation: null,
        ...state
      }
    })

    it('Login adquire e libera lock corretamente', () => {
      const nowSpy = vi.spyOn(Date, 'now').mockReturnValue(1000)
      const lockRef = createLockRef()
      const logger = { log: vi.fn(), warn: vi.fn() }
      const { acquireAuthLock, releaseAuthLock } = createAuthLock(lockRef, logger)

      expect(acquireAuthLock('login')).toBe(true)
      expect(lockRef.current.locked).toBe(true)
      expect(logger.log).toHaveBeenCalledWith('Auth lock acquired for login')

      releaseAuthLock()
      expect(lockRef.current.locked).toBe(false)
      expect(lockRef.current.operation).toBeNull()
      expect(logger.log).toHaveBeenCalledWith('Auth lock released (login)')

      nowSpy.mockRestore()
    })

    it('Login falha se lock ja esta ativo', () => {
      const nowSpy = vi.spyOn(Date, 'now').mockReturnValue(1000 + AUTH_LOCK_TIMEOUT_MS - 1)
      const lockRef = createLockRef({ locked: true, timestamp: 1000, operation: 'login' })
      const logger = { log: vi.fn(), warn: vi.fn() }
      const { acquireAuthLock } = createAuthLock(lockRef, logger)

      expect(acquireAuthLock('login')).toBe(false)
      expect(logger.warn).toHaveBeenCalled()

      nowSpy.mockRestore()
    })

    it('onAuthStateChanged respeita lock durante login', () => {
      const nowSpy = vi.spyOn(Date, 'now').mockReturnValue(2000)
      const lockRef = createLockRef({ locked: true, timestamp: 2000, operation: 'login' })
      const logger = { log: vi.fn(), warn: vi.fn() }
      const { acquireAuthLock } = createAuthLock(lockRef, logger)

      nowSpy.mockReturnValue(2000 + 100)
      expect(acquireAuthLock('restore')).toBe(false)

      nowSpy.mockRestore()
    })
  })
})
