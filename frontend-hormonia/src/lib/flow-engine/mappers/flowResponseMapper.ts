import { FlowState, FlowType, FlowStatus } from '@/lib/api-client/types'

export const smartMapFlowResponse = (response: any): FlowState => {
  const data = response?.data || response
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
  const enrollmentDate = data?.enrollment_date || data?.started_at || new Date().toISOString()
  const lastMessageSent = data?.last_message_sent || data?.last_interaction_at
  const stateData = data?.state_data || data?.step_data || {}
  const metadata = data?.metadata || data?.template?.metadata_json || {}
  const patientName = data?.patient_name || data?.patient?.name
  const monthlyCycle = data?.monthly_cycle || data?.patient?.monthly_cycle

  return {
    id: data?.id,
    patient_id: data?.patient_id,
    template_id: templateId,
    flow_type: data?.flow_type as FlowType,
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
