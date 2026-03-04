// Flow Designer Types - Centralized definitions for the visual flow designer

export interface FlowNode {
  id: string
  type: FlowNodeType
  position: { x: number; y: number }
  data: FlowNodeData
  selected?: boolean
  dragging?: boolean
}

export enum FlowNodeType {
  START = 'start',
  MESSAGE = 'message',
  CONDITION = 'condition',
  DELAY = 'delay',
  ACTION = 'action',
  END = 'end',
  AI_RESPONSE = 'ai_response',
  QUIZ = 'quiz',
  WEBHOOK = 'webhook',
}

export interface FlowNodeData {
  label: string
  description?: string
  config: Record<string, unknown>
  validation?: ValidationRule[]
}

export interface FlowConnection {
  id: string
  source: string
  target: string
  sourceHandle?: string
  targetHandle?: string
  label?: string
  condition?: string
  animated?: boolean
}

export interface FlowDesign {
  id: string
  name: string
  description: string
  version: string
  nodes: FlowNode[]
  connections: FlowConnection[]
  variables: FlowVariable[]
  metadata: FlowMetadata
  created_at: string
  updated_at: string
}

export interface FlowVariable {
  id: string
  name: string
  type: 'string' | 'number' | 'boolean' | 'date' | 'object'
  default_value?: unknown
  description?: string
  required?: boolean
}

export interface FlowMetadata {
  author: string
  tags: string[]
  category: string
  estimated_duration?: number
  target_audience?: string[]
  complexity_level: 'simple' | 'medium' | 'complex'
}

export interface ValidationRule {
  field: string
  rule: 'required' | 'min_length' | 'max_length' | 'pattern' | 'custom'
  value?: unknown
  message: string
}

// Node-specific configurations
export interface MessageNodeConfig {
  content: string
  message_type: 'text' | 'image' | 'video' | 'audio' | 'document'
  personalization_hints?: string[]
  ai_instructions?: string
  delay_before?: number
  delay_after?: number
  media_url?: string
  interactive_elements?: InteractiveElements
}

export interface ConditionNodeConfig {
  conditions: ConditionRule[]
  operator: 'AND' | 'OR'
  default_path?: string
}

export interface ConditionRule {
  variable: string
  operator: 'equals' | 'not_equals' | 'contains' | 'greater_than' | 'less_than' | 'exists'
  value: unknown
  label?: string
}

export interface DelayNodeConfig {
  duration: number
  unit: 'seconds' | 'minutes' | 'hours' | 'days'
  description?: string
}

export interface ActionNodeConfig {
  action_type:
    | 'set_variable'
    | 'send_notification'
    | 'create_task'
    | 'update_patient'
    | 'trigger_webhook'
  parameters: Record<string, unknown>
  description?: string
}

export interface AIResponseNodeConfig {
  prompt_template: string
  context_variables: string[]
  response_format: 'text' | 'json'
  max_tokens?: number
  temperature?: number
  fallback_message?: string
}

export interface QuizNodeConfig {
  quiz_id: string
  questions: QuizQuestion[]
  scoring_method: 'points' | 'percentage' | 'pass_fail'
  pass_threshold?: number
  results_variable?: string
}

export interface QuizQuestion {
  id: string
  question: string
  type: 'multiple_choice' | 'single_choice' | 'text' | 'scale'
  options?: QuizOption[]
  required?: boolean
  points?: number
}

export interface QuizOption {
  id: string
  text: string
  value: unknown
  points?: number
}

export interface WebhookNodeConfig {
  url: string
  method: 'GET' | 'POST' | 'PUT' | 'DELETE'
  headers?: Record<string, string>
  body?: string
  response_variable?: string
  timeout?: number
  retry_count?: number
}

export interface InteractiveElements {
  type: 'buttons' | 'quick_reply' | 'list' | 'carousel'
  items: InteractiveItem[]
}

export interface InteractiveItem {
  id: string
  title: string
  description?: string
  image_url?: string
  action: InteractiveAction
}

export interface InteractiveAction {
  type: 'postback' | 'url' | 'phone' | 'share'
  value: string
  label?: string
}

// Designer State
export interface FlowDesignerState {
  design: FlowDesign
  selectedNodes: string[]
  selectedConnections: string[]
  clipboard: ClipboardItem[]
  history: HistoryItem[]
  historyIndex: number
  zoom: number
  pan: { x: number; y: number }
  mode: DesignerMode
  isModified: boolean
}

export enum DesignerMode {
  SELECT = 'select',
  CONNECT = 'connect',
  PAN = 'pan',
}

export interface ClipboardItem {
  type: 'node' | 'connection'
  data: FlowNode | FlowConnection
}

export interface HistoryItem {
  action: string
  timestamp: number
  data: unknown
  description: string
}

// Flow Testing
export interface FlowTestSession {
  id: string
  design_id: string
  current_node: string
  variables: Record<string, unknown>
  execution_log: FlowExecutionStep[]
  status: 'running' | 'completed' | 'error' | 'paused'
  started_at: string
  completed_at?: string
}

export interface FlowExecutionStep {
  id: string
  node_id: string
  timestamp: string
  input?: unknown
  output?: unknown
  duration_ms: number
  status: 'success' | 'error' | 'skipped'
  error_message?: string
}

// Flow Validation
export interface FlowValidationResult {
  isValid: boolean
  errors: FlowValidationError[]
  warnings: FlowValidationWarning[]
}

export interface FlowValidationError {
  id: string
  type: 'missing_connection' | 'invalid_config' | 'circular_dependency' | 'unreachable_node'
  node_id?: string
  connection_id?: string
  message: string
  severity: 'error' | 'warning'
}

export interface FlowValidationWarning {
  id: string
  type: 'performance' | 'best_practice' | 'accessibility'
  node_id?: string
  message: string
  suggestion?: string
}

// Export/Import
export interface FlowExportOptions {
  format: 'json' | 'yaml' | 'xml'
  include_metadata: boolean
  include_test_data: boolean
  minify: boolean
}

export interface FlowImportResult {
  success: boolean
  design?: FlowDesign
  errors?: string[]
  warnings?: string[]
}

// Additional exports for chart compatibility
export interface ChartData {
  [key: string]: unknown
}

export interface TreatmentType {
  id: string
  name: string
  description?: string
}
