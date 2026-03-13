import type { ApiClientCore } from './core'
import type { MessageResponse, QuizTemplate, QuizTemplateResponse } from './types'

export interface CreateQuizTemplateRequest {
  name: string
  description?: string
  version?: string
  is_active?: boolean
  questions: Array<{
    question_text: string
    question_type: string
    options?: string[]
    required?: boolean
  }>
}

export interface UpdateQuizTemplateRequest extends Partial<CreateQuizTemplateRequest> {}

export interface QuizTemplateAnalytics {
  template_id: string
  total_sessions: number
  completed_sessions: number
  completion_rate: number
  average_score?: number
}

export interface QuizTemplatesApi {
  list: (params?: Record<string, string | number | boolean>) => Promise<QuizTemplateResponse>
  listTemplates: (params?: Record<string, string | number | boolean>) => Promise<QuizTemplateResponse>
  createTemplate: (template: CreateQuizTemplateRequest) => Promise<QuizTemplate>
  create: (template: CreateQuizTemplateRequest) => Promise<QuizTemplate>
  updateTemplate: (templateId: string, data: UpdateQuizTemplateRequest) => Promise<QuizTemplate>
  deleteTemplate: (templateId: string) => Promise<MessageResponse>
  getTemplateAnalytics: (templateId: string) => Promise<QuizTemplateAnalytics>
}

const listTemplates = async (
  client: ApiClientCore,
  params?: Record<string, string | number | boolean>
): Promise<QuizTemplateResponse> => {
  const res = await client.get<unknown>('/api/v2/templates/quizzes', params)
  return Array.isArray(res) ? { items: res as QuizTemplate[] } : (res as QuizTemplateResponse)
}

export function createQuizTemplatesApi(client: ApiClientCore): QuizTemplatesApi {
  return {
    list: (options) => listTemplates(client, options),
    listTemplates: (options) => listTemplates(client, options),
    createTemplate: (template: CreateQuizTemplateRequest) =>
      client.post<QuizTemplate, CreateQuizTemplateRequest>('/api/v2/templates/quizzes', template),
    create: (template: CreateQuizTemplateRequest) =>
      client.post<QuizTemplate, CreateQuizTemplateRequest>('/api/v2/templates/quizzes', template),
    updateTemplate: (templateId: string, data: UpdateQuizTemplateRequest) =>
      client.put<QuizTemplate, UpdateQuizTemplateRequest>(`/api/v2/templates/quizzes/${templateId}`, data),
    deleteTemplate: (templateId: string) =>
      client.delete<MessageResponse>(`/api/v2/templates/quizzes/${templateId}`),
    getTemplateAnalytics: (templateId: string) =>
      client.get<QuizTemplateAnalytics>(`/api/v2/templates/quizzes/${templateId}/analytics`),
  }
}
