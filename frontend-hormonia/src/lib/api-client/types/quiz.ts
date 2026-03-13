import type { SearchFilters } from './common'

export interface QuestionOption {
  id: string
  text: string
  value: string | number
  is_correct?: boolean
}

export interface QuizQuestion {
  id: string
  type: 'multiple_choice' | 'open_text' | 'scale' | 'yes_no' | 'date' | 'number'
  text: string
  description?: string
  required: boolean
  options?: QuestionOption[]
}

export interface QuizTemplate {
  id: string
  name: string
  version: string
  description?: string
  questions: QuizQuestion[]
  questions_count?: number
  estimated_duration_minutes?: number
  is_active: boolean
  created_at: string
  updated_at: string
  analytics?: {
    total_responses?: number
    completion_rate?: number
    average_completion_time?: number
  }
}

export interface QuizTemplateResponse {
  items: QuizTemplate[]
}

export interface QuizSessionStartRequest {
  patient_id: string
  quiz_template_id: string
}

export interface QuizSession {
  id: string
  patient_id: string
  patient_name?: string
  quiz_template_id: string
  template_name?: string
  status: 'pending' | 'in_progress' | 'completed' | 'abandoned'
  is_completed?: boolean
  started_at?: string
  completed_at?: string
  score?: number
  created_at: string
  updated_at: string
}

export interface QuizSubmitRequest {
  question_id: string
  answer: string | string[]
  response_metadata?: Record<string, unknown>
}

export interface QuizResponse {
  id: string
  session_id: string
  question_id: string
  answer: string | string[]
  answered_at: string
}

export interface QuizSessionListFilters extends SearchFilters {
  patient_id?: string
  template_id?: string
  status?: QuizSession['status']
  started_after?: string
  started_before?: string
}

export interface QuizSessionResponses {
  session_id: string
  responses: QuizResponse[]
  total_questions: number
  answered_questions: number
}

export interface QuizSessionAnalysis {
  session_id: string
  score: number
  total_questions: number
  correct_answers: number
  analysis: Record<string, unknown>
}

export interface PatientQuizResponses {
  patient_id: string
  sessions: QuizSession[]
  total: number
}
