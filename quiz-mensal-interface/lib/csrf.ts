/**
 * CSRF Token Validation Utilities
 */

import { NextRequest } from 'next/server'

// Token expiry time (1 hour)
export const TOKEN_EXPIRY = 60 * 60 * 1000

export const CSRF_COOKIE_NAME = 'csrf-token'

/**
 * Validate CSRF token
 */
export function validateCSRFToken(request: NextRequest, providedToken: string): boolean {
  try {
    const cookieToken = request.cookies.get(CSRF_COOKIE_NAME)?.value
    if (!cookieToken || !providedToken) {
      return false
    }

    return cookieToken === providedToken
  } catch (error) {
    console.error('CSRF token validation error:', error)
    return false
  }
}

export function buildCSRFCookie(token: string): { value: string; maxAge: number } {
  return {
    value: token,
    maxAge: TOKEN_EXPIRY / 1000
  }
}

// Alias for backward compatibility
export { validateCSRFToken as validateCSRF }
