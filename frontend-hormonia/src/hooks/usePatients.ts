import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, useCallback, useMemo, useEffect } from 'react'

import { useDebounce } from './useDebounce'
import { apiClient } from '../lib/api-client'
import type { Patient } from '../lib/types/api'

export interface PatientFilters {
  search?: string
  status?: 'active' | 'paused' | 'completed' | 'inactive'
  treatment_type?: string
  start_date_from?: string
  start_date_to?: string
  page?: number
  size?: number
}

export interface UsePatientFiltersOptions {
  initialFilters?: Partial<PatientFilters>
  debounceMs?: number
  pageSize?: number
}

export function usePatientFilters(options: UsePatientFiltersOptions = {}) {
  const {
    initialFilters = {},
    debounceMs = 300,
    pageSize = 20
  } = options

  const [filters, setFilters] = useState<PatientFilters>(() => ({
    search: '',
    treatment_type: '',
    start_date_from: '',
    start_date_to: '',
    page: 1,
    size: pageSize,
    ...initialFilters
  }))

  // Debounce search to avoid excessive API calls
  const debouncedSearch = useDebounce(filters['search'] || '', debounceMs)

  // Create query parameters for API call
  const queryParams = useMemo(() => {
    const params: Record<string, any> = {
      page: filters['page'] || 1,
      size: filters.size || pageSize
    }

    if (debouncedSearch) {
      params['search'] = debouncedSearch
    }

    if (filters['status']) {
      params['status'] = filters['status']
    }

    if (filters['treatment_type'] && filters['treatment_type'] !== '') {
      params['treatment_type'] = filters['treatment_type']
    }

    // Date range filters would need backend support
    if (filters['start_date_from']) {
      params['start_date_from'] = filters['start_date_from']
    }

    if (filters['start_date_to']) {
      params['start_date_to'] = filters['start_date_to']
    }

    return params
  }, [debouncedSearch, filters['status'], filters['treatment_type'], filters['start_date_from'], filters['start_date_to'], filters['page'], filters.size, pageSize])

  // Update specific filter
  const updateFilter = useCallback(<K extends keyof PatientFilters>(
    key: K,
    value: PatientFilters[K]
  ) => {
    setFilters(prev => ({
      ...prev,
      [key]: value,
      // Reset to page 1 when filter changes (except for page)
      ...(key !== 'page' ? { page: 1 } : {})
    }))
  }, [])

  // Update multiple filters at once
  const updateFilters = useCallback((newFilters: Partial<PatientFilters>) => {
    setFilters(prev => ({
      ...prev,
      ...newFilters,
      // Reset to page 1 when filters change
      page: 1
    }))
  }, [])

  // Reset all filters
  const resetFilters = useCallback(() => {
    setFilters({
      search: '',
      treatment_type: '',
      start_date_from: '',
      start_date_to: '',
      page: 1,
      size: pageSize
    })
  }, [pageSize])

  // Check if any filters are active
  const hasActiveFilters = useMemo(() => {
    return Boolean(
      filters['search'] ||
      filters['status'] ||
      filters['treatment_type'] ||
      filters['start_date_from'] ||
      filters['start_date_to']
    )
  }, [filters])

  // Get active filter count
  const activeFilterCount = useMemo(() => {
    let count = 0
    if (filters['search']) count++
    if (filters['status']) count++
    if (filters['treatment_type']) count++
    if (filters['start_date_from'] || filters['start_date_to']) count++
    return count
  }, [filters])

  return {
    filters,
    queryParams,
    updateFilter,
    updateFilters,
    resetFilters,
    hasActiveFilters,
    activeFilterCount
  }
}

export function usePatients(filterOptions?: UsePatientFiltersOptions) {
  const queryClient = useQueryClient()
  // Maintain cursor map per page and persistent total across pages
  const [cursorsByPage, setCursorsByPage] = useState<Record<number, string | undefined>>({ 1: undefined })
  const [persistedTotal, setPersistedTotal] = useState<number>(0)
  const {
    filters,
    queryParams,
    updateFilter,
    updateFilters,
    resetFilters,
    hasActiveFilters,
    activeFilterCount
  } = usePatientFilters(filterOptions)

  // Reset cursors when non-page filters change
  const filtersKey = useMemo(() => {
    const { page: _p, size: _s, ...rest } = filters || ({} as any)
    return JSON.stringify(rest)
  }, [filters])

  useEffect(() => {
    // When filters (except page/size) change, reset to page 1 and clear cursors
    setCursorsByPage({ 1: undefined })
    setPersistedTotal(0)
  }, [filtersKey])

  // Compute effective API params using cursor-based pagination
  const effectiveParams = useMemo(() => {
    const limit = queryParams['size'] || filterOptions?.pageSize || 20
    const cursor = cursorsByPage[filters.page || 1]
    const { page: _page, size: _size, ...rest } = queryParams as any
    return { limit, ...(cursor ? { cursor } : {}), ...rest }
  }, [queryParams, filters.page, cursorsByPage, filterOptions?.pageSize])

  // Fetch patients with current filters
  const {
    data,
    isLoading,
    error,
    refetch,
    isFetching
  } = useQuery({
    queryKey: ['patients', effectiveParams, filters.page],
    queryFn: async () => {
      const response: any = await apiClient.patients.list({ ...effectiveParams })
      // Prefer has_more from API; fallback to pages computation only if absent
      const has_more = (typeof response?.has_more === 'boolean')
        ? response.has_more
        : (typeof response?.pages === 'number' && (response?.page ?? 1) < response.pages)

      const normalized = {
        data: (response?.data ?? response?.items) || [],
        total: response?.total ?? 0,
        page: filters.page || 1,
        size: effectiveParams['limit'] || 20,
        has_more,
        next_cursor: response?.next_cursor
      } as any

      return normalized as any
    },
    staleTime: 30000, // 30 seconds
    retry: 2,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000)
  })

  // Handle success effects since we removed onSuccess for typing compatibility
  useEffect(() => {
    const resp: any = data as any
    if (!resp) return
    if (typeof resp?.total === 'number' && resp.total > 0) {
      setPersistedTotal(resp.total)
    }
    const currentPage = filters.page || 1
    if (resp?.next_cursor) {
      setCursorsByPage(prev => ({ ...prev, [currentPage + 1]: resp.next_cursor }))
    }
  }, [data, filters.page])

  // Invalidate patients query to force refresh
  const invalidatePatients = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['patients'] })
  }, [queryClient])

  // Pre-fetch next page
  const prefetchNextPage = useCallback(() => {
    if ((data as any)?.has_more) {
      const nextPage = (filters.page || 1) + 1
      const nextCursor = (data as any)?.next_cursor || cursorsByPage[nextPage]
      const limit = queryParams['size'] || filterOptions?.pageSize || 20
      const nextParams = { ...effectiveParams, cursor: nextCursor, limit }

      queryClient.prefetchQuery({
        queryKey: ['patients', nextParams, nextPage],
        queryFn: async () => {
          const response: any = await apiClient.patients.list(nextParams as any)
          const has_more = (typeof response?.has_more === 'boolean')
            ? response.has_more
            : (typeof response?.pages === 'number' && (response?.page ?? 1) < response.pages)

          return {
            data: (response?.data ?? response?.items) || [],
            total: response?.total ?? 0,
            page: nextPage,
            size: limit,
            has_more,
            next_cursor: response?.next_cursor
          } as any
        },
        staleTime: 30000
      })
    }
  }, [data, filters.page, queryParams, filterOptions?.pageSize, effectiveParams, cursorsByPage, queryClient])

  return {
    // Data
    patients: (data as any)?.data || [],
    total: (persistedTotal || (data as any)?.total || 0),
    page: filters.page || 1,
    limit: (data as any)?.size || (queryParams['size'] || 20),
    hasMore: (data as any)?.has_more || false,

    // Loading states
    isLoading,
    isFetching,

    error,

    // Filters
    filters,
    hasActiveFilters,
    activeFilterCount,

    
    // Actions
    updateFilter,
    updateFilters,
    resetFilters,
    refetch,
    invalidatePatients,
    prefetchNextPage
  }
}

// Hook for treatment types (could be moved to a separate file)
export function useTreatmentTypes() {
  return useQuery({
    queryKey: ['treatment-types'],
    queryFn: async () => {
      // In a real implementation, this might come from a dedicated endpoint
      // For now, return common treatment types
      return [
        'Terapia Hormonal Feminina',
        'Terapia Hormonal Masculina',
        'Reposição Hormonal',
        'Tratamento Personalizado',
        'Acompanhamento Nutricional',
        'Suplementação Hormonal'
      ]
    },
    staleTime: Infinity, // These don't change often
    gcTime: Infinity
  })
}