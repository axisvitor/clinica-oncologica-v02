/**
 * Alert Types and Interfaces
 *
 * Type definitions specific to the alerts feature.
 * These extend the base Alert type from api-client with UI-specific types.
 */

import type { Alert as BaseAlert } from '@/lib/api-client/types'

/**
 * Alert severity levels
 * Maps to backend severity values
 */
export type AlertSeverity = 'low' | 'medium' | 'high' | 'critical'

/**
 * Alert type categories
 * Common alert types used throughout the application
 */
export type AlertType =
  | 'system'
  | 'medical'
  | 'engagement'
  | 'patient'
  | 'medication'
  | 'appointment'
  | 'quiz'
  | 'notification'

/**
 * Alert interface extending base type with UI-specific fields
 */
export interface Alert extends BaseAlert {
  patient_name?: string
  is_acknowledged?: boolean
}

/**
 * Filter parameters for alert lists
 */
export interface AlertFilters {
  type?: AlertType
  severity?: AlertSeverity
  status?: 'pending' | 'acknowledged' | 'resolved' | 'dismissed'
  patient_id?: string
  created_after?: string
  created_before?: string
  search?: string
  page?: number
  size?: number
}

/**
 * Alert statistics for dashboard
 */
export interface AlertStats {
  total: number
  unread: number
  by_severity: Record<AlertSeverity, number>
  by_type: Record<string, number>
}
