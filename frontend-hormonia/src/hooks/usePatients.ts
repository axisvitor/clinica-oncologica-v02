import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, useCallback, useMemo } from 'react'
import { useDebounce } from './useDebounce'
import { apiClient } from '../lib/api-client'
import type { Patient, PaginatedResponse } from '../lib/types/api'

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
  const {
    filters,
    queryParams,
    updateFilter,
    updateFilters,
    resetFilters,
    hasActiveFilters,
    activeFilterCount
  } = usePatientFilters(filterOptions)

  // Fetch patients with current filters
  const {
    data,
    isLoading,
    error,
    refetch,
    isFetching
  } = useQuery({
    queryKey: ['patients', queryParams],
    queryFn: async () => {
      const response = await apiClient.patients.list(queryParams)
      // Handle both possible response formats
      if ('items' in response) {
        return {
          data: response.items,
          total: response.total,
          page: response['page'],
          limit: response.size || 10,
          has_more: response['page'] < response.pages
        } as unknown as PaginatedResponse<Patient>
      }
      return response as unknown as PaginatedResponse<Patient>
    },
    staleTime: 30000, // 30 seconds
    retry: 2,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000)
  })

  // Invalidate patients query to force refresh
  const invalidatePatients = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['patients'] })
  }, [queryClient])

  // Pre-fetch next page
  const prefetchNextPage = useCallback(() => {
    if (data?.has_more) {
      const nextPageParams = {
        ...queryParams,
        page: (queryParams['page'] || 1) + 1
      }
      
      queryClient.prefetchQuery({
        queryKey: ['patients', nextPageParams],
        queryFn: async () => {
          const response = await apiClient.patients.list(nextPageParams)
          // Handle both possible response formats
          if ('items' in response) {
            return {
              data: response.items,
              total: response.total,
              page: response['page'],
              limit: response.size || 10,
              has_more: response['page'] < response.pages
            } as unknown as PaginatedResponse<Patient>
          }
          return response as unknown as PaginatedResponse<Patient>
        },
        staleTime: 30000
      })
    }
  }, [data?.has_more, queryParams, queryClient])

  return {
    // Data
    patients: data?.data || [],
    total: data?.total || 0,
    page: data?.['page'] || 1,
    limit: data?.size || 20,
    hasMore: data?.has_more || false,
    
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