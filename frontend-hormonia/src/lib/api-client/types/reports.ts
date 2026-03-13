import type { SearchFilters } from './common'

export interface Report {
  id: string
  report_type: string
  name: string
  patient_id?: string
  format: 'pdf' | 'excel' | 'csv'
  status: 'pending' | 'generating' | 'completed' | 'failed'
  file_url?: string
  generated_at?: string
  generated_by?: string
  error_message?: string
  parameters?: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface ReportListFilters extends SearchFilters {
  report_type?: string
  status?: Report['status']
  patient_id?: string
  generated_after?: string
  generated_before?: string
}

export interface GenerateReportRequest {
  patient_id?: string
  report_type: string
  format?: 'pdf' | 'excel' | 'csv'
  parameters?: Record<string, unknown>
}

export interface ScheduleReportRequest {
  report_type: string
  frequency: 'daily' | 'weekly' | 'monthly'
  recipients: string[]
  parameters?: Record<string, unknown>
}

export interface ScheduledReport {
  id: string
  report_type: string
  frequency: string
  recipients: string[]
  next_run: string
  is_active: boolean
  created_at: string
}
