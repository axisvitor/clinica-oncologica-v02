/**
 * API Response Types
 *
 * Define interfaces for backend API responses to improve type safety
 * while maintaining compatibility with existing response transformers.
 */

// ============================================================================
// Generic Response Types
// ============================================================================

export interface ApiResponse<T> {
  data: T
  message?: string
  timestamp: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

export interface ApiError {
  status: number
  message: string
  detail?: string
  errors?: Record<string, string[]>
}

// ============================================================================
// Auth Response Types
// ============================================================================

export interface AuthUser {
  id: string
  email: string
  full_name: string
  role: string
  is_active: boolean
  created_at?: string
  updated_at?: string
}

export interface AuthMeResponse {
  id: string
  email: string
  full_name: string
  role: string
  is_active: boolean
}

export interface LogoutResponse {
  message: string
}

// ============================================================================
// Patient Response Types
// ============================================================================

export interface Patient {
  id: string
  name: string
  email?: string
  phone?: string
  birth_date?: string
  cpf?: string
  treatment_type?: string
  treatment_start_date?: string
  current_day?: number
  status: 'active' | 'inactive' | 'completed'
  created_at: string
  updated_at: string
  metadata?: Record<string, unknown>
}

export interface PatientListResponse {
  data: Patient[]
  total: number
  page: number
  limit: number
  pages: number
}

export interface TimelineEvent {
  id: string
  patient_id: string
  event_type: string
  title: string
  description?: string
  created_at: string
  metadata?: Record<string, unknown>
}

export interface PatientTimelineResponse {
  events: TimelineEvent[]
  total: number
}

// ============================================================================
// Message Response Types
// ============================================================================

export interface Message {
  id: string
  patient_id: string
  content: string
  type: string
  direction: 'inbound' | 'outbound'
  status: 'pending' | 'sent' | 'delivered' | 'failed'
  scheduled_for?: string
  sent_at?: string
  created_at: string
  metadata?: Record<string, unknown>
}

export interface MessageListResponse {
  messages: Message[]
  total: number
  skip: number
  limit: number
}

export interface SendMessageRequest {
  patient_id: string
  content: string
  type?: string
  scheduled_for?: string
}

export interface SendMessageResponse {
  id: string
  message: string
  scheduled_for?: string
}

// ============================================================================
// Flow Response Types
// ============================================================================

export interface Flow {
  id: string
  patient_id: string
  flow_type: string
  status: 'active' | 'paused' | 'completed' | 'cancelled'
  current_day?: number
  started_at: string
  completed_at?: string
  metadata?: Record<string, unknown>
}

export interface FlowState {
  patient_id: string
  flow_type: string
  status: string
  current_day: number
  next_message_date?: string
  total_days?: number
}

export interface FlowTemplate {
  id: string
  name: string
  description?: string
  flow_type: string
  total_days: number
  is_active: boolean
  created_at: string
  updated_at: string
}

// ============================================================================
// Analytics Response Types
// ============================================================================

export interface DashboardAnalytics {
  total_patients: number
  active_patients: number
  total_messages: number
  engagement_rate: number
  recent_activity: unknown[]
}

export interface PatientAnalytics {
  patient_id: string
  total_messages: number
  response_rate: number
  engagement_score: number
  last_interaction?: string
}

export interface EngagementAnalytics {
  period: string
  total_interactions: number
  unique_patients: number
  average_response_time: number
  engagement_trend: Array<{
    date: string
    count: number
  }>
}

// ============================================================================
// Alert Response Types
// ============================================================================

export interface Alert {
  id: string
  patient_id?: string
  type: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  title: string
  message: string
  acknowledged: boolean
  resolved: boolean
  created_at: string
  acknowledged_at?: string
  resolved_at?: string
  metadata?: Record<string, unknown>
}

export interface CreateAlertRequest {
  patient_id?: string
  type: string
  severity: string
  title: string
  message: string
  metadata?: Record<string, unknown>
}

// ============================================================================
// Report Response Types
// ============================================================================

export interface Report {
  id: string
  patient_id?: string
  type: string
  title: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  file_path?: string
  created_at: string
  completed_at?: string
  metadata?: Record<string, unknown>
}

export interface GenerateReportRequest {
  patient_id: string
  type: string
  config?: Record<string, unknown>
}

// ============================================================================
// Quiz Response Types
// ============================================================================

export interface QuizTemplate {
  id: string
  name: string
  version: string
  description?: string
  questions: QuizQuestion[]
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface QuizQuestion {
  id: string
  type: 'multiple_choice' | 'open_text' | 'scale' | 'yes_no' | 'date' | 'number'
  text: string
  description?: string
  required: boolean
  options?: QuestionOption[]
  validation_rules?: ValidationRule[]
  metadata?: Record<string, unknown>
}

export interface QuestionOption {
  id: string
  text: string
  value: string | number
  is_correct?: boolean
}

export interface ValidationRule {
  type: string
  value: unknown
  message: string
}

export interface QuizSession {
  id: string
  patient_id: string
  quiz_template_id: string
  status: 'pending' | 'in_progress' | 'completed' | 'expired'
  started_at?: string
  completed_at?: string
  responses?: Record<string, unknown>
  score?: number
}

export interface QuizTemplateListResponse {
  items: QuizTemplate[]
  total: number
  page: number
  size: number
}

export interface QuizSessionListResponse {
  items: QuizSession[]
  total: number
  page: number
  size: number
}

// ============================================================================
// Monthly Quiz Response Types
// ============================================================================

export interface MonthlyQuizLink {
  session_id: string
  patient_id: string
  quiz_template_id: string
  link: string
  status: 'active' | 'completed' | 'expired' | 'cancelled'
  expires_at: string
  created_at: string
  completed_at?: string
}

export interface CreateQuizLinkRequest {
  patient_id: string
  quiz_template_id: string
  delivery_method?: string
  expiry_hours?: number
  custom_message?: string
}

export interface BulkCreateQuizLinkRequest {
  patient_ids: string[]
  quiz_template_id: string
  delivery_method?: string
  expiry_hours?: number
  custom_message?: string
}

export interface QuizLinkStatus {
  session_id: string
  patient_id: string
  status: string
  link: string
  expires_at: string
  completed_at?: string
  responses?: Record<string, unknown>
}

export interface MonthlyQuizStats {
  total_sent: number
  total_completed: number
  total_expired: number
  total_active: number
  average_score: number
  completion_rate: number
  expiration_rate: number
}

// ============================================================================
// Admin User Management Response Types
// ============================================================================

export interface AdminUser {
  id: string
  email: string
  full_name: string
  role: string
  is_active: boolean
  permissions?: string[]
  created_at: string
  updated_at: string
  last_login?: string
}

export interface UserActivity {
  id: string
  user_id: string
  action: string
  resource?: string
  details?: Record<string, unknown>
  ip_address?: string
  user_agent?: string
  created_at: string
}

export interface CreateUserRequest {
  email: string
  full_name: string
  role: string
  password?: string
  is_active?: boolean
  permissions?: string[]
}

export interface UpdateUserRequest {
  email?: string
  full_name?: string
  role?: string
  is_active?: boolean
  permissions?: string[]
}

export interface ResetPasswordResponse {
  temporary_password: string
  message: string
}

// ============================================================================
// AI Response Types
// ============================================================================

export interface AIChatResponse {
  message: string
  intent?: string
  confidence?: number
  suggestions?: string[]
}

export interface AIAnalysisResponse {
  analysis_type: string
  results: Record<string, unknown>
  confidence: number
  recommendations?: string[]
}

export interface AISentimentResponse {
  sentiment: 'positive' | 'neutral' | 'negative'
  score: number
  confidence: number
}

export interface AIInsights {
  patient_id: string
  insights: Array<{
    type: string
    title: string
    description: string
    priority: 'low' | 'medium' | 'high'
    confidence: number
  }>
  timeframe: string
  generated_at: string
}

export interface AIRecommendations {
  patient_id: string
  recommendations: Array<{
    type: string
    title: string
    description: string
    priority: 'low' | 'medium' | 'high'
    rationale: string
  }>
  generated_at: string
}
