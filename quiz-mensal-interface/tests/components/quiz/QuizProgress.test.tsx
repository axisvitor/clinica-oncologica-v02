import React from 'react'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { QuizProgress } from '@/components/quiz/QuizProgress'

describe('QuizProgress Component', () => {
  const defaultProps = {
    currentQuestion: 3,
    totalQuestions: 10,
    progress: 30,
  }

  describe('Rendering', () => {
    it('should render progress bar', () => {
      render(<QuizProgress {...defaultProps} />)

      // Check the progress container exists
      expect(screen.getByText(/Pergunta 3 de 10/)).toBeInTheDocument()
    })

    it('should display current question and total', () => {
      render(<QuizProgress {...defaultProps} />)

      expect(screen.getByText('Pergunta 3 de 10')).toBeInTheDocument()
    })

    it('should display percentage', () => {
      render(<QuizProgress {...defaultProps} />)

      expect(screen.getByText('30%')).toBeInTheDocument()
    })

    it('should round percentage to nearest integer', () => {
      render(<QuizProgress currentQuestion={1} totalQuestions={3} progress={33.33} />)

      expect(screen.getByText('33%')).toBeInTheDocument()
    })
  })

  describe('Progress Calculation', () => {
    it('should display 0% at start', () => {
      render(<QuizProgress currentQuestion={1} totalQuestions={10} progress={0} />)

      expect(screen.getByText('0%')).toBeInTheDocument()
    })

    it('should display 100% when complete', () => {
      render(<QuizProgress currentQuestion={10} totalQuestions={10} progress={100} />)

      expect(screen.getByText('100%')).toBeInTheDocument()
    })

    it('should display 50% at halfway', () => {
      render(<QuizProgress currentQuestion={5} totalQuestions={10} progress={50} />)

      expect(screen.getByText('50%')).toBeInTheDocument()
    })
  })

  describe('Question Counter', () => {
    it('should update question counter correctly', () => {
      const { rerender } = render(
        <QuizProgress currentQuestion={1} totalQuestions={10} progress={10} />,
      )

      expect(screen.getByText('Pergunta 1 de 10')).toBeInTheDocument()

      rerender(<QuizProgress currentQuestion={5} totalQuestions={10} progress={50} />)
      expect(screen.getByText('Pergunta 5 de 10')).toBeInTheDocument()

      rerender(<QuizProgress currentQuestion={10} totalQuestions={10} progress={100} />)
      expect(screen.getByText('Pergunta 10 de 10')).toBeInTheDocument()
    })
  })

  describe('Edge Cases', () => {
    it('should handle single question quiz', () => {
      render(<QuizProgress currentQuestion={1} totalQuestions={1} progress={100} />)

      expect(screen.getByText('Pergunta 1 de 1')).toBeInTheDocument()
      expect(screen.getByText('100%')).toBeInTheDocument()
    })

    it('should handle large number of questions', () => {
      render(<QuizProgress currentQuestion={50} totalQuestions={100} progress={50} />)

      expect(screen.getByText('Pergunta 50 de 100')).toBeInTheDocument()
    })
  })
})
