import { renderHook, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { usePatients } from '../usePatients'
import { apiClient } from '../../lib/api-client'
import React from 'react'

vi.mock('../../lib/api-client')

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children)
}

describe('usePatients', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should fetch patients list successfully', async () => {
    const mockPatients = {
      items: [
        {
          id: '1',
          name: 'John Doe',
          email: 'john@example.com',
          status: 'active',
          created_at: '2024-01-01',
          updated_at: '2024-01-01',
        },
      ],
      total: 1,
      page: 1,
      size: 20,
      pages: 1,
    }

    vi.mocked(apiClient.patients.list).mockResolvedValue(mockPatients)

    const { result } = renderHook(() => usePatients(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data).toEqual(mockPatients)
    expect(apiClient.patients.list).toHaveBeenCalledWith({
      page: 1,
      size: 20,
      search: '',
      status: undefined,
      treatment_type: undefined,
    })
  })

  it('should handle search filter', async () => {
    const mockPatients = {
      items: [],
      total: 0,
      page: 1,
      size: 20,
      pages: 0,
    }

    vi.mocked(apiClient.patients.list).mockResolvedValue(mockPatients)

    const { result } = renderHook(
      () => usePatients({ search: 'john' }),
      {
        wrapper: createWrapper(),
      }
    )

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(apiClient.patients.list).toHaveBeenCalledWith({
      page: 1,
      size: 20,
      search: 'john',
      status: undefined,
      treatment_type: undefined,
    })
  })

  it('should handle pagination', async () => {
    const mockPatients = {
      items: [],
      total: 100,
      page: 2,
      size: 20,
      pages: 5,
    }

    vi.mocked(apiClient.patients.list).mockResolvedValue(mockPatients)

    const { result } = renderHook(
      () => usePatients({ page: 2, size: 20 }),
      {
        wrapper: createWrapper(),
      }
    )

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(apiClient.patients.list).toHaveBeenCalledWith({
      page: 2,
      size: 20,
      search: '',
      status: undefined,
      treatment_type: undefined,
    })
  })

  it('should handle error state', async () => {
    const mockError = new Error('Failed to fetch patients')
    vi.mocked(apiClient.patients.list).mockRejectedValue(mockError)

    const { result } = renderHook(() => usePatients(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    expect(result.current.error).toBeDefined()
  })
})
