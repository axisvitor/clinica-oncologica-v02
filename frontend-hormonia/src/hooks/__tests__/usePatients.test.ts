import { readFileSync } from 'node:fs'
import path from 'node:path'

import { renderHook, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { usePatients } from '../usePatients'
import { apiClient } from '../../lib/api-client'
import React from 'react'

vi.mock('../../lib/api-client')

const readRepoFile = (relativePath: string) =>
  readFileSync(path.resolve(process.cwd(), relativePath), 'utf8')

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

  it('keeps the hook on the canonical @/types/api patient surface', () => {
    const source = readRepoFile('src/hooks/usePatients.ts')

    expect(source).toContain("import type { Patient } from '@/types/api'")
<<<<<<< HEAD
    expect(source).not.toMatch(/from ['"]\.\.\/lib\/types\/api['"]/)
=======
    expect(source).not.toMatch(/from ['"]\.\.\/lib\/types\/api['"]/) 
>>>>>>> gsd/M003/S03
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

    expect(result.current.patients).toHaveLength(1)
    expect(result.current.patients[0].name).toBe('John Doe')
    expect(result.current.total).toBe(1)
    expect(result.current.data?.items).toHaveLength(1)
    expect(apiClient.patients.list).toHaveBeenCalledWith({
      limit: 20,
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
      () =>
        usePatients({
          initialFilters: { search: 'john' },
          debounceMs: 0,
        }),
      {
        wrapper: createWrapper(),
      }
    )

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(apiClient.patients.list).toHaveBeenCalledWith({
      limit: 20,
      search: 'john',
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
      () =>
        usePatients({
          initialFilters: { page: 2, size: 20 },
        }),
      {
        wrapper: createWrapper(),
      }
    )

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.page).toBe(2)
    expect(result.current.total).toBe(100)
    expect(result.current.hasMore).toBe(true)
    expect(apiClient.patients.list).toHaveBeenCalledWith({
      limit: 20,
    })
  })

  it('should handle error state', async () => {
    const mockError = new Error('Failed to fetch patients')
    vi.mocked(apiClient.patients.list).mockRejectedValue(mockError)

    const { result } = renderHook(() => usePatients(), {
      wrapper: createWrapper(),
    })

    await waitFor(
      () => {
        expect(result.current.isError).toBe(true)
      },
      { timeout: 5000 }
    )

    expect(result.current.error).toBe(mockError)
  })
})
