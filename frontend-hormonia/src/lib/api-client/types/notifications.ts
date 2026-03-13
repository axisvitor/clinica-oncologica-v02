export interface Notification {
  id: string
  type: string
  title: string
  message: string
  read: boolean
  created_at: string
  metadata?: Record<string, unknown>
}

export interface NotificationListResponse {
  notifications: Notification[]
  items: Notification[]
  total: number
  unread_count: number
}
