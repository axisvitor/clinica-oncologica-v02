/**
 * Shared Hook Types and Utilities
 *
 * Common type definitions for hooks to ensure type safety
 * and consistency across the application.
 */

/**
 * Common hook return patterns for data fetching
 */
export interface QueryResult<T> {
  data: T | null
  isLoading: boolean
  error: Error | null
  refetch: () => void
}

export interface MutationResult<TData, TVariables> {
  mutate: (variables: TVariables) => Promise<TData>
  isPending: boolean
  error: Error | null
  data: TData | null
}

export interface PaginatedResult<T> {
  data: T[]
  total: number
  page: number
  pageSize: number
  hasMore: boolean
}

/**
 * Common hook options for pagination
 */
export interface PaginationOptions {
  page?: number
  pageSize?: number
}

export interface SortOptions {
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
}

export interface FilterOptions {
  search?: string
  status?: string
  [key: string]: unknown
}

/**
 * WebSocket message types
 */
export interface WebSocketMessage<T = unknown> {
  type: string
  data?: T
  timestamp: string
}

export interface WebSocketHookReturn<T = unknown> {
  isConnected: boolean
  lastMessage: WebSocketMessage<T> | null
  error: Error | null
  send: (data: T) => boolean
  connect: () => void
  disconnect: () => void
}

/**
 * Metrics-specific WebSocket types
 */
export interface SystemMetrics {
  cpu_usage?: number
  memory_usage?: number
  active_connections?: number
  request_count?: number
  error_rate?: number
  timestamp: string
}

export interface PatientMetrics {
  patient_id: string
  engagement_score?: number
  response_rate?: number
  last_activity?: string
}

export interface MetricsWebSocketData {
  type: 'system' | 'patient' | 'alert' | 'ping' | 'pong'
  metrics?: SystemMetrics | PatientMetrics
  message?: string
}

/**
 * Notification types
 */
export interface SystemNotification {
  id: string
  type: 'info' | 'warning' | 'error' | 'success'
  message: string
  title?: string
  timestamp: string
  read?: boolean
}

export interface PatientUpdate {
  patient_id: string
  update_type: 'status' | 'quiz_completion' | 'message_sent' | 'alert'
  data: Record<string, unknown>
  timestamp: string
}

/**
 * API response wrapper types
 */
export interface ApiResponse<T> {
  data: T
  message?: string
  success: boolean
}

export interface PaginatedApiResponse<T> {
  data: T[]
  total: number
  page: number
  size: number
  has_more: boolean
  next_cursor?: string
}

/**
 * Error types for hooks
 */
export interface HookError extends Error {
  code?: string
  details?: Record<string, unknown>
}

/**
 * Date range filtering
 */
export interface DateRangeFilter {
  start_date?: string
  end_date?: string
}

/**
 * Type guard utilities
 */
export function isWebSocketMessage<T>(value: unknown): value is WebSocketMessage<T> {
  return (
    typeof value === 'object' &&
    value !== null &&
    'type' in value &&
    typeof (value as WebSocketMessage).type === 'string'
  )
}

export function isApiResponse<T>(value: unknown): value is ApiResponse<T> {
  return (
    typeof value === 'object' &&
    value !== null &&
    'success' in value &&
    typeof (value as ApiResponse<unknown>).success === 'boolean'
  )
}

/**
 * Generic analysis data types
 */
export interface AnalysisRequest {
  type: 'sentiment' | 'pattern' | 'anomaly' | 'trend' | 'classification'
  data: Record<string, unknown>
  options?: {
    confidence_threshold?: number
    max_results?: number
    include_details?: boolean
  }
}

export interface AnalysisResult {
  type: string
  result: {
    status: 'completed' | 'pending' | 'failed'
    insights: string[]
    confidence: number
    details?: Record<string, unknown>
  }
  confidence: number
  metadata: {
    timestamp: string
    processing_time_ms?: number
    model_version?: string
  }
}
