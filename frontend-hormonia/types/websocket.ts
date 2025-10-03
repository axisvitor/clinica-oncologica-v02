/**
 * WebSocket Types - Real-time communication interfaces
 * Enhanced WebSocket type definitions with comprehensive event handling
 */

import type { BaseEvent, EventListener, EventSubscription } from './shared'
import type { Patient, Message, Flow, Alert, Report, AIInsight } from './api'
import type { User } from './auth'

// ============================================================================
// WEBSOCKET EVENTS
// ============================================================================

/** WebSocket event types */
export enum WebSocketEventType {
  // Connection events
  CONNECTED = 'connected',
  DISCONNECTED = 'disconnected',
  AUTHENTICATED = 'authenticated',
  AUTHENTICATION_FAILED = 'authentication_failed',
  RECONNECTING = 'reconnecting',
  RECONNECTED = 'reconnected',
  ERROR = 'error',
  PING = 'ping',
  PONG = 'pong',

  // Patient events
  PATIENT_CREATED = 'patient_created',
  PATIENT_UPDATED = 'patient_updated',
  PATIENT_DELETED = 'patient_deleted',
  PATIENT_STATUS_CHANGED = 'patient_status_changed',
  PATIENT_ENROLLED = 'patient_enrolled',

  // Flow events
  FLOW_STARTED = 'flow_started',
  FLOW_PAUSED = 'flow_paused',
  FLOW_RESUMED = 'flow_resumed',
  FLOW_COMPLETED = 'flow_completed',
  FLOW_STATE_CHANGED = 'flow_state_changed',
  FLOW_PROGRESSION = 'flow_progression',
  FLOW_TRANSITION = 'flow_transition',
  FLOW_ERROR = 'flow_error',

  // Message events
  MESSAGE_SENT = 'message_sent',
  MESSAGE_DELIVERED = 'message_delivered',
  MESSAGE_READ = 'message_read',
  MESSAGE_FAILED = 'message_failed',
  MESSAGE_RECEIVED = 'message_received',
  MESSAGE_STATUS_UPDATED = 'message_status_updated',
  NEW_MESSAGE = 'new_message',

  // Quiz events
  QUIZ_STARTED = 'quiz_started',
  QUIZ_RESPONSE_SUBMITTED = 'quiz_response_submitted',
  QUIZ_COMPLETED = 'quiz_completed',
  QUIZ_ANALYTICS_UPDATED = 'quiz_analytics_updated',

  // Alert events
  ALERT_CREATED = 'alert_created',
  ALERT_UPDATED = 'alert_updated',
  ALERT_ACKNOWLEDGED = 'alert_acknowledged',
  ALERT_RESOLVED = 'alert_resolved',
  ALERT_ESCALATED = 'alert_escalated',

  // Report events
  REPORT_GENERATION_STARTED = 'report_generation_started',
  REPORT_GENERATION_PROGRESS = 'report_generation_progress',
  REPORT_GENERATION_COMPLETED = 'report_generation_completed',
  REPORT_GENERATION_FAILED = 'report_generation_failed',

  // AI events
  AI_INSIGHT_GENERATED = 'ai_insight_generated',
  AI_ANALYSIS_COMPLETED = 'ai_analysis_completed',
  AI_RECOMMENDATION_CREATED = 'ai_recommendation_created',
  AI_CHAT_RESPONSE = 'ai_chat_response',

  // System events
  SYSTEM_MAINTENANCE = 'system_maintenance',
  SYSTEM_NOTIFICATION = 'system_notification',
  SYSTEM_HEALTH_CHANGED = 'system_health_changed',
  SYSTEM_UPDATE = 'system_update',

  // User events
  USER_ONLINE = 'user_online',
  USER_OFFLINE = 'user_offline',
  USER_ACTIVITY = 'user_activity',

  // Room events
  ROOM_JOINED = 'room_joined',
  ROOM_LEFT = 'room_left',
  ROOM_USER_COUNT_CHANGED = 'room_user_count_changed'
}

// ============================================================================
// MESSAGE STRUCTURES
// ============================================================================

/** Base WebSocket message */
export interface WebSocketMessage<T = unknown> extends BaseEvent<T> {
  readonly type: WebSocketEventType
  readonly id?: string
  readonly room?: string
  readonly user_id?: string
  readonly correlation_id?: string
}

/** WebSocket error message */
export interface WebSocketError {
  readonly type: WebSocketErrorType
  readonly message: string
  readonly code?: string | number
  readonly details?: Record<string, unknown>
  readonly timestamp: string
  readonly retryable?: boolean
  readonly retry_after?: number
}

/** WebSocket error types */
export enum WebSocketErrorType {
  CONNECTION = 'connection',
  AUTHENTICATION = 'authentication',
  AUTHORIZATION = 'authorization',
  MESSAGE = 'message',
  NETWORK = 'network',
  PROTOCOL = 'protocol',
  RATE_LIMIT = 'rate_limit',
  SERVER = 'server',
  UNKNOWN = 'unknown'
}

// ============================================================================
// CONNECTION & STATE
// ============================================================================

/** WebSocket connection state */
export interface WebSocketConnectionState {
  readonly isConnected: boolean
  readonly isConnecting: boolean
  readonly isAuthenticated: boolean
  readonly isReconnecting: boolean
  readonly reconnectAttempts: number
  readonly maxReconnectAttempts: number
  readonly lastError: WebSocketError | null
  readonly connectionId: string | null
  readonly connectedAt: string | null
  readonly lastPingAt: string | null
  readonly lastPongAt: string | null
  readonly latency: number | null
  readonly readyState: WebSocketReadyState
}

/** WebSocket ready state */
export enum WebSocketReadyState {
  CONNECTING = 0,
  OPEN = 1,
  CLOSING = 2,
  CLOSED = 3
}

/** WebSocket configuration */
export interface WebSocketConfig {
  readonly url: string
  readonly protocols?: string | string[]
  readonly reconnectAttempts: number
  readonly reconnectDelay: number
  readonly maxReconnectDelay: number
  readonly reconnectDecay: number
  readonly heartbeatInterval: number
  readonly connectionTimeout: number
  readonly enableLogging: boolean
  readonly autoReconnect: boolean
  readonly enableCompression?: boolean
  readonly enablePing?: boolean
  readonly bufferMessages?: boolean
  readonly maxBufferSize?: number
}

// ============================================================================
// EVENT DATA TYPES
// ============================================================================

/** Patient event data */
export interface PatientEventData {
  readonly patient: Patient
  readonly changes?: Partial<Patient>
  readonly previous_values?: Partial<Patient>
  readonly user_id?: string
  readonly metadata?: Record<string, unknown>
}

/** Message event data */
export interface MessageEventData {
  readonly message: Message
  readonly patient?: Patient
  readonly changes?: Partial<Message>
  readonly error_details?: string
  readonly metadata?: Record<string, unknown>
}

/** Flow event data */
export interface FlowEventData {
  readonly flow: Flow
  readonly patient?: Patient
  readonly previous_state?: string
  readonly milestone_reached?: string
  readonly changes?: Partial<Flow>
  readonly metadata?: Record<string, unknown>
}

/** Alert event data */
export interface AlertEventData {
  readonly alert: Alert
  readonly patient?: Patient
  readonly user?: User
  readonly changes?: Partial<Alert>
  readonly escalation_level?: number
  readonly metadata?: Record<string, unknown>
}

/** Report event data */
export interface ReportEventData {
  readonly report: Report
  readonly patient?: Patient
  readonly progress_percentage?: number
  readonly error_details?: string
  readonly file_info?: {
    readonly size: number
    readonly format: string
    readonly download_url?: string
  }
  readonly metadata?: Record<string, unknown>
}

/** AI event data */
export interface AIEventData {
  readonly insight?: AIInsight
  readonly analysis_type?: string
  readonly confidence?: number
  readonly patient_id?: string
  readonly recommendations?: string[]
  readonly processing_time_ms?: number
  readonly metadata?: Record<string, unknown>
}

/** System event data */
export interface SystemEventData {
  readonly message: string
  readonly level: 'info' | 'warning' | 'error' | 'critical'
  readonly component?: string
  readonly affected_services?: string[]
  readonly estimated_duration?: string
  readonly action_required?: boolean
  readonly maintenance_window?: {
    readonly start: string
    readonly end: string
    readonly timezone: string
  }
  readonly metadata?: Record<string, unknown>
}

/** User activity event data */
export interface UserActivityEventData {
  readonly user: User
  readonly activity_type: UserActivityType
  readonly resource?: string
  readonly resource_id?: string
  readonly details?: Record<string, unknown>
}

/** User activity types */
export enum UserActivityType {
  LOGIN = 'login',
  LOGOUT = 'logout',
  PAGE_VIEW = 'page_view',
  ACTION_PERFORMED = 'action_performed',
  IDLE = 'idle',
  ACTIVE = 'active'
}

// ============================================================================
// AUTHENTICATION & ROOMS
// ============================================================================

/** Authentication request */
export interface AuthenticationRequest {
  readonly token: string
  readonly user_id?: string
  readonly metadata?: Record<string, unknown>
}

/** Authentication response */
export interface AuthenticationResponse {
  readonly success: boolean
  readonly user_id?: string
  readonly user_role?: string
  readonly permissions?: string[]
  readonly connection_id: string
  readonly message: string
  readonly expires_at?: string
}

/** Room subscription request */
export interface RoomSubscriptionRequest {
  readonly room: string
  readonly events?: WebSocketEventType[]
  readonly metadata?: Record<string, unknown>
}

/** Room subscription response */
export interface RoomSubscriptionResponse {
  readonly success: boolean
  readonly room: string
  readonly subscribed_events: WebSocketEventType[]
  readonly user_count?: number
  readonly message: string
}

/** Patient room subscription */
export interface PatientRoomSubscription {
  readonly patient_id: string
  readonly subscribed_at: string
  readonly events: WebSocketEventType[]
  readonly auto_unsubscribe?: boolean
}

// ============================================================================
// HANDLERS & SUBSCRIPTIONS
// ============================================================================

/** WebSocket event handler */
export type WebSocketEventHandler<T = unknown> = EventListener<T>

/** WebSocket error handler */
export type WebSocketErrorHandler = (error: WebSocketError) => void

/** WebSocket connection handler */
export type WebSocketConnectionHandler = (state: WebSocketConnectionState) => void

/** WebSocket subscription */
export interface WebSocketSubscription extends EventSubscription {
  readonly event: WebSocketEventType
  readonly handler: WebSocketEventHandler
  readonly room?: string
  readonly once?: boolean
  readonly priority?: number
}

// ============================================================================
// MANAGER INTERFACE
// ============================================================================

/** WebSocket manager interface */
export interface IWebSocketManager {
  // Connection management
  connect(token: string, options?: Partial<WebSocketConfig>): Promise<void>
  disconnect(code?: number, reason?: string): void
  reconnect(): Promise<void>
  isConnected(): boolean
  getConnectionState(): WebSocketConnectionState
  getConfig(): WebSocketConfig

  // Authentication
  authenticate(token: string): Promise<AuthenticationResponse>
  refreshToken(newToken: string): Promise<boolean>
  isAuthenticated(): boolean

  // Room management
  joinRoom(room: string, events?: WebSocketEventType[]): Promise<RoomSubscriptionResponse>
  leaveRoom(room: string): Promise<boolean>
  joinPatientRoom(patientId: string): Promise<RoomSubscriptionResponse>
  leavePatientRoom(patientId: string): Promise<boolean>
  getCurrentRooms(): string[]
  getRoomSubscriptions(): PatientRoomSubscription[]

  // Event handling
  on<T = unknown>(event: WebSocketEventType, handler: WebSocketEventHandler<T>, options?: {
    room?: string
    once?: boolean
    priority?: number
  }): string
  off(event: WebSocketEventType, handlerId?: string): void
  once<T = unknown>(event: WebSocketEventType, handler: WebSocketEventHandler<T>): string
  emit(event: WebSocketEventType, data: unknown, room?: string): void
  removeAllListeners(event?: WebSocketEventType): void

  // Message handling
  send(message: WebSocketMessage): void
  sendToRoom(room: string, message: WebSocketMessage): void
  getMessageQueue(): WebSocketMessage[]
  clearMessageQueue(): void

  // Utility methods
  ping(): Promise<number> // Returns latency in ms
  getStats(): WebSocketStats
  getLastError(): WebSocketError | null
  enableLogging(enabled: boolean): void
  setHeartbeatInterval(interval: number): void

  // Event emitters for connection state
  onConnect(handler: WebSocketConnectionHandler): string
  onDisconnect(handler: WebSocketConnectionHandler): string
  onError(handler: WebSocketErrorHandler): string
  onReconnect(handler: WebSocketConnectionHandler): string
}

// ============================================================================
// STATISTICS & MONITORING
// ============================================================================

/** WebSocket statistics */
export interface WebSocketStats {
  readonly connectionTime: string | null
  readonly connectedDuration: number | null // in milliseconds
  readonly messagesReceived: number
  readonly messagesSent: number
  readonly eventsEmitted: number
  readonly eventsReceived: number
  readonly reconnectCount: number
  readonly currentRooms: string[]
  readonly latency: number | null
  readonly averageLatency: number | null
  readonly lastActivityAt: string | null
  readonly bytesReceived: number
  readonly bytesSent: number
  readonly errorCount: number
  readonly lastErrors: WebSocketError[]
}

/** Connection quality metrics */
export interface ConnectionQuality {
  readonly signal_strength: 'excellent' | 'good' | 'fair' | 'poor'
  readonly latency_ms: number
  readonly packet_loss_percentage: number
  readonly jitter_ms: number
  readonly bandwidth_kbps?: number
}

// ============================================================================
// HOOKS RETURN TYPES
// ============================================================================

/** useWebSocket hook return type */
export interface UseWebSocketReturn {
  readonly connectionState: WebSocketConnectionState
  readonly stats: WebSocketStats
  readonly error: WebSocketError | null
  readonly isOnline: boolean

  // Connection methods
  readonly connect: (token: string, options?: Partial<WebSocketConfig>) => Promise<void>
  readonly disconnect: (code?: number, reason?: string) => void
  readonly reconnect: () => Promise<void>

  // Room methods
  readonly joinRoom: (room: string, events?: WebSocketEventType[]) => Promise<RoomSubscriptionResponse>
  readonly leaveRoom: (room: string) => Promise<boolean>
  readonly joinPatientRoom: (patientId: string) => Promise<RoomSubscriptionResponse>
  readonly leavePatientRoom: (patientId: string) => Promise<boolean>
  readonly getCurrentRooms: () => string[]

  // Event methods
  readonly subscribe: <T = unknown>(event: WebSocketEventType, handler: WebSocketEventHandler<T>, options?: {
    room?: string
    once?: boolean
  }) => () => void
  readonly emit: (event: WebSocketEventType, data: unknown, room?: string) => void
  readonly send: (message: WebSocketMessage) => void

  // Utility methods
  readonly ping: () => Promise<number>
  readonly getConnectionQuality: () => ConnectionQuality | null
}

/** useWebSocketPatient hook return type */
export interface UseWebSocketPatientReturn {
  readonly isSubscribed: boolean
  readonly patientEvents: WebSocketMessage<PatientEventData>[]
  readonly messageEvents: WebSocketMessage<MessageEventData>[]
  readonly flowEvents: WebSocketMessage<FlowEventData>[]
  readonly alertEvents: WebSocketMessage<AlertEventData>[]
  
  readonly subscribeToPatient: (patientId: string) => Promise<void>
  readonly unsubscribeFromPatient: (patientId: string) => Promise<void>
  readonly clearEvents: () => void
  readonly getEventHistory: (eventType?: WebSocketEventType) => WebSocketMessage[]
}

// ============================================================================
// CONSTANTS
// ============================================================================

/** Default WebSocket configuration */
export const DEFAULT_WEBSOCKET_CONFIG: WebSocketConfig = {
  url: '',
  reconnectAttempts: 5,
  reconnectDelay: 1000,
  maxReconnectDelay: 30000,
  reconnectDecay: 1.5,
  heartbeatInterval: 30000,
  connectionTimeout: 10000,
  enableLogging: false,
  autoReconnect: true,
  enableCompression: true,
  enablePing: true,
  bufferMessages: true,
  maxBufferSize: 100
} as const

/** WebSocket close codes */
export const WEBSOCKET_CLOSE_CODES = {
  NORMAL_CLOSURE: 1000,
  GOING_AWAY: 1001,
  PROTOCOL_ERROR: 1002,
  UNSUPPORTED_DATA: 1003,
  NO_STATUS_RECEIVED: 1005,
  ABNORMAL_CLOSURE: 1006,
  INVALID_FRAME_PAYLOAD_DATA: 1007,
  POLICY_VIOLATION: 1008,
  MESSAGE_TOO_BIG: 1009,
  MANDATORY_EXTENSION: 1010,
  INTERNAL_SERVER_ERROR: 1011,
  SERVICE_RESTART: 1012,
  TRY_AGAIN_LATER: 1013,
  BAD_GATEWAY: 1014,
  TLS_HANDSHAKE: 1015
} as const

/** Connection quality thresholds */
export const CONNECTION_QUALITY_THRESHOLDS = {
  LATENCY: {
    EXCELLENT: 50,
    GOOD: 150,
    FAIR: 300,
    POOR: 1000
  },
  PACKET_LOSS: {
    EXCELLENT: 0,
    GOOD: 1,
    FAIR: 3,
    POOR: 10
  }
} as const

/** Event priority levels */
export const EVENT_PRIORITIES = {
  CRITICAL: 1,
  HIGH: 2,
  NORMAL: 3,
  LOW: 4
} as const