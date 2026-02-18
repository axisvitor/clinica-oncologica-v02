import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import React from 'react'

// Import hooks to test
import { useQuestionarios } from '@/hooks/api/useQuestionarios'
import { useTreatmentDistribution } from '@/hooks/api/useTreatmentDistribution'
import { useMedicoDashboardStats } from '@/hooks/api/useMedicoDashboardStats'

// Mock API client
const mockApiClient = {
  questionarios: {
    getAll: vi.fn(),
    getById: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
  medico: {
    getTreatmentDistribution: vi.fn(),
    getDashboardStats: vi.fn(),
  },
}

vi.mock('../../lib/api-client', () => ({
  apiClient: mockApiClient,
}))

// Mock useAuth hook
const mockUseAuth = vi.fn()
vi.mock('@/hooks/useAuth', () => ({
  useAuth: mockUseAuth,
}))

describe('API Hooks', () => {
  let queryClient: QueryClient

  const createWrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )

  beforeEach(() => {
    vi.clearAllMocks()
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })

    // Default auth mock
    mockUseAuth.mockReturnValue({
      user: { id: '1', role: 'medico' },
      isAuthenticated: true,
    })
  })

  describe('useQuestionarios', () => {
    it('should fetch questionarios successfully', async () => {
      const mockQuestionarios = [
        { id: '1', title: 'Test Quiz 1', description: 'Description 1' },
        { id: '2', title: 'Test Quiz 2', description: 'Description 2' },
      ]

      mockApiClient.questionarios.getAll.mockResolvedValue({
        data: mockQuestionarios,
        total: 2,
      })

      const { result } = renderHook(() => useQuestionarios(), {
        wrapper: createWrapper,
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.data).toEqual({
        data: mockQuestionarios,
        total: 2,
      })
      expect(result.current.error).toBeNull()
      expect(mockApiClient.questionarios.getAll).toHaveBeenCalledWith({
        page: 1,
        limit: 10,
        search: '',
        status: 'all',
      })
    })

    it('should handle questionarios fetch error', async () => {
      const mockError = new Error('Failed to fetch questionarios')
      mockApiClient.questionarios.getAll.mockRejectedValue(mockError)

      const { result } = renderHook(() => useQuestionarios(), {
        wrapper: createWrapper,
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.error).toBe(mockError)
      expect(result.current.data).toBeUndefined()
    })

    it('should use custom query parameters', async () => {
      const customParams = {
        page: 2,
        limit: 20,
        search: 'test search',
        status: 'active' as const,
      }

      mockApiClient.questionarios.getAll.mockResolvedValue({
        data: [],
        total: 0,
      })

      renderHook(() => useQuestionarios(customParams), {
        wrapper: createWrapper,
      })

      await waitFor(() => {
        expect(mockApiClient.questionarios.getAll).toHaveBeenCalledWith(customParams)
      })
    })

    it('should be disabled when user is not authenticated', () => {
      mockUseAuth.mockReturnValue({
        user: null,
        isAuthenticated: false,
      })

      const { result } = renderHook(() => useQuestionarios(), {
        wrapper: createWrapper,
      })

      expect(result.current.isLoading).toBe(false)
      expect(result.current.data).toBeUndefined()
      expect(mockApiClient.questionarios.getAll).not.toHaveBeenCalled()
    })
  })

  describe('useTreatmentDistribution', () => {
    it('should fetch treatment distribution successfully', async () => {
      const mockDistribution = {
        distributions: [
          { treatment_type: 'Terapia Hormonal Feminina', count: 10, percentage: 50 },
          { treatment_type: 'Terapia Hormonal Masculina', count: 8, percentage: 40 },
          { treatment_type: 'Reposicao Hormonal', count: 2, percentage: 10 },
        ],
        total_patients: 20,
        last_updated: '2024-01-01T00:00:00-03:00',
      }

      mockApiClient.medico.getTreatmentDistribution.mockResolvedValue(mockDistribution)

      const { result } = renderHook(() => useTreatmentDistribution(), {
        wrapper: createWrapper,
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.data).toEqual(mockDistribution)
      expect(result.current.error).toBeNull()
      expect(mockApiClient.medico.getTreatmentDistribution).toHaveBeenCalled()
    })

    it('should handle treatment distribution fetch error', async () => {
      const mockError = new Error('Failed to fetch treatment distribution')
      mockApiClient.medico.getTreatmentDistribution.mockRejectedValue(mockError)

      const { result } = renderHook(() => useTreatmentDistribution(), {
        wrapper: createWrapper,
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.error).toBe(mockError)
      expect(result.current.data).toBeUndefined()
    })

    it('should pass date range parameters', async () => {
      const dateRange = {
        startDate: '2024-01-01',
        endDate: '2024-01-31',
      }

      mockApiClient.medico.getTreatmentDistribution.mockResolvedValue({
        distributions: [],
        total_patients: 0,
        last_updated: '2024-01-01T00:00:00-03:00',
      })

      renderHook(() => useTreatmentDistribution(dateRange), {
        wrapper: createWrapper,
      })

      await waitFor(() => {
        expect(mockApiClient.medico.getTreatmentDistribution).toHaveBeenCalledWith(dateRange)
      })
    })

    it('should be disabled when user is not medico', () => {
      mockUseAuth.mockReturnValue({
        user: { id: '1', role: 'paciente' },
        isAuthenticated: true,
      })

      const { result } = renderHook(() => useTreatmentDistribution(), {
        wrapper: createWrapper,
      })

      expect(result.current.isLoading).toBe(false)
      expect(result.current.data).toBeUndefined()
      expect(mockApiClient.medico.getTreatmentDistribution).not.toHaveBeenCalled()
    })
  })

  describe('useMedicoDashboardStats', () => {
    it('should fetch dashboard stats successfully', async () => {
      const mockStats = {
        total_patients: 50,
        active_patients: 45,
        pending_quizzes: 12,
        completed_quizzes_today: 8,
        high_risk_patients: 3,
        recent_activities: [
          { type: 'quiz_completed', patient_name: 'Joao Silva', timestamp: '2024-01-01T10:00:00-03:00' },
          { type: 'patient_registered', patient_name: 'Maria Santos', timestamp: '2024-01-01T09:30:00-03:00' },
        ],
        trends: {
          patients_growth: 10.5,
          quiz_completion_rate: 85.2,
          adherence_rate: 92.1,
        },
      }

      mockApiClient.medico.getDashboardStats.mockResolvedValue(mockStats)

      const { result } = renderHook(() => useMedicoDashboardStats(), {
        wrapper: createWrapper,
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.data).toEqual(mockStats)
      expect(result.current.error).toBeNull()
      expect(mockApiClient.medico.getDashboardStats).toHaveBeenCalled()
    })

    it('should handle dashboard stats fetch error', async () => {
      const mockError = new Error('Failed to fetch dashboard stats')
      mockApiClient.medico.getDashboardStats.mockRejectedValue(mockError)

      const { result } = renderHook(() => useMedicoDashboardStats(), {
        wrapper: createWrapper,
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.error).toBe(mockError)
      expect(result.current.data).toBeUndefined()
    })

    it('should use custom refresh interval', async () => {
      const customInterval = 30000 // 30 seconds

      mockApiClient.medico.getDashboardStats.mockResolvedValue({
        total_patients: 50,
        active_patients: 45,
        pending_quizzes: 12,
      })

      renderHook(() => useMedicoDashboardStats({ refreshInterval: customInterval }), {
        wrapper: createWrapper,
      })

      await waitFor(() => {
        expect(mockApiClient.medico.getDashboardStats).toHaveBeenCalled()
      })

      // Note: Testing the actual interval behavior would require more complex timer mocking
      // This test at least verifies the hook accepts the parameter
    })

    it('should disable auto-refresh when specified', async () => {
      mockApiClient.medico.getDashboardStats.mockResolvedValue({
        total_patients: 50,
        active_patients: 45,
        pending_quizzes: 12,
      })

      renderHook(() => useMedicoDashboardStats({ enabled: false }), {
        wrapper: createWrapper,
      })

      // Should not make initial call when disabled
      expect(mockApiClient.medico.getDashboardStats).not.toHaveBeenCalled()
    })

    it('should be disabled when user is not medico', () => {
      mockUseAuth.mockReturnValue({
        user: { id: '1', role: 'admin' },
        isAuthenticated: true,
      })

      const { result } = renderHook(() => useMedicoDashboardStats(), {
        wrapper: createWrapper,
      })

      expect(result.current.isLoading).toBe(false)
      expect(result.current.data).toBeUndefined()
      expect(mockApiClient.medico.getDashboardStats).not.toHaveBeenCalled()
    })
  })

  describe('Query Key Management', () => {
    it('should use consistent query keys for caching', async () => {
      // Test that the same parameters result in the same query key
      const params = { page: 1, limit: 10, search: 'test' }

      mockApiClient.questionarios.getAll.mockResolvedValue({
        data: [],
        total: 0,
      })

      const { result: result1 } = renderHook(() => useQuestionarios(params), {
        wrapper: createWrapper,
      })

      const { result: result2 } = renderHook(() => useQuestionarios(params), {
        wrapper: createWrapper,
      })

      await waitFor(() => {
        expect(result1.current.isLoading).toBe(false)
        expect(result2.current.isLoading).toBe(false)
      })

      // Should only call API once due to caching
      expect(mockApiClient.questionarios.getAll).toHaveBeenCalledTimes(1)
    })
  })

  describe('Error Recovery', () => {
    it('should retry failed requests when retry is triggered', async () => {
      let callCount = 0
      mockApiClient.questionarios.getAll.mockImplementation(() => {
        callCount++
        if (callCount === 1) {
          return Promise.reject(new Error('Network error'))
        }
        return Promise.resolve({ data: [], total: 0 })
      })

      const { result } = renderHook(() => useQuestionarios(), {
        wrapper: createWrapper,
      })

      // Wait for initial error
      await waitFor(() => {
        expect(result.current.error).toBeTruthy()
      })

      // Manually retry
      result.current.refetch()

      // Wait for successful retry
      await waitFor(() => {
        expect(result.current.data).toEqual({ data: [], total: 0 })
        expect(result.current.error).toBeNull()
      })

      expect(callCount).toBe(2)
    })
  })

  describe('Loading States', () => {
    it('should handle loading states correctly', async () => {
      let resolvePromise: (value: any) => void
      const pendingPromise = new Promise((resolve) => {
        resolvePromise = resolve
      })

      mockApiClient.questionarios.getAll.mockReturnValue(pendingPromise)

      const { result } = renderHook(() => useQuestionarios(), {
        wrapper: createWrapper,
      })

      // Should start loading
      expect(result.current.isLoading).toBe(true)
      expect(result.current.data).toBeUndefined()

      // Resolve the promise
      resolvePromise!({ data: [], total: 0 })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.data).toEqual({ data: [], total: 0 })
    })
  })

  describe('Data Transformation', () => {
    it('should handle empty responses correctly', async () => {
      mockApiClient.questionarios.getAll.mockResolvedValue({
        data: [],
        total: 0,
      })

      const { result } = renderHook(() => useQuestionarios(), {
        wrapper: createWrapper,
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.data).toEqual({
        data: [],
        total: 0,
      })
    })

    it('should handle malformed API responses gracefully', async () => {
      // Test with incomplete response
      mockApiClient.questionarios.getAll.mockResolvedValue({
        data: [{ id: '1' }], // Missing required fields
        // Missing total field
      })

      const { result } = renderHook(() => useQuestionarios(), {
        wrapper: createWrapper,
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      // Should still work with partial data
      expect(result.current.data).toBeDefined()
      expect(result.current.error).toBeNull()
    })
  })
})
