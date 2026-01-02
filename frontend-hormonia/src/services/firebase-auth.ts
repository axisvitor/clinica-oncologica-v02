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
import { isErrorWithMessage, getErrorMessage } from '@/lib/utils/type-guards'
import type { User, LoginResponse } from '@/types/api'

const logger = createLogger('FirebaseAuthService')

let tokenRefreshInterval: NodeJS.Timeout | null = null

// Store the session_id from backend login response
// This should NEVER be overwritten with Firebase JWT tokens
let currentSessionId: string | null = null

/**
 * Get the current session ID (UUID from backend)
 * NOT the Firebase JWT token
 */
export function getSessionId(): string | null {
  return currentSessionId
}

/**
 * Clear the stored session ID
 * Called on logout
 */
export function clearSessionId(): void {
  currentSessionId = null
  apiClient.setAuthToken(null)
}

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

    // VALIDATION: Try to fetch fresh CSRF token (optional for Header-Based Auth)
    logger.log('Fetching fresh CSRF token for login...')
    try {
      await apiClient.fetchCsrfToken()
      // We don't block if this fails, as we are using Header Auth
    } catch (error) {
      logger.warn('Failed to fetch CSRF token (non-fatal for Header Auth):', error)
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

    // Step 3: Create backend session via apiClient
    // SECURITY FIX: Session ID is returned in response for Header-Based Auth
    let sessionData;
    try {
      sessionData = await apiClient.auth.createSession(firebaseToken, {
        user_agent: navigator.userAgent,
        timestamp: new Date().toISOString()
      })

      if (!sessionData.valid) {
        throw new Error('Session creation failed - invalid valid')
      }

      logger.log('Backend session created')
    } catch (error) {
      logger.error('Session creation failed:', error)

      // Provide helpful error message
      if (error instanceof Error) {
        if (isErrorWithMessage(error) && error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
          throw new Error('Cannot connect to server. Please check your internet connection and try again.')
        }
        if (isErrorWithMessage(error) && error.message.includes('blocked') || error.message.includes('CORS')) {
          throw new Error('Security error: Connection blocked. Please contact support.')
        }
      }

      throw error
    }

    // Step 4: Firebase token stored in memory via Firebase Auth SDK
    // Session ID stored securely in httpOnly cookie (not accessible to JavaScript)

    // Step 5: NOW safe to call auth.me()
    // CRITICAL FIX: Store session_id and use it for all API calls
    // NEVER use Firebase JWT token for API calls - it will fail session validation
    if (sessionData.session_id) {
      currentSessionId = sessionData.session_id
      apiClient.setAuthToken(sessionData.session_id)
      logger.log('Session ID stored and set as Auth Token:', sessionData.session_id.substring(0, 8) + '...')
    } else {
      // Fallback: No session_id means backend didn't return one - this is an error
      logger.error('Backend did not return session_id - login will fail')
      throw new Error('Backend session creation failed - no session_id returned')
    }

    const userResponse = await apiClient.auth.me()

    if (!userResponse || !userResponse.data) {
      throw new Error('Failed to fetch user data from backend')
    }

    logger.log('Login successful, session created')

    // Setup automatic token refresh
    setupTokenRefresh()

    return {
      user: userResponse.data,
      tokens: {
        access_token: sessionData.session_id || firebaseToken
        // refresh_token is omitted (optional property)
      },
      session_id: sessionData.session_id || 'cookie'
    }
  } catch (error: any) {
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

    // Clear stored session_id
    clearSessionId()

    logger.log('Logout successful')
  } catch (error) {
    logger.error('Logout failed:', error)
    // Force cleanup even if logout fails (cookie already cleared by backend)
    // Firebase Auth SDK automatically clears in-memory token
    if (tokenRefreshInterval) {
      clearInterval(tokenRefreshInterval)
      tokenRefreshInterval = null
    }
    // Clear session_id on error too
    clearSessionId()
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
      // Use session_id if available, otherwise fallback to Firebase token
      if (currentSessionId) {
        apiClient.setAuthToken(currentSessionId)
      } else {
        apiClient.setAuthToken(firebaseToken)
      }
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
      // Always clear session_id on logout
      clearSessionId()
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
      clearSessionId()
      return null
    }

    // CRITICAL: Use stored session_id, NOT Firebase JWT token
    // The session_id (UUID) is what the backend expects for authentication
    if (!currentSessionId) {
      logger.log('No session_id stored - user needs to login again')
      // User has Firebase auth but no backend session - likely page refresh
      // The session cookie should still be valid, so try auth.me() without setting token
      // This relies on the cookie being sent automatically
      const response = await apiClient.auth.me()
      if (response?.data) {
        logger.log('Session validated via cookie only')
        return {
          ...response.data,
          session_id: 'cookie'
        }
      }
      return null
    }

    // Ensure session_id is set as auth token (not Firebase JWT)
    apiClient.setAuthToken(currentSessionId)
    const response = await apiClient.auth.me()

    if (!response || !response.data) {
      logger.log('Backend session invalid, clearing')
      clearSessionId()
      return null
    }

    return {
      ...response.data,
      session_id: currentSessionId
    }
  } catch (error) {
    logger.error('Get current user failed:', error)
    // Don't clear session on error - might be network issue
    return null
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
      // This keeps the Firebase session alive, but we use session_id for API calls
      await firebaseUser.getIdToken(true)

      logger.log('Firebase token refreshed successfully')

      // SECURITY: Validate session with backend (uses session_id, not Firebase token)
      // This prevents use after account deactivation
      try {
        // Ensure session_id is set as auth token (NOT Firebase JWT)
        if (currentSessionId) {
          apiClient.setAuthToken(currentSessionId)
        }
        // auth.me() will use cookie if no session_id stored
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

        logger.log('Backend session validation successful')
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
