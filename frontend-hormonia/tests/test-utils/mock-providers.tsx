import React from 'react'
import { vi } from 'vitest'

// Mock providers and contexts for testing

// Mock AuthContext
export const mockAuthContext = {
  user: {
    id: '1',
    email: 'test@example.com',
    role: 'user',
    permissions: ['read:dashboard'],
  },
  isAuthenticated: true,
  isLoading: false,
  session: {
    access_token: 'mock-token',
    refresh_token: 'mock-refresh-token',
  },
  login: vi.fn(),
  logout: vi.fn(),
  hasRole: vi.fn().mockReturnValue(true),
  hasPermission: vi.fn().mockReturnValue(true),
}

// Mock config provider
export const mockConfig = {
  VITE_API_BASE_URL: 'http://localhost:8000',
  VITE_WS_BASE_URL: 'ws://localhost:8000/ws',
  VITE_FIREBASE_API_KEY: 'mock-api-key',
  VITE_FIREBASE_AUTH_DOMAIN: 'mock-auth-domain',
  VITE_FIREBASE_PROJECT_ID: 'mock-project-id',
}

export const mockConfigContext = {
  config: mockConfig,
  isLoading: false,
  error: null,
}

// Mock toast provider
export const mockToast = {
  toast: vi.fn(),
  dismiss: vi.fn(),
  toasts: [],
}

// Mock API client responses
export const mockApiResponses = {
  patients: {
    getAll: vi.fn().mockResolvedValue({
      data: [
        {
          id: '1',
          name: 'João Silva',
          phone: '+55 11 99999-9999',
          email: 'joao@example.com',
          treatment_type: 'Terapia Hormonal Feminina',
          status: 'active',
        },
      ],
      total: 1,
    }),
    create: vi.fn().mockResolvedValue({
      id: '2',
      name: 'Maria Santos',
      phone: '+55 11 88888-8888',
      email: 'maria@example.com',
      treatment_type: 'Terapia Hormonal Feminina',
      status: 'active',
    }),
    update: vi.fn().mockResolvedValue({
      id: '1',
      name: 'João Silva Updated',
      phone: '+55 11 99999-9999',
      email: 'joao@example.com',
      treatment_type: 'Terapia Hormonal Feminina',
      status: 'active',
    }),
    delete: vi.fn().mockResolvedValue({ success: true }),
  },
  quiz: {
    submitResponse: vi.fn().mockResolvedValue({ success: true }),
    getSession: vi.fn().mockResolvedValue({
      id: 'session-1',
      patient_id: 'patient-1',
      template_id: 'template-1',
      template_name: 'Monthly Check-up',
      status: 'active',
      responses: {},
      questions: [
        {
          id: 'q1',
          type: 'multiple_choice',
          question: 'How are you feeling?',
          options: ['Great', 'Good', 'Okay', 'Not great'],
          required: true,
        },
      ],
    }),
  },
  questionarios: {
    getAll: vi.fn().mockResolvedValue({
      data: [
        {
          id: '1',
          title: 'Monthly Check-up',
          description: 'Monthly health assessment',
          status: 'active',
          questions: [],
        },
      ],
      total: 1,
    }),
    create: vi.fn().mockResolvedValue({
      id: '2',
      title: 'New Quiz',
      description: 'New quiz description',
      status: 'active',
      questions: [],
    }),
  },
  medico: {
    getTreatmentDistribution: vi.fn().mockResolvedValue({
      distributions: [
        { treatment_type: 'Terapia Hormonal Feminina', count: 10, percentage: 50 },
        { treatment_type: 'Terapia Hormonal Masculina', count: 8, percentage: 40 },
        { treatment_type: 'Reposição Hormonal', count: 2, percentage: 10 },
      ],
      total_patients: 20,
      last_updated: '2024-01-01T00:00:00Z',
    }),
    getDashboardStats: vi.fn().mockResolvedValue({
      total_patients: 50,
      active_patients: 45,
      pending_quizzes: 12,
      completed_quizzes_today: 8,
      high_risk_patients: 3,
      recent_activities: [],
      trends: {
        patients_growth: 10.5,
        quiz_completion_rate: 85.2,
        adherence_rate: 92.1,
      },
    }),
  },
  auth: {
    login: vi.fn().mockResolvedValue({
      user: mockAuthContext.user,
      session: mockAuthContext.session,
    }),
    logout: vi.fn().mockResolvedValue({ success: true }),
    refreshToken: vi.fn().mockResolvedValue({
      access_token: 'new-token',
      refresh_token: 'new-refresh-token',
    }),
  },
}

// Mock WebSocket
export class MockWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3

  url: string
  readyState: number = MockWebSocket.CONNECTING
  onopen: ((event: Event) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null

  constructor(url: string) {
    this.url = url
    // Simulate connection success
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN
      this.onopen?.(new Event('open'))
    }, 0)
  }

  send(data: string) {
    if (this.readyState === MockWebSocket.OPEN) {
      // Simulate successful send
      return
    }
    throw new Error('WebSocket is not open')
  }

  close(code?: number, reason?: string) {
    this.readyState = MockWebSocket.CLOSED
    setTimeout(() => {
      this.onclose?.(new CloseEvent('close', { code: code || 1000, reason: reason || '' }))
    }, 0)
  }

  // Helper methods for testing
  simulateMessage(data: any) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }))
    }
  }

  simulateError() {
    if (this.onerror) {
      this.onerror(new Event('error'))
    }
  }

  simulateClose(code = 1000, reason = '') {
    this.readyState = MockWebSocket.CLOSED
    if (this.onclose) {
      this.onclose(new CloseEvent('close', { code, reason }))
    }
  }
}

// Mock logger
export const mockLogger = {
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
  debug: vi.fn(),
}

// Mock react-hook-form
export const mockUseForm = () => ({
  register: vi.fn(),
  handleSubmit: vi.fn((fn) => (e) => {
    e?.preventDefault()
    fn({})
  }),
  formState: { errors: {} },
  reset: vi.fn(),
  setValue: vi.fn(),
  watch: vi.fn(),
  control: {},
})

// Mock react-router-dom
export const mockNavigate = vi.fn()
export const mockLocation = {
  pathname: '/',
  search: '',
  hash: '',
  state: null,
  key: 'default',
}

export const mockRouter = {
  navigate: mockNavigate,
  location: mockLocation,
}

// Mock localStorage
export const mockLocalStorage = (() => {
  let store: Record<string, string> = {}

  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key]
    }),
    clear: vi.fn(() => {
      store = {}
    }),
    get store() {
      return { ...store }
    },
  }
})()

// Mock window.matchMedia
export const mockMatchMedia = (matches = false) => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation(query => ({
      matches,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
}

// Mock IntersectionObserver
export const mockIntersectionObserver = () => {
  global.IntersectionObserver = vi.fn().mockImplementation(() => ({
    observe: vi.fn(),
    unobserve: vi.fn(),
    disconnect: vi.fn(),
  }))
}

// Mock ResizeObserver
export const mockResizeObserver = () => {
  global.ResizeObserver = vi.fn().mockImplementation(() => ({
    observe: vi.fn(),
    unobserve: vi.fn(),
    disconnect: vi.fn(),
  }))
}

// Mock fetch
export const mockFetch = (response: any = {}, ok = true) => {
  global.fetch = vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 400,
    json: vi.fn().mockResolvedValue(response),
    text: vi.fn().mockResolvedValue(JSON.stringify(response)),
  })
}

// Reset all mocks
export const resetAllMocks = () => {
  vi.clearAllMocks()
  Object.values(mockApiResponses).forEach(service => {
    Object.values(service).forEach(method => {
      if (vi.isMockFunction(method)) {
        method.mockClear()
      }
    })
  })
}

// Test error scenarios
export const mockApiError = (status = 400, message = 'API Error') => ({
  status,
  data: { message },
  message,
})

export const mockNetworkError = () => new Error('Network Error')

// Performance testing helpers
export const mockPerformance = () => {
  const now = vi.fn(() => Date.now())
  Object.defineProperty(window, 'performance', {
    writable: true,
    value: { now },
  })
  return now
}

// Setup for component testing
export const setupComponentTest = () => {
  mockMatchMedia()
  mockIntersectionObserver()
  mockResizeObserver()
  mockFetch()

  // Replace WebSocket globally
  global.WebSocket = MockWebSocket as any

  // Replace localStorage
  Object.defineProperty(window, 'localStorage', {
    value: mockLocalStorage,
    writable: true,
  })
}

// Cleanup after tests
export const cleanupComponentTest = () => {
  resetAllMocks()
  vi.restoreAllMocks()
}

export default {
  mockAuthContext,
  mockConfigContext,
  mockToast,
  mockApiResponses,
  MockWebSocket,
  mockLogger,
  mockUseForm,
  mockRouter,
  mockLocalStorage,
  mockMatchMedia,
  mockIntersectionObserver,
  mockResizeObserver,
  mockFetch,
  resetAllMocks,
  mockApiError,
  mockNetworkError,
  setupComponentTest,
  cleanupComponentTest,
}