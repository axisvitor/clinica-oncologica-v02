/**
 * Legacy AI Types - Enhanced AI type definitions have been moved
 * @deprecated Import AI types from '/types/api' for the latest definitions
 */

// Import and re-export AI-related types from the centralized API types module
import type {
  AIChatMessage,
  AIInsight as AIInsightType,
  ChatSession as ChatSessionType
} from '../src/types/api'

// Export types with backward compatibility aliases
export type ChatMessage = AIChatMessage
export { ChatRole } from '../src/types/api'
export type AIInsight = AIInsightType
export type ChatSession = ChatSessionType

// Re-export other AI-related types
export type {
  SentimentAnalysis,
  SentimentLabel,
  EmotionScores,
  InsightType
} from '../src/types/api'

// Export missing AIRecommendation interface for backward compatibility
export interface AIRecommendation {
  id: string
  type: 'treatment' | 'communication' | 'follow_up' | 'alert'
  title: string
  description: string
  rationale: string
  confidence: number
  priority: 'low' | 'medium' | 'high'
  actions: Array<{
    id: string
    type: string
    title: string
    description: string
    urgency: string
  }>
  created_at: string
  updated_at: string
  patient_id: string
}

// Export PerformanceTrend interface for AI analytics
export interface PerformanceTrend {
  patient_id: string
  date: string
  conversations: number
  avg_sentiment: number
  response_accuracy: number
  resolution_rate: number
  accuracy?: number
  response_time?: number
  usage?: number
  success_rate?: number
  error_rate?: number
  throughput?: number
}

// Export AIAnalyticsDashboard interface
export interface AIAnalyticsDashboard {
  insights: AIInsight[]
  metrics: {
    total_conversations: number
    avg_sentiment: number
    response_accuracy: number
    human_handoff_rate: number
    total_insights: number
    critical_alerts: number
    recommendations_count: number
    accuracy_score: number
    engagement_rate: number
    resolution_time: number
    customer_satisfaction: number
    ai_confidence: number
  }
  recommendations: AIRecommendation[]
  trends: Array<{
    name: string
    value: number
    change: number
    trend: 'up' | 'down' | 'stable'
    period: string
  }>
  overview: {
    total_conversations: number
    avg_sentiment: number
    response_accuracy: number
    human_handoff_rate: number
    total_insights: number
    critical_alerts: number
    recommendations_count: number
    accuracy_score: number
    engagement_rate: number
    active_sessions: number
    daily_messages: number
    response_time_avg: number
  }
  engagement_metrics: Array<{
    patient_id: string
    response_rate: number
    avg_response_time: number
    sentiment_trend: Array<{ date: string; value: number }>
    engagement_score: number
    last_interaction: string
    total_interactions: number
    name?: string
    value?: number
    change?: number
    trend?: 'up' | 'down' | 'stable'
    satisfaction_score?: number
    messages_sent: number
    messages_received: number
  }>
  performance_trends: PerformanceTrend[]
}

// Legacy type aliases - use types from /types/api.ts instead
export interface ChatResponse {
  message: string
  confidence: number
  intent?: string
  entities?: Record<string, unknown>
  suggestions?: string[]
  requires_human_review?: boolean
}

export interface AnalysisRequest {
  data: unknown
  analysis_type: 'sentiment' | 'pattern' | 'anomaly' | 'trend' | 'classification'
  parameters?: Record<string, unknown>
}

export interface AnalysisResult {
  type: string
  result: unknown
  confidence: number
  metadata: Record<string, unknown>
  created_at: string
}

// All advanced AI types have been moved to /types/api.ts
// Please import from /types/api for the latest AI type definitions

// Legacy hook options for backward compatibility
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
  types?: string[]
  min_confidence?: number
}

// Additional types for AI functionality
export interface PatientEngagementMetrics {
  patient_id: string
  response_rate: number
  avg_response_time: number
  engagement_score: number
  sentiment_trend: Array<{ date: string; value: number }>
  last_interaction: string
  total_interactions: number
}

export interface AIGeneratedMessage {
  content: string
  confidence: number
  personalization_applied: string[]
  alternatives: string[]
  metadata: {
    intent: string
    tone: string
    length: number
    complexity_level: string
  }
}
