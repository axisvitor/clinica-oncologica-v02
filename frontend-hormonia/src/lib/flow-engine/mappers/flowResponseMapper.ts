import { FlowState, FlowType, FlowStatus } from '@/lib/api-client/types'

type FlowResponse = Partial<FlowState> & {
  current_step?: number
  last_interaction_at?: string
  template?: {
    id?: string
    metadata_json?: Record<string, unknown>
  }
  template_version?: string
  state_data?: Record<string, unknown>
  step_data?: Record<string, unknown>
  patient?: {
    name?: string
    monthly_cycle?: number
  }
}

export const smartMapFlowResponse = (
  response: FlowResponse | { data?: FlowResponse } | null | undefined
): FlowState => {
  const raw =
    response && typeof response === 'object' && 'data' in response
      ? (response as { data?: FlowResponse }).data ?? response
      : response
  const data = (raw ?? {}) as FlowResponse
  const status =
    data?.status ||
    (data?.paused_at
      ? FlowStatus.PAUSED
      : data?.completed_at
      ? FlowStatus.COMPLETED
      : FlowStatus.ACTIVE)
  const currentDay = data?.current_day ?? data?.current_step ?? 0
  const templateId =
    data?.template_id || data?.template?.id || data?.template_version || 'default-template'
  const fallbackId = data?.id || templateId || 'unknown-flow'
  const fallbackPatientId = data?.patient_id || 'unknown-patient'
  const flowType = (data?.flow_type ?? FlowType.ONBOARDING) as FlowType
  const enrollmentDate = data?.enrollment_date || data?.started_at || new Date().toISOString()
  const lastMessageSent = data?.last_message_sent || data?.last_interaction_at
  const stateData = data?.state_data || data?.step_data || {}
  const metadata = data?.metadata || data?.template?.metadata_json || {}
  const patientName = data?.patient_name || data?.patient?.name
  const monthlyCycle = data?.monthly_cycle || data?.patient?.monthly_cycle

  return {
    id: fallbackId,
    patient_id: fallbackPatientId,
    template_id: templateId,
    flow_type: flowType,
    status: status as FlowStatus,
    current_day: currentDay,
    enrollment_date: enrollmentDate,
    last_message_sent: lastMessageSent,
    state_data: stateData,
    sentiment_score: data?.sentiment_score,
    requires_attention: data?.requires_attention,
    started_at: data?.started_at || enrollmentDate,
    paused_at: data?.paused_at,
    completed_at: data?.completed_at,
    metadata,
    patient_name: patientName,
    monthly_cycle: monthlyCycle
  }
}
