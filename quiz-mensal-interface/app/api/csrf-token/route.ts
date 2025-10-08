/**
 * CSRF Token Generation Endpoint
 * Provides secure CSRF tokens for quiz form submissions
 */

import { NextRequest, NextResponse } from 'next/server'
import { randomBytes } from 'crypto'
import { storeCSRFToken, TOKEN_EXPIRY } from '@/lib/csrf'

/**
 * Generate a secure CSRF token and store it in httpOnly cookie
 */
export async function GET(request: NextRequest) {
  try {
    // Generate secure random token
    const csrfToken = randomBytes(32).toString('hex')
    const sessionId = randomBytes(16).toString('hex')

    // Store token with expiry
    storeCSRFToken(sessionId, csrfToken)

    // Create response with CSRF token
    const response = NextResponse.json({
      csrfToken,
      message: 'CSRF token generated successfully'
    })

    // Set httpOnly cookie with session ID
    response.cookies.set('csrf-session', sessionId, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict',
      maxAge: TOKEN_EXPIRY / 1000,
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
