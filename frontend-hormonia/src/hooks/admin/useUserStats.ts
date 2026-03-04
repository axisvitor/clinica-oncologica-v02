/**
 * User Stats Hook - Dashboard Statistics
 *
 * Derives and fetches user statistics for admin dashboard
 * - Aggregates data from API and user list
 * - Calculates derived metrics
 * - Provides fallback logic for missing data
 *
 * @module hooks/admin/useUserStats
 */

import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'
import { apiClient } from '@/lib/api-client'
import { AdminUser, AdminDashboardStats } from '@/types/admin'
import { createLogger } from '@/utils/logger'

const logger = createLogger('useUserStats')

export interface UseUserStatsOptions {
  /** User list data for deriving stats */
  usersData?: {
    items: AdminUser[]
    total: number
  }
  /** Enable real-time updates */
  refetchInterval?: number | false
  /** Enable the query */
  enabled?: boolean
}

/**
 * Hook for fetching and computing user statistics
 *
 * @param options - Configuration options
 * @returns Statistics data and loading state
 *
 * @example
 * ```tsx
 * const { stats, isLoading, error } = useUserStats({
 *   usersData: usersResponse,
 *   refetchInterval: 30000
 * })
 *
 * console.log(stats?.users.total) // Total users count
 * console.log(stats?.users.active) // Active users count
 * ```
 */
export function useUserStats(options: UseUserStatsOptions = {}) {
  const { usersData, refetchInterval = false, enabled = true } = options

  // Derive stats from user list (fallback)
  const derivedStats = useMemo((): AdminDashboardStats | null => {
    if (!usersData?.items) return null

    const users = usersData.items
    const now = new Date()

    return {
      users: {
        total: usersData.total || 0,
        active: users.filter((u: AdminUser) => u.is_active).length,
        locked: users.filter((u: AdminUser) => u.locked_until && new Date(u.locked_until) > now)
          .length,
        new_today: 0, // Would need created_at comparison
      },
      security: {
        failed_logins: users.reduce(
          (sum: number, u: AdminUser) => sum + (u.failed_login_attempts || 0),
          0
        ),
        active_sessions: 0, // Not available from user list
        blocked_ips: 0, // Not available from user list
      },
      system: {
        uptime: 0,
        memory_usage: 0,
        cpu_usage: 0,
        disk_usage: 0,
      },
      audit: {
        total_logs: 0,
        critical_events: 0,
        warnings: 0,
      },
    }
  }, [usersData])

  // Fetch stats from API
  const {
    data: stats,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['admin-stats'],
    queryFn: async () => {
      try {
        // Try to get real stats from API
        const [systemStats, systemHealth] = await Promise.all([
          apiClient.admin.system.systemStats().catch(() => null),
          apiClient.admin.system.getHealth().catch(() => null),
        ])

        // Build comprehensive stats
        const stats: AdminDashboardStats = {
          users: {
            total: systemStats?.users?.total ?? usersData?.total ?? 0,
            active: systemStats?.users?.active_now ?? derivedStats?.users.active ?? 0,
            locked: derivedStats?.users.locked ?? 0,
            new_today: 0,
          },
          security: {
            failed_logins: derivedStats?.security.failed_logins ?? 0,
            active_sessions: 0,
            blocked_ips: 0,
          },
          system: {
            uptime:
              systemHealth?.status === 'healthy'
                ? 99.9
                : systemHealth?.status === 'degraded'
                  ? 95.0
                  : 0,
            memory_usage: 0,
            cpu_usage: 0,
            disk_usage: 0,
          },
          audit: {
            total_logs: 0,
            critical_events: 0,
            warnings: 0,
          },
        }

        return stats
      } catch (error) {
        logger.warn('Failed to fetch system stats from API, using derived data', { error })

        // Fallback to derived stats
        return (
          derivedStats || {
            users: { total: 0, active: 0, locked: 0, new_today: 0 },
            security: { failed_logins: 0, active_sessions: 0, blocked_ips: 0 },
            system: { uptime: 0, memory_usage: 0, cpu_usage: 0, disk_usage: 0 },
            audit: { total_logs: 0, critical_events: 0, warnings: 0 },
          }
        )
      }
    },
    enabled: enabled && !!usersData,
    refetchInterval,
    staleTime: 10000, // 10 seconds
  })

  // Calculate additional derived metrics
  const metrics = useMemo(() => {
    if (!stats) return null

    return {
      /** Percentage of active users */
      activePercentage: stats.users.total > 0 ? (stats.users.active / stats.users.total) * 100 : 0,

      /** Percentage of locked users */
      lockedPercentage: stats.users.total > 0 ? (stats.users.locked / stats.users.total) * 100 : 0,

      /** Average failed login attempts per user */
      avgFailedLogins: usersData?.items.length
        ? stats.security.failed_logins / usersData.items.length
        : 0,

      /** System health status */
      systemHealth:
        stats.system.uptime >= 99
          ? 'healthy'
          : stats.system.uptime >= 95
            ? 'degraded'
            : 'unhealthy',
    }
  }, [stats, usersData])

  return {
    /** Dashboard statistics */
    stats,
    /** Derived metrics */
    metrics,
    /** Loading state */
    isLoading,
    /** Error state */
    error,
    /** Refetch stats */
    refetch,
  }
}
