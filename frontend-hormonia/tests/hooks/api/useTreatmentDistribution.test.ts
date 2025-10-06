import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useTreatmentDistribution } from '@/src/hooks/api/useTreatmentDistribution'
import type { TreatmentDistributionResponse } from '@/src/types/api-wave2'
import React from 'react'
import { vi, describe, it, beforeEach, expect } from 'vitest'

// Mock the api-client module
vi.mock('@/src/lib/api-client', () => ({
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
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children)
}

// Import the mocked apiClient after setting up the mock
import { apiClient } from '@/src/lib/api-client'

describe('useTreatmentDistribution', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should fetch treatment distribution for default 30d period', async () => {
    const mockData: TreatmentDistributionResponse = {
      period: '30d',
      total_patients: 1260,
      distribution: [
        {
          treatment_type: 'Quimioterapia',
          count: 450,
          percentage: 35.71,
          active_patients: 380,
          avg_treatment_days: 45,
          color: '#3b82f6'
        },
        {
          treatment_type: 'Radioterapia',
          count: 380,
          percentage: 30.16,
          active_patients: 320,
          avg_treatment_days: 38,
          color: '#10b981'
        },
        {
          treatment_type: 'Imunoterapia',
          count: 280,
          percentage: 22.22,
          active_patients: 240,
          avg_treatment_days: 52,
          color: '#f59e0b'
        },
        {
          treatment_type: 'Cirurgia',
          count: 150,
          percentage: 11.90,
          active_patients: 90,
          avg_treatment_days: 15,
          color: '#ef4444'
        }
      ],
      trend_data: [
        { week: '2025-09-01', count: 1180 },
        { week: '2025-09-08', count: 1205 },
        { week: '2025-09-15', count: 1230 },
        { week: '2025-09-22', count: 1260 }
      ],
      last_updated: '2025-10-06T14:30:00Z'
    }

    vi.mocked(apiClient.request).mockResolvedValueOnce(mockData)

    const { result } = renderHook(() => useTreatmentDistribution(), {
      wrapper: createWrapper()
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data).toEqual(mockData)
    expect(apiClient.request).toHaveBeenCalledWith(
      '/api/v1/analytics/treatment-distribution?period=30d'
    )
  })

  it('should fetch treatment distribution for 7d period', async () => {
    const mockData: TreatmentDistributionResponse = {
      period: '7d',
      total_patients: 320,
      distribution: [
        {
          treatment_type: 'Quimioterapia',
          count: 120,
          percentage: 37.5,
          active_patients: 100,
          avg_treatment_days: 5,
          color: '#3b82f6'
        }
      ],
      trend_data: [
        { week: '2025-10-01', count: 320 }
      ],
      last_updated: '2025-10-06T14:30:00Z'
    }

    vi.mocked(apiClient.request).mockResolvedValueOnce(mockData)

    const { result } = renderHook(() => useTreatmentDistribution('7d'), {
      wrapper: createWrapper()
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data).toEqual(mockData)
    expect(apiClient.request).toHaveBeenCalledWith(
      '/api/v1/analytics/treatment-distribution?period=7d'
    )
  })

  it('should fetch treatment distribution for 90d period', async () => {
    const mockData: TreatmentDistributionResponse = {
      period: '90d',
      total_patients: 3800,
      distribution: [
        {
          treatment_type: 'Quimioterapia',
          count: 1400,
          percentage: 36.84,
          active_patients: 1200,
          avg_treatment_days: 75,
          color: '#3b82f6'
        }
      ],
      trend_data: [],
      last_updated: '2025-10-06T14:30:00Z'
    }

    vi.mocked(apiClient.request).mockResolvedValueOnce(mockData)

    const { result } = renderHook(() => useTreatmentDistribution('90d'), {
      wrapper: createWrapper()
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(apiClient.request).toHaveBeenCalledWith(
      '/api/v1/analytics/treatment-distribution?period=90d'
    )
  })

  it('should fetch treatment distribution for all period', async () => {
    const mockData: TreatmentDistributionResponse = {
      period: 'all',
      total_patients: 15000,
      distribution: [
        {
          treatment_type: 'Quimioterapia',
          count: 5500,
          percentage: 36.67,
          active_patients: 450,
          avg_treatment_days: 120,
          color: '#3b82f6'
        }
      ],
      trend_data: [],
      last_updated: '2025-10-06T14:30:00Z'
    }

    vi.mocked(apiClient.request).mockResolvedValueOnce(mockData)

    const { result } = renderHook(() => useTreatmentDistribution('all'), {
      wrapper: createWrapper()
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(apiClient.request).toHaveBeenCalledWith(
      '/api/v1/analytics/treatment-distribution?period=all'
    )
  })

  it('should cache results with queryKey including period', async () => {
    const mockData: TreatmentDistributionResponse = {
      period: '30d',
      total_patients: 1260,
      distribution: [],
      trend_data: [],
      last_updated: '2025-10-06T14:30:00Z'
    }

    vi.mocked(apiClient.request).mockResolvedValue(mockData)

    const wrapper = createWrapper()

    // First render with 30d period
    renderHook(() => useTreatmentDistribution('30d'), { wrapper })

    await waitFor(() => expect(apiClient.request).toHaveBeenCalledTimes(1))

    // Render again with same period - should use cache
    renderHook(() => useTreatmentDistribution('30d'), { wrapper })

    // Still 1, used cache
    expect(apiClient.request).toHaveBeenCalledTimes(1)
  })

  it('should make separate requests for different periods', async () => {
    const mockData7d: TreatmentDistributionResponse = {
      period: '7d',
      total_patients: 320,
      distribution: [],
      trend_data: [],
      last_updated: '2025-10-06T14:30:00Z'
    }

    const mockData30d: TreatmentDistributionResponse = {
      period: '30d',
      total_patients: 1260,
      distribution: [],
      trend_data: [],
      last_updated: '2025-10-06T14:30:00Z'
    }

    vi.mocked(apiClient.request)
      .mockResolvedValueOnce(mockData7d)
      .mockResolvedValueOnce(mockData30d)

    const wrapper = createWrapper()

    // Render with 7d period
    const { result: result1 } = renderHook(() => useTreatmentDistribution('7d'), { wrapper })
    await waitFor(() => expect(result1.current.isSuccess).toBe(true))

    // Render with 30d period - should be new request (different cache key)
    const { result: result2 } = renderHook(() => useTreatmentDistribution('30d'), { wrapper })
    await waitFor(() => expect(result2.current.isSuccess).toBe(true))

    // Should have made 2 separate requests
    expect(apiClient.request).toHaveBeenCalledTimes(2)
    expect(apiClient.request).toHaveBeenNthCalledWith(
      1,
      '/api/v1/analytics/treatment-distribution?period=7d'
    )
    expect(apiClient.request).toHaveBeenNthCalledWith(
      2,
      '/api/v1/analytics/treatment-distribution?period=30d'
    )
  })

  it('should respect enabled option', () => {
    const { result } = renderHook(
      () => useTreatmentDistribution('30d', { enabled: false }),
      { wrapper: createWrapper() }
    )

    expect(result.current.fetchStatus).toBe('idle')
    expect(apiClient.request).not.toHaveBeenCalled()
  })

  it('should handle API errors gracefully', async () => {
    const mockError = new Error('API Error: 500')
    vi.mocked(apiClient.request).mockRejectedValueOnce(mockError)

    const { result } = renderHook(() => useTreatmentDistribution(), {
      wrapper: createWrapper()
    })

    await waitFor(() => expect(result.current.isError).toBe(true))

    expect(result.current.error).toEqual(mockError)
    expect(result.current.data).toBeUndefined()
  })

  it('should retry failed requests up to 2 times', async () => {
    const mockError = new Error('Network error')
    vi.mocked(apiClient.request)
      .mockRejectedValueOnce(mockError)
      .mockRejectedValueOnce(mockError)
      .mockRejectedValueOnce(mockError)

    const { result } = renderHook(() => useTreatmentDistribution(), {
      wrapper: createWrapper()
    })

    await waitFor(() => expect(result.current.isError).toBe(true), { timeout: 5000 })

    // Should retry 2 times (initial + 2 retries = 3 total calls)
    expect(apiClient.request).toHaveBeenCalledTimes(3)
  })

  it('should have 5 minute stale time', async () => {
    const mockData: TreatmentDistributionResponse = {
      period: '30d',
      total_patients: 1260,
      distribution: [],
      trend_data: [],
      last_updated: '2025-10-06T14:30:00Z'
    }

    vi.mocked(apiClient.request).mockResolvedValueOnce(mockData)

    const { result } = renderHook(() => useTreatmentDistribution(), {
      wrapper: createWrapper()
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    // Query should not be stale initially
    expect(result.current.isStale).toBe(false)
  })

  it('should handle empty distribution data', async () => {
    const mockData: TreatmentDistributionResponse = {
      period: '30d',
      total_patients: 0,
      distribution: [],
      trend_data: [],
      last_updated: '2025-10-06T14:30:00Z'
    }

    vi.mocked(apiClient.request).mockResolvedValueOnce(mockData)

    const { result } = renderHook(() => useTreatmentDistribution(), {
      wrapper: createWrapper()
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.distribution).toEqual([])
    expect(result.current.data?.total_patients).toBe(0)
  })

  it('should return data with correct structure', async () => {
    const mockData: TreatmentDistributionResponse = {
      period: '30d',
      total_patients: 100,
      distribution: [
        {
          treatment_type: 'Test Treatment',
          count: 50,
          percentage: 50,
          active_patients: 45,
          avg_treatment_days: 30,
          color: '#000000'
        }
      ],
      trend_data: [
        { week: '2025-10-01', count: 100 }
      ],
      last_updated: '2025-10-06T14:30:00Z'
    }

    vi.mocked(apiClient.request).mockResolvedValueOnce(mockData)

    const { result } = renderHook(() => useTreatmentDistribution(), {
      wrapper: createWrapper()
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    // Verify structure
    expect(result.current.data).toHaveProperty('period')
    expect(result.current.data).toHaveProperty('total_patients')
    expect(result.current.data).toHaveProperty('distribution')
    expect(result.current.data).toHaveProperty('trend_data')
    expect(result.current.data).toHaveProperty('last_updated')

    // Verify distribution item structure
    const firstItem = result.current.data?.distribution[0]
    expect(firstItem).toHaveProperty('treatment_type')
    expect(firstItem).toHaveProperty('count')
    expect(firstItem).toHaveProperty('percentage')
    expect(firstItem).toHaveProperty('active_patients')
    expect(firstItem).toHaveProperty('avg_treatment_days')
    expect(firstItem).toHaveProperty('color')
  })
})
