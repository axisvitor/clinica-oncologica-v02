import { useState, useCallback, useRef } from 'react'
import { AuthError, AuthRetryConfig } from './types'
import { createLogger } from '../../lib/logger'

const logger = createLogger('useAuthRetry')

const DEFAULT_RETRY_CONFIG: AuthRetryConfig = {
  maxRetries: 3,
  retryDelay: 1000,
  exponentialBackoff: true
}

interface UseAuthRetryOptions {
  config?: Partial<AuthRetryConfig>
  onRetryFailed?: (error: AuthError, attempts: number) => void
}

export function useAuthRetry({
  config = {},
  onRetryFailed
}: UseAuthRetryOptions = {}) {
  const retryConfig = { ...DEFAULT_RETRY_CONFIG, ...config }
  const [isRetrying, setIsRetrying] = useState(false)
  const [retryCount, setRetryCount] = useState(0)
  const retryTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const isRetryableError = useCallback((error: AuthError): boolean => {
    // Don't retry certain errors
    const nonRetryableCodes = [
      'invalid_credentials',
      'user_not_found',
      'invalid_email',
      'weak_password',
      'email_already_exists',
      'unauthorized'
    ]

    if (error.code && nonRetryableCodes.includes(error.code)) {
      return false
    }

    // Explicit retryable flag
    if (error.retryable !== undefined) {
      return error.retryable
    }

    // Network errors are generally retryable
    if (error.message?.includes('network') || error.message?.includes('timeout')) {
      return true
    }

    // Server errors (5xx) are retryable
    if (error.message?.includes('500') || error.message?.includes('502') || error.message?.includes('503')) {
      return true
    }

    return false
  }, [])

  const calculateDelay = useCallback((attempt: number): number => {
    if (!retryConfig.exponentialBackoff) {
      return retryConfig.retryDelay
    }

    // Exponential backoff with jitter
    const exponentialDelay = retryConfig.retryDelay * Math.pow(2, attempt - 1)
    const jitter = Math.random() * 0.1 * exponentialDelay
    return Math.min(exponentialDelay + jitter, 30000) // Max 30 seconds
  }, [retryConfig])

  const executeWithRetry = useCallback(async <T>(
    operation: () => Promise<T>,
    operationName: string = 'auth operation'
  ): Promise<T> => {
    let lastError: AuthError
    let attempt = 0

    while (attempt <= retryConfig.maxRetries) {
      try {
        if (attempt > 0) {
          setIsRetrying(true)
          setRetryCount(attempt)
        }

        const result = await operation()

        // Success - reset retry state
        setIsRetrying(false)
        setRetryCount(0)
        if (retryTimeoutRef.current) {
          clearTimeout(retryTimeoutRef.current)
          retryTimeoutRef.current = null
        }

        return result
      } catch (error) {
        lastError = error as AuthError
        attempt++

        logger.warn(`${operationName} attempt ${attempt} failed:`, lastError.message)

        // Check if we should retry
        if (attempt > retryConfig.maxRetries || !isRetryableError(lastError)) {
          break
        }

        // Wait before retry
        const delay = lastError.retryAfter
          ? Math.max(lastError.retryAfter * 1000, calculateDelay(attempt))
          : calculateDelay(attempt)

        logger.debug(`Retrying ${operationName} in ${delay}ms...`)

        await new Promise(resolve => {
          retryTimeoutRef.current = setTimeout(resolve, delay)
        })
      }
    }

    // All retries exhausted
    setIsRetrying(false)
    setRetryCount(0)

    if (onRetryFailed) {
      onRetryFailed(lastError!, attempt)
    }

    throw lastError!
  }, [retryConfig, isRetryableError, calculateDelay, onRetryFailed])

  const resetRetryState = useCallback(() => {
    setIsRetrying(false)
    setRetryCount(0)
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current)
      retryTimeoutRef.current = null
    }
  }, [])

  const createAuthError = useCallback((
    message: string,
    code?: string,
    retryable?: boolean,
    retryAfter?: number
  ): AuthError => {
    const error = new Error(message) as AuthError
    if (code) error.code = code
    if (retryable !== undefined) error.retryable = retryable
    if (retryAfter !== undefined) error.retryAfter = retryAfter
    return error
  }, [])

  return {
    executeWithRetry,
    isRetrying,
    retryCount,
    resetRetryState,
    createAuthError,
    isRetryableError,
    config: retryConfig
  }
}