/**
 * Monthly Quiz Types for Frontend
 *
 * TypeScript type definitions for monthly quiz via link functionality.
 */

export type DeliveryMethod = 'whatsapp' | 'email' | 'sms' | 'manual'

// Re-export QuizLinkStatus from centralized types
export type { QuizLinkStatus, QuizLinkStatusValue } from '@/types/api'

// Deprecated local enum kept for compatibility if referenced elsewhere.
// Prefer the statuses from the API client types.
export enum _QuizLinkStatus {
  ACTIVE = 'active',
  EXPIRED = 'expired',
  USED = 'used',
  CANCELLED = 'cancelled'
}

export type MonthlyQuizLinkCreate = import('@/lib/api-client/monthly-quiz').QuizLinkCreate

export type MonthlyQuizLink = import('@/lib/api-client/monthly-quiz').QuizLink

export interface MonthlyQuizAccessRequest {
  token: string;
}

export interface MonthlyQuizAccess {
  quiz_session_id: string;
  patient_name: string;
  template_name: string;
  template_version: string;
  questions: any[];
  current_question_index: number;
  total_questions: number;
  expires_at: string;
  session_id?: string;
  quiz_template?: any;
  patient_id?: string;
}

export interface MonthlyQuizSubmit {
  token: string;
  question_id?: string;
  response_value?: string;
  response_metadata?: Record<string, any>;
  responses?: Record<string, any>;
}

export type MonthlyQuizStats = import('@/lib/api-client/monthly-quiz').QuizStats

export type BulkQuizLinkCreate = import('@/lib/api-client/monthly-quiz').QuizLinkBulkCreate

export interface BulkQuizLinkResponse {
  success: number;
  failed: number;
  links: MonthlyQuizLink[];
  errors?: Array<{ patient_id: string; error: string }>;
}
