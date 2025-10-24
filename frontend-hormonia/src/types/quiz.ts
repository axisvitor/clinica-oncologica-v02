// Quiz System Types - Aligned with Backend API
//
// IMPORTANT: Response types must match backend QuestionType enum
// Valid values: multiple_choice, single_choice, open_text, scale, yes_no, date, number
// Backend also accepts: boolean, rating (validated in quiz.py line 574-580)

export enum QuestionType {
  MULTIPLE_CHOICE = 'multiple_choice',
  SINGLE_CHOICE = 'single_choice',
  OPEN_TEXT = 'open_text',
  SCALE = 'scale',
  YES_NO = 'yes_no',
  DATE = 'date',
  NUMBER = 'number',
  // Aliases for backend compatibility (validated by backend)
  BOOLEAN = 'boolean',
  RATING = 'rating'
}

export interface ValidationRule {
  type: string
  value: string | number | boolean | any[]
  message: string
}

export interface QuestionOption {
  id: string
  text: string
  value: string | number
  is_correct?: boolean
}

export interface QuizQuestion {
  id: string
  type: QuestionType
  text: string
  description?: string
  required: boolean
  options?: QuestionOption[]
  validation_rules?: ValidationRule[]
  metadata?: Record<string, any>
}

export interface QuizTemplate {
  id: string
  name: string
  version: string
  questions: QuizQuestion[]
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface QuizTemplateCreate {
  name: string
  version: string
  questions: QuizQuestion[]
  is_active?: boolean
}

export interface QuizTemplateUpdate {
  name?: string
  version?: string
  questions?: QuizQuestion[]
  is_active?: boolean
}

export interface QuizSession {
  id: string
  patient_id: string
  quiz_template_id: string
  current_question_index: number
  is_completed: boolean
  started_at: string
  completed_at?: string
  // Enriched fields from service
  patient_name?: string
  template_name?: string
  template_version?: string
  score?: number
}

export interface QuizSessionCreate {
  patient_id: string
  quiz_template_id: string
}

export interface QuizResponse {
  id: string
  patient_id: string
  quiz_template_id: string
  question_id: string
  question_text: string
  response_type: string
  response_value: string
  response_metadata: Record<string, any>
  responded_at: string
  created_at: string
}

export interface QuizResponseCreate {
  patient_id: string
  quiz_template_id: string
  question_id: string
  question_text: string
  response_type: QuestionType
  response_value: string
  response_metadata?: Record<string, any>
  responded_at: string
}

// Paginated response types
export interface QuizTemplateListResponse {
  items: QuizTemplate[]
  total: number
  page: number
  size: number
  // Backwards compatibility
  templates?: QuizTemplate[]
}

export interface QuizSessionListResponse {
  items: QuizSession[]
  total: number
  page: number
  size: number
  // Backwards compatibility
  sessions?: QuizSession[]
}

export interface QuizResponseListResponse {
  items: QuizResponse[]
  total: number
  page: number
  size: number
  // Backwards compatibility
  responses?: QuizResponse[]
}

// Quiz Response Viewer Types
export interface QuizResponseWithContext {
  id: string
  patient_id: string
  quiz_template_id: string
  quiz_session_id?: string
  question_id: string
  question_text: string
  response_type: string
  response_value: string
  response_metadata: Record<string, any>
  other_text?: string
  responded_at: string
  created_at: string
  // Additional context
  template_name?: string
  template_version?: string
  session_status?: string
}

export interface PatientQuizResponsesResponse {
  items: QuizResponseWithContext[]
  total: number
  page: number
  size: number
  pages: number
}

export interface QuizSessionWithResponses {
  id: string
  patient_id: string
  quiz_template_id: string
  status: string
  current_question: number
  total_questions?: number
  answered_questions?: number
  score?: number
  max_score?: number
  passed?: boolean
  started_at: string
  completed_at?: string
  time_spent_seconds?: number
  session_metadata: Record<string, any>
  // Template info
  template_name?: string
  template_version?: string
  // Responses
  responses: QuizResponseWithContext[]
}

export interface QuizAnalysisResponse {
  session_id: string
  patient_id: string
  template_name: string
  template_version: string
  completed_at?: string
  // AI Analysis
  risk_score?: number
  risk_level?: 'low' | 'medium' | 'high' | 'critical'
  sentiment_score?: number
  key_concerns: string[]
  recommendations: string[]
  // Response summary
  total_responses: number
  flagged_responses: number
}

export interface QuizAnalytics {
  quiz_template_id: string
  total_responses: number
  completion_rate: number
  average_completion_time?: number
  question_analytics: Record<string, any>[]
  trends: Record<string, any>
}

export interface PatientQuizAnalytics {
  patient_id: string
  total_quizzes_completed: number
  completion_rate: number
  average_score?: number
  recent_activity: Record<string, any>[]
  trends: Record<string, any>
}

export interface QuizValidationResult {
  is_valid: boolean
  errors: string[]
  warnings: string[]
}

// Re-export QuizLinkStatus types from centralized location
export type { QuizLinkStatus, QuizLinkStatusValue, MonthlyQuizStatusData as MonthlyQuizLinkStatus } from './api'

export interface MonthlyQuizLink {
  id: string
  patient_id: string
  patient_name: string
  quiz_template_id: string
  template_name: string
  template_version: string
  session_id: string
  status: 'active' | 'expired' | 'completed' | 'cancelled'
  sent_at: string
  expires_at: string
  completed_at?: string
  delivery_method: 'whatsapp' | 'email' | 'sms'
  custom_message?: string
}

export interface MonthlyQuizStats {
  total_sent: number
  total_completed: number
  total_expired: number
  total_active: number
  completion_rate: number
}

export interface CreateMonthlyQuizLinkRequest {
  patient_id: string
  quiz_template_id: string
  delivery_method: 'whatsapp' | 'email' | 'sms'
  expiry_hours: number
  custom_message?: string
}

export interface BulkCreateMonthlyQuizLinkRequest {
  patient_ids: string[]
  quiz_template_id: string
  delivery_method: 'whatsapp' | 'email' | 'sms'
  expiry_hours: number
  custom_message?: string
}