/**
 * Flow Engine Core Types
 * Centralized type definitions for the flow engine system
 */

import { FlowType, FlowStatus } from '@/types/api'
import type { MessageType, Flow } from '@/types/api'

// Re-export core types for convenience
export { FlowType, FlowStatus }
export type { MessageType, Flow }

/**
 * FlowNode - Represents a single node in a flow execution graph
 * 
 * Uses discriminated union pattern for type safety. Each node type has specific
 * configuration and behavior. Nodes are connected via the `next` property.
 * 
 * @example
 * ```typescript
 * const messageNode: MessageFlowNode = {
 *   id: 'msg-1',
 *   type: 'message',
 *   config: {
 *     content: 'Hello, how are you?',
 *     message_type: 'text'
 *   },
 *   next: 'condition-1'
 * }
 * ```
 */
export type FlowNode =
  | MessageFlowNode
  | ConditionFlowNode
  | ActionFlowNode
  | DelayFlowNode

/**
 * BaseFlowNode - Common properties for all flow nodes
 */
export interface BaseFlowNode {
  /** Unique identifier for the node */
  id: string
  /** Optional position for visual flow editor */
  position?: { x: number; y: number }
}

/**
 * MessageFlowNode - Sends a message to the patient
 * 
 * @example
 * ```typescript
 * const node: MessageFlowNode = {
 *   id: 'welcome-msg',
 *   type: 'message',
 *   config: {
 *     content: 'Welcome to your treatment!',
 *     message_type: 'text',
 *     ai_instructions: 'Be warm and encouraging'
 *   },
 *   next: 'check-response'
 * }
 * ```
 */
export interface MessageFlowNode extends BaseFlowNode {
  type: 'message'
  config: MessageNodeConfig
  /** ID of the next node to execute */
  next?: string
}

/**
 * ConditionFlowNode - Evaluates a condition and branches accordingly
 * 
 * @example
 * ```typescript
 * const node: ConditionFlowNode = {
 *   id: 'check-age',
 *   type: 'condition',
 *   config: {
 *     field: 'patient.age',
 *     operator: 'greater_than',
 *     value: 18,
 *     branches: {
 *       'true': 'adult-flow',
 *       'false': 'minor-flow'
 *     }
 *   }
 * }
 * ```
 */
export interface ConditionFlowNode extends BaseFlowNode {
  type: 'condition'
  config: ConditionNodeConfig
  /** Array of possible next node IDs based on condition result */
  next?: string[]
}

/**
 * ActionFlowNode - Performs an action (e.g., update database, call API)
 * 
 * @example
 * ```typescript
 * const node: ActionFlowNode = {
 *   id: 'update-status',
 *   type: 'action',
 *   config: {
 *     action_type: 'update_patient',
 *     parameters: {
 *       status: 'active'
 *     }
 *   },
 *   next: 'send-confirmation'
 * }
 * ```
 */
export interface ActionFlowNode extends BaseFlowNode {
  type: 'action'
  config: ActionNodeConfig
  /** ID of the next node to execute */
  next?: string
}

/**
 * DelayFlowNode - Pauses flow execution for a specified duration
 * 
 * @example
 * ```typescript
 * const node: DelayFlowNode = {
 *   id: 'wait-24h',
 *   type: 'delay',
 *   config: {
 *     delay_seconds: 86400  // 24 hours
 *   },
 *   next: 'follow-up-msg'
 * }
 * ```
 */
export interface DelayFlowNode extends BaseFlowNode {
  type: 'delay'
  config: DelayNodeConfig
  /** ID of the next node to execute after delay */
  next?: string
}

/**
 * Flow Node Configuration interfaces
 */
export interface MessageNodeConfig {
  content: string
  message_type: MessageType
  personalization_hints?: string[]
  ai_instructions?: string
  [key: string]: unknown
}

export interface ConditionNodeConfig {
  field: string
  operator: 'equals' | 'not_equals' | 'contains' | 'greater_than' | 'less_than'
  value: unknown
  branches?: Record<string, string>
  [key: string]: unknown
}

export interface ActionNodeConfig {
  action_type: string
  parameters?: Record<string, unknown>
  [key: string]: unknown
}

export interface DelayNodeConfig {
  delay_seconds: number
  delay_until?: string
  [key: string]: unknown
}

/**
 * Generic Flow Node Config for cases where specific type is not known
 */
export interface FlowNodeConfig {
  [key: string]: unknown
}

/**
 * FlowExecutionContext - Maintains state during flow execution
 * 
 * Tracks the current state of a flow as it executes, including which node
 * is currently being processed, variables collected during execution, and
 * a history of all executed steps.
 * 
 * @example
 * ```typescript
 * const context: FlowExecutionContext = {
 *   patient_id: 'patient-123',
 *   flow_id: 'onboarding-flow',
 *   current_node: 'welcome-msg',
 *   variables: {
 *     patient_name: 'John Doe',
 *     enrollment_date: '2024-01-15'
 *   },
 *   history: [],
 *   metadata: {
 *     started_at: '2024-01-15T10:00:00Z'
 *   }
 * }
 * ```
 */
export interface FlowExecutionContext {
  /** ID of the patient for whom the flow is executing */
  patient_id: string
  /** ID of the flow being executed */
  flow_id: string
  /** ID of the currently executing node */
  current_node: string
  /** Variables collected and used during flow execution */
  variables: Record<string, unknown>
  /** History of all executed steps in this flow */
  history: FlowExecutionStep[]
  /** Additional metadata about the execution */
  metadata?: Record<string, unknown>
}

/**
 * FlowExecutionStep - Records a single step in flow execution history
 * 
 * Each step represents the execution of one node in the flow, including
 * the result, any output produced, and timing information.
 * 
 * @example
 * ```typescript
 * const step: FlowExecutionStep = {
 *   node_id: 'welcome-msg',
 *   executed_at: '2024-01-15T10:00:00Z',
 *   result: 'success',
 *   output: {
 *     message_id: 'msg-456',
 *     sent: true
 *   }
 * }
 * ```
 */
export interface FlowExecutionStep {
  /** ID of the node that was executed */
  node_id: string
  /** ISO timestamp when the node was executed */
  executed_at: string
  /** Result of the execution */
  result: 'success' | 'failure' | 'skipped'
  /** Output produced by the node execution */
  output?: unknown
  /** Error message if execution failed */
  error?: string
  /** Additional metadata about the execution */
  metadata?: Record<string, unknown>
}

/**
 * Flow Execution Result - Result of executing a flow node
 */
export interface FlowExecutionResult {
  success: boolean
  next_node?: string | string[]
  output?: unknown
  error?: string
  context_updates?: Partial<FlowExecutionContext>
}

/**
 * Flow Processor Interface - Defines contract for node processors
 */
export interface FlowNodeProcessor<T extends FlowNode = FlowNode> {
  canProcess(node: FlowNode): node is T
  process(node: T, context: FlowExecutionContext): Promise<FlowExecutionResult>
}

/**
 * Condition Evaluation Result
 */
export interface ConditionEvaluationResult {
  passed: boolean
  branch?: string
  reason?: string
}

/**
 * Flow Template (re-export from API types)
 */
export type { FlowTemplate } from '@/types/api'

/**
 * Flow State Machine Types (for state transitions)
 */
export interface FlowTransition {
  from_state: string
  to_state: string
  trigger: string
  conditions?: Array<{
    field: string
    operator: string
    value: unknown
  }>
  actions?: string[]
}

export interface FlowStateMachine {
  states: string[]
  initial_state: string
  transitions: FlowTransition[]
  final_states: string[]
}

/**
 * Type guards for flow nodes
 */
export function isMessageNode(node: FlowNode): node is MessageFlowNode {
  return node.type === 'message'
}

export function isConditionNode(node: FlowNode): node is ConditionFlowNode {
  return node.type === 'condition'
}

export function isActionNode(node: FlowNode): node is ActionFlowNode {
  return node.type === 'action'
}

export function isDelayNode(node: FlowNode): node is DelayFlowNode {
  return node.type === 'delay'
}
