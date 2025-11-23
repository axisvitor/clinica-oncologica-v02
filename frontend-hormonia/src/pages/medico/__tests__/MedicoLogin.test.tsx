/**
 * Test Suite for MedicoLogin Page
 *
 * Tests:
 * - Form submission uses signIn (not fetch)
 * - Successful login navigates to dashboard
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { BrowserRouter } from 'react-router-dom'
import MedicoLogin from '../MedicoLogin'
import type { MedicoLoginResponse } from '@/types/medico'

// Mock react-router-dom navigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate
  }
})

// Mock MedicoAuthContext
const mockSignIn = vi.fn()
const mockAuthState = {
  isAuthenticated: false,
  isLoading: false,
  error: null,
  user: null
}

vi.mock('../../../contexts/MedicoAuthContext', async () => {
  const actual = await vi.importActual('../../../contexts/MedicoAuthContext')
  return {
    ...actual,
    useMedicoAuth: () => ({
      state: mockAuthState,
      signIn: mockSignIn,
      signOut: vi.fn(),
      refreshToken: vi.fn(),
      extendSession: vi.fn(),
      updatePerfil: vi.fn(),
      getPacientesAtribuidos: vi.fn()
    })
  }
})

describe('MedicoLogin', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockAuthState.isAuthenticated = false
    mockAuthState.isLoading = false
    mockAuthState.error = null
  })

  const renderLoginPage = () => {
    return render(
      <BrowserRouter>
        <MedicoLogin />
      </BrowserRouter>
    )
  }

  describe('Form Submission', () => {
    it('should use signIn method (not fetch) on form submission', async () => {
      // Setup
      const mockResponse: MedicoLoginResponse = {
        success: true,
        user: {
          id: 'test-uid',
          email: '12345@medico.local',
          full_name: 'Dr. Test',
          role: 'doctor',
          crm: '12345',
          especialidade: 'Oncologia',
          conselho_regional: 'CRM-SC',
          pacientes_atribuidos: [],
          is_active: true,
          permissions: [],
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          last_login: new Date().toISOString(),
          login_count: 0,
          two_factor_enabled: false,
          failed_login_attempts: 0,
          locked_until: null
        },
        token: 'test-token-abc123',
        refreshToken: 'test-refresh-token',
        redirectTo: '/medico/dashboard'
      }

      mockSignIn.mockResolvedValue(mockResponse)

      // Render
      renderLoginPage()

      // Fill form
      const crmInput = screen.getByLabelText(/CRM/i)
      const passwordInput = screen.getByLabelText(/Senha/i)
      const submitButton = screen.getByRole('button', { name: /Entrar/i })

      fireEvent.change(crmInput, { target: { value: '12345' } })
      fireEvent.change(passwordInput, { target: { value: 'password123' } })

      // Submit form
      fireEvent.click(submitButton)

      // Verify signIn was called (NOT fetch)
      await waitFor(() => {
        expect(mockSignIn).toHaveBeenCalledTimes(1)
      })

      // Verify signIn was called with correct arguments
      expect(mockSignIn).toHaveBeenCalledWith(
        '12345@medico.local', // email constructed from CRM
        'password123',        // password
        false                 // rememberMe default
      )

      // Verify fetch was NOT called
      expect(global.fetch).not.toHaveBeenCalled()
    })

    it('should construct email from CRM before calling signIn', async () => {
      // Setup
      mockSignIn.mockResolvedValue({
        success: true,
        token: 'test-token',
        refreshToken: 'refresh-token',
        redirectTo: '/medico/dashboard'
      })

      // Render
      renderLoginPage()

      // Fill form with CRM only (no @ symbol)
      const crmInput = screen.getByLabelText(/CRM/i)
      const passwordInput = screen.getByLabelText(/Senha/i)

      fireEvent.change(crmInput, { target: { value: '54321' } })
      fireEvent.change(passwordInput, { target: { value: 'testpass' } })

      // Submit
      const submitButton = screen.getByRole('button', { name: /Entrar/i })
      fireEvent.click(submitButton)

      // Verify email was constructed correctly: CRM@medico.local
      await waitFor(() => {
        expect(mockSignIn).toHaveBeenCalledWith(
          '54321@medico.local',
          'testpass',
          false
        )
      })
    })

    it('should not call fetch API directly', async () => {
      // Spy on fetch
      const fetchSpy = vi.spyOn(global, 'fetch')

      mockSignIn.mockResolvedValue({
        success: true,
        token: 'test-token',
        redirectTo: '/medico/dashboard'
      })

      // Render
      renderLoginPage()

      // Fill and submit form
      fireEvent.change(screen.getByLabelText(/CRM/i), { target: { value: '12345' } })
      fireEvent.change(screen.getByLabelText(/Senha/i), { target: { value: 'pass' } })
      fireEvent.click(screen.getByRole('button', { name: /Entrar/i }))

      await waitFor(() => {
        expect(mockSignIn).toHaveBeenCalled()
      })

      // Verify fetch was NEVER called
      expect(fetchSpy).not.toHaveBeenCalled()

      fetchSpy.mockRestore()
    })
  })

  describe('Navigation on Successful Login', () => {
    it('should navigate to /medico/dashboard on successful login', async () => {
      // Setup
      mockSignIn.mockResolvedValue({
        success: true,
        user: {
          id: 'test-uid',
          email: '12345@medico.local',
          full_name: 'Dr. Test',
          role: 'doctor',
          crm: '12345',
          especialidade: 'Oncologia',
          conselho_regional: 'CRM-SC',
          pacientes_atribuidos: [],
          is_active: true,
          permissions: [],
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          last_login: new Date().toISOString(),
          login_count: 0,
          two_factor_enabled: false,
          failed_login_attempts: 0,
          locked_until: null
        },
        token: 'valid-token',
        refreshToken: 'valid-refresh-token',
        redirectTo: '/medico/dashboard'
      })

      // Render
      renderLoginPage()

      // Fill and submit form
      fireEvent.change(screen.getByLabelText(/CRM/i), { target: { value: '12345' } })
      fireEvent.change(screen.getByLabelText(/Senha/i), { target: { value: 'password' } })
      fireEvent.click(screen.getByRole('button', { name: /Entrar/i }))

      // Verify navigation occurred
      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/medico/dashboard')
      })
    })

    it('should not navigate on failed login', async () => {
      // Setup - simulate login failure
      mockSignIn.mockResolvedValue({
        success: false,
        error: 'Invalid credentials'
      })

      // Render
      renderLoginPage()

      // Fill and submit form
      fireEvent.change(screen.getByLabelText(/CRM/i), { target: { value: 'wrong' } })
      fireEvent.change(screen.getByLabelText(/Senha/i), { target: { value: 'wrong' } })
      fireEvent.click(screen.getByRole('button', { name: /Entrar/i }))

      // Wait for error to appear
      await waitFor(() => {
        expect(screen.getByText(/Invalid credentials/i)).toBeInTheDocument()
      })

      // Verify navigation did NOT occur
      expect(mockNavigate).not.toHaveBeenCalled()
    })

    it('should display error message on failed login', async () => {
      // Setup
      mockSignIn.mockResolvedValue({
        success: false,
        error: 'CRM ou senha incorretos'
      })

      // Render
      renderLoginPage()

      // Fill and submit form
      fireEvent.change(screen.getByLabelText(/CRM/i), { target: { value: '99999' } })
      fireEvent.change(screen.getByLabelText(/Senha/i), { target: { value: 'wrongpass' } })
      fireEvent.click(screen.getByRole('button', { name: /Entrar/i }))

      // Verify error message appears
      await waitFor(() => {
        expect(screen.getByText(/CRM ou senha incorretos/i)).toBeInTheDocument()
      })

      // Verify still on login page (no navigation)
      expect(mockNavigate).not.toHaveBeenCalled()
    })
  })

  describe('Form Validation', () => {
    it('should validate CRM format before submission', async () => {
      // Render
      renderLoginPage()

      // Fill with invalid CRM (too short)
      fireEvent.change(screen.getByLabelText(/CRM/i), { target: { value: '123' } })
      fireEvent.change(screen.getByLabelText(/Senha/i), { target: { value: 'password' } })

      // Try to submit
      fireEvent.click(screen.getByRole('button', { name: /Entrar/i }))

      // Verify validation error appears
      await waitFor(() => {
        expect(screen.getByText(/CRM deve conter 4-7 dígitos/i)).toBeInTheDocument()
      })

      // Verify signIn was NOT called due to validation failure
      expect(mockSignIn).not.toHaveBeenCalled()
    })

    it('should validate password is not empty', async () => {
      // Render
      renderLoginPage()

      // Fill CRM but leave password empty
      fireEvent.change(screen.getByLabelText(/CRM/i), { target: { value: '12345' } })

      // Try to submit
      fireEvent.click(screen.getByRole('button', { name: /Entrar/i }))

      // Verify validation error appears
      await waitFor(() => {
        expect(screen.getByText(/Senha é obrigatória/i)).toBeInTheDocument()
      })

      // Verify signIn was NOT called
      expect(mockSignIn).not.toHaveBeenCalled()
    })

    it('should validate password minimum length', async () => {
      // Render
      renderLoginPage()

      // Fill with short password
      fireEvent.change(screen.getByLabelText(/CRM/i), { target: { value: '12345' } })
      fireEvent.change(screen.getByLabelText(/Senha/i), { target: { value: '123' } })

      // Try to submit
      fireEvent.click(screen.getByRole('button', { name: /Entrar/i }))

      // Verify validation error
      await waitFor(() => {
        expect(screen.getByText(/Senha deve ter no mínimo 6 caracteres/i)).toBeInTheDocument()
      })

      expect(mockSignIn).not.toHaveBeenCalled()
    })
  })

  describe('Loading State', () => {
    it('should disable submit button when loading', async () => {
      // Setup - make signIn take time
      mockSignIn.mockImplementation(() => new Promise(resolve => setTimeout(resolve, 1000)))
      mockAuthState.isLoading = true

      // Render
      renderLoginPage()

      // Submit button should be disabled
      const submitButton = screen.getByRole('button', { name: /Autenticando/i })
      expect(submitButton).toBeDisabled()
    })

    it('should show loading text during authentication', async () => {
      // Setup
      mockAuthState.isLoading = true

      // Render
      renderLoginPage()

      // Verify loading text appears
      expect(screen.getByText(/Autenticando/i)).toBeInTheDocument()
    })
  })

  describe('Auto-redirect when already authenticated', () => {
    it('should redirect to dashboard if already authenticated', async () => {
      // Setup - user already logged in
      mockAuthState.isAuthenticated = true

      // Render
      renderLoginPage()

      // Verify navigation to dashboard occurred
      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/medico/dashboard')
      })
    })
  })
})
