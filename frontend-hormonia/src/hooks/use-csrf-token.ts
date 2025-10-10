/**
 * Custom hook for CSRF token management
 *
 * Handles fetching and caching CSRF tokens for secure API requests.
 * Integrates with apiClient to automatically include tokens in state-changing requests.
 */
import { useEffect, useState } from 'react'
import { apiClient } from '../lib/api-client'
import { createLogger } from '../lib/logger'

const logger = createLogger('useCsrfToken')

export function useCsrfToken() {
  const [csrfToken, setCsrfToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    let mounted = true

    const fetchToken = async () => {
      try {
        setIsLoading(true)
        setError(null)

        await apiClient.fetchCsrfToken()

        if (mounted) {
          const token = apiClient.getCsrfToken()
          setCsrfToken(token)
          logger.debug('CSRF token fetched and cached')
        }
      } catch (err) {
        if (mounted) {
          const error = err instanceof Error ? err : new Error('Failed to fetch CSRF token')
          setError(error)
          logger.error('Failed to fetch CSRF token:', error)
        }
      } finally {
        if (mounted) {
          setIsLoading(false)
        }
      }
    }

    fetchToken()

    return () => {
      mounted = false
    }
  }, [])

  /**
   * Manually refresh CSRF token
   * Call this after session creation or when token expires
   */
  const refreshToken = async () => {
    try {
      setIsLoading(true)
      setError(null)

      await apiClient.fetchCsrfToken()
      const token = apiClient.getCsrfToken()
      setCsrfToken(token)
      logger.debug('CSRF token refreshed')
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to refresh CSRF token')
      setError(error)
      logger.error('Failed to refresh CSRF token:', error)
      throw error
    } finally {
      setIsLoading(false)
    }
  }

  return {
    csrfToken,
    isLoading,
    error,
    refreshToken
  }
}
