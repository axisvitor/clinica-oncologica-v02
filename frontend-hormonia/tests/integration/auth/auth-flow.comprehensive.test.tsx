import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider, safeLocalStorage } from '@/app/providers/AuthContext'
import { LoginPage } from '@/pages/LoginPage'
import { LoginPage } from '@/pages/LoginPage'
import { ProtectedRoute } from '@/features/auth/ProtectedRoute'

// Mock Dashboard component
const MockDashboard = () => <div data-testid="dashboard">Dashboard</div>

// Mock dependencies
const mockFirebaseAuth = vi.hoisted(() => ({
  onAuthStateChanged: vi.fn(),
  onIdTokenChanged: vi.fn(),
  getCurrentUser: vi.fn(),
  signOut: vi.fn(),
  setPersistence: vi.fn(),
  isConfigured: vi.fn().mockReturnValue(true)
}))

const mockApiClient = vi.hoisted(() => ({
  setAuthToken: vi.fn(),
  clearAuthToken: vi.fn(),
  fetchCsrfToken: vi.fn(),
  auth: {
    me: vi.fn(),
    checkAuth: vi.fn()
  },
  dashboard: {
    getMain: vi.fn().mockResolvedValue({})
  },
  getBaseURL: vi.fn().mockReturnValue('https://api.example.com'),
  getCsrfToken: vi.fn().mockReturnValue('csrf-token')
}))

const mockWsManager = vi.hoisted(() => ({
  connect: vi.fn().mockResolvedValue(undefined),
  disconnect: vi.fn(),
  updateToken: vi.fn()
}))

const mockFirebaseAuthService = vi.hoisted(() => ({
  loginUser: vi.fn(),
  logoutUser: vi.fn(),
  logoutAllDevices: vi.fn()
}))

const mockToast = vi.hoisted(() => vi.fn())
const mockUseAuthSubmit = vi.hoisted(() =>
  vi.fn().mockReturnValue({
    isSubmitting: false,
    error: null,
    handleSubmit: vi.fn(async () => undefined)
  })
)

// Mock modules
vi.mock('@/lib/firebase-lazy', () => ({
  firebaseAuthLazy: mockFirebaseAuth
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
  useAuthSubmit: mockUseAuthSubmit
}))

const createAuthSubmitState = (
  overrides: Partial<{
    isSubmitting: boolean
    error: string | null
    handleSubmit: (fn: unknown) => unknown
  }> = {}
) => ({
  isSubmitting: false,
  error: null,
  handleSubmit: vi.fn(async () => undefined),
  ...overrides
})

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
    vi.spyOn(safeLocalStorage, 'setItem')
    vi.spyOn(safeLocalStorage, 'removeItem')
    authStateChangeCallback = undefined
    tokenChangeCallback = undefined

    // Setup Firebase auth state change mock
    mockFirebaseAuth.onAuthStateChanged.mockImplementation((callback) => {
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
    mockApiClient.auth.checkAuth.mockResolvedValue({ authenticated: false })
    mockApiClient.dashboard.getMain.mockResolvedValue({})
    mockFirebaseAuth.signOut.mockResolvedValue({ error: null })
    mockFirebaseAuth.getCurrentUser.mockResolvedValue(mockFirebaseUser)
    mockFirebaseUser.getIdToken.mockResolvedValue('firebase-token')
    mockFirebaseAuthService.loginUser.mockResolvedValue({
      user: mockUser,
      session_id: 'session-123'
    })
    mockUseAuthSubmit.mockImplementation(({ onSubmit }) =>
      createAuthSubmitState({
        handleSubmit: vi.fn((data) => onSubmit(data))
      })
    )
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  const waitForAuthListener = async () => {
    await waitFor(() => {
      expect(authStateChangeCallback).toBeDefined()
    })
  }

  const triggerAuthState = async (firebaseUser: typeof mockFirebaseUser | null) => {
    await waitForAuthListener()
    await act(async () => {
      await authStateChangeCallback(firebaseUser)
    })
  }

  const triggerTokenChange = async (firebaseUser: typeof mockFirebaseUser) => {
    await waitFor(() => {
      expect(tokenChangeCallback).toBeDefined()
    })
    await act(async () => {
      await tokenChangeCallback(firebaseUser)
    })
  }

  const renderApp = async (
    initialRoute: string = '/',
    firebaseUser?: typeof mockFirebaseUser | null
  ) => {
    render(<TestApp initialRoute={initialRoute} />)
    if (firebaseUser !== undefined) {
      await triggerAuthState(firebaseUser)
    }
  }

  const waitForLoginPage = async () => {
    await waitFor(() => {
      expect(screen.getByText(/entrar na sua conta/i)).toBeInTheDocument()
    })
  }

  const waitForDashboard = async () => {
    await waitFor(() => {
      expect(screen.getByTestId('dashboard')).toBeInTheDocument()
    })
  }

  describe('Complete Login Flow', () => {
    it('should complete full login flow from login page to dashboard', async () => {
      mockFirebaseAuthService.loginUser.mockResolvedValue({
        user: mockUser,
        session_id: 'session-123'
      })

      mockFirebaseAuth.getCurrentUser.mockResolvedValue(mockFirebaseUser)

      await renderApp('/login', null)
      await waitForLoginPage()

      // Fill and submit login form
      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/^senha$/i)
      const submitButton = screen.getByRole('button', { name: /entrar/i })

      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'password123')
      await user.click(submitButton)

      // Wait for login to complete and redirect
      await waitFor(() => {
        expect(mockFirebaseAuthService.loginUser).toHaveBeenCalledWith('test@example.com', 'password123')
      })

      // Should redirect to dashboard
      await waitForDashboard()

      // Verify WebSocket connection
      expect(mockWsManager.connect).toHaveBeenCalledWith('firebase-token')
      expect(safeLocalStorage.setItem).toHaveBeenCalledWith('session_id', 'session-123')
    })

    it('should handle login with remember me option', async () => {
      mockFirebaseAuthService.loginUser.mockResolvedValue({
        user: mockUser,
        session_id: 'session-123'
      })

      mockFirebaseAuth.getCurrentUser.mockResolvedValue(mockFirebaseUser)

      await renderApp('/login', null)
      await waitForLoginPage()

      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/^senha$/i)
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
      mockUseAuthSubmit.mockReturnValue(createAuthSubmitState({ error: 'Invalid credentials' }))

      await renderApp('/login', null)
      await waitForLoginPage()

      expect(screen.getByText('Invalid credentials')).toBeInTheDocument()
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })

    it('should redirect authenticated users away from login page', async () => {
      await renderApp('/login', mockFirebaseUser)
      await waitForDashboard()
    })
  })

  describe('Protected Route Access', () => {
    it('should redirect unauthenticated users to login page', async () => {
      await renderApp('/dashboard', null)
      await waitForLoginPage()
    })

    it('should allow authenticated users to access protected routes', async () => {
      await renderApp('/dashboard', mockFirebaseUser)
      await waitForDashboard()
    })

    it('should preserve intended route after login', async () => {
      mockFirebaseAuthService.loginUser.mockResolvedValue({
        user: mockUser,
        session_id: 'session-123'
      })

      // Start at protected route (should redirect to login)
      await renderApp('/dashboard', null)
      await waitForLoginPage()

      // Complete login
      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/^senha$/i)
      const submitButton = screen.getByRole('button', { name: /entrar/i })

      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'password123')
      await user.click(submitButton)

      // Should be redirected back to intended route
      await waitForDashboard()
    })
  })

  describe('Session Management', () => {
    it('should handle session expiration gracefully', async () => {
      await renderApp('/dashboard', mockFirebaseUser)
      await waitForDashboard()

      // Simulate session expiration (backend validation failure)
      mockApiClient.auth.me.mockRejectedValue(new Error('Session expired'))

      await triggerAuthState(mockFirebaseUser)
      await waitForLoginPage()

      expect(mockToast).toHaveBeenCalledWith({
        title: 'Sessão expirada',
        description: 'Sua sessão expirou. Por favor, faça login novamente.',
        variant: 'destructive'
      })
    })

    it('should handle token refresh seamlessly', async () => {
      await renderApp('/dashboard', mockFirebaseUser)
      await waitForDashboard()

      // Simulate token refresh
      const newToken = 'refreshed-firebase-token'
      mockFirebaseUser.getIdToken.mockResolvedValue(newToken)

      await triggerTokenChange(mockFirebaseUser)

      // Should update WebSocket and API client with new token
      expect(mockWsManager.updateToken).toHaveBeenCalledWith(newToken)

      // User should remain on dashboard
      expect(screen.getByTestId('dashboard')).toBeInTheDocument()
    })
  })

  describe('Logout Flow', () => {
    it('should complete logout flow and redirect to login', async () => {
      await renderApp('/dashboard', mockFirebaseUser)
      await waitForDashboard()

      // Simulate logout
      await triggerAuthState(null)
      await waitForLoginPage()

      // Should disconnect WebSocket
      expect(mockWsManager.disconnect).toHaveBeenCalled()
      expect(safeLocalStorage.removeItem).toHaveBeenCalledWith('session_id')
    })
  })

  describe('Error Recovery', () => {
    it('should handle temporary network failures gracefully', async () => {
      mockUseAuthSubmit.mockImplementation(({ onSubmit }) =>
        createAuthSubmitState({
          error: 'Network error',
          handleSubmit: vi.fn((data) => onSubmit(data))
        })
      )

      await renderApp('/login', null)
      await waitForLoginPage()

      expect(screen.getByText('Network error')).toBeInTheDocument()

      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/^senha$/i)
      const submitButton = screen.getByRole('button', { name: /entrar/i })

      await user.clear(emailInput)
      await user.clear(passwordInput)
      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'password123')
      await user.click(submitButton)

      await waitForDashboard()
    })

    it('should handle backend unavailability gracefully', async () => {
      mockApiClient.auth.me.mockRejectedValue(new Error('Backend unavailable'))
      await renderApp('/dashboard', mockFirebaseUser)
      await waitForLoginPage()

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
      expect(screen.getByRole('status', { name: /loading/i })).toBeInTheDocument()

      // Complete auth check
      await triggerAuthState(null)
      await waitForLoginPage()

      // Should no longer show loading
      await waitFor(() => {
        expect(screen.queryByRole('status', { name: /loading/i })).not.toBeInTheDocument()
      })
    })

    it('should show submitting state during login', async () => {
      mockUseAuthSubmit.mockReturnValue(createAuthSubmitState({ isSubmitting: true }))

      await renderApp('/login', null)
      await waitForLoginPage()

      const submitButton = screen.getByRole('button', { name: /entrando.../i })
      expect(submitButton).toBeDisabled()
      expect(screen.getByText('Entrando...')).toBeInTheDocument()
    })
  })

  describe('WebSocket Integration', () => {
    it('should connect WebSocket on successful authentication', async () => {
      await renderApp('/', mockFirebaseUser)

      expect(mockWsManager.connect).toHaveBeenCalledWith('firebase-token')
    })

    it('should disconnect WebSocket on logout', async () => {
      await renderApp('/', mockFirebaseUser)
      await triggerAuthState(null)

      expect(mockWsManager.disconnect).toHaveBeenCalled()
    })

    it('should update WebSocket token on refresh', async () => {
      await renderApp('/', mockFirebaseUser)

      const newToken = 'new-token'
      mockFirebaseUser.getIdToken.mockResolvedValue(newToken)

      await triggerTokenChange(mockFirebaseUser)

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

    it('should allow login after CSRF initialization', async () => {
      mockFirebaseAuthService.loginUser.mockResolvedValue({
        user: mockUser,
        session_id: 'session-123'
      })
      mockFirebaseAuth.getCurrentUser.mockResolvedValue(mockFirebaseUser)

      await renderApp('/login', null)
      await waitForLoginPage()

      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/^senha$/i)
      const submitButton = screen.getByRole('button', { name: /entrar/i })

      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'password123')
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockFirebaseAuthService.loginUser).toHaveBeenCalledWith('test@example.com', 'password123')
      })

      expect(mockApiClient.fetchCsrfToken).toHaveBeenCalled()
    })
  })
})
