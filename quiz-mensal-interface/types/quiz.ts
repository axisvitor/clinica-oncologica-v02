export interface OtherAnswer {
  value: string
  customText: string
}

export type SingleAnswer = string | OtherAnswer
export type MultipleAnswer = string[] | { options: string[]; otherText?: string }

export interface QuizUIState {
  isLoading: boolean
  error: QuizError | null
  currentQuestionIndex: number
  selectedAnswer: SingleAnswer | MultipleAnswer | null
  answers: Map<string, SingleAnswer | MultipleAnswer>
  otherTexts: Map<string, string>
}

export interface MonthlyQuizLink {
  id: string
  patient_id: string
  template_id: string
  access_url: string
  expires_at: string
  created_at: string
  is_active: boolean
  patient_name?: string
  patient_phone?: string
  template_name?: string
  template_version?: string
  session_id?: string
  status?: 'active' | 'completed' | 'expired'
}

export interface MonthlyQuizStats {
  total_links_created: number
  active_links: number
  expired_links: number
  completed_quizzes: number
  completion_rate: number
  average_completion_time?: number
  delivery_methods_distribution?: Record<string, number>
}

export interface QuizError {
  message?: string
  detail?: string
  code?: string
  status?: number
}

export type QuestionType =
  | 'single_choice'
  | 'multiple_choice'
  | 'scale'
  | 'text'
  | 'free_text'
  | 'yes_no'

export interface QuizQuestion {
  id: string
  text: string
  type: QuestionType
  options?: (string | { id?: string; value: string; text: string; allow_other?: boolean })[]
  min_value?: number
  max_value?: number
  allow_other?: boolean
  required?: boolean
}

export interface QuizSession {
  id: string
  quiz_session_id: string
  patient_id: string
  template_id: string
  patient_name: string
  template_name: string
  expires_at: string
  questions: QuizQuestion[]
  created_at?: string
  completed_at?: string
  status?: string
  new_token?: string
  current_question_index?: number
}

export interface QuizAccessRequest {
  token: string
}

export interface QuizSubmitRequest {
  token: string
  question_id: string
  response_value: string | string[]
  response_metadata?: Record<string, unknown>
  other_text?: string
}

export interface QuizSubmitResponse {
  success: boolean
  is_last_question: boolean
  next_question?: QuizQuestion
  session_status: string
  message?: string
  response_id?: string
  new_token?: string
}
