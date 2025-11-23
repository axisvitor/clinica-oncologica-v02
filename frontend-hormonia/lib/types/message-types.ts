// Basic message type definitions
export interface MessageBase {
  id: string
  content: string
  timestamp: string
  status: 'sent' | 'delivered' | 'read' | 'failed'
}

export interface SendMessageRequest {
  patient_id: string
  content: string
  type?: string
  scheduled_for?: string
}

export interface MessageResponse {
  id: string
  content: string
  status: string
  timestamp: string
}