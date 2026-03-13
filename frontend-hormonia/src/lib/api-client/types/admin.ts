import type { SearchFilters } from './common'

export type {
  AdminUser,
  AuditLogEntry,
  SystemSettings,
  AdminUserActivity as UserActivityEntry,
} from '@/types/admin'

export interface AdminUserListFilters extends SearchFilters {
  role?: string
  is_active?: boolean
  status?: string
}

export interface CreateUserRequest {
  email: string
  full_name: string
  password: string
  role: string
  permissions?: string[]
  two_factor_enabled?: boolean
}

export interface UpdateUserRequest extends Partial<Omit<CreateUserRequest, 'password'>> {
  is_active?: boolean
  password?: string
}

export interface ResetPasswordRequest {
  new_password: string
  force_change?: boolean
}

export interface UserActivityFilters extends SearchFilters {
  action?: string
  resource?: string
  start_date?: string
  end_date?: string
}

export interface Role {
  id: string
  name: string
  description?: string
  permissions: string[]
  is_system: boolean
  created_at: string
  updated_at: string
}

export interface CreateRoleRequest {
  name: string
  description?: string
  permissions: string[]
}

export interface AuditLogFilters extends SearchFilters {
  user_id?: string
  action?: string
  entity_type?: string
  entity_id?: string
  start_date?: string
  end_date?: string
}

export interface SystemHealth {
  status: 'healthy' | 'degraded' | 'down'
  components: Array<{
    name: string
    status: 'up' | 'down' | 'degraded'
    last_check: string
    details?: Record<string, unknown>
  }>
  timestamp: string
}

export interface SystemMetrics {
  cpu_usage: number
  memory_usage: number
  disk_usage: number
  active_connections: number
  request_rate: number
  error_rate: number
  timestamp: string
}

export interface SystemStats {
  system: {
    cpu_percent: number
    memory_percent: number
    disk_percent: number
    uptime_seconds: number
    uptime?: number
  }
  users: {
    total: number
    active_now: number
    by_role: {
      admin?: number
      doctor?: number
      [key: string]: number | undefined
    }
  }
  security?: {
    failed_logins?: number
    active_sessions?: number
    blocked_ips?: number
  }
  database: {
    total_records: number
    total_patients: number
    total_users: number
    connections: number
  }
  timestamp: string
  uptime_seconds?: number
  total_requests?: number
  total_errors?: number
  active_users?: number
  database_size?: number
  cache_hit_rate?: number
}

export interface CreateAdminUserRequest {
  email: string
  full_name: string
  role: string
  permissions?: string[]
  password?: string
}

export interface UpdateAdminUserRequest {
  email?: string
  full_name?: string
  role?: string
  permissions?: string[]
  is_active?: boolean
}
