/**
 * Quiz Session Management Utilities
 * SECURITY: Cookies are signed with HMAC-SHA256 to prevent tampering
 */

import { Buffer } from 'buffer'
import { NextRequest } from 'next/server'
import { createHmac, timingSafeEqual } from 'crypto'

export const SESSION_EXPIRY = 4 * 60 * 60 * 1000
export const SESSION_COOKIE_NAME = 'quiz-session-data'

// SECURITY: Secret key for HMAC signing (REQUIRED - no fallback allowed)
// Skip validation during build phase (NEXT_PHASE is set by Next.js during build)
const IS_BUILD_PHASE = process.env.NEXT_PHASE === 'phase-production-build'
const HMAC_SECRET = process.env.QUIZ_SESSION_SECRET

if (!IS_BUILD_PHASE) {
  if (!HMAC_SECRET) {
    throw new Error(
      '🚨 CRITICAL SECURITY ERROR: QUIZ_SESSION_SECRET environment variable is not set!\n' +
      'Generate a secure secret with: node -e "console.log(require(\'crypto\').randomBytes(32).toString(\'hex\'))"\n' +
      'Then add it to your .env file: QUIZ_SESSION_SECRET=your_generated_secret'
    )
  }

  if (HMAC_SECRET.length < 32) {
    throw new Error(
      '🚨 CRITICAL SECURITY ERROR: QUIZ_SESSION_SECRET must be at least 32 characters long!\n' +
      'Generate a secure secret with: node -e "console.log(require(\'crypto\').randomBytes(32).toString(\'hex\'))"'
    )
  }
}

export interface StoredQuizSession {
  token: string
  sessionData: any
  expires: number
}

/**
 * Generate HMAC signature for session data
 */
function signSession(data: string): string {
  return createHmac('sha256', HMAC_SECRET!)
    .update(data)
    .digest('base64url')
}

/**
 * Verify HMAC signature (timing-safe comparison)
 */
function verifySignature(data: string, signature: string): boolean {
  const expected = signSession(data)
  try {
    return timingSafeEqual(
      Buffer.from(signature, 'base64url'),
      Buffer.from(expected, 'base64url')
    )
  } catch {
    return false
  }
}

function encodeSession(payload: StoredQuizSession): string {
  const data = Buffer.from(JSON.stringify(payload), 'utf8').toString('base64url')
  const signature = signSession(data)
  // Format: data.signature
  return `${data}.${signature}`
}

function decodeSession(raw: string | undefined): StoredQuizSession | null {
  if (!raw) {
    return null
  }

  try {
    // Split data and signature
    const parts = raw.split('.')
    if (parts.length !== 2) {
      console.error('Invalid session cookie format (missing signature)')
      return null
    }

    const [data, signature] = parts

    // SECURITY: Verify signature before parsing
    if (!verifySignature(data, signature)) {
      console.error('Session cookie signature verification failed - possible tampering')
      return null
    }

    const parsed = JSON.parse(Buffer.from(data, 'base64url').toString('utf8'))
    if (
      typeof parsed !== 'object' || parsed === null ||
      typeof parsed.token !== 'string' ||
      typeof parsed.expires !== 'number'
    ) {
      return null
    }
    return parsed as StoredQuizSession
  } catch (error) {
    console.error('Failed to decode quiz session cookie:', error)
    return null
  }
}

export function createSessionCookie(token: string, sessionData: any) {
  const payload: StoredQuizSession = {
    token,
    sessionData,
    expires: Date.now() + SESSION_EXPIRY
  }

  return {
    value: encodeSession(payload),
    maxAge: Math.floor(SESSION_EXPIRY / 1000),
    payload
  }
}

export function getSessionData(request: NextRequest): StoredQuizSession | null {
  const raw = request.cookies.get(SESSION_COOKIE_NAME)?.value
  const payload = decodeSession(raw)

  if (!payload) {
    return null
  }

  if (Date.now() > payload.expires) {
    return null
  }

  return payload
}

export function rotateSessionCookie(payload: StoredQuizSession, newToken: string) {
  const updated: StoredQuizSession = {
    ...payload,
    token: newToken,
    expires: Date.now() + SESSION_EXPIRY
  }

  return {
    value: encodeSession(updated),
    maxAge: Math.floor(SESSION_EXPIRY / 1000),
    payload: updated
  }
}
