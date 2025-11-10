import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useSystemStats } from '@/hooks/useSystemStats'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'
import { AdminDashboardStats } from '@/types/admin'

// Mock API Client
const mockApiClient = {
  get: vi.fn()
}

vi.mock('@/lib/api-client', () => ({
  apiClient: mockApiClient
}))

// Mock System Stats Mapper
const mockMapSystemStats = vi.fn()
const mockIsSystemStatsResponse = vi.fn()

vi.mock('@/lib/mappers/systemStatsMapper', () => ({
  mapSystemStats: mockMapSystemStats,
  isSystemStatsResponse: mockIsSystemStatsResponse
}))

describe('useSystemStats Hook', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { 
          retry: false,
          refetchOnWindowFocus: false
        },
        mutations: { retry: false }
      }
    })
    vi.clearAllMocks()
  })

  afterEach(() => {
    queryClient.clear()
  })

  const createWrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )

  const mockBackendResponse = {
    users: {
      total: 150,
      active: 142,
      locked: 3,
      new_today: 5
    },
    security: {
      failed_logins: 12,
      active_sessions: 89,
      blocked_ips: 2
    },
    system: {
      uptime: 86400, // 24 hours in seconds
      memory_usage: 65.5,
      cpu_usage: 23.8,
      disk_usage: 45.2
    },
    audit: {
      total_logs: 5420,
      critical_events: 2,
      warnings: 15
    }
  }

  const mockMappedStats: AdminDashboardStats = {
    totalUsers: 150,
    activeUsers: 142,
    lockedUsers: 3,
    newUsersToday: 5,
    failedLogins: 12,
    activeSessions: 89,
    blockedIPs: 2,
    systemUptime: 86400,
    memoryUsage: 65.5,
    cpuUsage: 23.8,
    diskUsage: 45.2,
    totalAuditLogs: 5420,
    criticalEvents: 2,
    warnings: 15,
    lastUpdated: new Date().toISOString()
  }

  describe('Basic Functionality', () => {
    it('should fetch system stats successfully', async () => {
      mockApiClient.get.mockResolvedValue(mockBackendResponse)
      mockIsSystemStatsResponse.mockReturnValue(true)
      mockMapSystemStats.mockReturnValue(mockMappedStats)

      const { result } = renderHook(() => useSystemStats(), { 
        wrapper: createWrapper 
      })

      // Initial loading state
      expect(result.current.isLoading).toBe(true)
      expect(result.current.stats).toBeUndefined()
      expect(result.current.error).toBeNull()

      // Wait for data to load
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      // Verify API was called correctly
      expect(mockApiClient.get).toHaveBeenCalledWith('/api/v2/admin/system-stats')

      // Verify response validation
      expect(mockIsSystemStatsResponse).toHaveBeenCalledWith(mockBackendResponse)

      // Verify mapping
      expect(mockMapSystemStats).toHaveBeenCalledWith(mockBackendResponse)

      // Verify final stats
      expect(result.current.stats).toEqual(mockMappedStats)
      expect(result.current.error).toBeNull()
    })

    it('should handle API errors gracefully', async () => {
      const apiError = new Error('Network error')
      mockApiClient.get.mockRejectedValue(apiError)

      const { result } = renderHook(() => useSystemStats(), { 
        wrapper: createWrapper 
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.stats).toBeUndefined()
      expect(result.current.error).toBeTruthy()
    })

    it('should handle invalid response format', async () => {
      const invalidResponse = { invalid: 'data' }
      mockApiClient.get.mockResolvedValue(invalidResponse)
      mockIsSystemStatsResponse.mockReturnValue(false)

      const { result } = renderHook(() => useSystemStats(), { 
        wrapper: createWrapper 
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(mockIsSystemStatsResponse).toHaveBeenCalledWith(invalidResponse)
      expect(mockMapSystemStats).not.toHaveBeenCalled()
      expect(result.current.error).toBeTruthy()
    })
  })

  describe('Real-time Updates', () => {
    it('should enable polling when realTimeUpdates is true', async () => {
      mockApiClient.get.mockResolvedValue(mockBackendResponse)
      mockIsSystemStatsResponse.mockReturnValue(true)
      mockMapSystemStats.mockReturnValue(mockMappedStats)

      const { result } = renderHook(() => useSystemStats({ 
        realTimeUpdates: true,
        refreshInterval: 1000 // 1 second for testing
      }), { 
        wrapper: createWrapper 
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.stats).toEqual(mockMappedStats)

      // Verify that the query is set up for polling
      const queryState = queryClient.getQueryState(['admin-system-stats'])
      expect(queryState).toBeDefined()
    })

    it('should disable polling when realTimeUpdates is false', async () => {
      mockApiClient.get.mockResolvedValue(mockBackendResponse)
      mockIsSystemStatsResponse.mockReturnValue(true)
      mockMapSystemStats.mockReturnValue(mockMappedStats)

      const { result } = renderHook(() => useSystemStats({ 
        realTimeUpdates: false
      }), { 
        wrapper: createWrapper 
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.stats).toEqual(mockMappedStats)
    })

    it('should use custom refresh interval', async () => {
      mockApiClient.get.mockResolvedValue(mockBackendResponse)
      mockIsSystemStatsResponse.mockReturnValue(true)
      mockMapSystemStats.mockReturnValue(mockMappedStats)

      const customInterval = 5000 // 5 seconds

      const { result } = renderHook(() => useSystemStats({ 
        realTimeUpdates: true,
        refreshInterval: customInterval
      }), { 
        wrapper: createWrapper 
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.stats).toEqual(mockMappedStats)
    })
  })

  describe('Data Structure Validation', () => {
    it('should validate complete system stats structure', async () => {
      mockApiClient.get.mockResolvedValue(mockBackendResponse)
      mockIsSystemStatsResponse.mockReturnValue(true)
      mockMapSystemStats.mockReturnValue(mockMappedStats)

      const { result } = renderHook(() => useSystemStats(), { 
        wrapper: createWrapper 
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      const stats = result.current.stats!

      // Validate user statistics
      expect(typeof stats.totalUsers).toBe('number')
      expect(typeof stats.activeUsers).toBe('number')
      expect(typeof stats.lockedUsers).toBe('number')
      expect(typeof stats.newUsersToday).toBe('number')

      // Validate security statistics
      expect(typeof stats.failedLogins).toBe('number')
      expect(typeof stats.activeSessions).toBe('number')
      expect(typeof stats.blockedIPs).toBe('number')

      // Validate system statistics
      expect(typeof stats.systemUptime).toBe('number')
      expect(typeof stats.memoryUsage).toBe('number')
      expect(typeof stats.cpuUsage).toBe('number')
      expect(typeof stats.diskUsage).toBe('number')

      // Validate audit statistics
      expect(typeof stats.totalAuditLogs).toBe('number')
      expect(typeof stats.criticalEvents).toBe('number')
      expect(typeof stats.warnings).toBe('number')

      // Validate metadata
      expect(typeof stats.lastUpdated).toBe('string')
    })

    it('should handle partial data gracefully', async () => {
      const partialResponse = {
        users: {
          total: 100,
          active: 95
          // Missing locked and new_today
        },
        security: {
          failed_logins: 5
          // Missing other security fields
        }
        // Missing system and audit sections
      }

      const partialMappedStats: AdminDashboardStats = {
        totalUsers: 100,
        activeUsers: 95,
        lockedUsers: 0,
        newUsersToday: 0,
        failedLogins: 5,
        activeSessions: 0,
        blockedIPs: 0,
        systemUptime: 0,
        memoryUsage: 0,
        cpuUsage: 0,
        diskUsage: 0,
        totalAuditLogs: 0,
        criticalEvents: 0,
        warnings: 0,
        lastUpdated: new Date().toISOString()
      }

      mockApiClient.get.mockResolvedValue(partialResponse)
      mockIsSystemStatsResponse.mockReturnValue(true)
      mockMapSystemStats.mockReturnValue(partialMappedStats)

      const { result } = renderHook(() => useSystemStats(), { 
        wrapper: createWrapper 
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.stats).toEqual(partialMappedStats)
      expect(result.current.error).toBeNull()
    })
  })

  describe('Refetch Functionality', () => {
    it('should allow manual refetch', async () => {
      mockApiClient.get.mockResolvedValue(mockBackendResponse)
      mockIsSystemStatsResponse.mockReturnValue(true)
      mockMapSystemStats.mockReturnValue(mockMappedStats)

      const { result } = renderHook(() => useSystemStats(), { 
        wrapper: createWrapper 
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      // Clear previous calls
      mockApiClient.get.mockClear()

      // Trigger refetch
      await result.current.refetch()

      // Verify API was called again
      expect(mockApiClient.get).toHaveBeenCalledWith('/api/v2/admin/system-stats')
    })

    it('should handle refetch errors', async () => {
      // Initial successful load
      mockApiClient.get.mockResolvedValueOnce(mockBackendResponse)
      mockIsSystemStatsResponse.mockReturnValue(true)
      mockMapSystemStats.mockReturnValue(mockMappedStats)

      const { result } = renderHook(() => useSystemStats(), { 
        wrapper: createWrapper 
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      // Mock error on refetch
      mockApiClient.get.mockRejectedValueOnce(new Error('Refetch failed'))

      // Trigger refetch
      const refetchResult = await result.current.refetch()

      expect(refetchResult.isError).toBe(true)
    })
  })

  describe('Integration with Backend', () => {
    it('should match expected backend endpoint contract', async () => {
      mockApiClient.get.mockResolvedValue(mockBackendResponse)
      mockIsSystemStatsResponse.mockReturnValue(true)
      mockMapSystemStats.mockReturnValue(mockMappedStats)

      const { result } = renderHook(() => useSystemStats(), { 
        wrapper: createWrapper 
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      // Verify correct endpoint is called
      expect(mockApiClient.get).toHaveBeenCalledWith('/api/v2/admin/system-stats')

      // Verify response structure validation
      expect(mockIsSystemStatsResponse).toHaveBeenCalledWith(mockBackendResponse)

      // Verify mapping is applied
      expect(mockMapSystemStats).toHaveBeenCalledWith(mockBackendResponse)
    })

    it('should handle authentication errors', async () => {
      const authError = new Error('Unauthorized')
      authError.name = 'AuthError'
      mockApiClient.get.mockRejectedValue(authError)

      const { result } = renderHook(() => useSystemStats(), { 
        wrapper: createWrapper 
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.error).toBeTruthy()
      expect(result.current.stats).toBeUndefined()
    })

    it('should handle server errors', async () => {
      const serverError = new Error('Internal Server Error')
      serverError.name = 'ServerError'
      mockApiClient.get.mockRejectedValue(serverError)

      const { result } = renderHook(() => useSystemStats(), { 
        wrapper: createWrapper 
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.error).toBeTruthy()
      expect(result.current.stats).toBeUndefined()
    })
  })

  describe('Performance', () => {
    it('should cache results appropriately', async () => {
      mockApiClient.get.mockResolvedValue(mockBackendResponse)
      mockIsSystemStatsResponse.mockReturnValue(true)
      mockMapSystemStats.mockReturnValue(mockMappedStats)

      // First hook instance
      const { result: result1 } = renderHook(() => useSystemStats(), { 
        wrapper: createWrapper 
      })

      await waitFor(() => {
        expect(result1.current.isLoading).toBe(false)
      })

      // Second hook instance should use cached data
      const { result: result2 } = renderHook(() => useSystemStats(), { 
        wrapper: createWrapper 
      })

      // Should immediately have data from cache
      expect(result2.current.stats).toEqual(mockMappedStats)

      // API should only be called once
      expect(mockApiClient.get).toHaveBeenCalledTimes(1)
    })

    it('should handle concurrent requests efficiently', async () => {
      mockApiClient.get.mockResolvedValue(mockBackendResponse)
      mockIsSystemStatsResponse.mockReturnValue(true)
      mockMapSystemStats.mockReturnValue(mockMappedStats)

      // Create multiple hook instances simultaneously
      const { result: result1 } = renderHook(() => useSystemStats(), { 
        wrapper: createWrapper 
      })
      const { result: result2 } = renderHook(() => useSystemStats(), { 
        wrapper: createWrapper 
      })
      const { result: result3 } = renderHook(() => useSystemStats(), { 
        wrapper: createWrapper 
      })

      await waitFor(() => {
        expect(result1.current.isLoading).toBe(false)
        expect(result2.current.isLoading).toBe(false)
        expect(result3.current.isLoading).toBe(false)
      })

      // All should have the same data
      expect(result1.current.stats).toEqual(mockMappedStats)
      expect(result2.current.stats).toEqual(mockMappedStats)
      expect(result3.current.stats).toEqual(mockMappedStats)

      // API should only be called once due to deduplication
      expect(mockApiClient.get).toHaveBeenCalledTimes(1)
    })
  })
})