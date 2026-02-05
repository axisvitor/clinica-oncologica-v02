import React, { Component, ErrorInfo, ReactNode } from 'react';
import { ErrorFallback } from './ErrorFallback';
import { logger } from '@/lib/logger';
import { apiClient } from '@/lib/api-client';

export interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  level?: 'page' | 'component' | 'critical';
  maxRetries?: number;
  enableReporting?: boolean;
}

interface Props extends ErrorBoundaryProps {}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  errorId: string | null;
  retryCount: number;
}

const DEFAULT_MAX_RETRIES = 3;
const RETRY_DELAY = 1000;

/**
 * Enhanced Error Boundary Component with production features
 * Catches unhandled errors in the component tree and displays a fallback UI
 *
 * Features:
 * - Automatic retry with exponential backoff
 * - Error reporting to monitoring services
 * - Different severity levels
 * - Production-safe error display
 *
 * @example
 * ```tsx
 * <ErrorBoundary level="critical" maxRetries={3}>
 *   <App />
 * </ErrorBoundary>
 * ```
 */
export class ErrorBoundary extends Component<Props, State> {
  private retryTimeoutId: NodeJS.Timeout | null = null;

  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: null,
      retryCount: 0,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    // Generate unique error ID for tracking
    const errorId = `ERR_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    // Update state so the next render will show the fallback UI
    return {
      hasError: true,
      error,
      errorId
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    const { level = 'component', enableReporting = true } = this.props;

    // Log error details for debugging
    logger.error('Error Boundary caught an error', {
      error,
      errorInfo,
      componentStack: errorInfo.componentStack,
      timestamp: new Date().toISOString(),
      level,
      errorId: this.state.errorId
    });

    // Update state with error details
    this.setState({
      errorInfo,
    });

    // Report error in production
    if (enableReporting && process.env['NODE_ENV'] === 'production') {
      this.reportError(error, errorInfo, level);
    }

    // Call custom error handler if provided
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  private reportError = (error: Error, errorInfo: ErrorInfo, level: string) => {
    // Type definition for Sentry on window
    interface SentryScope {
      setTag: (key: string, value: string | boolean) => void;
      setLevel: (level: string) => void;
      setContext: (name: string, context: Record<string, unknown>) => void;
    }
    interface SentryInstance {
      withScope: (callback: (scope: SentryScope) => void) => void;
      captureException: (error: Error) => void;
    }
    type WindowWithSentry = Window & typeof globalThis & { Sentry?: SentryInstance };

    try {
      // Report to Sentry if available
      const windowWithSentry = window as WindowWithSentry;
      if (typeof window !== 'undefined' && windowWithSentry.Sentry) {
        windowWithSentry.Sentry.withScope((scope: SentryScope) => {
          scope.setTag('errorBoundary', true);
          scope.setLevel(level === 'critical' ? 'error' : 'warning');
          scope.setContext('errorInfo', {
            componentStack: errorInfo.componentStack,
            errorBoundaryLevel: level,
            errorId: this.state.errorId
          });
          windowWithSentry.Sentry?.captureException(error);
        });
      }

      // Send to backend error tracking
      const payload = {
        error: {
          message: error.message,
          stack: error.stack,
          name: error.name,
        },
        errorInfo: {
          componentStack: errorInfo.componentStack,
        },
        level,
        errorId: this.state.errorId,
        url: window.location.href,
        userAgent: navigator.userAgent,
        timestamp: new Date().toISOString(),
      };

      void apiClient
        .request("/api/v2/errors/client", {
          method: "POST",
          body: JSON.stringify(payload),
        })
        .catch(reportError => {
          logger.error("Failed to report error to backend", reportError);
        });
    } catch (reportError) {
      logger.error('Error reporting failed', reportError);
    }
  };

  handleRetry = (): void => {
    const { maxRetries = DEFAULT_MAX_RETRIES } = this.props;
    const { retryCount } = this.state;

    if (retryCount >= maxRetries) {
      logger.warn('Max retries reached, not retrying');
      return;
    }

    this.setState({
      retryCount: retryCount + 1
    });

    // Clear any existing timeout
    if (this.retryTimeoutId) {
      clearTimeout(this.retryTimeoutId);
    }

    // Retry after delay with exponential backoff
    this.retryTimeoutId = setTimeout(() => {
      this.setState({
        hasError: false,
        error: null,
        errorInfo: null
      });
    }, RETRY_DELAY * (retryCount + 1));
  };

  handleReset = (): void => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: null,
      retryCount: 0,
    });

    // Reload the page to ensure clean state
    window.location.reload();
  };

  componentWillUnmount(): void {
    if (this.retryTimeoutId) {
      clearTimeout(this.retryTimeoutId);
    }
  }

  render(): ReactNode {
    if (this.state.hasError) {
      const { maxRetries = DEFAULT_MAX_RETRIES } = this.props;
      const { retryCount } = this.state;

      // Use custom fallback if provided
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Use enhanced fallback UI with retry functionality
      return (
        <ErrorFallback
          error={this.state.error}
          errorInfo={this.state.errorInfo}
          errorId={this.state.errorId}
          level={this.props.level || 'component'}
          retryCount={retryCount}
          maxRetries={maxRetries}
          onReset={this.handleReset}
          onRetry={this.handleRetry}
        />
      );
    }

    return this.props.children;
  }
}

// Higher-order component for easier use
// eslint-disable-next-line react-refresh/only-export-components
export function withErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  errorBoundaryProps?: Omit<ErrorBoundaryProps, 'children'>
) {
  const WrappedComponent = (props: P) => (
    <ErrorBoundary {...errorBoundaryProps}>
      <Component {...props} />
    </ErrorBoundary>
  );

  WrappedComponent.displayName = `withErrorBoundary(${Component.displayName || Component.name})`;
  return WrappedComponent;
}

// Hook for reporting errors manually
// eslint-disable-next-line react-refresh/only-export-components
export function useErrorReporting() {
  // Type definition for Sentry on window
  interface SentryScope {
    setContext: (name: string, context: Record<string, unknown>) => void;
  }
  interface SentryInstance {
    withScope: (callback: (scope: SentryScope) => void) => void;
    captureException: (error: Error) => void;
  }
  type WindowWithSentry = Window & typeof globalThis & { Sentry?: SentryInstance };

  const reportError = (error: Error, context?: Record<string, unknown>) => {
    const windowWithSentry = window as WindowWithSentry;
    if (process.env['NODE_ENV'] === 'production' && typeof window !== 'undefined' && windowWithSentry.Sentry) {
      windowWithSentry.Sentry.withScope((scope: SentryScope) => {
        if (context) {
          scope.setContext('manual_report', context);
        }
        windowWithSentry.Sentry?.captureException(error);
      });
    } else {
      logger.error('Manual error report', { error, context });
    }
  };

  return { reportError };
}

// Legacy hook for compatibility (alias for useErrorReporting)
// eslint-disable-next-line react-refresh/only-export-components
export function useErrorHandler() {
  const { reportError } = useErrorReporting();

  return (error: Error, errorInfo?: React.ErrorInfo) => {
    logger.error('Manual error handler triggered:', {
      error: error.message,
      stack: error.stack,
      errorInfo
    });

    if (process.env['NODE_ENV'] === 'production') {
      reportError(error, { errorInfo });
    }
  };
}

// Simple error fallback component for inline use
export function SimpleErrorFallback({
  error,
  resetError
}: {
  error: Error;
  resetError: () => void;
}) {
  return (
    <div className="text-center py-8">
      <div className="w-12 h-12 text-red-500 mx-auto mb-4">
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      </div>
      <h3 className="text-lg font-medium text-gray-900 mb-2">
        Algo deu errado
      </h3>
      <p className="text-gray-600 mb-4">
        {error.message}
      </p>
      <button
        onClick={resetError}
        className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
      >
        Tentar novamente
      </button>
    </div>
  );
}

export default ErrorBoundary;
