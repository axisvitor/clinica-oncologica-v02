// Shared Message Types - Messaging domain types for frontend and backend

/**
 * Message direction - matches message_direction type
 */
export enum MessageDirection {
    INBOUND = 'inbound',
    OUTBOUND = 'outbound'
}

/**
 * Message status - matches message_status type
 */
export enum MessageStatus {
    PENDING = 'pending',
    SCHEDULED = 'scheduled',
    SENDING = 'sending',
    SENT = 'sent',
    DELIVERED = 'delivered',
    READ = 'read',
    FAILED = 'failed'
}

/**
 * Delivery status - matches deliverystatus type
 */
export enum DeliveryStatus {
    SCHEDULED = 'scheduled',
    QUEUED = 'queued',
    SENDING = 'sending',
    SENT = 'sent',
    DELIVERED = 'delivered',
    READ = 'read',
    FAILED = 'failed',
    CANCELLED = 'cancelled'
}

/**
 * Message priority - matches message_priority type
 */
export enum MessagePriority {
    CRITICAL = 'critical',
    HIGH = 'high',
    NORMAL = 'normal',
    LOW = 'low'
}

/**
 * Message type - matches message_type enum
 */
export enum MessageType {
    TEXT = 'text',
    BUTTON = 'button',
    LIST = 'list',
    MEDIA = 'media',
    LOCATION = 'location',
    QUIZ_INTRO = 'quiz_intro',
    QUIZ_QUESTION = 'quiz_question',
    QUIZ_ENCOURAGEMENT = 'quiz_encouragement',
    QUIZ_COMPLETION = 'quiz_completion',
    MONTHLY_QUIZ_LINK = 'monthly_quiz_link',
    MONTHLY_QUIZ_REMINDER = 'monthly_quiz_reminder',
    MONTHLY_QUIZ_EXPIRED = 'monthly_quiz_expired',
    MONTHLY_QUIZ_COMPLETED = 'monthly_quiz_completed'
}

/**
 * Core message interface - matches messages table
 */
export interface Message {
    id: string
    patient_id: string
    direction: MessageDirection | string
    type: MessageType | string
    content: string
    message_metadata?: Record<string, unknown>
    whatsapp_id?: string | null
    status: MessageStatus | string
    delivery_status?: DeliveryStatus | string
    priority?: MessagePriority | string
    scheduled_for?: string | null
    sent_at?: string | null
    delivered_at?: string | null
    read_at?: string | null
    retry_count?: number
    last_retry_at?: string | null
    failure_reason?: string | null
    next_retry_at?: string | null
    idempotency_key?: string | null
    created_at: string
    updated_at: string
}

/**
 * Send message request
 */
export interface SendMessageRequest {
    patient_id: string
    content: string
    type?: MessageType | string
    priority?: MessagePriority | string
    scheduled_for?: string
    metadata?: Record<string, unknown>
}

/**
 * Bulk message request
 */
export interface BulkMessageRequest {
    patient_ids: string[]
    content: string
    type?: MessageType | string
    scheduled_for?: string
}

/**
 * Bulk message response
 */
export interface BulkMessageResponse {
    success: number
    failed: number
    messages: Message[]
    errors?: Array<{ patient_id: string; error: string }>
}

/**
 * Conversation response
 */
export interface ConversationResponse {
    patient_id: string
    messages: Message[]
    total: number
}

/**
 * Message list filters
 */
export interface MessageListFilters {
    patient_id?: string
    direction?: MessageDirection | string
    status?: MessageStatus | string
    type?: MessageType | string
    priority?: MessagePriority | string
    start_date?: string
    end_date?: string
    search?: string
    page?: number
    size?: number
    limit?: number
    cursor?: string
}
