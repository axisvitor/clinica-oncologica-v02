import React from 'react'
import { Loader as Loader2, CircleAlert as AlertCircle, CircleCheck as CheckCircle, Info } from 'lucide-react'
import { Card, CardContent } from '../ui/card'
import { Alert, AlertDescription, AlertTitle } from '../ui/alert'

interface LoadingStateProps {
  message?: string
  className?: string
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = 'Loading...',
  className = ''
}) => (
  <div className={`flex flex-col items-center justify-center p-8 ${className}`}>
    <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
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

// Skeleton loaders for specific components
export const TableSkeleton: React.FC<{ rows?: number }> = ({ rows = 5 }) => (
  <div className="space-y-2">
    <div className="h-10 bg-gray-200 rounded animate-pulse" />
    {Array.from({ length: rows }).map((_, i) => (
      <div key={i} className="h-16 bg-gray-100 rounded animate-pulse" />
    ))}
  </div>
)

export const CardSkeleton: React.FC = () => (
  <Card>
    <CardContent className="p-6">
      <div className="space-y-3">
        <div className="h-4 bg-gray-200 rounded w-3/4 animate-pulse" />
        <div className="h-4 bg-gray-200 rounded w-1/2 animate-pulse" />
        <div className="h-4 bg-gray-200 rounded w-5/6 animate-pulse" />
      </div>
    </CardContent>
  </Card>
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

export const DashboardSkeleton: React.FC = () => (
  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
    {Array.from({ length: 4 }).map((_, i) => (
      <CardSkeleton key={i} />
    ))}
  </div>
)

export const LoadingButton: React.FC<{ loading: boolean; children: React.ReactNode }> = ({
  loading,
  children
}) => (
  <button disabled={loading} className="relative">
    {loading && (
      <Loader2 className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-4 w-4 animate-spin" />
    )}
    <span className={loading ? 'invisible' : ''}>{children}</span>
  </button>
)

export default {
  LoadingState,
  ErrorState,
  EmptyState,
  SuccessState,
  TableSkeleton,
  CardSkeleton,
  ConnectionStatus,
  DashboardSkeleton,
  LoadingButton
}