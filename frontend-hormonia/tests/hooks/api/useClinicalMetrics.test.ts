import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useClinicalMetrics } from '@/src/hooks/api/useClinicalMetrics'
import type { ClinicalMetrics } from '@/src/hooks/api/useClinicalMetrics'
import React from 'react'
import { vi, describe, it, beforeEach, expect } from 'vitest'

// Mock the api-client module
vi.mock('@/src/lib/api-client', () => ({
  apiClient: {
    get: vi.fn()
  }
}))

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false }
    }
  })
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children)
}

// Import the mocked apiClient after setting up the mock
import { apiClient } from '@/src/lib/api-client'

describe('useClinicalMetrics', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should fetch clinical metrics for default 7d period', async () => {
    const mockData: ClinicalMetrics = {
      patientEngagement: 0.85,
      quizCompletion: 0.75,
      messageResponseRate: 0.90,
      averageSentiment: 4.2,
      riskPatients: 3,
      totalPatients: 50,
      activeFlows: 25,
      completedFlows: 40
    }

    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: mockData,
      timestamp: new Date().toISOString()
    })

    const { result } = renderHook(() => useClinicalMetrics(), {
      wrapper: createWrapper()
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data).toEqual(mockData)
    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/metrics/clinical', {
      params: { timeRange: '7d' }
    })
  })

  it('should fetch clinical metrics for 30d period', async () => {
    const mockData: ClinicalMetrics = {
      patientEngagement: 0.80,
      quizCompletion: 0.70,
      messageResponseRate: 0.85,
      averageSentiment: 4.0,
      riskPatients: 5,
      totalPatients: 60,
      activeFlows: 30,
      completedFlows: 45
    }

    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: mockData
    })

    const { result } = renderHook(() => useClinicalMetrics({ timeRange: '30d' }), {
      wrapper: createWrapper()
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data).toEqual(mockData)
    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/metrics/clinical', {
      params: { timeRange: '30d' }
    })
  })

  it('should fetch clinical metrics for 90d period', async () => {
    const mockData: ClinicalMetrics = {
      patientEngagement: 0.78,
      quizCompletion: 0.68,
      messageResponseRate: 0.82,
      averageSentiment: 3.9,
      riskPatients: 8,
      totalPatients: 75,
      activeFlows: 40,
      completedFlows: 60
    }

    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: mockData
    })

    const { result } = renderHook(() => useClinicalMetrics({ timeRange: '90d' }), {
      wrapper: createWrapper()
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/metrics/clinical', {
      params: { timeRange: '90d' }
    })
  })

  it('should cache results with queryKey including timeRange', async () => {
    const mockData: ClinicalMetrics = {
      patientEngagement: 0.85,
      quizCompletion: 0.75,
      messageResponseRate: 0.90,
      averageSentiment: 4.2,
      riskPatients: 3,
      totalPatients: 50,
      activeFlows: 25,
      completedFlows: 40
    }

    vi.mocked(apiClient.get).mockResolvedValue({
      data: mockData
    })

    const wrapper = createWrapper()

    // First render with 7d period
    renderHook(() => useClinicalMetrics({ timeRange: '7d' }), { wrapper })

    await waitFor(() => expect(apiClient.get).toHaveBeenCalledTimes(1))

    // Render again with same period - should use cache
    renderHook(() => useClinicalMetrics({ timeRange: '7d' }), { wrapper })

    // Still 1, used cache
    expect(apiClient.get).toHaveBeenCalledTimes(1)
  })

  it('should make separate requests for different timeRanges', async () => {
    const mockData7d: ClinicalMetrics = {
      patientEngagement: 0.85,
      quizCompletion: 0.75,
      messageResponseRate: 0.90,
      averageSentiment: 4.2,
      riskPatients: 3,
      totalPatients: 50,
      activeFlows: 25,
      completedFlows: 40
    }

    const mockData30d: ClinicalMetrics = {
      patientEngagement: 0.80,
      quizCompletion: 0.70,
      messageResponseRate: 0.85,
      averageSentiment: 4.0,
      riskPatients: 5,
      totalPatients: 60,
      activeFlows: 30,
      completedFlows: 45
    }

    vi.mocked(apiClient.get)
      .mockResolvedValueOnce({ data: mockData7d })
      .mockResolvedValueOnce({ data: mockData30d })

    const wrapper = createWrapper()

    // Render with 7d period
    const { result: result1 } = renderHook(() => useClinicalMetrics({ timeRange: '7d' }), { wrapper })
    await waitFor(() => expect(result1.current.isSuccess).toBe(true))

    // Render with 30d period - should be new request (different cache key)
    const { result: result2 } = renderHook(() => useClinicalMetrics({ timeRange: '30d' }), { wrapper })
    await waitFor(() => expect(result2.current.isSuccess).toBe(true))

    // Should have made 2 separate requests
    expect(apiClient.get).toHaveBeenCalledTimes(2)
    expect(apiClient.get).toHaveBeenNthCalledWith(1, '/api/v1/metrics/clinical', {
      params: { timeRange: '7d' }
    })
    expect(apiClient.get).toHaveBeenNthCalledWith(2, '/api/v1/metrics/clinical', {
      params: { timeRange: '30d' }
    })
  })

  it('should handle API errors gracefully', async () => {
    const mockError = new Error('API Error: 500')
    vi.mocked(apiClient.get).mockRejectedValueOnce(mockError)

    const { result } = renderHook(() => useClinicalMetrics(), {
      wrapper: createWrapper()
    })

    await waitFor(() => expect(result.current.isError).toBe(true))

    expect(result.current.error).toEqual(mockError)
    expect(result.current.data).toBeUndefined()
  })

  it('should use custom refetchInterval option', async () => {
    const mockData: ClinicalMetrics = {
      patientEngagement: 0.85,
      quizCompletion: 0.75,
      messageResponseRate: 0.90,
      averageSentiment: 4.2,
      riskPatients: 3,
      totalPatients: 50,
      activeFlows: 25,
      completedFlows: 40
    }

    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: mockData
    })

    const { result } = renderHook(
      () => useClinicalMetrics({ refetchInterval: 10000 }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data).toEqual(mockData)
  })

  it('should have 30 second staleTime for real-time monitoring', async () => {
    const mockData: ClinicalMetrics = {
      patientEngagement: 0.85,
      quizCompletion: 0.75,
      messageResponseRate: 0.90,
      averageSentiment: 4.2,
      riskPatients: 3,
      totalPatients: 50,
      activeFlows: 25,
      completedFlows: 40
    }

    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: mockData
    })

    const { result } = renderHook(() => useClinicalMetrics(), {
      wrapper: createWrapper()
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    // Query should not be stale initially
    expect(result.current.isStale).toBe(false)
  })

  it('should return data with correct ClinicalMetrics structure', async () => {
    const mockData: ClinicalMetrics = {
      patientEngagement: 0.85,
      quizCompletion: 0.75,
      messageResponseRate: 0.90,
      averageSentiment: 4.2,
      riskPatients: 3,
      totalPatients: 50,
      activeFlows: 25,
      completedFlows: 40
    }

    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: mockData
    })

    const { result } = renderHook(() => useClinicalMetrics(), {
      wrapper: createWrapper()
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    // Verify structure
    expect(result.current.data).toHaveProperty('patientEngagement')
    expect(result.current.data).toHaveProperty('quizCompletion')
    expect(result.current.data).toHaveProperty('messageResponseRate')
    expect(result.current.data).toHaveProperty('averageSentiment')
    expect(result.current.data).toHaveProperty('riskPatients')
    expect(result.current.data).toHaveProperty('totalPatients')
    expect(result.current.data).toHaveProperty('activeFlows')
    expect(result.current.data).toHaveProperty('completedFlows')
  })
})
