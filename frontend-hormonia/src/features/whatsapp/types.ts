// WhatsApp Integration Types

export interface WhatsAppInstance {
  name: string
  status: 'connected' | 'disconnected' | 'connecting' | 'error'
  qr_code?: string
  phone_number?: string
  profile_name?: string
  created_at: string
  last_seen?: string
}

export interface WhatsAppMessage {
  id: string
  instance_name: string
  chat_id: string
  recipient_id: string
  message_type: 'text' | 'image' | 'document' | 'audio'
  content: string
  media_url?: string
  status: 'pending' | 'sent' | 'delivered' | 'read' | 'failed'
  sent_at?: string
  created_at: string
  error_message?: string
}

export interface QueueStats {
  pending: number
  scheduled: number
  retry_scheduled: number
  dead_letter: number
}

export interface MessageStats {
  total: number
  sent: number
  delivered: number
  read: number
  failed: number
  pending: number
}

export interface SendMessageData {
  instance_name: string
  to: string
  message_type: 'text' | 'image' | 'audio' | 'document'
  text?: string
  media_file?: File
  media_caption?: string
}

export interface MessageFormState {
  to: string
  text: string
  mediaFile: File | null
  mediaCaption: string
}
