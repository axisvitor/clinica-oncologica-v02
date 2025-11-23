import {
  FlowType,
  MessageType,
  type FlowTemplate,
  type MessageTemplate,
  type Condition
} from '../types/flow'
import { apiClient } from '../api-client'
import { createLogger } from '../logger'
import { CreateFlowTemplateRequest } from '../api-client/types'

const logger = createLogger('TemplateManager')

/**
 * Patient data interface for personalization
 */
interface PatientData {
  patient_name?: string
  [key: string]: unknown
}

export class TemplateManager {
  private templates: Map<FlowType, FlowTemplate> = new Map()
  private messageVariations: Map<string, MessageTemplate[]> = new Map()

  constructor() {
    this.initializeDefaultTemplates()
  }

  // Initialize default templates for development
  private initializeDefaultTemplates(): void {
    const initial15DaysTemplate: FlowTemplate = {
      id: 'initial_15_days_template',
      flow_type: FlowType.INITIAL_15_DAYS,
      name: 'Initial 15 Days Onboarding',
      description: 'Patient introduction and engagement building',
      humanization_level: 'high',
      metadata: {
        version: '1.0',
        created_by: 'system',
        last_updated: new Date().toISOString()
      },
      is_active: true,
      steps: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      messages: {
        1: {
          id: 'day_1_welcome',
          day: 1,
          content: 'Olá {patient_name}! 👋 Sou a Hormon[IA], sua companheira nesta jornada. Estou aqui para te apoiar e tornar tudo mais simples. Como você está se sentindo hoje?',
          message_type: MessageType.TEXT,
          personalization_hints: ['greeting_style', 'warmth_level'],
          ai_instructions: 'Crie uma mensagem de boas-vindas calorosa que use o nome do paciente e estabeleça um vínculo inicial de confiança.',
          follow_up: [
            {
              intent: 'explain_purpose',
              delay_seconds: 30,
              ai_instructions: 'Explique o propósito da assistente de forma conversacional e tranquilizadora.'
            }
          ]
        },
        2: {
          id: 'day_2_check_in',
          day: 2,
          content: 'Bom dia, {patient_name}! ☀️ Como foi sua primeira noite? Lembre-se: estou aqui sempre que precisar. Que tal me contar como está se sentindo?',
          message_type: MessageType.TEXT,
          personalization_hints: ['time_of_day', 'emotional_support'],
          ai_instructions: 'Faça um check-in empático focando no bem-estar emocional.'
        },
        3: {
          id: 'day_3_education',
          day: 3,
          content: 'Oi {patient_name}! 💙 Hoje quero compartilhar algo importante com você. Você sabia que manter uma rotina pode ajudar muito no seu tratamento?',
          message_type: MessageType.INTERACTIVE,
          interactive_elements: {
            buttons: [
              { id: 'want_tips', text: 'Quero dicas!', action: 'routine_tips' },
              { id: 'tell_more', text: 'Me conte mais', action: 'routine_info' },
              { id: 'not_now', text: 'Talvez depois', action: 'routine_later' }
            ]
          },
          personalization_hints: ['education_style', 'engagement_level']
        },
        7: {
          id: 'day_7_milestone',
          day: 7,
          content: 'Parabéns, {patient_name}! 🎉 Você completou sua primeira semana comigo. Como está se sentindo? Estou muito orgulhosa de você!',
          message_type: MessageType.TEXT,
          personalization_hints: ['celebration_style', 'achievement_recognition'],
          ai_instructions: 'Celebre o marco de uma semana de forma genuína e encorajadora.'
        },
        10: {
          id: 'day_10_support',
          day: 10,
          content: 'Olá, querida {patient_name}! 💕 Estamos chegando na metade do nosso primeiro ciclo juntas. Como posso te apoiar melhor?',
          message_type: MessageType.INTERACTIVE,
          interactive_elements: {
            quick_replies: [
              'Preciso de informações',
              'Apoio emocional',
              'Dicas práticas',
              'Só conversar'
            ]
          },
          personalization_hints: ['support_type', 'communication_preference']
        },
        15: {
          id: 'day_15_completion',
          day: 15,
          content: 'Que jornada incrível, {patient_name}! 🌟 Completamos nossos primeiros 15 dias juntas. Você está pronta para a próxima fase?',
          message_type: MessageType.TEXT,
          personalization_hints: ['completion_celebration', 'transition_preparation'],
          ai_instructions: 'Celebre a conclusão dos 15 dias e prepare para a transição para a próxima fase.'
        }
      }
    }

    this.templates.set(FlowType.INITIAL_15_DAYS, initial15DaysTemplate)
  }

  // Load templates from API
  async loadTemplates(): Promise<void> {
    try {
      const templates = await apiClient.flows.getTemplates()
      templates.forEach((template) => {
        this.templates.set(template.flow_type as FlowType, template as unknown as FlowTemplate)
      })
      logger.info('Templates loaded from API', { count: templates.length })
    } catch (error) {
      logger.error('Failed to load templates from API, using defaults', { error })
      // Fall back to default templates
    }
  }

  // Get template by flow type
  getTemplate(flowType: FlowType): FlowTemplate | null {
    return this.templates.get(flowType) || null
  }

  // Get message template for specific day
  getMessageForDay(flowType: FlowType, day: number): MessageTemplate | null {
    const template = this.templates.get(flowType)
    return template?.messages?.[day] || null
  }

  // Get message variations for A/B testing
  getMessageVariations(templateId: string): MessageTemplate[] {
    return this.messageVariations.get(templateId) || []
  }

  // Personalize message content
  personalizeMessage(template: MessageTemplate, patientData: PatientData): string {
    let content = template.content

    // Replace placeholders
    Object.entries(patientData).forEach(([key, value]) => {
      const placeholder = `{${key}}`
      content = content.replace(new RegExp(placeholder, 'g'), String(value ?? ''))
    })

    return content
  }

  // Validate template structure
  validateTemplate(template: FlowTemplate): boolean {
    if (!template.id || !template.flow_type || !template.messages) {
      return false
    }

    // Validate each message
    for (const message of Object.values(template.messages)) {
      if (!this.validateMessage(message as MessageTemplate)) {
        return false
      }
    }

    return true
  }

  // Validate message structure
  private validateMessage(message: MessageTemplate): boolean {
    return !!(
      message.id &&
      message.day &&
      message.content &&
      message.message_type
    )
  }

  // Create new template
  async createTemplate(template: FlowTemplate): Promise<FlowTemplate> {
    if (!this.validateTemplate(template)) {
      logger.warn('Template validation failed', { templateId: template.id })
      throw new Error('Invalid template structure')
    }

    try {
      logger.info('Creating template', { templateId: template.id, flowType: template.flow_type })
      const createdTemplate = await apiClient.flows.createTemplate(template as unknown as CreateFlowTemplateRequest)
      this.templates.set(template.flow_type, createdTemplate as unknown as FlowTemplate)
      logger.info('Template created successfully', { templateId: createdTemplate.id })
      return createdTemplate as unknown as FlowTemplate
    } catch (error) {
      logger.error('Failed to create template', { templateId: template.id, error })
      throw error
    }
  }

  // Update existing template
  async updateTemplate(template: FlowTemplate): Promise<FlowTemplate> {
    if (!this.validateTemplate(template)) {
      logger.warn('Template validation failed', { templateId: template.id })
      throw new Error('Invalid template structure')
    }

    try {
      logger.info('Updating template', { templateId: template.id, flowType: template.flow_type })
      const updatedTemplate = await apiClient.flows.updateTemplate(template.id, template)
      this.templates.set(template.flow_type, updatedTemplate as unknown as FlowTemplate)
      logger.info('Template updated successfully', { templateId: updatedTemplate.id })
      return updatedTemplate as unknown as FlowTemplate
    } catch (error) {
      logger.error('Failed to update template', { templateId: template.id, error })
      throw error
    }
  }

  // Delete template
  async deleteTemplate(templateId: string, flowType: FlowType): Promise<void> {
    try {
      logger.info('Deleting template', { templateId, flowType })
      await apiClient.flows.deleteTemplate(templateId)
      this.templates.delete(flowType)
      logger.info('Template deleted successfully', { templateId })
    } catch (error) {
      logger.error('Failed to delete template', { templateId, error })
      throw error
    }
  }

  // Get all templates
  getAllTemplates(): FlowTemplate[] {
    return Array.from(this.templates.values())
  }

  // Check if conditions are met
  evaluateConditions(conditions: Condition[], patientData: PatientData): boolean {
    if (!conditions || conditions.length === 0) return true

    return conditions.every((condition: Condition) => {
      const value = patientData[condition.field]

      switch (condition.operator) {
        case 'equals':
          return value === condition.value
        case 'not_equals':
          return value !== condition.value
        case 'contains':
          return String(value ?? '').includes(String(condition.value ?? ''))
        case 'greater_than':
          return Number(value ?? 0) > Number(condition.value ?? 0)
        case 'less_than':
          return Number(value ?? 0) < Number(condition.value ?? 0)
        default:
          return false
      }
    })
  }
}

// Singleton instance
export const templateManager = new TemplateManager()
