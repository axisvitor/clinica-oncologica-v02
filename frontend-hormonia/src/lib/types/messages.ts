// Message types for the application
export enum MessageType {
  TEXT = 'text',
  TEMPLATE = 'template',
  INTERACTIVE = 'interactive',
  EDUCATIONAL = 'educational'
}

export interface Message {
  id: string
  patient_id: string
  content: string
  type: MessageType
  status: 'sent' | 'delivered' | 'failed' | 'pending'
  scheduled_for?: string
  created_at: string
  updated_at: string
}