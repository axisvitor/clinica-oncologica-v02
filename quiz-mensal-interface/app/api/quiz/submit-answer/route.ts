/**
 * Secure Quiz Answer Submission Endpoint
 * Handles quiz answer submissions with CSRF protection and cookie-based authentication
 */

import { NextRequest, NextResponse } from 'next/server'
import { validateCSRF } from '../../csrf-token/route'
import { getSessionData, updateSessionToken } from '../initialize-session/route'
import { quizAPI } from '@/lib/api'

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
    const response = await quizAPI.submitAnswer(
      sessionData.token,
      question_id,
      response_value,
      { other_text, ...response_metadata }
    )

    // Handle token rotation if new token is provided
    if (response.new_token) {
      updateSessionToken(request, response.new_token)
    }

    return NextResponse.json({
      success: true,
      message: response.message || 'Answer submitted successfully',
      response_id: response.response_id,
      is_last_question: response.is_last_question
    })
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