import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../lib/api-client'
import {
  ChatMessage,
  ChatSession,
  ChatResponse,
  AIInsight,
  AIRecommendation,
  SentimentAnalysis,
  UseAIChatOptions,
  UseAIAnalyticsOptions,
  UseAIInsightsOptions,
  PatientEngagementMetrics,
  AIGeneratedMessage
} from '../lib/types/ai'
import { ChatRole, SentimentLabel } from '../../types/api'
import { FEATURES } from '../config'

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
  const queryClient = useQueryClient()

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
        response = await apiClient.ai.chat(content, context)
      } catch (error) {
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
      console.error('Failed to send message:', error)
      
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
      console.error('Failed to load session:', error)
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
export function useAIInsights(patientId: string) {
  return useQuery({
    queryKey: ['ai-insights', patientId],
    queryFn: async () => {
      if (!FEATURES.AI_CHAT) {
        // Return mock insights for demo
        return [
          {
            id: `insight-${Date.now()}-1`,
            type: 'pattern' as const,
            title: 'Padrão de Resposta Positivo',
            description: 'Paciente demonstra engajamento consistente com as mensagens enviadas pela manhã',
            confidence: 0.89,
            priority: 'medium' as const,
            data: {
              response_rate: 0.92,
              preferred_time: '08:00-10:00'
            },
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            patient_id: patientId
          },
          {
            id: `insight-${Date.now()}-2`,
            type: 'trend' as const,
            title: 'Melhora no Sentimento',
            description: 'Sentimento geral das mensagens melhorou 15% nos últimos 7 dias',
            confidence: 0.82,
            priority: 'high' as const,
            data: {
              trend: 'upward',
              change_percentage: 15
            },
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            patient_id: patientId
          }
        ] as AIInsight[]
      }

      return apiClient.ai.insights(patientId)
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
    enabled: !!patientId,
    retry: 2,
    refetchOnWindowFocus: false
  })
}

/**
 * Hook for fetching AI recommendations with 5-minute cache
 */
export function useAIRecommendations(patientId: string) {
  return useQuery({
    queryKey: ['ai-recommendations', patientId],
    queryFn: async () => {
      if (!FEATURES.AI_CHAT) {
        // Return mock recommendations
        return [
          {
            id: `rec-${Date.now()}-1`,
            type: 'communication' as const,
            title: 'Otimizar Horário de Mensagens',
            description: 'Ajustar envio de mensagens para o período da manhã',
            rationale: 'Baseado em padrões de engajamento, o paciente responde 40% mais rápido entre 8h-10h',
            confidence: 0.85,
            priority: 'medium' as const,
            actions: [
              {
                id: 'action-1',
                type: 'message' as const,
                title: 'Agendar mensagens matinais',
                description: 'Configurar envio automático de mensagens entre 8h-10h',
                urgency: 'medium' as const,
                estimated_time: '5 minutos',
                resources_needed: ['Sistema de agendamento']
              }
            ],
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            patient_id: patientId
          },
          {
            id: `rec-${Date.now()}-2`,
            type: 'follow_up' as const,
            title: 'Acompanhamento Necessário',
            description: 'Paciente não respondeu às últimas 3 mensagens',
            rationale: 'Queda no engajamento pode indicar necessidade de contato direto',
            confidence: 0.78,
            priority: 'high' as const,
            actions: [
              {
                id: 'action-2',
                type: 'appointment' as const,
                title: 'Agendar contato telefônico',
                description: 'Realizar contato telefônico para verificar bem-estar',
                urgency: 'high' as const,
                estimated_time: '15 minutos'
              }
            ],
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            patient_id: patientId
          }
        ] as AIRecommendation[]
      }

      return apiClient.ai.recommendations(patientId)
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
    enabled: !!patientId,
    retry: 2,
    refetchOnWindowFocus: false
  })
}

/**
 * Hook for comprehensive patient summary with 10-minute cache
 */
export function useAISummary(patientId: string) {
  return useQuery({
    queryKey: ['ai-summary', patientId],
    queryFn: async () => {
      if (!FEATURES.AI_CHAT) {
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
    enabled: !!patientId,
    retry: 2,
    refetchOnWindowFocus: false
  })
}

/**
 * Hook for analyzing patient data with AI
 */
export function useAIAnalyze() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      patientId,
      analysisType,
      data
    }: {
      patientId: string
      analysisType: 'sentiment' | 'pattern' | 'anomaly' | 'trend' | 'classification'
      data: any
    }) => {
      if (!FEATURES.AI_CHAT) {
        // Return mock analysis
        return {
          type: analysisType,
          result: {
            status: 'completed',
            insights: ['Mock insight 1', 'Mock insight 2'],
            confidence: 0.85
          },
          confidence: 0.85,
          metadata: {
            analyzed_at: new Date().toISOString(),
            data_points: 150
          },
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        }
      }

      return apiClient.ai.analyze(data, analysisType)
    },
    onSuccess: (_, variables) => {
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
export function useAISentiment(text?: string) {
  return useMutation({
    mutationFn: async (textToAnalyze: string): Promise<SentimentAnalysis> => {
      if (!FEATURES.AI_CHAT) {
        // Return mock sentiment
        const score = Math.random() * 2 - 1 // -1 to 1
        return {
          score,
          magnitude: Math.abs(score),
          label: score > 0.2 ? SentimentLabel.POSITIVE : score < -0.2 ? SentimentLabel.NEGATIVE : SentimentLabel.NEUTRAL,
          confidence: 0.8 + Math.random() * 0.2,
          emotions: {
            joy: score > 0 ? Math.random() * score : 0,
            sadness: score < 0 ? Math.random() * Math.abs(score) : 0,
            anger: Math.random() * 0.3,
            fear: Math.random() * 0.2,
            surprise: Math.random() * 0.4
          }
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
      if (!FEATURES.AI_CHAT) {
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
      
      // In a real implementation, call API
      return apiClient.ai.insights('all')
    },
    staleTime: refresh_interval,
    refetchInterval: refresh_interval,
    enabled: FEATURES.AI_CHAT || true // Allow mock data even when AI is disabled
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
      if (!FEATURES.AI_CHAT) {
        // Return mock insights
        return [
          {
            id: `insight-detail-${Date.now()}`,
            type: 'pattern' as const,
            title: 'Padrão de Engajamento',
            description: 'Pacientes respondem melhor pela manhã',
            confidence: 0.89,
            priority: 'medium' as const,
            data: {
              time_range: '08:00-10:00',
              response_rate: 0.92
            },
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            patient_id
          }
        ] as AIInsight[]
      }

      const insights = await apiClient.ai.insights(patient_id || 'all', timeframe)

      // Filter by confidence and type
      return insights
        .filter((insight: AIInsight) => insight.confidence >= min_confidence)
        .filter((insight: AIInsight) => !types || types.includes(insight.type))
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    enabled: !!patient_id || !patient_id
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

      return apiClient.ai.generateResponse(patientId, messageHistory, intent)
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
export function useAI(patientId: string) {
  const insights = useAIInsights(patientId)
  const recommendations = useAIRecommendations(patientId)
  const summary = useAISummary(patientId)
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
