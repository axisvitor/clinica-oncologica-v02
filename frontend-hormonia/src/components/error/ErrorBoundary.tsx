import React, { Component, ErrorInfo, ReactNode } from 'react';
import { ErrorFallback } from './ErrorFallback';

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
    console.error('Error Boundary caught an error:', {
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
    if (enableReporting && process.env.NODE_ENV === 'production') {
      this.reportError(error, errorInfo, level);
    }

    // Call custom error handler if provided
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  private reportError = (error: Error, errorInfo: ErrorInfo, level: string) => {
    try {
      // Report to Sentry if available
      if (typeof window !== 'undefined' && window.Sentry) {
        window.Sentry.withScope((scope) => {
          scope.setTag('errorBoundary', true);
          scope.setLevel(level === 'critical' ? 'error' : 'warning');
          scope.setContext('errorInfo', {
            componentStack: errorInfo.componentStack,
            errorBoundaryLevel: level,
            errorId: this.state.errorId
          });
          window.Sentry.captureException(error);
        });
      }

      // Send to backend error tracking
      fetch('/api/v1/errors/client', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          error: {
            message: error.message,
            stack: error.stack,
            name: error.name
          },
          errorInfo: {
            componentStack: errorInfo.componentStack
          },
          level,
          errorId: this.state.errorId,
          url: window.location.href,
          userAgent: navigator.userAgent,
          timestamp: new Date().toISOString()
        })
      }).catch(reportError => {
        console.error('Failed to report error to backend:', reportError);
      });
    } catch (reportError) {
      console.error('Error reporting failed:', reportError);
    }
  };

  handleRetry = (): void => {
    const { maxRetries = DEFAULT_MAX_RETRIES } = this.props;
    const { retryCount } = this.state;

    if (retryCount >= maxRetries) {
      console.warn('Max retries reached, not retrying');
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
          level={this.props.level}
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
export function useErrorReporting() {
  const reportError = (error: Error, context?: Record<string, any>) => {
    if (process.env.NODE_ENV === 'production' && typeof window !== 'undefined' && window.Sentry) {
      window.Sentry.withScope((scope) => {
        if (context) {
          scope.setContext('manual_report', context);
        }
        window.Sentry.captureException(error);
      });
    } else {
      console.error('Manual error report:', error, context);
    }
  };

  return { reportError };
}

export default ErrorBoundary;
