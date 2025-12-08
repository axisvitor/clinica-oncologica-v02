/**
 * CSRF Token Generation Endpoint
 * Provides secure CSRF tokens for quiz form submissions
 */

import { NextRequest, NextResponse } from 'next/server'
import { randomBytes } from 'crypto'
import { TOKEN_EXPIRY, CSRF_COOKIE_NAME, buildCSRFCookie } from '@/lib/csrf'
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
 * Generate a secure CSRF token with rate limiting and CORS validation
 */
export async function GET(request: NextRequest) {
  return rateLimiters.csrfToken(request, async () => {
    return withCors(async (req) => {
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
    })(request)
  })
}
