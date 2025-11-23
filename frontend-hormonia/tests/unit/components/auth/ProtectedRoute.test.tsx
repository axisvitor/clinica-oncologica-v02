import React from 'react'
import { render, screen } from '@testing-library/react'
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import * as AuthContext from '@/contexts/AuthContext'

// Mock components
vi.mock('@/components/ui/loading-spinner', () => ({
  LoadingSpinner: ({ size }: { size?: string }) => (
    <div data-testid="loading-spinner" data-size={size}>Loading...</div>
  ),
}))

vi.mock('@/components/ui/alert', () => ({
  Alert: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div data-testid="alert" className={className}>{children}</div>
  ),
  AlertDescription: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="alert-description">{children}</div>
  ),
  AlertTitle: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="alert-title">{children}</div>
  ),
}))

vi.mock('lucide-react', () => ({
  AlertTriangle: () => <div data-testid="alert-triangle-icon" />,
}))

// Test components
const TestChild = () => <div data-testid="protected-content">Protected Content</div>
const LoginPage = () => {
  const location = useLocation()
  return (
    <div data-testid="login-page">
      Login Page - Redirected from: {location.state?.from?.pathname || 'unknown'}
    </div>
  )
}

// Test wrapper component
const TestWrapper = ({
  children,
  initialPath = '/'
}: {
  children: React.ReactNode
  initialPath?: string
}) => (
  <BrowserRouter>
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="*" element={children} />
    </Routes>
  </BrowserRouter>
)

describe('ProtectedRoute', () => {
  const mockUser = {
    id: '1',
    email: 'test@example.com',
    role: 'user',
    permissions: ['read:dashboard']
  }

  const createMockAuthContext = (overrides = {}) => ({
    isAuthenticated: true,
    isLoading: false,
    user: mockUser,
    hasRole: vi.fn().mockReturnValue(true),
    hasPermission: vi.fn().mockReturnValue(true),
    ...overrides
  })

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Loading State', () => {
    it('should show loading spinner when authentication is loading', () => {
      const mockAuth = createMockAuthContext({ isLoading: true })
      vi.spyOn(AuthContext, 'useAuth').mockReturnValue(mockAuth)

      render(
        <TestWrapper>
          <ProtectedRoute>
            <TestChild />
          </ProtectedRoute>
        </TestWrapper>
      )

      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument()
      expect(screen.getByTestId('loading-spinner')).toHaveAttribute('data-size', 'lg')
      expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument()
    })
  })

  describe('Authentication', () => {
    it('should render children when user is authenticated', () => {
      const mockAuth = createMockAuthContext()
      vi.spyOn(AuthContext, 'useAuth').mockReturnValue(mockAuth)

      render(
        <TestWrapper>
          <ProtectedRoute>
            <TestChild />
          </ProtectedRoute>
        </TestWrapper>
      )

      expect(screen.getByTestId('protected-content')).toBeInTheDocument()
      expect(screen.queryByTestId('login-page')).not.toBeInTheDocument()
    })

    it('should redirect to login when user is not authenticated', () => {
      const mockAuth = createMockAuthContext({
        isAuthenticated: false,
        user: null
      })
      vi.spyOn(AuthContext, 'useAuth').mockReturnValue(mockAuth)

      render(
        <TestWrapper>
          <ProtectedRoute>
            <TestChild />
          </ProtectedRoute>
        </TestWrapper>
      )

      expect(screen.getByTestId('login-page')).toBeInTheDocument()
      expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument()
    })
  })

  describe('Role-based Access Control', () => {
    it('should allow access when user has required role', () => {
      const mockAuth = createMockAuthContext()
      mockAuth.hasRole.mockReturnValue(true)
      vi.spyOn(AuthContext, 'useAuth').mockReturnValue(mockAuth)

      render(
        <TestWrapper>
          <ProtectedRoute requiredRole="admin">
            <TestChild />
          </ProtectedRoute>
        </TestWrapper>
      )

      expect(mockAuth.hasRole).toHaveBeenCalledWith('admin')
      expect(screen.getByTestId('protected-content')).toBeInTheDocument()
    })

    it('should deny access when user lacks required role', () => {
      const mockAuth = createMockAuthContext()
      mockAuth.hasRole.mockReturnValue(false)
      vi.spyOn(AuthContext, 'useAuth').mockReturnValue(mockAuth)

      render(
        <TestWrapper>
          <ProtectedRoute requiredRole="admin">
            <TestChild />
          </ProtectedRoute>
        </TestWrapper>
      )

      expect(mockAuth.hasRole).toHaveBeenCalledWith('admin')
      expect(screen.getByTestId('alert')).toBeInTheDocument()
      expect(screen.getByTestId('alert-title')).toHaveTextContent('Acesso Negado')
      expect(screen.getByTestId('alert-description')).toHaveTextContent('Role necessária: admin')
      expect(screen.getByTestId('alert-description')).toHaveTextContent('Sua role atual: user')
      expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument()
    })

    it('should allow access when user has any of the required roles', () => {
      const mockAuth = createMockAuthContext()
      mockAuth.hasRole.mockImplementation((role) => role === 'user')
      vi.spyOn(AuthContext, 'useAuth').mockReturnValue(mockAuth)

      render(
        <TestWrapper>
          <ProtectedRoute requiredRoles={['admin', 'user', 'moderator']}>
            <TestChild />
          </ProtectedRoute>
        </TestWrapper>
      )

      expect(mockAuth.hasRole).toHaveBeenCalledWith('admin')
      expect(mockAuth.hasRole).toHaveBeenCalledWith('user')
      expect(screen.getByTestId('protected-content')).toBeInTheDocument()
    })

    it('should deny access when user has none of the required roles', () => {
      const mockAuth = createMockAuthContext()
      mockAuth.hasRole.mockReturnValue(false)
      vi.spyOn(AuthContext, 'useAuth').mockReturnValue(mockAuth)

      render(
        <TestWrapper>
          <ProtectedRoute requiredRoles={['admin', 'moderator']}>
            <TestChild />
          </ProtectedRoute>
        </TestWrapper>
      )

      expect(screen.getByTestId('alert')).toBeInTheDocument()
      expect(screen.getByTestId('alert-description')).toHaveTextContent('Roles necessárias: admin, moderator')
      expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument()
    })

    it('should handle empty required roles array', () => {
      const mockAuth = createMockAuthContext()
      vi.spyOn(AuthContext, 'useAuth').mockReturnValue(mockAuth)

      render(
        <TestWrapper>
          <ProtectedRoute requiredRoles={[]}>
            <TestChild />
          </ProtectedRoute>
        </TestWrapper>
      )

      expect(screen.getByTestId('protected-content')).toBeInTheDocument()
    })
  })

  describe('Permission-based Access Control', () => {
    it('should allow access when user has required permission', () => {
      const mockAuth = createMockAuthContext()
      mockAuth.hasPermission.mockReturnValue(true)
      vi.spyOn(AuthContext, 'useAuth').mockReturnValue(mockAuth)

      render(
        <TestWrapper>
          <ProtectedRoute requiredPermission="write:patients">
            <TestChild />
          </ProtectedRoute>
        </TestWrapper>
      )

      expect(mockAuth.hasPermission).toHaveBeenCalledWith('write:patients')
      expect(screen.getByTestId('protected-content')).toBeInTheDocument()
    })

    it('should deny access when user lacks required permission', () => {
      const mockAuth = createMockAuthContext()
      mockAuth.hasPermission.mockReturnValue(false)
      vi.spyOn(AuthContext, 'useAuth').mockReturnValue(mockAuth)

      render(
        <TestWrapper>
          <ProtectedRoute requiredPermission="write:patients">
            <TestChild />
          </ProtectedRoute>
        </TestWrapper>
      )

      expect(mockAuth.hasPermission).toHaveBeenCalledWith('write:patients')
      expect(screen.getByTestId('alert')).toBeInTheDocument()
      expect(screen.getByTestId('alert-description')).toHaveTextContent('Permissão necessária: write:patients')
      expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument()
    })
  })

  describe('Combined Access Control', () => {
    it('should apply both role and permission checks when both are specified', () => {
      const mockAuth = createMockAuthContext()
      mockAuth.hasRole.mockReturnValue(true)
      mockAuth.hasPermission.mockReturnValue(true)
      vi.spyOn(AuthContext, 'useAuth').mockReturnValue(mockAuth)

      render(
        <TestWrapper>
          <ProtectedRoute requiredRole="admin" requiredPermission="write:patients">
            <TestChild />
          </ProtectedRoute>
        </TestWrapper>
      )

      expect(mockAuth.hasRole).toHaveBeenCalledWith('admin')
      expect(mockAuth.hasPermission).toHaveBeenCalledWith('write:patients')
      expect(screen.getByTestId('protected-content')).toBeInTheDocument()
    })

    it('should deny access if role check fails even with valid permission', () => {
      const mockAuth = createMockAuthContext()
      mockAuth.hasRole.mockReturnValue(false)
      mockAuth.hasPermission.mockReturnValue(true)
      vi.spyOn(AuthContext, 'useAuth').mockReturnValue(mockAuth)

      render(
        <TestWrapper>
          <ProtectedRoute requiredRole="admin" requiredPermission="write:patients">
            <TestChild />
          </ProtectedRoute>
        </TestWrapper>
      )

      expect(mockAuth.hasRole).toHaveBeenCalledWith('admin')
      expect(mockAuth.hasPermission).not.toHaveBeenCalled() // Should not reach permission check
      expect(screen.getByTestId('alert-description')).toHaveTextContent('Role necessária: admin')
      expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument()
    })
  })

  describe('Error Cases', () => {
    it('should handle user without role property gracefully', () => {
      const mockAuth = createMockAuthContext({
        user: { id: '1', email: 'test@example.com' } // No role property
      })
      mockAuth.hasRole.mockReturnValue(false)
      vi.spyOn(AuthContext, 'useAuth').mockReturnValue(mockAuth)

      render(
        <TestWrapper>
          <ProtectedRoute requiredRole="admin">
            <TestChild />
          </ProtectedRoute>
        </TestWrapper>
      )

      expect(screen.getByTestId('alert')).toBeInTheDocument()
      // Should not crash and should not show role in description
      expect(screen.getByTestId('alert-description')).not.toHaveTextContent('Sua role atual:')
    })
  })

  describe('Accessibility', () => {
    it('should have proper alert structure for screen readers', () => {
      const mockAuth = createMockAuthContext()
      mockAuth.hasRole.mockReturnValue(false)
      vi.spyOn(AuthContext, 'useAuth').mockReturnValue(mockAuth)

      render(
        <TestWrapper>
          <ProtectedRoute requiredRole="admin">
            <TestChild />
          </ProtectedRoute>
        </TestWrapper>
      )

      const alert = screen.getByTestId('alert')
      const alertTitle = screen.getByTestId('alert-title')
      const alertDescription = screen.getByTestId('alert-description')

      expect(alert).toContainElement(alertTitle)
      expect(alert).toContainElement(alertDescription)
      expect(alertTitle).toHaveTextContent('Acesso Negado')
    })
  })
})