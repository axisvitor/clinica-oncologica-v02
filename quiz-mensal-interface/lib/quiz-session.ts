/**
 * Quiz Session Management Utilities
 */

import { NextRequest } from 'next/server'

// Simple in-memory store for session data (in production, use Redis or database)
const sessions = new Map<string, {
  token: string
  sessionData: any
  expires: number
}>()

// Session expiry time (4 hours - matches quiz expiry)
export const SESSION_EXPIRY = 4 * 60 * 60 * 1000

/**
 * Store quiz session data
 */
export function storeSession(sessionId: string, token: string, sessionData: any): void {
  const expires = Date.now() + SESSION_EXPIRY
  sessions.set(sessionId, {
    token,
    sessionData,
    expires
  })
  cleanupExpiredSessions()
}

/**
 * Get session data from cookie
 */
export function getSessionData(request: NextRequest) {
  try {
    const sessionId = request.cookies.get('quiz-session')?.value
    if (!sessionId) {
      return null
    }

    const sessionData = sessions.get(sessionId)
    if (!sessionData) {
      return null
    }

    // Check if session is expired
    if (Date.now() > sessionData.expires) {
      sessions.delete(sessionId)
      return null
    }

    return sessionData
  } catch (error) {
    console.error('Session data retrieval error:', error)
    return null
  }
}

/**
 * Update session token (for token rotation)
 */
export function updateSessionToken(request: NextRequest, newToken: string) {
  try {
    const sessionId = request.cookies.get('quiz-session')?.value
    if (!sessionId) {
      return false
    }

    const sessionData = sessions.get(sessionId)
    if (!sessionData) {
      return false
    }

    // Update token
    sessionData.token = newToken
    sessions.set(sessionId, sessionData)
    return true
  } catch (error) {
    console.error('Session token update error:', error)
    return false
  }
}

/**
 * Clean up expired sessions to prevent memory leaks
 */
function cleanupExpiredSessions() {
  const now = Date.now()
  for (const [sessionId, sessionData] of sessions.entries()) {
    if (now > sessionData.expires) {
      sessions.delete(sessionId)
    }
  }
}
