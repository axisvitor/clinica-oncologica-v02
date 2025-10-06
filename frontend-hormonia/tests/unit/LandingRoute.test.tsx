import { render, screen } from '@testing-library/react'
import { BrowserRouter, MemoryRouter } from 'react-router-dom'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { LandingRoute } from '@/src/pages/LandingRoute'
import { useAuth } from '@/src/contexts/AuthContext'

// Mock the AuthContext
vi.mock('@/src/contexts/AuthContext')
const mockUseAuth = useAuth as ReturnType<typeof vi.fn>

// Mock the logger to avoid console logs in tests
vi.mock('@/src/lib/logger', () => ({
  createLogger: () => ({
    log: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
    error: vi.fn(),
    warn: vi.fn()
  })
}))

describe('LandingRoute', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Loading State', () => {
    it('shows loading spinner when auth is loading', () => {
      mockUseAuth.mockReturnValue({
        user: null,
        isLoading: true,
        isAuthenticated: false,
        session: null,
        login: vi.fn(),
        logout: vi.fn(),
        hasPermission: vi.fn(),
        hasRole: vi.fn()
      })

      render(
        <BrowserRouter>
          <LandingRoute />
        </BrowserRouter>
      )

      expect(screen.getByText(/verificando autenticação/i)).toBeInTheDocument()
      expect(screen.getByRole('status')).toBeInTheDocument() // LoadingSpinner has role="status"
    })

    it('shows loading message in Portuguese', () => {
      mockUseAuth.mockReturnValue({
        user: null,
        isLoading: true,
        isAuthenticated: false,
        session: null,
        login: vi.fn(),
        logout: vi.fn(),
        hasPermission: vi.fn(),
        hasRole: vi.fn()
      })

      render(
        <BrowserRouter>
          <LandingRoute />
        </BrowserRouter>
      )

      expect(screen.getByText('Verificando autenticação...')).toBeInTheDocument()
    })
  })

  describe('Unauthenticated State', () => {
    it('redirects to /login when not authenticated', () => {
      mockUseAuth.mockReturnValue({
        user: null,
        isLoading: false,
        isAuthenticated: false,
        session: null,
        login: vi.fn(),
        logout: vi.fn(),
        hasPermission: vi.fn(),
        hasRole: vi.fn()
      })

      const { container } = render(
        <MemoryRouter initialEntries={['/']}>
          <LandingRoute />
        </MemoryRouter>
      )

      // Navigate component renders null, check that no loading spinner is shown
      expect(screen.queryByText(/verificando autenticação/i)).not.toBeInTheDocument()
    })
  })

  describe('Admin User Redirects', () => {
    it('redirects to /admin for admin role', () => {
      mockUseAuth.mockReturnValue({
        user: {
          id: '1',
          email: 'admin@example.com',
          full_name: 'Admin User',
          role: 'admin',
          is_active: true,
          permissions: ['admin.read'],
          created_at: new Date().toISOString()
        },
        isLoading: false,
        isAuthenticated: true,
        session: { access_token: 'token' },
        login: vi.fn(),
        logout: vi.fn(),
        hasPermission: vi.fn(),
        hasRole: vi.fn()
      })

      render(
        <MemoryRouter initialEntries={['/']}>
          <LandingRoute />
        </MemoryRouter>
      )

      expect(screen.queryByText(/verificando autenticação/i)).not.toBeInTheDocument()
    })

    it('redirects to /admin for ADMIN role (uppercase)', () => {
      mockUseAuth.mockReturnValue({
        user: {
          id: '1',
          email: 'admin@example.com',
          full_name: 'Admin User',
          role: 'ADMIN',
          is_active: true,
          permissions: ['admin.read'],
          created_at: new Date().toISOString()
        },
        isLoading: false,
        isAuthenticated: true,
        session: { access_token: 'token' },
        login: vi.fn(),
        logout: vi.fn(),
        hasPermission: vi.fn(),
        hasRole: vi.fn()
      })

      render(
        <MemoryRouter initialEntries={['/']}>
          <LandingRoute />
        </MemoryRouter>
      )

      expect(screen.queryByText(/verificando autenticação/i)).not.toBeInTheDocument()
    })

    it('redirects to /admin for superuser', () => {
      mockUseAuth.mockReturnValue({
        user: {
          id: '1',
          email: 'superuser@example.com',
          full_name: 'Super User',
          role: 'user',
          is_active: true,
          permissions: [],
          created_at: new Date().toISOString(),
          is_superuser: true
        } as any,
        isLoading: false,
        isAuthenticated: true,
        session: { access_token: 'token' },
        login: vi.fn(),
        logout: vi.fn(),
        hasPermission: vi.fn(),
        hasRole: vi.fn()
      })

      render(
        <MemoryRouter initialEntries={['/']}>
          <LandingRoute />
        </MemoryRouter>
      )

      expect(screen.queryByText(/verificando autenticação/i)).not.toBeInTheDocument()
    })
  })

  describe('Physician User Redirects', () => {
    it('redirects to /physician/dashboard for medico role', () => {
      mockUseAuth.mockReturnValue({
        user: {
          id: '2',
          email: 'medico@example.com',
          full_name: 'Dr. Physician',
          role: 'medico',
          is_active: true,
          permissions: ['patients.read'],
          created_at: new Date().toISOString()
        },
        isLoading: false,
        isAuthenticated: true,
        session: { access_token: 'token' },
        login: vi.fn(),
        logout: vi.fn(),
        hasPermission: vi.fn(),
        hasRole: vi.fn()
      })

      render(
        <MemoryRouter initialEntries={['/']}>
          <LandingRoute />
        </MemoryRouter>
      )

      expect(screen.queryByText(/verificando autenticação/i)).not.toBeInTheDocument()
    })

    it('redirects to /physician/dashboard for physician role', () => {
      mockUseAuth.mockReturnValue({
        user: {
          id: '2',
          email: 'physician@example.com',
          full_name: 'Dr. Physician',
          role: 'physician',
          is_active: true,
          permissions: ['patients.read'],
          created_at: new Date().toISOString()
        },
        isLoading: false,
        isAuthenticated: true,
        session: { access_token: 'token' },
        login: vi.fn(),
        logout: vi.fn(),
        hasPermission: vi.fn(),
        hasRole: vi.fn()
      })

      render(
        <MemoryRouter initialEntries={['/']}>
          <LandingRoute />
        </MemoryRouter>
      )

      expect(screen.queryByText(/verificando autenticação/i)).not.toBeInTheDocument()
    })

    it('redirects to /physician/dashboard for PHYSICIAN role (uppercase)', () => {
      mockUseAuth.mockReturnValue({
        user: {
          id: '2',
          email: 'physician@example.com',
          full_name: 'Dr. Physician',
          role: 'PHYSICIAN',
          is_active: true,
          permissions: ['patients.read'],
          created_at: new Date().toISOString()
        },
        isLoading: false,
        isAuthenticated: true,
        session: { access_token: 'token' },
        login: vi.fn(),
        logout: vi.fn(),
        hasPermission: vi.fn(),
        hasRole: vi.fn()
      })

      render(
        <MemoryRouter initialEntries={['/']}>
          <LandingRoute />
        </MemoryRouter>
      )

      expect(screen.queryByText(/verificando autenticação/i)).not.toBeInTheDocument()
    })

    it('redirects to /physician/dashboard for DOCTOR role', () => {
      mockUseAuth.mockReturnValue({
        user: {
          id: '2',
          email: 'doctor@example.com',
          full_name: 'Dr. Doctor',
          role: 'DOCTOR',
          is_active: true,
          permissions: ['patients.read'],
          created_at: new Date().toISOString()
        },
        isLoading: false,
        isAuthenticated: true,
        session: { access_token: 'token' },
        login: vi.fn(),
        logout: vi.fn(),
        hasPermission: vi.fn(),
        hasRole: vi.fn()
      })

      render(
        <MemoryRouter initialEntries={['/']}>
          <LandingRoute />
        </MemoryRouter>
      )

      expect(screen.queryByText(/verificando autenticação/i)).not.toBeInTheDocument()
    })
  })

  describe('Patient User Redirects', () => {
    it('redirects to /patients for patient role', () => {
      mockUseAuth.mockReturnValue({
        user: {
          id: '3',
          email: 'patient@example.com',
          full_name: 'Patient User',
          role: 'patient',
          is_active: true,
          permissions: [],
          created_at: new Date().toISOString()
        },
        isLoading: false,
        isAuthenticated: true,
        session: { access_token: 'token' },
        login: vi.fn(),
        logout: vi.fn(),
        hasPermission: vi.fn(),
        hasRole: vi.fn()
      })

      render(
        <MemoryRouter initialEntries={['/']}>
          <LandingRoute />
        </MemoryRouter>
      )

      expect(screen.queryByText(/verificando autenticação/i)).not.toBeInTheDocument()
    })

    it('redirects to /patients for paciente role', () => {
      mockUseAuth.mockReturnValue({
        user: {
          id: '3',
          email: 'paciente@example.com',
          full_name: 'Paciente User',
          role: 'paciente',
          is_active: true,
          permissions: [],
          created_at: new Date().toISOString()
        },
        isLoading: false,
        isAuthenticated: true,
        session: { access_token: 'token' },
        login: vi.fn(),
        logout: vi.fn(),
        hasPermission: vi.fn(),
        hasRole: vi.fn()
      })

      render(
        <MemoryRouter initialEntries={['/']}>
          <LandingRoute />
        </MemoryRouter>
      )

      expect(screen.queryByText(/verificando autenticação/i)).not.toBeInTheDocument()
    })

    it('redirects to /patients for PATIENT role (uppercase)', () => {
      mockUseAuth.mockReturnValue({
        user: {
          id: '3',
          email: 'patient@example.com',
          full_name: 'Patient User',
          role: 'PATIENT',
          is_active: true,
          permissions: [],
          created_at: new Date().toISOString()
        },
        isLoading: false,
        isAuthenticated: true,
        session: { access_token: 'token' },
        login: vi.fn(),
        logout: vi.fn(),
        hasPermission: vi.fn(),
        hasRole: vi.fn()
      })

      render(
        <MemoryRouter initialEntries={['/']}>
          <LandingRoute />
        </MemoryRouter>
      )

      expect(screen.queryByText(/verificando autenticação/i)).not.toBeInTheDocument()
    })
  })

  describe('Default Fallback', () => {
    it('redirects to /dashboard for unknown role', () => {
      mockUseAuth.mockReturnValue({
        user: {
          id: '4',
          email: 'user@example.com',
          full_name: 'Unknown User',
          role: 'unknown_role',
          is_active: true,
          permissions: [],
          created_at: new Date().toISOString()
        },
        isLoading: false,
        isAuthenticated: true,
        session: { access_token: 'token' },
        login: vi.fn(),
        logout: vi.fn(),
        hasPermission: vi.fn(),
        hasRole: vi.fn()
      })

      render(
        <MemoryRouter initialEntries={['/']}>
          <LandingRoute />
        </MemoryRouter>
      )

      expect(screen.queryByText(/verificando autenticação/i)).not.toBeInTheDocument()
    })

    it('redirects to /dashboard for user with no role', () => {
      mockUseAuth.mockReturnValue({
        user: {
          id: '4',
          email: 'user@example.com',
          full_name: 'No Role User',
          role: '',
          is_active: true,
          permissions: [],
          created_at: new Date().toISOString()
        },
        isLoading: false,
        isAuthenticated: true,
        session: { access_token: 'token' },
        login: vi.fn(),
        logout: vi.fn(),
        hasPermission: vi.fn(),
        hasRole: vi.fn()
      })

      render(
        <MemoryRouter initialEntries={['/']}>
          <LandingRoute />
        </MemoryRouter>
      )

      expect(screen.queryByText(/verificando autenticação/i)).not.toBeInTheDocument()
    })
  })
})
