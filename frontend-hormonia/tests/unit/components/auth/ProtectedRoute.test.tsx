import React from 'react'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import { useAuth } from '@/app/providers/AuthContext'

vi.mock('@/app/providers/AuthContext', () => ({
  useAuth: vi.fn(),
}))

vi.mock('@/components/ui/loading-spinner', () => ({
  LoadingSpinner: ({ size }: { size?: string }) => (
    <div data-testid="loading-spinner" data-size={size}>Loading...</div>
  ),
}))

const mockedUseAuth = vi.mocked(useAuth)

const ProtectedContent = () => <div data-testid="protected-content">Protected Content</div>

function renderRoute(route = '/dashboard', element: React.ReactElement) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/login" element={<div data-testid="login-page">Login Page</div>} />
        <Route path="/dashboard" element={element} />
      </Routes>
    </MemoryRouter>
  )
}

describe('ProtectedRoute (canonical)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading spinner while auth is initializing', () => {
    mockedUseAuth.mockReturnValue({
      isAuthenticated: false,
      isInitializing: true,
      user: null,
    } as ReturnType<typeof useAuth>)

    renderRoute('/dashboard', (
      <ProtectedRoute>
        <ProtectedContent />
      </ProtectedRoute>
    ))

    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument()
    expect(screen.getByTestId('loading-spinner').parentElement).toHaveClass(
      'flex',
      'items-center',
      'justify-center',
      'min-h-screen'
    )
    expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument()
  })

  it('redirects unauthenticated users to /login', () => {
    mockedUseAuth.mockReturnValue({
      isAuthenticated: false,
      isInitializing: false,
      user: null,
    } as ReturnType<typeof useAuth>)

    renderRoute('/dashboard', (
      <ProtectedRoute>
        <ProtectedContent />
      </ProtectedRoute>
    ))

    expect(screen.getByTestId('login-page')).toBeInTheDocument()
    expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument()
  })

  it('renders children when user is authenticated and no extra guard is required', () => {
    mockedUseAuth.mockReturnValue({
      isAuthenticated: true,
      isInitializing: false,
      user: {
        id: '1',
        email: 'doctor@example.com',
        role: 'doctor',
      },
    } as ReturnType<typeof useAuth>)

    renderRoute('/dashboard', (
      <ProtectedRoute>
        <ProtectedContent />
      </ProtectedRoute>
    ))

    expect(screen.getByTestId('protected-content')).toBeInTheDocument()
  })

  it('blocks access when required permission is not granted for the user role', () => {
    mockedUseAuth.mockReturnValue({
      isAuthenticated: true,
      isInitializing: false,
      user: {
        id: '1',
        email: 'doctor@example.com',
        role: 'doctor',
      },
    } as ReturnType<typeof useAuth>)

    renderRoute('/dashboard', (
      <ProtectedRoute requiredPermission="canAccessAdmin">
        <ProtectedContent />
      </ProtectedRoute>
    ))

    expect(screen.getByText('Acesso Negado')).toBeInTheDocument()
    expect(screen.getByText(/Permissão necessária:/)).toBeInTheDocument()
    expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument()
  })

  it('allows access when required permission is granted for the user role', () => {
    mockedUseAuth.mockReturnValue({
      isAuthenticated: true,
      isInitializing: false,
      user: {
        id: '1',
        email: 'admin@example.com',
        role: 'admin',
      },
    } as ReturnType<typeof useAuth>)

    renderRoute('/dashboard', (
      <ProtectedRoute requiredPermission="canAccessAdmin">
        <ProtectedContent />
      </ProtectedRoute>
    ))

    expect(screen.getByTestId('protected-content')).toBeInTheDocument()
    expect(screen.queryByText('Acesso Negado')).not.toBeInTheDocument()
  })
})
