import type { ApiClientCore } from './core'
import type {
  MessageResponse,
  PaginatedResponse,
  PatientQuizResponses,
  QuizSession,
  QuizSessionAnalysis,
  QuizSessionListFilters,
  QuizSessionResponses,
  QuizTemplate,
  QuizTemplateResponse,
} from './types'

export interface QuizApi {
  templates: (params?: Record<string, string | number | boolean>) => Promise<QuizTemplateResponse>
  start: (patientId: string, quizTemplateId: string) => Promise<QuizSession>
  getSession: (sessionId: string) => Promise<QuizSession>
  submitResponse: (
    sessionId: string,
    questionId: string,
    answer: string | string[],
    responseMetadata?: Record<string, unknown>
  ) => Promise<MessageResponse>
  sessions: (filters?: QuizSessionListFilters) => Promise<PaginatedResponse<QuizSession>>
  getPatientResponses: (
    patientId: string,
    options?: Record<string, unknown>
  ) => Promise<PatientQuizResponses>
  getSessionResponses: (sessionId: string) => Promise<QuizSessionResponses>
  getSessionAnalysis: (sessionId: string) => Promise<QuizSessionAnalysis>
}

export function createQuizApi(client: ApiClientCore): QuizApi {
  return {
    templates: async (
      params?: Record<string, string | number | boolean>
    ): Promise<QuizTemplateResponse> => {
      const res = await client.get<unknown>('/api/v2/templates/quizzes', params)
      return Array.isArray(res) ? { items: res as QuizTemplate[] } : (res as QuizTemplateResponse)
    },

    start: (patientId: string, quizTemplateId: string) =>
      client.post<QuizSession>('/api/v2/quiz', {
        patient_id: patientId,
        quiz_template_id: quizTemplateId,
      }),

    sessions: async (options?: QuizSessionListFilters) => {
      const { size, limit, cursor, patient_id, ...rest } = options || {}
      const effLimit = limit ?? size ?? 20
      const params: Record<string, string | number | boolean> = {
        limit: effLimit,
        ...(cursor ? { cursor } : {}),
        ...rest,
      }

      const endpoint = patient_id
        ? `/api/v2/quiz/patients/${patient_id}/quiz-responses`
        : '/api/v2/quiz/sessions'

      const res = await client.get<PaginatedResponse<QuizSession>>(endpoint, params)
      const items = Array.isArray(res?.data) ? res.data : (res?.items ?? [])
      return {
        data: items,
        items,
        total: res?.total ?? 0,
        has_more: res?.has_more,
        next_cursor: res?.next_cursor,
      }
    },

    getSessionResponses: (sessionId: string) =>
      client.get<QuizSessionResponses>(`/api/v2/quiz/${sessionId}/responses`),

    getSessionAnalysis: (sessionId: string) =>
      client.get<QuizSessionAnalysis>(`/api/v2/quiz/${sessionId}/analysis`),

    getSession: (sessionId: string) => client.get<QuizSession>(`/api/v2/quiz/sessions/${sessionId}`),

    submitResponse: (
      sessionId: string,
      questionId: string,
      answer: string | string[],
      responseMetadata?: Record<string, unknown>
    ) =>
      client.post<MessageResponse>(`/api/v2/quiz/sessions/${sessionId}/responses`, {
        question_id: questionId,
        answer,
        metadata: responseMetadata,
      }),

    getPatientResponses: async (
      patientId: string,
      options?: Record<string, unknown>
    ): Promise<PatientQuizResponses> => {
      const res = await client.get<PaginatedResponse<QuizSession>>('/api/v2/quiz-extensions/responses', {
        patient_id: patientId,
        ...(options as Record<string, string | number | boolean>),
      })
      const items = Array.isArray(res?.data) ? res.data : (res?.items ?? [])
      return {
        patient_id: patientId,
        sessions: items,
        total: res?.total ?? 0,
      }
    },
  }
}
