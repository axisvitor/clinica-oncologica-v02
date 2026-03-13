import type { SearchFilters } from './common'

export interface Message {
  id: string
  patient_id: string
  content: string
  direction: 'inbound' | 'outbound'
  type?: string
  status: 'pending' | 'sent' | 'delivered' | 'failed' | 'read'
  scheduled_for?: string
  sent_at?: string
  delivered_at?: string
  read_at?: string
  error_message?: string
  metadata?: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface MessageListFilters extends SearchFilters {
  patient_id?: string
  direction?: 'inbound' | 'outbound'
  status?: Message['status']
  type?: string
  start_date?: string
  end_date?: string
}

export interface SendMessageRequest {
  patient_id: string
  content: string
  type?: string
  scheduled_for?: string
  metadata?: Record<string, unknown>
}

export interface BulkMessageRequest {
  patient_ids: string[]
  content: string
  type?: string
  scheduled_for?: string
}

export interface BulkMessageResponse {
  success: number
  failed: number
  messages: Message[]
  errors?: Array<{ patient_id: string; error: string }>
}

export interface ConversationResponse {
  patient_id: string
  messages: Message[]
  total: number
}
