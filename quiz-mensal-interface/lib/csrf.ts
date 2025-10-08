/**
 * CSRF Token Validation Utilities
 */

import { NextRequest } from 'next/server'

// Simple in-memory store for CSRF tokens (in production, use Redis or database)
const csrfTokens = new Map<string, { token: string, expires: number }>()

// Token expiry time (1 hour)
export const TOKEN_EXPIRY = 60 * 60 * 1000

/**
 * Store CSRF token
 */
export function storeCSRFToken(sessionId: string, token: string): void {
  const expires = Date.now() + TOKEN_EXPIRY
  csrfTokens.set(sessionId, { token, expires })
  cleanupExpiredTokens()
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

// Alias for backward compatibility
export { validateCSRFToken as validateCSRF }
