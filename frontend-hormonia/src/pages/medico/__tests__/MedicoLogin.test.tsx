import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { BrowserRouter } from 'react-router-dom'
import MedicoLogin from '../MedicoLogin'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

const mockSignIn = vi.fn()
const mockSignOut = vi.fn()
const mockAuthState = {
  isAuthenticated: false,
  isLoading: false,
  error: null as string | null,
  medico: null,
}

vi.mock('@/app/providers/MedicoAuthContext', () => ({
  useMedicoAuth: () => ({
    ...mockAuthState,
    signIn: mockSignIn,
    signOut: mockSignOut,
  }),
}))

describe('MedicoLogin', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockAuthState.isAuthenticated = false
    mockAuthState.isLoading = false
    mockAuthState.error = null
    mockAuthState.medico = null
    mockSignIn.mockResolvedValue({ success: true })
  })

  const renderLoginPage = () => {
    return render(
      <BrowserRouter>
        <MedicoLogin />
      </BrowserRouter>,
    )
  }

  it('calls signIn with CRM and password on submit', async () => {
    renderLoginPage()

    fireEvent.change(screen.getByLabelText(/CRM/i), { target: { value: '12345' } })
    fireEvent.change(screen.getByLabelText(/Senha/i), { target: { value: 'password123' } })
    fireEvent.click(screen.getByRole('button', { name: /Entrar/i }))

    await waitFor(() => {
      expect(mockSignIn).toHaveBeenCalledWith('12345', 'password123', false)
    })
    expect(mockSignIn).toHaveBeenCalledTimes(1)
  })

  it('navigates to dashboard after successful login', async () => {
    mockSignIn.mockResolvedValue({ success: true })

    renderLoginPage()

    fireEvent.change(screen.getByLabelText(/CRM/i), { target: { value: '12345' } })
    fireEvent.change(screen.getByLabelText(/Senha/i), { target: { value: 'password123' } })
    fireEvent.click(screen.getByRole('button', { name: /Entrar/i }))

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/medico/dashboard')
    })
  })

  it('shows signIn error and does not navigate when login fails', async () => {
    mockSignIn.mockResolvedValue({
      success: false,
      error: 'CRM ou senha incorretos',
    })

    renderLoginPage()

    fireEvent.change(screen.getByLabelText(/CRM/i), { target: { value: '99999' } })
    fireEvent.change(screen.getByLabelText(/Senha/i), { target: { value: 'wrongpass' } })
    fireEvent.click(screen.getByRole('button', { name: /Entrar/i }))

    await waitFor(() => {
      expect(screen.getByText(/CRM ou senha incorretos/i)).toBeInTheDocument()
    })
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('validates CRM format before calling signIn', async () => {
    renderLoginPage()

    fireEvent.change(screen.getByLabelText(/CRM/i), { target: { value: '123' } })
    fireEvent.change(screen.getByLabelText(/Senha/i), { target: { value: 'password123' } })
    fireEvent.click(screen.getByRole('button', { name: /Entrar/i }))

    await waitFor(() => {
      expect(screen.getByText(/CRM deve conter 4-7 dígitos/i)).toBeInTheDocument()
    })
    expect(mockSignIn).not.toHaveBeenCalled()
  })

  it('validates password length before calling signIn', async () => {
    renderLoginPage()

    fireEvent.change(screen.getByLabelText(/CRM/i), { target: { value: '12345' } })
    fireEvent.change(screen.getByLabelText(/Senha/i), { target: { value: '123' } })
    fireEvent.click(screen.getByRole('button', { name: /Entrar/i }))

    await waitFor(() => {
      expect(screen.getByText(/Senha deve ter no mínimo 6 caracteres/i)).toBeInTheDocument()
    })
    expect(mockSignIn).not.toHaveBeenCalled()
  })

  it('shows loading state while auth is initializing', () => {
    mockAuthState.isLoading = true

    renderLoginPage()

    const submitButton = screen.getByRole('button', { name: /Autenticando/i })
    expect(submitButton).toBeDisabled()
  })

  it('redirects immediately when already authenticated', async () => {
    mockAuthState.isAuthenticated = true

    renderLoginPage()

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/medico/dashboard')
    })
  })

  it('renders context error message when available', () => {
    mockAuthState.error = 'Sessão expirada'

    renderLoginPage()

    expect(screen.getByText(/Sessão expirada/i)).toBeInTheDocument()
  })
})
