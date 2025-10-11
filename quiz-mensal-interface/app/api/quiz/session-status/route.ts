/**
 * Quiz Session Status Endpoint
 * Checks if user has a valid authentication session
 */

import { NextRequest, NextResponse } from 'next/server'
import { getSessionData } from '@/lib/quiz-session'

// Force dynamic rendering for this route
export const dynamic = 'force-dynamic'

/**
 * Check session status
 */
export async function GET(request: NextRequest) {
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
}