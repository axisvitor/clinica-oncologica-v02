// API types for the application
export enum FlowType {
  INITIAL_15_DAYS = 'initial_15_days',
  DAYS_16_45 = 'days_16_45',
  MONTHLY_RECURRING = 'monthly_recurring'
}

export enum FlowStatus {
  ACTIVE = 'active',
  PAUSED = 'paused',
  COMPLETED = 'completed',
  CANCELLED = 'cancelled'
}

export interface FlowState {
  id: string
  patient_id: string
  flow_type: FlowType
  status: FlowStatus
  current_day: number
  enrollment_date: string
  last_message_sent?: string
  state_data: Record<string, any>
}

// Re-export common types
export * from '../types/api'