/**
 * Sentry configuration for React frontend monitoring.
 *
 * Provides comprehensive error tracking, performance monitoring, and user context
 * for the Clínica Oncológica frontend application.
 */

import * as Sentry from '@sentry/react';
import { BrowserTracing } from '@sentry/tracing';
import { CaptureConsole } from '@sentry/integrations';
import { Replay } from '@sentry/replay';
import React from 'react';
import { useLocation, useNavigationType, createRoutesFromChildren, matchRoutes } from 'react-router-dom';

// Environment configuration
const ENVIRONMENT = import.meta.env.VITE_ENVIRONMENT || 'development';
const SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN;
const SENTRY_TRACES_SAMPLE_RATE = parseFloat(import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE || '0.1');
const SENTRY_REPLAYS_SESSION_SAMPLE_RATE = parseFloat(import.meta.env.VITE_SENTRY_REPLAYS_SESSION_SAMPLE_RATE || '0.1');
const SENTRY_REPLAYS_ON_ERROR_SAMPLE_RATE = parseFloat(import.meta.env.VITE_SENTRY_REPLAYS_ON_ERROR_SAMPLE_RATE || '1.0');

interface UserContext {
  id: string;
  email?: string;
  role?: string;
  name?: string;
}

interface SessionContext {
  sessionId: string;
  startTime: string;
  userAgent: string;
  viewport: string;
}

export class SentryMonitoring {
  private static isInitialized = false;
  private static sessionContext: SessionContext | null = null;

  /**
   * Initialize Sentry SDK with comprehensive monitoring configuration
   */
  static init(): void {
    if (this.isInitialized || !SENTRY_DSN) {
      if (!SENTRY_DSN) {
        console.warn('Sentry DSN not configured. Monitoring disabled.');
      }
      return;
    }

    Sentry.init({
      dsn: SENTRY_DSN,
      environment: ENVIRONMENT,
      integrations: [
        // Browser tracing for performance monitoring
        new BrowserTracing({
          // Capture interactions as transactions
          routingInstrumentation: Sentry.reactRouterV6Instrumentation(
            React.useEffect,
            useLocation,
            useNavigationType,
            createRoutesFromChildren,
            matchRoutes
          ),
          // Track Web Vitals
          enableWebVitals: true,
          // Custom transaction names
          beforeNavigate: (context) => ({
            ...context,
            name: `${context.location.pathname}`,
            tags: {
              'route.name': context.location.pathname,
            },
          }),
        }),

        // Session replay for debugging
        new Replay({
          // Capture 10% of all sessions
          sessionSampleRate: SENTRY_REPLAYS_SESSION_SAMPLE_RATE,
          // Capture 100% of sessions with an error
          errorSampleRate: SENTRY_REPLAYS_ON_ERROR_SAMPLE_RATE,
          // Mask sensitive data
          maskAllText: true,
          maskAllInputs: true,
          blockAllMedia: true,
        }),

        // Console error capturing
        new CaptureConsole({
          levels: ['error', 'warn'],
        }),
      ],

      // Performance monitoring
      tracesSampleRate: SENTRY_TRACES_SAMPLE_RATE,

      // Error filtering
      beforeSend: this.beforeSendFilter,
      beforeSendTransaction: this.beforeSendTransactionFilter,

      // Release information
      release: import.meta.env.VITE_APP_VERSION || 'unknown',

      // Additional configuration
      maxBreadcrumbs: 50,
      attachStacktrace: true,
      autoSessionTracking: true,

      // Don't send default PII
      sendDefaultPii: false,

      // Custom error capturing
      ignoreErrors: [
        // Browser extension errors
        'top.GLOBALS',
        'originalCreateNotification',
        'canvas.contentDocument',
        'MyApp_RemoveAllHighlights',
        'http://tt.epicplay.com',
        "Can't find variable: ZiteReader",
        'jigsaw is not defined',
        'ComboSearch is not defined',
        'http://loading.retry.widdit.com/',
        'atomicFindClose',
        // Network errors that are not actionable
        'Network request failed',
        'NetworkError when attempting to fetch resource',
        'The Internet connection appears to be offline',
        'Load failed',
        // Ad blocker related
        'blocked by client',
      ],

      denyUrls: [
        // Chrome extensions
        /extensions\//i,
        /^chrome:\/\//i,
        /^chrome-extension:\/\//i,
        // Firefox extensions
        /^resource:\/\//i,
        // Safari extensions
        /^safari-extension:\/\//i,
        // Edge extensions
        /^ms-browser-extension:\/\//i,
      ],
    });

    this.isInitialized = true;
    this.initializeSessionContext();
    console.log(`Sentry initialized for environment: ${ENVIRONMENT}`);
  }

  /**
   * Filter events before sending to Sentry
   */
  private static beforeSendFilter(event: Sentry.Event, hint: Sentry.EventHint): Sentry.Event | null {
    // Skip development errors that are not actionable
    if (ENVIRONMENT === 'development') {
      const error = hint.originalException;
      if (error instanceof Error) {
        // Skip HMR and development-only errors
        if (error.message.includes('Loading chunk') ||
            error.message.includes('Loading CSS chunk')) {
          return null;
        }
      }
    }

    // Add custom tags
    event.tags = {
      ...event.tags,
      component: 'frontend-react',
      service: 'clinica-oncologica',
    };

    // Add session context if available
    if (this.sessionContext) {
      event.contexts = {
        ...event.contexts,
        session: this.sessionContext,
      };
    }

    return event;
  }

  /**
   * Filter performance transactions before sending
   */
  private static beforeSendTransactionFilter(event: Sentry.Event): Sentry.Event | null {
    // Skip very fast transactions in production
    if (ENVIRONMENT === 'production') {
      const duration = (event.timestamp || 0) - (event.start_timestamp || 0);
      if (duration < 0.1) { // Skip transactions under 100ms
        return null;
      }
    }

    // Add custom tags
    event.tags = {
      ...event.tags,
      transaction_type: 'frontend',
    };

    return event;
  }

  /**
   * Initialize session context for tracking
   */
  private static initializeSessionContext(): void {
    this.sessionContext = {
      sessionId: crypto.randomUUID(),
      startTime: new Date().toISOString(),
      userAgent: navigator.userAgent,
      viewport: `${window.innerWidth}x${window.innerHeight}`,
    };

    Sentry.setContext('session', this.sessionContext);
  }

  /**
   * Set user context for error tracking
   */
  static setUserContext(user: UserContext): void {
    Sentry.setUser({
      id: user.id,
      email: user.email,
      username: user.name,
      role: user.role,
    });

    Sentry.setTag('user_role', user.role || 'unknown');
    Sentry.addBreadcrumb({
      message: 'User context updated',
      category: 'auth',
      level: 'info',
      data: {
        userId: user.id,
        role: user.role,
      },
    });
  }

  /**
   * Clear user context on logout
   */
  static clearUserContext(): void {
    Sentry.setUser(null);
    Sentry.addBreadcrumb({
      message: 'User logged out',
      category: 'auth',
      level: 'info',
    });
  }

  /**
   * Track page views and navigation
   */
  static trackPageView(pageName: string, additionalData?: Record<string, any>): void {
    Sentry.addBreadcrumb({
      message: `Navigation to ${pageName}`,
      category: 'navigation',
      level: 'info',
      data: {
        page: pageName,
        timestamp: new Date().toISOString(),
        ...additionalData,
      },
    });

    Sentry.setTag('current_page', pageName);
  }

  /**
   * Track business events and user interactions
   */
  static trackEvent(eventName: string, data: Record<string, any> = {}): void {
    Sentry.addBreadcrumb({
      message: `Event: ${eventName}`,
      category: 'user_action',
      level: 'info',
      data: {
        event: eventName,
        timestamp: new Date().toISOString(),
        ...data,
      },
    });
  }

  /**
   * Track form interactions and validation errors
   */
  static trackFormError(formName: string, field: string, error: string): void {
    Sentry.captureMessage(`Form validation error in ${formName}`, {
      level: 'warning',
      tags: {
        form_name: formName,
        field_name: field,
        error_type: 'validation',
      },
      extra: {
        form: formName,
        field,
        error,
        timestamp: new Date().toISOString(),
      },
    });
  }

  /**
   * Track API call failures with context
   */
  static trackApiError(endpoint: string, method: string, status: number, error: string): void {
    Sentry.captureMessage(`API Error: ${method} ${endpoint}`, {
      level: 'error',
      tags: {
        api_endpoint: endpoint,
        http_method: method,
        http_status: status.toString(),
        error_type: 'api',
      },
      extra: {
        endpoint,
        method,
        status,
        error,
        timestamp: new Date().toISOString(),
      },
    });
  }

  /**
   * Track clinical dashboard interactions
   */
  static trackClinicalDashboard(action: string, componentName: string, metadata?: Record<string, any>): void {
    this.trackEvent('clinical_dashboard_interaction', {
      action,
      component: componentName,
      ...metadata,
    });

    Sentry.setContext('clinical_context', {
      last_action: action,
      component: componentName,
      timestamp: new Date().toISOString(),
      ...metadata,
    });
  }

  /**
   * Track patient data access for audit purposes
   */
  static trackPatientDataAccess(dataType: string, accessLevel: string, patientId?: string): void {
    Sentry.addBreadcrumb({
      message: `Patient data access: ${dataType}`,
      category: 'data_access',
      level: 'info',
      data: {
        data_type: dataType,
        access_level: accessLevel,
        patient_id: patientId ? '[REDACTED]' : undefined, // Don't log actual patient ID
        timestamp: new Date().toISOString(),
      },
    });

    Sentry.setTag('last_data_access', dataType);
  }

  /**
   * Track performance metrics manually
   */
  static trackPerformance(metricName: string, value: number, unit: string = 'ms'): void {
    Sentry.addBreadcrumb({
      message: `Performance metric: ${metricName}`,
      category: 'performance',
      level: 'info',
      data: {
        metric: metricName,
        value,
        unit,
        timestamp: new Date().toISOString(),
      },
    });
  }

  /**
   * Capture custom exception with context
   */
  static captureException(error: Error, context?: Record<string, any>): string {
    return Sentry.captureException(error, {
      extra: context,
      tags: {
        error_source: 'frontend',
        ...(context?.tags || {}),
      },
    });
  }

  /**
   * Start a custom transaction for performance monitoring
   */
  static startTransaction(name: string, op: string = 'custom'): Sentry.Transaction {
    return Sentry.startTransaction({
      name,
      op,
      tags: {
        transaction_source: 'frontend',
      },
    });
  }

  /**
   * Get current session information
   */
  static getSessionInfo(): SessionContext | null {
    return this.sessionContext;
  }

  /**
   * Check if Sentry is properly initialized
   */
  static isConfigured(): boolean {
    return this.isInitialized && !!SENTRY_DSN;
  }
}

// Export Sentry components for React integration
export const {
  ErrorBoundary,
  withErrorBoundary,
  captureException,
  captureMessage,
  withSentryConfig,
} = Sentry;

// Initialize Sentry when module is imported
SentryMonitoring.init();