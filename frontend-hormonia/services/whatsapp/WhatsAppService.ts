// WhatsApp Service API
export interface WhatsAppInstance {
  id: string
  name: string
  status: 'connected' | 'disconnected' | 'connecting' | 'created'
  phone?: string
  qrCode?: string
  isConnected?: boolean
  createdAt?: string
  profileName?: string
  phoneNumber?: string
}

export interface WhatsAppMessage {
  id: string
  to: string
  from: string
  content: string
  type: 'text' | 'image' | 'document'
  timestamp: string
  status: 'sent' | 'delivered' | 'read' | 'failed'
}

export interface MessageRequest {
  to: string
  content: string
  type?: 'text' | 'image' | 'document'
  instanceName?: string
  text?: string
  mediaUrl?: string
  mediaCaption?: string
  filename?: string
}

export interface MessageResponse {
  id: string
  status: 'sent' | 'failed'
  message?: string
}

export class WhatsAppService {
  private baseUrl: string

  constructor(baseUrl = '/api/whatsapp') {
    this.baseUrl = baseUrl
  }

  async getInstances(): Promise<WhatsAppInstance[]> {
    const response = await fetch(`${this.baseUrl}/instances`)
    return response.json()
  }

  async createInstance(name: string): Promise<WhatsAppInstance> {
    const response = await fetch(`${this.baseUrl}/instances`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    })
    return response.json()
  }

  async sendMessage(instanceId: string, to: string, content: string): Promise<WhatsAppMessage>
  async sendMessage(request: MessageRequest): Promise<MessageResponse>
  async sendMessage(instanceIdOrRequest: string | MessageRequest, to?: string, content?: string): Promise<WhatsAppMessage | MessageResponse> {
    if (typeof instanceIdOrRequest === 'string') {
      // Legacy method signature
      const response = await fetch(`${this.baseUrl}/instances/${instanceIdOrRequest}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ to, content })
      })
      return response.json()
    } else {
      // New method signature with MessageRequest
      const response = await fetch(`${this.baseUrl}/instances/${instanceIdOrRequest.instanceName}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(instanceIdOrRequest)
      })
      const data = await response.json()
      return {
        id: data.id,
        status: data.status || 'sent',
        message: data.message
      }
    }
  }

  async getMessages(instanceId: string): Promise<WhatsAppMessage[]> {
    const response = await fetch(`${this.baseUrl}/instances/${instanceId}/messages`)
    return response.json()
  }

  async listInstances(): Promise<{ instances: WhatsAppInstance[] }> {
    const instances = await this.getInstances()
    return { instances }
  }

  async deleteInstance(instanceId: string): Promise<void> {
    await fetch(`${this.baseUrl}/instances/${instanceId}`, {
      method: 'DELETE'
    })
  }

  async connectInstance(instanceId: string): Promise<WhatsAppInstance> {
    const response = await fetch(`${this.baseUrl}/instances/${instanceId}/connect`, {
      method: 'POST'
    })
    return response.json()
  }

  async disconnectInstance(instanceId: string): Promise<void> {
    await fetch(`${this.baseUrl}/instances/${instanceId}/disconnect`, {
      method: 'POST'
    })
  }

  async restartInstance(instanceId: string): Promise<WhatsAppInstance> {
    const response = await fetch(`${this.baseUrl}/instances/${instanceId}/restart`, {
      method: 'POST'
    })
    return response.json()
  }

  async getQrCode(instanceId: string): Promise<{ qrCode: string }> {
    const response = await fetch(`${this.baseUrl}/instances/${instanceId}/qr`)
    return response.json()
  }

  async getInstanceStatus(instanceId: string): Promise<WhatsAppInstance> {
    const response = await fetch(`${this.baseUrl}/instances/${instanceId}/status`)
    return response.json()
  }

  async validatePhoneNumber(phoneNumber: string): Promise<{ isValid: boolean }> {
    const response = await fetch(`${this.baseUrl}/validate-phone`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phoneNumber })
    })
    return response.json()
  }

  async checkWhatsAppNumber(phoneNumber: string): Promise<{ exists: boolean }> {
    const response = await fetch(`${this.baseUrl}/check-whatsapp`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phoneNumber })
    })
    return response.json()
  }

  async uploadMedia(file: File): Promise<{ mediaUrl: string }> {
    const formData = new FormData()
    formData.append('file', file)
    const response = await fetch(`${this.baseUrl}/upload-media`, {
      method: 'POST',
      body: formData
    })
    return response.json()
  }

  async getQueueStats(): Promise<{ pending: number; scheduled: number; retryScheduled: number; deadLetter: number }> {
    const response = await fetch(`${this.baseUrl}/queue/stats`)
    return response.json()
  }

  async getMessageStatistics(period: string = '24h'): Promise<{ sent: number; delivered: number; failed: number; pending: number }> {
    const response = await fetch(`${this.baseUrl}/statistics/messages?period=${period}`)
    return response.json()
  }
}

export const whatsappService = new WhatsAppService()