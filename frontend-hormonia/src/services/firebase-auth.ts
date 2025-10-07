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
  permissions?: string[]
  created_at?: string
  firebase_uid?: string
  session_id?: string
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
    const sessionResponse = await fetch(`${apiClient.getBaseURL()}/api/v1/session`, {
      method: 'POST',
      credentials: 'include',  // CRITICAL: Send/receive cookies
      headers: {
        'Content-Type': 'application/json'
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

    // Step 4: Store only Firebase token (session_id is in secure cookie)
    localStorage.setItem('firebase_token', firebaseToken)

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
    localStorage.removeItem('firebase_token')
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
      const response = await fetch(`${apiClient.getBaseURL()}/api/v1/session/logout`, {
        method: 'DELETE',
        credentials: 'include',  // CRITICAL: Send cookies
        headers: {
          'Content-Type': 'application/json'
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

    // Clear local storage (session_id no longer stored here)
    localStorage.removeItem('firebase_token')

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
    localStorage.removeItem('firebase_token')
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

    const firebaseToken = localStorage.getItem('firebase_token')

    if (!firebaseToken) {
      logger.warn('No Firebase token found, performing local logout only')
      await logoutUser()
      return { sessions_deleted: 1 }
    }

    try {
      // Call backend logout-all endpoint (invalidates all Redis sessions for user)
      // SECURITY: Uses Bearer token (not session) to authenticate this action
      const response = await fetch(`${apiClient.getBaseURL()}/api/v1/session/logout-all`, {
        method: 'DELETE',
        credentials: 'include',  // CRITICAL: Clear cookie on this device
        headers: {
          'Authorization': `Bearer ${firebaseToken}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.ok) {
        const logoutData = await response.json()
        logger.log(`All sessions invalidated: ${logoutData.sessions_deleted} sessions deleted`)

        // Clear local storage (session_id no longer stored here)
        localStorage.removeItem('firebase_token')

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
    const firebaseToken = localStorage.getItem('firebase_token')

    if (!firebaseToken) {
      logger.log('No active session found')
      return null
    }

    // Check Firebase auth state
    const firebaseUser = await firebaseAuth.getCurrentUser()
    if (!firebaseUser) {
      logger.log('No Firebase user, clearing session')
      localStorage.removeItem('firebase_token')
      return null
    }

    // Validate with backend (cookie sent automatically)
    apiClient.setAuthToken(firebaseToken)
    const response = await apiClient.auth.me()

    if (!response || !response.data) {
      logger.log('Backend session invalid, clearing')
      localStorage.removeItem('firebase_token')
      return null
    }

    return {
      ...response.data,
      session_id: 'cookie' // Placeholder - actual session_id is in httpOnly cookie
    }
  } catch (error) {
    logger.error('Get current user failed:', error)
    localStorage.removeItem('firebase_token')
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

      // Force token refresh
      const newToken = await firebaseUser.getIdToken(true)

      // Update stored token
      localStorage.setItem('firebase_token', newToken)

      // Update API client
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
