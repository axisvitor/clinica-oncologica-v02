/**
 * Loading States Component Library
 *
 * Provides state components for loading, error, empty, and success states.
 * Skeleton components are imported from the consolidated skeleton library.
 */

import React from 'react'
import { CircleAlert as AlertCircle, CircleCheck as CheckCircle, Info } from 'lucide-react'
import { Card, CardContent } from '../ui/card'
import { Alert, AlertDescription, AlertTitle } from '../ui/alert'
import { LoadingSpinner } from '../ui/loading-spinner'

// Re-export skeletons from consolidated library for backwards compatibility
export { CardSkeleton, TableSkeleton, DashboardSkeleton } from '../ui/skeleton'

interface LoadingStateProps {
  message?: string
  className?: string
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = 'Loading\u2026',
  className = ''
}) => (
  <div className={`flex flex-col items-center justify-center p-8 ${className}`}>
    <LoadingSpinner size="lg" className="mb-4" />
    <p className="text-muted-foreground">{message}</p>
  </div>
)

interface ErrorStateProps {
  error: Error | string
  onRetry?: () => void
  className?: string
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  error,
  onRetry,
  className = ''
}) => {
  const errorMessage = typeof error === 'string' ? error : error.message

  return (
    <Alert variant="destructive" className={className}>
      <AlertCircle className="h-4 w-4" />
      <AlertTitle>Error</AlertTitle>
      <AlertDescription className="flex flex-col gap-2">
        <span>{errorMessage}</span>
        {onRetry && (
          <button
            onClick={onRetry}
            className="text-sm underline hover:no-underline"
          >
            Try again
          </button>
        )}
      </AlertDescription>
    </Alert>
  )
}

interface EmptyStateProps {
  title: string
  description?: string
  action?: {
    label: string
    onClick: () => void
  }
  icon?: React.ReactNode
  className?: string
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  action,
  icon,
  className = ''
}) => (
  <Card className={className}>
    <CardContent className="flex flex-col items-center justify-center p-8 text-center">
      {icon || <Info className="h-12 w-12 text-muted-foreground mb-4" />}
      <h3 className="text-lg font-semibold mb-2">{title}</h3>
      {description && (
        <p className="text-muted-foreground mb-4">{description}</p>
      )}
      {action && (
        <button
          onClick={action.onClick}
          className="text-primary underline hover:no-underline"
        >
          {action.label}
        </button>
      )}
    </CardContent>
  </Card>
)

interface SuccessStateProps {
  title: string
  description?: string
  className?: string
}

export const SuccessState: React.FC<SuccessStateProps> = ({
  title,
  description,
  className = ''
}) => (
  <Alert className={`border-green-200 bg-green-50 ${className}`}>
    <CheckCircle className="h-4 w-4 text-green-600" />
    <AlertTitle className="text-green-900">{title}</AlertTitle>
    {description && (
      <AlertDescription className="text-green-800">
        {description}
      </AlertDescription>
    )}
  </Alert>
)

// Additional specialized components
export const ConnectionStatus: React.FC<{ isConnected: boolean }> = ({ isConnected }) => (
  <div className="flex items-center gap-2">
    <div className={`h-2 w-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
    <span className="text-sm text-muted-foreground">
      {isConnected ? 'Connected' : 'Disconnected'}
    </span>
  </div>
)

export const LoadingButton: React.FC<{ loading: boolean; children: React.ReactNode }> = ({
  loading,
  children
}) => (
  <button disabled={loading} className="relative">
    {loading && (
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
        <LoadingSpinner size="sm" />
      </div>
    )}
    <span className={loading ? 'invisible' : ''}>{children}</span>
  </button>
)

export default {
  LoadingState,
  ErrorState,
  EmptyState,
  SuccessState,
  ConnectionStatus,
  LoadingButton
}
