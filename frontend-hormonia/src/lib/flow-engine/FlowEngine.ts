import {
  FlowType,
  FlowStatus,
  type FlowState,
  type MessageTemplate,
  type FlowTemplate,
  type InboundMessage,
  type ResponseResult,
  type FlowEvent,
  type FlowTransition,
  type FlowStateMachine
} from '../types/flow'
import { apiClient } from '../api-client'
import { createLogger } from '../logger'
import EventEmitter from 'eventemitter3'

const logger = createLogger('FlowEngine')

export class FlowEngine extends EventEmitter {
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
      const templates = await apiClient.flows.getTemplates()
      templates.forEach(template => {
        this.templates.set(template.flow_type, template)
      })
      logger.info('Flow templates loaded', { count: templates.length })
    } catch (error) {
      logger.error('Failed to load flow templates', { error })
    }
  }

  // Get current flow state for a patient
  async getFlowState(patientId: string): Promise<FlowState | null> {
    try {
      const flowState = await apiClient.flows.getState(patientId)
      if (flowState) {
        this.activeFlows.set(patientId, flowState)
        logger.debug('Flow state retrieved', { patientId, flowType: flowState.flow_type })
      }
      return flowState
    } catch (error) {
      logger.error('Failed to get flow state', { patientId, error })
      return null
    }
  }

  // Start a new flow for a patient
  async startFlow(patientId: string, flowType: FlowType): Promise<FlowState> {
    try {
      logger.info('Starting flow', { patientId, flowType })
      const flowState = await apiClient.flows.start(patientId, flowType)
      this.activeFlows.set(patientId, flowState)

      this.emit('flow_started', {
        type: 'flow_started',
        patient_id: patientId,
        flow_id: flowState.id,
        data: { flow_type: flowType },
        timestamp: new Date().toISOString()
      } as FlowEvent)

      logger.info('Flow started successfully', { patientId, flowId: flowState.id })
      return flowState
    } catch (error) {
      logger.error('Failed to start flow', { patientId, flowType, error })
      throw error
    }
  }

  // Advance flow to next state
  async advanceFlow(patientId: string, forceDay?: number): Promise<FlowState> {
    try {
      logger.info('Advancing flow', { patientId, forceDay })
      const flowState = await apiClient.flows.advance(patientId, forceDay)
      this.activeFlows.set(patientId, flowState)

      this.emit('flow_advanced', {
        type: 'message_sent',
        patient_id: patientId,
        flow_id: flowState.id,
        data: { current_day: flowState.current_day },
        timestamp: new Date().toISOString()
      } as FlowEvent)

      logger.info('Flow advanced successfully', { patientId, currentDay: flowState.current_day })
      return flowState
    } catch (error) {
      logger.error('Failed to advance flow', { patientId, forceDay, error })
      throw error
    }
  }

  // Pause a flow
  async pauseFlow(patientId: string): Promise<FlowState> {
    try {
      logger.info('Pausing flow', { patientId })
      const flowState = await apiClient.flows.pause(patientId)
      this.activeFlows.set(patientId, flowState)

      this.emit('flow_paused', {
        type: 'flow_paused',
        patient_id: patientId,
        flow_id: flowState.id,
        timestamp: new Date().toISOString()
      } as FlowEvent)

      logger.info('Flow paused successfully', { patientId, flowId: flowState.id })
      return flowState
    } catch (error) {
      logger.error('Failed to pause flow', { patientId, error })
      throw error
    }
  }

  // Resume a flow
  async resumeFlow(patientId: string): Promise<FlowState> {
    try {
      logger.info('Resuming flow', { patientId })
      const flowState = await apiClient.flows.resume(patientId)
      this.activeFlows.set(patientId, flowState)

      this.emit('flow_resumed', {
        type: 'flow_resumed',
        patient_id: patientId,
        flow_id: flowState.id,
        timestamp: new Date().toISOString()
      } as FlowEvent)

      logger.info('Flow resumed successfully', { patientId, flowId: flowState.id })
      return flowState
    } catch (error) {
      logger.error('Failed to resume flow', { patientId, error })
      throw error
    }
  }

  // Process patient response
  async processResponse(patientId: string, message: InboundMessage): Promise<ResponseResult> {
    try {
      logger.info('Processing patient response', { patientId, messageId: message.id })
      // @ts-expect-error TODO: fix message type
      const result = await apiClient.flows.processResponse(patientId, message)

      this.emit('response_received', {
        type: 'response_received',
        patient_id: patientId,
        flow_id: message.id,
        data: {
          content: message.content,
          sentiment: result.sentiment_score,
          requires_attention: result.requires_attention
        },
        timestamp: new Date().toISOString()
      } as FlowEvent)

      logger.info('Response processed successfully', {
        patientId,
        sentiment: result.sentiment_score,
        requiresAttention: result.requires_attention
      })
      return result
    } catch (error) {
      logger.error('Failed to process response', { patientId, error })
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
  async getAnalytics(): Promise<any> {
    try {
      const analytics = await apiClient.flows.getAnalytics()
      logger.debug('Flow analytics retrieved', { analytics })
      return analytics
    } catch (error) {
      logger.error('Failed to get flow analytics', { error })
      return null
    }
  }
}

// Singleton instance
export const flowEngine = new FlowEngine()
