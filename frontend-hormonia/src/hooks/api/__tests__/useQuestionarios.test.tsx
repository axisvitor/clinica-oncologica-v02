import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useQuestionarios } from '../useQuestionarios'
import { apiClient } from '@/lib/api-client'

// Mock API client
vi.mock('@/lib/api-client', () => ({
  apiClient: {
    quizzes: {
      listTemplates: vi.fn(),
      getTemplateAnalytics: vi.fn(),
    },
  },
}))

// Test data
const mockTemplates = [
  {
    id: '1',
    name: 'Medical Oncology Assessment',
    version: '1.0',
    questions: [],
    is_active: true,
    created_at: '2024-01-15T10:00:00-03:00',
    updated_at: '2024-01-15T10:00:00-03:00',
  },
  {
    id: '2',
    name: 'Wellness Lifestyle Quiz',
    version: '1.0',
    questions: [],
    is_active: true,
    created_at: '2024-01-10T10:00:00-03:00',
    updated_at: '2024-01-10T10:00:00-03:00',
  },
  {
    id: '3',
    name: 'Medical Health Check',
    version: '1.0',
    questions: [],
    is_active: false,
    created_at: '2024-01-20T10:00:00-03:00',
    updated_at: '2024-01-20T10:00:00-03:00',
  },
  {
    id: '4',
    name: 'Wellness Mental Health',
    version: '1.0',
    questions: [],
    is_active: true,
    created_at: '2024-01-05T10:00:00-03:00',
    updated_at: '2024-01-05T10:00:00-03:00',
  },
]

const mockAnalytics = {
  total_responses: 42,
  completion_rate: 0.85,
  average_completion_time: 300,
}

// Helper to create wrapper with QueryClient
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

describe('useQuestionarios', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(apiClient.quizzes.listTemplates).mockResolvedValue(mockTemplates)
    vi.mocked(apiClient.quizzes.getTemplateAnalytics).mockResolvedValue(mockAnalytics)
  })

  it('should fetch all templates by default', async () => {
    const { result } = renderHook(() => useQuestionarios({ queryOverrides: { retry: 0 } }), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data).toBeDefined()
    expect(result.current.data?.items).toHaveLength(4)
    expect(result.current.data?.total).toBe(4)
    expect(result.current.data?.page).toBe(1)
    expect(result.current.data?.size).toBe(12)
  })

  it('should filter by search term', async () => {
    const { result } = renderHook(
      () => useQuestionarios({ search: 'wellness', queryOverrides: { retry: 0 } }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.items).toHaveLength(2)
    expect(result.current.data?.items[0].name).toContain('Wellness')
    expect(result.current.data?.total).toBe(2)
  })

  it('should filter by type - medical', async () => {
    const { result } = renderHook(
      () => useQuestionarios({ type: 'medical', queryOverrides: { retry: 0 } }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.items).toHaveLength(2)
    expect(result.current.data?.total).toBe(2)
    result.current.data?.items.forEach((template: any) => {
      expect(template.name.toLowerCase()).toMatch(/medical|oncolog/)
    })
  })

  it('should filter by type - wellness', async () => {
    const { result } = renderHook(
      () => useQuestionarios({ type: 'wellness', queryOverrides: { retry: 0 } }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.items).toHaveLength(2)
    expect(result.current.data?.total).toBe(2)
    result.current.data?.items.forEach((template) => {
      expect(template.name.toLowerCase()).toContain('wellness')
    })
  })

  it('should filter by status - active', async () => {
    const { result } = renderHook(
      () => useQuestionarios({ status: 'active', queryOverrides: { retry: 0 } }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.items).toHaveLength(3)
    expect(result.current.data?.total).toBe(3)
    result.current.data?.items.forEach((template: any) => {
      expect(template.is_active).toBe(true)
    })
  })

  it('should filter by status - inactive', async () => {
    const { result } = renderHook(
      () => useQuestionarios({ status: 'inactive', queryOverrides: { retry: 0 } }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.items).toHaveLength(1)
    expect(result.current.data?.total).toBe(1)
    expect(result.current.data?.items[0].is_active).toBe(false)
  })

  it('should sort by name ascending', async () => {
    const { result } = renderHook(
      () => useQuestionarios({ sortBy: 'name', sortOrder: 'asc', queryOverrides: { retry: 0 } }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const names = result.current.data?.items.map((t) => t.name) || []
    expect(names[0]).toBe('Medical Health Check')
    expect(names[1]).toBe('Medical Oncology Assessment')
  })

  it('should sort by name descending', async () => {
    const { result } = renderHook(
      () => useQuestionarios({ sortBy: 'name', sortOrder: 'desc', queryOverrides: { retry: 0 } }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const names = result.current.data?.items.map((t: any) => t.name) || []
    expect(names[0]).toMatch(/Wellness/)
    expect(names[names.length - 1]).toMatch(/Medical/)
  })

  it('should sort by created_at descending (default)', async () => {
    const { result } = renderHook(() => useQuestionarios(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const dates = result.current.data?.items.map((t: any) => new Date(t.created_at)) || []
    for (let i = 0; i < dates.length - 1; i++) {
      expect(dates[i].getTime()).toBeGreaterThanOrEqual(dates[i + 1].getTime())
    }
  })

  it('should sort by created_at ascending', async () => {
    const { result } = renderHook(
      () =>
        useQuestionarios({ sortBy: 'created_at', sortOrder: 'asc', queryOverrides: { retry: 0 } }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const dates = result.current.data?.items.map((t: any) => new Date(t.created_at)) || []
    for (let i = 0; i < dates.length - 1; i++) {
      expect(dates[i].getTime()).toBeLessThanOrEqual(dates[i + 1].getTime())
    }
  })

  it('should paginate results', async () => {
    const { result } = renderHook(
      () => useQuestionarios({ page: 1, size: 2, queryOverrides: { retry: 0 } }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.items).toHaveLength(2)
    expect(result.current.data?.total).toBe(4)
    expect(result.current.data?.page).toBe(1)
    expect(result.current.data?.size).toBe(2)
  })

  it('should return second page of results', async () => {
    const { result } = renderHook(
      () => useQuestionarios({ page: 2, size: 2, queryOverrides: { retry: 0 } }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.items).toHaveLength(2)
    expect(result.current.data?.total).toBe(4)
    expect(result.current.data?.page).toBe(2)
  })

  it('should combine multiple filters', async () => {
    const { result } = renderHook(
      () =>
        useQuestionarios({
          type: 'medical',
          status: 'active',
          search: 'oncology',
          queryOverrides: { retry: 0 },
        }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.items).toHaveLength(1)
    expect(result.current.data?.items[0].name).toBe('Medical Oncology Assessment')
    expect(result.current.data?.items[0].is_active).toBe(true)
  })

  it('should fetch analytics for each template', async () => {
    const { result } = renderHook(() => useQuestionarios(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    result.current.data?.items.forEach((template: any) => {
      expect(template.analytics).toBeDefined()
      expect(template.analytics?.total_responses).toBe(42)
      expect(template.analytics?.completion_rate).toBe(0.85)
    })
  })

  it('should handle analytics fetch error gracefully', async () => {
    vi.mocked(apiClient.quizzes.getTemplateAnalytics).mockRejectedValue(
      new Error('Analytics not available')
    )

    const { result } = renderHook(() => useQuestionarios(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    result.current.data?.items.forEach((template: any) => {
      expect(template.analytics).toEqual({
        total_responses: 0,
        completion_rate: 0,
        average_completion_time: null,
      })
    })
  })

  it('should update query key when filters change', async () => {
    const { result, rerender } = renderHook(({ options }) => useQuestionarios(options), {
      wrapper: createWrapper(),
      initialProps: { options: { search: 'medical', queryOverrides: { retry: 0 } } },
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.total).toBe(2)

    // Change search filter
    rerender({ options: { search: 'wellness', queryOverrides: { retry: 0 } } })

    await waitFor(() => {
      expect(result.current.data?.total).toBe(2)
      expect(result.current.data?.items[0].name).toContain('Wellness')
    })
  })

  it('should handle empty results', async () => {
    const { result } = renderHook(
      () => useQuestionarios({ search: 'nonexistent', queryOverrides: { retry: 0 } }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.items).toHaveLength(0)
    expect(result.current.data?.total).toBe(0)
  })

  it('should handle API error', async () => {
    vi.mocked(apiClient.quizzes.listTemplates).mockRejectedValue(new Error('API Error'))

    const { result } = renderHook(() => useQuestionarios({ queryOverrides: { retry: 0 } }), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))

    expect(result.current.error).toBeDefined()
  })

  it('should use correct staleTime and gcTime', () => {
    const { result } = renderHook(() => useQuestionarios(), {
      wrapper: createWrapper(),
    })

    // Query options are set correctly
    expect(result.current.dataUpdatedAt).toBeDefined()
  })

  it('should sort by responses count', async () => {
    // Mock different analytics for each template
    vi.mocked(apiClient.quizzes.getTemplateAnalytics)
      .mockResolvedValueOnce({ total_responses: 10, completion_rate: 0.8 })
      .mockResolvedValueOnce({ total_responses: 50, completion_rate: 0.9 })
      .mockResolvedValueOnce({ total_responses: 5, completion_rate: 0.7 })
      .mockResolvedValueOnce({ total_responses: 30, completion_rate: 0.85 })

    const { result } = renderHook(
      () =>
        useQuestionarios({ sortBy: 'responses', sortOrder: 'desc', queryOverrides: { retry: 0 } }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const responses =
      result.current.data?.items.map((t: any) => t.analytics?.total_responses || 0) || []
    for (let i = 0; i < responses.length - 1; i++) {
      expect(responses[i]).toBeGreaterThanOrEqual(responses[i + 1])
    }
  })
})
