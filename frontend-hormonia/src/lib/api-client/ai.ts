import type {
  GenerateSummaryRequest,
  PatientSummaryListResponse,
  PatientSummaryResponse,
} from '@/types/api'

import type { ApiClientCore } from './core'
import type {
  AIAnalysisResponse,
  AIChatResponse,
  AIGenerateResponseResponse,
  AIHealthResponse,
  AIInsights,
  AIRecommendations,
  HumanizeRequest,
  HumanizeResponse,
  SentimentAnalysisResponse,
} from './types'

export type HumanizeContext = {
  patient_id?: string
  patientId?: string
  message_type?: string
  messageType?: string
  tone?: string
  tone_type?: string
  max_length?: number
  maxLength?: number
  use_cache?: boolean
  useCache?: boolean
}

type SentimentAnalysisPayload = {
  message?: string
  text?: string
  patient_id?: string
  include_medical_concerns?: boolean
  include_urgency?: boolean
}

export interface AiApi {
  health: () => Promise<AIHealthResponse>
  chat: (message: string, context?: HumanizeContext) => Promise<AIChatResponse>
  analyze: (
    data: unknown,
    analysisType: 'sentiment' | 'risk' | 'response'
  ) => Promise<AIAnalysisResponse>
  generateResponse: (
    patientId: string,
    messageHistory: Array<{ role: string; content: string }>,
    intent?: string
  ) => Promise<AIGenerateResponseResponse>
  sentiment: (text: string) => Promise<SentimentAnalysisResponse>
  insights: (patientId: string, timeframe?: string) => Promise<AIInsights>
  recommendations: (patientId: string) => Promise<AIRecommendations>
  generateSummary: (request: GenerateSummaryRequest) => Promise<PatientSummaryResponse>
  getSummaries: (
    patientId: string,
    limit?: number,
    offset?: number
  ) => Promise<PatientSummaryListResponse>
  getSummary: (summaryId: string) => Promise<PatientSummaryResponse>
  exportSummaryPdf: (summaryId: string) => Promise<Blob>
}

const timeframeToDays = (timeframe?: string) => {
  switch (timeframe) {
    case 'day':
      return 1
    case 'week':
      return 7
    case 'month':
      return 30
    case 'quarter':
      return 90
    default:
      return undefined
  }
}

const buildHumanizeRequest = (
  message: string,
  context?: HumanizeContext,
  overrides?: Partial<HumanizeRequest>
): HumanizeRequest => {
  const patientId =
    typeof context?.patient_id === 'string'
      ? context.patient_id
      : typeof context?.patientId === 'string'
        ? context.patientId
        : undefined
  const messageType =
    typeof context?.message_type === 'string'
      ? context.message_type
      : typeof context?.messageType === 'string'
        ? context.messageType
        : undefined
  const tone =
    typeof context?.tone === 'string'
      ? context.tone
      : typeof context?.tone_type === 'string'
        ? context.tone_type
        : undefined
  const maxLength =
    typeof context?.max_length === 'number'
      ? context.max_length
      : typeof context?.maxLength === 'number'
        ? context.maxLength
        : undefined
  const useCache =
    typeof context?.use_cache === 'boolean'
      ? context.use_cache
      : typeof context?.useCache === 'boolean'
        ? context.useCache
        : undefined

  return {
    message,
    ...(patientId && patientId !== 'all' ? { patient_id: patientId } : {}),
    message_type: messageType as HumanizeRequest['message_type'] | undefined,
    tone: tone as HumanizeRequest['tone'] | undefined,
    max_length: maxLength,
    use_cache: useCache ?? true,
    ...overrides,
  }
}

export function createAiApi(client: ApiClientCore): AiApi {
  return {
    health: () => client.get<AIHealthResponse>('/api/v2/ai/health'),

    chat: async (message: string, context?: HumanizeContext) => {
      const response = await client.post<HumanizeResponse>(
        '/api/v2/ai/humanize',
        buildHumanizeRequest(message, context)
      )
      const confidence = Math.max(0, Math.min(1, (response.readability_score ?? 0) / 100))
      return {
        response: response.humanized_message,
        message: response.humanized_message,
        confidence,
        metadata: {
          personalization_notes: response.personalization_notes,
          tone_analysis: response.tone_analysis,
          cache_info: response.cache_info,
          token_usage: response.token_usage,
        },
      }
    },

    analyze: async (data: unknown, analysisType: 'sentiment' | 'risk' | 'response') => {
      if (analysisType === 'sentiment') {
        const payload = data as SentimentAnalysisPayload
        const message =
          (typeof payload?.message === 'string' && payload.message) ||
          (typeof payload?.text === 'string' && payload.text) ||
          ''
        const response = await client.post<Record<string, unknown>>('/api/v2/ai/analyze/sentiment', {
          message,
          patient_id: payload?.patient_id,
          include_medical_concerns: payload?.include_medical_concerns ?? true,
          include_urgency: payload?.include_urgency ?? true,
        })
        return { type: 'sentiment', result: response }
      }

      if (analysisType === 'risk') {
        const response = await client.post<Record<string, unknown>>('/api/v2/ai/analyze/risk', data)
        return { type: 'risk', result: response }
      }

      if (analysisType === 'response') {
        const response = await client.post<Record<string, unknown>>('/api/v2/ai/analyze/response', data)
        return { type: 'response', result: response }
      }

      throw new Error(`Unsupported analysis type: ${analysisType}`)
    },

    generateResponse: async (
      patientId: string,
      messageHistory: Array<{ role: string; content: string }>,
      intent?: string
    ) => {
      const lastMessage = [...messageHistory]
        .reverse()
        .find((entry) => entry.content?.trim())?.content
      const template =
        lastMessage ||
        (intent
          ? `Gerar uma resposta empatica para o contexto: ${intent}`
          : 'Responder de forma empatica e profissional.')
      const response = await client.post<HumanizeResponse>(
        '/api/v2/ai/humanize',
        buildHumanizeRequest(template, { patient_id: patientId }, { use_cache: false })
      )
      return {
        generated_response: response.humanized_message,
        confidence: Math.max(0, Math.min(1, (response.readability_score ?? 0) / 100)),
        alternative_responses: [],
      }
    },

    sentiment: async (text: string) => {
      const response = await client.post<{
        sentiment?: string
        confidence?: number
      }>('/api/v2/ai/analyze/sentiment', { message: text })
      const sentiment =
        response.sentiment === 'positive' || response.sentiment === 'negative'
          ? response.sentiment
          : 'neutral'
      const score = sentiment === 'positive' ? 0.8 : sentiment === 'negative' ? 0.2 : 0.5
      return {
        sentiment,
        score,
        confidence: response.confidence ?? 0,
      }
    },

    insights: (patientId: string, timeframe?: string) => {
      if (!patientId || patientId === 'all') {
        return Promise.reject(new Error('patientId is required for AI insights'))
      }
      const days = timeframeToDays(timeframe)
      return client.get<AIInsights>(`/api/v2/ai/insights/${patientId}`, days ? { days } : undefined)
    },

    recommendations: (patientId: string) =>
      client.get<AIRecommendations>(`/api/v2/ai/recommendations/${patientId}`),

    generateSummary: (request: GenerateSummaryRequest) =>
      client.post<PatientSummaryResponse>('/api/v2/ai/summary', request),

    getSummaries: (patientId: string, limit = 10, offset = 0) =>
      client.get<PatientSummaryListResponse>(`/api/v2/ai/summary/patient/${patientId}`, {
        limit,
        offset,
      }),

    getSummary: (summaryId: string) =>
      client.get<PatientSummaryResponse>(`/api/v2/ai/summary/${summaryId}`),

    exportSummaryPdf: async (summaryId: string): Promise<Blob> => {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        ...client.getSessionHeaders(),
      }
      const response = await fetch(`${client.getBaseURL()}/api/v2/ai/summary/${summaryId}/pdf`, {
        method: 'GET',
        headers,
        credentials: 'include',
      })
      if (!response.ok) {
        throw new Error(`Failed to export PDF: ${response.statusText}`)
      }
      return response.blob()
    },
  }
}
