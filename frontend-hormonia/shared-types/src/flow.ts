// Shared Flow Types - Flow domain types for frontend and backend

/**
 * Flow type enum
 */
export enum FlowType {
    ONBOARDING = 'onboarding',
    DAILY_FOLLOW_UP = 'daily_follow_up',
    QUIZ_MENSAL = 'quiz_mensal',
    CUSTOM = 'custom',
    // Legacy keys for backward compatibility
    INITIAL_15_DAYS = 'initial_15_days',
    DAYS_16_45 = 'days_16_45',
    MONTHLY_RECURRING = 'monthly_recurring',
    MONTHLY_QUIZ = 'monthly_quiz',
    DAILY_CHECKIN = 'daily_checkin',
    DAILY_ENGAGEMENT = 'daily_engagement'
}

/**
 * Flow status enum
 */
export enum FlowStatus {
    ACTIVE = 'active',
    PAUSED = 'paused',
    COMPLETED = 'completed',
    CANCELLED = 'cancelled'
}

/**
 * Response type enum
 */
export enum ResponseType {
    TEXT = 'text',
    BUTTON = 'button',
    QUICK_REPLY = 'quick_reply',
    LIST = 'list'
}

/**
 * Condition for flow logic
 */
export interface FlowCondition {
    field: string
    operator: 'equals' | 'not_equals' | 'contains' | 'greater_than' | 'less_than'
    value: unknown
}

/**
 * Interactive elements for messages
 */
export interface InteractiveElements {
    buttons?: Array<{ id: string; text: string; action: string }>
    quick_replies?: string[]
    list_items?: Array<{ id: string; title: string; description?: string }>
}

/**
 * Follow-up action configuration
 */
export interface FollowUpAction {
    intent: string
    delay_seconds: number
    ai_instructions?: string
    conditions?: FlowCondition[]
}

/**
 * Message template for flows
 */
export interface MessageTemplate {
    id: string
    day: number
    content: string
    message_type: string
    interactive_elements?: InteractiveElements
    conditions?: FlowCondition[]
    personalization_hints: string[]
    ai_instructions?: string
    follow_up?: FollowUpAction[]
}

/**
 * Flow step definition
 */
export interface FlowStep {
    id: string
    day: number
    message_template: string
    conditions?: Record<string, unknown>
    metadata?: Record<string, unknown>
}

/**
 * Flow template - matches flow_template_versions table
 */
export interface FlowTemplate {
    id: string
    name: string
    description?: string | null
    flow_type: FlowType | string
    is_active: boolean
    steps: FlowStep[]
    settings?: Record<string, unknown>
    messages?: Record<number, MessageTemplate>
    metadata?: Record<string, unknown>
    humanization_level?: string
    created_at: string
    updated_at: string
}

/**
 * Flow state - patient's current flow status
 */
export interface FlowState {
    id: string
    patient_id: string
    template_id: string
    flow_type: FlowType | string
    current_day: number
    enrollment_date: string
    last_message_sent?: string | null
    state_data: Record<string, unknown>
    sentiment_score?: number | null
    requires_attention?: boolean
    status: FlowStatus | string
    started_at: string
    paused_at?: string | null
    completed_at?: string | null
    metadata?: Record<string, unknown>
    patient_name?: string
    monthly_cycle?: number
}

/**
 * Response processing result
 */
export interface ResponseResult {
    response_type: ResponseType | string
    extracted_data: Record<string, unknown>
    sentiment_score: number
    requires_attention: boolean
    follow_up_actions: FollowUpAction[]
}

/**
 * Flow analytics summary
 */
export interface FlowAnalytics {
    total_flows: number
    active_flows: number
    paused_flows?: number
    completed_flows: number
    completion_rate: number
    average_duration_days: number
    by_type?: Record<string, number>
    total_active_flows?: number
    engagement_rate?: number
    average_response_time?: number
    flows_by_type?: Record<string, number>
    daily_metrics?: DailyMetric[]
    status_distribution?: Record<string, number>
    new_patients_7d?: number
    avg_response_time_minutes?: number
    weekly_trend?: Array<Record<string, unknown>>
    template_completion_rates?: TemplateCompletionRate[]
    template_duration_days?: TemplateDurationMetric[]
}

/** 
 * Daily metric data point 
 */
export interface DailyMetric {
    date: string
    messages_sent: number
    responses_received: number
    new_enrollments: number
    completions: number
    active_flows?: number
}

export interface TemplateCompletionRate {
    template_id: string
    template_name: string
    kind_key: string
    version_number: number
    total: number
    completed: number
    completion_rate: number
}

export interface TemplateDurationMetric {
    template_id: string
    template_name: string
    kind_key: string
    version_number: number
    average_duration_days: number
}

/**
 * Create flow template request
 */
export interface CreateFlowTemplateRequest {
    name: string
    description?: string
    flow_type: FlowType | string
    steps: Omit<FlowStep, 'id'>[]
    settings?: Record<string, unknown>
}

/**
 * Update flow template request
 */
export interface UpdateFlowTemplateRequest extends Partial<Omit<CreateFlowTemplateRequest, 'steps'>> {
    steps?: (FlowStep | Omit<FlowStep, 'id'>)[]
    is_active?: boolean
}

/**
 * Flow list filters
 */
export interface FlowListFilters {
    flow_type?: FlowType | string
    is_active?: boolean
    search?: string
    page?: number
    size?: number
    limit?: number
    cursor?: string
}
