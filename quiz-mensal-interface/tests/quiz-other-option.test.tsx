/**
 * Quiz "Outra" Option Tests
 * Tests the "other" option functionality for single and multiple choice questions
 */

import React from 'react'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom'
import QuizInterface from '@/components/quiz-interface'
import { QuizSessionBuilder, QuizQuestionBuilder } from './fixtures/quiz-fixtures'

// Mock fetch for API calls
const mockFetch = jest.fn()
global.fetch = mockFetch

describe('Quiz "Outra" Option Tests', () => {
  const mockOnComplete = jest.fn()

  // Create a session with single choice question that has allow_other
  const createSingleChoiceSession = () =>
    new QuizSessionBuilder()
      .withQuestions([
        new QuizQuestionBuilder()
          .withId('q-single-other')
          .withType('single_choice')
          .withText('Qual é o principal sintoma?')
          .withOptions([
            { id: 'opt1', value: 'headache', text: 'Dor de cabeça' },
            { id: 'opt2', value: 'nausea', text: 'Náusea' },
          ])
          .allowOther(true)
          .build(),
      ])
      .build()

  // Create a session with multiple choice question that has allow_other
  const createMultipleChoiceSession = () =>
    new QuizSessionBuilder()
      .withQuestions([
        new QuizQuestionBuilder()
          .withId('q-multi-other')
          .withType('multiple_choice')
          .withText('Quais sintomas você está sentindo?')
          .withOptions([
            { id: 'opt1', value: 'pain', text: 'Dor' },
            { id: 'opt2', value: 'insomnia', text: 'Insônia' },
          ])
          .allowOther(true)
          .build(),
      ])
      .build()

  beforeEach(() => {
    jest.clearAllMocks()
    mockFetch.mockReset()
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('csrf-token')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ csrfToken: 'test-csrf-token' }),
        })
      }
      if (url.includes('submit-answer')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              is_last_question: true,
              session_status: 'completed',
            }),
        })
      }
      return Promise.reject(new Error('Unknown URL'))
    })
  })

  describe('Single Choice - "Outra" Option', () => {
    it('should render "Outra" option for single choice question with allow_other', () => {
      const session = createSingleChoiceSession()
      render(<QuizInterface session={session} onComplete={mockOnComplete} />)

      expect(screen.getByText('Outra')).toBeInTheDocument()
    })

    it('should show text input when "Outra" is selected', async () => {
      const user = userEvent.setup()
      const session = createSingleChoiceSession()

      render(<QuizInterface session={session} onComplete={mockOnComplete} />)

      const outraLabel = screen.getByText('Outra')
      await user.click(outraLabel)

      await waitFor(() => {
        const textInput = screen.getByPlaceholderText(/Digite sua resposta personalizada/i)
        expect(textInput).toBeInTheDocument()
      })
    })

    it('should allow typing custom text', async () => {
      const user = userEvent.setup()
      const session = createSingleChoiceSession()

      render(<QuizInterface session={session} onComplete={mockOnComplete} />)

      const outraLabel = screen.getByText('Outra')
      await user.click(outraLabel)

      const textInput = await screen.findByPlaceholderText(/Digite sua resposta personalizada/i)

      // Use fireEvent for reliable text input
      fireEvent.change(textInput, { target: { value: 'Tontura persistente' } })

      expect(textInput).toHaveValue('Tontura persistente')
    })

    it('should hide text input when selecting regular option', async () => {
      const user = userEvent.setup()
      const session = createSingleChoiceSession()

      render(<QuizInterface session={session} onComplete={mockOnComplete} />)

      // First select Outra
      const outraLabel = screen.getByText('Outra')
      await user.click(outraLabel)

      await waitFor(() => {
        expect(
          screen.getByPlaceholderText(/Digite sua resposta personalizada/i),
        ).toBeInTheDocument()
      })

      // Then select a regular option
      const regularOption = screen.getByLabelText('Dor de cabeça')
      await user.click(regularOption)

      await waitFor(() => {
        expect(
          screen.queryByPlaceholderText(/Digite sua resposta personalizada/i),
        ).not.toBeInTheDocument()
      })
    })
  })

  describe('Multiple Choice - "Outra" Option', () => {
    it('should render "Outra" option for multiple choice question with allow_other', () => {
      const session = createMultipleChoiceSession()
      render(<QuizInterface session={session} onComplete={mockOnComplete} />)

      expect(screen.getByText('Outra')).toBeInTheDocument()
    })

    it('should show text input when "Outra" is checked', async () => {
      const user = userEvent.setup()
      const session = createMultipleChoiceSession()

      render(<QuizInterface session={session} onComplete={mockOnComplete} />)

      const outraCheckbox = screen.getByRole('checkbox', { name: 'Outra' })
      await user.click(outraCheckbox)

      await waitFor(() => {
        const textInput = screen.getByPlaceholderText(/Digite sua resposta personalizada/i)
        expect(textInput).toBeInTheDocument()
      })
    })

    it('should allow selecting multiple options including Outra', async () => {
      const user = userEvent.setup()
      const session = createMultipleChoiceSession()

      render(<QuizInterface session={session} onComplete={mockOnComplete} />)

      const dorCheckbox = screen.getByRole('checkbox', { name: 'Dor' })
      const outraCheckbox = screen.getByRole('checkbox', { name: 'Outra' })

      await user.click(dorCheckbox)
      await user.click(outraCheckbox)

      expect(dorCheckbox).toBeChecked()
      expect(outraCheckbox).toBeChecked()
    })

    it('should hide text input when unchecking "Outra"', async () => {
      const user = userEvent.setup()
      const session = createMultipleChoiceSession()

      render(<QuizInterface session={session} onComplete={mockOnComplete} />)

      const outraCheckbox = screen.getByRole('checkbox', { name: 'Outra' })

      // Check Outra
      await user.click(outraCheckbox)
      await waitFor(() => {
        expect(
          screen.getByPlaceholderText(/Digite sua resposta personalizada/i),
        ).toBeInTheDocument()
      })

      // Uncheck Outra
      await user.click(outraCheckbox)
      await waitFor(() => {
        expect(
          screen.queryByPlaceholderText(/Digite sua resposta personalizada/i),
        ).not.toBeInTheDocument()
      })
    })
  })

  describe('Form Validation', () => {
    it('should allow typing custom text with "Outra" selected', async () => {
      const user = userEvent.setup()
      const session = createSingleChoiceSession()

      render(<QuizInterface session={session} onComplete={mockOnComplete} />)

      // Select Outra
      const outraLabel = screen.getByText('Outra')
      await user.click(outraLabel)

      // Type custom text using fireEvent for reliable input
      const textInput = await screen.findByPlaceholderText(/Digite sua resposta personalizada/i)
      fireEvent.change(textInput, { target: { value: 'Tontura persistente' } })

      // Verify text was entered
      expect(textInput).toHaveValue('Tontura persistente')
    })

    it('should enable submit button with valid answer', async () => {
      const user = userEvent.setup()
      const session = createSingleChoiceSession()

      render(<QuizInterface session={session} onComplete={mockOnComplete} />)

      // Select a regular option
      const regularOption = screen.getByLabelText('Dor de cabeça')
      await user.click(regularOption)

      // Submit button should be accessible
      const submitButton = screen.getByTestId('submit-quiz')
      expect(submitButton).toBeInTheDocument()
    })
  })
})
