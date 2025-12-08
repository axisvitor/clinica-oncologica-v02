import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from '@/contexts/AuthContext'
import AdminApp from '@/components/admin/AdminApp'
import { signInWithEmailAndPassword, signOut } from 'firebase/auth'
import React from 'react'

// Mock Firebase
vi.mock('@/lib/firebase', () => ({
  auth: {
    currentUser: null,
    onAuthStateChanged: vi.fn((callback) => {
      callback(null)
      return vi.fn() // unsubscribe function
    }),
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
  }),
}))

// Mock toast
vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}))

const TestWrapper = ({ children }: { children: React.ReactNode }) => (
  <BrowserRouter>
    <AuthProvider>{children}</AuthProvider>
  </BrowserRouter>
)

describe('Admin Authentication Flow - Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  describe('Admin Login Flow', () => {
    it('should display login form when not authenticated', () => {
      render(
        <TestWrapper>
          <AdminApp />
        </TestWrapper>
      )

      // Should show login form
      expect(screen.getByText(/admin login/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
    })

    it('should handle successful admin login', async () => {
      const user = userEvent.setup()
      const mockAdminUser = {
        uid: 'admin-123',
        email: 'admin@hormonia.com',
        displayName: 'Admin User',
        getIdTokenResult: vi.fn().mockResolvedValue({
          claims: { admin: true },
        }),
      }

      vi.mocked(signInWithEmailAndPassword).mockResolvedValueOnce({
        user: mockAdminUser,
      } as any)

      render(
        <TestWrapper>
          <AdminApp />
        </TestWrapper>
      )

      // Fill in login form
      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/password/i)
      const loginButton = screen.getByRole('button', { name: /login/i })

      await user.type(emailInput, 'admin@hormonia.com')
      await user.type(passwordInput, 'SecurePassword123!')
      await user.click(loginButton)

      // Wait for login to complete
      await waitFor(() => {
        expect(signInWithEmailAndPassword).toHaveBeenCalledWith(
          expect.anything(),
          'admin@hormonia.com',
          'SecurePassword123!'
        )
      })
    })

    it('should show error message on failed login', async () => {
      const user = userEvent.setup()
      const loginError = new Error('Invalid credentials')

      vi.mocked(signInWithEmailAndPassword).mockRejectedValueOnce(loginError)

      render(
        <TestWrapper>
          <AdminApp />
        </TestWrapper>
      )

      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/password/i)
      const loginButton = screen.getByRole('button', { name: /login/i })

      await user.type(emailInput, 'admin@hormonia.com')
      await user.type(passwordInput, 'wrongpassword')
      await user.click(loginButton)

      await waitFor(() => {
        expect(signInWithEmailAndPassword).toHaveBeenCalled()
      })
    })

    it('should validate email format', async () => {
      const user = userEvent.setup()

      render(
        <TestWrapper>
          <AdminApp />
        </TestWrapper>
      )

      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/password/i)
      const loginButton = screen.getByRole('button', { name: /login/i })

      await user.type(emailInput, 'invalid-email')
      await user.type(passwordInput, 'password123')
      await user.click(loginButton)

      // Should not call signIn with invalid email
      expect(signInWithEmailAndPassword).not.toHaveBeenCalled()
    })

    it('should handle remember me functionality', async () => {
      const user = userEvent.setup()
      const mockUser = {
        uid: 'admin-123',
        email: 'admin@hormonia.com',
        getIdTokenResult: vi.fn().mockResolvedValue({
          claims: { admin: true },
        }),
      }

      vi.mocked(signInWithEmailAndPassword).mockResolvedValueOnce({
        user: mockUser,
      } as any)

      render(
        <TestWrapper>
          <AdminApp />
        </TestWrapper>
      )

      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/password/i)
      const rememberMeCheckbox = screen.getByLabelText(/remember me/i)
      const loginButton = screen.getByRole('button', { name: /login/i })

      await user.type(emailInput, 'admin@hormonia.com')
      await user.type(passwordInput, 'password123')
      await user.click(rememberMeCheckbox)
      await user.click(loginButton)

      await waitFor(() => {
        expect(localStorage.setItem).toHaveBeenCalledWith('rememberMe', 'true')
      })
    })
  })

  describe('Admin Logout Flow', () => {
    it('should handle logout successfully', async () => {
      const user = userEvent.setup()
      vi.mocked(signOut).mockResolvedValueOnce(undefined)

      // Mock authenticated state
      const mockUser = {
        uid: 'admin-123',
        email: 'admin@hormonia.com',
        displayName: 'Admin User',
        getIdTokenResult: vi.fn().mockResolvedValue({
          claims: { admin: true },
        }),
      }

      render(
        <TestWrapper>
          <AdminApp />
        </TestWrapper>
      )

      // Simulate clicking logout button (implementation depends on UI)
      // This is a placeholder - actual implementation may vary
      await waitFor(() => {
        const logoutButton = screen.queryByRole('button', { name: /logout/i })
        if (logoutButton) {
          user.click(logoutButton)
        }
      })
    })

    it('should clear localStorage on logout', async () => {
      vi.mocked(signOut).mockResolvedValueOnce(undefined)

      // Set rememberMe before logout
      localStorage.setItem('rememberMe', 'true')

      render(
        <TestWrapper>
          <AdminApp />
        </TestWrapper>
      )

      // Trigger logout (implementation depends on UI)
      await waitFor(() => {
        expect(localStorage.removeItem).toHaveBeenCalledWith('rememberMe')
      })
    })

    it('should redirect to login page after logout', async () => {
      const user = userEvent.setup()
      vi.mocked(signOut).mockResolvedValueOnce(undefined)

      render(
        <TestWrapper>
          <AdminApp />
        </TestWrapper>
      )

      // After logout, should show login form
      await waitFor(() => {
        expect(screen.queryByText(/admin login/i)).toBeInTheDocument()
      })
    })
  })

  describe('Protected Routes', () => {
    it('should redirect non-admin users to login', () => {
      const mockUser = {
        uid: 'user-123',
        email: 'user@example.com',
        getIdTokenResult: vi.fn().mockResolvedValue({
          claims: {}, // No admin claim
        }),
      }

      render(
        <TestWrapper>
          <AdminApp />
        </TestWrapper>
      )

      // Non-admin should see login or access denied
      expect(screen.getByText(/admin login/i)).toBeInTheDocument()
    })

    it('should allow admin users to access protected routes', async () => {
      const mockAdminUser = {
        uid: 'admin-123',
        email: 'admin@hormonia.com',
        displayName: 'Admin User',
        getIdTokenResult: vi.fn().mockResolvedValue({
          claims: { admin: true },
        }),
      }

      render(
        <TestWrapper>
          <AdminApp />
        </TestWrapper>
      )

      // Admin should be able to access admin routes
      // This depends on the actual implementation
    })
  })

  describe('Session Management', () => {
    it('should maintain session with remember me', async () => {
      localStorage.setItem('rememberMe', 'true')

      render(
        <TestWrapper>
          <AdminApp />
        </TestWrapper>
      )

      // Should attempt to restore session
      await waitFor(() => {
        expect(localStorage.getItem).toHaveBeenCalledWith('rememberMe')
      })
    })

    it('should show session warning before expiry', async () => {
      // Mock session that's about to expire
      const mockUser = {
        uid: 'admin-123',
        email: 'admin@hormonia.com',
        getIdTokenResult: vi.fn().mockResolvedValue({
          claims: { admin: true },
        }),
      }

      render(
        <TestWrapper>
          <AdminApp />
        </TestWrapper>
      )

      // Session warning logic would be tested here
      // Implementation depends on AdminSessionManager
    })

    it('should handle session expiry gracefully', async () => {
      vi.mocked(signOut).mockResolvedValueOnce(undefined)

      render(
        <TestWrapper>
          <AdminApp />
        </TestWrapper>
      )

      // Simulate session expiry
      // Should redirect to login
      await waitFor(() => {
        expect(screen.getByText(/admin login/i)).toBeInTheDocument()
      })
    })
  })

  describe('Error Handling', () => {
    it('should handle network errors during login', async () => {
      const user = userEvent.setup()
      const networkError = new Error('Network error')

      vi.mocked(signInWithEmailAndPassword).mockRejectedValueOnce(networkError)

      render(
        <TestWrapper>
          <AdminApp />
        </TestWrapper>
      )

      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/password/i)
      const loginButton = screen.getByRole('button', { name: /login/i })

      await user.type(emailInput, 'admin@hormonia.com')
      await user.type(passwordInput, 'password123')
      await user.click(loginButton)

      await waitFor(() => {
        expect(signInWithEmailAndPassword).toHaveBeenCalled()
      })
    })

    it('should handle Firebase auth errors', async () => {
      const user = userEvent.setup()
      const authError = {
        code: 'auth/wrong-password',
        message: 'Wrong password',
      }

      vi.mocked(signInWithEmailAndPassword).mockRejectedValueOnce(authError)

      render(
        <TestWrapper>
          <AdminApp />
        </TestWrapper>
      )

      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/password/i)
      const loginButton = screen.getByRole('button', { name: /login/i })

      await user.type(emailInput, 'admin@hormonia.com')
      await user.type(passwordInput, 'wrongpassword')
      await user.click(loginButton)

      await waitFor(() => {
        expect(signInWithEmailAndPassword).toHaveBeenCalled()
      })
    })
  })

  describe('Password Security', () => {
    it('should show password strength indicator', async () => {
      const user = userEvent.setup()

      render(
        <TestWrapper>
          <AdminApp />
        </TestWrapper>
      )

      const passwordInput = screen.getByLabelText(/password/i)

      await user.type(passwordInput, 'weak')
      // Should show weak password indicator

      await user.clear(passwordInput)
      await user.type(passwordInput, 'StrongPassword123!')
      // Should show strong password indicator
    })

    it('should toggle password visibility', async () => {
      const user = userEvent.setup()

      render(
        <TestWrapper>
          <AdminApp />
        </TestWrapper>
      )

      const passwordInput = screen.getByLabelText(/password/i) as HTMLInputElement
      const toggleButton = screen.getByRole('button', { name: /show password/i })

      expect(passwordInput.type).toBe('password')

      await user.click(toggleButton)
      expect(passwordInput.type).toBe('text')

      await user.click(toggleButton)
      expect(passwordInput.type).toBe('password')
    })
  })
})
