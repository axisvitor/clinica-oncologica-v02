/**
 * Quiz Session Initialization Endpoint
 * Converts URL token to secure httpOnly cookie session
 */

import { NextRequest, NextResponse } from 'next/server'
import { validateCSRF } from '@/lib/csrf'
import { createSessionCookie, SESSION_COOKIE_NAME } from '@/lib/quiz-session'
import { quizAPI } from '@/lib/api'
import { rateLimiters } from '@/lib/rate-limiter'
import { withCors } from '@/lib/cors-validator'

// Force dynamic rendering for this route
export const dynamic = 'force-dynamic'

/**
 * Handle CORS preflight
 */
export async function OPTIONS(request: NextRequest) {
  return withCors(async () => {
    return new NextResponse(null, { status: 204 })
  })(request)
}

/**
 * Initialize secure session with quiz token (with rate limiting and CORS)
 */
export async function POST(request: NextRequest) {
  return rateLimiters.initializeSession(request, async () => {
    return withCors(async (req) => {
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
    const sessionCookie = createSessionCookie(session.new_token || token, session)

    // Create response
    const response = NextResponse.json({
      ...session,
      message: 'Session initialized successfully'
    })

    response.cookies.set(SESSION_COOKIE_NAME, sessionCookie.value, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict',
      maxAge: sessionCookie.maxAge,
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
    })(request)
  })
}
