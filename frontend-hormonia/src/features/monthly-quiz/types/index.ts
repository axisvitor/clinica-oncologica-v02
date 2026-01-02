/**
 * Monthly Quiz Types for Frontend
 *
 * TypeScript type definitions for monthly quiz via link functionality.
 */

export type DeliveryMethod = 'whatsapp' | 'email' | 'sms' | 'manual'

// Re-export QuizLinkStatus from centralized types
export type { QuizLinkStatus, QuizLinkStatusValue } from '@/types/api'

export type MonthlyQuizLinkCreate = import('@/lib/api-client/monthly-quiz').QuizLinkCreate

export type MonthlyQuizLink = import('@/lib/api-client/monthly-quiz').QuizLink

export interface MonthlyQuizAccessRequest {
  token: string;
}

export interface QuizQuestionOption {
  id: string;
  text: string;
  value?: string | number;
  is_correct?: boolean;
}

export interface QuizValidationRule {
  type?: string;
  min?: number;
  max?: number;
  value?: string | number | boolean;
  message?: string;
}

export interface QuizQuestionData {
  id: string;
  type: string;
  text: string;
  description?: string;
  required?: boolean;
  options?: QuizQuestionOption[];
  validation_rules?: QuizValidationRule[];
  metadata?: Record<string, unknown>;
}

export interface MonthlyQuizAccess {
  quiz_id: string; // Added to match backend response
  quiz_session_id: string;
  patient_name: string;
  template_name: string;
  template_version: string;
  questions: QuizQuestionData[];
  current_question_index: number;
  total_questions: number;
  expires_at: string;
  session_id?: string;
  quiz_template?: Record<string, unknown>;
  patient_id?: string;
}

export interface MonthlyQuizSubmit {
  token: string;
  quiz_id: string; // Added for URL parameter
  question_id?: string;
  response_value?: string;
  response_metadata?: Record<string, unknown>;
  responses?: Record<string, unknown>;
}

export type MonthlyQuizStats = import('@/lib/api-client/monthly-quiz').QuizStats

export type BulkQuizLinkCreate = import('@/lib/api-client/monthly-quiz').QuizLinkBulkCreate

export interface BulkQuizLinkResponse {
  success: number;
  failed: number;
  links: MonthlyQuizLink[];
  errors?: Array<{ patient_id: string; error: string }>;
}
