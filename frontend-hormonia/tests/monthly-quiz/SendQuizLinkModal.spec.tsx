import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

vi.mock('@/lib/api-client', () => {
  return {
    apiClient: {
      monthlyQuiz: {
        createLink: vi.fn()
      },
      quiz: {
        templates: vi.fn()
      }
    }
  }
})

// Mock Radix Select to a native select for test stability
vi.mock('@/components/ui/select', () => {
  const React = require('react')
  return {
    Select: ({ value, onValueChange, children }: any) => (
      <select data-testid="mock-select" value={value ?? ''} onChange={(e: any) => onValueChange?.(e.target.value)}>
        {children}
      </select>
    ),
    SelectTrigger: ({ children }: any) => <>{children}</>,
    SelectContent: ({ children }: any) => <>{children}</>,
    SelectValue: ({ children }: any) => <>{children}</>,
    SelectItem: ({ value, children }: any) => <option value={value}>{children}</option>,
  }
})

import { apiClient } from '@/lib/api-client'
import { SendQuizLinkModal } from '@/components/quiz/SendQuizLinkModal'

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  })

  return render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>
  )
}

describe('SendQuizLinkModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('envia link com sucesso e fecha o modal', async () => {
    ;(apiClient.quiz.templates as any).mockResolvedValueOnce({
      items: [
        { id: 'template-1', name: 'Monthly Template', version: '1.0' }
      ]
    })

    ;(apiClient.monthlyQuiz.createLink as any).mockResolvedValueOnce({
      id: 'session-123',
      link_url: 'https://app/quiz?token=abc',
      token: 'abc',
      delivery_attempts: [{ status: 'sent' }],
      last_delivery_status: 'sent'
    })

    const onOpenChange = vi.fn()

    const { container } = renderWithQuery(
      <SendQuizLinkModal
        open
        onOpenChange={onOpenChange}
        patientId="patient-1"
        patientName="Maria"
      />
    )

    // Aguarda opção do template aparecer e seleciona via <select> mockado
    await screen.findByText(/Monthly Template \(v1\.0\)/i)
    const selects = screen.getAllByTestId('mock-select')
    fireEvent.change(selects[0], { target: { value: 'template-1' } })

    // Submete
    const submitBtn = screen.getByRole('button', { name: /enviar/i })
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(apiClient.monthlyQuiz.createLink).toHaveBeenCalledWith({
        patient_id: 'patient-1',
        quiz_template_id: 'template-1',
        delivery_method: 'whatsapp',
        expiry_hours: 72
      })
    })

    await waitFor(() => {
      expect(onOpenChange).toHaveBeenCalledWith(false)
    })
  })

  it('mostra erro quando API falha', async () => {
    ;(apiClient.quiz.templates as any).mockResolvedValueOnce({
      items: [
        { id: 'template-1', name: 'Monthly Template', version: '1.0' }
      ]
    })

    ;(apiClient.monthlyQuiz.createLink as any).mockRejectedValueOnce({
      data: { message: 'Falha ao criar link' }
    })

    const onOpenChange = vi.fn()

    const { container } = renderWithQuery(
      <SendQuizLinkModal
        open
        onOpenChange={onOpenChange}
        patientId="patient-1"
        patientName="Maria"
      />
    )

    await screen.findByText(/Monthly Template \(v1\.0\)/i)
    const selects = screen.getAllByTestId('mock-select')
    fireEvent.change(selects[0], { target: { value: 'template-1' } })

    const submitBtn = screen.getByRole('button', { name: /enviar/i })
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(apiClient.monthlyQuiz.createLink).toHaveBeenCalled()
    })
  })
})
