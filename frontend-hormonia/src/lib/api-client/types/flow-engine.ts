import type { Condition } from './flows'

export enum MessageType {
  TEXT = 'text',
  IMAGE = 'image',
  AUDIO = 'audio',
  VIDEO = 'video',
  DOCUMENT = 'document',
  INTERACTIVE = 'interactive',
  TEMPLATE = 'template',
}

export interface InboundMessage {
  id: string
  content: string
  sender_id: string
  timestamp: string
  type?: MessageType
  metadata?: Record<string, unknown>
}

export type FlowEventType =
  | 'flow_started'
  | 'flow_paused'
  | 'flow_resumed'
  | 'flow_advanced'
  | 'flow_completed'
  | 'message_sent'
  | 'response_received'

export interface FlowEvent {
  type: FlowEventType
  patient_id: string
  flow_id: string
  data?: Record<string, unknown>
  timestamp: string
}

export interface FlowStateTransition {
  from_state: string
  to_state: string
  trigger: string
  conditions?: Condition[]
}

export interface FlowStateMachine {
  states: string[]
  initial_state: string
  transitions: FlowStateTransition[]
  final_states: string[]
}
