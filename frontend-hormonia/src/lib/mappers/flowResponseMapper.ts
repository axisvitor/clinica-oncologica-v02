/**
 * Maps backend flow responses to frontend FlowState format
 *
 * Backend returns nested structure:
 * - flow_state: { id, patient_id, flow_type, status, metadata }
 * - advancement_result: { current_day, next_scheduled, ... }
 *
 * Frontend expects flat FlowState:
 * - id, patient_id, flow_type, status, current_day, ...
 */

import type { FlowState } from '../types/flow'

interface FlowAdvancementResult {
  current_day: number
  next_scheduled?: string
  messages_sent?: number
  completion_percentage?: number
}

interface BackendFlowResponse {
  flow_state: {
    id: string
    patient_id: string
    flow_type: string
    status: string
    metadata?: Record<string, any>
    created_at?: string
    updated_at?: string
  }
  advancement_result?: FlowAdvancementResult
}

/**
 * Converts backend nested flow response to frontend flat FlowState
 */
export function mapFlowResponse(backendResponse: BackendFlowResponse): FlowState {
  const { flow_state, advancement_result } = backendResponse

  return {
    id: flow_state.id,
    patient_id: flow_state.patient_id,
    flow_type: flow_state.flow_type as any, // Cast to FlowType enum
    status: flow_state.status as any, // Cast to FlowStatus enum
    current_day: advancement_result?.current_day || 0,
    current_state: `day_${advancement_result?.current_day || 0}`,
    is_paused: flow_state.status === 'paused',
    enrollment_date: flow_state.created_at || new Date().toISOString(),
    next_scheduled: advancement_result?.next_scheduled,
    state_data: flow_state.metadata || {},
    metadata: flow_state.metadata || {},
    created_at: flow_state.created_at || new Date().toISOString(),
    updated_at: flow_state.updated_at || new Date().toISOString(),
    // Additional fields from advancement_result
    messages_sent: advancement_result?.messages_sent,
    completion_percentage: advancement_result?.completion_percentage
  } as FlowState
}

/**
 * Type guard to check if response matches nested backend structure
 */
export function isNestedFlowResponse(data: any): data is BackendFlowResponse {
  return (
    data &&
    typeof data === 'object' &&
    data.flow_state &&
    typeof data.flow_state === 'object' &&
    typeof data.flow_state.id === 'string' &&
    typeof data.flow_state.patient_id === 'string'
  )
}

/**
 * Smart mapper that handles both nested and flat responses
 */
export function smartMapFlowResponse(response: any): FlowState {
  if (isNestedFlowResponse(response)) {
    return mapFlowResponse(response)
  }

  // Already flat, return as-is
  return response as FlowState
}
