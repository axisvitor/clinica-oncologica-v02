import { useState, useCallback, useRef, useEffect } from 'react'
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
  UseAIInsightsOptions
} from '../lib/types/ai'
import { ChatRole, SentimentLabel } from '../types/api'
import { FEATURES } from '../config'

// AI Chat Hook
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
      patient_id,
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
      timestamp: new Date().toISOString()
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
      timestamp: new Date().toISOString()
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
          suggestions: enable_suggestions ? ['Como posso ajudar mais?'] : undefined,
          requires_human_review: false
        }
      }

      const assistantMessage: ChatMessage = {
        id: `msg-${Date.now() + 1}`,
        role: ChatRole.ASSISTANT,
        content: response.message,
        timestamp: new Date().toISOString(),
        metadata: {
          confidence: response.confidence,
          intent: response.intent,
          requires_review: response.requires_human_review
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
        timestamp: new Date().toISOString()
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
        patient_id,
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

// AI Analytics Hook
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

// AI Insights Hook
export function useAIInsights(options: UseAIInsightsOptions = {}) {
  const {
    patient_id,
    timeframe = 'week',
    types,
    min_confidence = 0.5
  } = options

  return useQuery({
    queryKey: ['ai-insights', patient_id, timeframe, types, min_confidence],
    queryFn: async () => {
      if (!FEATURES.AI_CHAT) {
        // Return mock insights
        return [
          {
            id: 'insight-1',
            type: 'pattern',
            title: 'Padrão de Engajamento',
            description: 'Pacientes respondem melhor pela manhã',
            confidence: 0.89,
            priority: 'medium',
            data: {},
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            patient_id
          }
        ] as AIInsight[]
      }
      
      return apiClient.ai.insights(patient_id || 'all', timeframe)
    },
    staleTime: 300000, // 5 minutes
    enabled: !!patient_id || !patient_id // Always enabled
  })
}

// AI Sentiment Analysis Hook
export function useSentimentAnalysis() {
  return useMutation({
    mutationFn: async (text: string): Promise<SentimentAnalysis> => {
      if (!FEATURES.AI_CHAT) {
        // Return mock sentiment
        return {
          score: Math.random() * 2 - 1, // -1 to 1
          magnitude: Math.random(),
          label: Math.random() > 0.5 ? SentimentLabel.POSITIVE : SentimentLabel.NEGATIVE,
          confidence: 0.8 + Math.random() * 0.2
        }
      }
      
      return apiClient.ai.sentiment(text)
    }
  })
}

// AI Recommendations Hook
export function useAIRecommendations(patientId?: string) {
  return useQuery({
    queryKey: ['ai-recommendations', patientId],
    queryFn: async () => {
      if (!FEATURES.AI_CHAT) {
        // Return mock recommendations
        return [
          {
            id: 'rec-1',
            type: 'communication',
            title: 'Otimizar Comunicação',
            description: 'Ajustar horário de envio de mensagens',
            rationale: 'Baseado em padrões de engajamento',
            confidence: 0.85,
            priority: 'medium',
            actions: [],
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            patient_id: patientId || 'all'
          }
        ] as AIRecommendation[]
      }
      
      return apiClient.ai.recommendations(patientId || 'all')
    },
    staleTime: 600000, // 10 minutes
    enabled: !!patientId || !patientId
  })
}

// AI Message Generation Hook
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
    }) => {
      if (!FEATURES.AI_CHAT) {
        // Return mock generated message
        return {
          content: 'Esta é uma mensagem gerada pela IA (simulação)',
          confidence: 0.85,
          personalization_applied: ['tone_adjustment', 'context_awareness'],
          alternatives: ['Alternativa 1', 'Alternativa 2'],
          metadata: {
            intent: intent || 'general',
            tone: 'friendly',
            length: 50,
            complexity_level: 'simple'
          }
        }
      }
      
      return apiClient.ai.generateResponse(patientId, messageHistory, intent)
    }
  })
}

// Combined AI Hook for convenience
export function useAI(patientId?: string) {
  const chat = useAIChat({ patient_id: patientId })
  const analytics = useAIAnalytics()
  const insights = useAIInsights({ patient_id: patientId })
  const recommendations = useAIRecommendations(patientId)
  const sentiment = useSentimentAnalysis()
  const messageGeneration = useAIMessageGeneration()

  return {
    chat,
    analytics,
    insights,
    recommendations,
    sentiment,
    messageGeneration,
    isEnabled: FEATURES.AI_CHAT
  }
}
