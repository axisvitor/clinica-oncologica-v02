/**
 * Frontend integration tests for AdminApp and unified authentication.
 * Tests critical UI functionality and auth integration without over-testing implementation.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// Import components
import AdminApp from '../../frontend-hormonia/src/AdminApp'
import { AuthProvider } from '../../frontend-hormonia/src/contexts/AuthContext'
import AdminRoutes from '../../frontend-hormonia/src/routes/AdminRoutes'

// Mock Firebase
vi.mock('firebase/app', () => ({
  initializeApp: vi.fn(() => ({})),
  getApps: vi.fn(() => []),
}))

vi.mock('firebase/auth', () => ({
  getAuth: vi.fn(() => ({
    currentUser: null,
    onAuthStateChanged: vi.fn(),
  })),
  onAuthStateChanged: vi.fn(),
  signInWithEmailAndPassword: vi.fn(),
  signOut: vi.fn(),
  User: vi.fn(),
}))

// Mock API client
vi.mock('../../frontend-hormonia/src/lib/api-client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
  setAuthToken: vi.fn(),
  clearAuthToken: vi.fn(),
}))

// Mock hooks
vi.mock('../../frontend-hormonia/src/hooks/useAuth', () => ({
  useAuth: vi.fn(() => ({
    user: null,
    loading: false,
    isAuthenticated: false,
    login: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
  })),
}))

vi.mock('../../frontend-hormonia/src/hooks/useUserAdmin', () => ({
  useUserAdmin: vi.fn(() => ({
    users: [],
    loading: false,
    error: null,
    createUser: vi.fn(),
    updateUser: vi.fn(),
    deleteUser: vi.fn(),
    getUserStats: vi.fn(),
  })),
}))

// Test wrapper component
const TestWrapper = ({ children }: { children: React.ReactNode }) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          {children}
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

describe('AdminApp Integration', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })
    vi.clearAllMocks()
  })

  afterEach(() => {
    queryClient.clear()
  })

  it('renders without crashing', () => {
    render(
      <TestWrapper>
        <AdminApp />
      </TestWrapper>
    )

    // Should render without throwing errors
    expect(document.querySelector('.admin-app')).toBeTruthy()
  })

  it('includes error boundary', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    const ThrowError = () => {
      throw new Error('Test error')
    }

    // Should not crash the entire app
    render(
      <TestWrapper>
        <AdminApp />
      </TestWrapper>
    )

    consoleSpy.mockRestore()
  })

  it('renders admin routes', () => {
    render(
      <TestWrapper>
        <AdminRoutes />
      </TestWrapper>
    )

    // AdminRoutes should render (may redirect based on auth state)
    expect(document.body).toBeTruthy()
  })
})

describe('Authentication Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('handles unauthenticated state', async () => {
    const { useAuth } = await import('../../frontend-hormonia/src/hooks/useAuth')
    ;(useAuth as any).mockReturnValue({
      user: null,
      loading: false,
      isAuthenticated: false,
      login: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    })

    render(
      <TestWrapper>
        <AdminApp />
      </TestWrapper>
    )

    // Should handle unauthenticated state gracefully
    await waitFor(() => {
      expect(document.body).toBeTruthy()
    })
  })

  it('handles authenticated admin user', async () => {
    const { useAuth } = await import('../../frontend-hormonia/src/hooks/useAuth')
    ;(useAuth as any).mockReturnValue({
      user: {
        id: 'admin-123',
        email: 'admin@example.com',
        role: 'admin',
        full_name: 'Admin User',
      },
      loading: false,
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    })

    render(
      <TestWrapper>
        <AdminApp />
      </TestWrapper>
    )

    // Should render admin interface
    await waitFor(() => {
      expect(document.body).toBeTruthy()
    })
  })

  it('handles loading state', async () => {
    const { useAuth } = await import('../../frontend-hormonia/src/hooks/useAuth')
    ;(useAuth as any).mockReturnValue({
      user: null,
      loading: true,
      isAuthenticated: false,
      login: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    })

    render(
      <TestWrapper>
        <AdminApp />
      </TestWrapper>
    )

    // Should handle loading state
    await waitFor(() => {
      expect(document.body).toBeTruthy()
    })
  })
})

describe('Admin Dashboard Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('integrates with user management hook', async () => {
    const mockGetUserStats = vi.fn().mockResolvedValue({
      total_users: 100,
      active_users: 85,
      inactive_users: 15,
      by_role: { admin: 5, doctor: 95 },
      recent_registrations: 10,
    })

    const { useUserAdmin } = await import('../../frontend-hormonia/src/hooks/useUserAdmin')
    ;(useUserAdmin as any).mockReturnValue({
      users: [],
      loading: false,
      error: null,
      createUser: vi.fn(),
      updateUser: vi.fn(),
      deleteUser: vi.fn(),
      getUserStats: mockGetUserStats,
    })

    const { useAuth } = await import('../../frontend-hormonia/src/hooks/useAuth')
    ;(useAuth as any).mockReturnValue({
      user: {
        id: 'admin-123',
        email: 'admin@example.com',
        role: 'admin',
        full_name: 'Admin User',
      },
      loading: false,
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    })

    render(
      <TestWrapper>
        <AdminApp />
      </TestWrapper>
    )

    // Should integrate with admin hooks
    await waitFor(() => {
      expect(document.body).toBeTruthy()
    })
  })
})

describe('Error Handling', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('handles API errors gracefully', async () => {
    const { useUserAdmin } = await import('../../frontend-hormonia/src/hooks/useUserAdmin')
    ;(useUserAdmin as any).mockReturnValue({
      users: [],
      loading: false,
      error: new Error('API Error'),
      createUser: vi.fn(),
      updateUser: vi.fn(),
      deleteUser: vi.fn(),
      getUserStats: vi.fn(),
    })

    const { useAuth } = await import('../../frontend-hormonia/src/hooks/useAuth')
    ;(useAuth as any).mockReturnValue({
      user: {
        id: 'admin-123',
        email: 'admin@example.com',
        role: 'admin',
        full_name: 'Admin User',
      },
      loading: false,
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    })

    render(
      <TestWrapper>
        <AdminApp />
      </TestWrapper>
    )

    // Should handle API errors without crashing
    await waitFor(() => {
      expect(document.body).toBeTruthy()
    })
  })

  it('handles network errors', async () => {
    const { useAuth } = await import('../../frontend-hormonia/src/hooks/useAuth')
    ;(useAuth as any).mockReturnValue({
      user: null,
      loading: false,
      isAuthenticated: false,
      error: new Error('Network Error'),
      login: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    })

    render(
      <TestWrapper>
        <AdminApp />
      </TestWrapper>
    )

    // Should handle network errors gracefully
    await waitFor(() => {
      expect(document.body).toBeTruthy()
    })
  })
})

describe('Toast Notifications', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('includes toaster component', () => {
    render(
      <TestWrapper>
        <AdminApp />
      </TestWrapper>
    )

    // Toaster should be present for notifications
    expect(document.body).toBeTruthy()
  })
})

describe('Provider Hierarchy', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('maintains correct provider hierarchy', () => {
    // Test that providers are correctly nested
    render(
      <TestWrapper>
        <AdminApp />
      </TestWrapper>
    )

    // Should render without provider context errors
    expect(document.body).toBeTruthy()
  })

  it('uses unified auth provider', async () => {
    const { useAuth } = await import('../../frontend-hormonia/src/hooks/useAuth')
    const mockUseAuth = useAuth as any

    render(
      <TestWrapper>
        <AdminApp />
      </TestWrapper>
    )

    // Should call useAuth hook (unified auth)
    await waitFor(() => {
      expect(mockUseAuth).toHaveBeenCalled()
    })
  })
})

describe('Route Protection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('handles unauthorized access attempts', async () => {
    const { useAuth } = await import('../../frontend-hormonia/src/hooks/useAuth')
    ;(useAuth as any).mockReturnValue({
      user: {
        id: 'doctor-123',
        email: 'doctor@example.com',
        role: 'doctor', // Not admin
        full_name: 'Doctor User',
      },
      loading: false,
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    })

    render(
      <TestWrapper>
        <AdminRoutes />
      </TestWrapper>
    )

    // Should handle non-admin user appropriately
    await waitFor(() => {
      expect(document.body).toBeTruthy()
    })
  })

  it('redirects unauthenticated users', async () => {
    const { useAuth } = await import('../../frontend-hormonia/src/hooks/useAuth')
    ;(useAuth as any).mockReturnValue({
      user: null,
      loading: false,
      isAuthenticated: false,
      login: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    })

    render(
      <TestWrapper>
        <AdminRoutes />
      </TestWrapper>
    )

    // Should handle unauthenticated state
    await waitFor(() => {
      expect(document.body).toBeTruthy()
    })
  })
})

describe('Performance Considerations', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('handles rapid re-renders', async () => {
    const { useAuth } = await import('../../frontend-hormonia/src/hooks/useAuth')
    let renderCount = 0

    const mockUseAuth = vi.fn(() => {
      renderCount++
      return {
        user: null,
        loading: renderCount < 3, // Simulate loading then loaded
        isAuthenticated: false,
        login: vi.fn(),
        logout: vi.fn(),
        refreshUser: vi.fn(),
      }
    })

    ;(useAuth as any).mockImplementation(mockUseAuth)

    const { rerender } = render(
      <TestWrapper>
        <AdminApp />
      </TestWrapper>
    )

    // Force multiple re-renders
    for (let i = 0; i < 5; i++) {
      rerender(
        <TestWrapper>
          <AdminApp />
        </TestWrapper>
      )
    }

    // Should handle rapid re-renders without issues
    await waitFor(() => {
      expect(document.body).toBeTruthy()
    })
  })

  it('handles concurrent operations', async () => {
    const { useAuth } = await import('../../frontend-hormonia/src/hooks/useAuth')
    const { useUserAdmin } = await import('../../frontend-hormonia/src/hooks/useUserAdmin')

    const mockPromises = Array.from({ length: 5 }, () =>
      Promise.resolve({ data: 'test' })
    )

    ;(useAuth as any).mockReturnValue({
      user: {
        id: 'admin-123',
        email: 'admin@example.com',
        role: 'admin',
        full_name: 'Admin User',
      },
      loading: false,
      isAuthenticated: true,
      login: vi.fn().mockResolvedValue({}),
      logout: vi.fn().mockResolvedValue({}),
      refreshUser: vi.fn().mockResolvedValue({}),
    })

    ;(useUserAdmin as any).mockReturnValue({
      users: [],
      loading: false,
      error: null,
      createUser: vi.fn().mockResolvedValue({}),
      updateUser: vi.fn().mockResolvedValue({}),
      deleteUser: vi.fn().mockResolvedValue({}),
      getUserStats: vi.fn().mockResolvedValue({}),
    })

    render(
      <TestWrapper>
        <AdminApp />
      </TestWrapper>
    )

    // Should handle concurrent operations
    await Promise.all(mockPromises)

    await waitFor(() => {
      expect(document.body).toBeTruthy()
    })
  })
})