import React, { ReactElement, ReactNode } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { vi } from 'vitest'
import { AuthProvider, AuthContextType } from '@/contexts/AuthContext'

// Mock user for testing
export const mockUser = {
  id: 'test-user-id',
  email: 'test@example.com',
  full_name: 'Test User',
  role: 'admin',
  is_active: true,
  permissions: ['read:patients', 'write:patients', 'read:reports', 'write:reports'],
  created_at: '2023-01-01T00:00:00-03:00'
}

export const mockFirebaseUser = {
  id: 'test-user-id',
  email: 'test@example.com',
  getIdToken: vi.fn().mockResolvedValue('mock-firebase-token'),
  created_at: '2023-01-01T00:00:00-03:00',
  user_metadata: {
    full_name: 'Test User',
    role: 'admin',
    permissions: ['read:patients', 'write:patients', 'read:reports', 'write:reports']
  }
}

export const mockSession = {
  access_token: 'test-access-token',
  refresh_token: 'test-refresh-token',
  expires_in: 3600,
  user: mockFirebaseUser
}

// Mock auth context values
export const createMockAuthContext = (overrides: Partial<AuthContextType> = {}): AuthContextType => ({
  user: mockUser,
  firebaseUser: mockFirebaseUser,
  session: mockSession,
  isAuthenticated: true,
  isLoading: false,
  login: vi.fn().mockResolvedValue(undefined),
  logout: vi.fn(),
  hasPermission: vi.fn().mockImplementation((permission: string) =>
    mockUser.permissions.includes(permission)
  ),
  hasRole: vi.fn().mockImplementation((role: string) =>
    mockUser.role === role
  ),
  ...overrides
})

// Create a custom render function that includes providers
interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  authContextValue?: Partial<AuthContextType>
  queryClient?: QueryClient
  initialRoute?: string
}

// eslint-disable-next-line react-refresh/only-export-components
const AllTheProviders = ({
  children,
  authContextValue = {},
  queryClient,
  initialRoute = '/'
}: {
  children: ReactNode
  authContextValue?: Partial<AuthContextType>
  queryClient?: QueryClient
  initialRoute?: string
}) => {
  const defaultQueryClient = new QueryClient({
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

  const client = queryClient || defaultQueryClient

  // Mock AuthProvider if authContextValue is provided
  const MockAuthProvider = ({ children }: { children: ReactNode }) => {
    const contextValue = createMockAuthContext(authContextValue)
    return (
      <AuthProvider>
        {/* Override context value using a mock */}
        {React.cloneElement(children as ReactElement, { mockAuthValue: contextValue })}
      </AuthProvider>
    )
  }

  // Set initial route
  if (initialRoute !== '/') {
    window.history.pushState({}, 'Test page', initialRoute)
  }

  return (
    <QueryClientProvider client={client}>
        <MockAuthProvider>
          {children}
        </MockAuthProvider>
    </QueryClientProvider>
  )
}

const customRender = (
  ui: ReactElement,
  options: CustomRenderOptions = {}
) => {
  const { authContextValue, queryClient, initialRoute, ...renderOptions } = options

  return render(ui, {
    wrapper: ({ children }) => (
      <AllTheProviders
        authContextValue={authContextValue}
        queryClient={queryClient}
        initialRoute={initialRoute}
      >
        {children}
      </AllTheProviders>
    ),
    ...renderOptions,
  })
}

// Re-export everything
// eslint-disable-next-line react-refresh/only-export-components
export * from '@testing-library/react'
export { customRender as render }

// Helper functions for common test scenarios
export const renderWithAuth = (
  ui: ReactElement,
  authOverrides: Partial<AuthContextType> = {},
  options: Omit<CustomRenderOptions, 'authContextValue'> = {}
) => {
  return customRender(ui, {
    ...options,
    authContextValue: authOverrides
  })
}

export const renderUnauthenticated = (
  ui: ReactElement,
  options: Omit<CustomRenderOptions, 'authContextValue'> = {}
) => {
  return customRender(ui, {
    ...options,
    authContextValue: {
      user: null,
      firebaseUser: null,
      session: null,
      isAuthenticated: false,
      isLoading: false
    }
  })
}

export const renderWithLoading = (
  ui: ReactElement,
  options: Omit<CustomRenderOptions, 'authContextValue'> = {}
) => {
  return customRender(ui, {
    ...options,
    authContextValue: {
      user: null,
      firebaseUser: null,
      session: null,
      isAuthenticated: false,
      isLoading: true
    }
  })
}

// Mock data factories
export const createMockPatient = (overrides = {}) => ({
  id: 'patient-1',
  name: 'João Silva',
  email: 'joao@example.com',
  phone: '+5511999999999',
  birth_date: '1990-01-01',
  gender: 'male',
  treatment_type: 'chemotherapy',
  status: 'active',
  created_at: '2023-01-01T00:00:00-03:00',
  updated_at: '2023-01-01T00:00:00-03:00',
  ...overrides
})

export const createMockMessage = (overrides = {}) => ({
  id: 'message-1',
  patient_id: 'patient-1',
  content: 'Test message',
  type: 'text',
  direction: 'outbound',
  status: 'delivered',
  sent_at: '2023-01-01T00:00:00-03:00',
  delivered_at: '2023-01-01T00:00:00-03:00',
  ...overrides
})

export const createMockQuiz = (overrides = {}) => ({
  id: 'quiz-1',
  title: 'Test Quiz',
  description: 'A test quiz',
  questions: [
    {
      id: 'q1',
      text: 'How are you feeling?',
      type: 'scale',
      options: ['1', '2', '3', '4', '5'],
      required: true
    }
  ],
  created_at: '2023-01-01T00:00:00-03:00',
  ...overrides
})

export const createMockReport = (overrides = {}) => ({
  id: 'report-1',
  patient_id: 'patient-1',
  type: 'progress',
  title: 'Progress Report',
  status: 'completed',
  generated_at: '2023-01-01T00:00:00-03:00',
  data: {},
  ...overrides
})

// Async helper for waiting for effects
export const waitForAsync = (delay = 0) =>
  new Promise(resolve => setTimeout(resolve, delay))

// Mock API responses
export const mockApiResponse = function<T>(data: T, delay = 0): Promise<T> {
  return new Promise(resolve => setTimeout(() => resolve(data), delay))
}

export const mockApiError = function(status = 500, message = 'Server Error', delay = 0): Promise<never> {
  return new Promise((_, reject) =>
    setTimeout(() => reject(new Error(`${status}: ${message}`)), delay)
  )
}

// Helper to create query client with custom options
export const createTestQueryClient = (overrides = {}) => {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
    ...overrides,
  })
}

// Helper for testing custom hooks with providers
export const createWrapperWithProviders = (
  authContextValue: Partial<AuthContextType> = {},
  queryClient?: QueryClient
) => {
  const client = queryClient || createTestQueryClient()

  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <AllTheProviders authContextValue={authContextValue}>
          {children}
        </AllTheProviders>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
