/**
 * Quiz Session Initialization Endpoint
 * Converts URL token to secure httpOnly cookie session
 */

import { NextRequest, NextResponse } from 'next/server'
import { validateCSRF } from '@/lib/csrf'
import { quizAPI } from '@/lib/api'

// Simple in-memory store for session data (in production, use Redis or database)
const sessions = new Map<string, {
  token: string
  sessionData: any
  expires: number
}>()

// Session expiry time (4 hours - matches quiz expiry)
const SESSION_EXPIRY = 4 * 60 * 60 * 1000

/**
 * Initialize secure session with quiz token
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { token } = body

    // Validate CSRF token
    const csrfToken = request.headers.get('X-CSRF-Token')
    if (!csrfToken || !validateCSRF(request, csrfToken)) {
      return NextResponse.json(
        { error: 'Invalid CSRF token' },
        { status: 403 }
      )
    }

    if (!token) {
      return NextResponse.json(
        { error: 'Token is required' },
        { status: 400 }
      )
    }

    // Access quiz with token via backend API
    const session = await quizAPI.accessQuiz(token)

    // Generate secure session ID
    const sessionId = require('crypto').randomBytes(32).toString('hex')
    const expires = Date.now() + SESSION_EXPIRY

    // Store session data
    sessions.set(sessionId, {
      token: session.new_token || token, // Use rotated token if available
      sessionData: session,
      expires
    })

    // Clean up expired sessions
    cleanupExpiredSessions()

    // Create response
    const response = NextResponse.json({
      ...session,
      message: 'Session initialized successfully'
    })

    // Set secure httpOnly cookie
    response.cookies.set('quiz-session', sessionId, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict',
      maxAge: SESSION_EXPIRY / 1000,
      path: '/'
    })

    return response
  } catch (error) {
    console.error('Session initialization error:', error)

    if (error instanceof Error) {
      return NextResponse.json(
        { error: error.message },
        { status: (error as any).status || 500 }
      )
    }

    return NextResponse.json(
      { error: 'Failed to initialize session' },
      { status: 500 }
    )
  }
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