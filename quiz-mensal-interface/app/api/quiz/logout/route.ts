/**
 * Quiz Session Logout Endpoint
 * Clears authentication session and cookies
 */

import { NextRequest, NextResponse } from 'next/server'
import { SESSION_COOKIE_NAME } from '@/lib/quiz-session'
import { CSRF_COOKIE_NAME } from '@/lib/csrf'

// Force dynamic rendering for this route
export const dynamic = 'force-dynamic'

/**
 * Clear authentication session
 */
export async function POST(request: NextRequest) {
  try {
    const response = NextResponse.json({
      success: true,
      message: 'Session cleared successfully'
    })

    const commonCookieOptions = {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict' as const,
      maxAge: 0,
      path: '/' as const
    }

    // Clear new session cookie
    response.cookies.set(SESSION_COOKIE_NAME, '', commonCookieOptions)

    // Clear legacy session cookie if present
    response.cookies.set('quiz-session', '', commonCookieOptions)

    // Clear CSRF token cookie
    response.cookies.set(CSRF_COOKIE_NAME, '', commonCookieOptions)

    return response
  } catch (error) {
    console.error('Session logout error:', error)
    return NextResponse.json(
      { error: 'Failed to clear session' },
      { status: 500 }
    )
  }
}
