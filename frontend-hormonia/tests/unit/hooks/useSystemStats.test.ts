import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useSystemStats } from '@/hooks/useSystemStats'
import { apiClient } from '@/lib/api-client'

// Mock API client
vi.mock('@/lib/api-client', () => ({
  apiClient: {
    get: vi.fn(),
  },
}))

// Mock logger
vi.mock('@/lib/logger', () => ({
  createLogger: () => ({
    log: vi.fn(),
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
  }),
}))

describe('useSystemStats', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('successful data fetching', () => {
    it('should fetch and return dashboard stats', async () => {
      const mockStats = {
        total_patients: 100,
        active_patients: 75,
        messages_today: 45,
        alerts_pending: 12,
        active_patients_percentage: 75.0,
        response_rate: 92.5,
        messages_sent: 450,
        completed_quizzes: 89,
        patients_change: 5.2,
        active_patients_change: 3.8,
        messages_change: -2.1,
        alerts_change: 15.0,
        recent_messages: [
          {
            id: '1',
            patient_name: 'João Silva',
            content: 'Consulta agendada',
            timestamp: '2025-10-10T10:30:00-03:00',
          },
        ],
        recent_alerts: [
          {
            id: '1',
            patient_name: 'Maria Santos',
            severity: 'high',
            message: 'Alerta de medicação',
            timestamp: '2025-10-10T11:00:00-03:00',
          },
        ],
        recent_quiz_completions: [
          {
            id: '1',
            patient_name: 'Pedro Costa',
            quiz_name: 'Avaliação Mensal',
            score: 85,
            completed_at: '2025-10-10T09:00:00-03:00',
          },
        ],
        engagement_chart: [
          { date: '2025-10-01', value: 78 },
          { date: '2025-10-02', value: 82 },
        ],
        alert_severity_chart: [
          { severity: 'high', count: 5 },
          { severity: 'medium', count: 15 },
        ],
        treatment_progress_chart: [
          { week: 1, completed: 45, pending: 20 },
        ],
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce(mockStats)

      const { result } = renderHook(() => useSystemStats())

      // Initial state
      expect(result.current.isLoading).toBe(true)
      expect(result.current.stats).toBeNull()
      expect(result.current.error).toBeNull()

      // Wait for data to load
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      // Verify stats loaded correctly
      expect(result.current.stats).toEqual(mockStats)
      expect(result.current.error).toBeNull()
      expect(apiClient.get).toHaveBeenCalledWith('/analytics/dashboard')
    })

    it('should handle empty stats data', async () => {
      const emptyStats = {
        total_patients: 0,
        active_patients: 0,
        messages_today: 0,
        alerts_pending: 0,
        active_patients_percentage: 0,
        response_rate: 0,
        messages_sent: 0,
        completed_quizzes: 0,
        patients_change: 0,
        active_patients_change: 0,
        messages_change: 0,
        alerts_change: 0,
        recent_messages: [],
        recent_alerts: [],
        recent_quiz_completions: [],
        engagement_chart: [],
        alert_severity_chart: [],
        treatment_progress_chart: [],
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce(emptyStats)

      const { result } = renderHook(() => useSystemStats())

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.stats).toEqual(emptyStats)
      expect(result.current.error).toBeNull()
    })
  })

  describe('error handling', () => {
    it('should handle API errors gracefully', async () => {
      const errorMessage = 'Failed to fetch dashboard stats'
      vi.mocked(apiClient.get).mockRejectedValueOnce(new Error(errorMessage))

      const { result } = renderHook(() => useSystemStats())

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.stats).toBeNull()
      expect(result.current.error).toBe(errorMessage)
    })

    it('should handle network errors', async () => {
      vi.mocked(apiClient.get).mockRejectedValueOnce(new Error('Network error'))

      const { result } = renderHook(() => useSystemStats())

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.stats).toBeNull()
      expect(result.current.error).toBe('Network error')
    })

    it('should handle timeout errors', async () => {
      vi.mocked(apiClient.get).mockRejectedValueOnce(new Error('Request timeout'))

      const { result } = renderHook(() => useSystemStats())

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.error).toBe('Request timeout')
    })
  })

  describe('data refresh', () => {
    it('should allow manual refresh of stats', async () => {
      const initialStats = {
        total_patients: 100,
        active_patients: 75,
        messages_today: 45,
        alerts_pending: 12,
      }

      const updatedStats = {
        total_patients: 105,
        active_patients: 80,
        messages_today: 50,
        alerts_pending: 10,
      }

      vi.mocked(apiClient.get)
        .mockResolvedValueOnce(initialStats)
        .mockResolvedValueOnce(updatedStats)

      const { result, rerender } = renderHook(() => useSystemStats())

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.stats).toMatchObject(initialStats)

      // Trigger refresh by remounting
      rerender()

      await waitFor(() => {
        expect(apiClient.get).toHaveBeenCalledTimes(2)
      })
    })
  })

  describe('loading states', () => {
    it('should show loading state during initial fetch', () => {
      vi.mocked(apiClient.get).mockImplementationOnce(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      )

      const { result } = renderHook(() => useSystemStats())

      expect(result.current.isLoading).toBe(true)
      expect(result.current.stats).toBeNull()
      expect(result.current.error).toBeNull()
    })

    it('should clear loading state after successful fetch', async () => {
      const mockStats = {
        total_patients: 100,
        active_patients: 75,
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce(mockStats)

      const { result } = renderHook(() => useSystemStats())

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.stats).toBeTruthy()
    })

    it('should clear loading state after error', async () => {
      vi.mocked(apiClient.get).mockRejectedValueOnce(new Error('API Error'))

      const { result } = renderHook(() => useSystemStats())

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.error).toBeTruthy()
    })
  })

  describe('data validation', () => {
    it('should handle malformed API responses', async () => {
      const malformedData = {
        // Missing required fields
        total_patients: 100,
        // other fields missing
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce(malformedData)

      const { result } = renderHook(() => useSystemStats())

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      // Hook should still work with partial data
      expect(result.current.stats).toBeTruthy()
    })

    it('should handle null API response', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce(null)

      const { result } = renderHook(() => useSystemStats())

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.stats).toBeNull()
    })
  })

  describe('chart data handling', () => {
    it('should correctly process engagement chart data', async () => {
      const mockStats = {
        engagement_chart: [
          { date: '2025-10-01', value: 78 },
          { date: '2025-10-02', value: 82 },
          { date: '2025-10-03', value: 85 },
        ],
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce(mockStats)

      const { result } = renderHook(() => useSystemStats())

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.stats?.engagement_chart).toHaveLength(3)
      expect(result.current.stats?.engagement_chart[0]).toHaveProperty('date')
      expect(result.current.stats?.engagement_chart[0]).toHaveProperty('value')
    })

    it('should correctly process alert severity chart data', async () => {
      const mockStats = {
        alert_severity_chart: [
          { severity: 'high', count: 5 },
          { severity: 'medium', count: 15 },
          { severity: 'low', count: 30 },
        ],
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce(mockStats)

      const { result } = renderHook(() => useSystemStats())

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.stats?.alert_severity_chart).toHaveLength(3)
    })

    it('should correctly process treatment progress chart data', async () => {
      const mockStats = {
        treatment_progress_chart: [
          { week: 1, completed: 45, pending: 20 },
          { week: 2, completed: 50, pending: 15 },
        ],
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce(mockStats)

      const { result } = renderHook(() => useSystemStats())

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.stats?.treatment_progress_chart).toHaveLength(2)
    })
  })

  describe('percentage calculations', () => {
    it('should handle percentage values correctly', async () => {
      const mockStats = {
        active_patients_percentage: 75.5,
        response_rate: 92.8,
        patients_change: 5.2,
        active_patients_change: -3.1,
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce(mockStats)

      const { result } = renderHook(() => useSystemStats())

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.stats?.active_patients_percentage).toBe(75.5)
      expect(result.current.stats?.response_rate).toBe(92.8)
      expect(result.current.stats?.patients_change).toBe(5.2)
      expect(result.current.stats?.active_patients_change).toBe(-3.1)
    })
  })
})
