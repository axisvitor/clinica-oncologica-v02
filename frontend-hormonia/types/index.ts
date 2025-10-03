/**
 * Types Index - Central export point for all type definitions
 * Provides organized exports and re-exports for the entire application
 *
 * @fileoverview This is the main barrel export for all TypeScript types in the application.
 * All components should import types from this file to ensure consistency and
 * prevent circular dependencies.
 *
 * @version 2.0.0
 * @since 1.0.0
 */

// ============================================================================
// SHARED BASE TYPES (Foundation)
// ============================================================================

export type {
  // Core base interfaces
  BaseEntity,
  SoftDeletableEntity,
  ApiResponse,
  ApiErrorResponse,
  PaginatedResponse,

  // Utility types
  DeepPartial,
  PartialBy,
  RequiredBy,
  Nullable,
  Optional,
  ValueOf,
  ArrayElement,
  AsyncReturnType,

  // Common enums (types only)
  Status as StatusType,
  Priority as PriorityType,
  Severity as SeverityType,
  UserRole as UserRoleType,

  // Query and filter types
  QueryParams,
  PaginationParams,
  SortParams,
  FilterParams,

  // Configuration types
  ApiClientConfig,
  WebSocketConfig,
  RetryConfig,

  // Error types
  BaseError,
  ValidationError,
  NetworkError,

  // Event types
  BaseEvent,
  EventListener,
  EventSubscription,

  // Component props
  BaseComponentProps,
  LoadingProps,
  ErrorProps,
  StateProps,

  // Form types
  FormField,
  ValidationRule,
  FormState,

  // Metadata and audit
  Metadata,
  AuditInfo,
  VersionedEntity,

  // Time and scheduling
  TimeRange,
  Duration,
  Schedule,

  // Feature flags
  FeatureFlag,
  FeatureFlags,

  // Analytics
  AnalyticsEvent,
  Metric,

  // Internationalization
  LocalizedText,
  TranslationKey,
  Locale
} from './shared'

export {
  // Re-export enums for direct usage
  Status,
  Priority,
  Severity,
  UserRole
} from './shared'

// ============================================================================
// AUTHENTICATION TYPES
// ============================================================================

export type {
  // Core auth entities
  User,
  AuthTokens,
  LoginResponse,
  LoginCredentials,
  RegisterData,

  // Auth state management
  AuthState,
  SessionData,
  SupabaseAuthData,

  // Permissions and authorization
  PermissionConfig,
  PermissionResult,
  ResourceAccess,
  PermissionSummary,

  // Auth errors and events
  AuthError,
  AuthEvent,
  AuthEventListener,

  // Retry and recovery
  AuthRetryConfig,
  AuthRetryState,

  // Hook options and return types
  UseAuthOptions,
  UseApiAuthOptions,
  UseSupabaseAuthOptions,
  UseSessionManagementOptions,
  UsePermissionsOptions,
  UseAuthReturn,
  UseApiAuthReturn,
  UseSupabaseAuthReturn,
  UseSessionManagementReturn,
  UsePermissionsReturn,
  UseAuthRetryReturn,

  // MFA and security
  MFAChallenge,
  MFAVerification,
  SecurityEvent,
  SessionInfo
} from './auth'

export {
  // Re-export enums for direct usage
  AuthErrorCode,
  AuthEventType,
  MFAChallengeType,
  SecurityEventType
} from './auth'

// ============================================================================
// API TYPES (Domain Entities)
// ============================================================================

export type {
  // Core domain entities
  Patient,
  Message,
  Flow,
  Alert,
  Report,

  // Quiz and assessment types
  QuizTemplate,
  QuizQuestion,
  QuizOption,
  QuizSession,
  QuestionValidation,

  // Analytics and metrics
  DashboardAnalytics,
  EngagementMetrics,
  FlowMetrics,
  TrendPoint,
  ActivityItem,

  // AI and automation
  AIChatMessage,
  AIInsight,
  SentimentAnalysis,
  EmotionScores,

  // System monitoring
  SystemHealth,
  ComponentHealth,
  PerformanceMetric,
  PerformanceThreshold,

  // Request/response types
  PatientQueryParams,
  MessageQueryParams,
  AlertQueryParams,
  ReportQueryParams,
  CreatePatientRequest,
  UpdatePatientRequest,
  SendMessageRequest,
  StartFlowRequest,
  CreateAlertRequest,
  GenerateReportRequest,
  BulkMessageRequest,

  // API client interface
  ApiClient,
  Notification,

  // Flow template types
  FlowTemplate,
  FlowStep,
  CreateFlowTemplateRequest,
  UpdateFlowTemplateRequest,

  // Extended API client interfaces
  ApiClientFlowsExtended,
  ApiClientReportsExtended,
  ApiClientPatientsExtended,

  // Additional types
  RequestOptions
} from './api'

export {
  // Re-export enums for direct usage
  PatientStatus,
  MessageDirection,
  MessageType,
  MessageStatus,
  FlowType,
  FlowStatus,
  AlertType,
  ReportType,
  ReportStatus,
  QuestionType,
  ScoringMethod,
  QuizSessionStatus,
  SystemHealthStatus,
  ActivityType,
  ChatRole,
  InsightType,
  SentimentLabel,
  ComponentStatus,
  NotificationType
} from './api'

// ============================================================================
// WEBSOCKET TYPES (Real-time Communication)
// ============================================================================

export type {
  // Core WebSocket types
  WebSocketMessage,
  WebSocketError,
  WebSocketConnectionState,

  // Event data types
  PatientEventData,
  MessageEventData,
  FlowEventData,
  AlertEventData,
  ReportEventData,
  AIEventData,
  SystemEventData,
  UserActivityEventData,

  // Authentication and rooms
  AuthenticationRequest,
  AuthenticationResponse,
  RoomSubscriptionRequest,
  RoomSubscriptionResponse,
  PatientRoomSubscription,

  // Handlers and subscriptions
  WebSocketEventHandler,
  WebSocketErrorHandler,
  WebSocketConnectionHandler,
  WebSocketSubscription,

  // Manager interface
  IWebSocketManager,

  // Statistics and monitoring
  WebSocketStats,
  ConnectionQuality,

  // Hook return types
  UseWebSocketReturn,
  UseWebSocketPatientReturn
} from './websocket'

export {
  // Re-export enums for direct usage
  WebSocketEventType,
  WebSocketErrorType,
  WebSocketReadyState,
  UserActivityType
} from './websocket'

// ============================================================================
// FLOW DESIGNER TYPES (Visual Flow Builder)
// ============================================================================

export type {
  // Core flow designer types
  FlowNode,
  FlowConnection,
  FlowDesign,
  FlowVariable,
  FlowMetadata,

  // Node configurations
  MessageNodeConfig,
  ConditionNodeConfig,
  ConditionRule,
  DelayNodeConfig,
  ActionNodeConfig,
  AIResponseNodeConfig,
  QuizNodeConfig,
  WebhookNodeConfig,
  InteractiveElements,
  InteractiveItem,
  InteractiveAction,

  // Designer state
  FlowDesignerState,
  ClipboardItem,
  HistoryItem,

  // Testing and validation
  FlowTestSession,
  FlowExecutionStep,
  FlowValidationResult,
  FlowValidationError,
  FlowValidationWarning,

  // Export/import
  FlowExportOptions,
  FlowImportResult
} from '../lib/types/flow-designer'

export {
  // Re-export enums for direct usage
  FlowNodeType,
  DesignerMode
} from '../lib/types/flow-designer'

// ============================================================================
// ADMIN TYPES (Administrative Interface)
// ============================================================================

export type {
  AdminUser,
  AdminUserActivity,
  AdminLoginCredentials,
  AdminLoginResponse,
  AdminAuthState,
  AdminSession,
  AdminApiResponse,
  AdminPaginatedResponse,
  AdminPaginatedData,
  AdminNotification,
  AdminError,
  SystemSettings,
  SecurityMetrics,
  TwoFactorSetup,
  PasswordStrength,
  SessionWarning,
  AdminDashboardStats,
  LoginAttempt,
  AuditLogEntry,
  AdminFormError,
  AdminFormValidation,
  AdminRoute,
  AdminNavItem,
  AdminActivityFilter
} from '../src/types/admin'

export {
  // Re-export admin error classes
  AdminAuthError,
  AdminSessionExpiredError,
  AdminPermissionError
} from '../src/types/admin'

// ============================================================================
// LEGACY COMPATIBILITY EXPORTS
// ============================================================================

// Re-export types from legacy locations for backward compatibility
// Components that still import from old paths will continue to work
// Note: Legacy API types are now available through wildcard exports

// ============================================================================
// TYPE UTILITIES AND HELPERS
// ============================================================================

/**
 * Helper type to extract the data type from a paginated response
 * @example
 * type PatientData = ExtractPaginatedData<PaginatedResponse<Patient>>
 */
export type ExtractPaginatedData<T> = T extends import('./shared').PaginatedResponse<infer U> ? U : never

/**
 * Helper type to make all properties of an object optional recursively
 * @example
 * type PartialPatient = DeepOptional<Patient>
 */
export type DeepOptional<T> = {
  [P in keyof T]?: T[P] extends object ? DeepOptional<T[P]> : T[P]
}

/**
 * Helper type to create a union of all possible event data types
 */
export type AllEventData =
  | import('./websocket').PatientEventData
  | import('./websocket').MessageEventData
  | import('./websocket').FlowEventData
  | import('./websocket').AlertEventData
  | import('./websocket').ReportEventData
  | import('./websocket').AIEventData
  | import('./websocket').SystemEventData
  | import('./websocket').UserActivityEventData

/**
 * Helper type to create a strongly typed WebSocket message
 * @example
 * type PatientMessage = TypedWebSocketMessage<PatientEventData>
 */
export type TypedWebSocketMessage<T extends AllEventData> = import('./websocket').WebSocketMessage<T>

// ============================================================================
// CONSTANTS AND DEFAULTS
// ============================================================================

/** Default configuration values exported for external use */
export const TYPE_CONSTANTS = {
  DEFAULT_PAGE_SIZE: 20,
  MAX_PAGE_SIZE: 100,
  DEFAULT_RETRY_ATTEMPTS: 3,
  DEFAULT_TIMEOUT_MS: 30000,
  WEBSOCKET_RECONNECT_ATTEMPTS: 5,
  WEBSOCKET_HEARTBEAT_INTERVAL: 30000
} as const

/** Version information for type system */
export const TYPE_SYSTEM_VERSION = {
  major: 2,
  minor: 0,
  patch: 0,
  build: Date.now()
} as const

// ============================================================================
// TYPE ALIASES FOR BACKWARD COMPATIBILITY
// ============================================================================

/** Backward compatibility aliases for renamed types */
export type SharedValidationRule = import('./shared').ValidationRule
export type ApiQuizQuestion = import('./api').QuizQuestion
export type ApiQuizOption = import('./api').QuizOption

/** Flow designer specific type aliases */
export type { ValidationRule as FlowValidationRule, QuizQuestion as FlowQuizQuestion, QuizOption as FlowQuizOption } from '../lib/types/flow-designer'

// Flow designer types are available through direct imports
// import type { ValidationRule, QuizQuestion, QuizOption } from '../lib/types/flow-designer'