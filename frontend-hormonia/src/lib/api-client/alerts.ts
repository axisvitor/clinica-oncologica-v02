import type { ApiClientCore } from './core'
import type {
  Alert,
  AlertListFilters,
  CreateAlertRequest,
  UpdateAlertRequest,
  UnreadCountResponse,
  PaginatedResponse,
  MessageResponse,
} from './types'

export interface AlertsListOptions extends AlertListFilters {
  page?: number
  size?: number
  cursor?: string
  limit?: number
}

export interface AlertsApi {
  list: (options?: AlertsListOptions) => Promise<PaginatedResponse<Alert>>
  get: (alertId: string) => Promise<Alert>
  create: (data: CreateAlertRequest) => Promise<Alert>
  update: (alertId: string, data: UpdateAlertRequest) => Promise<Alert>
  delete: (alertId: string) => Promise<MessageResponse>
  markAsRead: (alertId: string) => Promise<MessageResponse>
  markAllAsRead: () => Promise<MessageResponse>
  getUnreadCount: () => Promise<UnreadCountResponse>
  acknowledge: (alertId: string) => Promise<MessageResponse>
  resolve: (alertId: string) => Promise<MessageResponse>
}

export function createAlertsApi(client: ApiClientCore): AlertsApi {
  return {
    list: async (options: AlertsListOptions = {}) => {
      const { size, cursor, limit, ...filters } = options
      const effLimit = limit ?? size ?? 20
      const params: Record<string, string | number | boolean> = {
        limit: effLimit,
        ...(cursor ? { cursor } : {}),
        ...filters,
      }
      const res = await client.get<PaginatedResponse<Alert>>('/api/v2/alerts', params)
      const items = Array.isArray(res?.data) ? res.data : (res?.items ?? [])
      return {
        data: items,
        items,
        total: res?.total ?? 0,
        has_more: res?.has_more,
        next_cursor: res?.next_cursor,
      }
    },

    get: (alertId: string) => client.get<Alert>(`/api/v2/alerts/${alertId}`),

    create: (data: CreateAlertRequest) => client.post<Alert>('/api/v2/alerts', data),

    update: (alertId: string, data: UpdateAlertRequest) =>
      client.patch<Alert>(`/api/v2/alerts/${alertId}`, data),

    delete: (alertId: string) => client.delete<MessageResponse>(`/api/v2/alerts/${alertId}`),

    markAsRead: (alertId: string) =>
      client.patch<MessageResponse>(`/api/v2/alerts/${alertId}/read`, {}),

    markAllAsRead: () => client.post<MessageResponse>('/api/v2/alerts/read-all'),

    getUnreadCount: () => client.get<UnreadCountResponse>('/api/v2/alerts/unread-count'),

    acknowledge: (alertId: string) =>
      client.patch<MessageResponse>(`/api/v2/alerts/${alertId}/read`, {}),

    resolve: (alertId: string) =>
      client.patch<MessageResponse>(`/api/v2/alerts/${alertId}/read`, { notes: 'Resolved' }),
  }
}
