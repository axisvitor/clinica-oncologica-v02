/**
 * Message Types
 *
 * Type definitions for message-related functionality.
 */

/**
 * Message type categories (enum-like object for runtime usage)
 */
export const MessageType = {
  TEXT: 'text',
  TEMPLATE: 'template',
  INTERACTIVE: 'interactive',
  NOTIFICATION: 'notification',
  QUIZ: 'quiz',
  REMINDER: 'reminder',
  WELCOME: 'welcome',
  FOLLOW_UP: 'follow_up',
  SYSTEM: 'system',
} as const;

/**
 * Message type union for type checking
 */
export type MessageType = (typeof MessageType)[keyof typeof MessageType];

/**
 * Message direction enum
 */
export const MessageDirection = {
  INBOUND: 'inbound',
  OUTBOUND: 'outbound',
} as const;

export type MessageDirection = (typeof MessageDirection)[keyof typeof MessageDirection];

/**
 * Message status enum
 */
export const MessageStatus = {
  PENDING: 'pending',
  SENT: 'sent',
  DELIVERED: 'delivered',
  FAILED: 'failed',
  READ: 'read',
} as const;

export type MessageStatus = (typeof MessageStatus)[keyof typeof MessageStatus];

/**
 * Extended message interface with type information
 */
export interface TypedMessage {
  id: string;
  patient_id: string;
  content: string;
  direction: MessageDirection;
  type: MessageType;
  status: MessageStatus;
  scheduled_for?: string;
  sent_at?: string;
  delivered_at?: string;
  read_at?: string;
  error_message?: string;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}
