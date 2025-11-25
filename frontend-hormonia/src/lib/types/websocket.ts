/**
 * WebSocket TypeScript types for the Hormonia system
 */

export type WebSocketEventType =
  // Connection events
  | 'connected'
  | 'disconnected'
  | 'authenticated'
  | 'authentication_failed'
  | 'ping'
  | 'pong'
  | 'error'

  // Patient events
  | 'patient_updated'
  | 'patient_flow_changed'
  | 'patient_status_changed'

  // Flow-specific events
  | 'flow_state_changed'
  | 'flow_message_sent'
  | 'flow_progression'
  | 'flow_paused'
  | 'flow_resumed'
  | 'flow_transition'

  // Message events
  | 'new_message'
  | 'message_status_updated'
  | 'message_sent'
  | 'message_delivered'
  | 'message_read'
  | 'message_failed'

  // Quiz events
  | 'quiz_started'
  | 'quiz_response_submitted'
  | 'quiz_completed'
  | 'quiz_analytics_updated'

  // Report events
  | 'report_generation_started'
  | 'report_generation_completed'
  | 'report_generation_failed'

  // Alert events
  | 'alert_created'
  | 'alert_updated'
  | 'alert_acknowledged'
  | 'alert_resolved'

  // System events
  | 'system_maintenance'
  | 'system_notification';

export interface WebSocketMessage {
  type: WebSocketEventType;
  timestamp: string;
  data: Record<string, unknown>;
  user?: unknown;
  userId?: string;
}

export interface WebSocketConnectionState {
  isConnected: boolean;
  isConnecting: boolean;
  isAuthenticated: boolean;
  reconnectAttempts: number;
  lastError: string | null;
  connectionId: string | null;
}

export interface WebSocketConfig {
  url: string;
  reconnectAttempts: number;
  reconnectDelay: number;
  heartbeatInterval: number;
  connectionTimeout: number;
  enableLogging: boolean;
}

// Event-specific data types
export interface PatientEventData {
  patient_id: string;
  patient_name?: string;
  doctor_id?: string;
  changes?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface MessageEventData {
  message_id: string;
  patient_id: string;
  direction: 'inbound' | 'outbound';
  type: 'text' | 'button' | 'list' | 'media';
  content?: string;
  status?: string;
  whatsapp_id?: string;
  metadata?: Record<string, unknown>;
}

export interface QuizEventData {
  quiz_id?: string;
  patient_id: string;
  template_id?: string;
  session_id?: string;
  response_id?: string;
  question_id?: string;
  answer?: unknown;
  completed?: boolean;
  score?: number;
  metadata?: Record<string, unknown>;
}

export interface FlowEventData {
  patient_id: string;
  flow_type: 'initial_15_days' | 'days_16_45' | 'monthly_recurring';
  current_day: number;
  previous_day?: number;
  is_paused: boolean;
  enrollment_date: string;
  last_message_sent?: string;
  monthly_cycle?: number;
  changes?: Record<string, unknown>;
  milestone_reached?: string;
  metadata?: Record<string, unknown>;
}

export interface ReportEventData {
  report_id: string;
  patient_id: string;
  report_type: string;
  status: 'generating' | 'completed' | 'failed';
  file_path?: string;
  error_message?: string;
  metadata?: Record<string, unknown>;
}

export interface AlertEventData {
  alert_id: string;
  patient_id: string;
  alert_type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  description?: string;
  acknowledged: boolean;
  acknowledged_by?: string;
  acknowledged_at?: string;
  resolved: boolean;
  resolved_by?: string;
  resolved_at?: string;
  metadata?: Record<string, unknown>;
}

export interface SystemEventData {
  message: string;
  level: 'info' | 'warning' | 'error';
  affected_services?: string[];
  estimated_duration?: string;
  metadata?: Record<string, unknown>;
}

// Authentication types
export interface AuthenticationRequest {
  token: string;
}

export interface AuthenticationResponse {
  success: boolean;
  user_id?: string;
  user_role?: string;
  message: string;
}

export interface JoinRoomRequest {
  patient_id: string;
}

export interface JoinRoomResponse {
  success: boolean;
  patient_id?: string;
  message: string;
}

// Event handler types
export type WebSocketEventHandler<T = unknown> = (data: T) => void;
export type WebSocketErrorHandler = (error: WebSocketError) => void;
export type WebSocketConnectionHandler = (state: WebSocketConnectionState) => void;

export interface WebSocketError {
  type: 'connection' | 'authentication' | 'message' | 'network';
  message: string;
  code?: string | number;
  data?: unknown;
}

// Event subscription types
export interface EventSubscription {
  event: WebSocketEventType;
  handler: WebSocketEventHandler;
  id: string;
}

export interface PatientRoomSubscription {
  patient_id: string;
  subscribed_at: Date;
  events: WebSocketEventType[];
}

// WebSocket manager interface
export interface IWebSocketManager {
  // Connection management
  connect(token: string): Promise<void>;
  disconnect(): void;
  isConnected(): boolean;
  getConnectionState(): WebSocketConnectionState;

  // Authentication
  authenticate(token: string): Promise<boolean>;
  refreshToken(newToken: string): Promise<boolean>;

  // Room management
  joinPatientRoom(patientId: string): Promise<boolean>;
  leavePatientRoom(patientId: string): Promise<boolean>;
  getCurrentRooms(): string[];

  // Event handling
  on<T = unknown>(event: WebSocketEventType, handler: WebSocketEventHandler<T>): string;
  off(event: WebSocketEventType, handlerId?: string): void;
  emit(event: WebSocketEventType, data: unknown): void;

  // Utility methods
  ping(): Promise<boolean>;
  getStats(): WebSocketStats;
}

export interface WebSocketStats {
  connectionTime: Date | null;
  messagesReceived: number;
  messagesSent: number;
  reconnectCount: number;
  currentRooms: string[];
  latency: number | null;
}

// Hook return types
export interface UseWebSocketReturn {
  connectionState: WebSocketConnectionState;
  connect: (token: string) => Promise<void>;
  disconnect: () => void;
  joinRoom: (patientId: string) => Promise<boolean>;
  leaveRoom: (patientId: string) => Promise<boolean>;
  subscribe: <T = unknown>(event: WebSocketEventType, handler: WebSocketEventHandler<T>) => () => void;
  emit: (event: WebSocketEventType, data: Record<string, unknown>) => void;
  stats: WebSocketStats;
  error: WebSocketError | null;
}

// WebSocket Hook Options
export interface WebSocketHookOptions {
  enabled?: boolean;
  autoConnect?: boolean;
  reconnectOnTokenChange?: boolean;
  enableHeartbeat?: boolean;
  heartbeatInterval?: number;
  maxReconnectAttempts?: number;
  reconnectDelay?: number;
}