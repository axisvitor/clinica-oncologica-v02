// Flow System Types - Centralized flow-related type definitions
// Import core types from centralized API module
import {
  FlowType,
  FlowStatus,
  MessageType,
  MessageDirection,
  MessageStatus,
  type Flow
} from '@/types/api'

// Re-export core types for convenience (enums as values, types as types)
export {
  FlowType,
  FlowStatus,
  MessageType,
  MessageDirection,
  MessageStatus
}
export type { Flow } from '@/types/api'

// Legacy alias for backwards compatibility
export type FlowState = Flow

export enum ResponseType {
  TEXT = 'text',
  BUTTON = 'button',
  QUICK_REPLY = 'quick_reply',
  LIST = 'list'
}

// Core Flow Engine Interfaces
export interface MessageTemplate {
  id: string
  day: number
  content: string
  message_type: MessageType
  interactive_elements?: InteractiveElements
  conditions?: Condition[]
  personalization_hints: string[]
  ai_instructions?: string
  follow_up?: FollowUpAction[]
}

export interface FlowTemplate {
  id: string
  flow_type: FlowType
  name: string
  description: string
  messages: Record<number, MessageTemplate>
  metadata: Record<string, any>
  humanization_level: 'high' | 'medium' | 'low'
}

export interface InteractiveElements {
  buttons?: Array<{ id: string; text: string; action: string }>
  quick_replies?: string[]
  list_items?: Array<{ id: string; title: string; description?: string }>
}

export interface InteractiveOption {
  id: string
  title: string
  description?: string
  payload?: string
}

export interface Condition {
  field: string
  operator: 'equals' | 'not_equals' | 'contains' | 'greater_than' | 'less_than'
  value: any
}

export interface FollowUpAction {
  intent: string
  delay_seconds: number
  ai_instructions?: string
  conditions?: Condition[]
}

// Response Processing
export interface InboundMessage {
  id: string
  patient_id: string
  content: string
  message_type: MessageType
  timestamp: string
  metadata?: Record<string, any>
}

export interface ResponseResult {
  response_type: ResponseType
  extracted_data: Record<string, any>
  sentiment_score: number
  requires_attention: boolean
  follow_up_actions: FollowUpAction[]
}

export interface StructuredResponse {
  intent: string
  entities: Record<string, any>
  confidence: number
  raw_text: string
}

// Flow Analytics
export interface FlowAnalytics {
  total_active_flows: number
  completion_rate: number
  engagement_rate: number
  average_response_time: number
  flows_by_type: Record<FlowType, number>
  daily_metrics: DailyMetric[]
}

export interface DailyMetric {
  date: string
  messages_sent: number
  responses_received: number
  new_enrollments: number
  completions: number
}

// Flow Engine Events
export interface FlowEvent {
  type: 'flow_started' | 'flow_paused' | 'flow_resumed' | 'flow_completed' | 'message_sent' | 'response_received'
  patient_id: string
  flow_id: string
  data?: Record<string, any>
  timestamp: string
}

// State Machine Transitions - Exported for FlowEngine usage
export interface FlowTransition {
  from_state: string
  to_state: string
  trigger: string
  conditions?: Condition[]
  actions?: string[]
}

export interface FlowStateMachine {
  states: string[]
  initial_state: string
  transitions: FlowTransition[]
  final_states: string[]
}

// Note: FlowTransition and FlowStateMachine are already exported above (lines 134-147)
// No need for duplicate re-export

// Flow Designer interface for design mode
export interface FlowDesigner {
  id: string
  name: string
  description: string
  flow_type: FlowType
  status: FlowStatus
  nodes: FlowNode[]
  connections: FlowConnection[]
  metadata?: Record<string, any>
  created_at: string
  updated_at: string
}

// Flow Node interface
export interface FlowNode {
  id: string
  type: 'message' | 'condition' | 'action' | 'delay'
  position: { x: number; y: number }
  data: {
    label: string
    content?: string
    conditions?: Condition[]
    actions?: string[]
    delay?: number
  }
}

// Flow Connection interface
export interface FlowConnection {
  id: string
  source: string
  target: string
  sourceHandle?: string
  targetHandle?: string
  label?: string
  conditions?: Condition[]
}

// Flow Validation Result interface
export interface FlowValidationResult {
  isValid: boolean
  errors: FlowValidationError[]
  warnings: FlowValidationWarning[]
}

export interface FlowValidationError {
  nodeId?: string
  connectionId?: string
  message: string
  type: 'missing_connection' | 'invalid_condition' | 'circular_dependency' | 'invalid_node_data'
}

export interface FlowValidationWarning {
  nodeId?: string
  connectionId?: string
  message: string
  type: 'unreachable_node' | 'unused_condition' | 'performance_warning'
}