import type { ApiClientCore } from './core'
import type {
  AdminUser,
  AdminUserListFilters,
  CreateUserRequest,
  UpdateUserRequest,
  CreateAdminUserRequest,
  UpdateAdminUserRequest,
  ResetPasswordRequest,
  UserActivityEntry,
  UserActivityFilters,
  PaginatedResponse,
  MessageResponse,
} from './types'

export interface AdminUsersListOptions extends AdminUserListFilters {
  page?: number
  size?: number
}

export interface AdminUserActivityOptions extends UserActivityFilters {
  page?: number
  size?: number
}

export interface AdminUsersApi {
  list: (options?: AdminUsersListOptions) => Promise<PaginatedResponse<AdminUser>>
  get: (userId: string) => Promise<AdminUser>
  create: (data: CreateUserRequest) => Promise<AdminUser>
  update: (userId: string, data: UpdateUserRequest) => Promise<AdminUser>
  delete: (userId: string) => Promise<MessageResponse>
  activate: (userId: string) => Promise<MessageResponse>
  deactivate: (userId: string) => Promise<MessageResponse>
  updatePermissions: (userId: string, permissions: string[]) => Promise<MessageResponse>
  updateRole: (userId: string, role: string) => Promise<MessageResponse>
  getActivity: (
    userId: string,
    options?: AdminUserActivityOptions
  ) => Promise<PaginatedResponse<UserActivityEntry>>
  resetPassword: (userId: string, payload: ResetPasswordRequest) => Promise<MessageResponse>
  unlock: (userId: string) => Promise<MessageResponse>
  enable2FA: (userId: string) => Promise<MessageResponse>
  disable2FA: (userId: string) => Promise<MessageResponse>
}

export function createAdminUsersApi(client: ApiClientCore): AdminUsersApi {
  return {
    list: (options: AdminUsersListOptions = {}) => {
      const { page = 1, size = 20, ...filters } = options
      return client.get<PaginatedResponse<AdminUser>>('/api/v2/admin/users', {
        page,
        size,
        ...filters,
      })
    },

    get: (userId: string) => client.get<AdminUser>(`/api/v2/admin/users/${userId}`),

    create: (data: CreateUserRequest) =>
      client.post<AdminUser, CreateAdminUserRequest>('/api/v2/admin/users', data),

    update: (userId: string, data: UpdateUserRequest) =>
      client.put<AdminUser, UpdateAdminUserRequest>(`/api/v2/admin/users/${userId}`, data),

    delete: (userId: string) => client.delete<MessageResponse>(`/api/v2/admin/users/${userId}`),

    activate: (userId: string) => client.post<MessageResponse>(`/api/v2/admin/users/${userId}/activate`),

    deactivate: (userId: string) =>
      client.post<MessageResponse>(`/api/v2/admin/users/${userId}/deactivate`),

    updatePermissions: (userId: string, permissions: string[]) =>
      client.put<MessageResponse>(`/api/v2/admin/users/${userId}/permissions`, { permissions }),

    updateRole: (userId: string, role: string) =>
      client.put<MessageResponse>(`/api/v2/admin/users/${userId}/role`, { role }),

    getActivity: (userId: string, options: AdminUserActivityOptions = {}) => {
      const { page = 1, size = 20, ...filters } = options
      return client.get<PaginatedResponse<UserActivityEntry>>(
        `/api/v2/admin/users/${userId}/activity`,
        { page, size, ...filters }
      )
    },

    resetPassword: (userId: string, payload: ResetPasswordRequest) =>
      client.post<MessageResponse>(`/api/v2/admin/users/${userId}/reset-password`, {
        new_password: payload.new_password,
        force_change: payload.force_change ?? false,
      }),

    unlock: (userId: string) => client.post<MessageResponse>(`/api/v2/admin/users/${userId}/unlock`),

    enable2FA: (userId: string) =>
      client.post<MessageResponse>(`/api/v2/admin/users/${userId}/2fa/enable`),

    disable2FA: (userId: string) =>
      client.post<MessageResponse>(`/api/v2/admin/users/${userId}/2fa/disable`),
  }
}
