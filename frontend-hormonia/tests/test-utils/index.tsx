/**
 * Test utilities for Frontend-v2
 * Provides common test setup, mocks, and helpers
 */

import { ReactElement } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { vi } from 'vitest'
import { AuthProvider } from '@/src/contexts/AuthContext'

// Mock user types
export const mockUser = {
  id: 'test-user-id',
  email: 'test@example.com',
  full_name: 'Test User',
  role: 'admin',
  is_active: true,
  permissions: ['read:patients', 'write:patients', 'read:quiz', 'write:quiz'],
  created_at: new Date().toISOString()
}

export const mockFirebaseUser = {
  id: 'test-user-id',
  email: 'test@example.com',
  created_at: new Date().toISOString(),
  getIdToken: vi.fn().mockResolvedValue('mock-firebase-token'),
  user_metadata: {
    full_name: 'Test User',
    role: 'admin',
    permissions: ['read:patients', 'write:patients']
  }
}

export const mockSession = {
  access_token: 'mock-access-token',
  refresh_token: 'mock-refresh-token',
  expires_in: 3600,
  expires_at: Date.now() + 3600000,
  token_type: 'bearer',
  user: mockFirebaseUser
}

// Create a query client for tests
export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  })
}

// Mock AuthContext value
export const mockAuthContext = {
  user: mockUser,
  firebaseUser: mockFirebaseUser,
  session: mockSession,
  isAuthenticated: true,
  isLoading: false,
  login: vi.fn().mockResolvedValue(undefined),
  logout: vi.fn(),
  hasPermission: vi.fn((permission: string) => mockUser.permissions.includes(permission)),
  hasRole: vi.fn((role: string) => mockUser.role === role)
}

// Custom render with providers
interface AllProvidersProps {
  children: React.ReactNode
  queryClient?: QueryClient
  initialRoute?: string
}

function AllProviders({ children, queryClient, initialRoute = '/' }: AllProvidersProps) {
  const testQueryClient = queryClient || createTestQueryClient()

  if (initialRoute !== '/') {
    window.history.pushState({}, 'Test page', initialRoute)
  }

  return (
    <QueryClientProvider client={testQueryClient}>
      <BrowserRouter>
        {children}
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  queryClient?: QueryClient
  initialRoute?: string
  withAuth?: boolean
}

export function renderWithProviders(
  ui: ReactElement,
  {
    queryClient,
    initialRoute = '/',
    withAuth = false,
    ...renderOptions
  }: CustomRenderOptions = {}
) {
  const testQueryClient = queryClient || createTestQueryClient()

  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <AllProviders queryClient={testQueryClient} initialRoute={initialRoute}>
      {withAuth ? <AuthProvider>{children}</AuthProvider> : children}
    </AllProviders>
  )

  return {
    ...render(ui, { wrapper: Wrapper, ...renderOptions }),
    queryClient: testQueryClient
  }
}

// API mocking utilities
export function createMockApiClient() {
  return {
    auth: {
      login: vi.fn(),
      logout: vi.fn(),
      me: vi.fn(),
    },
    patients: {
      list: vi.fn(),
      get: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
      delete: vi.fn(),
    },
    questionnaires: {
      list: vi.fn(),
      get: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
      delete: vi.fn(),
      getAnalytics: vi.fn(),
    },
    setAuthToken: vi.fn(),
    setSessionToken: vi.fn(),
  }
}

// Mock Firebase Auth client (replaces legacy auth mocks)
export function createMockFirebaseAuth() {
  return {
    isConfigured: vi.fn(() => true),
    getCurrentSession: vi.fn().mockResolvedValue(mockSession),
    getCurrentUser: vi.fn().mockResolvedValue(mockFirebaseUser),
    signInWithPassword: vi.fn().mockResolvedValue({ user: mockFirebaseUser, session: mockSession, error: null }),
    signOut: vi.fn().mockResolvedValue({ error: null }),
    setPersistence: vi.fn().mockResolvedValue(undefined),
    onAuthStateChanged: vi.fn().mockResolvedValue(() => {}),
    onIdTokenChanged: vi.fn().mockResolvedValue(() => {})
  }
}

// Wait for async operations
export const waitForLoadingToFinish = () =>
  new Promise((resolve) => setTimeout(resolve, 0))

// Mock localStorage
export function mockLocalStorage() {
  const store: Record<string, string> = {}

  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key]
    }),
    clear: vi.fn(() => {
      Object.keys(store).forEach(key => delete store[key])
    }),
  }
}

// Mock sessionStorage
export function mockSessionStorage() {
  return mockLocalStorage() // Same implementation
}

// Mock toast notifications
export const mockToast = {
  toast: vi.fn(),
  dismiss: vi.fn(),
}

// Create mock form data
export function createMockFormData(data: Record<string, any>): FormData {
  const formData = new FormData()
  Object.entries(data).forEach(([key, value]) => {
    formData.append(key, value)
  })
  return formData
}

// Wait for element to be removed (useful for loading states)
export async function waitForElementToBeRemoved(
  callback: () => HTMLElement | null,
  options = { timeout: 3000 }
) {
  const startTime = Date.now()
  while (callback() !== null) {
    if (Date.now() - startTime > options.timeout) {
      throw new Error('Timeout waiting for element to be removed')
    }
    await new Promise(resolve => setTimeout(resolve, 50))
  }
}

// Re-export everything from testing library
export * from '@testing-library/react'
export { default as userEvent } from '@testing-library/user-event'
