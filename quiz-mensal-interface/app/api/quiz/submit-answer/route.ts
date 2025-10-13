/**
 * Secure Quiz Answer Submission Endpoint
 * Handles quiz answer submissions with CSRF protection and cookie-based authentication
 */

import { NextRequest, NextResponse } from 'next/server'
import { validateCSRF } from '@/lib/csrf'
import { getSessionData, rotateSessionCookie, SESSION_COOKIE_NAME } from '@/lib/quiz-session'
import { quizAPI } from '@/lib/api'

// Force dynamic rendering for this route
export const dynamic = 'force-dynamic'

/**
 * Submit quiz answer with CSRF protection
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { question_id, response_value, other_text, response_metadata } = body

    // Validate CSRF token
    const csrfToken = request.headers.get('X-CSRF-Token')
    if (!csrfToken || !validateCSRF(request, csrfToken)) {
      return NextResponse.json(
        { error: 'Invalid CSRF token' },
        { status: 403 }
      )
    }

    // Get session data from cookie
    const sessionData = getSessionData(request)
    if (!sessionData) {
      return NextResponse.json(
        { error: 'No valid session found' },
        { status: 401 }
      )
    }

    if (!question_id || response_value === undefined) {
      return NextResponse.json(
        { error: 'Question ID and response value are required' },
        { status: 400 }
      )
    }

    // Submit answer using the session token
    const submission = await quizAPI.submitAnswer(
      sessionData.token,
      question_id,
      response_value,
      { other_text, ...response_metadata }
    )

    const response = NextResponse.json({
      success: true,
      message: submission.message || 'Answer submitted successfully',
      response_id: submission.response_id,
      is_last_question: submission.is_last_question
    })

    // Handle token rotation if new token is provided
    if (submission.new_token) {
      const rotated = rotateSessionCookie(sessionData, submission.new_token)
      response.cookies.set(SESSION_COOKIE_NAME, rotated.value, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'strict',
        maxAge: rotated.maxAge,
        path: '/'
      })
    }

    return response
  } catch (error) {
    console.error('Answer submission error:', error)

    if (error instanceof Error) {
      return NextResponse.json(
        { error: error.message },
        { status: (error as any).status || 500 }
      )
    }

    return NextResponse.json(
      { error: 'Failed to submit answer' },
      { status: 500 }
    )
  }
}
