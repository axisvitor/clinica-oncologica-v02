export interface AIChatRequest {
  message: string
  context?: Record<string, unknown>
}

export interface AIChatResponse {
  response: string
  message?: string
  confidence?: number
  suggestions?: string[]
  metadata?: Record<string, unknown>
}

export interface HumanizeRequest {
  message: string
  patient_id?: string
  message_type?: 'welcome' | 'check_in' | 'reminder' | 'support' | 'education' | 'general'
  tone?: 'empathetic' | 'professional' | 'encouraging' | 'caring' | 'neutral'
  max_length?: number
  use_cache?: boolean
}

export interface TokenUsage {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  estimated_cost_usd?: number
  model?: string
}

export interface CacheInfo {
  hit: boolean
  key: string
  ttl_seconds: number
  cached_at?: string
}

export interface HumanizeResponse {
  original_message: string
  humanized_message: string
  personalization_notes: string[]
  readability_score: number
  tone_analysis: Record<string, number>
  cache_info?: CacheInfo
  token_usage?: TokenUsage
}

export interface AIHealthResponse {
  status: string
  services: Record<string, string>
  redis_cache: Record<string, unknown>
  gemini_api: Record<string, unknown>
  response_time_ms: number
  timestamp: string
}

export interface AIAnalysisRequest {
  data: unknown
  analysis_type: 'sentiment' | 'risk' | 'response'
}

export interface AIAnalysisResponse {
  type: 'sentiment' | 'risk' | 'response'
  result: Record<string, unknown>
}

export interface AIGenerateResponseRequest {
  patient_id: string
  message_history: Array<{ role: string; content: string }>
  intent?: string
}

export interface AIGenerateResponseResponse {
  generated_response: string
  confidence: number
  alternative_responses?: string[]
}

export interface SentimentAnalysisRequest {
  message: string
  patient_id?: string
  include_medical_concerns?: boolean
  include_urgency?: boolean
}

export interface SentimentAnalysisResponse {
  sentiment: 'positive' | 'negative' | 'neutral'
  score: number
  confidence: number
}

export interface AIInsight {
  id: string
  type: string
  title: string
  description: string
  confidence: number
  priority?: 'low' | 'medium' | 'high' | 'critical'
  patient_id?: string
  created_at: string
  metadata?: Record<string, unknown>
  risk_level?: 'low' | 'medium' | 'high' | 'critical'
  risk_factors?: string[]
}

export interface TrendData {
  metric: string
  direction: 'improving' | 'declining' | 'stable'
  change_percentage: number
  current_value?: number
  previous_value?: number
  data_points: Record<string, unknown>[]
}

export interface AIInsights {
  patient_id: string
  overall_status: string
  risk_level: 'low' | 'medium' | 'high' | 'critical'
  sentiment_trends: TrendData[]
  adherence_score: number
  key_insights: string[]
  alerts: Record<string, unknown>[]
  engagement_metrics: Record<string, unknown>
  last_contact?: string
  token_usage?: TokenUsage
  cache_info?: CacheInfo
  generated_at: string
}

export interface AIRecommendation {
  type: string
  priority: 'low' | 'medium' | 'high'
  description: string
  rationale: string
}

export interface AIRecommendations {
  patient_id: string
  recommendations: AIRecommendation[]
  generated_at?: string
}
