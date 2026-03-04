// Barrel exports for whatsapp feature
export { WhatsAppDashboard } from './WhatsAppDashboard'
export { WhatsAppInstanceManager } from './WhatsAppInstanceManager'
export { WhatsAppMessageSender } from './WhatsAppMessageSender'
export { WhatsAppIntegrationHub } from './WhatsAppIntegrationHub'

// Re-export types
export type { WhatsAppInstance, QueueStats } from './WhatsAppDashboard'

export type { MessageRequest, MessageResponse } from '../../services/whatsapp/WhatsAppService'
