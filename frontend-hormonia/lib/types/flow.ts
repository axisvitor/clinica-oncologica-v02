/**
 * Legacy Flow Types - Deprecated, use types from /types/api.ts instead
 * @deprecated Import from '/types/api' for the latest type definitions
 */

// Re-export flow-related types from the centralized API types module
export type {
  Flow,
  FlowType,
  FlowStatus as ApiFlowStatus,
  Message,
  MessageType as ApiMessageType,
  MessageDirection as ApiMessageDirection,
  MessageStatus as ApiMessageStatus
} from '../../types/api'

export enum ResponseType {
  TEXT = 'text',
  BUTTON = 'button',
  QUICK_REPLY = 'quick_reply',
  LIST = 'list'
}

// Export missing types for backward compatibility
export interface InboundMessage {
  id: string
  content: string
  patient_id: string
  timestamp: string
  message_type: import('../../types/api').MessageType
  metadata?: Record<string, unknown>
}

export interface ResponseResult {
  response_type: ResponseType
  extracted_data: Record<string, unknown>
  sentiment_score: number
  requires_attention: boolean
  follow_up_actions: FollowUpAction[]
}

export interface FlowEvent {
  type: string
  patient_id: string
  data: unknown
  timestamp: string
}

export interface InteractiveElements {
  buttons?: Array<{ id: string; text: string; action: string }>
  quick_replies?: string[]
  list_items?: Array<{ id: string; title: string; description?: string }>
}

export interface Condition {
  field: string
  operator: 'equals' | 'contains' | 'greater_than' | 'less_than'
  value: unknown
}

export interface FollowUpAction {
  intent: string
  delay_seconds: number
  ai_instructions?: string
  conditions?: Condition[]
}

// Legacy flow interfaces - use types from /types/api.ts instead
export type { Flow as FlowState } from '../../types/api'

// All detailed flow interfaces have been moved to /types/api.ts and /types/flow-designer.ts
// Please import from those modules for the latest type definitions

// Legacy type aliases for backward compatibility
export type MessageTemplate = {
  id: string
  day: number
  content: string
  message_type: import('../../types/api').MessageType
  interactive_elements?: InteractiveElements
  conditions?: Condition[]
  personalization_hints: string[]
  ai_instructions?: string
  follow_up?: unknown[]
}

export type FlowTemplate = {
  id: string
  flow_type: import('../../types/api').FlowType
  name: string
  description: string
  messages: Record<number, MessageTemplate>
  metadata: Record<string, unknown>
  humanization_level: 'high' | 'medium' | 'low'
}

// Re-export flow analytics from centralized types
export type { FlowMetrics as FlowAnalytics } from '../../types/api'

// Re-export FlowTransition and FlowStateMachine from the main flow types
export type {
  FlowTransition,
  FlowStateMachine
} from '../../src/lib/types/flow'
