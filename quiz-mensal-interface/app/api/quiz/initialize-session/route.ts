/**
 * Quiz Session Initialization Endpoint
 * Converts URL token to secure httpOnly cookie session
 */

import { NextRequest, NextResponse } from 'next/server'
import { validateCSRF } from '@/lib/csrf'
import { storeSession } from '@/lib/quiz-session'
import { quizAPI } from '@/lib/api'

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

    // Store session data
    storeSession(
      sessionId,
      session.new_token || token, // Use rotated token if available
      session
    )

    // Create response
    const response = NextResponse.json({
      ...session,
      message: 'Session initialized successfully'
    })

    // Set secure httpOnly cookie (4 hours)
    response.cookies.set('quiz-session', sessionId, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict',
      maxAge: 4 * 60 * 60, // 4 hours in seconds
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