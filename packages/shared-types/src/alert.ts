// Shared Alert Types - Alert domain types for frontend and backend

/**
 * Alert severity - matches alert_severity type
 */
export type AlertSeverity = 'low' | 'medium' | 'high' | 'critical'

/**
 * Severity type - matches severity_type enum used in admin tables
 */
export enum SeverityType {
    LOW = 'low',
    MEDIUM = 'medium',
    HIGH = 'high',
    CRITICAL = 'critical'
}

/**
 * Alert status
 */
export type AlertStatus = 'pending' | 'acknowledged' | 'resolved' | 'dismissed'

/**
 * Core alert interface - matches alerts table
 */
export interface Alert {
    id: string
    patient_id?: string | null
    type: string
    severity: AlertSeverity
    message: string
    data?: Record<string, unknown>
    acknowledged: boolean
    acknowledged_by?: string | null
    acknowledged_at?: string | null
    created_at: string
    updated_at: string
    // Frontend display helpers
    title?: string
    patient_name?: string
    status?: AlertStatus
    resolved_at?: string
    resolved_by?: string
}

/**
 * Create alert request
 */
export interface CreateAlertRequest {
    type: string
    severity: AlertSeverity
    title?: string
    message: string
    patient_id?: string
    data?: Record<string, unknown>
}

/**
 * Update alert request
 */
export interface UpdateAlertRequest extends Partial<CreateAlertRequest> {
    status?: AlertStatus
    acknowledged?: boolean
}

/**
 * Unread count response
 */
export interface UnreadCountResponse {
    count: number
    by_severity?: Record<AlertSeverity, number>
}

/**
 * Alert list filters
 */
export interface AlertListFilters {
    type?: string
    severity?: AlertSeverity
    status?: AlertStatus
    patient_id?: string
    acknowledged?: boolean
    created_after?: string
    created_before?: string
    search?: string
    page?: number
    size?: number
    limit?: number
    cursor?: string
}
