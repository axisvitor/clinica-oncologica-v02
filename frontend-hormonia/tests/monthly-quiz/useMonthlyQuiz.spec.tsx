import { describe, it, expect, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'

// Mock apiClient before importing the hook
vi.mock('@/lib/api-client', () => {
  return {
    apiClient: {
      monthlyQuiz: {
        createLink: vi.fn(),
        bulkCreate: vi.fn(),
      },
    },
  }
})

import { apiClient } from '@/lib/api-client'
import { useMonthlyQuiz } from '@/features/monthly-quiz/hooks/useMonthlyQuiz'

describe('useMonthlyQuiz - createQuizLink', () => {
  it('should call API and return created link on success', async () => {
    const mockResponse = {
      id: 'link-123',
      quiz_session_id: 'session-123',
      patient_id: 'patient-1',
      quiz_template_id: 'template-1',
      token: 'token-abc',
      link: 'https://sistema.com/quiz/session-123',
      delivery_method: 'whatsapp',
      status: 'pending',
      expires_at: new Date(Date.now() + 72 * 3600 * 1000).toISOString(),
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }

    const mockedCreate = (apiClient.monthlyQuiz.createLink as unknown as ReturnType<typeof vi.fn>)
    mockedCreate.mockResolvedValueOnce(mockResponse)

    const { result } = renderHook(() => useMonthlyQuiz())

    const payload = {
      patient_id: 'patient-1',
      quiz_template_id: 'template-1',
      delivery_method: 'whatsapp' as const,
      expiry_hours: 72,
      custom_message: 'Por favor, responda o questionário quando puder.'
    }

    let response: any
    await act(async () => {
      response = await result.current.createQuizLink(payload)
    })

    expect(apiClient.monthlyQuiz.createLink).toHaveBeenCalledWith(payload)
    expect(response).toEqual(mockResponse)
    expect(result.current.error).toBeNull()
    expect(result.current.loading).toBe(false)
  })

  it('should set error and return null on API failure', async () => {
    const mockedCreate = (apiClient.monthlyQuiz.createLink as unknown as ReturnType<typeof vi.fn>)
    mockedCreate.mockRejectedValueOnce(new Error('Failed to create quiz link'))

    const { result } = renderHook(() => useMonthlyQuiz())

    const payload = {
      patient_id: 'patient-2',
      quiz_template_id: 'template-2',
      delivery_method: 'whatsapp' as const,
      expiry_hours: 48,
    }

    let response: any
    await act(async () => {
      response = await result.current.createQuizLink(payload)
    })

    expect(apiClient.monthlyQuiz.createLink).toHaveBeenCalledWith(payload)
    expect(response).toBeNull()
    expect(result.current.error).toBeTruthy()
    expect(result.current.loading).toBe(false)
  })
})
