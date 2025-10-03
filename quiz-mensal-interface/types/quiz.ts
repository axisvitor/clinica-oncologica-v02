/**
 * Type definitions for Monthly Quiz Interface
 * Aligns with Backend API schemas
 */

export enum QuestionType {
  SINGLE_CHOICE = "single_choice",
  MULTIPLE_CHOICE = "multiple_choice",
  SCALE = "scale",
  TEXT = "text",
  YES_NO = "yes_no"
}

export interface QuestionOption {
  id: string
  text: string
  value: string
  is_correct?: boolean
  allow_other?: boolean
}

export interface QuizQuestion {
  id: string
  text: string
  type: QuestionType
  options?: QuestionOption[]  // Changed from string[] to QuestionOption[]
  min_value?: number
  max_value?: number
  required: boolean
  allow_other?: boolean
  metadata?: Record<string, any>
}

export interface QuizSession {
  quiz_session_id: string
  patient_name: string
  template_name: string
  template_version: string
  questions: QuizQuestion[]
  current_question_index: number
  total_questions: number
  expires_at: string
  new_token?: string  // NEW: For token rotation
}

export interface QuizAccessRequest {
  token: string
}

export interface QuizSubmitRequest {
  token: string
  question_id: string
  response_value: string | string[]  // Accept both string and array
  other_text?: string
  response_metadata?: Record<string, any>
}

export interface QuizSubmitResponse {
  success: boolean
  response_id?: string
  message: string
  is_last_question?: boolean
  new_token?: string  // NEW: For token rotation
}

export interface QuizError {
  detail: string
  status?: number
}

// UI State types
export interface OtherAnswer {
  value: string  // Changed from hardcoded "OUTRA" to dynamic value
  customText: string
}

export type SingleAnswer = string | OtherAnswer
export type MultipleAnswer = string[] | { options: string[], otherText?: string }

export interface QuizUIState {
  isLoading: boolean
  error: QuizError | null
  currentQuestionIndex: number
  selectedAnswer: SingleAnswer | MultipleAnswer | null
  answers: Map<string, SingleAnswer | MultipleAnswer>
  otherTexts: Map<string, string>
}

// Dashboard types - matches backend MonthlyQuizLinkRead schema
export interface MonthlyQuizLink {
  id: string
  patient_id: string
  template_id: string
  access_url: string
  expires_at: string
  created_at: string  // Use this instead of sent_at
  is_active: boolean
  patient_name?: string
  patient_phone?: string
  template_name?: string
  template_version?: string
  session_id?: string
  status?: 'active' | 'completed' | 'expired'
}

export interface MonthlyQuizStats {
  total_sent: number  // Changed from total_links_created
  total_completed: number  // Changed from completed_quizzes
  expired_links: number
  active_links: number
}