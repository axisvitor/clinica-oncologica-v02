/**
 * Error Boundary Components
 * Global error handling for React applications
 */

export {
  ErrorBoundary,
  withErrorBoundary,
  useErrorReporting,
  useErrorHandler,
  SimpleErrorFallback,
} from './ErrorBoundary'
export { ErrorFallback } from './ErrorFallback'
export type { ErrorBoundaryProps } from './ErrorBoundary'
export type { ErrorFallbackProps } from './ErrorFallback'

// Re-export types
export type { ErrorInfo } from 'react'
