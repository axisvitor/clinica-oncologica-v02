/**
 * CSRF Token Validation Utilities
 *
 * NOTE: This implementation is part of an alternative authentication flow
 * using httpOnly cookies (see SECURITY_FIXES.md). The main quiz flow uses
 * JWT token rotation instead (see lib/api.ts and lib/secure-token-manager.ts).
 *
 * These utilities are used by:
 * - app/api/csrf-token/route.ts
 * - app/api/quiz/submit-answer/route.ts
 * - app/api/quiz/initialize-session/route.ts
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
