// Flow System Types - Centralized flow-related type definitions
// Import core types from centralized API module
import {
  FlowType,
  FlowStatus,
  MessageType,
  MessageDirection,
  MessageStatus,
  ResponseType,
  Condition,
  InteractiveElements,
  FollowUpAction,
  MessageTemplate,
  ResponseResult,
  FlowTemplate,
  Flow,
  FlowState,
  DailyMetric,
  FlowAnalytics
} from '@/types/api'

// Re-export core types for convenience
export {
  FlowType,
  FlowStatus,
  MessageType,
  MessageDirection,
  MessageStatus,
  ResponseType
}

export type {
  Condition,
  InteractiveElements,
  FollowUpAction,
  MessageTemplate,
  ResponseResult,
  FlowTemplate,
  Flow,
  FlowState,
  DailyMetric,
  FlowAnalytics
}

// Local types that are not in API client types yet (or specific to frontend logic)

export interface InteractiveOption {
  id: string
  title: string
  description?: string
  payload?: string
}

// Response Processing
export interface InboundMessage {
  id: string
  patient_id: string
  content: string
  message_type: MessageType
  timestamp: string
  metadata?: Record<string, unknown>
}

export interface StructuredResponse {
  intent: string
  entities: Record<string, unknown>
  confidence: number
  raw_text: string
}

// Flow Engine Events
export interface FlowEvent {
  type: 'flow_started' | 'flow_paused' | 'flow_resumed' | 'flow_completed' | 'message_sent' | 'response_received' | 'flow_advanced'
  patient_id: string
  flow_id: string
  data?: Record<string, unknown>
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

// Flow Designer interface for design mode
export interface FlowDesigner {
  id: string
  name: string
  description: string
  flow_type: FlowType
  status: FlowStatus
  nodes: FlowNode[]
  connections: FlowConnection[]
  metadata?: Record<string, unknown>
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