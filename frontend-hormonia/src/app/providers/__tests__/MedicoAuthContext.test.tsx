import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useMedicoAuth } from '../MedicoAuthContext'
import { useAuth } from '../AuthContext'

vi.mock('../AuthContext', () => ({
  useAuth: vi.fn(),
}))

type MockAuthValue = {
  user: {
    full_name?: string
    name?: string
    crm?: string
  } | null
  isInitializing: boolean
  login: ReturnType<typeof vi.fn>
  logout: ReturnType<typeof vi.fn>
}

const mockUseAuth = vi.mocked(useAuth)
const mockLogin = vi.fn()
const mockLogout = vi.fn()

const setupAuthMock = (overrides: Partial<MockAuthValue> = {}) => {
  const value: MockAuthValue = {
    user: null,
    isInitializing: false,
    login: mockLogin,
    logout: mockLogout,
    ...overrides,
  }

  mockUseAuth.mockReturnValue(value as ReturnType<typeof useAuth>)
}

describe('useMedicoAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupAuthMock()
  })

  it('exposes explicit auth fields with unauthenticated defaults', () => {
    const { result } = renderHook(() => useMedicoAuth())

    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.isLoading).toBe(false)
    expect(result.current.error).toBeNull()
    expect(result.current.medico).toBeNull()
    expect(typeof result.current.signIn).toBe('function')
    expect(typeof result.current.signOut).toBe('function')
    expect('state' in (result.current as unknown as Record<string, unknown>)).toBe(false)
  })

  it('maps AuthContext user data to medico profile', () => {
    setupAuthMock({
      user: {
        full_name: 'Dr. Meredith Grey',
        crm: '12345',
      },
      isInitializing: true,
    })

    const { result } = renderHook(() => useMedicoAuth())

    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.isLoading).toBe(true)
    expect(result.current.medico).toEqual({
      full_name: 'Dr. Meredith Grey',
      crm: '12345',
    })
  })

  it('uses name as fallback when full_name is not available', () => {
    setupAuthMock({
      user: {
        name: 'Dr. Gregory House',
      },
    })

    const { result } = renderHook(() => useMedicoAuth())

    expect(result.current.medico).toEqual({
      full_name: 'Dr. Gregory House',
      crm: '',
    })
  })

  it('calls login through signIn and returns success', async () => {
    mockLogin.mockResolvedValue(undefined)

    const { result } = renderHook(() => useMedicoAuth())

    let response: { success: boolean; error?: string } | undefined
    await act(async () => {
      response = await result.current.signIn('12345', 'senha123')
    })

    expect(mockLogin).toHaveBeenCalledWith('12345', 'senha123', false)
    expect(response).toEqual({ success: true })
  })

  it('returns mapped error when login fails', async () => {
    mockLogin.mockRejectedValue(new Error('Credenciais inválidas'))

    const { result } = renderHook(() => useMedicoAuth())

    let response: { success: boolean; error?: string } | undefined
    await act(async () => {
      response = await result.current.signIn('12345', 'senha-errada', true)
    })

    expect(mockLogin).toHaveBeenCalledWith('12345', 'senha-errada', true)
    expect(response).toEqual({
      success: false,
      error: 'Credenciais inválidas',
    })
  })

  it('calls logout through signOut and returns success', async () => {
    mockLogout.mockResolvedValue(undefined)

    const { result } = renderHook(() => useMedicoAuth())

    let response: { success: boolean } | undefined
    await act(async () => {
      response = await result.current.signOut()
    })

    expect(mockLogout).toHaveBeenCalledTimes(1)
    expect(response).toEqual({ success: true })
  })
})
