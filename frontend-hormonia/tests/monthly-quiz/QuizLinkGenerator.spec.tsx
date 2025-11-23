import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

// Mock the hook used by the component
vi.mock('@/features/monthly-quiz/hooks/useMonthlyQuiz', () => {
  return {
    useMonthlyQuiz: () => ({
      loading: false,
      error: null,
      createQuizLink: vi.fn(async (_payload: any) => ({
        id: 'link-123',
        link_url: 'https://sistema.com/quiz/session-123'
      }))
    })
  }
})

import { QuizLinkGenerator } from '@/features/monthly-quiz/components/QuizLinkGenerator'

describe('QuizLinkGenerator component', () => {
  it('should call createQuizLink and show generated link', async () => {
    render(
      <QuizLinkGenerator
        patientId="patient-1"
        quizTemplateId="template-1"
      />
    )

    // Click the "Gerar Link" button
    const button = screen.getByRole('button', { name: /gerar link/i })
    fireEvent.click(button)

    // Expect generated link to appear
    await waitFor(() => {
      expect(screen.getByText(/Link Gerado:/i)).toBeInTheDocument()
      expect(screen.getByDisplayValue('https://sistema.com/quiz/session-123')).toBeInTheDocument()
    })
  })
})
