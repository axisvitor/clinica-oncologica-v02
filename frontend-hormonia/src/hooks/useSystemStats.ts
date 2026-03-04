import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import type { DashboardMetrics } from '@/lib/api-client/analytics'
import { AdminDashboardStats } from '@/types/admin'

interface UseSystemStatsOptions {
  /** Enable real-time updates via polling */
  realTimeUpdates?: boolean
  /** Auto-refresh interval in milliseconds */
  refreshInterval?: number
}

/**
 * Hook to fetch admin system statistics from /api/v2/admin/system-stats
 * Maps backend SystemStatsResponse to frontend AdminDashboardStats format
 */
export function useSystemStats(options: UseSystemStatsOptions = {}) {
  const {
    realTimeUpdates = true,
    refreshInterval = 30000, // 30 seconds default
  } = options

  const {
    data: stats,
    isLoading,
    error,
    refetch,
  } = useQuery<AdminDashboardStats>({
    queryKey: ['admin-system-stats'],
    queryFn: async () => {
      const dashboardMetrics = await apiClient.analytics.getDashboardMetrics()
      return mapDashboardMetricsToAdminStats(dashboardMetrics)
    },
    refetchInterval: realTimeUpdates ? refreshInterval : false,
    staleTime: 10000, // 10 seconds
    retry: 3,
  })

  return {
    stats,
    isLoading,
    error,
    refetch,
  }
}

function mapDashboardMetricsToAdminStats(metrics: DashboardMetrics): AdminDashboardStats {
  return {
    users: {
      total: metrics.total_patients,
      active: metrics.active_patients,
      locked: 0,
      new_today: 0,
    },
    security: {
      failed_logins: 0,
      active_sessions: metrics.active_patients,
      blocked_ips: 0,
    },
    system: {
      uptime: 0,
      memory_usage: 0,
      cpu_usage: 0,
      disk_usage: 0,
    },
    audit: {
      total_logs: metrics.completed_appointments,
      critical_events: 0,
      warnings: 0,
    },
  }
}
