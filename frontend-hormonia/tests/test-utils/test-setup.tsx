import React from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { AuthContext } from '@/contexts/AuthContext'

// Test utilities and providers for comprehensive testing

export interface TestUser {
  id: string
  email: string
  role: string
  permissions: string[]
  token?: string
}

export interface MockAuthContextValue {
  user: TestUser | null
  isAuthenticated: boolean
  isLoading: boolean
  session: { access_token: string; refresh_token: string } | null
  login: jest.MockedFunction<any>
  logout: jest.MockedFunction<any>
  hasRole: jest.MockedFunction<any>
  hasPermission: jest.MockedFunction<any>
}

// Default test user
// eslint-disable-next-line react-refresh/only-export-components
export const createTestUser = (overrides: Partial<TestUser> = {}): TestUser => ({
  id: '1',
  email: 'test@example.com',
  role: 'user',
  permissions: ['read:dashboard'],
  token: 'mock-token',
  ...overrides,
})

// Default admin user
// eslint-disable-next-line react-refresh/only-export-components
export const createAdminUser = (overrides: Partial<TestUser> = {}): TestUser => ({
  id: 'admin-1',
  email: 'admin@example.com',
  role: 'admin',
  permissions: ['read:dashboard', 'write:patients', 'admin:users'],
  token: 'admin-token',
  ...overrides,
})

// Default medico user
// eslint-disable-next-line react-refresh/only-export-components
export const createMedicoUser = (overrides: Partial<TestUser> = {}): TestUser => ({
  id: 'medico-1',
  email: 'medico@example.com',
  role: 'medico',
  permissions: ['read:dashboard', 'read:patients', 'write:patients', 'manage:quizzes'],
  token: 'medico-token',
  ...overrides,
})

// Mock auth context provider
export const MockAuthProvider: React.FC<{
  children: React.ReactNode
  value?: Partial<MockAuthContextValue>
}> = ({ children, value = {} }) => {
  const defaultValue: MockAuthContextValue = {
    user: createTestUser(),
    isAuthenticated: true,
    isLoading: false,
    session: {
      access_token: 'mock-access-token',
      refresh_token: 'mock-refresh-token',
    },
    login: jest.fn().mockResolvedValue(undefined),
    logout: jest.fn(),
    hasRole: jest.fn().mockReturnValue(true),
    hasPermission: jest.fn().mockReturnValue(true),
    ...value,
  }

  return (
    <AuthContext.Provider value={defaultValue as any}>
      {children}
    </AuthContext.Provider>
  )
}

// Query client for testing
// eslint-disable-next-line react-refresh/only-export-components
export const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        cacheTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  })

// Combined test wrapper
export interface TestWrapperProps {
  children: React.ReactNode
  queryClient?: QueryClient
  authValue?: Partial<MockAuthContextValue>
  initialRoute?: string
}

export const TestWrapper: React.FC<TestWrapperProps> = ({
  children,
  queryClient,
  authValue,
  initialRoute = '/',
}) => {
  const client = queryClient || createTestQueryClient()

  return (
    <QueryClientProvider client={client}>
      <MockAuthProvider value={authValue}>
        <BrowserRouter>
          {children}
        </BrowserRouter>
      </MockAuthProvider>
    </QueryClientProvider>
  )
}

// Custom render function with default providers
export interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  queryClient?: QueryClient
  authValue?: Partial<MockAuthContextValue>
  initialRoute?: string
}

// eslint-disable-next-line react-refresh/only-export-components
export const renderWithProviders = (
  ui: React.ReactElement,
  {
    queryClient,
    authValue,
    initialRoute,
    ...renderOptions
  }: CustomRenderOptions = {}
) => {
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <TestWrapper
      queryClient={queryClient}
      authValue={authValue}
      initialRoute={initialRoute}
    >
      {children}
    </TestWrapper>
  )

  return render(ui, { wrapper: Wrapper, ...renderOptions })
}

// Mock API responses
// eslint-disable-next-line react-refresh/only-export-components
export const createMockApiResponse = <T,>(data: T, total?: number) => ({
  data,
  total: total ?? (Array.isArray(data) ? data.length : 1),
  page: 1,
  limit: 10,
})

// Mock quiz data
// eslint-disable-next-line react-refresh/only-export-components
export const createMockQuiz = (overrides: any = {}) => ({
  id: 'quiz-1',
  title: 'Test Quiz',
  description: 'A test quiz for testing',
  status: 'active',
  questions: [
    {
      id: 'q1',
      type: 'multiple_choice',
      question: 'How are you feeling?',
      options: ['Great', 'Good', 'Okay', 'Not great'],
      required: true,
    },
  ],
  created_at: '2024-01-01T00:00:00-03:00',
  updated_at: '2024-01-01T00:00:00-03:00',
  ...overrides,
})

// Mock patient data
// eslint-disable-next-line react-refresh/only-export-components
export const createMockPatient = (overrides: any = {}) => ({
  id: 'patient-1',
  name: 'João Silva',
  phone: '+55 11 99999-9999',
  email: 'joao@example.com',
  birth_date: '1990-01-01',
  treatment_type: 'Terapia Hormonal Feminina',
  treatment_start_date: '2024-01-01',
  status: 'active',
  created_at: '2024-01-01T00:00:00-03:00',
  updated_at: '2024-01-01T00:00:00-03:00',
  ...overrides,
})

// Mock quiz session data
// eslint-disable-next-line react-refresh/only-export-components
export const createMockQuizSession = (overrides: any = {}) => ({
  id: 'session-1',
  patient_id: 'patient-1',
  template_id: 'template-1',
  template_name: 'Monthly Check-up',
  status: 'active',
  responses: {},
  questions: [
    {
      id: 'q1',
      type: 'multiple_choice',
      question: 'How are you feeling?',
      options: ['Great', 'Good', 'Okay', 'Not great'],
      required: true,
    },
  ],
  created_at: '2024-01-01T00:00:00-03:00',
  expires_at: '2024-01-08T00:00:00-03:00',
  ...overrides,
})

// WebSocket message mocks
// eslint-disable-next-line react-refresh/only-export-components
export const createMockWebSocketMessage = (type: string, data: any = {}) => ({
  type,
  data,
  timestamp: new Date().toISOString(),
})

// Error mocks
// eslint-disable-next-line react-refresh/only-export-components
export const createMockApiError = (message: string, status: number = 400) => ({
  message,
  status,
  data: { message },
})

// Form validation test helpers
// eslint-disable-next-line react-refresh/only-export-components
export const fillFormField = async (
  getByTestId: (testId: string) => HTMLElement,
  fieldId: string,
  value: string
) => {
  const field = getByTestId(fieldId) as HTMLInputElement
  field.value = value
  field.dispatchEvent(new Event('input', { bubbles: true }))
  field.dispatchEvent(new Event('change', { bubbles: true }))
}

// Accessibility test helpers
// eslint-disable-next-line react-refresh/only-export-components
export const checkAccessibility = (container: HTMLElement) => {
  // Check for basic accessibility requirements
  const forms = container.querySelectorAll('form')
  forms.forEach(form => {
    const inputs = form.querySelectorAll('input, textarea, select')
    inputs.forEach(input => {
      const id = input.getAttribute('id')
      const label = form.querySelector(`label[for="${id}"]`)
      if (!label && !input.getAttribute('aria-label')) {
        console.warn(`Input ${id} has no associated label`)
      }
    })
  })

  // Check for required attributes
  const buttons = container.querySelectorAll('button')
  buttons.forEach(button => {
    if (!button.textContent && !button.getAttribute('aria-label')) {
      console.warn('Button has no accessible text')
    }
  })
}

// Test data generators
// eslint-disable-next-line react-refresh/only-export-components
export const generateMockUsers = (count: number): TestUser[] =>
  Array.from({ length: count }, (_, i) =>
    createTestUser({
      id: `user-${i + 1}`,
      email: `user${i + 1}@example.com`,
    })
  )

// eslint-disable-next-line react-refresh/only-export-components
export const generateMockPatients = (count: number) =>
  Array.from({ length: count }, (_, i) =>
    createMockPatient({
      id: `patient-${i + 1}`,
      name: `Patient ${i + 1}`,
      email: `patient${i + 1}@example.com`,
    })
  )

// Performance testing helpers
// eslint-disable-next-line react-refresh/only-export-components
export const measureRenderTime = (renderFn: () => void): number => {
  const start = performance.now()
  renderFn()
  const end = performance.now()
  return end - start
}

// Mock localStorage for testing
// eslint-disable-next-line react-refresh/only-export-components
export const mockLocalStorage = () => {
  const store: Record<string, string> = {}

  return {
    getItem: jest.fn((key: string) => store[key] || null),
    setItem: jest.fn((key: string, value: string) => {
      store[key] = value
    }),
    removeItem: jest.fn((key: string) => {
      delete store[key]
    }),
    clear: jest.fn(() => {
      Object.keys(store).forEach(key => delete store[key])
    }),
  }
}

// Mock window.matchMedia for responsive testing
// eslint-disable-next-line react-refresh/only-export-components
export const mockMatchMedia = (matches: boolean = false) => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: jest.fn().mockImplementation(query => ({
      matches,
      media: query,
      onchange: null,
      addListener: jest.fn(),
      removeListener: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    })),
  })
}

// Cleanup utilities
// eslint-disable-next-line react-refresh/only-export-components
export const cleanupAfterTest = () => {
  // Clear all mocks
  jest.clearAllMocks()

  // Clear localStorage
  localStorage.clear()

  // Reset any global state if needed
}

export default {
  renderWithProviders,
  TestWrapper,
  MockAuthProvider,
  createTestUser,
  createAdminUser,
  createMedicoUser,
  createMockQuiz,
  createMockPatient,
  createMockQuizSession,
  createMockApiResponse,
  createMockApiError,
  createMockWebSocketMessage,
  mockLocalStorage,
  mockMatchMedia,
  cleanupAfterTest,
}