/**
 * System Stats Types
 * Defines the structure for system statistics and health metrics
 */

export interface SystemStats {
  system: {
    uptime: number
    cpu_usage?: number
    memory_usage?: number
  }
  users: {
    total: number
    active: number
  }
  security: {
    active_sessions: number
    failed_logins?: number
  }
  patients?: {
    total: number
    active: number
  }
  messages?: {
    sent_today: number
    pending: number
  }
}

export interface SystemHealthMetrics {
  cpu_percent: number
  memory_percent: number
  disk_usage_gb: number
  uptime_hours: number
}

export interface ActiveUsersMetrics {
  total: number
  doctors: number
  patients: number
  admins: number
}

export interface DatabaseMetrics {
  total_size_mb: number
  active_connections: number
  query_performance_ms: number
  cache_hit_rate: number
}

export interface ServiceStatusMetrics {
  redis: 'healthy' | 'degraded' | 'down'
  database: 'healthy' | 'degraded' | 'down'
  openai_api: 'healthy' | 'degraded' | 'down'
}

export interface SystemStatsResponse {
  system_health: SystemHealthMetrics
  active_users: ActiveUsersMetrics
  database_metrics: DatabaseMetrics
  service_status: ServiceStatusMetrics
  last_updated: string
}
