// API types for the application
import type { Priority } from './shared'
import type {
  Alert,
  QuizSession,
  AIInsight,
  QuizQuestion,
  QuestionOption,
  QuizTemplate,
  DailyMetric,
  FlowAnalytics,
  ResponseResult,
  MessageTemplate,
  Condition,
  InteractiveElements,
  FollowUpAction,
  FlowState,
  FlowTemplate,
  FlowStep,
  CreateFlowTemplateRequest,
  UpdateFlowTemplateRequest,
  StartFlowRequest,
  AlertListFilters as AlertQueryParams,
  CreateAlertRequest
} from '@/lib/api-client/types'
import { FlowType, FlowStatus, ResponseType } from '@/lib/api-client/types'
import type {
  Appointment,
  AppointmentCreate,
  AppointmentUpdate,
  AppointmentFilters,
  AppointmentStatus,
  AppointmentType,
  ConflictCheckRequest,
  ConflictCheckResponse,
} from '@/lib/api-client/appointments'
import type {
  Treatment,
  TreatmentCreate,
  TreatmentUpdate,
  TreatmentFilters,
  TreatmentStats,
  TreatmentStatus,
  TreatmentType
} from '@/lib/api-client/treatments'
import type {
  Medication,
  MedicationCreate,
  MedicationUpdate,
  MedicationFilters,
  MedicationSchedule,
  MedicationRoute,
  MedicationStats,
} from '@/lib/api-client/medications'
import type { Patient } from '@/lib/api-client/patients'

// Re-export canonical types for convenience
export type {
  Alert,
  QuizSession,
  Patient,
  AIInsight,
  QuizQuestion,
  QuestionOption,
  QuizTemplate,
  DailyMetric,
  FlowAnalytics,
  ResponseResult,
  MessageTemplate,
  Condition,
  InteractiveElements,
  FollowUpAction,
  FlowState,
  FlowTemplate,
  FlowStep,
  CreateFlowTemplateRequest,
  UpdateFlowTemplateRequest,
  StartFlowRequest,
  AlertQueryParams,
  CreateAlertRequest
}
export { FlowType, FlowStatus, ResponseType }

// Alias Flow to FlowState for backward compatibility if needed, or just export FlowState
export type Flow = FlowState

// ============================================================================
// AI TYPES - Core definitions
// ============================================================================

export enum ChatRole {
  USER = 'user',
  ASSISTANT = 'assistant',
  SYSTEM = 'system'
}

export interface AIChatMessage {
  id: string
  role: ChatRole
  content: string
  timestamp: string
  metadata?: Record<string, unknown>
  created_at?: string
  updated_at?: string
  patient_id?: string
}

export interface ChatSession {
  id: string
  patient_id?: string
  user_id: string
  title: string
  messages: AIChatMessage[]
  created_at: string
  updated_at: string
  status: 'active' | 'archived'
}

export enum InsightType {
  BEHAVIORAL = 'behavioral',
  EMOTIONAL = 'emotional',
  ENGAGEMENT = 'engagement',
  RISK = 'risk',
  OPPORTUNITY = 'opportunity',
  PATTERN = 'pattern',
  ANOMALY = 'anomaly'
}

// AIInsight moved to @/lib/api-client/types

export interface SentimentAnalysis {
  sentiment: 'positive' | 'negative' | 'neutral'
  score: number
  confidence: number
}

export type SentimentLabel = 'positive' | 'negative' | 'neutral'

export interface EmotionScores {
  joy: number
  sadness: number
  anger: number
  fear: number
  surprise: number
}

// Note: Priority type is exported from ./shared

export type PriorityType = 'low' | 'medium' | 'high' | 'critical'

export type Status = 'active' | 'inactive' | 'pending' | 'completed' | 'cancelled'

// ============================================================================
// PATIENT TYPES
// ============================================================================

export enum PatientStatus {
  ACTIVE = 'active',
  INACTIVE = 'inactive',
  PAUSED = 'paused',
  COMPLETED = 'completed',
  CANCELLED = 'cancelled'
}

/**
 * Patient - Represents a patient in the system
 * Imported from @/lib/api-client/patients
 */

export interface TimelineEvent {
  id: string
  patient_id: string
  event_type: 'message' | 'appointment' | 'quiz' | 'note' | 'system'
  title: string
  description?: string
  metadata?: Record<string, unknown>
  created_at: string
  created_by?: string
}

export interface PatientTimeline {
  patient_id: string
  events: TimelineEvent[]
}

// ============================================================================
// MESSAGE TYPES
// ============================================================================

export enum MessageDirection {
  INBOUND = 'inbound',
  OUTBOUND = 'outbound'
}

export enum MessageType {
  TEXT = 'text',
  IMAGE = 'image',
  VIDEO = 'video',
  AUDIO = 'audio',
  DOCUMENT = 'document',
  LOCATION = 'location',
  INTERACTIVE = 'interactive',
  TEMPLATE = 'template'
}

export enum MessageStatus {
  PENDING = 'pending',
  SENT = 'sent',
  DELIVERED = 'delivered',
  READ = 'read',
  FAILED = 'failed'
}

export interface Message {
  id: string
  patient_id: string
  direction: MessageDirection
  type: MessageType
  status: MessageStatus
  content: string
  metadata?: Record<string, unknown>
  sent_at?: string
  delivered_at?: string
  read_at?: string
  created_at: string
  updated_at?: string
}

export interface MessageQueryParams {
  patient_id?: string
  direction?: MessageDirection
  status?: MessageStatus
  page?: number
  size?: number
}

export interface SendMessageRequest {
  patient_id: string
  content: string
  type?: MessageType
  metadata?: Record<string, unknown>
}

export interface BulkMessageRequest {
  patient_ids: string[]
  content: string
  type?: MessageType
  scheduled_for?: string
}

// ============================================================================
// ALERT TYPES
// ============================================================================
// Alert types are now in @/lib/api-client/types
// Imported and re-exported above

export enum AlertType {
  INFO = 'info',
  WARNING = 'warning',
  ERROR = 'error',
  CRITICAL = 'critical'
}

// ============================================================================
// REPORT TYPES
// ============================================================================

export enum ReportType {
  PATIENT_SUMMARY = 'patient_summary',
  ENGAGEMENT = 'engagement',
  ANALYTICS = 'analytics',
  CUSTOM = 'custom'
}

export enum ReportStatus {
  PENDING = 'pending',
  GENERATING = 'generating',
  COMPLETED = 'completed',
  FAILED = 'failed'
}

/**
 * Report - Represents a generated report in the system
 * Used for patient summaries, analytics, and custom reports
 */
export interface Report {
  id: string
  type: ReportType | string
  status: ReportStatus | string
  title: string
  description?: string
  patient_id?: string
  patient_name?: string
  generated_by: string
  generated_at?: string
  file_url?: string
  file_path?: string  // Alternative to file_url for some backends
  content?: string  // Report content for preview
  parameters?: Record<string, unknown>
  metadata?: Record<string, unknown>  // Additional metadata
  created_at: string
  completed_at?: string  // When report generation completed
}

export interface ReportQueryParams {
  type?: ReportType
  status?: ReportStatus
  patient_id?: string
  page?: number
  size?: number
}

export interface GenerateReportRequest {
  type: ReportType | string
  title: string
  description?: string
  patient_id?: string
  parameters?: Record<string, unknown>
}
// ============================================================================

export enum QuestionType {
  MULTIPLE_CHOICE = 'multiple_choice',
  TEXT = 'text',
  SCALE = 'scale',
  YES_NO = 'yes_no'
}

export enum ScoringMethod {
  SUM = 'sum',
  AVERAGE = 'average',
  WEIGHTED = 'weighted',
  CUSTOM = 'custom'
}

export enum QuizSessionStatus {
  NOT_STARTED = 'not_started',
  IN_PROGRESS = 'in_progress',
  COMPLETED = 'completed',
  EXPIRED = 'expired'
}

// QuizQuestion and QuizTemplate are now re-exported from @/lib/api-client/types

/**
 * QuizLinkStatus - Status values for quiz links
 * Represents the current state of a quiz link sent to a patient
 */
export type QuizLinkStatusValue = 'not_sent' | 'sent' | 'accessed' | 'completed' | 'expired' | 'active' | 'cancelled' | 'pending'

/**
 * QuizLinkStatus - Complete quiz link status information
 * Used for tracking quiz link state and delivery
 */
export interface QuizLinkStatus {
  session_id: string
  patient_id: string
  status: QuizLinkStatusValue | string
  link?: string
  expires_at?: string
  completed_at?: string
  responses?: Record<string, unknown>
  delivery_attempts?: Array<Record<string, unknown>>
  last_delivery_status?: string
  last_delivery_method?: string
}

/**
 * MonthlyQuizStatusData - Monthly quiz status for a patient
 * Simplified status information for dashboard and patient views
 */
export interface MonthlyQuizStatusData {
  patient_id: string
  session_id?: string
  status: QuizLinkStatusValue
  last_sent?: string
  access_date?: string
  completion_date?: string
  expires_at?: string
  template_name?: string
  template_id?: string
}

/**
 * QuizResponse - A single answer to a quiz question
 * 
 * @example
 * ```typescript
 * const response: QuizResponse = {
 *   session_id: 'session-123',
 *   question_id: 'q1',
 *   answer: 'Feeling better',
 *   answered_at: '2024-01-15T10:30:00Z'
 * }
 * ```
 */
export interface QuizResponse {
  /** ID of the quiz session */
  session_id: string
  /** ID of the question being answered */
  question_id: string
  /** The patient's answer */
  answer: string
  /** ISO timestamp when the answer was submitted */
  answered_at: string
}

/**
 * QuizHistory - Historical record of a completed quiz
 * 
 * Represents a completed quiz session with all responses and scoring.
 * Used for tracking patient progress over time.
 * 
 * @example
 * ```typescript
 * const history: QuizHistory = {
 *   session_id: 'session-123',
 *   quiz_template_id: 'monthly-wellness',
 *   completed_at: '2024-01-15T11:00:00Z',
 *   score: 85,
 *   responses: {
 *     'q1': 'Feeling better',
 *     'q2': '7',
 *     'q3': 'Yes'
 *   }
 * }
 * ```
 */
export interface QuizHistory {
  /** ID of the quiz session */
  session_id: string
  /** ID of the quiz template that was used */
  quiz_template_id: string
  /** ISO timestamp when the quiz was completed */
  completed_at: string
  /** Calculated score for the quiz */
  score: number
  /** Map of question IDs to answers */
  responses: Record<string, unknown>
}

// Flow types are now re-exported from @/lib/api-client/types

// ============================================================================
// ANALYTICS & METRICS TYPES
// ============================================================================

export interface DashboardAnalytics {
  total_patients: number
  active_patients: number
  total_messages: number
  messages_today: number
  active_flows: number
  pending_alerts: number
  engagement_rate: number
  response_rate: number
}

export interface EngagementMetrics {
  patient_id: string
  total_messages: number
  total_messages_sent: number
  total_messages_received: number
  response_rate: number
  avg_response_time_minutes: number
  last_interaction: string
  engagement_score: number
}

export interface FlowMetrics {
  flow_type: FlowType
  total_enrollments: number
  active_enrollments: number
  completion_rate: number
  avg_completion_days: number
}

export interface ActivityItem {
  id: string
  type: 'message' | 'flow' | 'quiz' | 'alert' | 'system'
  description: string
  patient_id?: string
  timestamp: string
  metadata?: Record<string, unknown>
}

// ============================================================================
// USER & AUTH TYPES
// ============================================================================

/**
 * User - Represents an authenticated user in the system
 *
 * FIELD MAPPING (Frontend <-> Backend):
 * - name (frontend) <-> full_name (backend)
 * - full_name is kept for backward compatibility
 *
 * Use normalizers from @/lib/api-client/normalizers to convert between formats
 */
export interface User {
  id: string
  email: string
  name: string // PRIMARY: User's display name (mapped from backend full_name)
  full_name: string // LEGACY: Kept for backward compatibility (same as name)
  role: string
  permissions: string[]
  is_active: boolean
  created_at: string
  updated_at?: string | undefined
  firebase_uid?: string
  session_id?: string
  token?: string  // Optional for WebSocket/API auth
  avatar_url?: string  // Optional for profile picture
}

export interface LoginCredentials {
  email: string
  password: string
}

/**
 * AuthTokens - Authentication tokens for API access
 * Includes access token, refresh token, and expiration information
 */
export interface AuthTokens {
  access_token: string
  refresh_token?: string
  token_type?: string
  expires_in?: number  // Token expiration time in seconds
}

/**
 * LoginResponse - Response from successful authentication
 * Includes user data, authentication tokens, and session information
 */
export interface LoginResponse {
  user: User
  tokens: AuthTokens
  session_id?: string  // Optional session ID for Redis-based session management
}

/**
 * CursorPage<T> - Generic cursor-based pagination response
 * 
 * Used for efficient pagination of large datasets. Instead of page numbers,
 * uses a cursor to track position in the result set.
 * 
 * @template T - The type of items in the data array
 * 
 * @example
 * ```typescript
 * const page: CursorPage<Patient> = {
 *   data: [patient1, patient2, patient3],
 *   next_cursor: 'eyJpZCI6MTIzfQ==',
 *   has_more: true,
 *   total: 150
 * }
 * 
 * // Fetch next page using the cursor
 * const nextPage = await api.patients.list({ cursor: page.next_cursor })
 * ```
 */
export interface CursorPage<T> {
  /** Array of items in the current page */
  data: T[]
  /** Cursor for fetching the next page, null if no more pages */
  next_cursor: string | null
  /** Whether there are more items available */
  has_more: boolean
  /** Optional total count of all items (may be expensive to compute) */
  total?: number
}

// ============================================================================
// QUERY PARAMS TYPES
// ============================================================================

export interface PatientQueryParams {
  search?: string
  status?: PatientStatus | string
  doctor_id?: string
  page?: number
  size?: number
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

export interface CreatePatientRequest {
  name: string
  email?: string
  phone?: string
  cpf?: string
  birth_date?: string
  gender?: 'M' | 'F' | 'other'
  address?: Patient['address']
  medical_info?: Patient['medical_info']
  // FIX: doctor_id is REQUIRED in backend schema (patient.py line 57: nullable=False)
  // Backend requires doctor_id for all new patients
  doctor_id: string
  timezone?: string
}

export interface UpdatePatientRequest extends Partial<CreatePatientRequest> {
  status?: PatientStatus | string
}

// ============================================================================
// API CLIENT INTERFACE
// ============================================================================

export interface ApiClient {
  // Authentication
  auth: {
    login: (credentials: LoginCredentials) => Promise<LoginResponse>
    logout: () => Promise<void>
    refresh: () => Promise<AuthTokens>
  }

  // Patients
  patients: {
    list: (params?: PatientQueryParams) => Promise<any>
    get: (id: string) => Promise<Patient>
    create: (data: CreatePatientRequest) => Promise<Patient>
    update: (id: string, data: UpdatePatientRequest) => Promise<Patient>
    delete: (id: string) => Promise<void>
    timeline: (id: string) => Promise<PatientTimeline>
  }

  // Messages
  messages: {
    list: (params?: MessageQueryParams) => Promise<any>
    send: (data: SendMessageRequest) => Promise<Message>
    sendBulk: (data: BulkMessageRequest) => Promise<any>
  }

  // Flows
  flows: {
    list: () => Promise<Flow[]>
    get: (id: string) => Promise<Flow>
    getState: (patientId: string) => Promise<FlowState>
  }

  // Alerts
  alerts: {
    list: (params?: AlertQueryParams) => Promise<any>
    create: (data: CreateAlertRequest) => Promise<Alert>
    acknowledge: (id: string) => Promise<void>
    resolve: (id: string) => Promise<void>
  }

  // Reports
  reports: {
    list: (params?: ReportQueryParams) => Promise<any>
    generate: (data: GenerateReportRequest) => Promise<Report>
    download: (id: string, format?: string) => Promise<Blob>
  }

  // Quiz
  quiz: {
    templates: () => Promise<QuizTemplate[]>
    sessions: (filters?: Record<string, unknown>) => Promise<any>
    getSession: (id: string) => Promise<QuizSession>
  }

  // Analytics
  analytics: {
    dashboard: () => Promise<DashboardAnalytics>
    engagement: (patientId?: string) => Promise<EngagementMetrics[]>
    flows: () => Promise<FlowMetrics[]>
  }
}

// ============================================================================
// AI ADVANCED TYPES (migrated from lib/types/ai.ts)
// ============================================================================

export interface ChatResponse {
  message: string
  confidence: number
  intent?: string
  entities?: Record<string, unknown>
  suggestions?: string[]
  requires_human_review?: boolean
}

export interface AIChatResponse extends ChatResponse {
  message: string
}

export interface AIRecommendation {
  id: string
  type: 'treatment' | 'communication' | 'follow_up' | 'alert'
  title: string
  description: string
  rationale: string
  confidence: number
  priority: 'low' | 'medium' | 'high'
  actions: RecommendedAction[]
  created_at: string
  updated_at?: string
  patient_id: string
}

export interface RecommendedAction {
  id: string
  type: 'message' | 'appointment' | 'medication' | 'test' | 'referral'
  title: string
  description: string
  urgency: 'low' | 'medium' | 'high'
  estimated_time?: string
  resources_needed?: string[]
}

export interface PatientEngagementMetrics {
  patient_id: string
  response_rate: number
  avg_response_time: number // in minutes
  sentiment_trend: SentimentTrend[]
  engagement_score: number // 0-100
  last_interaction: string
  total_interactions: number
  preferred_communication_time?: string
}

export interface SentimentTrend {
  date: string
  sentiment_score: number
  message_count: number
}

export interface AIAnalyticsDashboard {
  overview: {
    total_conversations: number
    avg_sentiment: number
    response_accuracy: number
    human_handoff_rate: number
  }
  engagement_metrics: PatientEngagementMetrics[]
  insights: AIInsight[]
  recommendations: AIRecommendation[]
  performance_trends: PerformanceTrend[]
}

export interface PerformanceTrend {
  date: string
  conversations: number
  avg_sentiment: number
  response_accuracy: number
  resolution_rate: number
  patient_id?: string
}

export interface AIFlowContext {
  patient_id: string
  flow_type: string
  current_day: number
  patient_data: Record<string, unknown>
  conversation_history: AIChatMessage[]
  preferences: PatientPreferences
}

export interface PatientPreferences {
  communication_style: 'formal' | 'casual' | 'empathetic'
  language: string
  timezone: string
  preferred_time: string
  topics_of_interest: string[]
  sensitivity_level: 'low' | 'medium' | 'high'
}

export interface AIGeneratedMessage {
  content: string
  confidence: number
  personalization_applied: string[]
  alternatives?: string[]
  metadata: {
    intent: string
    tone: string
    length: number
    complexity_level: 'simple' | 'medium' | 'complex'
  }
}

export interface AIEvent {
  type: 'insight_generated' | 'recommendation_created' | 'anomaly_detected' | 'sentiment_alert'
  patient_id?: string
  data: unknown
  timestamp: string
  priority: 'low' | 'medium' | 'high' | 'critical'
}

export interface AIConfig {
  openai_model: string
  temperature: number
  max_tokens: number
  response_format: 'text' | 'json'
  safety_filters: boolean
  personalization_level: 'low' | 'medium' | 'high'
  human_review_threshold: number
}

export interface AIError {
  code: string
  message: string
  details?: Record<string, unknown>
  retry_after?: number
}

export interface UseAIChatOptions {
  patient_id?: string
  auto_save?: boolean
  max_messages?: number
  enable_suggestions?: boolean
}

export interface UseAIAnalyticsOptions {
  refresh_interval?: number
  include_insights?: boolean
  include_recommendations?: boolean
}

export interface UseAIInsightsOptions {
  patient_id?: string
  timeframe?: 'day' | 'week' | 'month' | 'quarter'
  types?: InsightType[]
  min_confidence?: number
}

export interface AnalysisRequest {
  data: unknown
  analysis_type: 'sentiment' | 'pattern' | 'anomaly' | 'trend' | 'classification'
  parameters?: Record<string, unknown>
}

export interface AnalysisResult {
  type: string
  result: unknown
  confidence: number
  metadata: Record<string, unknown>
  created_at: string
}

// ============================================================================
// PATIENT SUMMARY TYPES (migrated from lib/types/patient-summary.ts)
// ============================================================================

export type SeverityLevel = 'low' | 'medium' | 'high' | 'critical'

export interface HealthConcern {
  concern: string
  severity: SeverityLevel
  detected_date?: string
  source?: string
}

export interface QuizFindings {
  total_completed: number
  total_questions_answered: number
  key_findings: string[]
  symptom_trends: Record<string, string>
  concerning_responses: string[]
}

export interface TreatmentCompliance {
  adherence_score: number
  missed_interactions: number
  notes?: string
}

export interface SummaryContent {
  overview: string
  quiz_findings: QuizFindings
  health_concerns: HealthConcern[]
  engagement_metrics: EngagementMetrics
  treatment_compliance: TreatmentCompliance
  recommendations: string[]
}

export interface PatientSummaryResponse {
  summary_id: string
  patient_id: string
  patient_name: string
  start_date: string
  end_date: string
  content: SummaryContent
  generated_at: string
  generated_by?: string
  token_usage?: number
  model_used?: string
  generation_time_ms?: number
  from_cache: boolean
}

export interface PatientSummaryListResponse {
  summaries: PatientSummaryResponse[]
  total: number
  has_more: boolean
}

export interface GenerateSummaryRequest {
  patient_id: string
  start_date: string
  end_date: string
  include_sections?: string[]
  force_refresh?: boolean
  save_summary?: boolean
}
