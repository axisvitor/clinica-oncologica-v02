import { vi } from 'vitest'
import { User as FirebaseUser } from 'firebase/auth'

/**
 * Test Utilities and Helpers for Phase 4 Testing
 */

// ==================== Mock Data Factories ====================

export const createMockFirebaseUser = (overrides?: Partial<FirebaseUser>): FirebaseUser => {
  return {
    uid: 'test-uid-123',
    email: 'test@example.com',
    emailVerified: true,
    displayName: 'Test User',
    photoURL: null,
    phoneNumber: null,
    isAnonymous: false,
    tenantId: null,
    providerData: [],
    metadata: {
      creationTime: new Date().toISOString(),
      lastSignInTime: new Date().toISOString(),
    },
    refreshToken: 'mock-refresh-token',
    getIdToken: vi.fn().mockResolvedValue('mock-id-token'),
    getIdTokenResult: vi.fn().mockResolvedValue({
      token: 'mock-id-token',
      claims: {},
      authTime: new Date().toISOString(),
      issuedAtTime: new Date().toISOString(),
      expirationTime: new Date(Date.now() + 3600000).toISOString(),
      signInProvider: 'password',
      signInSecondFactor: null,
    }),
    reload: vi.fn().mockResolvedValue(undefined),
    toJSON: vi.fn().mockReturnValue({}),
    delete: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  } as FirebaseUser
}

export const createMockAdminUser = (): FirebaseUser => {
  return createMockFirebaseUser({
    uid: 'admin-uid-123',
    email: 'admin@hormonia.com',
    displayName: 'Admin User',
    getIdTokenResult: vi.fn().mockResolvedValue({
      token: 'mock-admin-token',
      claims: { admin: true, role: 'admin' },
      authTime: new Date().toISOString(),
      issuedAtTime: new Date().toISOString(),
      expirationTime: new Date(Date.now() + 3600000).toISOString(),
      signInProvider: 'password',
      signInSecondFactor: null,
    }),
  })
}

export const createMockSystemStats = () => ({
  total_patients: 100,
  active_patients: 75,
  messages_today: 45,
  alerts_pending: 12,
  active_patients_percentage: 75.0,
  response_rate: 92.5,
  messages_sent: 450,
  completed_quizzes: 89,
  patients_change: 5.2,
  active_patients_change: 3.8,
  messages_change: -2.1,
  alerts_change: 15.0,
  recent_messages: [
    {
      id: '1',
      patient_name: 'João Silva',
      content: 'Consulta agendada para amanhã',
      timestamp: '2025-10-10T10:30:00-03:00',
    },
    {
      id: '2',
      patient_name: 'Maria Santos',
      content: 'Dúvida sobre medicação',
      timestamp: '2025-10-10T09:15:00-03:00',
    },
  ],
  recent_alerts: [
    {
      id: '1',
      patient_name: 'Maria Santos',
      severity: 'high',
      message: 'Alerta de medicação vencida',
      timestamp: '2025-10-10T11:00:00-03:00',
    },
    {
      id: '2',
      patient_name: 'Pedro Costa',
      severity: 'medium',
      message: 'Lembrete de consulta',
      timestamp: '2025-10-10T08:30:00-03:00',
    },
  ],
  recent_quiz_completions: [
    {
      id: '1',
      patient_name: 'Pedro Costa',
      quiz_name: 'Avaliação Mensal de Outubro',
      score: 85,
      completed_at: '2025-10-10T09:00:00-03:00',
    },
    {
      id: '2',
      patient_name: 'Ana Lima',
      quiz_name: 'Questionário de Bem-Estar',
      score: 92,
      completed_at: '2025-10-09T16:45:00-03:00',
    },
  ],
  engagement_chart: [
    { date: '2025-10-01', value: 78 },
    { date: '2025-10-02', value: 82 },
    { date: '2025-10-03', value: 85 },
    { date: '2025-10-04', value: 80 },
    { date: '2025-10-05', value: 88 },
    { date: '2025-10-06', value: 90 },
    { date: '2025-10-07', value: 87 },
  ],
  alert_severity_chart: [
    { severity: 'high', count: 5 },
    { severity: 'medium', count: 15 },
    { severity: 'low', count: 30 },
  ],
  treatment_progress_chart: [
    { week: 1, completed: 45, pending: 20 },
    { week: 2, completed: 50, pending: 15 },
    { week: 3, completed: 55, pending: 10 },
    { week: 4, completed: 60, pending: 5 },
  ],
})

// ==================== Test Wrappers ====================

export const createAuthContextValue = (overrides?: any) => ({
  user: null,
  isAuthenticated: false,
  isLoading: false,
  isAdmin: false,
  login: vi.fn(),
  logout: vi.fn(),
  logoutAll: vi.fn(),
  ...overrides,
})

// ==================== Mock API Responses ====================

export const mockApiSuccess = <T>(data: T) => Promise.resolve(data)

export const mockApiError = (message: string, code = 500) =>
  Promise.reject(new Error(message))

export const mockFirebaseAuthSuccess = (user: FirebaseUser) =>
  Promise.resolve({ user })

export const mockFirebaseAuthError = (code: string, message: string) =>
  Promise.reject({
    code: `auth/${code}`,
    message,
  })

// ==================== Time Utilities ====================

export const waitForAsync = (ms = 0) =>
  new Promise((resolve) => setTimeout(resolve, ms))

export const advanceTimersByTime = async (ms: number) => {
  vi.advanceTimersByTime(ms)
  await waitForAsync(0)
}

// ==================== DOM Utilities ====================

export const expectElementToBeVisible = async (element: Element | null) => {
  expect(element).toBeInTheDocument()
  expect(element).toBeVisible()
}

export const expectElementToBeHidden = (element: Element | null) => {
  expect(element).not.toBeInTheDocument()
}

// ==================== LocalStorage Utilities ====================

export const mockLocalStorage = () => {
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
      Object.keys(store).forEach((key) => delete store[key])
    }),
    get store() {
      return { ...store }
    },
  }
}

// ==================== Firebase Mock Utilities ====================

export const mockFirebaseAuth = () => ({
  currentUser: null,
  onAuthStateChanged: vi.fn((callback) => {
    callback(null)
    return vi.fn() // unsubscribe
  }),
  signInWithEmailAndPassword: vi.fn(),
  signOut: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  sendPasswordResetEmail: vi.fn(),
  updateProfile: vi.fn(),
})

// ==================== API Client Mock Utilities ====================

export const mockApiClient = () => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
})

// ==================== Toast Mock Utilities ====================

export const mockToast = () => ({
  toast: vi.fn(),
})

// ==================== Router Mock Utilities ====================

export const mockRouter = () => ({
  navigate: vi.fn(),
  location: { pathname: '/', search: '', hash: '', state: null },
  params: {},
})

// ==================== Assert Helpers ====================

export const assertAuthStateChange = (
  authState: any,
  expected: { isAuthenticated: boolean; isAdmin: boolean; user: any }
) => {
  expect(authState.isAuthenticated).toBe(expected.isAuthenticated)
  expect(authState.isAdmin).toBe(expected.isAdmin)
  if (expected.user) {
    expect(authState.user).toMatchObject(expected.user)
  } else {
    expect(authState.user).toBeNull()
  }
}

export const assertApiCall = (
  mockFn: any,
  endpoint: string,
  params?: any
) => {
  expect(mockFn).toHaveBeenCalledWith(endpoint, params)
}

export const assertLocalStorageSet = (
  localStorage: any,
  key: string,
  value: string
) => {
  expect(localStorage.setItem).toHaveBeenCalledWith(key, value)
}

export const assertLocalStorageRemoved = (
  localStorage: any,
  key: string
) => {
  expect(localStorage.removeItem).toHaveBeenCalledWith(key)
}

// ==================== Test Data Builders ====================

export class UserBuilder {
  private user: Partial<FirebaseUser> = {}

  withEmail(email: string) {
    this.user.email = email
    return this
  }

  withUid(uid: string) {
    this.user.uid = uid
    return this
  }

  withDisplayName(displayName: string) {
    this.user.displayName = displayName
    return this
  }

  asAdmin() {
    this.user.getIdTokenResult = vi.fn().mockResolvedValue({
      claims: { admin: true },
    })
    return this
  }

  build(): FirebaseUser {
    return createMockFirebaseUser(this.user)
  }
}

export class SystemStatsBuilder {
  private stats: any = createMockSystemStats()

  withPatients(total: number, active: number) {
    this.stats.total_patients = total
    this.stats.active_patients = active
    this.stats.active_patients_percentage = (active / total) * 100
    return this
  }

  withMessages(today: number, total: number) {
    this.stats.messages_today = today
    this.stats.messages_sent = total
    return this
  }

  withAlerts(pending: number) {
    this.stats.alerts_pending = pending
    return this
  }

  withTrends(
    patients: number,
    activePatients: number,
    messages: number,
    alerts: number
  ) {
    this.stats.patients_change = patients
    this.stats.active_patients_change = activePatients
    this.stats.messages_change = messages
    this.stats.alerts_change = alerts
    return this
  }

  build() {
    return this.stats
  }
}

// ==================== Export Builders ====================

export const builders = {
  user: () => new UserBuilder(),
  stats: () => new SystemStatsBuilder(),
}
