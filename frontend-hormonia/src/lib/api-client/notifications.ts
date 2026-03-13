import type { ApiClientCore } from './core'
import type { NotificationListResponse } from './types'

export interface NotificationsApi {
  list: () => Promise<NotificationListResponse>
}

export function createNotificationsApi(client: ApiClientCore): NotificationsApi {
  return {
    list: () => client.get<NotificationListResponse>('/api/v2/notifications'),
  }
}
