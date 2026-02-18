import React from 'react'
import { renderHook, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { useSystemStats } from '@/hooks/useSystemStats'

const { mockGetDashboardMetrics } = vi.hoisted(() => ({
  mockGetDashboardMetrics: vi.fn(),
}))

vi.mock('@/lib/api-client', () => ({
  apiClient: {
    analytics: {
      getDashboardMetrics: mockGetDashboardMetrics,
    },
  },
}))

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retryDelay: 1,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  })

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

describe('useSystemStats (canonical)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches dashboard metrics and maps them to admin stats shape', async () => {
    mockGetDashboardMetrics.mockResolvedValue({
      total_patients: 150,
      active_patients: 120,
      total_appointments: 320,
      completed_appointments: 280,
      pending_messages: 12,
      unread_messages: 7,
      quiz_completion_rate: 88,
      patient_engagement_rate: 74,
    })

    const { result } = renderHook(() => useSystemStats(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(mockGetDashboardMetrics).toHaveBeenCalledTimes(1)
    expect(result.current.error).toBeNull()
    expect(result.current.stats).toEqual({
      users: {
        total: 150,
        active: 120,
        locked: 0,
        new_today: 0,
      },
      security: {
        failed_logins: 0,
        active_sessions: 120,
        blocked_ips: 0,
      },
      system: {
        uptime: 0,
        memory_usage: 0,
        cpu_usage: 0,
        disk_usage: 0,
      },
      audit: {
        total_logs: 280,
        critical_events: 0,
        warnings: 0,
      },
    })
  })

  it('exposes query error when metrics request fails', async () => {
    mockGetDashboardMetrics.mockRejectedValue(new Error('Network failure'))

    const { result } = renderHook(() => useSystemStats(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(result.current.error).toBeTruthy()
    })

    expect(result.current.stats).toBeUndefined()
  })

  it('supports manual refetch', async () => {
    mockGetDashboardMetrics
      .mockResolvedValueOnce({
        total_patients: 10,
        active_patients: 8,
        total_appointments: 20,
        completed_appointments: 16,
        pending_messages: 0,
        unread_messages: 0,
        quiz_completion_rate: 80,
        patient_engagement_rate: 70,
      })
      .mockResolvedValueOnce({
        total_patients: 20,
        active_patients: 15,
        total_appointments: 30,
        completed_appointments: 24,
        pending_messages: 1,
        unread_messages: 1,
        quiz_completion_rate: 85,
        patient_engagement_rate: 75,
      })

    const { result } = renderHook(() => useSystemStats({ realTimeUpdates: false }), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    await act(async () => {
      await result.current.refetch()
    })

    await waitFor(() => {
      expect(mockGetDashboardMetrics).toHaveBeenCalledTimes(2)
      expect(result.current.stats?.users.total).toBe(20)
    })
  })
})
