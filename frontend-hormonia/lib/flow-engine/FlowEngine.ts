import {
  FlowState,
  MessageTemplate,
  FlowTemplate,
  InboundMessage,
  ResponseResult,
  FlowEvent,
  FlowStateMachine,
  ResponseType
} from '../types/flow'
import { FlowType } from '../../types/api'
import { apiClient } from '../api-client'
import * as EventEmitter from 'eventemitter3'

export class FlowEngine extends EventEmitter.EventEmitter {
  private templates: Map<FlowType, FlowTemplate> = new Map()
  private stateMachines: Map<FlowType, FlowStateMachine> = new Map()
  private activeFlows: Map<string, FlowState> = new Map()

  constructor() {
    super()
    this.initializeStateMachines()
  }

  // Initialize state machines for different flow types
  private initializeStateMachines() {
    // Initial 15 days flow state machine
    const initial15DaysStateMachine: FlowStateMachine = {
      states: ['enrolled', 'day_1', 'day_2', 'day_3', 'day_7', 'day_10', 'day_15', 'completed', 'paused'],
      initial_state: 'enrolled',
      transitions: [
        { from_state: 'enrolled', to_state: 'day_1', trigger: 'start_flow' },
        { from_state: 'day_1', to_state: 'day_2', trigger: 'advance_day' },
        { from_state: 'day_2', to_state: 'day_3', trigger: 'advance_day' },
        { from_state: 'day_3', to_state: 'day_7', trigger: 'advance_day' },
        { from_state: 'day_7', to_state: 'day_10', trigger: 'advance_day' },
        { from_state: 'day_10', to_state: 'day_15', trigger: 'advance_day' },
        { from_state: 'day_15', to_state: 'completed', trigger: 'complete_flow' },
        { from_state: '*', to_state: 'paused', trigger: 'pause_flow' },
        { from_state: 'paused', to_state: '*', trigger: 'resume_flow' }
      ],
      final_states: ['completed']
    }

    this.stateMachines.set(FlowType.INITIAL_15_DAYS, initial15DaysStateMachine)
  }

  // Load flow templates
  async loadTemplates(): Promise<void> {
    try {
      // TODO: Implement template loading from API
      console.warn('Flow templates loading not yet implemented')
    } catch (error) {
      console.error('Failed to load flow templates:', error)
    }
  }

  // Get current flow state for a patient
  async getFlowState(patientId: string): Promise<FlowState | null> {
    try {
      const flowState = await apiClient.flows.getState(patientId)
      if (flowState) {
        this.activeFlows.set(patientId, flowState)
      }
      return flowState
    } catch (error) {
      console.error('Failed to get flow state:', error)
      return null
    }
  }

  // Start a new flow for a patient
  async startFlow(patientId: string, flowType: FlowType): Promise<FlowState> {
    try {
      const flowState = await apiClient.flows.start({ patient_id: patientId, flow_type: flowType })
      this.activeFlows.set(patientId, flowState)
      
      this.emit('flow_started', {
        type: 'flow_started',
        patient_id: patientId,
        flow_id: flowState.id,
        data: { flow_type: flowType },
        timestamp: new Date().toISOString()
      } as FlowEvent)

      return flowState
    } catch (error) {
      console.error('Failed to start flow:', error)
      throw error
    }
  }

  // Advance flow to next state
  async advanceFlow(patientId: string, forceDay?: number): Promise<FlowState> {
    try {
      const flowState = await apiClient.flows.advance(patientId, forceDay)
      this.activeFlows.set(patientId, flowState)
      
      this.emit('flow_advanced', {
        type: 'message_sent',
        patient_id: patientId,
        flow_id: flowState.id,
        data: { current_day: flowState.current_day },
        timestamp: new Date().toISOString()
      } as FlowEvent)

      return flowState
    } catch (error) {
      console.error('Failed to advance flow:', error)
      throw error
    }
  }

  // Pause a flow
  async pauseFlow(patientId: string): Promise<FlowState> {
    try {
      const flowState = await apiClient.flows.pause(patientId)
      this.activeFlows.set(patientId, flowState)
      
      this.emit('flow_paused', {
        type: 'flow_paused',
        patient_id: patientId,
        flow_id: flowState.id,
        data: { status: 'paused' },
        timestamp: new Date().toISOString()
      } as FlowEvent)

      return flowState
    } catch (error) {
      console.error('Failed to pause flow:', error)
      throw error
    }
  }

  // Resume a flow
  async resumeFlow(patientId: string): Promise<FlowState> {
    try {
      const flowState = await apiClient.flows.resume(patientId)
      this.activeFlows.set(patientId, flowState)
      
      this.emit('flow_resumed', {
        type: 'flow_resumed',
        patient_id: patientId,
        flow_id: flowState.id,
        data: { status: 'resumed' },
        timestamp: new Date().toISOString()
      } as FlowEvent)

      return flowState
    } catch (error) {
      console.error('Failed to resume flow:', error)
      throw error
    }
  }

  // Process patient response
  async processResponse(patientId: string, message: InboundMessage): Promise<ResponseResult> {
    try {
      const apiResult = await apiClient.flows.processResponse(
        patientId,
        message.content,
        message.metadata || {}
      ) as Partial<ResponseResult> | undefined

      const responseResult: ResponseResult = {
        response_type: (apiResult?.response_type as ResponseResult['response_type']) || ResponseType.TEXT,
        extracted_data: apiResult?.extracted_data || {},
        sentiment_score: typeof apiResult?.sentiment_score === 'number' ? apiResult.sentiment_score : 0.5,
        requires_attention: apiResult?.requires_attention ?? false,
        follow_up_actions: apiResult?.follow_up_actions || []
      }

      this.emit('response_received', {
        type: 'response_received',
        patient_id: patientId,
        flow_id: message.id,
        data: {
          content: message.content,
          sentiment: responseResult.sentiment_score,
          requires_attention: responseResult.requires_attention
        },
        timestamp: new Date().toISOString()
      } as FlowEvent)

      return responseResult
    } catch (error) {
      console.error('Failed to process response:', error)
      throw error
    }
  }

  // Validate state transition
  private canTransition(flowType: FlowType, fromState: string, toState: string, trigger: string): boolean {
    const stateMachine = this.stateMachines.get(flowType)
    if (!stateMachine) return false

    const transition = stateMachine.transitions.find(t => 
      (t.from_state === fromState || t.from_state === '*') && 
      t.to_state === toState && 
      t.trigger === trigger
    )

    return !!transition
  }

  // Get template for specific flow and day
  getMessageTemplate(flowType: FlowType, day: number): MessageTemplate | null {
    const template = this.templates.get(flowType)
    return template?.messages[day] || null
  }

  // Get all active flows
  getActiveFlows(): FlowState[] {
    return Array.from(this.activeFlows.values())
  }

  // Get flow analytics
  async getAnalytics(): Promise<Record<string, unknown> | null> {
    try {
      return await apiClient.flows.getAnalytics()
    } catch (error) {
      console.error('Failed to get flow analytics:', error)
      return null
    }
  }
}

// Singleton instance
export const flowEngine = new FlowEngine()
