/**
 * User Filters Hook - Filter State Management
 *
 * Manages user list filters and pagination state
 * - Search, role, status, and 2FA filters
 * - Pagination state management
 * - Filter reset functionality
 *
 * @module hooks/admin/useUserFilters
 */

import { useState, useCallback, useMemo, useRef, useEffect } from 'react'

export interface UserFilters {
  search?: string
  role?: string
  status?: string
  twoFactor?: string
  page?: number
  size?: number
}

export interface UseUserFiltersOptions {
  /** Initial filters */
  initialFilters?: Partial<UserFilters>
  /** Page size */
  pageSize?: number
}

/**
 * Hook for managing user list filters
 *
 * @param options - Configuration options
 * @returns Filter state and update functions
 *
 * @example
 * ```tsx
 * const { filters, updateFilters, resetFilters, hasActiveFilters } = useUserFilters({
 *   pageSize: 20
 * })
 *
 * // Update search filter
 * updateFilters({ search: 'john@example.com' })
 *
 * // Reset all filters
 * resetFilters()
 * ```
 */
export function useUserFilters(options: UseUserFiltersOptions = {}) {
  const { initialFilters = {}, pageSize = 10 } = options

  // Initialize filters with defaults - memoized to prevent recreating on each render
  const defaultFilters: UserFilters = useMemo(
    () => ({
      page: 1,
      size: pageSize,
      ...initialFilters,
    }),
    [pageSize, initialFilters]
  )

  const [filters, setFilters] = useState<UserFilters>(defaultFilters)

  /**
   * Update filters and reset to page 1
   * Resets pagination when filters change to show first page of results
   */
  const updateFilters = useCallback((newFilters: Partial<UserFilters>) => {
    setFilters((prev) => ({
      ...prev,
      ...newFilters,
      // Reset to first page when filters change (unless page is explicitly set)
      page: newFilters.page ?? 1,
    }))
  }, [])

  /**
   * Update a single filter value
   */
  const updateFilter = useCallback(
    (key: keyof UserFilters, value: string | number | undefined) => {
      updateFilters({ [key]: value })
    },
    [updateFilters]
  )

  /**
   * Update page number
   */
  const setPage = useCallback((page: number) => {
    setFilters((prev) => ({ ...prev, page }))
  }, [])

  /**
   * Update page size and reset to page 1
   */
  const setPageSize = useCallback((size: number) => {
    setFilters((prev) => ({ ...prev, size, page: 1 }))
  }, [])

  // Use ref to store defaultFilters for resetFilters callback
  const defaultFiltersRef = useRef(defaultFilters)
  useEffect(() => {
    defaultFiltersRef.current = defaultFilters
  }, [defaultFilters])

  /**
   * Reset filters to default state
   */
  const resetFilters = useCallback(() => {
    setFilters(defaultFiltersRef.current)
  }, [])

  /**
   * Check if any filters are active (excluding pagination)
   */
  const hasActiveFilters = useMemo(() => {
    return !!(
      filters.search ||
      (filters.role && filters.role !== 'all') ||
      (filters.status && filters.status !== 'all') ||
      (filters.twoFactor && filters.twoFactor !== 'all')
    )
  }, [filters])

  /**
   * Get filter count (excluding pagination)
   */
  const activeFilterCount = useMemo(() => {
    let count = 0
    if (filters.search) count++
    if (filters.role && filters.role !== 'all') count++
    if (filters.status && filters.status !== 'all') count++
    if (filters.twoFactor && filters.twoFactor !== 'all') count++
    return count
  }, [filters])

  /**
   * Get URL query params from filters
   * Useful for syncing with URL
   */
  const toQueryParams = useCallback((): Record<string, string> => {
    const params: Record<string, string> = {}

    if (filters.search) params['search'] = filters.search
    if (filters.role && filters.role !== 'all') params['role'] = filters.role
    if (filters.status && filters.status !== 'all') params['status'] = filters.status
    if (filters.twoFactor && filters.twoFactor !== 'all') params['twoFactor'] = filters.twoFactor
    if (filters.page) params['page'] = String(filters.page)
    if (filters.size) params['size'] = String(filters.size)

    return params
  }, [filters])

  /**
   * Set filters from URL query params
   */
  const fromQueryParams = useCallback((params: Record<string, string>) => {
    const newFilters: Partial<UserFilters> = {}

    if (params['search']) newFilters.search = params['search']
    if (params['role']) newFilters.role = params['role']
    if (params['status']) newFilters.status = params['status']
    if (params['twoFactor']) newFilters.twoFactor = params['twoFactor']
    if (params['page']) newFilters.page = parseInt(params['page'], 10)
    if (params['size']) newFilters.size = parseInt(params['size'], 10)

    setFilters((prev) => ({ ...prev, ...newFilters }))
  }, [])

  return {
    /** Current filter state */
    filters,
    /** Update multiple filters at once */
    updateFilters,
    /** Update a single filter */
    updateFilter,
    /** Set current page */
    setPage,
    /** Set page size */
    setPageSize,
    /** Reset all filters to defaults */
    resetFilters,
    /** Whether any filters are active */
    hasActiveFilters,
    /** Count of active filters */
    activeFilterCount,
    /** Convert filters to URL query params */
    toQueryParams,
    /** Set filters from URL query params */
    fromQueryParams,
  }
}
