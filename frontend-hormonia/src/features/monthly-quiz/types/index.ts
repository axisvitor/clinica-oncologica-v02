/**
 * Monthly Quiz Types for Frontend
 *
 * TypeScript type definitions for monthly quiz via link functionality.
 */

export enum DeliveryMethod {
  WHATSAPP = 'whatsapp',
  EMAIL = 'email',
  SMS = 'sms',
  MANUAL = 'manual'
}

export enum QuizLinkStatus {
  ACTIVE = 'active',
  EXPIRED = 'expired',
  USED = 'used',
  CANCELLED = 'cancelled'
}

export interface MonthlyQuizLinkCreate {
  patient_id: string;
  quiz_template_id: string;
  delivery_method?: DeliveryMethod;
  expiry_hours?: number;
  custom_message?: string;
}

export interface MonthlyQuizLink {
  id: string;
  patient_id: string;
  quiz_template_id: string;
  token: string;
  link_url: string;
  delivery_method: DeliveryMethod;
  status: QuizLinkStatus;
  expires_at: string;
  created_at: string;
  accessed_at?: string;
  completed_at?: string;
  access_count: number;
}

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
}

export interface MonthlyQuizSubmit {
  token: string;
  question_id: string;
  response_value: string;
  response_metadata?: Record<string, any>;
}

export interface MonthlyQuizStats {
  // New field names (primary - matches backend)
  total_sent: number;
  total_completed: number;
  total_expired: number;
  total_active: number;
  average_score: number;

  // Old field names (backward compatibility)
  total_links_created?: number;
  completed_quizzes?: number;
  expired_links?: number;
  active_links?: number;

  // Calculated metrics
  completion_rate: number;
  expiration_rate: number;

  // Optional fields
  average_completion_time?: number;
  delivery_methods_distribution?: Record<string, number>;
}

export interface BulkQuizLinkCreate {
  patient_ids: string[];
  quiz_template_id: string;
  delivery_method?: DeliveryMethod;
  expiry_hours?: number;
  custom_message?: string;
}

export interface BulkQuizLinkResponse {
  total_requested: number;
  total_created: number;
  total_failed: number;
  links: MonthlyQuizLink[];
  failures: Array<{ patient_id: string; error: string }>;
}