/**
 * Quiz Session Status Endpoint
 * Checks if user has a valid authentication session
 */

import { NextRequest, NextResponse } from 'next/server'
import { getSessionData } from '@/lib/quiz-session'
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
 * Check session status (with rate limiting and CORS)
 */
export async function GET(request: NextRequest) {
  return rateLimiters.sessionStatus(request, async () => {
    return withCors(async (req) => {
  try {
    const sessionData = getSessionData(request)

    if (!sessionData) {
      return NextResponse.json(
        { valid: false, message: 'No valid session found' },
        { status: 401 }
      )
    }

    return NextResponse.json({
      valid: true,
      message: 'Session is valid',
      expires_at: new Date(sessionData.expires).toISOString()
    })
  } catch (error) {
    console.error('Session status check error:', error)
    return NextResponse.json(
      { valid: false, error: 'Failed to check session status' },
      { status: 500 }
    )
  }
    })(request)
  })
}