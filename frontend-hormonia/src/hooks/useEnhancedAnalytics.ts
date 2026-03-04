/**
 * Enhanced Analytics React Hook
 * Manages analytics data fetching and state
 */

import { useState, useEffect, useCallback } from 'react'
import { createLogger } from '@/utils/logger'

const logger = createLogger('useEnhancedAnalytics')
import {
  EnhancedDashboard,
  Prediction,
  TrendData,
  CustomReport,
  DashboardFilters,
  ReportConfig,
} from '../types/enhanced-analytics'
import { enhancedAnalyticsApi } from '../lib/api-client/enhanced-analytics'

export interface UseEnhancedAnalyticsOptions {
  filters?: DashboardFilters
  autoRefresh?: boolean
  refreshInterval?: number // milliseconds
}

export interface UseEnhancedAnalyticsReturn {
  dashboard: EnhancedDashboard | null
  loading: boolean
  error: Error | null
  refresh: () => Promise<void>
  generateReport: (config: ReportConfig) => Promise<CustomReport>
  downloadReport: (reportId: string, format: 'pdf' | 'csv' | 'json') => Promise<void>
  exportDashboard: (format: 'pdf' | 'csv') => Promise<void>
  acknowledgeAlert: (alertId: string) => Promise<void>
  updateFilters: (filters: DashboardFilters) => void
}

export function useEnhancedAnalytics(
  options: UseEnhancedAnalyticsOptions = {}
): UseEnhancedAnalyticsReturn {
  const [dashboard, setDashboard] = useState<EnhancedDashboard | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const [filters, setFilters] = useState<DashboardFilters | undefined>(options.filters)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const data = await enhancedAnalyticsApi.getDashboard(filters)
      setDashboard(data)
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to fetch dashboard')
      setError(error)
      logger.error('Error fetching dashboard', error)
    } finally {
      setLoading(false)
    }
  }, [filters])

  const generateReport = useCallback(async (config: ReportConfig): Promise<CustomReport> => {
    setLoading(true)
    setError(null)

    try {
      const report = await enhancedAnalyticsApi.generateCustomReport(config)
      return report
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to generate report')
      setError(error)
      throw error
    } finally {
      setLoading(false)
    }
  }, [])

  const downloadReport = useCallback(
    async (reportId: string, format: 'pdf' | 'csv' | 'json'): Promise<void> => {
      try {
        const blob = await enhancedAnalyticsApi.downloadReport(reportId, format)

        // Create download link
        const url = window.URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = `report-${reportId}.${format}`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        window.URL.revokeObjectURL(url)
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Failed to download report')
        setError(error)
        throw error
      }
    },
    []
  )

  const exportDashboard = useCallback(
    async (format: 'pdf' | 'csv'): Promise<void> => {
      setLoading(true)
      try {
        const blob = await enhancedAnalyticsApi.exportDashboard(filters, format)

        // Create download link
        const url = window.URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = `dashboard-${new Date().toISOString()}.${format}`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        window.URL.revokeObjectURL(url)
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Failed to export dashboard')
        setError(error)
        throw error
      } finally {
        setLoading(false)
      }
    },
    [filters]
  )

  const acknowledgeAlert = useCallback(
    async (alertId: string): Promise<void> => {
      try {
        await enhancedAnalyticsApi.acknowledgeAlert(alertId)

        // Update dashboard to reflect acknowledged alert
        if (dashboard) {
          setDashboard({
            ...dashboard,
            alerts: dashboard.alerts.map((alert) =>
              alert.id === alertId ? { ...alert, acknowledged: true } : alert
            ),
          })
        }
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Failed to acknowledge alert')
        setError(error)
        throw error
      }
    },
    [dashboard]
  )

  const updateFilters = useCallback((newFilters: DashboardFilters) => {
    setFilters(newFilters)
  }, [])

  // Initial load
  useEffect(() => {
    refresh()
  }, [refresh])

  // Auto-refresh
  useEffect(() => {
    if (!options.autoRefresh) return

    const interval = setInterval(() => {
      refresh()
    }, options.refreshInterval || 60000) // Default: 1 minute

    return () => clearInterval(interval)
  }, [options.autoRefresh, options.refreshInterval, refresh])

  return {
    dashboard,
    loading,
    error,
    refresh,
    generateReport,
    downloadReport,
    exportDashboard,
    acknowledgeAlert,
    updateFilters,
  }
}

export interface UsePredictionsOptions {
  patientId?: string
  predictionType?: string
  autoRefresh?: boolean
  refreshInterval?: number
}

export interface UsePredictionsReturn {
  predictions: Prediction[]
  loading: boolean
  error: Error | null
  refresh: () => Promise<void>
  refreshForPatient: (patientId: string) => Promise<void>
}

export function usePredictions(options: UsePredictionsOptions = {}): UsePredictionsReturn {
  const [predictions, setPredictions] = useState<Prediction[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const data = await enhancedAnalyticsApi.getPredictions(
        options.patientId,
        options.predictionType
      )
      setPredictions(data)
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to fetch predictions')
      setError(error)
      logger.error('Error fetching predictions', error)
    } finally {
      setLoading(false)
    }
  }, [options.patientId, options.predictionType])

  const refreshForPatient = useCallback(async (patientId: string) => {
    setLoading(true)
    setError(null)

    try {
      const data = await enhancedAnalyticsApi.refreshPredictions(patientId)
      setPredictions(data)
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to refresh predictions')
      setError(error)
      throw error
    } finally {
      setLoading(false)
    }
  }, [])

  // Initial load
  useEffect(() => {
    refresh()
  }, [refresh])

  // Auto-refresh
  useEffect(() => {
    if (!options.autoRefresh) return

    const interval = setInterval(() => {
      refresh()
    }, options.refreshInterval || 120000) // Default: 2 minutes

    return () => clearInterval(interval)
  }, [options.autoRefresh, options.refreshInterval, refresh])

  return {
    predictions,
    loading,
    error,
    refresh,
    refreshForPatient,
  }
}

export interface UseTrendsOptions {
  metric: string
  period: string
  filters?: DashboardFilters
}

export interface UseTrendsReturn {
  trendData: TrendData | null
  loading: boolean
  error: Error | null
  refresh: () => Promise<void>
}

export function useTrends(options: UseTrendsOptions): UseTrendsReturn {
  const [trendData, setTrendData] = useState<TrendData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const data = await enhancedAnalyticsApi.getTrends(
        options.metric,
        options.period,
        options.filters
      )
      setTrendData(data)
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to fetch trend data')
      setError(error)
      logger.error('Error fetching trend data', error)
    } finally {
      setLoading(false)
    }
  }, [options.metric, options.period, options.filters])

  // Refresh when options change
  useEffect(() => {
    refresh()
  }, [refresh])

  return {
    trendData,
    loading,
    error,
    refresh,
  }
}
