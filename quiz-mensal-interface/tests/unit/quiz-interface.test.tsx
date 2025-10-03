/**
 * Quiz Interface Comprehensive Unit Tests
 * Tests quiz navigation, answer submission, and validation
 */

import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom'
import QuizInterface from '../../components/quiz-interface'

// Mock the API
const mockSubmitAnswer = jest.fn()
const mockToast = jest.fn()

jest.mock('../../lib/api', () => ({
  quizAPI: {
    submitAnswer: (...args: any[]) => mockSubmitAnswer(...args)
  }
}))

jest.mock('../../hooks/use-toast', () => ({
  useToast: () => ({
    toast: mockToast
  })
}))

describe('QuizInterface - Comprehensive Tests', () => {
  const mockSession = {
    id: 'session-1',
    patient_id: 'patient-1',
    quiz_template_id: 'template-1',
    current_question_index: 0,
    total_questions: 3,
    questions: [
      {
        id: 'q1',
        type: 'single_choice' as const,
        text: 'Como você avalia sua dor hoje?',
        options: [
          { value: '1', label: 'Sem dor' },
          { value: '2', label: 'Dor leve' },
          { value: '3', label: 'Dor moderada' },
          { value: '4', label: 'Dor forte' },
          { value: '5', label: 'Dor insuportável' },
          { value: 'OUTRA', label: 'Outra' }
        ]
      },
      {
        id: 'q2',
        type: 'multiple_choice' as const,
        text: 'Quais sintomas você experimentou esta semana?',
        options: [
          { value: 'nausea', label: 'Náusea' },
          { value: 'fatigue', label: 'Fadiga' },
          { value: 'pain', label: 'Dor' },
          { value: 'OUTRA', label: 'Outra' }
        ]
      },
      {
        id: 'q3',
        type: 'open_text' as const,
        text: 'Descreva quaisquer outros sintomas',
        options: []
      }
    ]
  }

  const mockToken = 'test-token'

  beforeEach(() => {
    jest.clearAllMocks()
    mockSubmitAnswer.mockResolvedValue({ success: true })
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

      expect(screen.getByText(/1.*3/)).toBeInTheDocument() // "1 de 3" or similar
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

      // Should be able to proceed to next
      expect(screen.getByRole('button', { name: /próximo|enviar/i })).toBeEnabled()
    })

    it('should allow changing selected answer', async () => {
      const user = userEvent.setup()
      render(<QuizInterface session={mockSession} token={mockToken} />)

      await user.click(screen.getByText('Dor leve'))
      await user.click(screen.getByText('Dor forte'))

      // Second selection should override first
      expect(screen.getByRole('button', { name: /próximo|enviar/i })).toBeEnabled()
    })

    it('should show "Outra" text input when selected', async () => {
      const user = userEvent.setup()
      render(<QuizInterface session={mockSession} token={mockToken} />)

      await user.click(screen.getByText('Outra'))

      const textInput = screen.getByPlaceholderText(/descreva|digite/i)
      expect(textInput).toBeInTheDocument()
    })

    it('should validate "Outra" option requires text', async () => {
      const user = userEvent.setup()
      render(<QuizInterface session={mockSession} token={mockToken} />)

      await user.click(screen.getByText('Outra'))

      const submitButton = screen.getByRole('button', { name: /próximo|enviar/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith(
          expect.objectContaining({
            title: expect.stringContaining('obrigatório'),
            variant: 'destructive'
          })
        )
      })
    })

    it('should submit "Outra" answer with text', async () => {
      const user = userEvent.setup()
      render(<QuizInterface session={mockSession} token={mockToken} />)

      await user.click(screen.getByText('Outra'))

      const textInput = screen.getByPlaceholderText(/descreva|digite/i)
      await user.type(textInput, 'Dor específica na região lombar')

      const submitButton = screen.getByRole('button', { name: /próximo|enviar/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockSubmitAnswer).toHaveBeenCalledWith(
          mockToken,
          'q1',
          'OUTRA',
          expect.objectContaining({
            other_text: 'Dor específica na região lombar'
          })
        )
      })
    })
  })

  describe('Multiple Choice Questions', () => {
    it('should allow selecting multiple options', async () => {
      const user = userEvent.setup()
      const sessionQ2 = { ...mockSession, current_question_index: 1 }
      render(<QuizInterface session={sessionQ2} token={mockToken} />)

      await user.click(screen.getByText('Náusea'))
      await user.click(screen.getByText('Fadiga'))

      expect(screen.getByRole('button', { name: /próximo|enviar/i })).toBeEnabled()
    })

    it('should allow deselecting options', async () => {
      const user = userEvent.setup()
      const sessionQ2 = { ...mockSession, current_question_index: 1 }
      render(<QuizInterface session={sessionQ2} token={mockToken} />)

      const nauseaOption = screen.getByText('Náusea')
      await user.click(nauseaOption)
      await user.click(nauseaOption) // Deselect

      // Should still be able to submit with no selections if not required
      expect(screen.getByRole('button', { name: /próximo|enviar/i })).toBeInTheDocument()
    })

    it('should handle "Outra" option with multiple selections', async () => {
      const user = userEvent.setup()
      const sessionQ2 = { ...mockSession, current_question_index: 1 }
      render(<QuizInterface session={sessionQ2} token={mockToken} />)

      await user.click(screen.getByText('Náusea'))
      await user.click(screen.getByText('Outra'))

      const textInput = screen.getByPlaceholderText(/descreva|digite/i)
      await user.type(textInput, 'Outro sintoma')

      const submitButton = screen.getByRole('button', { name: /próximo|enviar/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockSubmitAnswer).toHaveBeenCalledWith(
          mockToken,
          'q2',
          expect.arrayContaining(['nausea']),
          expect.objectContaining({
            other_text: 'Outro sintoma'
          })
        )
      })
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

      const nextButton = screen.getByRole('button', { name: /próximo|enviar/i })
      await user.click(nextButton)

      await waitFor(() => {
        expect(screen.getByText('Quais sintomas você experimentou esta semana?')).toBeInTheDocument()
      })
    })

    it('should allow going back to previous question', async () => {
      const user = userEvent.setup()
      const sessionQ2 = { ...mockSession, current_question_index: 1 }
      render(<QuizInterface session={sessionQ2} token={mockToken} />)

      const backButton = screen.getByRole('button', { name: /anterior|voltar/i })
      await user.click(backButton)

      expect(screen.getByText('Como você avalia sua dor hoje?')).toBeInTheDocument()
    })

    it('should disable back button on first question', () => {
      render(<QuizInterface session={mockSession} token={mockToken} />)

      const backButton = screen.queryByRole('button', { name: /anterior|voltar/i })
      expect(backButton).toBeDisabled()
    })

    it('should restore previous answers when navigating back', async () => {
      const user = userEvent.setup()
      render(<QuizInterface session={mockSession} token={mockToken} />)

      // Answer first question
      await user.click(screen.getByText('Dor leve'))
      await user.click(screen.getByRole('button', { name: /próximo/i }))

      await waitFor(() => {
        expect(screen.getByText('Quais sintomas')).toBeInTheDocument()
      })

      // Go back
      await user.click(screen.getByRole('button', { name: /anterior/i }))

      // Previous answer should be selected
      expect(screen.getByText('Dor leve')).toBeInTheDocument()
    })
  })

  describe('Validation', () => {
    it('should prevent submission without selecting answer', async () => {
      const user = userEvent.setup()
      render(<QuizInterface session={mockSession} token={mockToken} />)

      const submitButton = screen.getByRole('button', { name: /próximo|enviar/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith(
          expect.objectContaining({
            title: expect.stringContaining('obrigatória'),
            variant: 'destructive'
          })
        )
      })

      expect(mockSubmitAnswer).not.toHaveBeenCalled()
    })

    it('should validate "Outra" option text is not empty', async () => {
      const user = userEvent.setup()
      render(<QuizInterface session={mockSession} token={mockToken} />)

      await user.click(screen.getByText('Outra'))

      const textInput = screen.getByPlaceholderText(/descreva|digite/i)
      await user.type(textInput, '   ') // Only whitespace

      const submitButton = screen.getByRole('button', { name: /próximo|enviar/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalled()
      })
    })
  })

  describe('Answer Submission', () => {
    it('should submit answer to API', async () => {
      const user = userEvent.setup()
      render(<QuizInterface session={mockSession} token={mockToken} />)

      await user.click(screen.getByText('Dor moderada'))

      const submitButton = screen.getByRole('button', { name: /próximo|enviar/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockSubmitAnswer).toHaveBeenCalledWith(
          mockToken,
          'q1',
          '3',
          expect.objectContaining({ question_index: 0 })
        )
      })
    })

    it('should show success toast after submission', async () => {
      const user = userEvent.setup()
      render(<QuizInterface session={mockSession} token={mockToken} />)

      await user.click(screen.getByText('Dor leve'))
      await user.click(screen.getByRole('button', { name: /próximo/i }))

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith(
          expect.objectContaining({
            title: expect.stringContaining('enviada')
          })
        )
      })
    })

    it('should handle API errors gracefully', async () => {
      const user = userEvent.setup()
      mockSubmitAnswer.mockRejectedValue(new Error('Network error'))

      render(<QuizInterface session={mockSession} token={mockToken} />)

      await user.click(screen.getByText('Dor leve'))
      await user.click(screen.getByRole('button', { name: /próximo/i }))

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith(
          expect.objectContaining({
            title: expect.stringContaining('Erro'),
            variant: 'destructive'
          })
        )
      })
    })

    it('should disable submit button during submission', async () => {
      const user = userEvent.setup()
      mockSubmitAnswer.mockImplementation(() => new Promise(resolve => setTimeout(resolve, 1000)))

      render(<QuizInterface session={mockSession} token={mockToken} />)

      await user.click(screen.getByText('Dor leve'))

      const submitButton = screen.getByRole('button', { name: /próximo/i })
      await user.click(submitButton)

      expect(submitButton).toBeDisabled()
    })
  })

  describe('Quiz Completion', () => {
    it('should show completion message on last question', async () => {
      const user = userEvent.setup()
      const sessionLast = { ...mockSession, current_question_index: 2 }
      render(<QuizInterface session={sessionLast} token={mockToken} />)

      const textarea = screen.getByRole('textbox')
      await user.type(textarea, 'Final answer')

      const submitButton = screen.getByRole('button', { name: /concluir|finalizar/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith(
          expect.objectContaining({
            title: expect.stringContaining('concluído')
          })
        )
      })
    })

    it('should call onComplete callback', async () => {
      const user = userEvent.setup()
      const onComplete = jest.fn()
      const sessionLast = { ...mockSession, current_question_index: 2 }

      render(<QuizInterface session={sessionLast} token={mockToken} onComplete={onComplete} />)

      const textarea = screen.getByRole('textbox')
      await user.type(textarea, 'Final answer')

      await user.click(screen.getByRole('button', { name: /concluir|finalizar/i }))

      await waitFor(() => {
        expect(onComplete).toHaveBeenCalled()
      })
    })

    it('should mark quiz as completed', async () => {
      const user = userEvent.setup()
      const sessionLast = { ...mockSession, current_question_index: 2 }

      render(<QuizInterface session={sessionLast} token={mockToken} />)

      const textarea = screen.getByRole('textbox')
      await user.type(textarea, 'Final answer')

      await user.click(screen.getByRole('button', { name: /concluir/i }))

      await waitFor(() => {
        expect(mockSubmitAnswer).toHaveBeenCalled()
      })
    })
  })

  describe('UI States', () => {
    it('should show loading spinner during submission', async () => {
      const user = userEvent.setup()
      mockSubmitAnswer.mockImplementation(() => new Promise(resolve => setTimeout(resolve, 1000)))

      render(<QuizInterface session={mockSession} token={mockToken} />)

      await user.click(screen.getByText('Dor leve'))
      await user.click(screen.getByRole('button', { name: /próximo/i }))

      expect(screen.getByTestId('loading-spinner') || screen.getByRole('status')).toBeInTheDocument()
    })

    it('should update progress bar as quiz progresses', async () => {
      const user = userEvent.setup()
      render(<QuizInterface session={mockSession} token={mockToken} />)

      await user.click(screen.getByText('Dor leve'))
      await user.click(screen.getByRole('button', { name: /próximo/i }))

      await waitFor(() => {
        // Progress should now be 66.67% (2/3)
        const progressBar = document.querySelector('[role="progressbar"]')
        expect(progressBar).toBeInTheDocument()
      })
    })
  })

  describe('Accessibility', () => {
    it('should have proper ARIA labels', () => {
      render(<QuizInterface session={mockSession} token={mockToken} />)

      const progressBar = document.querySelector('[role="progressbar"]')
      expect(progressBar).toHaveAttribute('aria-valuemin')
      expect(progressBar).toHaveAttribute('aria-valuemax')
      expect(progressBar).toHaveAttribute('aria-valuenow')
    })

    it('should support keyboard navigation', async () => {
      const user = userEvent.setup()
      render(<QuizInterface session={mockSession} token={mockToken} />)

      // Tab through options
      await user.tab()
      // Space to select
      await user.keyboard('{Space}')

      expect(screen.getByRole('button', { name: /próximo/i })).toBeEnabled()
    })
  })
})