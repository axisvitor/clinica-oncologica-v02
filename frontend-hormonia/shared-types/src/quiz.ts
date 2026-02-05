// Shared Quiz Types

export enum QuestionType {
    MULTIPLE_CHOICE = 'multiple_choice',
    SINGLE_CHOICE = 'single_choice',
    OPEN_TEXT = 'open_text',
    SCALE = 'scale',
    YES_NO = 'yes_no',
    DATE = 'date',
    NUMBER = 'number',
    // Aliases for backend compatibility
    BOOLEAN = 'boolean',
    RATING = 'rating',
    TEXT = 'text'
}

export interface QuestionOption {
    id: string
    text: string
    value: string | number
    is_correct?: boolean
    allow_other?: boolean
}

export interface ValidationRule {
    type: string
    value: string | number | boolean | unknown[]
    message: string
}

export interface QuizQuestion {
    id: string
    type: QuestionType
    text: string
    description?: string
    required: boolean
    options?: QuestionOption[]
    validation_rules?: ValidationRule[]
    metadata?: Record<string, unknown>
    min_value?: number
    max_value?: number
    allow_other?: boolean
}

export interface QuizTemplate {
    id: string
    name: string
    version: string
    questions: QuizQuestion[]
    is_active: boolean
    created_at: string
    updated_at: string
}

export interface QuizSession {
    quiz_session_id: string
    patient_name: string
    template_name: string
    template_version: string
    questions: QuizQuestion[]
    current_question_index: number
    total_questions: number
    expires_at: string
    new_token?: string
    status?: string
}

export interface QuizResponse {
    id: string
    patient_id: string
    quiz_template_id: string
    question_id: string
    question_text: string
    response_type: string
    response_value: string | number | boolean | string[] | Record<string, unknown>
    response_metadata: Record<string, unknown>
    responded_at: string
    created_at: string
}

export interface QuizSubmitRequest {
    token: string
    question_id: string
    response_value: string | number | boolean | string[] | Record<string, unknown>
    other_text?: string
    response_metadata?: Record<string, unknown>
}

export interface QuizSubmitResponse {
    success: boolean
    response_id?: string
    message: string
    is_last_question?: boolean
    new_token?: string
}
