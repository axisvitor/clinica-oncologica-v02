// AI Service Types - Use /types/api.ts for latest definitions
// Import types for internal use
import type { AIChatMessage as AIChatMessageImport, AIInsight as AIInsightImport } from '../../../types/api'

// Re-export types from centralized API types
export type {
  AIChatMessage,
  AIChatMessage as ChatMessage,
  ChatRole
} from '../../../types/api'

// Type aliases for internal use
type AIChatMessage = AIChatMessageImport
type ChatMessage = AIChatMessageImport
type AIInsight = AIInsightImport

export interface ChatSession {
  id: string
  patient_id?: string
  user_id: string
  title: string
  messages: AIChatMessageImport[]
  created_at: string
  updated_at: string
  status: 'active' | 'archived'
}

export interface ChatResponse {
  message: string
  confidence: number
  intent?: string
  entities?: Record<string, any>
  suggestions?: string[]
  requires_human_review?: boolean
}

// Re-export from centralized types
export type {
  SentimentAnalysis,
  SentimentLabel,
  EmotionScores
} from '../../../types/api'

// Re-export from centralized types
export type {
  AIInsight,
  InsightType
} from '../../../types/api'

export interface AIRecommendation {
  id: string
  type: 'treatment' | 'communication' | 'follow_up' | 'alert'
  title: string
  description: string
  rationale: string
  confidence: number
  priority: 'low' | 'medium' | 'high'
  actions: RecommendedAction[]
  created_at: string
  updated_at?: string
  patient_id: string
}

export interface RecommendedAction {
  id: string
  type: 'message' | 'appointment' | 'medication' | 'test' | 'referral'
  title: string
  description: string
  urgency: 'low' | 'medium' | 'high'
  estimated_time?: string
  resources_needed?: string[]
}

export interface AnalysisRequest {
  data: any
  analysis_type: 'sentiment' | 'pattern' | 'anomaly' | 'trend' | 'classification'
  parameters?: Record<string, any>
}

export interface AnalysisResult {
  type: string
  result: any
  confidence: number
  metadata: Record<string, any>
  created_at: string
}

// Advanced Analytics Types
export interface PatientEngagementMetrics {
  patient_id: string
  response_rate: number
  avg_response_time: number // in minutes
  sentiment_trend: SentimentTrend[]
  engagement_score: number // 0-100
  last_interaction: string
  total_interactions: number
  preferred_communication_time?: string
}

export interface SentimentTrend {
  date: string
  sentiment_score: number
  message_count: number
}

export interface AIAnalyticsDashboard {
  overview: {
    total_conversations: number
    avg_sentiment: number
    response_accuracy: number
    human_handoff_rate: number
  }
  engagement_metrics: PatientEngagementMetrics[]
  insights: AIInsightImport[]
  recommendations: AIRecommendation[]
  performance_trends: PerformanceTrend[]
}

export interface PerformanceTrend {
  date: string
  conversations: number
  avg_sentiment: number
  response_accuracy: number
  resolution_rate: number
  patient_id?: string
}

// Flow AI Integration
export interface AIFlowContext {
  patient_id: string
  flow_type: string
  current_day: number
  patient_data: Record<string, any>
  conversation_history: AIChatMessageImport[]
  preferences: PatientPreferences
}

export interface PatientPreferences {
  communication_style: 'formal' | 'casual' | 'empathetic'
  language: string
  timezone: string
  preferred_time: string
  topics_of_interest: string[]
  sensitivity_level: 'low' | 'medium' | 'high'
}

export interface AIGeneratedMessage {
  content: string
  confidence: number
  personalization_applied: string[]
  alternatives?: string[]
  metadata: {
    intent: string
    tone: string
    length: number
    complexity_level: 'simple' | 'medium' | 'complex'
  }
}

// Real-time AI Events
export interface AIEvent {
  type: 'insight_generated' | 'recommendation_created' | 'anomaly_detected' | 'sentiment_alert'
  patient_id?: string
  data: any
  timestamp: string
  priority: 'low' | 'medium' | 'high' | 'critical'
}

// AI Configuration
export interface AIConfig {
  openai_model: string
  temperature: number
  max_tokens: number
  response_format: 'text' | 'json'
  safety_filters: boolean
  personalization_level: 'low' | 'medium' | 'high'
  human_review_threshold: number
}

// Error Types
export interface AIError {
  code: string
  message: string
  details?: Record<string, any>
  retry_after?: number
}

// Hooks Types
export interface UseAIChatOptions {
  patient_id?: string
  auto_save?: boolean
  max_messages?: number
  enable_suggestions?: boolean
}

export interface UseAIAnalyticsOptions {
  refresh_interval?: number
  include_insights?: boolean
  include_recommendations?: boolean
}

export interface UseAIInsightsOptions {
  patient_id?: string
  timeframe?: 'day' | 'week' | 'month' | 'quarter'
  types?: AIInsightImport['type'][]
  min_confidence?: number
}
