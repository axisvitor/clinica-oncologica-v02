/**
 * API Types - Consolidated API client and response types
 * Centralized API interface definitions with enhanced type safety
 */

import type {
  BaseEntity,
  SoftDeletableEntity,
  PaginatedResponse,
  ApiResponse,
  ApiErrorResponse,
  QueryParams,
  Priority,
  Status,
  UserRole,
  Metadata
} from './shared'
import type { User, AuthTokens } from './auth'

// ============================================================================
// CORE DOMAIN ENTITIES
// ============================================================================

/** Patient entity */
export interface Patient extends BaseEntity {
  readonly name: string
  readonly email?: string
  readonly phone: string
  readonly whatsapp_number: string
  readonly birth_date?: string
  readonly treatment_type: string
  readonly enrollment_date: string
  readonly status: PatientStatus
  readonly current_day?: number  // Fixed property name to match application expectations
  readonly current_flow_day?: number  // Keep for backwards compatibility
  readonly doctor_id?: string
  readonly metadata?: Metadata
}

/** Patient status enum */
export enum PatientStatus {
  ACTIVE = 'active',
  INACTIVE = 'inactive',
  COMPLETED = 'completed',
  PAUSED = 'paused',
  CANCELLED = 'cancelled'
}

/** Message entity */
export interface Message extends BaseEntity {
  readonly patient_id: string
  readonly direction: MessageDirection
  readonly type: MessageType
  readonly content: string
  readonly status: MessageStatus
  readonly whatsapp_id?: string
  readonly scheduled_for?: string
  readonly sent_at?: string
  readonly delivered_at?: string
  readonly read_at?: string
  readonly failed_at?: string
  readonly error_message?: string
  readonly metadata?: Metadata
}

/** Message direction */
export enum MessageDirection {
  INBOUND = 'inbound',
  OUTBOUND = 'outbound'
}

/** Message type */
export enum MessageType {
  TEXT = 'text',
  IMAGE = 'image',
  AUDIO = 'audio',
  VIDEO = 'video',
  DOCUMENT = 'document',
  INTERACTIVE = 'interactive',
  TEMPLATE = 'template'
}

/** Message status */
export enum MessageStatus {
  PENDING = 'pending',
  QUEUED = 'queued',
  SENT = 'sent',
  DELIVERED = 'delivered',
  READ = 'read',
  FAILED = 'failed',
  CANCELLED = 'cancelled'
}

/** Flow entity */
export interface Flow extends BaseEntity {
  readonly patient_id: string
  readonly flow_type: FlowType
  readonly current_state: string
  readonly current_day: number
  readonly is_paused: boolean
  readonly enrollment_date: string
  readonly last_message_sent?: string
  readonly monthly_cycle?: number
  readonly status: FlowStatus
  readonly state_data: Record<string, unknown>
  readonly metadata?: Metadata
}

/** Flow type enum */
export enum FlowType {
  INITIAL_15_DAYS = 'initial_15_days',
  DAYS_16_45 = 'days_16_45',
  MONTHLY_RECURRING = 'monthly_recurring',
  CUSTOM = 'custom'
}

/** Flow status enum */
export enum FlowStatus {
  ACTIVE = 'active',
  PAUSED = 'paused',
  COMPLETED = 'completed',
  CANCELLED = 'cancelled'
}

/** Alert entity */
export interface Alert extends BaseEntity {
  readonly patient_id?: string
  readonly patient_name?: string
  readonly type: AlertType
  readonly severity: Priority
  readonly title: string
  readonly message: string
  readonly acknowledged: boolean
  readonly acknowledged_by?: string
  readonly acknowledged_at?: string
  readonly resolved: boolean
  readonly resolved_by?: string
  readonly resolved_at?: string
  readonly metadata?: Metadata
}

/** Alert type enum */
export enum AlertType {
  PATIENT_INACTIVE = 'patient_inactive',
  FLOW_STUCK = 'flow_stuck',
  MESSAGE_FAILED = 'message_failed',
  LOW_ENGAGEMENT = 'low_engagement',
  SYSTEM_ERROR = 'system_error',
  SECURITY_BREACH = 'security_breach',
  PERFORMANCE_ISSUE = 'performance_issue'
}

/** Report entity */
export interface Report extends BaseEntity {
  readonly patient_id: string
  readonly patient_name?: string
  readonly report_type: ReportType
  readonly type: string
  readonly status: ReportStatus
  readonly title: string
  readonly description?: string
  readonly file_path?: string
  readonly file_size?: number
  readonly generated_by: string
  readonly generated_at?: string
  readonly content?: string
  readonly summary?: unknown
  readonly parameters?: Metadata
  readonly metadata?: Metadata
}

/** Report type enum */
export enum ReportType {
  PATIENT_SUMMARY = 'patient_summary',
  FLOW_ANALYTICS = 'flow_analytics',
  ENGAGEMENT_REPORT = 'engagement_report',
  MEDICAL_REPORT = 'medical_report',
  COMPLIANCE_REPORT = 'compliance_report'
}

/** Report status enum */
export enum ReportStatus {
  PENDING = 'pending',
  GENERATING = 'generating',
  COMPLETED = 'completed',
  FAILED = 'failed',
  EXPIRED = 'expired'
}

// ============================================================================
// QUIZ & ASSESSMENT TYPES
// ============================================================================

/** Quiz template */
export interface QuizTemplate extends BaseEntity {
  readonly title: string
  readonly description?: string
  readonly questions: readonly QuizQuestion[]
  readonly scoring_method: ScoringMethod
  readonly pass_threshold?: number
  readonly estimated_duration?: number
  readonly is_active: boolean
  readonly category?: string
  readonly tags?: readonly string[]
  readonly metadata?: Metadata
}

/** Quiz question */
export interface QuizQuestion {
  readonly id: string
  readonly question: string
  readonly type: QuestionType
  readonly options?: readonly QuizOption[]
  readonly required: boolean
  readonly points?: number
  readonly order: number
  readonly validation?: QuestionValidation
}

/** Quiz option */
export interface QuizOption {
  readonly id: string
  readonly text: string
  readonly value: unknown
  readonly points?: number
  readonly is_correct?: boolean
}

/** Question type enum */
export enum QuestionType {
  SINGLE_CHOICE = 'single_choice',
  MULTIPLE_CHOICE = 'multiple_choice',
  TEXT = 'text',
  NUMBER = 'number',
  SCALE = 'scale',
  YES_NO = 'yes_no',
  DATE = 'date'
}

/** Scoring method enum */
export enum ScoringMethod {
  POINTS = 'points',
  PERCENTAGE = 'percentage',
  PASS_FAIL = 'pass_fail',
  WEIGHTED = 'weighted'
}

/** Question validation */
export interface QuestionValidation {
  readonly min_length?: number
  readonly max_length?: number
  readonly min_value?: number
  readonly max_value?: number
  readonly pattern?: string
  readonly custom_validator?: string
}

/** Quiz session */
export interface QuizSession extends BaseEntity {
  readonly patient_id: string
  readonly template_id: string
  readonly status: QuizSessionStatus
  readonly responses: Record<string, unknown>
  readonly score?: number
  readonly percentage?: number
  readonly passed?: boolean
  readonly started_at: string
  readonly completed_at?: string
  readonly time_taken?: number
  readonly metadata?: Metadata
}

/** Quiz session status */
export enum QuizSessionStatus {
  STARTED = 'started',
  IN_PROGRESS = 'in_progress',
  COMPLETED = 'completed',
  ABANDONED = 'abandoned',
  EXPIRED = 'expired'
}

// ============================================================================
// ANALYTICS & METRICS
// ============================================================================

/** Dashboard analytics */
export interface DashboardAnalytics {
  readonly total_patients: number
  readonly active_patients: number
  readonly patients_change: number
  readonly active_patients_percentage: number
  readonly messages_sent_today: number
  readonly messages_received_today: number
  readonly average_response_rate: number
  readonly response_rate: number
  readonly response_rate_change: number
  readonly alerts_count: number
  readonly active_alerts: number
  readonly alerts_change: number
  readonly reports_generated: number
  readonly completed_quizzes: number
  readonly quizzes_change: number
  readonly system_health: SystemHealthStatus
  readonly engagement_metrics: EngagementMetrics
  readonly flow_metrics: FlowMetrics
  readonly recent_activity: readonly ActivityItem[]
}

/** System health status */
export enum SystemHealthStatus {
  HEALTHY = 'healthy',
  WARNING = 'warning',
  CRITICAL = 'critical',
  MAINTENANCE = 'maintenance'
}

/** Engagement metrics */
export interface EngagementMetrics {
  readonly response_rate: number
  readonly avg_response_time: number
  readonly completion_rate: number
  readonly satisfaction_score?: number
  readonly engagement_trend: readonly TrendPoint[]
}

/** Flow metrics */
export interface FlowMetrics {
  readonly active_flows: number
  readonly completed_flows: number
  readonly paused_flows: number
  readonly avg_completion_time: number
  readonly flow_distribution: Record<FlowType, number>
}

/** Trend point */
export interface TrendPoint {
  readonly date: string
  readonly value: number
  readonly change?: number
}

/** Activity item */
export interface ActivityItem {
  readonly id: string
  readonly type: ActivityType
  readonly title: string
  readonly description: string
  readonly timestamp: string
  readonly user_id?: string
  readonly patient_id?: string
  readonly metadata?: Metadata
}

/** Activity type enum */
export enum ActivityType {
  PATIENT_ENROLLED = 'patient_enrolled',
  FLOW_STARTED = 'flow_started',
  FLOW_COMPLETED = 'flow_completed',
  MESSAGE_SENT = 'message_sent',
  QUIZ_COMPLETED = 'quiz_completed',
  ALERT_CREATED = 'alert_created',
  REPORT_GENERATED = 'report_generated',
  USER_LOGIN = 'user_login',
  SYSTEM_EVENT = 'system_event'
}

// ============================================================================
// AI & AUTOMATION
// ============================================================================

/** AI chat message */
export interface AIChatMessage extends BaseEntity {
  readonly session_id?: string
  readonly patient_id?: string
  readonly role: ChatRole
  readonly content: string
  readonly timestamp: string
  readonly confidence?: number
  readonly intent?: string
  readonly entities?: Record<string, unknown>
  readonly metadata?: {
    confidence?: number
    intent?: string
    requires_review?: boolean
  } & Metadata
}

/** Chat role enum */
export enum ChatRole {
  USER = 'user',
  ASSISTANT = 'assistant',
  SYSTEM = 'system'
}

/** Chat session interface */
export interface ChatSession extends BaseEntity {
  readonly patient_id?: string
  readonly user_id: string
  readonly title: string
  readonly messages: readonly AIChatMessage[]
  readonly status: 'active' | 'archived' | 'deleted'
  readonly metadata?: Metadata
}

/** AI insight */
export interface AIInsight extends BaseEntity {
  readonly patient_id?: string
  readonly type: InsightType
  readonly title: string
  readonly description: string
  readonly confidence: number
  readonly priority: Priority
  readonly recommendations?: readonly string[]
  readonly data?: Metadata
  readonly expires_at?: string
}

/** Insight type enum */
export enum InsightType {
  PATTERN = 'pattern',
  ANOMALY = 'anomaly',
  TREND = 'trend',
  RECOMMENDATION = 'recommendation',
  PREDICTION = 'prediction',
  ALERT = 'alert'
}

/** Sentiment analysis */
export interface SentimentAnalysis {
  readonly score: number // -1 to 1
  readonly magnitude: number // 0 to 1
  readonly label: SentimentLabel
  readonly confidence: number
  readonly emotions?: EmotionScores
}

/** Sentiment label enum */
export enum SentimentLabel {
  POSITIVE = 'positive',
  NEGATIVE = 'negative',
  NEUTRAL = 'neutral',
  MIXED = 'mixed'
}

/** Emotion scores */
export interface EmotionScores {
  readonly joy?: number
  readonly sadness?: number
  readonly anger?: number
  readonly fear?: number
  readonly surprise?: number
  readonly disgust?: number
}

// ============================================================================
// SYSTEM MONITORING
// ============================================================================

/** System health report */
export interface SystemHealth {
  readonly status: SystemHealthStatus
  readonly components: readonly ComponentHealth[]
  readonly metrics: Record<string, number>
  readonly uptime_seconds: number
  readonly version: string
  readonly last_updated: string
}

/** Component health */
export interface ComponentHealth {
  readonly name: string
  readonly status: ComponentStatus
  readonly last_check: string
  readonly response_time_ms?: number
  readonly error_message?: string
  readonly details?: Metadata
}

/** Component status enum */
export enum ComponentStatus {
  UP = 'up',
  DOWN = 'down',
  DEGRADED = 'degraded',
  MAINTENANCE = 'maintenance'
}

/** Performance metric */
export interface PerformanceMetric {
  readonly name: string
  readonly value: number
  readonly unit: string
  readonly component: string
  readonly timestamp: string
  readonly threshold?: PerformanceThreshold
}

/** Performance threshold */
export interface PerformanceThreshold {
  readonly warning: number
  readonly critical: number
  readonly unit: string
}

// ============================================================================
// API REQUEST/RESPONSE TYPES
// ============================================================================

/** Patient query parameters */
export interface PatientQueryParams extends QueryParams {
  readonly treatment_type?: string
  readonly doctor_id?: string
  readonly flow_status?: string
  readonly enrollment_after?: string
  readonly enrollment_before?: string
}

/** Message query parameters */
export interface MessageQueryParams extends QueryParams {
  readonly patient_id?: string
  readonly direction?: MessageDirection
  readonly type?: MessageType
  readonly status?: MessageStatus
  readonly sent_after?: string
  readonly sent_before?: string
}

/** Alert query parameters */
export interface AlertQueryParams extends QueryParams {
  readonly patient_id?: string
  readonly type?: AlertType
  readonly severity?: Priority
  readonly acknowledged?: boolean
  readonly resolved?: boolean
  readonly created_after?: string
  readonly created_before?: string
}

/** Report query parameters */
export interface ReportQueryParams extends QueryParams {
  readonly patient_id?: string
  readonly type?: ReportType
  readonly status?: ReportStatus
  readonly generated_by?: string
  readonly generated_after?: string
  readonly generated_before?: string
}

/** Create patient request */
export interface CreatePatientRequest {
  readonly name: string
  readonly email?: string
  readonly phone: string
  readonly whatsapp_number: string
  readonly birth_date?: string
  readonly treatment_type: string
  readonly doctor_id?: string
  readonly metadata?: Metadata
}

/** Update patient request */
export interface UpdatePatientRequest {
  readonly name?: string
  readonly email?: string
  readonly phone?: string
  readonly whatsapp_number?: string
  readonly birth_date?: string
  readonly treatment_type?: string
  readonly status?: PatientStatus
  readonly doctor_id?: string
  readonly metadata?: Metadata
}

/** Send message request */
export interface SendMessageRequest {
  readonly patient_id: string
  readonly content: string
  readonly type?: MessageType
  readonly scheduled_for?: string
  readonly metadata?: Metadata
}

/** Start flow request */
export interface StartFlowRequest {
  readonly patient_id: string
  readonly flow_type: FlowType
  readonly start_day?: number
  readonly metadata?: Metadata
}

/** Create alert request */
export interface CreateAlertRequest {
  readonly patient_id?: string
  readonly type: AlertType
  readonly severity: Priority
  readonly title: string
  readonly message: string
  readonly metadata?: Metadata
}

/** Generate report request */
export interface GenerateReportRequest {
  readonly patient_id: string
  readonly type: ReportType
  readonly title: string
  readonly description?: string
  readonly parameters?: Metadata
}

/** Bulk message request */
export interface BulkMessageRequest {
  readonly messages: readonly SendMessageRequest[]
  readonly batch_size?: number
  readonly delay_between_batches?: number
}

// ============================================================================
// API CLIENT INTERFACE
// ============================================================================

/** API client interface */
export interface ApiClient {
  // Authentication
  readonly auth: {
    readonly login: (credentials: { email: string; password: string }) => Promise<AuthTokens & { user: User }>
    readonly refresh: (refreshToken: string) => Promise<AuthTokens & { user: User }>
    readonly me: () => Promise<User>
    readonly logout: () => Promise<void>
  }

  // Patients
  readonly patients: {
    readonly list: (params?: PatientQueryParams) => Promise<PaginatedResponse<Patient>>
    readonly get: (id: string) => Promise<Patient>
    readonly create: (data: CreatePatientRequest) => Promise<Patient>
    readonly update: (id: string, data: UpdatePatientRequest) => Promise<Patient>
    readonly delete: (id: string) => Promise<void>
    readonly activate: (id: string) => Promise<void>
    readonly deactivate: (id: string) => Promise<void>
    readonly timeline: (id: string) => Promise<readonly ActivityItem[]>
  }

  // Messages
  readonly messages: {
    readonly list: (params?: MessageQueryParams) => Promise<PaginatedResponse<Message>>
    readonly send: (data: SendMessageRequest) => Promise<Message>
    readonly sendBulk: (data: BulkMessageRequest) => Promise<{ batch_id: string; message_ids: string[] }>
    readonly retry: (id: string) => Promise<Message>
    readonly cancel: (id: string) => Promise<void>
  }

  // Flows
  readonly flows: {
    readonly list: (params?: { patient_id?: string; status?: string }) => Promise<PaginatedResponse<Flow>>
    readonly start: (data: StartFlowRequest) => Promise<Flow>
    readonly getState: (patientId: string) => Promise<Flow>
    readonly advance: (patientId: string, forceDay?: number) => Promise<Flow>
    readonly pause: (patientId: string) => Promise<Flow>
    readonly resume: (patientId: string) => Promise<Flow>
    readonly processResponse: (patientId: string, message: Message) => Promise<void>
    readonly getAnalytics: () => Promise<FlowMetrics>
  }

  // Alerts
  readonly alerts: {
    readonly list: (params?: AlertQueryParams) => Promise<PaginatedResponse<Alert>>
    readonly create: (data: CreateAlertRequest) => Promise<Alert>
    readonly get: (id: string) => Promise<Alert>
    readonly acknowledge: (id: string) => Promise<Alert>
    readonly resolve: (id: string) => Promise<Alert>
    readonly delete: (id: string) => Promise<void>
  }

  // Reports
  readonly reports: {
    readonly list: (params?: ReportQueryParams) => Promise<PaginatedResponse<Report>>
    readonly generate: (data: GenerateReportRequest) => Promise<Report>
    readonly get: (id: string) => Promise<Report>
    readonly download: (id: string) => Promise<{ content: string; contentType: string; filename: string }>
    readonly delete: (id: string) => Promise<void>
  }

  // Analytics
  readonly analytics: {
    readonly dashboard: () => Promise<DashboardAnalytics>
    readonly patients: (params?: { start_date?: string; end_date?: string }) => Promise<EngagementMetrics>
    readonly engagement: (params?: { start_date?: string; end_date?: string }) => Promise<EngagementMetrics>
  }

  // AI
  readonly ai: {
    readonly chat: (message: string, context?: Metadata) => Promise<{ response: string; confidence: number }>
    readonly analyze: (data: unknown, analysisType: string) => Promise<AIInsight>
    readonly sentiment: (text: string) => Promise<SentimentAnalysis>
    readonly insights: (patientId: string, timeframe?: string) => Promise<readonly AIInsight[]>
    readonly recommendations: (patientId: string) => Promise<readonly AIInsight[]>
  }

  // System
  readonly system: {
    readonly health: () => Promise<SystemHealth>
    readonly metrics: () => Promise<readonly PerformanceMetric[]>
    readonly notifications: () => Promise<readonly Notification[]>
  }

  // Utility methods
  readonly setAuthToken: (token: string | null) => void
  readonly setSessionToken: (session: unknown) => void
  readonly request: <T>(endpoint: string, options?: RequestInit & { params?: Record<string, unknown> }) => Promise<T>
}

/** Notification entity */
export interface Notification extends BaseEntity {
  readonly user_id: string
  readonly title: string
  readonly message: string
  readonly type: NotificationType
  readonly priority: Priority
  readonly read: boolean
  readonly read_at?: string
  readonly action_url?: string
  readonly action_text?: string
  readonly metadata?: Metadata
}

/** Notification type enum */
export enum NotificationType {
  INFO = 'info',
  SUCCESS = 'success',
  WARNING = 'warning',
  ERROR = 'error',
  REMINDER = 'reminder',
  ALERT = 'alert'
}

// ============================================================================
// TYPE GUARDS
// ============================================================================

/** Check if entity is a Patient */
export function isPatient(entity: unknown): entity is Patient {
  return typeof entity === 'object' && 
         entity !== null && 
         'name' in entity && 
         'whatsapp_number' in entity
}

/** Check if entity is a Message */
export function isMessage(entity: unknown): entity is Message {
  return typeof entity === 'object' && 
         entity !== null && 
         'patient_id' in entity && 
         'direction' in entity && 
         'content' in entity
}

/** Check if entity is an Alert */
export function isAlert(entity: unknown): entity is Alert {
  return typeof entity === 'object' && 
         entity !== null && 
         'type' in entity && 
         'severity' in entity && 
         'title' in entity
}

/** Check if response is paginated */
export function isPaginatedApiResponse<T>(response: unknown): response is PaginatedResponse<T> {
  return typeof response === 'object' && 
         response !== null && 
         'data' in response && 
         Array.isArray((response as Record<string, unknown>)['data']) && 
         'total' in response
}

// ============================================================================
// CONSTANTS
// ============================================================================

/** Default query parameters */
export const DEFAULT_QUERY_PARAMS: QueryParams = {
  page: 1,
  size: 20,
  sort_order: 'desc'
} as const

/** API endpoints */
export const API_ENDPOINTS = {
  AUTH: '/auth',
  PATIENTS: '/patients',
  MESSAGES: '/messages',
  FLOWS: '/flows',
  ALERTS: '/alerts',
  REPORTS: '/reports',
  ANALYTICS: '/analytics',
  AI: '/ai',
  SYSTEM: '/system'
} as const

/** Cache timeouts (in milliseconds) */
export const CACHE_TIMEOUTS = {
  ANALYTICS: 5 * 60 * 1000,  // 5 minutes
  PATIENTS: 2 * 60 * 1000,   // 2 minutes
  MESSAGES: 30 * 1000,       // 30 seconds
  SYSTEM: 10 * 1000          // 10 seconds
} as const

// ============================================================================
// FLOW TEMPLATE TYPES (Missing from main API)
// ============================================================================

/** Flow template entity */
export interface FlowTemplate extends BaseEntity {
  readonly name: string
  readonly description?: string
  readonly flow_type: FlowType
  readonly steps: readonly FlowStep[]
  readonly is_active: boolean
  readonly category?: string
  readonly estimated_duration?: number
  readonly metadata?: Metadata
}

/** Flow step definition */
export interface FlowStep {
  readonly id: string
  readonly name: string
  readonly description?: string
  readonly step_type: string
  readonly day: number
  readonly content?: string
  readonly conditions?: Record<string, unknown>
  readonly metadata?: Metadata
}

/** Create flow template request */
export interface CreateFlowTemplateRequest {
  readonly name: string
  readonly description?: string
  readonly flow_type: FlowType
  readonly steps: readonly Omit<FlowStep, 'id'>[]
  readonly category?: string
  readonly metadata?: Metadata
}

/** Update flow template request */
export interface UpdateFlowTemplateRequest {
  readonly name?: string
  readonly description?: string
  readonly steps?: readonly Omit<FlowStep, 'id'>[]
  readonly is_active?: boolean
  readonly category?: string
  readonly metadata?: Metadata
}

// ============================================================================
// ADDITIONAL API CLIENT TYPES
// ============================================================================

/** Request options for API client */
export interface RequestOptions {
  readonly method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  readonly headers?: Record<string, string>
  readonly body?: string | FormData
  readonly params?: Record<string, string | number | boolean>
  readonly timeout?: number
  readonly cache?: boolean
}

// Update the API client interface to include template methods
export interface ApiClientFlowsExtended {
  readonly list: (params?: { patient_id?: string; status?: string }) => Promise<PaginatedResponse<Flow>>
  readonly start: (data: StartFlowRequest) => Promise<Flow>
  readonly getState: (patientId: string) => Promise<Flow>
  readonly advance: (patientId: string, forceDay?: number) => Promise<Flow>
  readonly pause: (patientId: string) => Promise<Flow>
  readonly resume: (patientId: string) => Promise<Flow>
  readonly processResponse: (patientId: string, message: Message) => Promise<void>
  readonly getAnalytics: () => Promise<FlowMetrics>
  // Template management methods
  readonly getTemplates: () => Promise<PaginatedResponse<FlowTemplate>>
  readonly createTemplate: (template: CreateFlowTemplateRequest) => Promise<FlowTemplate>
  readonly updateTemplate: (id: string, template: UpdateFlowTemplateRequest) => Promise<FlowTemplate>
  readonly deleteTemplate: (id: string) => Promise<void>
  readonly cloneTemplate: (id: string, name?: string) => Promise<FlowTemplate>
}

export interface ApiClientReportsExtended {
  readonly list: (params?: ReportQueryParams) => Promise<PaginatedResponse<Report>>
  readonly generate: (data: GenerateReportRequest) => Promise<Report>
  readonly get: (id: string) => Promise<Report>
  readonly download: (id: string) => Promise<{ content: string; contentType: string; filename: string }>
  readonly delete: (id: string) => Promise<void>
  readonly preview: (data: GenerateReportRequest) => Promise<{ preview: string; estimated_size: number }>
}

export interface ApiClientPatientsExtended {
  readonly list: (params?: PatientQueryParams) => Promise<PaginatedResponse<Patient>>
  readonly get: (id: string) => Promise<Patient>
  readonly create: (data: CreatePatientRequest) => Promise<Patient>
  readonly update: (id: string, data: UpdatePatientRequest) => Promise<Patient>
  readonly delete: (id: string) => Promise<void>
  readonly deletePatient: (id: string) => Promise<void> // Deprecated alias
  readonly activate: (id: string) => Promise<void>
  readonly deactivate: (id: string) => Promise<void>
  readonly timeline: (id: string) => Promise<readonly ActivityItem[]>
}

// Re-export PaginatedResponse for backward compatibility
export type { PaginatedResponse } from './shared'
