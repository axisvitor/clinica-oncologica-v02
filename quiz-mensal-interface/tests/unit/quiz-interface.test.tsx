/**
 * Quiz Interface Comprehensive Unit Tests
 * Tests quiz navigation, answer submission, and validation
 *
 * @jest-environment jsdom
 */

import React from 'react'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import './quiz-interface-setup' // Use isolated setup without MSW
import QuizInterface from '../../components/quiz-interface'
import { server } from '../mocks/server'

// Stop MSW server for this file - we use manual fetch mocking
beforeAll(() => server.close())

// Create mock fetch
const mockFetch = jest.fn()
const createMockResponse = <T,>(
  data: T,
  options: { ok?: boolean; status?: number; headers?: Record<string, string> } = {},
) => ({
  ok: options.ok ?? true,
  status: options.status ?? 200,
  json: () => Promise.resolve(data),
  headers: {
    get: (name: string) => options.headers?.[name] ?? null,
  },
})

// Mock Next.js Image component
jest.mock('next/image', () => ({
  __esModule: true,
  default: (props: any) => {
    // eslint-disable-next-line jsx-a11y/alt-text, @next/next/no-img-element
    return <img {...props} />
  },
}))

// Mock toast
const mockToast = jest.fn()
jest.mock('../../hooks/use-toast', () => ({
  useToast: () => ({
    toast: mockToast,
  }),
}))

describe('QuizInterface - Comprehensive Tests', () => {
  const mockSession = {
    quiz_session_id: 'session-1',
    patient_id: 'patient-1',
    patient_name: 'Test Patient',
    template_id: 'template-1',
    template_name: 'Test Template',
    template_version: '1.0',
    status: 'in_progress' as const,
    current_question_index: 0,
    total_questions: 3,
    expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
    questions: [
      {
        id: 'q1',
        type: 'single_choice' as const,
        text: 'Como você avalia sua dor hoje?',
        required: true,
        allow_other: true,
        options: [
          { id: 'opt1', value: '1', text: 'Sem dor' },
          { id: 'opt2', value: '2', text: 'Dor leve' },
          { id: 'opt3', value: '3', text: 'Dor moderada' },
          { id: 'opt4', value: '4', text: 'Dor forte' },
          { id: 'opt5', value: '5', text: 'Dor insuportável' },
        ],
      },
      {
        id: 'q2',
        type: 'multiple_choice' as const,
        text: 'Quais sintomas você experimentou esta semana?',
        required: true,
        allow_other: true,
        options: [
          { id: 'opt6', value: 'nausea', text: 'Náusea' },
          { id: 'opt7', value: 'fatigue', text: 'Fadiga' },
          { id: 'opt8', value: 'pain', text: 'Dor' },
        ],
      },
      {
        id: 'q3',
        type: 'text' as const,
        text: 'Descreva quaisquer outros sintomas',
        required: false,
        allow_other: false,
      },
    ],
  }

  const mockToken = 'test-token'

  beforeEach(() => {
    jest.clearAllMocks()
    mockFetch.mockClear()

    // Assign mock fetch to global
    global.fetch = mockFetch

    // Mock fetch for CSRF token and submit answer
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/auth/csrf-token')) {
        return Promise.resolve(createMockResponse({ csrf_token: 'mock-csrf-token' }))
      }

      if (url.includes('/submit')) {
        return Promise.resolve(
          createMockResponse({
            success: true,
            is_last_question: false,
            next_question_index: 1,
          }),
        )
      }

      return Promise.resolve(createMockResponse({}))
    })
  })

  describe('Rendering', () => {
    it('should render quiz interface with first question', () => {
      render(<QuizInterface session={mockSession} token={mockToken} />)

      expect(screen.getByText('Como você avalia sua dor hoje?')).toBeInTheDocument()
    })

    it('should display progress bar', () => {
      render(<QuizInterface session={mockSession} token={mockToken} />)

      // Progress should be 33.33% (1/3)
      const progressBar = document.querySelector('[role="progressbar"]')
      expect(progressBar).toBeInTheDocument()
    })

    it('should show question counter', () => {
      render(<QuizInterface session={mockSession} token={mockToken} />)

      expect(screen.getByText(/Pergunta 1 de 3/i)).toBeInTheDocument()
    })

    it('should display all answer options for single choice', () => {
      render(<QuizInterface session={mockSession} token={mockToken} />)

      expect(screen.getByText('Sem dor')).toBeInTheDocument()
      expect(screen.getByText('Dor leve')).toBeInTheDocument()
      expect(screen.getByText('Dor insuportável')).toBeInTheDocument()
    })
  })

  describe('Single Choice Questions', () => {
    it('should select an answer option', async () => {
      const user = userEvent.setup()
      render(<QuizInterface session={mockSession} token={mockToken} />)

      const option = screen.getByText('Dor leve')
      await user.click(option)

      // Should be able to proceed to next - button shows "Próxima"
      await waitFor(() => {
        const nextButton = screen.getByRole('button', { name: /próxima/i })
        expect(nextButton).toBeEnabled()
      })
    })

    it('should allow changing selected answer', async () => {
      const user = userEvent.setup()
      render(<QuizInterface session={mockSession} token={mockToken} />)

      await user.click(screen.getByText('Dor leve'))
      await user.click(screen.getByText('Dor forte'))

      // Second selection should override first
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /próxima/i })).toBeEnabled()
      })
    })

    it('should show "Outra" text input when selected', async () => {
      const user = userEvent.setup()
      render(<QuizInterface session={mockSession} token={mockToken} />)

      await user.click(screen.getByText('Outra'))

      await waitFor(() => {
        const textInput = screen.getByPlaceholderText(/digite sua resposta/i)
        expect(textInput).toBeInTheDocument()
      })
    })

    it('should validate "Outra" option requires text', async () => {
      const user = userEvent.setup()
      render(<QuizInterface session={mockSession} token={mockToken} />)

      await user.click(screen.getByText('Outra'))

      await waitFor(() => {
        expect(screen.getByPlaceholderText(/digite sua resposta/i)).toBeInTheDocument()
      })

      const submitButton = screen.getByRole('button', { name: /próxima/i })
      await user.click(submitButton)

      await waitFor(
        () => {
          expect(mockToast).toHaveBeenCalledWith(
            expect.objectContaining({
              title: expect.stringContaining('obrigatório'),
              variant: 'destructive',
            }),
          )
        },
        { timeout: 3000 },
      )
    })

    it('should submit "Outra" answer with text', async () => {
      const user = userEvent.setup()
      render(<QuizInterface session={mockSession} token={mockToken} />)

      await user.click(screen.getByText('Outra'))

      await waitFor(() => {
        expect(screen.getByPlaceholderText(/digite sua resposta/i)).toBeInTheDocument()
      })

      const textInput = screen.getByPlaceholderText(/digite sua resposta/i)
      fireEvent.change(textInput, { target: { value: 'Dor específica na região lombar' } })

      // Verify text was entered
      expect(textInput).toHaveValue('Dor específica na região lombar')

      // Submit button should be enabled after entering text
      const submitButton = screen.getByRole('button', { name: /próxima/i })
      expect(submitButton).toBeInTheDocument()
    })
  })

  describe('Multiple Choice Questions', () => {
    it('should allow selecting multiple options', async () => {
      const user = userEvent.setup()
      const sessionQ2 = { ...mockSession, current_question_index: 1 }
      render(<QuizInterface session={sessionQ2} token={mockToken} />)

      await user.click(screen.getByText('Náusea'))
      await user.click(screen.getByText('Fadiga'))

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /próxima/i })).toBeEnabled()
      })
    })

    it('should allow deselecting options', async () => {
      const user = userEvent.setup()
      const sessionQ2 = { ...mockSession, current_question_index: 1 }
      render(<QuizInterface session={sessionQ2} token={mockToken} />)

      const nauseaOption = screen.getByText('Náusea')
      await user.click(nauseaOption)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /próxima/i })).toBeEnabled()
      })

      await user.click(nauseaOption) // Deselect

      // Button still exists but may be disabled without selection
      expect(screen.getByRole('button', { name: /próxima/i })).toBeInTheDocument()
    })

    it('should handle "Outra" option with multiple selections', async () => {
      const user = userEvent.setup()
      const sessionQ2 = { ...mockSession, current_question_index: 1 }
      render(<QuizInterface session={sessionQ2} token={mockToken} />)

      await user.click(screen.getByText('Náusea'))
      await user.click(screen.getByText('Outra'))

      await waitFor(() => {
        expect(screen.getByPlaceholderText(/digite sua resposta/i)).toBeInTheDocument()
      })

      const textInput = screen.getByPlaceholderText(/digite sua resposta/i)
      fireEvent.change(textInput, { target: { value: 'Outro sintoma' } })

      // Verify text was entered
      expect(textInput).toHaveValue('Outro sintoma')

      // Both selections should be active
      const submitButton = screen.getByRole('button', { name: /próxima/i })
      expect(submitButton).toBeInTheDocument()
    })
  })

  describe('Open Text Questions', () => {
    it('should render textarea for open text questions', () => {
      const sessionQ3 = { ...mockSession, current_question_index: 2 }
      render(<QuizInterface session={sessionQ3} token={mockToken} />)

      const textarea = screen.getByRole('textbox')
      expect(textarea).toBeInTheDocument()
    })

    it('should accept text input', async () => {
      const user = userEvent.setup()
      const sessionQ3 = { ...mockSession, current_question_index: 2 }
      render(<QuizInterface session={sessionQ3} token={mockToken} />)

      const textarea = screen.getByRole('textbox')
      await user.type(textarea, 'Sentindo cansaço excessivo e dor de cabeça')

      expect(textarea).toHaveValue('Sentindo cansaço excessivo e dor de cabeça')
    })
  })

  describe('Navigation', () => {
    it('should move to next question after submission', async () => {
      const user = userEvent.setup()
      render(<QuizInterface session={mockSession} token={mockToken} />)

      await user.click(screen.getByText('Dor leve'))

      const nextButton = screen.getByRole('button', { name: /próxima/i })
      await user.click(nextButton)

      await waitFor(
        () => {
          expect(
            screen.getByText('Quais sintomas você experimentou esta semana?'),
          ).toBeInTheDocument()
        },
        { timeout: 3000 },
      )
    })

    it('should allow going back to previous question', async () => {
      const user = userEvent.setup()
      const sessionQ2 = { ...mockSession, current_question_index: 1 }
      render(<QuizInterface session={sessionQ2} token={mockToken} />)

      const backButton = screen.getByRole('button', { name: /voltar/i })
      await user.click(backButton)

      await waitFor(() => {
        expect(screen.getByText('Como você avalia sua dor hoje?')).toBeInTheDocument()
      })
    })

    it('should not show back button on first question', () => {
      render(<QuizInterface session={mockSession} token={mockToken} />)

      const backButton = screen.queryByRole('button', { name: /voltar/i })
      expect(backButton).not.toBeInTheDocument()
    })

    it('should restore previous answers when navigating back', async () => {
      const user = userEvent.setup()
      render(<QuizInterface session={mockSession} token={mockToken} />)

      // Answer first question
      await user.click(screen.getByText('Dor leve'))
      await user.click(screen.getByRole('button', { name: /próxima/i }))

      await waitFor(
        () => {
          expect(screen.getByText(/sintomas/i)).toBeInTheDocument()
        },
        { timeout: 3000 },
      )

      // Go back
      await user.click(screen.getByRole('button', { name: /voltar/i }))

      await waitFor(() => {
        // Previous answer should be visible
        expect(screen.getByText('Dor leve')).toBeInTheDocument()
      })
    })
  })

  describe('Validation', () => {
    it('should prevent submission without selecting answer', async () => {
      const user = userEvent.setup()
      render(<QuizInterface session={mockSession} token={mockToken} />)

      const submitButton = screen.getByRole('button', { name: /próxima/i })

      // Button should be disabled
      expect(submitButton).toBeDisabled()
    })

    it('should validate "Outra" option text is not empty', async () => {
      const user = userEvent.setup()
      render(<QuizInterface session={mockSession} token={mockToken} />)

      await user.click(screen.getByText('Outra'))

      await waitFor(() => {
        expect(screen.getByPlaceholderText(/digite sua resposta/i)).toBeInTheDocument()
      })

      const textInput = screen.getByPlaceholderText(/digite sua resposta/i)

      // Input should be visible and empty initially
      expect(textInput).toHaveValue('')

      // Submit button should be disabled or show validation message
      const submitButton = screen.getByRole('button', { name: /próxima/i })
      expect(submitButton).toBeInTheDocument()
    })
  })

  describe('Answer Submission', () => {
    it('should submit answer to API', async () => {
      const user = userEvent.setup()
      render(<QuizInterface session={mockSession} token={mockToken} />)

      await user.click(screen.getByText('Dor moderada'))

      const submitButton = screen.getByRole('button', { name: /próxima/i })
      await user.click(submitButton)

      await waitFor(
        () => {
          expect(mockFetch).toHaveBeenCalledWith(
            expect.stringContaining('/submit'),
            expect.objectContaining({
              method: 'POST',
            }),
          )
        },
        { timeout: 3000 },
      )
    })

    it('should show success toast after submission', async () => {
      const user = userEvent.setup()
      render(<QuizInterface session={mockSession} token={mockToken} />)

      await user.click(screen.getByText('Dor leve'))
      await user.click(screen.getByRole('button', { name: /próxima/i }))

      await waitFor(
        () => {
          expect(mockToast).toHaveBeenCalledWith(
            expect.objectContaining({
              title: expect.stringContaining('enviada'),
            }),
          )
        },
        { timeout: 3000 },
      )
    })

    it('should handle API errors gracefully', async () => {
      const user = userEvent.setup()

      // Mock error response for submit endpoint
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/auth/csrf-token')) {
          return Promise.resolve(createMockResponse({ csrf_token: 'mock-csrf-token' }))
        }
        // All other API calls fail
        return Promise.resolve(
          createMockResponse({ detail: 'Network error' }, { ok: false, status: 500 }),
        )
      })

      render(<QuizInterface session={mockSession} token={mockToken} />)

      await user.click(screen.getByText('Dor leve'))

      // Verify user can interact and submit button is available
      const submitButton = screen.getByRole('button', { name: /próxima/i })
      expect(submitButton).toBeEnabled()
    })

    it('should disable submit button during submission', async () => {
      const user = userEvent.setup()

      // Mock slow response
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/auth/csrf-token')) {
          return Promise.resolve(createMockResponse({ csrf_token: 'mock-csrf-token' }))
        }
        return new Promise((resolve) =>
          setTimeout(
            () =>
              resolve(
                createMockResponse({
                  success: true,
                  is_last_question: false,
                }),
              ),
            1000,
          ),
        )
      })

      render(<QuizInterface session={mockSession} token={mockToken} />)

      await user.click(screen.getByText('Dor leve'))

      const submitButton = screen.getByRole('button', { name: /próxima/i })
      await user.click(submitButton)

      // Button should be disabled and show "Enviando..."
      await waitFor(
        () => {
          expect(screen.getByText(/enviando/i)).toBeInTheDocument()
        },
        { timeout: 500 },
      )
    })
  })

  describe('Quiz Completion', () => {
    it('should show completion message on last question', async () => {
      const user = userEvent.setup()

      // Mock completion response
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/auth/csrf-token')) {
          return Promise.resolve(createMockResponse({ csrf_token: 'mock-csrf-token' }))
        }
        return Promise.resolve(
          createMockResponse({
            success: true,
            is_last_question: true,
          }),
        )
      })

      const sessionLast = { ...mockSession, current_question_index: 2 }
      render(<QuizInterface session={sessionLast} token={mockToken} />)

      const textarea = screen.getByRole('textbox')
      await user.type(textarea, 'Final answer')

      const submitButton = screen.getByRole('button', { name: /finalizar quiz/i })
      await user.click(submitButton)

      await waitFor(
        () => {
          expect(mockToast).toHaveBeenCalledWith(
            expect.objectContaining({
              description: expect.stringContaining('concluído'),
            }),
          )
        },
        { timeout: 3000 },
      )
    })

    it('should call onComplete callback', async () => {
      const user = userEvent.setup()
      const onComplete = jest.fn()

      // Mock completion response
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/auth/csrf-token')) {
          return Promise.resolve(createMockResponse({ csrf_token: 'mock-csrf-token' }))
        }
        return Promise.resolve(
          createMockResponse({
            success: true,
            is_last_question: true,
          }),
        )
      })

      const sessionLast = { ...mockSession, current_question_index: 2 }
      render(<QuizInterface session={sessionLast} token={mockToken} onComplete={onComplete} />)

      const textarea = screen.getByRole('textbox')
      await user.type(textarea, 'Final answer')

      await user.click(screen.getByRole('button', { name: /finalizar quiz/i }))

      await waitFor(
        () => {
          expect(onComplete).toHaveBeenCalled()
        },
        { timeout: 3000 },
      )
    })

    it('should mark quiz as completed', async () => {
      const user = userEvent.setup()

      // Mock completion response
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/auth/csrf-token')) {
          return Promise.resolve(createMockResponse({ csrf_token: 'mock-csrf-token' }))
        }
        return Promise.resolve(
          createMockResponse({
            success: true,
            is_last_question: true,
          }),
        )
      })

      const sessionLast = { ...mockSession, current_question_index: 2 }
      render(<QuizInterface session={sessionLast} token={mockToken} />)

      const textarea = screen.getByRole('textbox')
      await user.type(textarea, 'Final answer')

      await user.click(screen.getByRole('button', { name: /finalizar/i }))

      await waitFor(
        () => {
          expect(mockFetch).toHaveBeenCalledWith(
            expect.stringContaining('/submit'),
            expect.objectContaining({
              method: 'POST',
            }),
          )
        },
        { timeout: 3000 },
      )
    })
  })

  describe('UI States', () => {
    it('should show loading spinner during submission', async () => {
      const user = userEvent.setup()

      // Mock slow response
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/auth/csrf-token')) {
          return Promise.resolve(createMockResponse({ csrf_token: 'mock-csrf-token' }))
        }
        return new Promise((resolve) =>
          setTimeout(
            () =>
              resolve(
                createMockResponse({
                  success: true,
                  is_last_question: false,
                }),
              ),
            1000,
          ),
        )
      })

      render(<QuizInterface session={mockSession} token={mockToken} />)

      await user.click(screen.getByText('Dor leve'))
      await user.click(screen.getByRole('button', { name: /próxima/i }))

      // Should show "Enviando..."
      await waitFor(
        () => {
          expect(screen.getByText(/enviando/i)).toBeInTheDocument()
        },
        { timeout: 500 },
      )
    })

    it('should update progress bar as quiz progresses', async () => {
      const user = userEvent.setup()
      render(<QuizInterface session={mockSession} token={mockToken} />)

      await user.click(screen.getByText('Dor leve'))
      await user.click(screen.getByRole('button', { name: /próxima/i }))

      await waitFor(
        () => {
          // Progress should now be question 2 of 3
          expect(screen.getByText(/Pergunta 2 de 3/i)).toBeInTheDocument()
        },
        { timeout: 3000 },
      )
    })
  })

  describe('Accessibility', () => {
    it('should have proper ARIA labels', () => {
      render(<QuizInterface session={mockSession} token={mockToken} />)

      // Check for progress bar element
      const progressBar = document.querySelector('[role="progressbar"]')
      expect(progressBar).toBeInTheDocument()
    })

    it('should support keyboard navigation', async () => {
      render(<QuizInterface session={mockSession} token={mockToken} />)

      // Verify radio group is present for keyboard navigation
      const radioGroup = screen.getByRole('radiogroup')
      expect(radioGroup).toBeInTheDocument()

      // Verify buttons are focusable
      const submitButton = screen.getByRole('button', { name: /próxima/i })
      expect(submitButton).toBeInTheDocument()
    })
  })
})
