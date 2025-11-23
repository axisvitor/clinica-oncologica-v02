/**
 * Admin API Module
 *
 * Handles all admin-related API calls:
 * - User management (CRUD operations)
 * - System statistics and metrics
 * - Audit logs
 * - Role management
 * - System health monitoring
 */

import type { ApiClientCore, PaginatedResponse } from './core'

// ============================================================================
// TYPE DEFINITIONS
// ============================================================================

export interface AdminUser {
  id: string
  email: string
  full_name: string | null
  role: 'admin' | 'doctor'
  is_active: boolean
  permissions: string[]
  created_at: string
  updated_at?: string
  last_login?: string
  firebase_uid?: string
  two_factor_enabled?: boolean
}

export interface AdminUserCreate {
  email: string
  full_name: string
  password: string
  role: AdminUser['role']
  permissions?: string[]
  is_active?: boolean
}

export interface AdminUserUpdate {
  full_name?: string
  role?: AdminUser['role']
  permissions?: string[]
  is_active?: boolean
}

export interface UserActivityEntry {
  id: string
  user_id: string
  action: string
  resource_type?: string
  resource_id?: string
  details?: Record<string, unknown>
  ip_address?: string
  user_agent?: string
  created_at: string
}

export interface SystemStats {
  generated_at: string
  users: {
    total: number
    active: number
    inactive: number
    new_this_month: number
  }
  appointments: {
    total: number
    scheduled: number
    completed: number
    cancelled: number
    pending: number
  }
  revenue: {
    total: number
    this_month: number
    last_month: number
    growth_percentage: number
  }
  system: {
    error_rate: number
    uptime_percentage: number
    avg_response_time_ms: number
  }
}

export interface SystemHealth {
  status: 'healthy' | 'degraded' | 'down'
  database: {
    connected: boolean
    response_time_ms: number
  }
  cache: {
    connected: boolean
    hit_rate: number
  }
  external_services: Array<{
    name: string
    status: 'up' | 'down'
    last_checked: string
  }>
  timestamp: string
}

export interface SystemMetrics {
  cpu_usage: number
  memory_usage: number
  disk_usage: number
  active_connections: number
  requests_per_minute: number
  average_response_time: number
  error_rate: number
  timestamp: string
}

export interface AuditLogEntry {
  id: string
  user_id: string
  user_email?: string
  action: string
  resource_type: string
  resource_id?: string
  details?: Record<string, unknown>
  ip_address?: string
  user_agent?: string
  status: 'success' | 'failure'
  created_at: string
}

export interface Role {
  id: string
  name: string
  description?: string
  permissions: string[]
  is_system_role: boolean
  created_at: string
  updated_at?: string
}

export interface CreateRoleRequest {
  name: string
  description?: string
  permissions: string[]
}

// ============================================================================
// ADMIN API METHODS
// ============================================================================

/**
 * Admin API methods
 */
export function createAdminApi(client: ApiClientCore) {
  return {
    // ========================================================================
    // USER MANAGEMENT
    // ========================================================================

    /**
     * List all users with pagination
     */
    listUsers: async (
      page: number = 1,
      size: number = 20,
      filters?: {
        search?: string
        role?: string
        is_active?: boolean
      }
    ): Promise<PaginatedResponse<AdminUser>> => {
      const params: Record<string, string | number | boolean> = {
        page,
        limit: size,
        ...filters
      }

      const response = await client.get<any>('/api/v2/admin/users', params)

      // Normalize response to match PaginatedResponse interface
      const items = Array.isArray(response?.data) ? response.data : (response?.items ?? [])

      return {
        items,
        total: response?.total ?? items.length,
        page,
        size,
        pages: response?.pages ?? Math.ceil((response?.total ?? items.length) / size)
      }
    },

    /**
     * Get user by ID
     */
    getUser: async (userId: string): Promise<AdminUser> => {
      return client.get<AdminUser>(`/api/v2/admin/users/${userId}`)
    },

    /**
     * Create new user
     */
    createUser: async (data: AdminUserCreate): Promise<AdminUser> => {
      return client.post<AdminUser>('/api/v2/admin/users', data)
    },

    /**
     * Update user
     */
    updateUser: async (userId: string, data: AdminUserUpdate): Promise<AdminUser> => {
      return client.put<AdminUser>(`/api/v2/admin/users/${userId}`, data)
    },

    /**
     * Delete user
     */
    deleteUser: async (userId: string): Promise<{ message: string }> => {
      return client.delete<{ message: string }>(`/api/v2/admin/users/${userId}`)
    },

    /**
     * Activate user
     */
    activateUser: async (userId: string): Promise<{ message: string }> => {
      return client.post<{ message: string }>(`/api/v2/admin/users/${userId}/activate`)
    },

    /**
     * Deactivate user
     */
    deactivateUser: async (userId: string): Promise<{ message: string }> => {
      return client.post<{ message: string }>(`/api/v2/admin/users/${userId}/deactivate`)
    },

    /**
     * Reset user password
     */
    resetPassword: async (
      userId: string,
      data: { new_password: string; force_change?: boolean }
    ): Promise<{ message: string }> => {
      return client.post<{ message: string }>(
        `/api/v2/admin/users/${userId}/reset-password`,
        data
      )
    },

    /**
     * Update user permissions
     */
    updatePermissions: async (
      userId: string,
      permissions: string[]
    ): Promise<{ message: string }> => {
      return client.put<{ message: string }>(
        `/api/v2/admin/users/${userId}/permissions`,
        { permissions }
      )
    },

    /**
     * Get user activity log
     */
    getUserActivity: async (
      userId: string,
      page: number = 1,
      size: number = 20
    ): Promise<PaginatedResponse<UserActivityEntry>> => {
      const params = { page, limit: size }
      const response = await client.get<any>(
        `/api/v2/admin/users/${userId}/activity`,
        params
      )

      const items = Array.isArray(response?.data) ? response.data : (response?.items ?? [])

      return {
        items,
        total: response?.total ?? items.length,
        page,
        size,
        pages: response?.pages ?? Math.ceil((response?.total ?? items.length) / size)
      }
    },

    // ========================================================================
    // SYSTEM STATISTICS
    // ========================================================================

    /**
     * Get system statistics
     */
    getSystemStats: async (): Promise<SystemStats> => {
      return client.get<SystemStats>('/api/v2/admin/system-stats')
    },

    /**
     * Get system health
     */
    getSystemHealth: async (): Promise<SystemHealth> => {
      return client.get<SystemHealth>('/api/v2/admin/system/health')
    },

    /**
     * Get system metrics
     */
    getSystemMetrics: async (): Promise<SystemMetrics> => {
      return client.get<SystemMetrics>('/api/v2/admin/system/metrics')
    },

    // ========================================================================
    // AUDIT LOGS
    // ========================================================================

    /**
     * List audit logs
     */
    listAuditLogs: async (
      page: number = 1,
      size: number = 20,
      filters?: {
        user_id?: string
        action?: string
        resource_type?: string
        start_date?: string
        end_date?: string
      }
    ): Promise<PaginatedResponse<AuditLogEntry>> => {
      const params: Record<string, string | number | boolean> = {
        page,
        limit: size,
        ...filters
      }

      const response = await client.get<any>('/api/v2/admin/audit', params)
      const items = Array.isArray(response?.data) ? response.data : (response?.items ?? [])

      return {
        items,
        total: response?.total ?? items.length,
        page,
        size,
        pages: response?.pages ?? Math.ceil((response?.total ?? items.length) / size)
      }
    },

    /**
     * Export audit logs to CSV
     */
    exportAuditLogs: async (filters?: {
      user_id?: string
      action?: string
      start_date?: string
      end_date?: string
    }): Promise<Blob> => {
      const queryParams = new URLSearchParams(filters as any)
      const response = await fetch(
        `${client.getBaseURL()}/api/v2/admin/audit/export?${queryParams}`,
        {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${client.getAuthToken()}`
          },
          credentials: 'include'
        }
      )

      if (!response.ok) {
        throw new Error('Failed to export audit logs')
      }

      return response.blob()
    },

    // ========================================================================
    // ROLE MANAGEMENT
    // ========================================================================

    /**
     * List all roles
     */
    listRoles: async (): Promise<Role[]> => {
      const response = await client.get<any>('/api/v2/admin/roles')
      return Array.isArray(response) ? response : (response?.data ?? response?.items ?? [])
    },

    /**
     * Create role
     */
    createRole: async (data: CreateRoleRequest): Promise<Role> => {
      return client.post<Role>('/api/v2/admin/roles', data)
    },

    /**
     * Update role
     */
    updateRole: async (roleId: string, data: Partial<CreateRoleRequest>): Promise<Role> => {
      return client.put<Role>(`/api/v2/admin/roles/${roleId}`, data)
    },

    /**
     * Delete role
     */
    deleteRole: async (roleId: string): Promise<{ message: string }> => {
      return client.delete<{ message: string }>(`/api/v2/admin/roles/${roleId}`)
    },

    // ========================================================================
    // SYSTEM OPERATIONS
    // ========================================================================

    /**
     * Clear system cache
     */
    clearCache: async (): Promise<{ message: string }> => {
      return client.post<{ message: string }>('/api/v2/admin/system/clear-cache')
    },

    /**
     * Run system maintenance
     */
    runMaintenance: async (): Promise<{ message: string }> => {
      return client.post<{ message: string }>('/api/v2/admin/system/maintenance')
    }
  }
}

// Export types
export type AdminApi = ReturnType<typeof createAdminApi>
