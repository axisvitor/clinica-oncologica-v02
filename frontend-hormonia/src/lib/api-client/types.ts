/**
 * Shared API Client Types
 *
 * Common types used across all API client modules for consistent type safety.
 */

// ============================================================================
// COMMON API RESPONSE TYPES
// ============================================================================

/**
 * Standard API response wrapper
 */
export interface ApiResponse<T> {
  data: T;
  message?: string;
  success: boolean;
  timestamp?: string;
}

/**
 * Paginated response with cursor support (V2 API)
 */
export interface PaginatedResponse<T> {
  data: T[];
  items?: T[]; // Backward compatibility
  pagination?: {
    page: number;
    limit: number;
    total: number;
    hasMore: boolean;
  };
  // V2 cursor pagination
  total?: number;
  page?: number;
  size?: number;
  pages?: number;
  has_more?: boolean;
  next_cursor?: string | null;
}

/**
 * Error response structure
 */
export interface ApiErrorResponse {
  error: {
    message: string;
    code: string;
    details?: Record<string, unknown>;
  };
  timestamp?: string;
}

// ============================================================================
// COMMON ID AND FILTER TYPES
// ============================================================================

/**
 * Entity ID type (string or number)
 */
export type EntityId = string | number;

/**
 * Base filter parameters
 */
export interface BaseFilters {
  page?: number;
  size?: number;
  limit?: number;
  cursor?: string;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}

/**
 * Search filters with text search
 */
export interface SearchFilters extends BaseFilters {
  search?: string;
  q?: string;
}

/**
 * Time-based filters
 */
export interface TimeRangeFilters {
  start_date?: string;
  end_date?: string;
  created_after?: string;
  created_before?: string;
}

// ============================================================================
// COMMON CRUD RESPONSE TYPES
// ============================================================================

/**
 * Create operation response
 */
export interface CreateResponse {
  id: EntityId;
  createdAt: string;
  created_at?: string; // Backend compatibility
}

/**
 * Update operation response
 */
export interface UpdateResponse {
  id: EntityId;
  updatedAt: string;
  updated_at?: string; // Backend compatibility
}

/**
 * Delete operation response
 */
export interface DeleteResponse {
  success: boolean;
  message: string;
  deletedAt?: string;
  deleted_at?: string;
}

/**
 * Generic success message response
 */
export interface MessageResponse {
  message: string;
  success?: boolean;
}

// ============================================================================
// LIST AND COLLECTION TYPES
// ============================================================================

/**
 * Generic list response
 */
export interface ListResponse<T> {
  items: T[];
  total: number;
}

/**
 * List with metadata
 */
export interface ListWithMetadata<T> {
  items: T[];
  total: number;
  metadata?: Record<string, unknown>;
}

// ============================================================================
// MESSAGES API TYPES
// ============================================================================

export interface Message {
  id: string;
  patient_id: string;
  content: string;
  direction: 'inbound' | 'outbound';
  type?: string;
  status: 'pending' | 'sent' | 'delivered' | 'failed' | 'read';
  scheduled_for?: string;
  sent_at?: string;
  delivered_at?: string;
  read_at?: string;
  error_message?: string;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface MessageListFilters extends SearchFilters {
  patient_id?: string;
  direction?: 'inbound' | 'outbound';
  status?: Message['status'];
  type?: string;
  start_date?: string;
  end_date?: string;
}

export interface SendMessageRequest {
  patient_id: string;
  content: string;
  type?: string;
  scheduled_for?: string;
  metadata?: Record<string, unknown>;
}

export interface BulkMessageRequest {
  patient_ids: string[];
  content: string;
  type?: string;
  scheduled_for?: string;
}

export interface BulkMessageResponse {
  success: number;
  failed: number;
  messages: Message[];
  errors?: Array<{ patient_id: string; error: string }>;
}

export interface ConversationResponse {
  patient_id: string;
  messages: Message[];
  total: number;
}

// ============================================================================
// FLOWS API TYPES
// ============================================================================

export enum FlowType {
  INITIAL_15_DAYS = 'initial_15_days',
  DAYS_16_45 = 'days_16_45',
  MONTHLY_RECURRING = 'monthly_recurring'
}

export enum ResponseType {
  TEXT = 'text',
  BUTTON = 'button',
  QUICK_REPLY = 'quick_reply',
  LIST = 'list'
}

export enum FlowStatus {
  ACTIVE = 'active',
  PAUSED = 'paused',
  COMPLETED = 'completed',
  CANCELLED = 'cancelled'
}

export interface Condition {
  field: string;
  operator: 'equals' | 'not_equals' | 'contains' | 'greater_than' | 'less_than';
  value: unknown;
}

export interface InteractiveElements {
  buttons?: Array<{ id: string; text: string; action: string }>;
  quick_replies?: string[];
  list_items?: Array<{ id: string; title: string; description?: string }>;
}

export interface FollowUpAction {
  intent: string;
  delay_seconds: number;
  ai_instructions?: string;
  conditions?: Condition[];
}

export interface MessageTemplate {
  id: string;
  day: number;
  content: string;
  message_type: string; // Changed from MessageType enum to string to avoid circular dependency if needed, or use MessageType if available
  interactive_elements?: InteractiveElements;
  conditions?: Condition[];
  personalization_hints: string[];
  ai_instructions?: string;
  follow_up?: FollowUpAction[];
}

export interface ResponseResult {
  response_type: ResponseType;
  extracted_data: Record<string, unknown>;
  sentiment_score: number;
  requires_attention: boolean;
  follow_up_actions: FollowUpAction[];
}

export interface FlowTemplate {
  id: string;
  name: string;
  description?: string;
  flow_type: FlowType;
  is_active: boolean;
  steps: FlowStep[];
  settings?: Record<string, unknown>;
  messages?: Record<number, MessageTemplate>;
  metadata?: Record<string, unknown>;
  humanization_level?: string;
  created_at: string;
  updated_at: string;
}

export interface FlowStep {
  id: string;
  day: number;
  message_template: string;
  conditions?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface FlowState {
  id: string;
  patient_id: string;
  template_id: string;
  flow_type: FlowType;
  current_day: number;
  enrollment_date: string;
  last_message_sent?: string;
  state_data: Record<string, unknown>;
  sentiment_score?: number;
  requires_attention?: boolean;
  status: FlowStatus;
  started_at: string;
  paused_at?: string;
  completed_at?: string;
  metadata?: Record<string, unknown>;
  patient_name?: string; // Added for frontend display
  monthly_cycle?: number;
}

export interface FlowListFilters extends SearchFilters {
  flow_type?: string;
  is_active?: boolean;
}

export interface CreateFlowTemplateRequest {
  name: string;
  description?: string;
  flow_type: string;
  steps: Omit<FlowStep, 'id'>[];
  settings?: Record<string, unknown>;
}

export interface UpdateFlowTemplateRequest extends Partial<Omit<CreateFlowTemplateRequest, 'steps'>> {
  steps?: (FlowStep | Omit<FlowStep, 'id'>)[];
  is_active?: boolean;
}

export interface FlowAdvanceRequest {
  target_day?: number;
  skip_conditions?: boolean;
}

export interface FlowPauseRequest {
  reason?: string;
}

export interface FlowProcessResponseRequest {
  response_text: string;
  day?: number;
  flow_type?: string;
}

export interface StartFlowRequest {
  patient_id: string;
  flow_type: FlowType;
  initial_state?: Record<string, unknown>;
}

export interface DailyMetric {
  date: string;
  messages_sent: number;
  responses_received: number;
  new_enrollments: number;
  completions: number;
}

export interface FlowAnalytics {
  total_flows: number;
  active_flows: number;
  completed_flows: number;
  completion_rate: number;
  average_duration_days: number;
  by_type?: Record<string, number>;
  // Extended fields for dashboard
  total_active_flows?: number;
  engagement_rate?: number;
  average_response_time?: number;
  flows_by_type?: Record<string, number>;
  daily_metrics?: DailyMetric[];
}

// ============================================================================
// ALERTS API TYPES
// ============================================================================

export interface Alert {
  id: string;
  type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  message: string;
  patient_id?: string;
  patient_name?: string; // Added for frontend display
  status: 'pending' | 'acknowledged' | 'resolved' | 'dismissed';
  is_acknowledged?: boolean; // Helper property
  acknowledged_at?: string;
  acknowledged_by?: string;
  resolved_at?: string;
  resolved_by?: string;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface AlertListFilters extends SearchFilters {
  type?: string;
  severity?: Alert['severity'];
  status?: Alert['status'];
  patient_id?: string;
  created_after?: string;
  created_before?: string;
}

export interface CreateAlertRequest {
  type: string;
  severity: Alert['severity'];
  title: string;
  message: string;
  patient_id?: string;
  metadata?: Record<string, unknown>;
}

export interface UpdateAlertRequest extends Partial<CreateAlertRequest> {
  status?: Alert['status'];
}

export interface UnreadCountResponse {
  count: number;
  by_severity?: Record<string, number>;
}

// ============================================================================
// REPORTS API TYPES
// ============================================================================

export interface Report {
  id: string;
  report_type: string;
  name: string;
  patient_id?: string;
  format: 'pdf' | 'excel' | 'csv';
  status: 'pending' | 'generating' | 'completed' | 'failed';
  file_url?: string;
  generated_at?: string;
  generated_by?: string;
  error_message?: string;
  parameters?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ReportListFilters extends SearchFilters {
  report_type?: string;
  status?: Report['status'];
  patient_id?: string;
  generated_after?: string;
  generated_before?: string;
}

export interface GenerateReportRequest {
  patient_id?: string;
  report_type: string;
  format?: 'pdf' | 'excel' | 'csv';
  parameters?: Record<string, unknown>;
}

export interface ScheduleReportRequest {
  report_type: string;
  frequency: 'daily' | 'weekly' | 'monthly';
  recipients: string[];
  parameters?: Record<string, unknown>;
}

export interface ScheduledReport {
  id: string;
  report_type: string;
  frequency: string;
  recipients: string[];
  next_run: string;
  is_active: boolean;
  created_at: string;
}

// ============================================================================
// ADMIN API TYPES
// Note: We re-export AdminUser and related types from @/types/admin
// This provides a single import point while keeping the canonical definitions
// in the specialized admin types file
// ============================================================================

export type {
  AdminUser,
  AuditLogEntry,
  SystemSettings,
  AdminUserActivity as UserActivityEntry,
} from '@/types/admin';

export interface AdminUserListFilters extends SearchFilters {
  role?: string;
  is_active?: boolean;
  status?: string;
}

export interface CreateUserRequest {
  email: string;
  full_name: string;
  password: string;
  role: string;
  permissions?: string[];
  two_factor_enabled?: boolean;
}

export interface UpdateUserRequest extends Partial<Omit<CreateUserRequest, 'password'>> {
  is_active?: boolean;
  password?: string; // Allow password updates
}

export interface ResetPasswordRequest {
  new_password: string;
  force_change?: boolean;
}

export interface UserActivityFilters extends SearchFilters {
  action?: string;
  resource?: string;
  start_date?: string;
  end_date?: string;
}

export interface Role {
  id: string;
  name: string;
  description?: string;
  permissions: string[];
  is_system: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateRoleRequest {
  name: string;
  description?: string;
  permissions: string[];
}

export interface AuditLogFilters extends SearchFilters {
  user_id?: string;
  action?: string;
  entity_type?: string;
  entity_id?: string;
  start_date?: string;
  end_date?: string;
}

export interface SystemHealth {
  status: 'healthy' | 'degraded' | 'down';
  components: Array<{
    name: string;
    status: 'up' | 'down' | 'degraded';
    last_check: string;
    details?: Record<string, unknown>;
  }>;
  timestamp: string;
}

export interface SystemMetrics {
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  active_connections: number;
  request_rate: number;
  error_rate: number;
  timestamp: string;
}

export interface SystemStats {
  system: {
    cpu_percent: number;
    memory_percent: number;
    disk_percent: number;
    uptime_seconds: number;
    uptime?: number; // For compatibility
  };
  users: {
    total: number;
    active_now: number;
    by_role: {
      admin?: number;
      doctor?: number;
      [key: string]: number | undefined;
    };
  };
  security?: {
    failed_logins?: number;
    active_sessions?: number;
    blocked_ips?: number;
  };
  database: {
    total_records: number;
    total_patients: number;
    total_users: number;
    connections: number;
  };
  timestamp: string;
  // Legacy flat properties for backward compatibility
  uptime_seconds?: number;
  total_requests?: number;
  total_errors?: number;
  active_users?: number;
  database_size?: number;
  cache_hit_rate?: number;
}

// ============================================================================
// AI API TYPES
// ============================================================================

export interface AIChatRequest {
  message: string;
  context?: Record<string, unknown>;
}

export interface AIChatResponse {
  response: string;
  message?: string; // Alias for response content
  confidence?: number;
  suggestions?: string[];
  metadata?: Record<string, unknown>;
}

export interface AIAnalysisRequest {
  data: unknown;
  analysis_type: string;
}

export interface AIAnalysisResponse {
  analysis: Record<string, unknown>;
  insights: string[];
  recommendations?: string[];
}

export interface AIGenerateResponseRequest {
  patient_id: string;
  message_history: Array<{ role: string; content: string }>;
  intent?: string;
}

export interface AIGenerateResponseResponse {
  generated_response: string;
  confidence: number;
  alternative_responses?: string[];
}

export interface SentimentAnalysisRequest {
  text: string;
}

export interface SentimentAnalysisResponse {
  sentiment: 'positive' | 'negative' | 'neutral';
  score: number;
  confidence: number;
}

export interface AIInsight {
  id: string;
  type: string; // Changed from enum to string to avoid circular dependency or need to move enum
  title: string;
  description: string;
  confidence: number;
  priority?: 'low' | 'medium' | 'high' | 'critical';
  patient_id?: string;
  created_at: string;
  metadata?: Record<string, unknown>;
  risk_level?: 'low' | 'medium' | 'high' | 'critical';
  risk_factors?: string[];
}

export interface AIInsights {
  patient_id: string;
  insights: AIInsight[];
  summary?: string;
  risk_level?: 'low' | 'medium' | 'high' | 'critical';
  risk_factors?: string[];
  sentiment_score?: number;
  filter?: (predicate: (insight: any) => boolean) => any[]; // For array-like behavior
}

export interface AIRecommendations {
  patient_id: string;
  recommendations: Array<{
    type: string;
    priority: 'low' | 'medium' | 'high';
    description: string;
    rationale: string;
  }>;
  // Array-like properties for direct array access
  length?: number;
  slice?: (start?: number, end?: number) => any[];
}

// ============================================================================
// QUIZ API TYPES
// ============================================================================

export interface QuestionOption {
  id: string;
  text: string;
  value: string | number;
  is_correct?: boolean;
}

export interface QuizQuestion {
  id: string;
  type: 'multiple_choice' | 'open_text' | 'scale' | 'yes_no' | 'date' | 'number';
  text: string;
  description?: string;
  required: boolean;
  options?: QuestionOption[];
}

export interface QuizTemplate {
  id: string;
  name: string;
  version: string;
  description?: string;
  questions: QuizQuestion[];
  questions_count?: number;
  estimated_duration_minutes?: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  analytics?: {
    total_responses?: number;
    completion_rate?: number;
    average_completion_time?: number;
  };
}

export interface QuizTemplateResponse {
  items: QuizTemplate[];
}

export interface QuizSessionStartRequest {
  patient_id: string;
  quiz_template_id: string;
}

export interface QuizSession {
  id: string;
  patient_id: string;
  patient_name?: string; // Added for frontend display
  quiz_template_id: string;
  template_name?: string; // Added for frontend display
  status: 'pending' | 'in_progress' | 'completed' | 'abandoned';
  is_completed?: boolean;
  started_at?: string;
  completed_at?: string;
  score?: number;
  created_at: string;
  updated_at: string;
}

export interface QuizSubmitRequest {
  question_id: string;
  answer: string | string[];
  response_metadata?: Record<string, unknown>;
}

export interface QuizResponse {
  id: string;
  session_id: string;
  question_id: string;
  answer: string | string[];
  answered_at: string;
}

export interface QuizSessionListFilters extends SearchFilters {
  patient_id?: string;
  template_id?: string;
  status?: QuizSession['status'];
  started_after?: string;
  started_before?: string;
}

export interface QuizSessionResponses {
  session_id: string;
  responses: QuizResponse[];
  total_questions: number;
  answered_questions: number;
}

export interface QuizSessionAnalysis {
  session_id: string;
  score: number;
  total_questions: number;
  correct_answers: number;
  analysis: Record<string, unknown>;
}

export interface PatientQuizResponses {
  patient_id: string;
  sessions: QuizSession[];
  total: number;
}

// NotificationListResponse is already defined in types/notifications or similar, 
// checking if I can import it or if I should just define it here if it's missing.
// The previous lint error said "Subsequent property declarations must have the same type".
// This implies it IS defined somewhere else in this file or merged.
// I will check the file content again to be sure.
// But for now, I will just restore PatientQuizResponses.

export interface RiskAssessmentRequest {
  patient_id?: string;
  days_lookback?: number;
}

export interface RiskAssessmentsResponse {
  assessments: any[];
}

// ============================================================================
// TASKS API TYPES
// ============================================================================

export enum TaskStatus {
  PENDING = 'PENDING',
  RUNNING = 'RUNNING',
  SUCCESS = 'SUCCESS',
  FAILURE = 'FAILURE',
  RETRY = 'RETRY',
  CANCELLED = 'CANCELLED'
}

export enum TaskType {
  CUSTOM = 'custom',
  DAILY_FLOW = 'daily_flow',
  MONTHLY_QUIZ = 'monthly_quiz',
  REPORT_GENERATION = 'report_generation',
  DATA_EXPORT = 'data_export',
  SYSTEM_MAINTENANCE = 'system_maintenance'
}

export enum TaskPriority {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  CRITICAL = 'critical'
}

export interface Task {
  id: string;
  celery_task_id: string;
  task_name: string;
  task_type: string;
  status: TaskStatus;
  priority: TaskPriority;
  description?: string;
  metadata?: Record<string, unknown>;
  progress?: {
    current: number;
    total: number;
    percent: number;
    message?: string;
    eta_seconds?: number;
  };
  result?: any;
  error?: string;
  traceback?: string;
  retry_count: number;
  worker_name?: string;
  queue_name?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  scheduled_at?: string;
  timeout_seconds?: number;
  user_id?: string;
  runtime_seconds?: number;
}

export interface TaskListFilters extends BaseFilters {
  status?: TaskStatus;
  task_type?: TaskType;
  priority?: TaskPriority;
  user_id?: string;
  start_date?: string;
  end_date?: string;
}

export interface QueueStatusV2 {
  queue_name: string;
  pending_count: number;
  active_count: number;
  workers: string[];
  avg_processing_time?: number;
}

export interface TaskStatisticsV2 {
  total_tasks: number;
  pending_tasks: number;
  running_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
  cancelled_tasks: number;
  retry_tasks: number;
  avg_runtime_seconds: number;
  avg_wait_time_seconds: number;
  success_rate: number;
  tasks_by_type: Record<string, number>;
  tasks_by_priority: Record<string, number>;
  slowest_tasks: Array<{ task_name: string; runtime_seconds: number }>;
  analysis_period_hours: number;
}

// ============================================================================
// NOTIFICATIONS API TYPES
// ============================================================================

export interface Notification {
  id: string;
  type: string;
  title: string;
  message: string;
  read: boolean;
  created_at: string;
  metadata?: Record<string, unknown>;
}

export interface NotificationListResponse {
  notifications: Notification[];
  items: Notification[]; // Alias for paginated API consistency
  total: number;
  unread_count: number;
}

// ============================================================================
// PHYSICIAN API TYPES
// ============================================================================

export interface RiskAssessmentRequest {
  patient_id?: string;
  days_lookback?: number;
}

export interface RiskAssessment {
  patient_id: string;
  patient_name?: string;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  risk_factors: string[];
  last_response?: string;
  recommended_actions: string[];
}

export interface RiskAssessmentsResponse {
  success: boolean;
  risk_level_filter: string;
  risk_assessments: RiskAssessment[];
  total_patients: number;
  generated_at: string;
  lookback_days: number;
}
