/// <reference types="vite/client" />

/**
 * Firebase Authentication Service with Session Management
 *
 * PERFORMANCE OPTIMIZATION:
 * Firebase SDK is now lazy-loaded to reduce initial bundle size by 107KB
 *
 * Integrates Firebase Authentication with backend session storage (Redis)
 * Handles login, logout, logout-all, and automatic token refresh
 */

import { firebaseAuthLazy } from '../lib/firebase-lazy'
import { apiClient } from '../lib/api-client'
import { createLogger } from '../lib/logger'
import type { User, LoginResponse } from '@/types/api'

const logger = createLogger('FirebaseAuthService')

let tokenRefreshInterval: NodeJS.Timeout | null = null

/**
 * Login user with email/password
 * Creates session in backend with Redis storage
 */
export async function loginUser(
  email: string,
  password: string
): Promise<LoginResponse> {
  try {
    logger.log('Attempting Firebase login:', email)

    // VALIDATION: Check API base URL before starting login flow
    const baseURL = apiClient.getBaseURL()
    if (!baseURL) {
      throw new Error('API not initialized. Please refresh the page and try again.')
    }

    // SECURITY: Ensure HTTPS in production
    if (typeof window !== 'undefined' && window.location.protocol === 'https:') {
      if (baseURL.startsWith('http://')) {
        logger.error('🚨 CRITICAL: HTTP detected in HTTPS page')
        throw new Error('Security error: Cannot connect to insecure backend from secure page. Please contact support.')
      }
    }

    // VALIDATION: ALWAYS fetch fresh CSRF token before login
    // This ensures we have the latest token and prevents concurrent fetch issues
    logger.log('Fetching fresh CSRF token for login...')
    try {
      await apiClient.fetchCsrfToken()
      const csrfToken = apiClient.getCsrfToken()
      if (!csrfToken) {
        throw new Error('CSRF token not available after fetch')
      }
      logger.log('Fresh CSRF token obtained:', csrfToken.substring(0, 16) + '...')
    } catch (error) {
      logger.error('Failed to fetch CSRF token:', error)
      throw new Error('Security validation failed. Please refresh the page and try again.')
    }

    logger.log('Pre-login validations passed')

    // Step 1: Sign in with Firebase (lazy loaded)
    const result = await firebaseAuthLazy.signInWithPassword({ email, password })

    if (result.error || !result.user || !result.session) {
      throw result.error || new Error('Login failed - no user or session')
    }

    logger.log('Firebase authentication successful (lazy loaded)')

    // Step 2: Get Firebase ID token
    const firebaseToken = await result.user.getIdToken()
    logger.log('Firebase token obtained')

    // Step 3: Create backend session via apiClient (uses /session/ with trailing slash)
    // SECURITY FIX: Session ID is now stored in httpOnly cookie (automatic)
    try {
      const sessionData = await apiClient.auth.createSession(firebaseToken, {
        user_agent: navigator.userAgent,
        timestamp: new Date().toISOString()
      })

      // SECURITY: session_id is now in httpOnly cookie (not in response body)
      // Browser handles cookie storage automatically
      if (sessionData.status !== 'authenticated') {
        throw new Error('Session creation failed - invalid status')
      }

      logger.log('Backend session created (httpOnly cookie set)')
    } catch (error) {
      logger.error('Session creation failed:', error)

      // Provide helpful error message
      if (error instanceof Error) {
        if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
          throw new Error('Cannot connect to server. Please check your internet connection and try again.')
        }
        if (error.message.includes('blocked') || error.message.includes('CORS')) {
          throw new Error('Security error: Connection blocked. Please contact support.')
        }
      }

      throw error
    }

    // Step 4: Firebase token stored in memory via Firebase Auth SDK
    // Session ID stored securely in httpOnly cookie (not accessible to JavaScript)

    // Step 5: NOW safe to call auth.me() (cookie sent automatically)
    apiClient.setAuthToken(firebaseToken)
    const userResponse = await apiClient.auth.me()

    if (!userResponse || !userResponse.data) {
      throw new Error('Failed to fetch user data from backend')
    }

    logger.log('Login successful, session created')

    // HYBRID AUTH: Keep Firebase token for backward compatibility
    // Both session cookie AND Bearer token will be sent for maximum compatibility
    // This ensures all endpoints work regardless of their authentication method
    logger.log('Keeping Firebase token for hybrid authentication (session + Bearer token)')

    // Setup automatic token refresh
    setupTokenRefresh()

    return {
      user: userResponse.data,
      tokens: {
        access_token: firebaseToken
        // refresh_token is omitted (optional property)
      },
      session_id: 'cookie' // Placeholder - actual session_id is in httpOnly cookie
    }
  } catch (error) {
    logger.error('Login failed:', error)
    // Clear any partial session data (cookie cleared by backend on error)
    // Firebase Auth SDK automatically clears in-memory token
    throw error
  }
}

/**
 * Logout current session
 * Invalidates session in backend Redis
 */
export async function logoutUser(): Promise<void> {
  try {
    logger.log('Logging out current session')

    // Call backend session logout endpoint (invalidates Redis session + clears cookie)
    // SECURITY: Cookie sent automatically, backend clears it
    try {
      const logoutData = await apiClient.auth.logout()
      logger.log('Backend session invalidated:', logoutData.message)
    } catch (error) {
      logger.warn('Backend logout request failed, continuing with cleanup:', error)
    }

    // Session cleared via httpOnly cookie by backend
    // Firebase Auth SDK automatically clears in-memory token

    // Clear token refresh interval
    if (tokenRefreshInterval) {
      clearInterval(tokenRefreshInterval)
      tokenRefreshInterval = null
    }

    // Sign out from Firebase (lazy loaded)
    await firebaseAuthLazy.signOut()

    logger.log('Logout successful')
  } catch (error) {
    logger.error('Logout failed:', error)
    // Force cleanup even if logout fails (cookie already cleared by backend)
    // Firebase Auth SDK automatically clears in-memory token
    if (tokenRefreshInterval) {
      clearInterval(tokenRefreshInterval)
      tokenRefreshInterval = null
    }
    throw error
  }
}

/**
 * Logout from all devices
 * Invalidates all user sessions in backend Redis
 */
export async function logoutAllDevices(): Promise<{ sessions_deleted: number }> {
  try {
    logger.log('Logging out from all devices')

    // Get Firebase token from Firebase Auth SDK (lazy loaded, in-memory)
    const currentUser = await firebaseAuthLazy.getCurrentUser()
    if (!currentUser) {
      logger.warn('No Firebase user found, performing local logout only')
      await logoutUser()
      return { sessions_deleted: 1 }
    }

    const firebaseToken = await currentUser.getIdToken()

    try {
      // Call backend logout-all endpoint (invalidates all Redis sessions for user)
      // SECURITY: Uses Bearer token to authenticate this action
      apiClient.setAuthToken(firebaseToken)
      const logoutData = await apiClient.auth.invalidateAllSessions()
      logger.log(`All sessions invalidated: ${logoutData.sessions_deleted} sessions deleted`)

      // Clear token refresh interval
      if (tokenRefreshInterval) {
        clearInterval(tokenRefreshInterval)
        tokenRefreshInterval = null
      }

      // Sign out from Firebase (lazy loaded)
      await firebaseAuthLazy.signOut()

      return { sessions_deleted: logoutData.sessions_deleted }
    } catch (error) {
      logger.error('Logout all request failed, falling back to single session logout:', error)
      await logoutUser()
      return { sessions_deleted: 1 }
    } finally {
      apiClient.setAuthToken(null)
    }
  } catch (error) {
    logger.error('Logout all devices failed:', error)
    throw error
  }
}

/**
 * Get current authenticated user
 * Validates session with backend
 */
export async function getCurrentUser(): Promise<User | null> {
  try {
    // Check Firebase auth state (lazy loaded, Firebase Auth SDK manages token in-memory)
    const firebaseUser = await firebaseAuthLazy.getCurrentUser()
    if (!firebaseUser) {
      logger.log('No Firebase user, session cleared')
      return null
    }

    // Get current Firebase ID token (in-memory from SDK)
    const firebaseToken = await firebaseUser.getIdToken()

    // Validate with backend (httpOnly cookie sent automatically)
    apiClient.setAuthToken(firebaseToken)
    const response = await apiClient.auth.me()

    if (!response || !response.data) {
      logger.log('Backend session invalid, clearing')
      // Firebase Auth SDK will handle token cleanup
      return null
    }

    return {
      ...response.data,
      session_id: 'cookie' // Placeholder - actual session_id is in httpOnly cookie
    }
  } catch (error) {
    logger.error('Get current user failed:', error)
    // Firebase Auth SDK will handle token cleanup
    return null
  } finally {
    // HYBRID AUTH: Keep Firebase token for backward compatibility
    // Both session cookie AND Bearer token available for all endpoints
    logger.log('Keeping Firebase token for hybrid authentication after getCurrentUser')
  }
}

/**
 * Check if current session is valid
 * Validates both Firebase and backend session
 */
export async function checkSession(): Promise<boolean> {
  try {
    const user = await getCurrentUser()
    return user !== null
  } catch (error) {
    logger.error('Session check failed:', error)
    return false
  }
}

/**
 * Setup automatic token refresh with backend validation
 * Firebase tokens expire after 1 hour, refresh every 55 minutes
 *
 * SECURITY IMPROVEMENT: After refreshing the token, validates with backend
 * to prevent token use after account deactivation. If validation fails,
 * forces logout to protect against unauthorized access.
 */
export function setupTokenRefresh(): void {
  // Clear any existing interval
  if (tokenRefreshInterval) {
    clearInterval(tokenRefreshInterval)
  }

  // Refresh token every 55 minutes (Firebase tokens expire after 1 hour)
  const REFRESH_INTERVAL = 55 * 60 * 1000 // 55 minutes in milliseconds

  tokenRefreshInterval = setInterval(async () => {
    try {
      logger.log('Auto-refreshing Firebase token (lazy loaded)')

      const firebaseUser = await firebaseAuthLazy.getCurrentUser()
      if (!firebaseUser) {
        logger.warn('No Firebase user for token refresh')
        if (tokenRefreshInterval) {
          clearInterval(tokenRefreshInterval)
          tokenRefreshInterval = null
        }
        return
      }

      // Force token refresh (Firebase SDK stores in-memory)
      const newToken = await firebaseUser.getIdToken(true)

      // Temporarily set token for validation
      apiClient.setAuthToken(newToken)

      logger.log('Token refreshed successfully')

      // SECURITY: Validate token with backend after refresh
      // This prevents use of refreshed tokens after account deactivation
      try {
        const validationResponse = await apiClient.auth.me()

        if (!validationResponse || !validationResponse.data) {
          logger.error('Backend validation failed after token refresh - session invalid')
          throw new Error('Session validation failed')
        }

        // Check if account is still active
        if (!validationResponse.data.is_active) {
          logger.error('Account deactivated - forcing logout')
          throw new Error('Account has been deactivated')
        }

        logger.log('Backend validation successful after token refresh')

        // HYBRID AUTH: Keep Firebase token for backward compatibility
        // Both session cookie AND Bearer token available after refresh
        logger.log('Keeping Firebase token for hybrid authentication after refresh')
      } catch (validationError) {
        logger.error('Token validation failed, forcing logout:', validationError)

        // Clear refresh interval
        if (tokenRefreshInterval) {
          clearInterval(tokenRefreshInterval)
          tokenRefreshInterval = null
        }

        // Force logout to clear session
        try {
          await logoutUser()
        } catch (logoutError) {
          logger.error('Logout during validation failure encountered error:', logoutError)
        }

        // Redirect to login page
        if (typeof window !== 'undefined') {
          window.location.href = '/login?session_invalid=true'
        }
      }
    } catch (error) {
      logger.error('Token refresh failed:', error)
      // Don't throw - error handling above will manage logout if needed
    }
  }, REFRESH_INTERVAL)

  logger.log('Token refresh with validation scheduled every 55 minutes')
}

/**
 * Stop automatic token refresh
 */
export function stopTokenRefresh(): void {
  if (tokenRefreshInterval) {
    clearInterval(tokenRefreshInterval)
    tokenRefreshInterval = null
    logger.log('Token refresh stopped')
  }
}

// Export lazy-loaded Firebase auth instance for direct use if needed
export { firebaseAuthLazy as firebaseAuth }
