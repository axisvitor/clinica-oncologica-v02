/**
 * CSRF Token Generation Endpoint
 * Provides secure CSRF tokens for quiz form submissions
 */

import { NextRequest, NextResponse } from 'next/server'
import { randomBytes } from 'crypto'

// Simple in-memory store for CSRF tokens (in production, use Redis or database)
const csrfTokens = new Map<string, { token: string, expires: number }>()

// Token expiry time (1 hour)
const TOKEN_EXPIRY = 60 * 60 * 1000

/**
 * Generate a secure CSRF token and store it in httpOnly cookie
 */
export async function GET(request: NextRequest) {
  try {
    // Generate secure random token
    const csrfToken = randomBytes(32).toString('hex')
    const sessionId = randomBytes(16).toString('hex')
    const expires = Date.now() + TOKEN_EXPIRY

    // Store token with expiry
    csrfTokens.set(sessionId, { token: csrfToken, expires })

    // Clean up expired tokens
    cleanupExpiredTokens()

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

/**
 * Validate CSRF token
 */
export function validateCSRFToken(request: NextRequest, providedToken: string): boolean {
  try {
    const sessionId = request.cookies.get('csrf-session')?.value
    if (!sessionId) {
      return false
    }

    const tokenData = csrfTokens.get(sessionId)
    if (!tokenData) {
      return false
    }

    // Check if token is expired
    if (Date.now() > tokenData.expires) {
      csrfTokens.delete(sessionId)
      return false
    }

    // Validate token
    return tokenData.token === providedToken
  } catch (error) {
    console.error('CSRF token validation error:', error)
    return false
  }
}

/**
 * Clean up expired tokens to prevent memory leaks
 */
function cleanupExpiredTokens() {
  const now = Date.now()
  for (const [sessionId, tokenData] of csrfTokens.entries()) {
    if (now > tokenData.expires) {
      csrfTokens.delete(sessionId)
    }
  }
}

// Export validation function for use in other endpoints
export { validateCSRFToken as validateCSRF }