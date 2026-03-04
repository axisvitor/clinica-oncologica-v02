import type { QuizQuestion, QuestionType, QuizTemplate } from './shared-quiz'

// Import QuizSession from canonical source or shared types
// For now, we'll use the shared type if available, or keep the local re-export pattern if it depends on api-client
import type { QuizSession } from '@/lib/api-client/types'

export type { QuizSession }

export interface QuizTemplateUpdate {
  name?: string
  version?: string
  questions?: QuizQuestion[]
  is_active?: boolean
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
  // FIX: Backend uses Text column that accepts any value, not just string
  // Backend model (quiz.py line 191): Column(Text, nullable=False)
  // Backend check constraint allows: multiple_choice, open_text, scale, boolean, rating, yes_no, number, date, single_choice
  // Response value can be: string, number, boolean, array (for multiple_choice), object (for complex responses)
  response_value: string | number | boolean | string[] | Record<string, unknown>
  response_metadata: Record<string, unknown>
  responded_at: string
  created_at: string
}

export interface QuizResponseCreate {
  patient_id: string
  quiz_template_id: string
  question_id: string
  question_text: string
  response_type: QuestionType
  // FIX: Match QuizResponse type - backend accepts multiple value types
  // Backend model (quiz.py line 191): Column(Text, nullable=False)
  // Response value type depends on response_type: string for text, number for scale/rating, boolean for yes_no, array for multiple_choice
  response_value: string | number | boolean | string[] | Record<string, unknown>
  response_metadata?: Record<string, unknown>
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
  // FIX: Match QuizResponse type - backend accepts multiple value types
  response_value: string | number | boolean | string[] | Record<string, unknown>
  response_metadata: Record<string, unknown>
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
  session_metadata: Record<string, unknown>
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
  question_analytics: Record<string, unknown>[]
  trends: Record<string, unknown>
}

export interface PatientQuizAnalytics {
  patient_id: string
  total_quizzes_completed: number
  completion_rate: number
  average_score?: number
  recent_activity: Record<string, unknown>[]
  trends: Record<string, unknown>
}

export interface QuizValidationResult {
  is_valid: boolean
  errors: string[]
  warnings: string[]
}

// Re-export QuizLinkStatus types from centralized location
export type {
  QuizLinkStatus,
  QuizLinkStatusValue,
  MonthlyQuizStatusData as MonthlyQuizLinkStatus,
} from './api'

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
