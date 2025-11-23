import { FlowState, FlowType, FlowStatus } from '@/lib/api-client/types'

export const smartMapFlowResponse = (response: any): FlowState => {
    // Handle potential nesting (e.g. response.data)
    const data = response.data || response

    return {
        id: data.id,
        patient_id: data.patient_id,
        template_id: data.template_id || 'default-template', // Fallback if missing
        flow_type: data.flow_type as FlowType,
        status: data.status as FlowStatus,
        current_day: data.current_day || 0,
        enrollment_date: data.enrollment_date || new Date().toISOString(),
        last_message_sent: data.last_message_sent,
        state_data: data.state_data || {},
        sentiment_score: data.sentiment_score,
        requires_attention: data.requires_attention,
        started_at: data.started_at || new Date().toISOString(),
        paused_at: data.paused_at,
        completed_at: data.completed_at,
        metadata: data.metadata || {},
        patient_name: data.patient_name,
        monthly_cycle: data.monthly_cycle
    }
}
