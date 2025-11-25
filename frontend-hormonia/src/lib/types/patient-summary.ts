/**
 * Patient Summary Types
 *
 * Types for AI-generated patient summaries.
 */

export type SeverityLevel = 'low' | 'medium' | 'high' | 'critical';

export interface HealthConcern {
  concern: string;
  severity: SeverityLevel;
  detected_date?: string;
  source?: string;
}

export interface QuizFindings {
  total_completed: number;
  total_questions_answered: number;
  key_findings: string[];
  symptom_trends: Record<string, string>;
  concerning_responses: string[];
}

export interface EngagementMetrics {
  response_rate: number;
  avg_response_time_minutes: number;
  total_messages_sent: number;
  total_messages_received: number;
  engagement_score: number;
}

export interface TreatmentCompliance {
  adherence_score: number;
  missed_interactions: number;
  notes?: string;
}

export interface SummaryContent {
  overview: string;
  quiz_findings: QuizFindings;
  health_concerns: HealthConcern[];
  engagement_metrics: EngagementMetrics;
  treatment_compliance: TreatmentCompliance;
  recommendations: string[];
}

export interface PatientSummaryResponse {
  summary_id: string;
  patient_id: string;
  patient_name: string;
  start_date: string;
  end_date: string;
  content: SummaryContent;
  generated_at: string;
  generated_by?: string;
  token_usage?: number;
  model_used?: string;
  generation_time_ms?: number;
  from_cache: boolean;
}

export interface PatientSummaryListResponse {
  summaries: PatientSummaryResponse[];
  total: number;
  has_more: boolean;
}

export interface GenerateSummaryRequest {
  patient_id: string;
  start_date: string;
  end_date: string;
  include_sections?: string[];
  force_refresh?: boolean;
  save_summary?: boolean;
}
