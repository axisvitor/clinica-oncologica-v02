import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from '@/contexts/AuthContext'
import { LoginPage } from '@/pages/LoginPage'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'

// Mock Dashboard component
const MockDashboard = () => <div data-testid="dashboard">Dashboard</div>

// Mock dependencies
const mockFirebaseAuth = {
  onAuthStateChange: vi.fn(),
  onIdTokenChanged: vi.fn(),
  getCurrentUser: vi.fn(),
  signInWithPassword: vi.fn(),
  signOut: vi.fn(),
  setPersistence: vi.fn(),
  isConfigured: vi.fn().mockReturnValue(true)
}

const mockApiClient = {
  setAuthToken: vi.fn(),
  fetchCsrfToken: vi.fn(),
  auth: {
    me: vi.fn(),
    createSession: vi.fn()
  },
  getBaseURL: vi.fn().mockReturnValue('https://api.example.com'),
  getCsrfToken: vi.fn().mockReturnValue('csrf-token')
}

const mockWsManager = {
  connect: vi.fn(),
  disconnect: vi.fn(),
  updateToken: vi.fn()
}

const mockFirebaseAuthService = {
  loginUser: vi.fn(),
  logoutUser: vi.fn(),
  logoutAllDevices: vi.fn()
}

const mockToast = vi.fn()

// Mock modules
vi.mock('@/lib/firebase-client', () => ({
  firebaseAuth: mockFirebaseAuth
}))

vi.mock('@/lib/api-client', () => ({
  apiClient: mockApiClient
}))

vi.mock('@/lib/websocket', () => ({
  wsManager: mockWsManager
}))

vi.mock('@/services/firebase-auth', () => mockFirebaseAuthService)

vi.mock('@/hooks/use-toast', () => ({
  toast: mockToast
}))

vi.mock('@/config/mock.config', () => ({
  isMockAuthEnabled: vi.fn().mockReturnValue(false)
}))

vi.mock('@/lib/runtime-config', () => ({
  isProduction: vi.fn().mockReturnValue(false)
}))

vi.mock('@/lib/config-initializer', () => ({
  useConfig: () => ({
    config: {
      VITE_ENVIRONMENT: 'development',
      VITE_DEBUG_MODE: 'true',
      VITE_SHOW_DEMO_CREDENTIALS: 'true'
    }
  })
}))

vi.mock('@/hooks/use-auth-submit', () => ({
  useAuthSubmit: vi.fn().mockReturnValue({
    isSubmitting: false,
    error: null,
    handleSubmit: vi.fn((fn) => fn)
  })
}))

const mockUser = {
  id: 'user-id',
  email: 'test@example.com',
  full_name: 'Test User',
  role: 'admin',
  is_active: true,
  permissions: ['read:patients', 'write:patients'],
  created_at: '2023-01-01T00:00:00Z'
}

const mockFirebaseUser = {
  uid: 'firebase-uid',
  email: 'test@example.com',
  getIdToken: vi.fn().mockResolvedValue('firebase-token')
}

// Test App component
const TestApp = ({ initialRoute = '/' }: { initialRoute?: string }) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      }
    },
  })

  if (initialRoute !== '/') {
    window.history.pushState({}, 'Test page', initialRoute)
  }

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <MockDashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <MockDashboard />
                </ProtectedRoute>
              }
            />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

describe('Auth Flow Integration Tests', () => {
  let user: ReturnType<typeof userEvent.setup>
  let authStateChangeCallback: any
  let tokenChangeCallback: any

  beforeEach(() => {
    user = userEvent.setup()
    vi.clearAllMocks()

    // Setup Firebase auth state change mock
    mockFirebaseAuth.onAuthStateChange.mockImplementation((callback) => {
      authStateChangeCallback = callback
      return vi.fn() // unsubscribe function
    })

    // Setup Firebase token change mock
    mockFirebaseAuth.onIdTokenChanged.mockImplementation((callback) => {
      tokenChangeCallback = callback
      return vi.fn() // unsubscribe function
    })

    mockApiClient.fetchCsrfToken.mockResolvedValue(undefined)
    mockApiClient.auth.me.mockResolvedValue({ data: mockUser })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Complete Login Flow', () => {
    it('should complete full login flow from login page to dashboard', async () => {
      mockFirebaseAuthService.loginUser.mockResolvedValue({
        user: mockUser,
        session_id: 'session-123'
      })

      mockFirebaseAuth.getCurrentUser.mockResolvedValue(mockFirebaseUser)

      render(<TestApp initialRoute="/login" />)

      // Verify we're on login page
      expect(screen.getByRole('heading', { name: /entrar na sua conta/i })).toBeInTheDocument()

      // Fill and submit login form
      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/senha/i)
      const submitButton = screen.getByRole('button', { name: /entrar/i })

      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'password123')
      await user.click(submitButton)

      // Wait for login to complete and redirect
      await waitFor(() => {
        expect(mockFirebaseAuthService.loginUser).toHaveBeenCalledWith('test@example.com', 'password123')
      })

      // Simulate Firebase auth state change
      await act(async () => {
        await authStateChangeCallback(mockFirebaseUser)
      })

      // Should redirect to dashboard
      await waitFor(() => {
        expect(screen.getByTestId('dashboard')).toBeInTheDocument()
      })

      // Verify WebSocket connection
      expect(mockWsManager.connect).toHaveBeenCalledWith('firebase-token')
    })

    it('should handle login with remember me option', async () => {
      mockFirebaseAuthService.loginUser.mockResolvedValue({
        user: mockUser,
        session_id: 'session-123'
      })

      mockFirebaseAuth.getCurrentUser.mockResolvedValue(mockFirebaseUser)

      render(<TestApp initialRoute="/login" />)

      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/senha/i)
      const rememberMeCheckbox = screen.getByRole('checkbox', { name: /manter-me conectado/i })
      const submitButton = screen.getByRole('button', { name: /entrar/i })

      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'password123')
      await user.click(rememberMeCheckbox)
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockFirebaseAuth.setPersistence).toHaveBeenCalledWith(true)
      })
    })

    it('should handle login errors and display error message', async () => {
      const useAuthSubmitMock = vi.mocked(require('@/hooks/use-auth-submit').useAuthSubmit)
      useAuthSubmitMock.mockReturnValue({
        isSubmitting: false,
        error: 'Invalid credentials',
        handleSubmit: vi.fn((fn) => fn)
      })

      render(<TestApp initialRoute="/login" />)

      expect(screen.getByText('Invalid credentials')).toBeInTheDocument()
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })

    it('should redirect authenticated users away from login page', async () => {
      render(<TestApp initialRoute="/login" />)

      // Simulate user already authenticated
      await act(async () => {
        await authStateChangeCallback(mockFirebaseUser)
      })

      await waitFor(() => {
        expect(screen.getByTestId('dashboard')).toBeInTheDocument()
      })
    })
  })

  describe('Protected Route Access', () => {
    it('should redirect unauthenticated users to login page', async () => {
      render(<TestApp initialRoute="/dashboard" />)

      // Simulate no authenticated user
      await act(async () => {
        await authStateChangeCallback(null)
      })

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /entrar na sua conta/i })).toBeInTheDocument()
      })
    })

    it('should allow authenticated users to access protected routes', async () => {
      render(<TestApp initialRoute="/dashboard" />)

      // Simulate authenticated user
      await act(async () => {
        await authStateChangeCallback(mockFirebaseUser)
      })

      await waitFor(() => {
        expect(screen.getByTestId('dashboard')).toBeInTheDocument()
      })
    })

    it('should preserve intended route after login', async () => {
      mockFirebaseAuthService.loginUser.mockResolvedValue({
        user: mockUser,
        session_id: 'session-123'
      })

      // Start at protected route (should redirect to login)
      render(<TestApp initialRoute="/dashboard" />)

      // Should be redirected to login
      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /entrar na sua conta/i })).toBeInTheDocument()
      })

      // Complete login
      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/senha/i)
      const submitButton = screen.getByRole('button', { name: /entrar/i })

      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'password123')
      await user.click(submitButton)

      // Simulate successful auth
      await act(async () => {
        await authStateChangeCallback(mockFirebaseUser)
      })

      // Should be redirected back to intended route
      await waitFor(() => {
        expect(screen.getByTestId('dashboard')).toBeInTheDocument()
      })
    })
  })

  describe('Session Management', () => {
    it('should handle session expiration gracefully', async () => {
      // Start with authenticated user
      render(<TestApp initialRoute="/dashboard" />)

      await act(async () => {
        await authStateChangeCallback(mockFirebaseUser)
      })

      await waitFor(() => {
        expect(screen.getByTestId('dashboard')).toBeInTheDocument()
      })

      // Simulate session expiration (backend validation failure)
      mockApiClient.auth.me.mockRejectedValue(new Error('Session expired'))

      await act(async () => {
        await authStateChangeCallback(mockFirebaseUser)
      })

      // Should redirect to login and show toast
      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /entrar na sua conta/i })).toBeInTheDocument()
      })

      expect(mockToast).toHaveBeenCalledWith({
        title: 'Sessão expirada',
        description: 'Sua sessão expirou. Por favor, faça login novamente.',
        variant: 'destructive'
      })
    })

    it('should handle token refresh seamlessly', async () => {
      render(<TestApp initialRoute="/dashboard" />)

      // Start with authenticated user
      await act(async () => {
        await authStateChangeCallback(mockFirebaseUser)
      })

      await waitFor(() => {
        expect(screen.getByTestId('dashboard')).toBeInTheDocument()
      })

      // Simulate token refresh
      const newToken = 'refreshed-firebase-token'
      mockFirebaseUser.getIdToken.mockResolvedValue(newToken)

      await act(async () => {
        await tokenChangeCallback(mockFirebaseUser)
      })

      // Should update WebSocket and API client with new token
      expect(mockWsManager.updateToken).toHaveBeenCalledWith(newToken)
      expect(mockApiClient.setAuthToken).toHaveBeenCalledWith(newToken)

      // User should remain on dashboard
      expect(screen.getByTestId('dashboard')).toBeInTheDocument()
    })
  })

  describe('Logout Flow', () => {
    it('should complete logout flow and redirect to login', async () => {
      render(<TestApp initialRoute="/dashboard" />)

      // Start with authenticated user
      await act(async () => {
        await authStateChangeCallback(mockFirebaseUser)
      })

      await waitFor(() => {
        expect(screen.getByTestId('dashboard')).toBeInTheDocument()
      })

      // Simulate logout
      await act(async () => {
        await authStateChangeCallback(null)
      })

      // Should redirect to login
      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /entrar na sua conta/i })).toBeInTheDocument()
      })

      // Should disconnect WebSocket
      expect(mockWsManager.disconnect).toHaveBeenCalled()
    })
  })

  describe('Error Recovery', () => {
    it('should handle temporary network failures gracefully', async () => {
      render(<TestApp initialRoute="/login" />)

      // First login attempt fails
      const useAuthSubmitMock = vi.mocked(require('@/hooks/use-auth-submit').useAuthSubmit)
      useAuthSubmitMock.mockReturnValue({
        isSubmitting: false,
        error: 'Network error',
        handleSubmit: vi.fn((fn) => fn)
      })

      expect(screen.getByText('Network error')).toBeInTheDocument()

      // Second attempt succeeds
      useAuthSubmitMock.mockReturnValue({
        isSubmitting: false,
        error: null,
        handleSubmit: vi.fn((fn) => fn)
      })

      mockFirebaseAuthService.loginUser.mockResolvedValue({
        user: mockUser,
        session_id: 'session-123'
      })

      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/senha/i)
      const submitButton = screen.getByRole('button', { name: /entrar/i })

      await user.clear(emailInput)
      await user.clear(passwordInput)
      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'password123')
      await user.click(submitButton)

      await act(async () => {
        await authStateChangeCallback(mockFirebaseUser)
      })

      await waitFor(() => {
        expect(screen.getByTestId('dashboard')).toBeInTheDocument()
      })
    })

    it('should handle backend unavailability gracefully', async () => {
      render(<TestApp initialRoute="/dashboard" />)

      // Backend validation fails
      mockApiClient.auth.me.mockRejectedValue(new Error('Backend unavailable'))

      await act(async () => {
        await authStateChangeCallback(mockFirebaseUser)
      })

      // Should sign out and redirect to login
      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /entrar na sua conta/i })).toBeInTheDocument()
      })

      expect(mockToast).toHaveBeenCalledWith({
        title: 'Sessão expirada',
        description: 'Sua sessão expirou. Por favor, faça login novamente.',
        variant: 'destructive'
      })
    })
  })

  describe('Loading States', () => {
    it('should show loading spinner during authentication check', async () => {
      render(<TestApp />)

      // Should show loading initially
      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument()

      // Complete auth check
      await act(async () => {
        await authStateChangeCallback(null)
      })

      // Should no longer show loading
      await waitFor(() => {
        expect(screen.queryByTestId('loading-spinner')).not.toBeInTheDocument()
      })
    })

    it('should show submitting state during login', async () => {
      const useAuthSubmitMock = vi.mocked(require('@/hooks/use-auth-submit').useAuthSubmit)
      useAuthSubmitMock.mockReturnValue({
        isSubmitting: true,
        error: null,
        handleSubmit: vi.fn((fn) => fn)
      })

      render(<TestApp initialRoute="/login" />)

      const submitButton = screen.getByRole('button', { name: /entrando.../i })
      expect(submitButton).toBeDisabled()
      expect(screen.getByText('Entrando...')).toBeInTheDocument()
    })
  })

  describe('WebSocket Integration', () => {
    it('should connect WebSocket on successful authentication', async () => {
      render(<TestApp />)

      await act(async () => {
        await authStateChangeCallback(mockFirebaseUser)
      })

      expect(mockWsManager.connect).toHaveBeenCalledWith('firebase-token')
    })

    it('should disconnect WebSocket on logout', async () => {
      render(<TestApp />)

      // First authenticate
      await act(async () => {
        await authStateChangeCallback(mockFirebaseUser)
      })

      // Then logout
      await act(async () => {
        await authStateChangeCallback(null)
      })

      expect(mockWsManager.disconnect).toHaveBeenCalled()
    })

    it('should update WebSocket token on refresh', async () => {
      render(<TestApp />)

      await act(async () => {
        await authStateChangeCallback(mockFirebaseUser)
      })

      const newToken = 'new-token'
      mockFirebaseUser.getIdToken.mockResolvedValue(newToken)

      await act(async () => {
        await tokenChangeCallback(mockFirebaseUser)
      })

      expect(mockWsManager.updateToken).toHaveBeenCalledWith(newToken)
    })
  })

  describe('CSRF Protection', () => {
    it('should fetch CSRF token on app initialization', async () => {
      render(<TestApp />)

      await waitFor(() => {
        expect(mockApiClient.fetchCsrfToken).toHaveBeenCalled()
      })
    })

    it('should refresh CSRF token before and after login', async () => {
      mockFirebaseAuthService.loginUser.mockResolvedValue({
        user: mockUser,
        session_id: 'session-123'
      })

      render(<TestApp initialRoute="/login" />)

      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/senha/i)
      const submitButton = screen.getByRole('button', { name: /entrar/i })

      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'password123')
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockApiClient.fetchCsrfToken).toHaveBeenCalled()
      })
    })
  })
})