import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useUserList } from '../useUserList'
import { apiClient } from '@/lib/api-client'

vi.mock('@/lib/api-client', () => ({
  apiClient: {
    adminUsers: {
      list: vi.fn(),
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

describe('useUserList', () => {
  const mockList = vi.mocked(apiClient.adminUsers.list)

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches users and maps response fields', async () => {
    mockList.mockResolvedValue({
      items: [
        {
          id: 'u1',
          full_name: 'Ana Silva',
          email: 'ana@example.com',
          role: 'admin',
          is_active: true,
        },
      ],
      total: 1,
      page: 1,
      size: 10,
      pages: 1,
      has_more: false,
    } as any)

    const { result } = renderHook(
      () =>
        useUserList({
          filters: {
            search: 'ana',
            status: 'active',
            twoFactor: 'enabled',
          },
        }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => {
      expect(result.current.users).toHaveLength(1)
    })

    expect(mockList).toHaveBeenCalledWith(
      expect.objectContaining({
        page: 1,
        size: 10,
        search: 'ana',
        is_active: true,
        two_factor_enabled: true,
      })
    )

    expect(result.current.total).toBe(1)
    expect(result.current.currentPage).toBe(1)
    expect(result.current.pageSize).toBe(10)
  })

  it('passes pagination and role filters to API', async () => {
    mockList.mockResolvedValue({
      items: [],
      total: 0,
      page: 2,
      size: 25,
      pages: 0,
      has_more: false,
    } as any)

    const { result } = renderHook(
      () =>
        useUserList({
          filters: {
            page: 2,
            size: 25,
            role: 'doctor',
          },
        }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(mockList).toHaveBeenCalledWith(
      expect.objectContaining({
        page: 2,
        size: 25,
        role: 'doctor',
      })
    )
  })

  it('surfaces API errors', async () => {
    mockList.mockRejectedValue(new Error('network error'))

    const { result } = renderHook(() => useUserList({ enableRetry: false }), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(result.current.error).toBeTruthy()
    })

    expect(result.current.users).toEqual([])
  })

  it('does not query when disabled', () => {
    renderHook(() => useUserList({ enabled: false }), {
      wrapper: createWrapper(),
    })

    expect(mockList).not.toHaveBeenCalled()
  })
})
