import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { AuthProvider, useAuth, AUTH_LOCK_TIMEOUT_MS } from '@/app/providers/AuthContext'

const mockFirebaseAuth = vi.hoisted(() => ({
  onAuthStateChanged: vi.fn(),
  onIdTokenChanged: vi.fn(),
  getCurrentUser: vi.fn(),
  setPersistence: vi.fn(),
  signOut: vi.fn(),
  isConfigured: vi.fn().mockReturnValue(true)
}))

const mockApiClient = vi.hoisted(() => ({
  fetchCsrfToken: vi.fn().mockResolvedValue(undefined),
  setAuthToken: vi.fn(),
  clearAuthToken: vi.fn(),
  auth: {
    checkAuth: vi.fn().mockResolvedValue({ authenticated: false }),
    me: vi.fn().mockResolvedValue({ data: null })
  },
  dashboard: {
    getMain: vi.fn().mockResolvedValue({})
  }
}))

const mockWsManager = vi.hoisted(() => ({
  connect: vi.fn().mockResolvedValue(undefined),
  disconnect: vi.fn(),
  updateToken: vi.fn()
}))

const mockFirebaseAuthService = vi.hoisted(() => ({
  loginUser: vi.fn(),
  logoutUser: vi.fn(),
  logoutAllDevices: vi.fn(),
  setSessionId: vi.fn(),
  clearSessionId: vi.fn()
}))

vi.mock('@/lib/firebase-lazy', () => ({
  firebaseAuthLazy: mockFirebaseAuth
}))

vi.mock('@/lib/api-client', () => ({
  apiClient: mockApiClient
}))

vi.mock('@/lib/websocket', () => ({
  wsManager: mockWsManager
}))

vi.mock('@/services/firebase-auth', () => mockFirebaseAuthService)

vi.mock('@/hooks/use-toast', () => ({
  toast: vi.fn()
}))

vi.mock('@/config/mock.config', () => ({
  isMockAuthEnabled: vi.fn().mockReturnValue(false)
}))

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <AuthProvider>{children}</AuthProvider>
)

const mockUser = {
  id: 'user-123',
  email: 'test@example.com',
  full_name: 'Test User',
  role: 'admin',
  is_active: true,
  permissions: ['users:read'],
  created_at: '2024-01-01T00:00:00-03:00'
}

const mockFirebaseUser = {
  uid: 'firebase-123',
  email: 'test@example.com',
  getIdToken: vi.fn().mockResolvedValue('firebase-token')
}

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('Race Condition Prevention', () => {
  let authStateHandler: ((user: any) => Promise<void>) | null

  beforeEach(() => {
    vi.clearAllMocks()
    authStateHandler = null

    mockApiClient.auth.checkAuth.mockResolvedValue({ authenticated: false })
    mockApiClient.auth.me.mockResolvedValue({ data: mockUser })

    mockFirebaseAuth.onAuthStateChanged.mockImplementation(async (handler) => {
      authStateHandler = handler
      return vi.fn()
    })

    mockFirebaseAuth.onIdTokenChanged.mockImplementation(async () => vi.fn())
    mockFirebaseAuth.getCurrentUser.mockResolvedValue(mockFirebaseUser)
    mockFirebaseAuth.setPersistence.mockResolvedValue(undefined)

    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: vi.fn(),
        setItem: vi.fn(),
        removeItem: vi.fn(),
        clear: vi.fn()
      },
      configurable: true
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('Login + onAuthStateChanged simultaneos nao criam dupla sessao', async () => {
    const deferred = createDeferred<{ user: typeof mockUser; session_id: string }>()
    mockFirebaseAuthService.loginUser.mockReturnValue(deferred.promise)

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(mockFirebaseAuth.onAuthStateChanged).toHaveBeenCalled()
    })

    let loginPromise: Promise<void> | undefined
    act(() => {
      loginPromise = result.current.login('test@example.com', 'password123')
    })

    await act(async () => {
      await authStateHandler?.(mockFirebaseUser)
    })

    deferred.resolve({ user: mockUser, session_id: 'session-1' })

    await act(async () => {
      if (loginPromise) {
        await loginPromise
      }
    })

    expect(mockFirebaseAuthService.loginUser).toHaveBeenCalledTimes(1)
    expect(mockApiClient.auth.me).not.toHaveBeenCalled()
  })

  it('onAuthStateChanged ignora eventos durante login ativo', async () => {
    const deferred = createDeferred<{ user: typeof mockUser; session_id: string }>()
    mockFirebaseAuthService.loginUser.mockReturnValue(deferred.promise)

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(mockFirebaseAuth.onAuthStateChanged).toHaveBeenCalled()
    })

    let loginPromise: Promise<void> | undefined
    act(() => {
      loginPromise = result.current.login('test@example.com', 'password123')
    })

    await act(async () => {
      await authStateHandler?.(mockFirebaseUser)
    })

    expect(mockApiClient.auth.me).not.toHaveBeenCalled()

    deferred.resolve({ user: mockUser, session_id: 'session-1' })
    if (loginPromise) {
      await act(async () => {
        await loginPromise
      })
    }
  })

  it('onAuthStateChanged processa eventos apos lock expirar', async () => {
    const deferred = createDeferred<{ user: typeof mockUser; session_id: string }>()
    mockFirebaseAuthService.loginUser.mockReturnValue(deferred.promise)

    const nowSpy = vi.spyOn(Date, 'now')
    nowSpy.mockReturnValue(0)

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(mockFirebaseAuth.onAuthStateChanged).toHaveBeenCalled()
    })

    let loginPromise: Promise<void> | undefined
    act(() => {
      loginPromise = result.current.login('test@example.com', 'password123')
    })

    nowSpy.mockReturnValue(AUTH_LOCK_TIMEOUT_MS + 1)
    await act(async () => {
      await authStateHandler?.(mockFirebaseUser)
    })

    expect(mockApiClient.auth.me).toHaveBeenCalled()

    deferred.resolve({ user: mockUser, session_id: 'session-1' })
    if (loginPromise) {
      await act(async () => {
        await loginPromise
      })
    }
  })
})

describe('Lock Timeout Scenarios', () => {
  let authStateHandler: ((user: any) => Promise<void>) | null

  beforeEach(() => {
    vi.clearAllMocks()
    authStateHandler = null

    mockApiClient.auth.checkAuth.mockResolvedValue({ authenticated: false })
    mockApiClient.auth.me.mockResolvedValue({ data: mockUser })

    mockFirebaseAuth.onAuthStateChanged.mockImplementation(async (handler) => {
      authStateHandler = handler
      return vi.fn()
    })

    mockFirebaseAuth.onIdTokenChanged.mockImplementation(async () => vi.fn())
    mockFirebaseAuth.getCurrentUser.mockResolvedValue(mockFirebaseUser)
    mockFirebaseAuth.setPersistence.mockResolvedValue(undefined)

    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: vi.fn(),
        setItem: vi.fn(),
        removeItem: vi.fn(),
        clear: vi.fn()
      },
      configurable: true
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('Login falha sem limpar lock - timeout previne deadlock', async () => {
    const firstLogin = createDeferred<{ user: typeof mockUser; session_id: string }>()
    mockFirebaseAuthService.loginUser
      .mockReturnValueOnce(firstLogin.promise)
      .mockResolvedValueOnce({ user: mockUser, session_id: 'session-2' })

    const nowSpy = vi.spyOn(Date, 'now')
    nowSpy.mockReturnValue(0)

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(mockFirebaseAuth.onAuthStateChanged).toHaveBeenCalled()
    })

    act(() => {
      result.current.login('test@example.com', 'password123')
    })

    nowSpy.mockReturnValue(AUTH_LOCK_TIMEOUT_MS + 100)

    await expect(result.current.login('test@example.com', 'password123')).resolves.toBeUndefined()
    expect(mockFirebaseAuthService.loginUser).toHaveBeenCalledTimes(2)

    firstLogin.resolve({ user: mockUser, session_id: 'session-1' })
    await act(async () => {
      await authStateHandler?.(mockFirebaseUser)
    })
  })
})
