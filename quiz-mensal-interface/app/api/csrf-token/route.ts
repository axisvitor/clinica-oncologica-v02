/**
 * CSRF Token Generation Endpoint
 * Provides secure CSRF tokens for quiz form submissions
 */

import { NextRequest, NextResponse } from 'next/server'
import { randomBytes } from 'crypto'
import { TOKEN_EXPIRY, CSRF_COOKIE_NAME, buildCSRFCookie } from '@/lib/csrf'

// Force dynamic rendering for this route
export const dynamic = 'force-dynamic'

/**
 * Generate a secure CSRF token and store it in httpOnly cookie
 */
export async function GET(request: NextRequest) {
  try {
    // Generate secure random token
    const csrfToken = randomBytes(32).toString('hex')

    // Create response with CSRF token
    const response = NextResponse.json({
      csrfToken,
      message: 'CSRF token generated successfully'
    })

    const cookie = buildCSRFCookie(csrfToken)

    response.cookies.set(CSRF_COOKIE_NAME, cookie.value, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict',
      maxAge: cookie.maxAge,
      path: '/'
    })

    return response
  } catch (error) {
    console.error('CSRF token generation error:', error)
    return NextResponse.json(
      { error: 'Failed to generate CSRF token' },
      { status: 500 }
    )
  }
}
