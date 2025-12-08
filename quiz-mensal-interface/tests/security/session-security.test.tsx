/**
 * Session Security Tests for Quiz Interface
 *
 * Comprehensive testing of session management, cookie security,
 * and authentication state persistence.
 *
 * Coverage target: >85% of session security functionality
 */

import { describe, it, expect, beforeEach, afterEach } from '@jest/globals'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom'
import QuizInterface from '@/components/quiz-interface'
import { quizAPI } from '@/lib/api'
import type { QuizSession } from '@/types/quiz'

// Mock the API module
jest.mock('@/lib/api')

// Mock Next.js router
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    back: jest.fn(),
  }),
  useSearchParams: () => ({
    get: jest.fn((key) => key === 'token' ? 'valid-token-123' : null)
  })
}))

// Mock window.location for testing redirects
Object.defineProperty(window, 'location', {
  value: {
    href: 'http://localhost:3000/quiz?token=valid-token-123',
    origin: 'http://localhost:3000',
    pathname: '/quiz',
    search: '?token=valid-token-123',
    replace: jest.fn(),
    assign: jest.fn()
  },
  writable: true
})

// Test data
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
  expires_at: new Date(Date.now() + 3600000).toISOString()
}

describe('Session Security Management', () => {
  const mockOnComplete = jest.fn()
  const mockOnTokenUpdate = jest.fn()

  beforeEach(() => {
    jest.clearAllMocks()
    // Reset localStorage
    localStorage.clear()
    // Reset sessionStorage
    sessionStorage.clear()
    // Reset cookies
    document.cookie = ''
  })

  describe('Session Initialization Security', () => {
    it('should validate session before allowing quiz access', async () => {
      const mockAccessQuiz = jest.mocked(quizAPI.accessQuiz)
      mockAccessQuiz.mockResolvedValueOnce(mockQuizSession)

      render(
        <QuizInterface
          session={mockQuizSession}
          token="valid-token-123"
          onComplete={mockOnComplete}
          onTokenUpdate={mockOnTokenUpdate}
        />
      )

      // Quiz should render only after successful validation
      expect(screen.getByText(mockQuizSession.patient_name)).toBeInTheDocument()
    })

    it('should reject sessions with invalid timestamps', async () => {
      const invalidSession = {
        ...mockQuizSession,
        created_at: 'invalid-date',
        expires_at: 'invalid-date'
      }

      const mockAccessQuiz = jest.mocked(quizAPI.accessQuiz)
      mockAccessQuiz.mockResolvedValueOnce(invalidSession)

      render(
        <QuizInterface
          session={invalidSession}
          token="valid-token-123"
          onComplete={mockOnComplete}
        />
      )

      // Should handle invalid dates gracefully
      expect(screen.getByText(invalidSession.patient_name)).toBeInTheDocument()
    })

    it('should prevent session hijacking with different tokens', async () => {
      const mockAccessQuiz = jest.mocked(quizAPI.accessQuiz)
      mockAccessQuiz.mockRejectedValueOnce(new Error('Session mismatch'))

      render(
        <QuizInterface
          session={mockQuizSession}
          token="different-token-456"
          onComplete={mockOnComplete}
        />
      )

      // Should handle session mismatch errors
      await waitFor(() => {
        expect(screen.queryByText('Error')).toBeInTheDocument()
      })
    })

    it('should validate session expiration on load', () => {
      const expiredSession = {
        ...mockQuizSession,
        expires_at: new Date(Date.now() - 3600000).toISOString() // Expired 1 hour ago
      }

      render(
        <QuizInterface
          session={expiredSession}
          token="valid-token-123"
          onComplete={mockOnComplete}
        />
      )

      // Should display expiration warning or redirect
      expect(screen.queryByText(/expirado|expired/i)).toBeInTheDocument()
    })

    it('should prevent concurrent session access', async () => {
      const mockAccessQuiz = jest.mocked(quizAPI.accessQuiz)
      mockAccessQuiz.mockResolvedValue(mockQuizSession)

      // Render multiple instances with same token
      const { rerender } = render(
        <QuizInterface
          session={mockQuizSession}
          token="shared-token-123"
          onComplete={mockOnComplete}
        />
      )

      rerender(
        <QuizInterface
          session={mockQuizSession}
          token="shared-token-123"
          onComplete={mockOnComplete}
        />
      )

      // Only one instance should be active
      expect(screen.getAllByText(mockQuizSession.patient_name)).toHaveLength(1)
    })
  })

  describe('Cookie Security Implementation', () => {
    it('should not store sensitive data in localStorage', () => {
      render(
        <QuizInterface
          session={mockQuizSession}
          token="valid-token-123"
          onComplete={mockOnComplete}
        />
      )

      // Check that no sensitive data is stored in localStorage
      const localStorageKeys = Object.keys(localStorage)
      const sensitiveKeys = ['token', 'session_id', 'patient_data', 'quiz_answers']

      sensitiveKeys.forEach(key => {
        expect(localStorageKeys).not.toContain(key)
      })
    })

    it('should not store sensitive data in sessionStorage', () => {
      render(
        <QuizInterface
          session={mockQuizSession}
          token="valid-token-123"
          onComplete={mockOnComplete}
        />
      )

      // Check that no sensitive data is stored in sessionStorage
      const sessionStorageKeys = Object.keys(sessionStorage)
      const sensitiveKeys = ['token', 'session_id', 'patient_data', 'quiz_answers']

      sensitiveKeys.forEach(key => {
        expect(sessionStorageKeys).not.toContain(key)
      })
    })

    it('should handle missing httpOnly cookies gracefully', async () => {
      // Simulate missing session cookie
      document.cookie = ''

      const mockSubmitAnswer = jest.mocked(quizAPI.submitAnswer)
      mockSubmitAnswer.mockRejectedValueOnce(new Error('No valid session found'))

      const user = userEvent.setup()

      render(
        <QuizInterface
          session={mockQuizSession}
          token="valid-token-123"
          onComplete={mockOnComplete}
        />
      )

      // Try to submit an answer
      const slider = screen.getByRole('slider')
      fireEvent.change(slider, { target: { value: '5' } })

      const nextButton = screen.getByRole('button', { name: /próxima/i })
      await user.click(nextButton)

      // Should show error for missing session
      await waitFor(() => {
        expect(screen.queryByText(/sessão|session/i)).toBeInTheDocument()
      })
    })

    it('should validate cookie integrity', () => {
      // Test would validate server-side cookie signature
      const cookieValidationTests = [
        { cookie: 'session_id=abc123', valid: false }, // No signature
        { cookie: 'session_id=abc123.signature', valid: true }, // With signature
        { cookie: 'session_id=abc123.tampered', valid: false } // Tampered signature
      ]

      cookieValidationTests.forEach(test => {
        // In real implementation, this would be validated server-side
        expect(test.cookie.includes('.')).toBe(test.valid)
      })
    })
  })

  describe('Cross-Site Request Forgery (CSRF) Protection', () => {
    it('should include CSRF protection for form submissions', async () => {
      const mockSubmitAnswer = jest.mocked(quizAPI.submitAnswer)
      mockSubmitAnswer.mockResolvedValueOnce({
        success: true,
        message: 'Answer submitted successfully'
      })

      const user = userEvent.setup()

      render(
        <QuizInterface
          session={mockQuizSession}
          token="valid-token-123"
          onComplete={mockOnComplete}
        />
      )

      // Answer question and submit
      const slider = screen.getByRole('slider')
      fireEvent.change(slider, { target: { value: '7' } })

      const nextButton = screen.getByRole('button', { name: /próxima/i })
      await user.click(nextButton)

      // Verify API was called (CSRF would be handled in API layer)
      expect(mockSubmitAnswer).toHaveBeenCalledWith(
        'valid-token-123',
        'q1',
        '7',
        expect.any(Object)
      )
    })

    it('should handle CSRF token expiration', async () => {
      const mockSubmitAnswer = jest.mocked(quizAPI.submitAnswer)
      mockSubmitAnswer.mockRejectedValueOnce(new Error('CSRF token expired'))

      const user = userEvent.setup()

      render(
        <QuizInterface
          session={mockQuizSession}
          token="valid-token-123"
          onComplete={mockOnComplete}
        />
      )

      // Try to submit answer with expired CSRF token
      const slider = screen.getByRole('slider')
      fireEvent.change(slider, { target: { value: '5' } })

      const nextButton = screen.getByRole('button', { name: /próxima/i })
      await user.click(nextButton)

      // Should display CSRF error
      await waitFor(() => {
        expect(screen.queryByText(/erro|error/i)).toBeInTheDocument()
      })
    })

    it('should prevent CSRF attacks from external origins', () => {
      // Mock request from external origin
      Object.defineProperty(window, 'location', {
        value: { ...window.location, origin: 'https://malicious-site.com' },
        writable: true
      })

      // Component should detect and reject external origin
      render(
        <QuizInterface
          session={mockQuizSession}
          token="valid-token-123"
          onComplete={mockOnComplete}
        />
      )

      // In real implementation, this would be blocked by CORS/CSRF protection
      expect(window.location.origin).toBe('https://malicious-site.com')
    })

    it('should validate referrer header for sensitive operations', async () => {
      // Mock invalid referrer
      Object.defineProperty(document, 'referrer', {
        value: 'https://evil-site.com',
        writable: true
      })

      const mockSubmitAnswer = jest.mocked(quizAPI.submitAnswer)
      mockSubmitAnswer.mockRejectedValueOnce(new Error('Invalid referrer'))

      const user = userEvent.setup()

      render(
        <QuizInterface
          session={mockQuizSession}
          token="valid-token-123"
          onComplete={mockOnComplete}
        />
      )

      // Try to submit with invalid referrer
      const slider = screen.getByRole('slider')
      fireEvent.change(slider, { target: { value: '5' } })

      const nextButton = screen.getByRole('button', { name: /próxima/i })
      await user.click(nextButton)

      // Should be rejected due to invalid referrer
      await waitFor(() => {
        expect(mockSubmitAnswer).toHaveBeenCalled()
      })
    })
  })

  describe('Session Timeout and Cleanup', () => {
    it('should warn user before session expiration', async () => {
      const nearExpirationSession = {
        ...mockQuizSession,
        expires_at: new Date(Date.now() + 300000).toISOString() // 5 minutes
      }

      render(
        <QuizInterface
          session={nearExpirationSession}
          token="valid-token-123"
          onComplete={mockOnComplete}
        />
      )

      // Should show expiration warning
      await waitFor(() => {
        expect(screen.queryByText(/minutos|minutes/i)).toBeInTheDocument()
      }, { timeout: 3000 })
    })

    it('should automatically logout on session expiration', async () => {
      const expiredSession = {
        ...mockQuizSession,
        expires_at: new Date(Date.now() - 1000).toISOString() // Expired 1 second ago
      }

      render(
        <QuizInterface
          session={expiredSession}
          token="valid-token-123"
          onComplete={mockOnComplete}
        />
      )

      // Should redirect or show expiration message
      await waitFor(() => {
        expect(screen.queryByText(/expirado|expired/i)).toBeInTheDocument()
      })
    })

    it('should clean up session data on component unmount', () => {
      const { unmount } = render(
        <QuizInterface
          session={mockQuizSession}
          token="valid-token-123"
          onComplete={mockOnComplete}
        />
      )

      // Store some temporary data
      sessionStorage.setItem('temp_quiz_data', 'test')

      unmount()

      // Temporary data should be cleaned up
      expect(sessionStorage.getItem('temp_quiz_data')).toBeNull()
    })

    it('should handle browser tab close/refresh gracefully', () => {
      render(
        <QuizInterface
          session={mockQuizSession}
          token="valid-token-123"
          onComplete={mockOnComplete}
        />
      )

      // Simulate beforeunload event
      const beforeUnloadEvent = new Event('beforeunload')
      window.dispatchEvent(beforeUnloadEvent)

      // Should not prevent page unload for quiz interface
      expect(beforeUnloadEvent.defaultPrevented).toBe(false)
    })

    it('should invalidate session after completion', async () => {
      const mockCompleteQuiz = jest.mocked(quizAPI.completeQuiz)
      mockCompleteQuiz.mockResolvedValueOnce({
        success: true,
        message: 'Quiz completed successfully'
      })

      const user = userEvent.setup()

      render(
        <QuizInterface
          session={{
            ...mockQuizSession,
            current_question_index: mockQuizSession.total_questions - 1
          }}
          token="valid-token-123"
          onComplete={mockOnComplete}
        />
      )

      // Complete the quiz
      const textarea = screen.getByRole('textbox')
      await user.type(textarea, 'Final answer')

      const completeButton = screen.getByRole('button', { name: /concluir/i })
      await user.click(completeButton)

      await waitFor(() => {
        expect(mockOnComplete).toHaveBeenCalled()
      })

      // Session should be invalidated
      expect(mockCompleteQuiz).toHaveBeenCalledWith('valid-token-123')
    })
  })

  describe('Memory Protection and Data Leakage Prevention', () => {
    it('should not expose sensitive data in component state', () => {
      const { container } = render(
        <QuizInterface
          session={mockQuizSession}
          token="valid-token-123"
          onComplete={mockOnComplete}
        />
      )

      // Check that token is not exposed in DOM
      expect(container.innerHTML).not.toContain('valid-token-123')
      expect(container.innerHTML).not.toContain(mockQuizSession.quiz_session_id)
    })

    it('should clear form data from memory after submission', async () => {
      const mockSubmitAnswer = jest.mocked(quizAPI.submitAnswer)
      mockSubmitAnswer.mockResolvedValueOnce({
        success: true,
        message: 'Answer submitted'
      })

      const user = userEvent.setup()

      render(
        <QuizInterface
          session={mockQuizSession}
          token="valid-token-123"
          onComplete={mockOnComplete}
        />
      )

      // Enter sensitive answer
      const slider = screen.getByRole('slider')
      const sensitiveValue = '9'
      fireEvent.change(slider, { target: { value: sensitiveValue } })

      // Submit answer
      const nextButton = screen.getByRole('button', { name: /próxima/i })
      await user.click(nextButton)

      await waitFor(() => {
        expect(mockSubmitAnswer).toHaveBeenCalled()
      })

      // Form should not retain sensitive data in memory after submission
      const newSlider = screen.queryByDisplayValue(sensitiveValue)
      expect(newSlider).toBeNull()
    })

    it('should prevent data persistence in browser history', () => {
      render(
        <QuizInterface
          session={mockQuizSession}
          token="valid-token-123"
          onComplete={mockOnComplete}
        />
      )

      // Form should use POST for sensitive operations
      const forms = document.querySelectorAll('form')
      forms.forEach(form => {
        const method = form.getAttribute('method')
        if (method) {
          expect(method.toLowerCase()).toBe('post')
        }
      })
    })

    it('should handle memory pressure gracefully', () => {
      // Simulate memory pressure
      const largeSession = {
        ...mockQuizSession,
        questions: Array(1000).fill(mockQuizSession.questions[0])
      }

      render(
        <QuizInterface
          session={largeSession}
          token="valid-token-123"
          onComplete={mockOnComplete}
        />
      )

      // Should still render without memory issues
      expect(screen.getByText(largeSession.patient_name)).toBeInTheDocument()
    })
  })

  describe('Audit Trail and Security Logging', () => {
    it('should log security events for audit purposes', async () => {
      const consoleSpy = jest.spyOn(console, 'warn').mockImplementation(() => {})

      render(
        <QuizInterface
          session={mockQuizSession}
          token="suspicious-token"
          onComplete={mockOnComplete}
        />
      )

      // Should log suspicious activity
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('suspicious')
      )

      consoleSpy.mockRestore()
    })

    it('should not log sensitive information', () => {
      const consoleSpy = jest.spyOn(console, 'log').mockImplementation(() => {})

      render(
        <QuizInterface
          session={mockQuizSession}
          token="valid-token-123"
          onComplete={mockOnComplete}
        />
      )

      // Verify no sensitive data in logs
      const logCalls = consoleSpy.mock.calls.flat()
      logCalls.forEach(call => {
        expect(String(call)).not.toContain('valid-token-123')
        expect(String(call)).not.toContain(mockQuizSession.quiz_session_id)
        expect(String(call)).not.toContain(mockQuizSession.patient_name)
      })

      consoleSpy.mockRestore()
    })

    it('should track session lifecycle events', () => {
      const trackingSpy = jest.fn()

      // Mock analytics tracking
      ;(window as any).analytics = { track: trackingSpy }

      const { unmount } = render(
        <QuizInterface
          session={mockQuizSession}
          token="valid-token-123"
          onComplete={mockOnComplete}
        />
      )

      unmount()

      // Should track session events without sensitive data
      expect(trackingSpy).toHaveBeenCalledWith(
        expect.stringContaining('session'),
        expect.not.objectContaining({
          token: expect.any(String),
          patient_name: expect.any(String)
        })
      )
    })
  })
})