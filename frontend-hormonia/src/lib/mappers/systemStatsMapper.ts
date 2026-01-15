/**
 * Maps backend SystemStatsResponse to frontend AdminDashboardStats
 *
 * Backend returns:
 * - system.cpu_percent, memory_percent, disk_percent, uptime_seconds
 * - users.total, active_now, by_role
 * - database.total_records, total_patients, total_users, connections
 *
 * Frontend expects:
 * - users.{total, active, locked, new_today}
 * - security.{failed_logins, active_sessions, blocked_ips}
 * - system.{uptime, memory_usage, cpu_usage, disk_usage}
 * - audit.{total_logs, critical_events, warnings}
 */

import { AdminDashboardStats } from '@/types/admin'

interface SystemStatsResponse {
  system: {
    cpu_percent: number
    memory_percent: number
    disk_percent: number
    uptime_seconds: number
  }
  users: {
    total: number
    active_now: number
    by_role: Record<string, number>
  }
  database: {
    total_records: number
    total_patients: number
    total_users: number
    connections: number
  }
  timestamp: string
}

/**
 * Converts backend SystemStatsResponse to frontend AdminDashboardStats format
 */
export function mapSystemStats(backendResponse: SystemStatsResponse): AdminDashboardStats {
  return {
    users: {
      total: backendResponse.users.total,
      active: backendResponse.users.active_now,
      locked: 0, // Not provided by backend - would need separate endpoint
      new_today: 0 // Not provided by backend - would need separate endpoint
    },
    security: {
      failed_logins: 0, // Not provided by backend - would need separate endpoint
      active_sessions: backendResponse.users.active_now, // Use active users as proxy
      blocked_ips: 0 // Not provided by backend - would need separate endpoint
    },
    system: {
      uptime: backendResponse.system.uptime_seconds / 86400, // Convert seconds to days
      memory_usage: backendResponse.system.memory_percent,
      cpu_usage: backendResponse.system.cpu_percent,
      disk_usage: backendResponse.system.disk_percent
    },
    audit: {
      total_logs: backendResponse.database.total_records,
      critical_events: 0, // Not provided by backend - would need separate endpoint
      warnings: 0 // Not provided by backend - would need separate endpoint
    }
  }
}

/**
 * Type guard to check if response matches SystemStatsResponse structure
 */
export function isSystemStatsResponse(data: unknown): data is SystemStatsResponse {
  if (!data || typeof data !== 'object') {
    return false
  }

  const candidate = data as {
    system?: { cpu_percent?: unknown; memory_percent?: unknown }
    users?: { total?: unknown }
  }

  return (
    typeof candidate.system?.cpu_percent === 'number' &&
    typeof candidate.system?.memory_percent === 'number' &&
    typeof candidate.users?.total === 'number'
  )
}
