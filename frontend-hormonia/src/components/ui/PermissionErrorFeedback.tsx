/**
 * Permission Error Feedback Components
 *
 * React components for displaying user-friendly error messages
 * related to authentication, authorization, and RLS violations.
 *
 * Features:
 * - RLS violation messages
 * - Authentication error displays
 * - Permission denied feedback
 * - Actionable error dialogs
 * - Toast notifications for errors
 */

import React from 'react'
import { AlertCircle, Lock, ShieldX, RefreshCw, ExternalLink, ArrowLeft } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from './alert'
import { Button } from './button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './card'
import { UserFriendlyError, AuthErrorType, createUserFriendlyError } from '../../lib/auth-error-handler'

interface PermissionErrorProps {
  error: UserFriendlyError
  onAction?: (action: string) => void
  className?: string
  variant?: 'alert' | 'card' | 'full-page'
  showActions?: boolean
}

/**
 * Generic permission error component that can be styled as alert, card, or full page
 */
export function PermissionError({
  error,
  onAction,
  className = '',
  variant = 'alert',
  showActions = true
}: PermissionErrorProps) {
  const getIcon = () => {
    switch (error.type) {
      case AuthErrorType.RLS_VIOLATION:
      case AuthErrorType.INSUFFICIENT_PERMISSIONS:
        return <ShieldX className="h-5 w-5" />
      case AuthErrorType.AUTHENTICATION_REQUIRED:
      case AuthErrorType.SESSION_EXPIRED:
        return <Lock className="h-5 w-5" />
      default:
        return <AlertCircle className="h-5 w-5" />
    }
  }

  const getVariant = () => {
    switch (error.type) {
      case AuthErrorType.RLS_VIOLATION:
      case AuthErrorType.INSUFFICIENT_PERMISSIONS:
        return 'destructive'
      case AuthErrorType.AUTHENTICATION_REQUIRED:
      case AuthErrorType.SESSION_EXPIRED:
        return 'default'
      default:
        return 'default'
    }
  }

  const handleAction = (action: string) => {
    if (onAction) {
      onAction(action)
    } else {
      // Default actions
      switch (action) {
        case 'sign_in':
          window.location.href = '/login'
          break
        case 'go_back':
          window.history.back()
          break
        case 'retry':
          window.location.reload()
          break
        case 'contact_support':
          // Open support modal or redirect to support page
          window.open('/support', '_blank')
          break
        default:
          console.log('Action not handled:', action)
      }
    }
  }

  const renderActions = () => {
    if (!showActions || !error.actions) return null

    return (
      <div className="flex gap-2 mt-4">
        {error.actions.primary && (
          <Button
            onClick={() => handleAction(error.actions!.primary!.action)}
            variant="default"
            size="sm"
          >
            {error.actions.primary.label}
          </Button>
        )}
        {error.actions.secondary && (
          <Button
            onClick={() => handleAction(error.actions!.secondary!.action)}
            variant="outline"
            size="sm"
          >
            {error.actions.secondary.label}
          </Button>
        )}
      </div>
    )
  }

  if (variant === 'card') {
    return (
      <Card className={`max-w-md mx-auto ${className}`}>
        <CardHeader className="pb-4">
          <div className="flex items-center gap-2">
            {getIcon()}
            <CardTitle className="text-lg">{error.title}</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <CardDescription className="mb-4">
            {error.message}
          </CardDescription>
          {renderActions()}
        </CardContent>
      </Card>
    )
  }

  if (variant === 'full-page') {
    return (
      <div className={`min-h-[50vh] flex items-center justify-center ${className}`}>
        <div className="text-center max-w-md mx-auto p-6">
          <div className="flex justify-center mb-4">
            <div className="p-3 bg-red-100 dark:bg-red-900/20 rounded-full">
              {getIcon()}
            </div>
          </div>
          <h1 className="text-2xl font-bold mb-2">{error.title}</h1>
          <p className="text-muted-foreground mb-6">{error.message}</p>
          {renderActions()}
        </div>
      </div>
    )
  }

  // Default alert variant
  return (
    <Alert variant={getVariant() as any} className={className}>
      {getIcon()}
      <AlertTitle>{error.title}</AlertTitle>
      <AlertDescription>
        {error.message}
        {renderActions()}
      </AlertDescription>
    </Alert>
  )
}

/**
 * Specific component for RLS violations
 */
export function RLSViolationError({
  resource,
  action,
  onContactSupport,
  onGoBack,
  className = ''
}: {
  resource?: string
  action?: string
  onContactSupport?: () => void
  onGoBack?: () => void
  className?: string
}) {
  const contextMessage = resource && action
    ? `You don't have permission to ${action} ${resource}.`
    : "You don't have permission to perform this action."

  const error: UserFriendlyError = {
    type: AuthErrorType.RLS_VIOLATION,
    title: 'Access Denied',
    message: `${contextMessage} Please contact your administrator if you believe this is an error.`,
    actionable: true,
    retryable: false,
    actions: {
      primary: {
        label: 'Contact Support',
        action: 'contact_support'
      },
      secondary: {
        label: 'Go Back',
        action: 'go_back'
      }
    }
  }

  return (
    <PermissionError
      error={error}
      onAction={(action) => {
        switch (action) {
          case 'contact_support':
            onContactSupport?.()
            break
          case 'go_back':
            onGoBack?.()
            break
        }
      }}
      className={className}
    />
  )
}

/**
 * Component for authentication required errors
 */
export function AuthRequiredError({
  onSignIn,
  message,
  className = ''
}: {
  onSignIn?: () => void
  message?: string
  className?: string
}) {
  const error: UserFriendlyError = {
    type: AuthErrorType.AUTHENTICATION_REQUIRED,
    title: 'Authentication Required',
    message: message || 'You need to sign in to access this content.',
    actionable: true,
    retryable: false,
    actions: {
      primary: {
        label: 'Sign In',
        action: 'sign_in'
      }
    }
  }

  return (
    <PermissionError
      error={error}
      onAction={(action) => {
        if (action === 'sign_in') {
          onSignIn?.()
        }
      }}
      className={className}
      variant="card"
    />
  )
}

/**
 * Component for session expired errors
 */
export function SessionExpiredError({
  onSignIn,
  className = ''
}: {
  onSignIn?: () => void
  className?: string
}) {
  const error: UserFriendlyError = {
    type: AuthErrorType.SESSION_EXPIRED,
    title: 'Session Expired',
    message: 'Your session has expired. Please sign in again to continue.',
    actionable: true,
    retryable: false,
    actions: {
      primary: {
        label: 'Sign In Again',
        action: 'sign_in'
      }
    }
  }

  return (
    <PermissionError
      error={error}
      onAction={(action) => {
        if (action === 'sign_in') {
          onSignIn?.()
        }
      }}
      className={className}
      variant="card"
    />
  )
}

/**
 * Component for network/connection errors
 */
export function NetworkError({
  onRetry,
  className = ''
}: {
  onRetry?: () => void
  className?: string
}) {
  const error: UserFriendlyError = {
    type: AuthErrorType.NETWORK_ERROR,
    title: 'Connection Error',
    message: 'Unable to connect to the server. Please check your internet connection and try again.',
    actionable: true,
    retryable: true,
    actions: {
      primary: {
        label: 'Retry',
        action: 'retry'
      }
    }
  }

  return (
    <PermissionError
      error={error}
      onAction={(action) => {
        if (action === 'retry') {
          onRetry?.()
        }
      }}
      className={className}
    />
  )
}

/**
 * Inline permission check component
 */
export function PermissionGuard({
  children,
  fallback,
  hasPermission,
  fallbackType = 'alert'
}: {
  children: React.ReactNode
  fallback?: React.ReactNode
  hasPermission: boolean
  fallbackType?: 'alert' | 'card' | 'full-page'
}) {
  if (hasPermission) {
    return <>{children}</>
  }

  if (fallback) {
    return <>{fallback}</>
  }

  return (
    <RLSViolationError
      className={fallbackType === 'full-page' ? 'min-h-[200px]' : ''}
    />
  )
}

/**
 * Hook for handling errors in components
 */
export function useErrorHandler() {
  const showError = (error: any, context?: string) => {
    // This would integrate with your toast/notification system
    console.error('Error occurred:', error, context)

    // Example toast implementation (adjust based on your toast library)
    // toast({
    //   title: error.title,
    //   description: error.message,
    //   variant: 'destructive',
    // })
  }

  const handleAuthError = (error: any, context?: string) => {
    const userFriendlyError = createUserFriendlyError(error, context)
    showError(userFriendlyError, context)
    return userFriendlyError
  }

  return {
    showError,
    handleAuthError
  }
}

// Re-export error handler utilities for convenience
