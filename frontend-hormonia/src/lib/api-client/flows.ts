import type { ApiClientCore } from './core'
import type {
  FlowTemplate,
  FlowState,
  FlowListFilters,
  CreateFlowTemplateRequest,
  UpdateFlowTemplateRequest,
  FlowAdvanceRequest,
  FlowAnalytics,
  PaginatedResponse,
  MessageResponse,
  ResponseResult,
} from './types'

export interface FlowsApi {
  list: (options?: FlowListFilters) => Promise<PaginatedResponse<FlowState>>
  get: (flowId: string) => Promise<FlowTemplate>
  create: (data: CreateFlowTemplateRequest) => Promise<FlowTemplate>
  update: (flowId: string, data: UpdateFlowTemplateRequest) => Promise<FlowTemplate>
  delete: (flowId: string) => Promise<MessageResponse>
  activate: (flowId: string) => Promise<FlowTemplate>
  deactivate: (flowId: string) => Promise<FlowTemplate>
  execute: (flowId: string, data?: FlowAdvanceRequest) => Promise<FlowState>
  getExecutions: (flowId: string) => Promise<Array<Record<string, unknown>>>
  getState: (patientId: string) => Promise<FlowState>
  start: (patientId: string, flowType: string) => Promise<FlowState>
  advance: (patientId: string, day?: number) => Promise<FlowState>
  pause: (patientId: string) => Promise<FlowState>
  resume: (patientId: string) => Promise<FlowState>
  processResponse: (
    patientId: string,
    responseText: string,
    metadata?: Record<string, unknown>
  ) => Promise<ResponseResult>
  getAnalytics: () => Promise<FlowAnalytics>
  getTemplates: () => Promise<FlowTemplate[]>
  createTemplate: (template: CreateFlowTemplateRequest) => Promise<FlowTemplate>
  updateTemplate: (templateId: string, data: UpdateFlowTemplateRequest) => Promise<FlowTemplate>
  deleteTemplate: (templateId: string) => Promise<MessageResponse>
}

export function createFlowsApi(client: ApiClientCore): FlowsApi {
  return {
    list: (options?: FlowListFilters) =>
      client.get<PaginatedResponse<FlowState>>(
        '/api/v2/flows',
        options as Record<string, string | number | boolean>
      ),

    get: (flowId: string) => client.get<FlowTemplate>(`/api/v2/templates/flows/${flowId}`),

    create: (data: CreateFlowTemplateRequest) =>
      client.post<FlowTemplate>('/api/v2/templates/flows', data),

    update: (flowId: string, data: UpdateFlowTemplateRequest) =>
      client.put<FlowTemplate>(`/api/v2/templates/flows/${flowId}`, data),

    delete: (flowId: string) => client.delete<MessageResponse>(`/api/v2/templates/flows/${flowId}`),

    activate: (flowId: string) =>
      client.put<FlowTemplate>(`/api/v2/templates/flows/${flowId}`, { is_active: true }),

    deactivate: (flowId: string) =>
      client.put<FlowTemplate>(`/api/v2/templates/flows/${flowId}`, { is_active: false }),

    execute: (flowId: string, data?: FlowAdvanceRequest) =>
      client.post<FlowState>(`/api/v2/flows/${flowId}/advance`, data),

    getExecutions: (flowId: string) =>
      client.get<Array<Record<string, unknown>>>(`/api/v2/flows/${flowId}/history`),

    processResponse: (
      patientId: string,
      responseText: string,
      metadata?: Record<string, unknown>
    ) =>
      client.post<ResponseResult>(`/api/v2/flows/${patientId}/response`, {
        response_text: responseText,
        metadata,
      }),

    getState: (patientId: string) => client.get<FlowState>(`/api/v2/flows/${patientId}/state`),

    start: (patientId: string, flowType: string) =>
      client.post<FlowState>('/api/v2/flows/start', {
        patient_id: patientId,
        flow_type: flowType,
      }),

    advance: (patientId: string, day?: number) =>
      client.post<FlowState>(`/api/v2/flows/${patientId}/advance`, {
        target_day: day,
        skip_conditions: false,
      }),

    pause: (patientId: string) =>
      client.post<FlowState>(`/api/v2/flows/${patientId}/pause`, {
        reason: 'Manual pause',
      }),

    resume: (patientId: string) => client.post<FlowState>(`/api/v2/flows/${patientId}/resume`),

    getAnalytics: () => client.get<FlowAnalytics>('/api/v2/flows/analytics'),

    getTemplates: () => client.get<FlowTemplate[]>('/api/v2/templates/flows'),

    createTemplate: (template: CreateFlowTemplateRequest) =>
      client.post<FlowTemplate>('/api/v2/templates/flows', template),

    updateTemplate: (templateId: string, data: UpdateFlowTemplateRequest) =>
      client.put<FlowTemplate>(`/api/v2/templates/flows/${templateId}`, data),

    deleteTemplate: (templateId: string) =>
      client.delete<MessageResponse>(`/api/v2/templates/flows/${templateId}`),
  }
}
