/**
 * Authentication and RLS Error Handling Utilities
 *
 * This module provides comprehensive error handling for authentication,
 * authorization, and Row Level Security (RLS) violations in Supabase operations.
 *
 * Features:
 * - RLS violation detection and user-friendly messages
 * - Authentication error categorization
 * - User feedback helpers
 * - Retry logic for transient errors
 * - Permission context helpers
 */

import { createLogger } from './logger'

// Removed Supabase dependency - PostgrestError type replaced with generic error
type PostgrestError = {
  message: string
  code?: string
  details?: string
  hint?: string
}

const logger = createLogger('AuthErrorHandler')

// Error types for better categorization
export enum AuthErrorType {
  AUTHENTICATION_REQUIRED = 'AUTHENTICATION_REQUIRED',
  INVALID_CREDENTIALS = 'INVALID_CREDENTIALS',
  SESSION_EXPIRED = 'SESSION_EXPIRED',
  INSUFFICIENT_PERMISSIONS = 'INSUFFICIENT_PERMISSIONS',
  RLS_VIOLATION = 'RLS_VIOLATION',
  NETWORK_ERROR = 'NETWORK_ERROR',
  RATE_LIMITED = 'RATE_LIMITED',
  SERVER_ERROR = 'SERVER_ERROR',
  UNKNOWN_ERROR = 'UNKNOWN_ERROR'
}

// User-friendly error messages
export interface UserFriendlyError {
  type: AuthErrorType
  title: string
  message: string
  actionable: boolean
  retryable: boolean
  actions?: {
    primary?: {
      label: string
      action: string
    }
    secondary?: {
      label: string
      action: string
    }
  }
}

// RLS error patterns to detect specific violations
const RLS_ERROR_PATTERNS = [
  /new row violates row-level security policy/i,
  /permission denied for table/i,
  /insufficient privilege/i,
  /row-level security policy/i,
  /policy.*violation/i,
  /access denied/i,
  /forbidden/i
]

// Authentication error patterns
const AUTH_ERROR_PATTERNS = {
  INVALID_CREDENTIALS: [
    /invalid login credentials/i,
    /email not confirmed/i,
    /invalid email or password/i,
    /user not found/i
  ],
  SESSION_EXPIRED: [
    /jwt expired/i,
    /token.*expired/i,
    /session.*expired/i,
    /invalid jwt/i
  ],
  RATE_LIMITED: [
    /too many requests/i,
    /rate limit/i,
    /too many attempts/i
  ]
}

/**
 * Analyzes an error and categorizes it for better handling
 */
export function categorizeError(error: unknown): AuthErrorType {
  if (!error) return AuthErrorType.UNKNOWN_ERROR

  const errorObj = error as Record<string, unknown> | null | undefined
  const errorMessage = typeof error === 'string' ? error :
    (errorObj?.['message'] as string) || (errorObj?.['error_description'] as string) || (errorObj?.['error'] as string) || ''

  const statusCode = (errorObj?.['status'] as number) || (errorObj?.['statusCode'] as number) || (errorObj?.['code'] as number)

  // Check for RLS violations first
  if (statusCode === 403 || RLS_ERROR_PATTERNS.some(pattern => pattern.test(errorMessage))) {
    return AuthErrorType.RLS_VIOLATION
  }

  // Check for authentication errors
  if (statusCode === 401) {
    return AuthErrorType.AUTHENTICATION_REQUIRED
  }

  // Check specific authentication patterns
  for (const [type, patterns] of Object.entries(AUTH_ERROR_PATTERNS)) {
    if (patterns.some(pattern => pattern.test(errorMessage))) {
      return type as AuthErrorType
    }
  }

  // Check for network errors
  if (statusCode >= 500 || errorMessage.includes('network') || errorMessage.includes('fetch')) {
    return AuthErrorType.NETWORK_ERROR
  }

  // Check for rate limiting
  if (statusCode === 429) {
    return AuthErrorType.RATE_LIMITED
  }

  return AuthErrorType.UNKNOWN_ERROR
}

/**
 * Converts a technical error into a user-friendly message
 */
export function createUserFriendlyError(error: unknown, context?: string): UserFriendlyError {
  const errorType = categorizeError(error)
  const contextSuffix = context ? ` when ${context}` : ''

  switch (errorType) {
    case AuthErrorType.RLS_VIOLATION:
      return {
        type: errorType,
        title: 'Access Denied',
        message: `You don't have permission to perform this action${contextSuffix}. Please contact your administrator if you believe this is an error.`,
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

    case AuthErrorType.AUTHENTICATION_REQUIRED:
      return {
        type: errorType,
        title: 'Authentication Required',
        message: `You need to sign in${contextSuffix}.`,
        actionable: true,
        retryable: false,
        actions: {
          primary: {
            label: 'Sign In',
            action: 'sign_in'
          }
        }
      }

    case AuthErrorType.INVALID_CREDENTIALS:
      return {
        type: errorType,
        title: 'Invalid Credentials',
        message: 'The email or password you entered is incorrect. Please try again.',
        actionable: true,
        retryable: true,
        actions: {
          primary: {
            label: 'Try Again',
            action: 'retry_login'
          },
          secondary: {
            label: 'Reset Password',
            action: 'reset_password'
          }
        }
      }

    case AuthErrorType.SESSION_EXPIRED:
      return {
        type: errorType,
        title: 'Session Expired',
        message: 'Your session has expired. Please sign in again.',
        actionable: true,
        retryable: false,
        actions: {
          primary: {
            label: 'Sign In',
            action: 'sign_in'
          }
        }
      }

    case AuthErrorType.INSUFFICIENT_PERMISSIONS:
      return {
        type: errorType,
        title: 'Insufficient Permissions',
        message: `You don't have the required permissions${contextSuffix}. Contact your administrator to request access.`,
        actionable: true,
        retryable: false,
        actions: {
          primary: {
            label: 'Request Access',
            action: 'request_access'
          },
          secondary: {
            label: 'Go Back',
            action: 'go_back'
          }
        }
      }

    case AuthErrorType.NETWORK_ERROR:
      return {
        type: errorType,
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

    case AuthErrorType.RATE_LIMITED:
      return {
        type: errorType,
        title: 'Too Many Attempts',
        message: 'You\'ve made too many requests. Please wait a moment before trying again.',
        actionable: true,
        retryable: true,
        actions: {
          primary: {
            label: 'Try Again Later',
            action: 'retry_later'
          }
        }
      }

    case AuthErrorType.SERVER_ERROR:
      return {
        type: errorType,
        title: 'Server Error',
        message: 'Something went wrong on our end. Please try again or contact support if the problem persists.',
        actionable: true,
        retryable: true,
        actions: {
          primary: {
            label: 'Retry',
            action: 'retry'
          },
          secondary: {
            label: 'Contact Support',
            action: 'contact_support'
          }
        }
      }

    default:
      return {
        type: AuthErrorType.UNKNOWN_ERROR,
        title: 'Unexpected Error',
        message: 'An unexpected error occurred. Please try again or contact support if the problem persists.',
        actionable: true,
        retryable: true,
        actions: {
          primary: {
            label: 'Retry',
            action: 'retry'
          },
          secondary: {
            label: 'Contact Support',
            action: 'contact_support'
          }
        }
      }
  }
}

/**
 * Checks if an error is related to RLS (Row Level Security)
 */
export function isRLSError(error: unknown): boolean {
  return categorizeError(error) === AuthErrorType.RLS_VIOLATION
}

/**
 * Checks if an error is retryable
 */
export function isRetryableError(error: unknown): boolean {
  const errorType = categorizeError(error)
  return [
    AuthErrorType.NETWORK_ERROR,
    AuthErrorType.RATE_LIMITED,
    AuthErrorType.SERVER_ERROR
  ].includes(errorType)
}

/**
 * Checks if an error requires authentication
 */
export function requiresAuthentication(error: unknown): boolean {
  const errorType = categorizeError(error)
  return [
    AuthErrorType.AUTHENTICATION_REQUIRED,
    AuthErrorType.SESSION_EXPIRED
  ].includes(errorType)
}

/**
 * Enhanced error handler for Supabase operations
 */
export class SupabaseErrorHandler {
  private static instance: SupabaseErrorHandler
  private errorListeners: ((error: UserFriendlyError) => void)[] = []

  static getInstance(): SupabaseErrorHandler {
    if (!SupabaseErrorHandler.instance) {
      SupabaseErrorHandler.instance = new SupabaseErrorHandler()
    }
    return SupabaseErrorHandler.instance
  }

  /**
   * Add a global error listener
   */
  onError(listener: (error: UserFriendlyError) => void): () => void {
    this.errorListeners.push(listener)

    // Return unsubscribe function
    return () => {
      const index = this.errorListeners.indexOf(listener)
      if (index > -1) {
        this.errorListeners.splice(index, 1)
      }
    }
  }

  /**
   * Handle and emit an error
   */
  handleError(error: unknown, context?: string): UserFriendlyError {
    const userFriendlyError = createUserFriendlyError(error, context)

    // Emit to listeners
    this.errorListeners.forEach(listener => {
      try {
        listener(userFriendlyError)
      } catch (listenerError) {
        logger.error('Error in error listener:', listenerError)
      }
    })

    return userFriendlyError
  }

  /**
   * Wrap a Supabase operation with error handling
   */
  async withErrorHandling<T>(
    operation: () => Promise<{ data: T; error: PostgrestError | null }>,
    context?: string
  ): Promise<T> {
    try {
      const { data, error } = await operation()

      if (error) {
        const userFriendlyError = this.handleError(error, context)
        throw new SupabaseOperationError(userFriendlyError, error)
      }

      return data
    } catch (error) {
      if (error instanceof SupabaseOperationError) {
        throw error
      }

      const userFriendlyError = this.handleError(error, context)
      throw new SupabaseOperationError(userFriendlyError, error)
    }
  }
}

/**
 * Custom error class for Supabase operations
 */
export class SupabaseOperationError extends Error {
  constructor(
    public userFriendlyError: UserFriendlyError,
    public originalError: unknown
  ) {
    super(userFriendlyError.message)
    this.name = 'SupabaseOperationError'
  }
}

/**
 * Utility function to get permission context for error messages
 */
export function getPermissionContext(tableName: string, operation: string): string {
  const operations: Record<string, string> = {
    select: 'viewing',
    insert: 'creating',
    update: 'updating',
    delete: 'deleting'
  }

  const action = operations[operation.toLowerCase()] || operation.toLowerCase()
  return `${action} ${tableName.replace('_', ' ')}`
}

/**
 * Helper to format table names for user display
 */
export function formatTableName(tableName: string): string {
  return tableName
    .replace(/_/g, ' ')
    .replace(/\b\w/g, l => l.toUpperCase())
}

// Export singleton instance
export const errorHandler = SupabaseErrorHandler.getInstance()