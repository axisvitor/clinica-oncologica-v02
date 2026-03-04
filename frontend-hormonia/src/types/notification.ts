/**
 * Notification Types
 */

export interface Notification {
  id: string
  title: string
  message: string
  type: 'info' | 'success' | 'warning' | 'error' | 'alert' | 'message' | 'report' | 'quiz'
  read?: boolean
  is_read?: boolean
  created_at: string
  metadata?: Record<string, unknown>
}

export interface NotificationListResponse {
  items: Notification[]
  total: number
  unread_count: number
}
