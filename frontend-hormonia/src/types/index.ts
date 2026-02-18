// Main types index file - Centralized type exports
// All types are now in /types/* (migrated from /lib/types/*)

// Re-export from centralized api.ts
export type { Patient as ApiPatient } from './api'
export type { User as ApiUser } from '@/hooks/auth/types'

// AI types from api.ts
export type {
  ChatRole,
  AIChatMessage,
  ChatSession,
  ChatResponse,
  AIChatResponse,
  AIRecommendation,
  RecommendedAction,
  PatientEngagementMetrics,
  SentimentTrend,
  AIAnalyticsDashboard,
  PerformanceTrend,
  AIFlowContext,
  PatientPreferences,
  AIGeneratedMessage,
  AIEvent,
  AIConfig,
  AIError,
  UseAIChatOptions,
  UseAIAnalyticsOptions,
  UseAIInsightsOptions,
  UseAISummaryOptions,
  AnalysisRequest,
  AnalysisResult,
  InsightType,
  SentimentAnalysis,
  SentimentLabel,
  EmotionScores,
  SeverityLevel,
  HealthConcern,
  QuizFindings,
  TreatmentCompliance,
  SummaryContent,
  PatientSummaryResponse,
  PatientSummaryListResponse,
  GenerateSummaryRequest
} from './api'

// Flow types from api.ts
export type {
  FlowState,
  MessageTemplate,
  Condition,
  InteractiveElements,
  FollowUpAction,
  ResponseResult,
  FlowAnalytics,
  DailyMetric
} from './api'
export { FlowType, FlowStatus, ResponseType } from './api'

// Flow designer types from flow-designer.ts
export * from './flow-designer'

// WebSocket types from websocket.ts
export type { WebSocketMessage as WSMessage } from './websocket'
export * from './websocket'

// Note: Core enums are available via imports from main types/api

// Common application types
export interface User {
  id: string
  email: string
  name: string
  role: string
  avatar?: string
  token?: string  // Add token property for WebSocket usage
  createdAt: string
  updatedAt: string
}

export interface Patient {
  id: string
  name: string
  email: string
  phone: string
  dateOfBirth: string
  diagnosis?: string
  status: 'active' | 'inactive' | 'completed' | 'paused' | 'cancelled'  // Extended to match API PatientStatus
  lastVisit?: string
  nextAppointment?: string
  current_day?: number  // Add missing property for compatibility
  createdAt: string
  updatedAt: string
  // doctor_id can be null when patient is unassigned
  doctor_id?: string | null
  // FIX: Added missing flow_state field from backend (patient.py line 70)
  // Backend: Enum(FlowState), nullable=False, default=ONBOARDING
  flow_state: 'onboarding' | 'active' | 'paused' | 'completed' | 'cancelled'
}

export interface AlertMessage {
  id: string
  type: 'info' | 'warning' | 'error' | 'success'
  title: string
  message: string
  timestamp: string
  read: boolean
  userId: string
}

export interface DashboardMetric {
  id: string
  title: string
  value: number | string
  change?: number
  trend?: 'up' | 'down' | 'stable'
  icon?: string
  description?: string
  format?: string
}

// Chart Data interface
export interface ChartData {
  name: string
  value: number
  color?: string
  fill?: string
  timestamp?: string
  label?: string
}

// Treatment Type
export interface TreatmentType {
  id: string
  name: string
  description?: string
}

// Enhanced PaginatedResponse for component compatibility - matches backend format
export interface PaginatedResponse<T> {
  items: T[]  // Primary data array property (backend format)
  total: number
  page: number
  size: number
  pages: number
  has_next: boolean
  has_prev: boolean
  // Alternative formats for backwards compatibility
  data?: T[]  // Legacy compatibility
  limit?: number  // Alternative naming
  has_more?: boolean  // Alternative naming
  current_page?: number  // Alternative naming
  page_size?: number  // Alternative naming
}
