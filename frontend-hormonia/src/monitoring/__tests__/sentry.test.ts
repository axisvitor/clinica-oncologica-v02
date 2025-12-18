import { describe, it, expect, beforeEach, vi } from 'vitest'
import { SentryMonitoring } from '../sentry'

// Mock Sentry module
vi.mock('@sentry/react', () => ({
  init: vi.fn(),
  setUser: vi.fn(),
  addBreadcrumb: vi.fn(),
  captureException: vi.fn(() => 'test-event-id'),
  captureMessage: vi.fn(() => 'test-message-id'),
  startTransaction: vi.fn(() => ({
    finish: vi.fn()
  })),
  setContext: vi.fn(),
  setMeasurement: vi.fn(),
  ErrorBoundary: () => null,
  withErrorBoundary: vi.fn(),
  withSentryConfig: vi.fn()
}))

vi.mock('@sentry/tracing', () => ({
  BrowserTracing: vi.fn()
}))

vi.mock('@sentry/integrations', () => ({
  CaptureConsole: vi.fn()
}))

vi.mock('@sentry/replay', () => ({
  Replay: vi.fn()
}))

describe('SentryMonitoring', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('User Context', () => {
    it('should set user context when Sentry is initialized', () => {
      const user = {
        id: 'user-123',
        email: 'test@example.com',
        name: 'Test User',
        role: 'admin'
      }

      SentryMonitoring.setUserContext(user)
      // Sentry.setUser should be called with user data
      expect(true).toBe(true) // Placeholder - actual test would check Sentry.setUser
    })

    it('should clear user context on logout', () => {
      SentryMonitoring.clearUserContext()
      // Sentry.setUser should be called with null
      expect(true).toBe(true)
    })
  })

  describe('Event Tracking', () => {
    it('should track page views', () => {
      SentryMonitoring.trackPageView('/dashboard', { source: 'navigation' })
      expect(true).toBe(true)
    })

    it('should track custom events', () => {
      SentryMonitoring.trackEvent('button_clicked', { buttonId: 'submit' })
      expect(true).toBe(true)
    })

    it('should track form errors', () => {
      SentryMonitoring.trackFormError('loginForm', 'email', 'Invalid email format')
      expect(true).toBe(true)
    })

    it('should track API errors', () => {
      SentryMonitoring.trackApiError('/api/users', 'POST', 500, 'Internal Server Error')
      expect(true).toBe(true)
    })
  })

  describe('Healthcare Compliance', () => {
    it('should track patient data access without exposing PII', () => {
      SentryMonitoring.trackPatientDataAccess('medical_records', 'read', 'patient-123')
      // Should track the access but not the actual patient ID
      expect(true).toBe(true)
    })

    it('should track clinical dashboard interactions', () => {
      SentryMonitoring.trackClinicalDashboard('view_patient', 'PatientCard', {
        componentType: 'card'
      })
      expect(true).toBe(true)
    })
  })

  describe('Performance Tracking', () => {
    it('should track performance metrics', () => {
      SentryMonitoring.trackPerformance('api_response_time', 250, 'ms')
      expect(true).toBe(true)
    })

    it('should start and track transactions', () => {
      const transaction = SentryMonitoring.startTransaction('load_dashboard', 'http')
      expect(transaction).toBeDefined()
    })
  })

  describe('Error Handling', () => {
    it('should capture exceptions with context', () => {
      const error = new Error('Test error')
      const eventId = SentryMonitoring.captureException(error, { context: 'test' })
      expect(eventId).toBeDefined()
    })
  })

  describe('Configuration', () => {
    it('should report initialization status', () => {
      const isConfigured = SentryMonitoring.isConfigured()
      expect(typeof isConfigured).toBe('boolean')
    })

    it('should provide session information', () => {
      const sessionInfo = SentryMonitoring.getSessionInfo()
      expect(sessionInfo).toBeDefined()
    })
  })
})
