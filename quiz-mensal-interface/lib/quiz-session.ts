/**
 * Quiz Session Management Utilities
 */

import { Buffer } from 'buffer'
import { NextRequest } from 'next/server'

export const SESSION_EXPIRY = 4 * 60 * 60 * 1000
export const SESSION_COOKIE_NAME = 'quiz-session-data'

export interface StoredQuizSession {
  token: string
  sessionData: any
  expires: number
}

function encodeSession(payload: StoredQuizSession): string {
  return Buffer.from(JSON.stringify(payload), 'utf8').toString('base64url')
}

function decodeSession(raw: string | undefined): StoredQuizSession | null {
  if (!raw) {
    return null
  }

  try {
    const parsed = JSON.parse(Buffer.from(raw, 'base64url').toString('utf8'))
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
