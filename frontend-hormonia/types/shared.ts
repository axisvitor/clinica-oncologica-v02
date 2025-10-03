/**
 * Shared Base Types - Consolidated foundation types for the entire application
 * Provides common interfaces, utility types, and base configurations
 */

// ============================================================================
// CORE BASE TYPES
// ============================================================================

/** Generic API response wrapper */
export interface ApiResponse<T = unknown> {
  readonly data: T
  readonly message?: string
  readonly timestamp: string
  readonly success: boolean
}

/** Error response from API */
export interface ApiErrorResponse {
  readonly error: string
  readonly message: string
  readonly details?: Record<string, unknown> | unknown[]
  readonly timestamp: string
  readonly status_code: number
  readonly request_id?: string
  readonly trace_id?: string
}

/** Paginated response structure - matches backend format */
export interface PaginatedResponse<T = unknown> {
  readonly items: T[]  // Primary data array property (backend format)
  readonly total: number
  readonly page: number
  readonly size: number
  readonly pages: number
  readonly has_next: boolean
  readonly has_prev: boolean
  // Legacy compatibility properties
  readonly data?: T[]  // For backward compatibility
  readonly has_more?: boolean  // Alternative naming
}

/** Base entity interface that all data models extend */
export interface BaseEntity {
  readonly id: string
  readonly created_at: string
  readonly updated_at: string
}

/** Soft-deletable entity */
export interface SoftDeletableEntity extends BaseEntity {
  readonly deleted_at?: string
}

// ============================================================================
// UTILITY TYPES
// ============================================================================

/** Make all properties optional recursively */
export type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P]
}

/** Make specified keys optional */
export type PartialBy<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>

/** Make specified keys required */
export type RequiredBy<T, K extends keyof T> = T & Required<Pick<T, K>>

/** Extract keys of specific type */
export type KeysOfType<T, U> = {
  [K in keyof T]: T[K] extends U ? K : never
}[keyof T]

/** Create a type with only specific properties */
export type PickByType<T, U> = Pick<T, KeysOfType<T, U>>

/** Nullable version of a type */
export type Nullable<T> = T | null

/** Optional version of a type */
export type Optional<T> = T | undefined

/** Create a union of property values */
export type ValueOf<T> = T[keyof T]

/** Create array item type */
export type ArrayElement<T> = T extends readonly (infer U)[] ? U : never

/** Create a type for async function return */
export type AsyncReturnType<T extends (...args: unknown[]) => Promise<unknown>> =
  T extends (...args: unknown[]) => Promise<infer R> ? R : never

// ============================================================================
// COMMON ENUMS
// ============================================================================

/** Standard status values */
export enum Status {
  ACTIVE = 'active',
  INACTIVE = 'inactive',
  PENDING = 'pending',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
  PAUSED = 'paused'
}

/** Priority levels */
export enum Priority {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  CRITICAL = 'critical'
}

/** Severity levels */
export enum Severity {
  INFO = 'info',
  WARNING = 'warning',
  ERROR = 'error',
  CRITICAL = 'critical'
}

/** User roles */
export enum UserRole {
  ADMIN = 'admin',
  DOCTOR = 'doctor',
  NURSE = 'nurse',
  ASSISTANT = 'assistant',
  SUPER_ADMIN = 'super_admin'
}

// ============================================================================
// QUERY & FILTER TYPES
// ============================================================================

/** Base pagination parameters */
export interface PaginationParams {
  readonly page?: number
  readonly size?: number
  readonly limit?: number
  readonly offset?: number
}

/** Base sorting parameters */
export interface SortParams {
  readonly sort_by?: string
  readonly sort_order?: 'asc' | 'desc'
}

/** Base filter parameters */
export interface FilterParams {
  readonly search?: string
  readonly status?: string
  readonly type?: string
  readonly start_date?: string
  readonly end_date?: string
}

/** Combined query parameters */
export type QueryParams = PaginationParams & SortParams & FilterParams

// ============================================================================
// CONFIGURATION TYPES
// ============================================================================

/** API client configuration */
export interface ApiClientConfig {
  readonly baseURL: string
  readonly timeout?: number
  readonly retryAttempts?: number
  readonly retryDelay?: number
  readonly headers?: Record<string, string>
  readonly enableCache?: boolean
  readonly cacheTimeout?: number
}

/** WebSocket configuration */
export interface WebSocketConfig {
  readonly url: string
  readonly reconnectAttempts: number
  readonly reconnectDelay: number
  readonly heartbeatInterval: number
  readonly connectionTimeout: number
  readonly enableLogging: boolean
  readonly autoReconnect?: boolean
}

/** Retry configuration */
export interface RetryConfig {
  readonly maxRetries: number
  readonly retryDelay: number
  readonly exponentialBackoff: boolean
  readonly retryableErrors?: string[]
}

// ============================================================================
// METADATA TYPES
// ============================================================================

/** Generic metadata structure */
export type Metadata = Record<string, unknown>

/** Audit information */
export interface AuditInfo {
  readonly created_by?: string
  readonly updated_by?: string
  readonly version?: number
  readonly changes?: Record<string, unknown>
}

/** Versioned entity */
export interface VersionedEntity extends BaseEntity {
  readonly version: number
  readonly audit?: AuditInfo
}

// ============================================================================
// ERROR TYPES
// ============================================================================

/** Base error interface */
export interface BaseError extends Error {
  readonly code?: string
  readonly details?: Record<string, unknown>
  readonly retryable?: boolean
  readonly retryAfter?: number
}

/** Validation error */
export interface ValidationError extends BaseError {
  readonly field?: string
  readonly constraint?: string
  readonly expected?: unknown
  readonly received?: unknown
}

/** Network error */
export interface NetworkError extends BaseError {
  readonly status?: number
  readonly statusText?: string
  readonly url?: string
}

// ============================================================================
// EVENT TYPES
// ============================================================================

/** Base event structure */
export interface BaseEvent<T = unknown> {
  readonly type: string
  readonly timestamp: string
  readonly data: T
  readonly source?: string
  readonly id?: string
}

/** Event listener function */
export type EventListener<T = unknown> = (event: BaseEvent<T>) => void | Promise<void>

/** Event subscription */
export interface EventSubscription {
  readonly id: string
  readonly event: string
  readonly handler: EventListener
  readonly once?: boolean
}

// ============================================================================
// COMPONENT PROP TYPES
// ============================================================================

/** Base component props */
export interface BaseComponentProps {
  readonly className?: string
  readonly id?: string
  readonly testId?: string
  readonly 'aria-label'?: string
  readonly 'aria-describedby'?: string
}

/** Loading state props */
export interface LoadingProps {
  readonly loading?: boolean
  readonly loadingText?: string
  readonly skeleton?: boolean
}

/** Error state props */
export interface ErrorProps {
  readonly error?: Error | string | null
  readonly onRetry?: () => void
  readonly retryText?: string
}

/** Combined state props */
export type StateProps = LoadingProps & ErrorProps

// ============================================================================
// FORM TYPES
// ============================================================================

/** Form field configuration */
export interface FormField<T = unknown> {
  readonly name: string
  readonly type: 'text' | 'email' | 'password' | 'number' | 'date' | 'select' | 'textarea' | 'checkbox' | 'radio'
  readonly label: string
  readonly placeholder?: string
  readonly required?: boolean
  readonly disabled?: boolean
  readonly validation?: ValidationRule[]
  readonly options?: Array<{ value: T; label: string }>
  readonly defaultValue?: T
}

/** Validation rule */
export interface ValidationRule {
  readonly type: 'required' | 'min' | 'max' | 'pattern' | 'custom'
  readonly value?: unknown
  readonly message: string
  readonly validator?: (value: unknown) => boolean | Promise<boolean>
}

/** Form state */
export interface FormState<T = Record<string, unknown>> {
  readonly values: T
  readonly errors: Record<keyof T, string>
  readonly touched: Record<keyof T, boolean>
  readonly isValid: boolean
  readonly isSubmitting: boolean
  readonly isDirty: boolean
}

// ============================================================================
// TIME & DATE TYPES
// ============================================================================

/** Time range */
export interface TimeRange {
  readonly start: string
  readonly end: string
}

/** Duration */
export interface Duration {
  readonly value: number
  readonly unit: 'seconds' | 'minutes' | 'hours' | 'days' | 'weeks' | 'months' | 'years'
}

/** Schedule */
export interface Schedule {
  readonly frequency: 'once' | 'daily' | 'weekly' | 'monthly' | 'yearly'
  readonly interval?: number
  readonly time?: string
  readonly timezone?: string
  readonly days_of_week?: number[]
  readonly days_of_month?: number[]
}

// ============================================================================
// FEATURE FLAGS
// ============================================================================

/** Feature flag */
export interface FeatureFlag {
  readonly key: string
  readonly enabled: boolean
  readonly description?: string
  readonly rollout_percentage?: number
  readonly user_groups?: string[]
}

/** Feature flags collection */
export type FeatureFlags = Record<string, FeatureFlag>

// ============================================================================
// ANALYTICS TYPES
// ============================================================================

/** Analytics event */
export interface AnalyticsEvent {
  readonly name: string
  readonly properties?: Record<string, unknown>
  readonly timestamp?: string
  readonly user_id?: string
  readonly session_id?: string
}

/** Metric value */
export interface Metric {
  readonly name: string
  readonly value: number
  readonly unit?: string
  readonly timestamp: string
  readonly tags?: Record<string, string>
}

// ============================================================================
// INTERNATIONALIZATION
// ============================================================================

/** Localized text */
export type LocalizedText = Record<string, string>

/** Translation key */
export type TranslationKey = string

/** Locale */
export interface Locale {
  readonly code: string
  readonly name: string
  readonly direction: 'ltr' | 'rtl'
  readonly currency?: string
  readonly dateFormat?: string
  readonly timeFormat?: string
}

// ============================================================================
// TYPE GUARDS
// ============================================================================

/** Check if value is not null or undefined */
export function isDefined<T>(value: T | null | undefined): value is T {
  return value !== null && value !== undefined
}

/** Check if error is API error */
export function isApiError(error: unknown): error is ApiErrorResponse {
  return typeof error === 'object' && 
         error !== null && 
         'error' in error && 
         'status_code' in error
}

/** Check if response is paginated */
export function isPaginatedResponse<T>(response: unknown): response is PaginatedResponse<T> {
  return typeof response === 'object' && 
         response !== null && 
         'data' in response && 
         'total' in response && 
         'page' in response
}

/** Check if entity has ID */
export function hasId(entity: unknown): entity is { id: string } {
  return typeof entity === 'object' && entity !== null && 'id' in entity
}

// ============================================================================
// CONSTANTS
// ============================================================================

/** Default pagination values */
export const DEFAULT_PAGINATION = {
  page: 1,
  size: 20,
  limit: 20
} as const

/** Default retry configuration */
export const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxRetries: 3,
  retryDelay: 1000,
  exponentialBackoff: true
} as const

/** HTTP status codes */
export const HTTP_STATUS = {
  OK: 200,
  CREATED: 201,
  NO_CONTENT: 204,
  BAD_REQUEST: 400,
  UNAUTHORIZED: 401,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  CONFLICT: 409,
  UNPROCESSABLE_ENTITY: 422,
  INTERNAL_SERVER_ERROR: 500,
  BAD_GATEWAY: 502,
  SERVICE_UNAVAILABLE: 503
} as const

/** Common date formats */
export const DATE_FORMATS = {
  ISO: 'YYYY-MM-DDTHH:mm:ss.SSSZ',
  DATE_ONLY: 'YYYY-MM-DD',
  TIME_ONLY: 'HH:mm:ss',
  DISPLAY: 'DD/MM/YYYY',
  DISPLAY_WITH_TIME: 'DD/MM/YYYY HH:mm'
} as const