import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useUserStats } from '../useUserStats'
import { apiClient } from '@/lib/api-client'

vi.mock('@/lib/api-client', () => ({
  apiClient: {
    admin: {
      system: {
        systemStats: vi.fn(),
        getHealth: vi.fn(),
      },
    },
  },
}))

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

const usersData = {
  total: 3,
  items: [
    {
      id: 'u1',
      full_name: 'Admin User',
      email: 'admin@example.com',
      is_active: true,
      failed_login_attempts: 2,
    },
    {
      id: 'u2',
      full_name: 'Doctor User',
      email: 'doctor@example.com',
      is_active: true,
      failed_login_attempts: 1,
    },
    {
      id: 'u3',
      full_name: 'Locked User',
      email: 'locked@example.com',
      is_active: false,
      failed_login_attempts: 3,
      locked_until: '2099-01-01T00:00:00Z',
    },
  ],
}

describe('useUserStats', () => {
  const mockSystemStats = vi.mocked(apiClient.admin.system.systemStats)
  const mockSystemHealth = vi.mocked(apiClient.admin.system.getHealth)

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches system stats and computes metrics', async () => {
    mockSystemStats.mockResolvedValue({
      users: {
        total: 10,
        active_now: 8,
      },
    } as any)
    mockSystemHealth.mockResolvedValue({ status: 'healthy' } as any)

    const { result } = renderHook(() => useUserStats({ usersData }), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(result.current.stats?.users.total).toBe(10)
    })

    expect(result.current.stats?.users.active).toBe(8)
    expect(result.current.metrics?.activePercentage).toBe(80)
    expect(mockSystemStats).toHaveBeenCalledTimes(1)
    expect(mockSystemHealth).toHaveBeenCalledTimes(1)
  })

  it('falls back to derived stats when API calls fail', async () => {
    mockSystemStats.mockRejectedValue(new Error('down'))
    mockSystemHealth.mockRejectedValue(new Error('down'))

    const { result } = renderHook(() => useUserStats({ usersData }), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(result.current.stats?.users.total).toBe(3)
    })

    expect(result.current.stats?.users.active).toBe(2)
    expect(result.current.stats?.security.failed_logins).toBe(6)
    expect(result.current.stats?.users.locked).toBe(1)
  })

  it('does not run query when usersData is not provided', async () => {
    const { result } = renderHook(() => useUserStats(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(mockSystemStats).not.toHaveBeenCalled()
    expect(mockSystemHealth).not.toHaveBeenCalled()
    expect(result.current.stats).toBeUndefined()
  })
})
