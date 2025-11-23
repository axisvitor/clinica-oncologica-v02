import {
  FlowType,
  type FlowState,
  type MessageTemplate,
  type FlowTemplate,
  type InboundMessage,
  type ResponseResult,
  type FlowEvent,
  type FlowStateMachine
} from '../types/flow'
import type {
  FlowExecutionContext,
  FlowExecutionStep,
  FlowExecutionResult,
  ConditionEvaluationResult
} from './types'
import { apiClient } from '../api-client'
import { createLogger } from '../logger'
import { smartMapFlowResponse } from './mappers/flowResponseMapper'
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
  private initializeStateMachines(): void {
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
      templates.forEach((template) => {
        this.templates.set(template.flow_type as FlowType, template as unknown as FlowTemplate)
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
        const state = flowState as unknown as FlowState
        this.activeFlows.set(patientId, state)
        logger.debug('Flow state retrieved', { patientId, flowType: state.flow_type })
        return state
      }
      return null
    } catch (error) {
      logger.error('Failed to get flow state', { patientId, error })
      return null
    }
  }

  // Start a new flow for a patient
  async startFlow(patientId: string, flowType: FlowType): Promise<FlowState> {
    try {
      logger.info('Starting flow', { patientId, flowType })
      const response = await apiClient.flows.start(patientId, flowType)

      // Map backend response (nested) to frontend FlowState (flat)
      const flowState = smartMapFlowResponse(response)
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
      const response = await apiClient.flows.advance(patientId, forceDay)

      // Map backend response (nested) to frontend FlowState (flat)
      const flowState = smartMapFlowResponse(response)
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
      const flowState = await apiClient.flows.pause(patientId) as unknown as FlowState
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
      const flowState = await apiClient.flows.resume(patientId) as unknown as FlowState
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

      // Extract message content and metadata separately
      // Backend expects response_text as a string, not the full message object
      const result = await apiClient.flows.processResponse(
        patientId,
        message.content,  // Pass content as string
        message.metadata  // Pass metadata separately
      )

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
    if (!template || !template.messages) return null
    return template.messages[day] || null
  }

  // Get all active flows
  getActiveFlows(): FlowState[] {
    return Array.from(this.activeFlows.values())
  }

  // Get flow analytics
  async getAnalytics(): Promise<Record<string, unknown> | null> {
    try {
      const analytics = await apiClient.flows.getAnalytics()
      logger.debug('Flow analytics retrieved', { analytics })
      return analytics as unknown as Record<string, unknown>
    } catch (error) {
      logger.error('Failed to get flow analytics', { error })
      return null
    }
  }

  // Process node execution (internal helper)
  private async processNode(
    nodeId: string,
    context: FlowExecutionContext
  ): Promise<FlowExecutionResult> {
    const step: FlowExecutionStep = {
      node_id: nodeId,
      executed_at: new Date().toISOString(),
      result: 'success'
    }

    try {
      // Node processing logic would go here
      context.history.push(step)

      return {
        success: true
      }
    } catch (error) {
      step.result = 'failure'
      step.error = error instanceof Error ? error.message : 'Unknown error'
      context.history.push(step)

      return {
        success: false,
        error: step.error
      }
    }
  }

  // Evaluate condition (internal helper)
  private evaluateCondition(
    field: string,
    operator: string,
    value: unknown,
    contextData: Record<string, unknown>
  ): ConditionEvaluationResult {
    const actualValue = contextData[field]

    let passed = false
    switch (operator) {
      case 'equals':
        passed = actualValue === value
        break
      case 'not_equals':
        passed = actualValue !== value
        break
      case 'contains':
        passed = String(actualValue).includes(String(value))
        break
      case 'greater_than':
        passed = Number(actualValue) > Number(value)
        break
      case 'less_than':
        passed = Number(actualValue) < Number(value)
        break
      default:
        passed = false
    }

    return {
      passed,
      reason: passed ? 'Condition met' : 'Condition not met'
    }
  }
}

// Singleton instance
export const flowEngine = new FlowEngine()
