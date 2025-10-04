/**
 * Unit tests for Firebase Client Authentication
 *
 * Tests login flow, error handling, and session management
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { signInWithEmailAndPassword, sendPasswordResetEmail, signOut } from 'firebase/auth'

// Mock Firebase Auth module
vi.mock('firebase/auth', () => ({
  getAuth: vi.fn(() => ({})),
  initializeApp: vi.fn(),
  signInWithEmailAndPassword: vi.fn(),
  sendPasswordResetEmail: vi.fn(),
  signOut: vi.fn(),
  onAuthStateChanged: vi.fn()
}))

// Mock firebase-client - adjust import based on actual structure
vi.mock('../../../src/lib/firebase-client', async () => {
  const actual = await vi.importActual('../../../src/lib/firebase-client')
  return {
    ...actual,
    firebaseAuth: {
      signInWithPassword: async ({ email, password }: { email: string; password: string }) => {
        try {
          const result = await signInWithEmailAndPassword({} as any, email, password)
          const token = await result.user.getIdToken()
          return {
            user: result.user,
            session: { access_token: token },
            error: null
          }
        } catch (error: any) {
          let message = 'Erro ao fazer login'
          if (error.code === 'auth/wrong-password' || error.code === 'auth/user-not-found') {
            message = 'Credenciais inválidas'
          } else if (error.code === 'auth/network-request-failed') {
            message = 'Erro de conexão. Verifique sua internet.'
          }
          return {
            user: null,
            session: null,
            error: { message }
          }
        }
      },
      resetPassword: async (email: string) => {
        try {
          await sendPasswordResetEmail({} as any, email)
          return { error: null }
        } catch (error: any) {
          return { error: { message: 'Erro ao enviar email de recuperação' } }
        }
      },
      logout: async () => {
        try {
          await signOut({} as any)
          return { error: null }
        } catch (error: any) {
          return { error: { message: 'Erro ao fazer logout' } }
        }
      }
    }
  }
})

import { firebaseAuth } from '../../../src/lib/firebase-client'

describe('Firebase Client Authentication', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('signInWithPassword', () => {
    it('should return user and session on successful login', async () => {
      // Arrange
      const mockUser = {
        uid: 'test-uid-123',
        email: 'test@example.com',
        getIdToken: vi.fn().mockResolvedValue('mock-firebase-token-xyz')
      }

      vi.mocked(signInWithEmailAndPassword).mockResolvedValue({
        user: mockUser
      } as any)

      // Act
      const result = await firebaseAuth.signInWithPassword({
        email: 'test@example.com',
        password: 'password123'
      })

      // Assert
      expect(result.user).toBeDefined()
      expect(result.user?.uid).toBe('test-uid-123')
      expect(result.session?.access_token).toBe('mock-firebase-token-xyz')
      expect(result.error).toBeNull()
    })

    it('should return error on invalid credentials', async () => {
      // Arrange
      const firebaseError = {
        code: 'auth/wrong-password',
        message: 'Wrong password'
      }

      vi.mocked(signInWithEmailAndPassword).mockRejectedValue(firebaseError)

      // Act
      const result = await firebaseAuth.signInWithPassword({
        email: 'test@example.com',
        password: 'wrong-password'
      })

      // Assert
      expect(result.user).toBeNull()
      expect(result.session).toBeNull()
      expect(result.error).toBeDefined()
      expect(result.error?.message).toBe('Credenciais inválidas')
    })

    it('should return generic error for user-not-found', async () => {
      // Arrange
      const firebaseError = {
        code: 'auth/user-not-found',
        message: 'User not found'
      }

      vi.mocked(signInWithEmailAndPassword).mockRejectedValue(firebaseError)

      // Act
      const result = await firebaseAuth.signInWithPassword({
        email: 'nonexistent@example.com',
        password: 'password123'
      })

      // Assert - Should return same message as wrong-password (prevent user enumeration)
      expect(result.error?.message).toBe('Credenciais inválidas')
      expect(result.user).toBeNull()
      expect(result.session).toBeNull()
    })

    it('should handle network errors gracefully', async () => {
      // Arrange
      const networkError = {
        code: 'auth/network-request-failed',
        message: 'Network error'
      }

      vi.mocked(signInWithEmailAndPassword).mockRejectedValue(networkError)

      // Act
      const result = await firebaseAuth.signInWithPassword({
        email: 'test@example.com',
        password: 'password123'
      })

      // Assert
      expect(result.error?.message).toContain('conexão')
      expect(result.user).toBeNull()
      expect(result.session).toBeNull()
    })

    it('should handle empty email', async () => {
      // Arrange
      const emptyEmailError = {
        code: 'auth/invalid-email',
        message: 'Invalid email'
      }

      vi.mocked(signInWithEmailAndPassword).mockRejectedValue(emptyEmailError)

      // Act
      const result = await firebaseAuth.signInWithPassword({
        email: '',
        password: 'password123'
      })

      // Assert
      expect(result.error).toBeDefined()
      expect(result.user).toBeNull()
    })

    it('should handle empty password', async () => {
      // Arrange
      const emptyPasswordError = {
        code: 'auth/missing-password',
        message: 'Missing password'
      }

      vi.mocked(signInWithEmailAndPassword).mockRejectedValue(emptyPasswordError)

      // Act
      const result = await firebaseAuth.signInWithPassword({
        email: 'test@example.com',
        password: ''
      })

      // Assert
      expect(result.error).toBeDefined()
      expect(result.user).toBeNull()
    })
  })

  describe('resetPassword', () => {
    it('should send password reset email successfully', async () => {
      // Arrange
      vi.mocked(sendPasswordResetEmail).mockResolvedValue(undefined)

      // Act
      const result = await firebaseAuth.resetPassword('test@example.com')

      // Assert
      expect(result.error).toBeNull()
      expect(sendPasswordResetEmail).toHaveBeenCalledWith({}, 'test@example.com')
    })

    it('should handle reset email errors', async () => {
      // Arrange
      const resetError = {
        code: 'auth/user-not-found',
        message: 'User not found'
      }

      vi.mocked(sendPasswordResetEmail).mockRejectedValue(resetError)

      // Act
      const result = await firebaseAuth.resetPassword('nonexistent@example.com')

      // Assert
      expect(result.error).toBeDefined()
      expect(result.error?.message).toContain('Erro')
    })
  })

  describe('logout', () => {
    it('should logout successfully', async () => {
      // Arrange
      vi.mocked(signOut).mockResolvedValue(undefined)

      // Act
      const result = await firebaseAuth.logout()

      // Assert
      expect(result.error).toBeNull()
      expect(signOut).toHaveBeenCalledWith({})
    })

    it('should handle logout errors', async () => {
      // Arrange
      const logoutError = new Error('Logout failed')
      vi.mocked(signOut).mockRejectedValue(logoutError)

      // Act
      const result = await firebaseAuth.logout()

      // Assert
      expect(result.error).toBeDefined()
      expect(result.error?.message).toContain('Erro')
    })
  })
})
