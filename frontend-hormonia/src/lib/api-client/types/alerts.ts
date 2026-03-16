import type { SearchFilters } from './common'

export type AlertSeverity = 'low' | 'medium' | 'high' | 'critical'

export enum AlertType {
  INFO = 'info',
  WARNING = 'warning',
  ERROR = 'error',
  CRITICAL = 'critical',
}

export interface Alert {
  id: string
  type: string
  severity: AlertSeverity
  title: string
  message: string
  recommendation?: string
  patient_id?: string
  patient_name?: string
  status: 'pending' | 'acknowledged' | 'resolved' | 'dismissed'
  is_acknowledged?: boolean
  acknowledged_at?: string
  acknowledged_by?: string
  resolved_at?: string
  resolved_by?: string
  metadata?: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface AlertListFilters extends SearchFilters {
  type?: string
  severity?: AlertSeverity
  status?: Alert['status']
  patient_id?: string
  created_after?: string
  created_before?: string
}

export interface CreateAlertRequest {
  type: string
  severity: AlertSeverity
  title: string
  message: string
  patient_id?: string
  metadata?: Record<string, unknown>
}

export interface UpdateAlertRequest extends Partial<CreateAlertRequest> {
  status?: Alert['status']
}

export interface UnreadCountResponse {
  count: number
  by_severity?: Record<string, number>
}
