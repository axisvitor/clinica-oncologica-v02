import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { usePhysicianRiskAssessments } from '@/hooks/api/usePhysicianRiskAssessments'
import React from 'react'
import { vi, describe, it, beforeEach, expect } from 'vitest'

// Mock the api-client module
vi.mock('@/lib/api-client', () => ({
  apiClient: {
    request: vi.fn()
  }
}))

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false }
    }
  })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

// Import the mocked apiClient after setting up the mock
import { apiClient } from '@/lib/api-client'

describe('usePhysicianRiskAssessments', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should fetch all patient risk assessments', async () => {
    const mockData = {
      assessments: [
        {
          patient_id: 'p1',
          patient_name: 'João Silva',
          risk_level: 'high' as const,
          risk_score: 0.65,
          risk_category: 'medication_adherence',
          assessment_date: '2025-10-06T10:00:00-03:00',
          recent_alerts: [
            {
              severity: 'high' as const,
              type: 'medication_alert',
              message: 'Baixa adesão ao tratamento',
              created_at: '2025-10-06T09:00:00-03:00'
            }
          ],
          trend: 'worsening' as const,
          last_interaction: '2025-10-05T14:30:00-03:00'
        }
      ],
      summary: {
        total_patients: 50,
        by_risk_level: {
          critical: 2,
          high: 8,
          medium: 15,
          low: 25
        },
        requiring_attention: 10
      },
      last_updated: '2025-10-06T14:30:00-03:00'
    }

    vi.mocked(apiClient.request).mockResolvedValueOnce(mockData)

    const { result } = renderHook(() => usePhysicianRiskAssessments(), {
      wrapper: createWrapper()
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data).toEqual(mockData)
    expect(apiClient.request).toHaveBeenCalledWith(
      '/api/v2/physician/risk-assessments?page=1&size=20'
    )
  })

  it('should filter by patient_id when provided', async () => {
    const mockData = {
      assessments: [],
      summary: {
        total_patients: 0,
        by_risk_level: {
          critical: 0,
          high: 0,
          medium: 0,
          low: 0
        },
        requiring_attention: 0
      },
      last_updated: '2025-10-06T14:30:00-03:00'
    }

    vi.mocked(apiClient.request).mockResolvedValueOnce(mockData)

    const { result } = renderHook(
      () => usePhysicianRiskAssessments({ patient_id: 'p123' }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(apiClient.request).toHaveBeenCalledWith(
      '/api/v2/physician/risk-assessments?patient_id=p123&page=1&size=20'
    )
  })

  it('should NOT refetch on window focus', async () => {
    const mockData = {
      assessments: [],
      summary: {
        total_patients: 0,
        by_risk_level: {
          critical: 0,
          high: 0,
          medium: 0,
          low: 0
        },
        requiring_attention: 0
      },
      last_updated: '2025-10-06T14:30:00-03:00'
    }

    vi.mocked(apiClient.request).mockResolvedValueOnce(mockData)

    const { result } = renderHook(() => usePhysicianRiskAssessments(), {
      wrapper: createWrapper()
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    // Clear previous calls
    vi.clearAllMocks()

    // Simulate window focus
    window.dispatchEvent(new Event('focus'))

    // Wait a bit to ensure no additional calls
    await new Promise(resolve => setTimeout(resolve, 100))

    // Should not trigger additional request due to refetchOnWindowFocus: false
    expect(apiClient.request).not.toHaveBeenCalled()
  })

  it('should use different cache for different patient_ids', async () => {
    const mockData = {
      assessments: [],
      summary: {
        total_patients: 0,
        by_risk_level: {
          critical: 0,
          high: 0,
          medium: 0,
          low: 0
        },
        requiring_attention: 0
      },
      last_updated: '2025-10-06T14:30:00-03:00'
    }

    vi.mocked(apiClient.request).mockResolvedValue(mockData)

    const wrapper = createWrapper()

    // First patient
    const { result: result1 } = renderHook(
      () => usePhysicianRiskAssessments({ patient_id: 'p1' }),
      { wrapper }
    )

    await waitFor(() => expect(result1.current.isSuccess).toBe(true))

    // Different patient - should be new request (different cache key)
    const { result: result2 } = renderHook(
      () => usePhysicianRiskAssessments({ patient_id: 'p2' }),
      { wrapper }
    )

    await waitFor(() => expect(result2.current.isSuccess).toBe(true))

    // Should have made 2 separate requests (different query keys)
    expect(apiClient.request).toHaveBeenCalledTimes(2)
    expect(apiClient.request).toHaveBeenCalledWith(
      '/api/v2/physician/risk-assessments?patient_id=p1&page=1&size=20'
    )
    expect(apiClient.request).toHaveBeenCalledWith(
      '/api/v2/physician/risk-assessments?patient_id=p2&page=1&size=20'
    )
  })

  it('should respect enabled option', () => {
    const { result } = renderHook(
      () => usePhysicianRiskAssessments({ enabled: false }),
      { wrapper: createWrapper() }
    )

    expect(result.current.fetchStatus).toBe('idle')
    expect(apiClient.request).not.toHaveBeenCalled()
  })

  it('should handle API errors gracefully', async () => {
    const mockError = new Error('API Error: 500')
    vi.mocked(apiClient.request).mockRejectedValue(mockError)

    const { result } = renderHook(() => usePhysicianRiskAssessments(), {
      wrapper: createWrapper()
    })

    await waitFor(() => expect(result.current.isError).toBe(true), {
      timeout: 5000
    })

    expect(result.current.error).toEqual(mockError)
    expect(result.current.data).toBeUndefined()
  })

  it('should retry failed requests up to 2 times', async () => {
    const mockError = new Error('Network error')
    // Mock to reject all attempts (initial + 2 retries = 3 total)
    vi.mocked(apiClient.request)
      .mockRejectedValueOnce(mockError)
      .mockRejectedValueOnce(mockError)
      .mockRejectedValueOnce(mockError)

    const { result } = renderHook(() => usePhysicianRiskAssessments(), {
      wrapper: createWrapper()
    })

    await waitFor(() => expect(result.current.isError).toBe(true), {
      timeout: 5000
    })

    // Should retry 2 times (initial + 2 retries = 3 total calls)
    expect(apiClient.request).toHaveBeenCalledTimes(3)
  })
})
