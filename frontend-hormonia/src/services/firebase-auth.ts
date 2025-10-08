/// <reference types="vite/client" />

/**
 * Firebase Authentication Service with Session Management
 *
 * Integrates Firebase Authentication with backend session storage (Redis)
 * Handles login, logout, logout-all, and automatic token refresh
 */

import { auth, firebaseAuth } from '../lib/firebase-client'
import type { User as FirebaseUser } from 'firebase/auth'
import { apiClient } from '../lib/api-client'
import { createLogger } from '../lib/logger'

const logger = createLogger('FirebaseAuthService')

export interface User {
  id: string
  email: string
  full_name: string
  role: string
  is_active: boolean
  permissions: string[]  // Required to match hooks/auth/types.ts
  created_at: string     // Required to match hooks/auth/types.ts
  firebase_uid?: string
  session_id?: string
  token?: string         // Optional for WebSocket/API auth
  avatar_url?: string    // Optional for profile picture
}

export interface LoginResponse {
  user: User
  session_id: string
}

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

    // Step 1: Sign in with Firebase
    const result = await firebaseAuth.signInWithPassword({ email, password })

    if (result.error || !result.user || !result.session) {
      throw result.error || new Error('Login failed - no user or session')
    }

    logger.log('Firebase authentication successful')

    // Step 2: Get Firebase ID token
    const firebaseToken = await result.user.getIdToken()
    logger.log('Firebase token obtained')

    // Step 3: Create backend session via /api/v1/session endpoint
    // SECURITY FIX: Session ID is now stored in httpOnly cookie (automatic)
    const csrfToken = apiClient.getCsrfToken()
    const sessionResponse = await fetch(`${apiClient.getBaseURL()}/api/v1/session`, {
      method: 'POST',
      credentials: 'include',  // CRITICAL: Send/receive cookies
      headers: {
        'Content-Type': 'application/json',
        ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {})
      },
      body: JSON.stringify({
        firebase_token: firebaseToken,
        device_info: {
          user_agent: navigator.userAgent,
          timestamp: new Date().toISOString()
        }
      })
    })

    if (!sessionResponse.ok) {
      const errorData = await sessionResponse.json().catch(() => ({}))
      throw new Error(errorData.detail || 'Failed to create backend session')
    }

    const sessionData = await sessionResponse.json()

    // SECURITY: session_id is now in httpOnly cookie (not in response body)
    // Browser handles cookie storage automatically
    if (sessionData.status !== 'authenticated') {
      throw new Error('Session creation failed - invalid status')
    }

    logger.log('Backend session created (httpOnly cookie set)')

    // Step 4: Firebase token stored in memory via Firebase Auth SDK
    // Session ID stored securely in httpOnly cookie (not accessible to JavaScript)
    // NO localStorage usage - prevents XSS token theft

    // Step 5: NOW safe to call auth.me() (cookie sent automatically)
    apiClient.setAuthToken(firebaseToken)
    const userResponse = await apiClient.auth.me()

    if (!userResponse || !userResponse.data) {
      throw new Error('Failed to fetch user data from backend')
    }

    logger.log('Login successful, session created')

    // Setup automatic token refresh
    setupTokenRefresh()

    return {
      user: userResponse.data,
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
      const csrfToken = apiClient.getCsrfToken()
      const response = await fetch(`${apiClient.getBaseURL()}/api/v1/session/logout`, {
        method: 'DELETE',
        credentials: 'include',  // CRITICAL: Send cookies
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {})
        }
      })

      if (response.ok) {
        const logoutData = await response.json()
        logger.log('Backend session invalidated:', logoutData.message)
      } else {
        logger.warn('Backend logout returned non-OK status:', response.status)
      }
    } catch (error) {
      logger.warn('Backend logout request failed, continuing with cleanup:', error)
    }

    // Local storage NO LONGER USED (session cleared via httpOnly cookie by backend)
    // Firebase Auth SDK automatically clears in-memory token

    // Clear token refresh interval
    if (tokenRefreshInterval) {
      clearInterval(tokenRefreshInterval)
      tokenRefreshInterval = null
    }

    // Sign out from Firebase
    await firebaseAuth.signOut()

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

    // Get Firebase token from Firebase Auth SDK (in-memory)
    const currentUser = await firebaseAuth.getCurrentUser()
    if (!currentUser) {
      logger.warn('No Firebase user found, performing local logout only')
      await logoutUser()
      return { sessions_deleted: 1 }
    }

    const firebaseToken = await currentUser.getIdToken()

    try {
      // Call backend logout-all endpoint (invalidates all Redis sessions for user)
      // SECURITY: Uses Bearer token (not session) to authenticate this action
      const csrfToken = apiClient.getCsrfToken()
      const response = await fetch(`${apiClient.getBaseURL()}/api/v1/session/logout-all`, {
        method: 'DELETE',
        credentials: 'include',  // CRITICAL: Clear cookie on this device
        headers: {
          'Authorization': `Bearer ${firebaseToken}`,
          'Content-Type': 'application/json',
          ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {})
        }
      })

      if (response.ok) {
        const logoutData = await response.json()
        logger.log(`All sessions invalidated: ${logoutData.sessions_deleted} sessions deleted`)

        // Local storage NO LONGER USED
        // Session cleared via httpOnly cookie by backend

        // Clear token refresh interval
        if (tokenRefreshInterval) {
          clearInterval(tokenRefreshInterval)
          tokenRefreshInterval = null
        }

        // Sign out from Firebase
        await firebaseAuth.signOut()

        return { sessions_deleted: logoutData.sessions_deleted }
      } else {
        logger.warn('Backend logout-all failed, falling back to single session logout')
        await logoutUser()
        return { sessions_deleted: 1 }
      }
    } catch (error) {
      logger.error('Logout all request failed, falling back to single session logout:', error)
      await logoutUser()
      return { sessions_deleted: 1 }
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
    // Check Firebase auth state (Firebase Auth SDK manages token in-memory)
    const firebaseUser = await firebaseAuth.getCurrentUser()
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
 * Setup automatic token refresh
 * Firebase tokens expire after 1 hour, refresh every 55 minutes
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
      logger.log('Auto-refreshing Firebase token')

      const firebaseUser = await firebaseAuth.getCurrentUser()
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

      // Update API client with refreshed token
      apiClient.setAuthToken(newToken)

      logger.log('Token refreshed successfully')
    } catch (error) {
      logger.error('Token refresh failed:', error)
      // Don't throw - let it retry on next interval
    }
  }, REFRESH_INTERVAL)

  logger.log('Token refresh scheduled every 55 minutes')
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

// Export Firebase auth instance for direct use if needed
export { auth, firebaseAuth }
