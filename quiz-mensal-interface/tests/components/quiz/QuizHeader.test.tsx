import React from 'react'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { QuizHeader } from '@/components/quiz/QuizHeader'

describe('QuizHeader Component', () => {
  const defaultProps = {
    patientName: 'João Silva',
    templateName: 'Questionário Mensal',
  }

  describe('Rendering', () => {
    it('should render header with patient name', () => {
      render(<QuizHeader {...defaultProps} />)

      expect(screen.getByText(/Quiz Mensal - João Silva/)).toBeInTheDocument()
    })

    it('should render template name as heading', () => {
      render(<QuizHeader {...defaultProps} />)

      const heading = screen.getByRole('heading', { level: 1 })
      expect(heading).toHaveTextContent('Questionário Mensal')
    })

    it('should display patient name in badge', () => {
      render(<QuizHeader {...defaultProps} />)

      expect(screen.getByText(/Quiz Mensal - João Silva/)).toBeInTheDocument()
    })
  })

  describe('Props Variations', () => {
    it('should handle different patient names', () => {
      render(<QuizHeader patientName="Maria Santos" templateName="Test Template" />)

      expect(screen.getByText(/Quiz Mensal - Maria Santos/)).toBeInTheDocument()
    })

    it('should handle different template names', () => {
      render(<QuizHeader patientName="Test" templateName="Custom Quiz Template" />)

      const heading = screen.getByRole('heading', { level: 1 })
      expect(heading).toHaveTextContent('Custom Quiz Template')
    })

    it('should handle long names', () => {
      const longName = 'João Carlos da Silva Ferreira Santos'
      render(<QuizHeader patientName={longName} templateName="Questionário" />)

      expect(screen.getByText(new RegExp(longName))).toBeInTheDocument()
    })
  })

  describe('Styling', () => {
    it('should have centered text', () => {
      const { container } = render(<QuizHeader {...defaultProps} />)

      const headerDiv = container.firstChild
      expect(headerDiv).toHaveClass('text-center')
    })

    it('should have proper spacing', () => {
      const { container } = render(<QuizHeader {...defaultProps} />)

      const headerDiv = container.firstChild
      expect(headerDiv).toHaveClass('space-y-4')
    })
  })

  describe('Accessibility', () => {
    it('should have accessible heading structure', () => {
      render(<QuizHeader {...defaultProps} />)

      const heading = screen.getByRole('heading', { level: 1 })
      expect(heading).toBeInTheDocument()
    })
  })
})
