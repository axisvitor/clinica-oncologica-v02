/**
 * API Types Re-exports - Centralized API client and response types
 * Re-exports all types from the main types directory for compatibility
 *
 * @note This file maintains compatibility with existing imports while
 * redirecting to the centralized type definitions in /types/
 */

// ============================================================================
// CORE API TYPES RE-EXPORTS
// ============================================================================

// Re-export all types from the centralized API types modules
export * from '@/types/api'
// Export specific types from shared to avoid conflicts (e.g., Status is already in api)
export type {
  UserRole,
  BaseEntity,
  SoftDeletableEntity,
  ListQueryParams,
  NotificationType,
  LoadingState,
  ValidationError,
  AuditMetadata
} from '@/types/shared'
export * from '@/lib/types/websocket'

// Note: Core types are re-exported via the wildcard export above

// Explicit exports for commonly used types to ensure availability
export type {
  // Core domain entities
  Patient,
  Message,
  Flow,
  Alert,
  Report,
  QuizTemplate,
  QuizSession,
  AIInsight,
  AIChatMessage,
  ChatSession,

  // User and auth types (using actual exports)
  // User,
  // AuthTokens,
  // LoginResponse,
  // LoginCredentials,

  // Analytics and metrics
  DashboardAnalytics,
  EngagementMetrics,
  FlowMetrics,
  ActivityItem,

  // Shared base types (re-exported from individual files)
  // PaginatedResponse,
  // ApiResponse,
  // ApiErrorResponse,
  // BaseEntity,
  // SoftDeletableEntity,
  // QueryParams,

  // Enums (re-exported via wildcard)
  // PatientStatus,
  // MessageDirection,
  // MessageType,
  // MessageStatus,
  // FlowType,
  // FlowStatus,
  // AlertType,
  // ReportType,
  // ReportStatus,
  // QuestionType,
  // ScoringMethod,
  // QuizSessionStatus,
  // Priority,
  // Status,
  // UserRole,

  // Request/Response types
  PatientQueryParams,
  MessageQueryParams,
  AlertQueryParams,
  ReportQueryParams,
  CreatePatientRequest,
  UpdatePatientRequest,
  SendMessageRequest,
  StartFlowRequest,
  CreateAlertRequest,
  GenerateReportRequest,
  BulkMessageRequest,

  // API Client interface
  ApiClient,

  // Flow templates
  FlowTemplate,
  FlowStep,
  CreateFlowTemplateRequest,
  UpdateFlowTemplateRequest
} from '@/types/api'

export type {
  // WebSocket types
  WebSocketMessage,
  WebSocketEventType,
  WebSocketConnectionState,
  WebSocketConfig,

  // Event data types
  PatientEventData,
  MessageEventData,
  QuizEventData,
  FlowEventData,
  AlertEventData,
  ReportEventData,
  SystemEventData,

  // WebSocket handlers and subscriptions
  WebSocketEventHandler,
  UseWebSocketReturn,
  EventSubscription as WebSocketSubscription
} from '@/lib/types/websocket'

// ============================================================================
// BACKWARDS COMPATIBILITY TYPES
// ============================================================================

// These types are maintained for backwards compatibility with existing code
// New code should import directly from /types/ modules

// Note: PaginatedResponse is re-exported from shared types above

// Legacy response types - use ApiErrorResponse and ApiResponse from shared types
/** @deprecated Use ApiErrorResponse from shared types */
export interface ErrorResponse {
  readonly error: string
  readonly message: string
  readonly status_code: number
  readonly details?: Record<string, any>
}

/** @deprecated Use ApiResponse from shared types */
export interface SuccessResponse {
  readonly success: boolean
  readonly message?: string
  readonly data?: any
}

// ============================================================================
// ADDITIONAL LEGACY COMPATIBILITY
// ============================================================================

// WebSocket types are properly exported above from websocket module
// Quiz types are exported from the main api module

// Platform Sync Types
export interface PlatformSyncPatientRecord {
  patient_id: string
  interactions: Array<Record<string, any>>
}

export interface AuditEntry {
  entity_type: string
  entity_id: string
  action: string
  changes: Record<string, any>
  user_id?: string
  source_system?: string
}

export interface SyncStatus {
  patient_sync_queue_depth: number
  audit_sync_queue_depth: number
  last_sync_time: string | null
  sync_lag_minutes: number | null
  status: 'healthy' | 'lagging'
}

export interface ConsistencyReport {
  timestamp: string
  issues_found: number
  recommendations: string[]
  details: Record<string, any>
}

// Monitoring Types
export interface SystemHealth {
  status: 'healthy' | 'warning' | 'critical'
  components: Array<{
    name: string
    status: 'up' | 'down' | 'degraded'
    last_check: string
    details?: Record<string, any>
  }>
  metrics: Record<string, number>
}

export interface PerformanceMetric {
  metric_type: string
  value: number
  component: string
  timestamp: string
  metadata?: Record<string, any>
}

export interface PerformanceBottleneck {
  bottleneck_type: string
  severity: 'low' | 'medium' | 'high'
  description: string
  affected_components: string[]
  recommendations: string[]
  detected_at: string
}

export interface Escalation {
  id: string
  title: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  description: string
  triggered_at: string
  acknowledged_at?: string
  resolved_at?: string
  acknowledged_by?: string
  resolved_by?: string
  metadata?: Record<string, any>
}

// Tasks Types
export interface TaskStatus {
  task_id: string
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  created_at: string
  started_at?: string
  completed_at?: string
  progress?: number
  result?: any
  error?: string
}

export interface WorkerStats {
  worker_id: string
  status: 'online' | 'offline'
  active_tasks: number
  processed_tasks: number
  failed_tasks: number
  load_average: number[]
  memory_usage: {
    rss: number
    vms: number
    percent: number
  }
}

export interface TaskResult<T = any> {
  task_id: string
  status: 'pending' | 'running' | 'success' | 'failure' | 'revoked'
  ready: boolean
  successful?: boolean
  failed?: boolean
  result?: T
  error?: string
  traceback?: string
}

export interface BulkMessageData {
  patient_id: string
  content: string
  type?: string
  scheduled_for?: string
  metadata?: Record<string, any>
}

// ============================================================================
// LEGACY TYPE ALIASES
// ============================================================================

/** @deprecated Use PaginatedResponse from shared types */
export interface PaginatedResponseAlt<T> {
  readonly items: T[]
  readonly total: number
  readonly page: number
  readonly size: number
  readonly pages: number
}

/** @deprecated Use ApiResponse from shared types */
export interface ApiSuccessResponse<T = any> {
  readonly success: boolean
  readonly message: string
  readonly data?: T
  readonly timestamp: string
}

// Note: ApiErrorResponse is properly exported from shared types above

// Note: ApiClientConfig is exported from shared types above

// ============================================================================
// ENHANCED ERROR TYPES (Legacy)
// ============================================================================

/** @deprecated Use ValidationError from shared types */
export interface ApiErrorDetails {
  readonly field?: string
  readonly issue?: string
  readonly code?: string
  readonly constraint?: string
  readonly expected?: any
  readonly received?: any
}

/** @deprecated Use ApiErrorResponse from shared types */
export interface EnhancedApiError {
  readonly error: string
  readonly message: string
  readonly details?: ApiErrorDetails | ApiErrorDetails[] | Record<string, any>
  readonly timestamp: string
  readonly request_id?: string
  readonly trace_id?: string
}

// ============================================================================
// AUTHENTICATION TYPES (Legacy)
// ============================================================================

// Note: LoginCredentials, AuthTokens, and User types are exported from auth types above

/** @deprecated Use User from auth types */
export interface UserInfo {
  id: string
  email: string
  name?: string
  role?: string
  permissions?: string[]
  last_login?: string
  created_at: string
  updated_at: string
}

/** @deprecated Use direct refresh methods from auth hooks */
export interface RefreshTokenRequest {
  refresh_token: string
}

// Query Parameter Types
export interface PaginationParams {
  page?: number
  size?: number
}

export interface FilterParams {
  search?: string
  status?: string
  start_date?: string
  end_date?: string
}

export interface SortParams {
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

// Combined Query Types
export type ListParams = PaginationParams & FilterParams & SortParams

// Monitoring Query Types
export interface MonitoringQueryParams {
  severity?: 'low' | 'medium' | 'high' | 'critical'
  component?: string
  limit?: number
  start_time?: string
  end_time?: string
}

export interface PerformanceQueryParams {
  hours?: number
  component?: string
  metric_type?: string
}

// Platform Sync Query Types
export interface AuditQueryParams {
  entity_type: string
  entity_id: string
  days?: number
}

export interface ConsistencyQueryParams {
  days?: number
}

export interface SyncCleanupParams {
  older_than_days?: number
}

// Tasks Query Types
export interface TaskQueryParams {
  status?: 'pending' | 'running' | 'completed' | 'failed'
  limit?: number
  offset?: number
}

export interface MessagingTaskParams {
  limit?: number
  max_retries?: number
  days_old?: number
  patient_id?: string
  days_back?: number
}

// ============================================================================
// REAL-TIME UPDATE TYPES
// ============================================================================

/** Real-time database update structure */
export interface RealtimeUpdate<T = any> {
  table: string
  event: 'INSERT' | 'UPDATE' | 'DELETE'
  old?: T
  new?: T
  timestamp: string
}

// ============================================================================
// HEALTH CHECK TYPES
// ============================================================================

/** Individual health check result */
export interface HealthCheck {
  name: string
  status: 'pass' | 'fail' | 'warn'
  duration_ms: number
  message?: string
  details?: Record<string, any>
}

/** Complete system health report */
export interface SystemHealthReport {
  status: 'pass' | 'fail' | 'warn'
  checks: HealthCheck[]
  timestamp: string
  uptime_seconds: number
  version: string
}

// Note: DashboardAnalytics and other analytics types are exported from api types above

/** @deprecated Use DashboardAnalytics from api types */
export interface DashboardMetrics {
  total_patients: number
  active_flows: number
  messages_sent_today: number
  alerts_count: number
  system_health: 'healthy' | 'warning' | 'critical'
  recent_activity: Array<{
    type: string
    description: string
    timestamp: string
  }>
}

// Note: All analytics types (DashboardAnalytics, EngagementMetrics, FlowMetrics)
// are properly exported from the main api types module above

// Note: AI types (AIInsight, SentimentAnalysis), Notification, and ActivityItem
// are all properly exported from the main api types module above

// Note: Flow template types (FlowTemplate, FlowStep, CreateFlowTemplateRequest, UpdateFlowTemplateRequest)
// are all properly exported from the main api types module above

// Note: All WebSocket types are properly exported from the websocket types module above
// This includes WebSocketMessage, WebSocketEventType, and all event data types

// Note: All query parameter types and request/response types are properly exported
// from the main api types module above, including:
// - PatientQueryParams, MessageQueryParams, AlertQueryParams, ReportQueryParams
// - CreatePatientRequest, UpdatePatientRequest, SendMessageRequest, BulkMessageRequest
// - StartFlowRequest, CreateAlertRequest, GenerateReportRequest

// Note: The complete ApiClient interface and all endpoint interfaces are properly exported
// from the main api types module above. This includes comprehensive type-safe client definitions.

// Note: Extended client interfaces are integrated into the main ApiClient interface
// exported from the api types module above. No separate extended interfaces needed.

// Request Options for API client
export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  headers?: Record<string, string>
  body?: string | FormData
  params?: Record<string, string | number | boolean>
  timeout?: number
  cache?: boolean
}

// Notification Types
export interface Notification {
  id: string
  title: string
  message: string
  type: 'info' | 'success' | 'warning' | 'error'
  read: boolean
  created_at: string
  metadata?: Record<string, any>
}

// ============================================================================
// FINAL NOTES
// ============================================================================

/*
 * This file serves as a compatibility layer for existing imports.
 *
 * New code should import directly from:
 * - /types/api.ts for core API types
 * - /types/shared.ts for base types and utilities
 * - /types/auth.ts for authentication types
 * - /types/websocket.ts for real-time communication types
 *
 * All major types are re-exported above for backwards compatibility.
 */

// Note: ApiResponse, ApiErrorResponse, and RequestOptions are exported from shared types above
