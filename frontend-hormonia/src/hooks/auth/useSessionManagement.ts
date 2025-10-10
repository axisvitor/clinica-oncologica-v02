import { useState, useCallback, useRef, useEffect } from 'react'
import { SessionData, AuthTokens } from './types'
import { TOKEN_REFRESH_THRESHOLD, SESSION_TIMEOUT } from '../../config'
import { createLogger } from '../../lib/logger'

const logger = createLogger('useSessionManagement')

interface UseSessionManagementOptions {
  onRefreshNeeded: () => Promise<void>
  onSessionExpired: () => void
  autoRefresh?: boolean
}

export function useSessionManagement({
  onRefreshNeeded,
  onSessionExpired,
  autoRefresh = true
}: UseSessionManagementOptions) {
  const [sessionExpiry, setSessionExpiry] = useState<number | null>(null)
  const refreshTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const sessionTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearTimeouts = useCallback(() => {
    if (refreshTimeoutRef.current) {
      clearTimeout(refreshTimeoutRef.current)
      refreshTimeoutRef.current = null
    }
    if (sessionTimeoutRef.current) {
      clearTimeout(sessionTimeoutRef.current)
      sessionTimeoutRef.current = null
    }
  }, [])

  const isSessionExpiring = useCallback((): boolean => {
    if (!sessionExpiry) return false
    const now = Date.now()
    return (sessionExpiry - now) <= TOKEN_REFRESH_THRESHOLD
  }, [sessionExpiry])

  const getTimeToExpiry = useCallback((): number => {
    if (!sessionExpiry) return 0
    const now = Date.now()
    return Math.max(0, sessionExpiry - now)
  }, [sessionExpiry])

  const setupSession = useCallback((expiresIn: number) => {
    const now = Date.now()
    const expiry = now + (expiresIn * 1000)
    setSessionExpiry(expiry)

    clearTimeouts()

    if (autoRefresh) {
      // Setup refresh token timer (5 minutes before expiry)
      const refreshTime = Math.max(0, (expiresIn * 1000) - TOKEN_REFRESH_THRESHOLD)
      refreshTimeoutRef.current = setTimeout(() => {
        onRefreshNeeded().catch((error) => {
          logger.error('Auto refresh failed:', error)
        })
      }, refreshTime)
    }

    // Setup session timeout (logout when session expires)
    const timeoutDuration = Math.min(expiresIn * 1000, SESSION_TIMEOUT)
    sessionTimeoutRef.current = setTimeout(() => {
      onSessionExpired()
    }, timeoutDuration)
  }, [autoRefresh, onRefreshNeeded, onSessionExpired, clearTimeouts])

  const updateSessionFromTokens = useCallback((tokens: AuthTokens) => {
    if (tokens.expires_in) {
      setupSession(tokens.expires_in)
      // SECURITY: Session managed by httpOnly cookies (backend)
      // No localStorage storage needed - cookies are automatic
    }
  }, [setupSession])

  const clearSession = useCallback(() => {
    clearTimeouts()
    setSessionExpiry(null)
  }, [clearTimeouts])

  const restoreSessionFromStorage = useCallback((): boolean => {
    // SECURITY: Session restoration handled by httpOnly cookies (backend)
    // Firebase Auth SDK manages token refresh automatically
    // No localStorage restoration needed
    logger.debug('Session restore: delegated to backend cookies + Firebase SDK')
    return false // Always return false - let backend/Firebase handle it
  }, [setupSession])

  const sessionData: SessionData = {
    expiry: sessionExpiry,
    isExpiring: isSessionExpiring(),
    timeToExpiry: getTimeToExpiry()
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => clearTimeouts()
  }, [clearTimeouts])

  return {
    sessionData,
    setupSession,
    updateSessionFromTokens,
    clearSession,
    restoreSessionFromStorage,
    isSessionExpiring,
    getTimeToExpiry
  }
}