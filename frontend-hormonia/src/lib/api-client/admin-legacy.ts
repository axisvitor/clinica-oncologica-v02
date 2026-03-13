import type { ApiClientCore } from './core'
import type {
  AdminUser,
  CreateUserRequest,
  UpdateUserRequest,
  CreateAdminUserRequest,
  UpdateAdminUserRequest,
  ResetPasswordRequest,
  Role,
  CreateRoleRequest,
  AuditLogEntry,
  AuditLogFilters,
  SystemSettings,
  SystemHealth,
  SystemMetrics,
  SystemStats,
  PaginatedResponse,
  MessageResponse,
} from './types'

export interface LegacyAdminApi {
  users: {
    list: (page?: number, size?: number) => Promise<AdminUser[]>
    get: (userId: string) => Promise<AdminUser>
    create: (data: CreateUserRequest) => Promise<AdminUser>
    update: (userId: string, data: UpdateUserRequest) => Promise<AdminUser>
    delete: (userId: string) => Promise<MessageResponse>
    resetPassword: (userId: string, payload?: ResetPasswordRequest) => Promise<MessageResponse>
    toggleStatus: (userId: string) => Promise<MessageResponse>
  }
  roles: {
    list: () => Promise<Role[]>
    create: (data: CreateRoleRequest) => Promise<Role>
    update: (roleId: string, data: Partial<CreateRoleRequest>) => Promise<Role>
    delete: (roleId: string) => Promise<MessageResponse>
  }
  audit: {
    list: (
      page?: number,
      size?: number,
      filters?: AuditLogFilters
    ) => Promise<PaginatedResponse<AuditLogEntry>>
    get: (auditId: string) => Promise<AuditLogEntry>
    export: (filters?: AuditLogFilters) => Promise<Blob>
  }
  settings: {
    get: () => Promise<SystemSettings>
    update: (data: Partial<SystemSettings>) => Promise<SystemSettings>
    reset: () => Promise<MessageResponse>
  }
  system: {
    getHealth: () => Promise<SystemHealth>
    getMetrics: () => Promise<SystemMetrics>
    systemStats: () => Promise<SystemStats>
    clearCache: () => Promise<MessageResponse>
    runMaintenance: () => Promise<MessageResponse>
  }
}

export function createLegacyAdminApi(client: ApiClientCore): LegacyAdminApi {
  return {
    users: {
      list: async (_page = 1, size = 20) => {
        const params: Record<string, string | number | boolean> = { limit: size }
        const res = await client.get<PaginatedResponse<AdminUser>>('/api/v2/admin/users', params)
        return Array.isArray(res?.data) ? res.data : (res?.items ?? [])
      },

      get: (userId: string) => client.get<AdminUser>(`/api/v2/admin/users/${userId}`),

      create: (data: CreateUserRequest) =>
        client.post<AdminUser, CreateAdminUserRequest>('/api/v2/admin/users', data),

      update: (userId: string, data: UpdateUserRequest) =>
        client.put<AdminUser, UpdateAdminUserRequest>(`/api/v2/admin/users/${userId}`, data),

      delete: (userId: string) => client.delete<MessageResponse>(`/api/v2/admin/users/${userId}`),

      resetPassword: (userId: string, payload?: ResetPasswordRequest) =>
        client.post<MessageResponse>(`/api/v2/admin/users/${userId}/reset-password`, payload ?? {}),

      toggleStatus: (userId: string) =>
        client.post<MessageResponse>(`/api/v2/admin/users/${userId}/deactivate`),
    },

    roles: {
      list: () => client.get<Role[]>('/api/v2/admin/roles'),

      create: (data: CreateRoleRequest) => client.post<Role>('/api/v2/admin/roles', data),

      update: (roleId: string, data: Partial<CreateRoleRequest>) =>
        client.put<Role>(`/api/v2/admin/roles/${roleId}`, data),

      delete: (roleId: string) => client.delete<MessageResponse>(`/api/v2/admin/roles/${roleId}`),
    },

    audit: {
      list: (page = 1, size = 20, filters?: AuditLogFilters) =>
        client.get<PaginatedResponse<AuditLogEntry>>('/api/v2/admin/audit', {
          page,
          size,
          ...filters,
        }),

      get: (auditId: string) => client.get<AuditLogEntry>(`/api/v2/admin/audit/${auditId}`),

      export: async (filters?: AuditLogFilters) => {
        const queryParams = new URLSearchParams(filters as Record<string, string>)
        const response = await fetch(`${client.getBaseURL()}/api/v2/admin/audit/export?${queryParams}`, {
          method: 'GET',
          headers: {
            ...client.getSessionHeaders(),
          },
          credentials: 'include',
        })

        if (!response.ok) {
          throw new Error('Failed to export audit logs')
        }

        return response.blob()
      },
    },

    settings: {
      get: () => client.get<SystemSettings>('/api/v2/admin/settings'),

      update: (data: Partial<SystemSettings>) =>
        client.put<SystemSettings>('/api/v2/admin/settings', data),

      reset: () => client.post<MessageResponse>('/api/v2/admin/settings/reset'),
    },

    system: {
      getHealth: () => client.get<SystemHealth>('/api/v2/admin/system/health'),

      getMetrics: () => client.get<SystemMetrics>('/api/v2/admin/system/metrics'),

      systemStats: () => client.get<SystemStats>('/api/v2/admin/system-stats'),

      clearCache: () => client.post<MessageResponse>('/api/v2/admin/system/clear-cache'),

      runMaintenance: () => client.post<MessageResponse>('/api/v2/admin/system/maintenance'),
    },
  }
}
