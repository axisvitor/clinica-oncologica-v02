// Shared Patient Types - Patient domain types for frontend and backend

/**
 * Patient flow state enum - matches PostgreSQL flow_state type
 */
export enum PatientFlowState {
    ONBOARDING = 'onboarding',
    ACTIVE = 'active',
    PAUSED = 'paused',
    COMPLETED = 'completed',
    INACTIVE = 'inactive',
    CANCELLED = 'cancelled'
}

/**
 * Core patient interface - matches patients table
 */
export interface Patient {
    id: string
    doctor_id: string
    phone: string
    name: string
    email?: string | null
    birth_date?: string | null
    treatment_type?: string | null
    treatment_start_date?: string | null
    treatment_phase?: string | null
    diagnosis?: string | null
    flow_state: PatientFlowState | string
    current_day: number
    cpf?: string | null
    doctor_notes?: string | null
    metadata?: Record<string, unknown>
    created_at: string
    updated_at: string
    deleted_at?: string | null
}

/**
 * Patient create request
 */
export interface CreatePatientRequest {
    name: string
    phone: string
    email?: string
    cpf?: string
    birth_date?: string
    treatment_type?: string
    treatment_start_date?: string
    treatment_phase?: string
    diagnosis?: string
    doctor_notes?: string
    metadata?: Record<string, unknown>
}

/**
 * Patient update request
 */
export interface UpdatePatientRequest extends Partial<CreatePatientRequest> {
    flow_state?: PatientFlowState | string
    current_day?: number
}

/**
 * Patient list filters
 */
export interface PatientListFilters {
    search?: string
    flow_state?: PatientFlowState | string
    treatment_type?: string
    treatment_phase?: string
    has_active_flow?: boolean
    page?: number
    size?: number
    limit?: number
    cursor?: string
}

/**
 * Patient risk assessment
 */
export interface PatientRiskAssessment {
    patient_id: string
    patient_name?: string
    risk_level: 'low' | 'medium' | 'high' | 'critical'
    risk_score?: number
    risk_factors: string[]
    last_response?: string | null
    recommended_actions: string[]
    assessed_at?: string
}

/**
 * Patient onboarding saga status - matches saga_status type
 */
export enum OnboardingSagaStatus {
    STARTED = 'STARTED',
    STEP_1_PATIENT_CREATED = 'STEP_1_PATIENT_CREATED',
    STEP_2_FIREBASE_USER_CREATED = 'STEP_2_FIREBASE_USER_CREATED',
    STEP_3_FLOW_INITIALIZED = 'STEP_3_FLOW_INITIALIZED',
    STEP_4_MESSAGE_SENT = 'STEP_4_MESSAGE_SENT',
    COMPLETED = 'COMPLETED',
    FAILED = 'FAILED',
    COMPENSATING = 'COMPENSATING',
    COMPENSATED = 'COMPENSATED',
    RETRY_SCHEDULED = 'RETRY_SCHEDULED'
}
