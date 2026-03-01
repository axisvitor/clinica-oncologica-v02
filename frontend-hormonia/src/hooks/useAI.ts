import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../lib/api-client'
import { createLogger } from '../lib/logger'
import {
  AIChatMessage as ChatMessage,
  ChatSession,
  ChatResponse,
  AIRecommendation,
  SentimentAnalysis,
  UseAIChatOptions,
  UseAIAnalyticsOptions,
  UseAIInsightsOptions,
  UseAISummaryOptions,
  AIGeneratedMessage,
  ChatRole,
  InsightType
} from '@/types/api'
import type { AIInsight, AIInsights, AIRecommendations } from '@/lib/api-client/types'
import { mapInsightsToCards } from '@/lib/ai-adapters'
import { FEATURES } from '../config'

const logger = createLogger('useAI')

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Format risk level for display
 */
export function formatRiskLevel(level: 'low' | 'medium' | 'high' | 'critical'): {
  label: string
  color: string
  bgColor: string
} {
  const riskMap = {
    low: {
      label: 'Baixo',
      color: 'text-green-700',
      bgColor: 'bg-green-50'
    },
    medium: {
      label: 'Médio',
      color: 'text-yellow-700',
      bgColor: 'bg-yellow-50'
    },
    high: {
      label: 'Alto',
      color: 'text-orange-700',
      bgColor: 'bg-orange-50'
    },
    critical: {
      label: 'Crítico',
      color: 'text-red-700',
      bgColor: 'bg-red-50'
    }
  }
  return riskMap[level]
}

/**
 * Get color for sentiment score
 */
export function getSentimentColor(score: number): {
  color: string
  bgColor: string
  label: string
} {
  if (score >= 0.5) {
    return {
      color: 'text-green-700',
      bgColor: 'bg-green-50',
      label: 'Positivo'
    }
  } else if (score >= -0.2) {
    return {
      color: 'text-gray-700',
      bgColor: 'bg-gray-50',
      label: 'Neutro'
    }
  } else {
    return {
      color: 'text-red-700',
      bgColor: 'bg-red-50',
      label: 'Negativo'
    }
  }
}

/**
 * Prioritize recommendations by urgency and confidence
 */
export function prioritizeRecommendations(recommendations: AIRecommendation[]): AIRecommendation[] {
  const priorityWeight: Record<string, number> = {
    critical: 4,
    high: 3,
    medium: 2,
    low: 1
  }

  return [...recommendations].sort((a: AIRecommendation, b: AIRecommendation) => {
    const aPriority = priorityWeight[a.priority] || 0
    const bPriority = priorityWeight[b.priority] || 0

    // Sort by priority first, then by confidence
    if (aPriority !== bPriority) {
      return bPriority - aPriority
    }
    return b.confidence - a.confidence
  })
}

/**
 * Format confidence score as percentage
 */
export function formatConfidence(confidence: number): string {
  return `${Math.round(confidence * 100)}%`
}

/**
 * Get emoji for sentiment label
 */
export function getSentimentEmoji(label: 'positive' | 'negative' | 'neutral'): string {
  const emojiMap = {
    positive: '😊',
    negative: '😟',
    neutral: '😐'
  }
  return emojiMap[label]
}

// ============================================================================
// CUSTOM HOOKS
// ============================================================================

/**
 * Hook for AI chat interactions with optimistic updates
 */
export function useAIChat(options: UseAIChatOptions = {}) {
  const {
    patient_id,
    auto_save = true,
    max_messages = 100,
    enable_suggestions = true
  } = options

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [session, setSession] = useState<ChatSession | null>(null)
  const _queryClient = useQueryClient()

  // Create new session
  const createSession = useCallback(async () => {
    const newSession: ChatSession = {
      id: `session-${Date.now()}`,
      ...(patient_id ? { patient_id } : {}),
      user_id: 'current-user',
      title: patient_id ? `Chat - Paciente ${patient_id}` : 'Chat com IA',
      messages: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      status: 'active'
    }

    setSession(newSession)
    setMessages([])

    // Add welcome message
    const welcomeMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: ChatRole.ASSISTANT,
      content: patient_id
        ? `Olá! Como posso ajudar com o paciente ${patient_id}?`
        : 'Olá! Como posso ajudá-lo hoje?',
      timestamp: new Date().toISOString(),
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    }

    setMessages([welcomeMessage])
    return newSession
  }, [patient_id])

  // Send message
  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isLoading || !FEATURES.AI_CHAT) return

    const userMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: ChatRole.USER,
      content: content.trim(),
      timestamp: new Date().toISOString(),
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    }

    setMessages(prev => [...prev, userMessage])
    setIsLoading(true)

    try {
      const context = {
        patient_id,
        session_id: session?.id,
        conversation_history: messages.slice(-10)
      }

      let response: ChatResponse
      try {
        const apiResponse = await apiClient.ai.chat(content, context)
        response = {
          message: apiResponse.message || apiResponse.response,
          confidence: apiResponse.confidence || 0,
          suggestions: apiResponse.suggestions,
          entities: apiResponse.metadata
        }
      } catch {
        // Fallback to mock response
        response = {
          message: `Entendi sua mensagem: "${content}". Esta é uma resposta simulada da IA.`,
          confidence: 0.85,
          intent: 'general_inquiry',
          ...(enable_suggestions ? { suggestions: ['Como posso ajudar mais?'] } : {}),
          requires_human_review: false
        }
      }

      const assistantMessage: ChatMessage = {
        id: `msg-${Date.now() + 1}`,
        role: ChatRole.ASSISTANT,
        content: response.message,
        timestamp: new Date().toISOString(),
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        metadata: {
          confidence: response.confidence,
          ...(response.intent ? { intent: response.intent } : {}),
          ...(response.requires_human_review !== undefined ? { requires_review: response.requires_human_review } : {})
        }
      }

      setMessages(prev => {
        const newMessages = [...prev, assistantMessage]
        // Limit messages if max_messages is set
        if (max_messages && newMessages.length > max_messages) {
          return newMessages.slice(-max_messages)
        }
        return newMessages
      })

      // Auto-save session if enabled
      if (auto_save && session) {
        // In a real implementation, save to API
        // await apiClient.ai.saveSession(session.id, messages)
      }

      return response

    } catch (error) {
      logger.error('Failed to send message', { error, content })

      const errorMessage: ChatMessage = {
        id: `msg-${Date.now() + 1}`,
        role: ChatRole.ASSISTANT,
        content: 'Desculpe, ocorreu um erro ao processar sua mensagem.',
        timestamp: new Date().toISOString(),
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }

      setMessages(prev => [...prev, errorMessage])
      throw error
    } finally {
      setIsLoading(false)
    }
  }, [messages, session, patient_id, isLoading, auto_save, max_messages, enable_suggestions])

  // Clear conversation
  const clearMessages = useCallback(() => {
    setMessages([])
  }, [])

  // Load session
  const loadSession = useCallback(async (sessionId: string) => {
    try {
      // In a real implementation, load from API
      // const sessionData = await apiClient.ai.getSession(sessionId)
      // setSession(sessionData)
      // setMessages(sessionData.messages)

      // Mock for demo
      const mockSession: ChatSession = {
        id: sessionId,
        ...(patient_id ? { patient_id } : {}),
        user_id: 'current-user',
        title: 'Chat Carregado',
        messages: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        status: 'active'
      }
      setSession(mockSession)
    } catch (error) {
      logger.error('Failed to load session', { error, sessionId })
      throw error
    }
  }, [patient_id])

  return {
    messages,
    session,
    isLoading,
    sendMessage,
    createSession,
    loadSession,
    clearMessages,
    isEnabled: FEATURES.AI_CHAT
  }
}

/**
 * Hook for fetching patient AI insights with 5-minute cache
 */
export function useAIInsights(
  patientId: string,
  timeframe?: 'day' | 'week' | 'month' | 'quarter',
  options?: { enabled?: boolean }
) {
  return useQuery<AIInsights>({
    queryKey: ['ai-insights', patientId, timeframe],
    queryFn: async () => {
      if (!FEATURES.AI_INSIGHTS) {
        // Return mock insights response for demo
        return {
          patient_id: patientId,
          overall_status: 'Paciente com engajamento consistente',
          risk_level: 'low',
          sentiment_trends: [],
          adherence_score: 0.87,
          key_insights: [
            'Paciente demonstra engajamento consistente com as mensagens enviadas pela manha',
            'Sentimento geral das mensagens melhorou nos ultimos 7 dias'
          ],
          alerts: [],
          engagement_metrics: {
            response_rate: 0.92,
            total_messages: 45,
            avg_response_time_hours: 2.5
          },
          last_contact: new Date().toISOString(),
          generated_at: new Date().toISOString()
        } as AIInsights
      }

      return apiClient.ai.insights(patientId, timeframe)
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
    enabled: !!patientId && FEATURES.AI_INSIGHTS && (options?.enabled ?? true),
    retry: 2,
    refetchOnWindowFocus: false
  })
}

/**
 * Hook for fetching AI recommendations with 5-minute cache
 */
export function useAIRecommendations(
  patientId: string,
  options?: { enabled?: boolean }
) {
  return useQuery<AIRecommendations>({
    queryKey: ['ai-recommendations', patientId],
    queryFn: async () => {
      if (!FEATURES.AI_RECOMMENDATIONS) {
        // Return mock recommendations response
        return {
          patient_id: patientId,
          recommendations: [
            {
              type: 'engagement',
              priority: 'medium',
              description: 'Ajustar envio de mensagens para o periodo da manha',
              rationale: 'Paciente responde mais rapido entre 8h-10h'
            },
            {
              type: 'follow_up',
              priority: 'high',
              description: 'Realizar contato telefonico para verificar bem-estar',
              rationale: 'Paciente nao respondeu as ultimas 3 mensagens'
            }
          ],
          generated_at: new Date().toISOString()
        } as AIRecommendations
      }

      return apiClient.ai.recommendations(patientId)
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
    enabled: !!patientId && (options?.enabled ?? true),
    retry: 2,
    refetchOnWindowFocus: false
  })
}

/**
 * Hook for comprehensive patient summary with 10-minute cache
 */
export function useAISummary(patientId: string, options: UseAISummaryOptions = {}) {
  return useQuery({
    queryKey: ['ai-summary', patientId],
    queryFn: async () => {
      if (!FEATURES.AI_INSIGHTS || !FEATURES.AI_RECOMMENDATIONS) {
        // Return mock comprehensive summary
        return {
          patient_id: patientId,
          overall_sentiment: 0.72,
          engagement_score: 85,
          risk_level: 'low' as const,
          key_insights: [
            'Engajamento consistente com mensagens matinais',
            'Sentimento positivo nas últimas interações',
            'Responde bem a mensagens personalizadas'
          ],
          recommendations: 3,
          last_analysis: new Date().toISOString(),
          metrics: {
            total_messages: 247,
            response_rate: 0.89,
            avg_response_time: 45, // minutes
            sentiment_trend: 'improving' as const
          }
        }
      }

      // In real implementation, this would be a dedicated endpoint
      const [insights, recommendations] = await Promise.all([
        apiClient.ai.insights(patientId),
        apiClient.ai.recommendations(patientId)
      ])

      return {
        patient_id: patientId,
        insights,
        recommendations,
        last_analysis: new Date().toISOString()
      }
    },
    staleTime: 10 * 60 * 1000, // 10 minutes
    gcTime: 15 * 60 * 1000, // 15 minutes
    enabled: !!patientId && (options.enabled ?? false),
    retry: 2,
    refetchOnWindowFocus: false
  })
}

/**
 * Hook for analyzing patient data with AI
 */
export function useAIAnalyze() {
  const queryClient = useQueryClient()

  type AIAnalyzeVariables = {
    patientId: string
    analysisType: 'sentiment' | 'risk' | 'response'
    data: Record<string, unknown>
  }

  return useMutation({
    mutationFn: async ({
      patientId: _patientId,
      analysisType,
      data
    }: AIAnalyzeVariables) => {
      if (!FEATURES.AI_ANALYTICS) {
        // Return mock analysis
        return { type: analysisType, result: { status: 'mock', data } }
      }

      return apiClient.ai.analyze(data, analysisType)
    },
    onSuccess: (_: unknown, variables: AIAnalyzeVariables) => {
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ['ai-insights', variables.patientId] })
      queryClient.invalidateQueries({ queryKey: ['ai-recommendations', variables.patientId] })
      queryClient.invalidateQueries({ queryKey: ['ai-summary', variables.patientId] })
    }
  })
}

/**
 * Hook for sentiment analysis with optimistic updates
 */
export function useAISentiment(_text?: string) {
  return useMutation({
    mutationFn: async (textToAnalyze: string): Promise<SentimentAnalysis> => {
      if (!FEATURES.AI_ANALYTICS) {
        // Return mock sentiment
        const score = Math.random() * 2 - 1 // -1 to 1
        const sentiment: 'positive' | 'negative' | 'neutral' = score > 0.2 ? 'positive' : score < -0.2 ? 'negative' : 'neutral'
        return {
          score,
          sentiment,
          confidence: 0.8 + Math.random() * 0.2,
        }
      }

      return apiClient.ai.sentiment(textToAnalyze)
    },
    retry: 1
  })
}

/**
 * Hook for AI analytics dashboard with refresh interval
 */
export function useAIAnalytics(options: UseAIAnalyticsOptions = {}) {
  const {
    refresh_interval = 300000, // 5 minutes
    include_insights = true,
    include_recommendations = true
  } = options

  return useQuery({
    queryKey: ['ai-analytics', { include_insights, include_recommendations }],
    queryFn: async () => {
      if (!FEATURES.AI_ANALYTICS) {
        // Return mock data when AI is not configured
        return {
          overview: {
            total_conversations: 1247,
            avg_sentiment: 0.78,
            response_accuracy: 0.92,
            human_handoff_rate: 0.08
          },
          insights: include_insights ? [] : undefined,
          recommendations: include_recommendations ? [] : undefined
        }
      }

      logger.warn('AI analytics summary requires patient scope; returning empty summary.')
      return {
        overview: {
          total_conversations: 0,
          avg_sentiment: 0.5,
          response_accuracy: 0,
          human_handoff_rate: 0
        },
        insights: include_insights ? [] : undefined,
        recommendations: include_recommendations ? [] : undefined
      }
    },
    staleTime: refresh_interval,
    refetchInterval: refresh_interval,
    enabled: true // Allow mock data even when AI is disabled
  })
}

/**
 * Hook for detailed insights with filtering options (advanced)
 */
export function useAIInsightsAdvanced(options: UseAIInsightsOptions = {}) {
  const {
    patient_id,
    timeframe = 'week',
    types,
    min_confidence = 0.5
  } = options

  return useQuery({
    queryKey: ['ai-insights-advanced', patient_id, timeframe, types, min_confidence],
    queryFn: async () => {
      if (!FEATURES.AI_INSIGHTS) {
        // Return mock insights
        return [
          {
            id: `insight-detail-${Date.now()}`,
            type: 'pattern' as const,
            title: 'Padrão de Engajamento',
            description: 'Pacientes respondem melhor pela manhã',
            confidence: 0.89,
            priority: 'medium' as const,
            metadata: {
              time_range: '08:00-10:00',
              response_rate: 0.92
            },
            created_at: new Date().toISOString(),
            patient_id
          }
        ] as AIInsight[]
      }

      if (!patient_id) {
        return [] as AIInsight[]
      }

      const response = await apiClient.ai.insights(patient_id || '', timeframe)
      const insightsList = mapInsightsToCards(response)

      // Filter by confidence and type
      return insightsList
        .filter((insight: AIInsight) => insight.confidence >= min_confidence)
        .filter((insight: AIInsight) => !types || types?.includes(insight.type as unknown as InsightType))
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    enabled: !!patient_id
  })
}

/**
 * Hook for AI message generation with alternatives
 */
export function useAIMessageGeneration() {
  return useMutation({
    mutationFn: async ({
      patientId,
      messageHistory,
      intent
    }: {
      patientId: string
      messageHistory: ChatMessage[]
      intent?: string
    }): Promise<AIGeneratedMessage> => {
      if (!FEATURES.AI_CHAT) {
        // Return mock generated message
        return {
          content: 'Olá! Como você está se sentindo hoje? Gostaria de conversar sobre seu tratamento?',
          confidence: 0.85,
          personalization_applied: ['tone_adjustment', 'context_awareness', 'patient_history'],
          alternatives: [
            'Oi! Tudo bem com você hoje? Quer falar sobre como está indo o tratamento?',
            'Bom dia! Como tem se sentido? Estou aqui para ajudar no que precisar.'
          ],
          metadata: {
            intent: intent || 'general',
            tone: 'friendly',
            length: 75,
            complexity_level: 'simple'
          }
        }
      }

      const response = await apiClient.ai.generateResponse(patientId, messageHistory, intent)
      return {
        content: response.generated_response,
        confidence: response.confidence,
        personalization_applied: [],
        alternatives: response.alternative_responses,
        metadata: {
          intent: intent || 'general',
          tone: 'neutral',
          length: response.generated_response.length,
          complexity_level: 'medium'
        }
      }
    },
    retry: 1
  })
}

// ============================================================================
// COMBINED HOOKS FOR CONVENIENCE
// ============================================================================

/**
 * Combined AI hook for comprehensive patient AI data
 */
type UseAIOptions = {
  summaryEnabled?: boolean
}

export function useAI(patientId: string, options: UseAIOptions = {}) {
  const insights = useAIInsights(patientId)
  const recommendations = useAIRecommendations(patientId)
  const summary = useAISummary(patientId, { enabled: options.summaryEnabled ?? false })
  const analyze = useAIAnalyze()
  const sentiment = useAISentiment()
  const messageGeneration = useAIMessageGeneration()

  return {
    insights,
    recommendations,
    summary,
    analyze,
    sentiment,
    messageGeneration,
    isEnabled: FEATURES.AI_CHAT,
    // Utility functions exposed for convenience
    utils: {
      formatRiskLevel,
      getSentimentColor,
      prioritizeRecommendations,
      formatConfidence,
      getSentimentEmoji
    }
  }
}

/**
 * Hook specifically for AI chat functionality
 */
export function useAIChatOnly(options: UseAIChatOptions = {}) {
  const chat = useAIChat(options)
  const analytics = useAIAnalytics()

  return {
    ...chat,
    analytics,
    isEnabled: FEATURES.AI_CHAT
  }
}

// Export backward compatibility aliases
export { useAISentiment as useSentimentAnalysis }
