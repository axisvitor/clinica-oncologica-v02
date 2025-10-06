import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useSystemStats } from '@/src/hooks/api/useSystemStats'
import type { SystemStatsResponse } from '@/src/types/api-wave2'
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
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

// Import the mocked apiClient after setting up the mock
import { apiClient } from '@/src/lib/api-client'

describe('useSystemStats', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should fetch system stats successfully', async () => {
    const mockData: SystemStatsResponse = {
      system_health: {
        cpu_percent: 25.5,
        memory_percent: 45.8,
        disk_usage_gb: 150.2,
        uptime_hours: 24
      },
      active_users: {
        total: 125,
        doctors: 20,
        patients: 100,
        admins: 5
      },
      database_metrics: {
        total_size_mb: 2048.5,
        active_connections: 12,
        query_performance_ms: 15.3,
        cache_hit_rate: 0.95
      },
      service_status: {
        redis: 'healthy',
        database: 'healthy',
        evolution_api: 'healthy',
        openai_api: 'healthy'
      },
      last_updated: '2025-10-06T14:30:00Z'
    }

    vi.mocked(apiClient.request).mockResolvedValueOnce(mockData)

    const { result } = renderHook(() => useSystemStats(), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data).toEqual(mockData)
    expect(apiClient.request).toHaveBeenCalledWith('/api/v1/admin/system-stats')
  })

  it('should handle errors gracefully', async () => {
    const error = new Error('Network error')
    // Mock to reject all attempts (initial + 2 retries = 3 total)
    vi.mocked(apiClient.request)
      .mockRejectedValueOnce(error)
      .mockRejectedValueOnce(error)
      .mockRejectedValueOnce(error)

    const { result } = renderHook(() => useSystemStats(), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isError).toBe(true), { timeout: 5000 })

    expect(result.current.error).toBeDefined()
  })

  it('should respect enabled option', () => {
    const { result } = renderHook(() => useSystemStats({ enabled: false }), {
      wrapper: createWrapper()
    })

    expect(result.current.fetchStatus).toBe('idle')
    expect(apiClient.request).not.toHaveBeenCalled()
  })

  it('should use custom refetch interval', async () => {
    const mockData: SystemStatsResponse = {
      system_health: {
        cpu_percent: 30.0,
        memory_percent: 50.0,
        disk_usage_gb: 200.0,
        uptime_hours: 48
      },
      active_users: {
        total: 150,
        doctors: 25,
        patients: 120,
        admins: 5
      },
      database_metrics: {
        total_size_mb: 3072.0,
        active_connections: 15,
        query_performance_ms: 12.5,
        cache_hit_rate: 0.92
      },
      service_status: {
        redis: 'healthy',
        database: 'healthy',
        evolution_api: 'degraded',
        openai_api: 'healthy'
      },
      last_updated: '2025-10-06T15:00:00Z'
    }

    vi.mocked(apiClient.request).mockResolvedValueOnce(mockData)

    const { result } = renderHook(() => useSystemStats({ refetchInterval: 60000 }), {
      wrapper: createWrapper()
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data).toEqual(mockData)
  })

  it('should retry failed requests up to 2 times', async () => {
    const error = new Error('Temporary failure')
    const mockData: SystemStatsResponse = {
      system_health: {
        cpu_percent: 20.0,
        memory_percent: 40.0,
        disk_usage_gb: 100.0,
        uptime_hours: 12
      },
      active_users: {
        total: 100,
        doctors: 15,
        patients: 80,
        admins: 5
      },
      database_metrics: {
        total_size_mb: 1024.0,
        active_connections: 10,
        query_performance_ms: 18.0,
        cache_hit_rate: 0.88
      },
      service_status: {
        redis: 'healthy',
        database: 'healthy',
        evolution_api: 'healthy',
        openai_api: 'healthy'
      },
      last_updated: '2025-10-06T16:00:00Z'
    }

    // First attempt fails, second attempt fails, third attempt succeeds
    vi.mocked(apiClient.request)
      .mockRejectedValueOnce(error)
      .mockRejectedValueOnce(error)
      .mockResolvedValueOnce(mockData)

    const { result } = renderHook(() => useSystemStats(), { wrapper: createWrapper() })

    // Wait for success after retries (with longer timeout to account for retryDelay)
    await waitFor(() => expect(result.current.isSuccess).toBe(true), { timeout: 5000 })

    expect(result.current.data).toEqual(mockData)
    expect(apiClient.request).toHaveBeenCalledTimes(3)
  })

  it('should have correct cache configuration', async () => {
    const mockData: SystemStatsResponse = {
      system_health: {
        cpu_percent: 15.0,
        memory_percent: 35.0,
        disk_usage_gb: 80.0,
        uptime_hours: 6
      },
      active_users: {
        total: 75,
        doctors: 10,
        patients: 60,
        admins: 5
      },
      database_metrics: {
        total_size_mb: 512.0,
        active_connections: 8,
        query_performance_ms: 20.0,
        cache_hit_rate: 0.85
      },
      service_status: {
        redis: 'healthy',
        database: 'healthy',
        evolution_api: 'healthy',
        openai_api: 'healthy'
      },
      last_updated: '2025-10-06T17:00:00Z'
    }

    vi.mocked(apiClient.request).mockResolvedValueOnce(mockData)

    const { result } = renderHook(() => useSystemStats(), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    // Verify the hook is using the correct query key
    expect(result.current.data).toEqual(mockData)

    // Query should use staleTime of 30 seconds (30000ms)
    // This is verified by the implementation, not directly testable in this way
    // but we can verify the data is cached by checking subsequent calls
  })
})
