/**
 * Sentry configuration for React frontend monitoring.
 *
 * Provides comprehensive error tracking, performance monitoring, and user context
 * for the Clínica Oncológica frontend application.
 *
 * Sentry packages installed:
 * - @sentry/react - Core React integration, tracing, replay, and integrations
 */

import * as Sentry from '@sentry/react'
import { createLogger } from '@/lib/logger'

// Note: In Sentry v10+, BrowserTracing and Replay are included in @sentry/react
// CaptureConsole is available via Sentry.captureConsoleIntegration()

const logger = createLogger('Sentry')
type MeasurementUnit = Parameters<typeof Sentry.setMeasurement>[2]
type SentryInitOptions = Parameters<typeof Sentry.init>[0]
type BeforeSend = NonNullable<SentryInitOptions['beforeSend']>
type BeforeSendTransaction = NonNullable<SentryInitOptions['beforeSendTransaction']>

interface UserContext {
  id: string
  email?: string
  role?: string
  name?: string
}

interface SessionContext {
  sessionId: string
  startTime: string
  userAgent: string
  viewport: string
}

export class SentryMonitoring {
  private static isInitialized = false
  private static sessionContext: SessionContext | null = null

  /**
   * Initialize Sentry SDK with comprehensive monitoring configuration
   */
  static init(): void {
    const SENTRY_DSN = import.meta.env['VITE_SENTRY_DSN']
    const ENVIRONMENT = import.meta.env['VITE_ENVIRONMENT'] || 'development'

    if (this.isInitialized) {
      logger.debug('Sentry already initialized')
      return
    }

    if (!SENTRY_DSN) {
      logger.warn('Sentry DSN not configured. Monitoring disabled.')
      return
    }

    const SENTRY_TRACES_SAMPLE_RATE = parseFloat(
      import.meta.env['VITE_SENTRY_TRACES_SAMPLE_RATE'] || '0.1'
    )
    const SENTRY_REPLAYS_SESSION_SAMPLE_RATE = parseFloat(
      import.meta.env['VITE_SENTRY_REPLAYS_SESSION_SAMPLE_RATE'] || '0.1'
    )
    const SENTRY_REPLAYS_ON_ERROR_SAMPLE_RATE = parseFloat(
      import.meta.env['VITE_SENTRY_REPLAYS_ON_ERROR_SAMPLE_RATE'] || '1.0'
    )

    try {
      Sentry.init({
        dsn: SENTRY_DSN,
        environment: ENVIRONMENT,
        integrations: [
          // Sentry v10+ API - integrations are now factory functions
          Sentry.browserTracingIntegration({
            enableInp: true,
          }),
          Sentry.replayIntegration({
            maskAllText: true,
            maskAllInputs: true,
            blockAllMedia: true,
          }),
          Sentry.captureConsoleIntegration({
            levels: ['error', 'warn'],
          }),
        ],
        tracePropagationTargets: ['localhost', /^https:\/\/[^/]*\.railway\.app/],
        tracesSampleRate: SENTRY_TRACES_SAMPLE_RATE,
        replaysSessionSampleRate: SENTRY_REPLAYS_SESSION_SAMPLE_RATE,
        replaysOnErrorSampleRate: SENTRY_REPLAYS_ON_ERROR_SAMPLE_RATE,
        beforeSend: this.beforeSendFilter,
        beforeSendTransaction: this.beforeSendTransactionFilter,
        release: import.meta.env['VITE_APP_VERSION'] || 'unknown',
        maxBreadcrumbs: 50,
        attachStacktrace: true,
        sendDefaultPii: false,
        ignoreErrors: [
          'top.GLOBALS',
          'originalCreateNotification',
          'canvas.contentDocument',
          'MyApp_RemoveAllHighlights',
          'http://tt.epicplay.com',
          "Can't find variable: ZiteReader",
        ],
        denyUrls: [
          /extensions\//i,
          /^chrome:\/\//i,
          /^chrome-extension:\/\//i,
          /^resource:\/\//i,
          /^safari-extension:\/\//i,
          /^ms-browser-extension:\/\//i,
        ],
      })

      this.isInitialized = true
      this.initializeSessionContext()
      logger.info(`Sentry initialized for environment: ${ENVIRONMENT}`)
    } catch (error) {
      logger.error('Failed to initialize Sentry:', error)
    }
  }

  /**
   * Filter events before sending to Sentry
   */
  private static beforeSendFilter: BeforeSend = (event, _hint) => {
    // Filter out development errors if in production
    if (event.environment === 'production' && event.level === 'debug') {
      return null
    }

    // Redact sensitive data from event
    if (event.request?.headers) {
      delete event.request.headers['Authorization']
      delete event.request.headers['Cookie']
    }

    return event
  }

  /**
   * Filter transactions before sending to Sentry
   */
  private static beforeSendTransactionFilter: BeforeSendTransaction = (event, _hint) => {
    // Filter out very short transactions (noise)
    if (event.start_timestamp && event.timestamp) {
      const duration = event.timestamp - event.start_timestamp
      if (duration < 0.01) {
        // Less than 10ms
        return null
      }
    }

    return event
  }

  /**
   * Set user context for error tracking
   */
  static setUserContext(user: UserContext): void {
    if (!this.isInitialized) {
      logger.debug('Sentry not initialized, skipping user context')
      return
    }

    try {
      Sentry.setUser({
        id: user.id,
        email: user.email,
        username: user.name,
        role: user.role,
      })
      logger.debug('User context set successfully')
    } catch (error) {
      logger.error('Failed to set user context:', error)
    }
  }

  /**
   * Clear user context on logout
   */
  static clearUserContext(): void {
    if (!this.isInitialized) {
      logger.debug('Sentry not initialized, skipping clear user context')
      return
    }

    try {
      Sentry.setUser(null)
      logger.debug('User context cleared successfully')
    } catch (error) {
      logger.error('Failed to clear user context:', error)
    }
  }

  /**
   * Track page views and navigation
   */
  static trackPageView(pageName: string, additionalData?: Record<string, unknown>): void {
    if (!this.isInitialized) return

    try {
      Sentry.addBreadcrumb({
        category: 'navigation',
        message: `Page view: ${pageName}`,
        level: 'info',
        data: additionalData,
      })
    } catch (error) {
      logger.error('Failed to track page view:', error)
    }
  }

  /**
   * Track business events and user interactions
   */
  static trackEvent(eventName: string, data: Record<string, unknown> = {}): void {
    if (!this.isInitialized) return

    try {
      Sentry.addBreadcrumb({
        category: 'user-interaction',
        message: eventName,
        level: 'info',
        data,
      })
    } catch (error) {
      logger.error('Failed to track event:', error)
    }
  }

  /**
   * Track form interactions and validation errors
   */
  static trackFormError(formName: string, field: string, error: string): void {
    if (!this.isInitialized) return

    try {
      Sentry.addBreadcrumb({
        category: 'validation',
        message: `Form error in ${formName}`,
        level: 'warning',
        data: { formName, field, error },
      })
    } catch (err) {
      logger.error('Failed to track form error:', err)
    }
  }

  /**
   * Track API call failures with context
   */
  static trackApiError(endpoint: string, method: string, status: number, error: string): void {
    if (!this.isInitialized) return

    try {
      Sentry.captureMessage(`API Error: ${method} ${endpoint}`, {
        level: 'error',
        tags: {
          endpoint,
          method,
          status: status.toString(),
        },
        extra: { error },
      })
    } catch (err) {
      logger.error('Failed to track API error:', err)
    }
  }

  /**
   * Track clinical dashboard interactions
   */
  static trackClinicalDashboard(
    action: string,
    componentName: string,
    metadata?: Record<string, unknown>
  ): void {
    if (!this.isInitialized) return

    try {
      Sentry.addBreadcrumb({
        category: 'clinical-dashboard',
        message: `${action} in ${componentName}`,
        level: 'info',
        data: metadata,
      })
    } catch (error) {
      logger.error('Failed to track clinical dashboard interaction:', error)
    }
  }

  /**
   * Track patient data access for audit purposes (HIPAA compliance)
   */
  static trackPatientDataAccess(dataType: string, accessLevel: string, patientId?: string): void {
    if (!this.isInitialized) return

    try {
      // Never log actual patient ID to Sentry for privacy
      Sentry.addBreadcrumb({
        category: 'patient-data-access',
        message: `Accessed ${dataType}`,
        level: 'info',
        data: {
          dataType,
          accessLevel,
          hasPatientId: !!patientId,
        },
      })
    } catch (error) {
      logger.error('Failed to track patient data access:', error)
    }
  }

  /**
   * Track performance metrics manually
   */
  static trackPerformance(metricName: string, value: number, unit: MeasurementUnit = 'ms'): void {
    if (!this.isInitialized) return

    try {
      Sentry.setMeasurement(metricName, value, unit)
    } catch (error) {
      logger.error('Failed to track performance metric:', error)
    }
  }

  /**
   * Capture custom exception with context
   */
  static captureException(error: Error, context?: Record<string, unknown>): string {
    if (!this.isInitialized) {
      logger.error('Exception (Sentry disabled):', error, context)
      return 'sentry-disabled'
    }

    try {
      const eventId = Sentry.captureException(error, { extra: context })
      return eventId
    } catch (err) {
      logger.error('Failed to capture exception:', err)
      return 'capture-failed'
    }
  }

  /**
   * Start a custom span for performance monitoring (Sentry v10+ API)
   * @deprecated Use Sentry.startSpan() directly for new code
   */
  static startTransaction(name: string, op: string = 'custom'): { finish: () => void } | null {
    if (!this.isInitialized) return null

    try {
      // Sentry v10+ uses startSpan instead of startTransaction
      // Return a compatible interface for backwards compatibility
      const spanRef = { finished: false }

      Sentry.startSpan({ name, op }, () => {
        // Span is automatically finished when callback completes
        spanRef.finished = true
      })

      return {
        finish: () => {
          // No-op since span is auto-finished in v10
          if (!spanRef.finished) {
            logger.debug(`Span ${name} finish called`)
          }
        },
      }
    } catch (error) {
      logger.error('Failed to start span:', error)
      return null
    }
  }

  /**
   * Get current session information
   */
  static getSessionInfo(): SessionContext | null {
    return this.sessionContext
  }

  /**
   * Check if Sentry is properly initialized
   */
  static isConfigured(): boolean {
    return this.isInitialized
  }

  private static initializeSessionContext(): void {
    this.sessionContext = {
      sessionId: crypto.randomUUID(),
      startTime: new Date().toISOString(),
      userAgent: navigator.userAgent,
      viewport: `${window.innerWidth}x${window.innerHeight}`,
    }

    // Set session context in Sentry
    if (this.isInitialized) {
      const sessionContext: Record<string, unknown> = { ...this.sessionContext }
      Sentry.setContext('session', sessionContext)
    }
  }
}

// Export Sentry components for React integration
export const ErrorBoundary = Sentry.ErrorBoundary
export const withErrorBoundary = Sentry.withErrorBoundary
export const captureException = (error: Error, context?: Record<string, unknown>) =>
  SentryMonitoring.captureException(error, context)
export const captureMessage = (message: string, level: Sentry.SeverityLevel = 'info') =>
  Sentry.captureMessage(message, level)

// Initialize Sentry when module is imported
SentryMonitoring.init()
