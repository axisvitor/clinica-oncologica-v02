/// <reference types="vite/client" />

/**
 * WhatsApp Integration Service for Frontend
 * Handles all WhatsApp-related operations through the backend API
 */

import { apiClient } from '@/lib/api-client'

export interface WhatsAppMessage {
  id: string
  externalId?: string
  messageType:
    | 'text'
    | 'image'
    | 'document'
    | 'audio'
    | 'video'
    | 'sticker'
    | 'location'
    | 'contact'
  content?: string
  mediaUrl?: string
  mediaCaption?: string
  status: 'pending' | 'sent' | 'delivered' | 'read' | 'failed'
  senderId: string
  recipientId: string
  createdAt: string
  sentAt?: string
  deliveredAt?: string
  readAt?: string
  retryCount: number
  metadata?: Record<string, unknown>
}

export interface WhatsAppContact {
  id: string
  phoneNumber: string
  formattedNumber: string
  name?: string
  profilePictureUrl?: string
  isWhatsappUser: boolean
  lastSeen?: string
  createdAt: string
  updatedAt: string
}

export interface WhatsAppInstance {
  id: string
  name: string
  status: string
  isConnected: boolean
  phoneNumber?: string
  profileName?: string
  qrCode?: string
  lastActivity?: string
  createdAt: string
}

export interface MessageRequest {
  instanceName: string
  to: string
  messageType: 'text' | 'image' | 'document' | 'audio' | 'video'
  text?: string
  mediaUrl?: string
  mediaCaption?: string
  filename?: string
  templateName?: string
  templateParams?: string[]
  metadata?: Record<string, unknown>
}

export interface MessageResponse {
  id: string
  externalId?: string
  status: 'pending' | 'sent' | 'delivered' | 'read' | 'failed'
  message: string
  timestamp: string
  metadata?: Record<string, unknown>
}

export interface QueueStats {
  pending: number
  scheduled: number
  retryScheduled: number
  deadLetter: number
}

class WhatsAppService {
  private baseUrl: string
  private apiKey?: string

  constructor() {
    // Use VITE_API_BASE_URL (without /api/v2) to avoid path duplication
    // If only VITE_API_URL is available, sanitize it by removing /api/v2 suffix
    this.baseUrl =
      import.meta.env['VITE_API_BASE_URL'] ||
      import.meta.env.VITE_API_BASE_URL ||
      import.meta.env['VITE_API_URL']?.replace(/\/api\/v2$/, '') ||
      import.meta.env.VITE_API_URL?.replace(/\/api\/v2$/, '') ||
      import.meta.env.VITE_API_URL ||
      'http://localhost:8000'
    this.apiKey = import.meta.env['VITE_API_KEY']
  }

  private async makeRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`

    const defaultHeaders: Record<string, string> = {
      'Content-Type': 'application/json',
    }

    if (this.apiKey) {
      defaultHeaders['Authorization'] = `Bearer ${this.apiKey}`
    }

    const config: RequestInit = {
      ...options,
      headers: {
        ...defaultHeaders,
        ...apiClient.getSessionHeaders(),
        ...options.headers,
      },
      credentials: options.credentials ?? 'include',
    }

    const response = await fetch(url, config)

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: 'Unknown error' }))
      throw new Error(errorData.detail || errorData.message || `HTTP ${response.status}`)
    }

    return response.json()
  }

  // Instance Management
  async createInstance(instanceName: string, webhookUrl?: string): Promise<WhatsAppInstance> {
    const params = new URLSearchParams()
    params.append('instance_name', instanceName)
    if (webhookUrl) {
      params.append('webhook_url', webhookUrl)
    }

    return this.makeRequest<WhatsAppInstance>(`/api/v2/whatsapp/instances?${params.toString()}`, {
      method: 'POST',
    })
  }

  async getInstanceStatus(instanceName: string): Promise<WhatsAppInstance> {
    return this.makeRequest<WhatsAppInstance>(`/api/v2/whatsapp/instances/${instanceName}`)
  }

  async getQrCode(instanceName: string): Promise<{ qr_code: string; timestamp: string }> {
    return this.makeRequest<{ qr_code: string; timestamp: string }>(
      `/api/v2/whatsapp/instances/${instanceName}/qr`
    )
  }

  async restartInstance(instanceName: string): Promise<{ status: string; timestamp: string }> {
    return this.makeRequest<{ status: string; timestamp: string }>(
      `/api/v2/whatsapp/instances/${instanceName}/restart`,
      { method: 'POST' }
    )
  }

  async deleteInstance(instanceName: string): Promise<{ status: string; timestamp: string }> {
    return this.makeRequest<{ status: string; timestamp: string }>(
      `/api/v2/whatsapp/instances/${instanceName}`,
      { method: 'DELETE' }
    )
  }

  async listInstances(): Promise<{
    instances: WhatsAppInstance[]
    total: number
    timestamp: string
  }> {
    return this.makeRequest<{
      instances: WhatsAppInstance[]
      total: number
      timestamp: string
    }>('/api/v2/whatsapp/instances')
  }

  // Message Management
  async sendMessage(request: MessageRequest): Promise<MessageResponse> {
    return this.makeRequest<MessageResponse>('/api/v2/whatsapp/messages', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  async sendTextMessage(
    instanceName: string,
    to: string,
    text: string,
    metadata?: Record<string, unknown>
  ): Promise<MessageResponse> {
    return this.sendMessage({
      instanceName,
      to,
      messageType: 'text',
      text,
      metadata: metadata || {},
    })
  }

  async sendImageMessage(
    instanceName: string,
    to: string,
    imageUrl: string,
    caption?: string,
    metadata?: Record<string, unknown>
  ): Promise<MessageResponse> {
    return this.sendMessage({
      instanceName,
      to,
      messageType: 'image',
      mediaUrl: imageUrl,
      mediaCaption: caption || '',
      metadata: metadata || {},
    })
  }

  async sendDocumentMessage(
    instanceName: string,
    to: string,
    documentUrl: string,
    filename: string,
    caption?: string,
    metadata?: Record<string, unknown>
  ): Promise<MessageResponse> {
    return this.sendMessage({
      instanceName,
      to,
      messageType: 'document',
      mediaUrl: documentUrl,
      filename,
      mediaCaption: caption || '',
      metadata: metadata || {},
    })
  }

  async getMessageHistory(
    instanceName: string,
    chatId: string,
    limit = 50,
    offset = 0
  ): Promise<{
    messages: WhatsAppMessage[]
    total: number
    limit: number
    offset: number
  }> {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    })

    return this.makeRequest<{
      messages: WhatsAppMessage[]
      total: number
      limit: number
      offset: number
    }>(`/api/v2/whatsapp/messages/${instanceName}/${chatId}?${params.toString()}`)
  }

  async getMessageStatistics(
    instanceName: string,
    startDate?: Date,
    endDate?: Date
  ): Promise<{
    instanceName: string
    period: { startDate?: string; endDate?: string }
    statistics: Record<string, number>
    generatedAt: string
  }> {
    const params = new URLSearchParams()
    if (startDate) {
      params.append('start_date', startDate.toISOString())
    }
    if (endDate) {
      params.append('end_date', endDate.toISOString())
    }

    return this.makeRequest<{
      instanceName: string
      period: { startDate?: string; endDate?: string }
      statistics: Record<string, number>
      generatedAt: string
    }>(`/api/v2/whatsapp/messages/${instanceName}/statistics?${params.toString()}`)
  }

  // Contact Management
  async syncContacts(instanceName: string): Promise<{
    status: string
    instanceName: string
    timestamp: string
  }> {
    return this.makeRequest<{
      status: string
      instanceName: string
      timestamp: string
    }>(`/api/v2/whatsapp/contacts/${instanceName}/sync`, {
      method: 'POST',
    })
  }

  async getContacts(
    instanceName: string,
    limit = 100,
    offset = 0,
    search?: string
  ): Promise<{
    contacts: WhatsAppContact[]
    total: number
    limit: number
    offset: number
  }> {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    })

    if (search) {
      params.append('search', search)
    }

    return this.makeRequest<{
      contacts: WhatsAppContact[]
      total: number
      limit: number
      offset: number
    }>(`/api/v2/whatsapp/contacts/${instanceName}?${params.toString()}`)
  }

  async checkWhatsAppNumber(
    instanceName: string,
    phoneNumber: string
  ): Promise<{
    phoneNumber: string
    formattedNumber: string
    isWhatsappUser: boolean
    checkedAt: string
  }> {
    const params = new URLSearchParams({
      phone_number: phoneNumber,
    })

    return this.makeRequest<{
      phoneNumber: string
      formattedNumber: string
      isWhatsappUser: boolean
      checkedAt: string
    }>(`/api/v2/whatsapp/contacts/${instanceName}/check?${params.toString()}`, {
      method: 'POST',
    })
  }

  // Queue Management
  async getQueueStats(): Promise<{
    queueStatistics: QueueStats
    timestamp: string
  }> {
    return this.makeRequest<{
      queueStatistics: QueueStats
      timestamp: string
    }>('/api/v2/whatsapp/queue/stats')
  }

  async startQueueProcessing(): Promise<{
    status: string
    timestamp: string
  }> {
    return this.makeRequest<{
      status: string
      timestamp: string
    }>('/api/v2/whatsapp/queue/process', {
      method: 'POST',
    })
  }

  // Health Check
  async healthCheck(): Promise<{
    status: string
    service: string
    timestamp: string
    version: string
  }> {
    return this.makeRequest<{
      status: string
      service: string
      timestamp: string
      version: string
    }>('/api/v2/whatsapp/health')
  }

  // Utility Methods
  formatPhoneNumber(phoneNumber: string): string {
    // Remove all non-digit characters
    const clean = phoneNumber.replace(/\D/g, '')

    // Add country code if missing (assuming Brazil +55)
    if (clean.length === 11 && clean.startsWith('0')) {
      return '55' + clean.slice(1)
    } else if (clean.length === 10 || clean.length === 11) {
      return '55' + clean
    }

    return clean
  }

  validatePhoneNumber(phoneNumber: string): {
    isValid: boolean
    formatted: string
    error?: string
  } {
    const formatted = this.formatPhoneNumber(phoneNumber)

    if (formatted.length < 12 || formatted.length > 15) {
      return {
        isValid: false,
        formatted,
        error: 'Invalid phone number length',
      }
    }

    return {
      isValid: true,
      formatted,
    }
  }

  // File Upload Utility
  async uploadMedia(file: File): Promise<{ url: string; type: string; size: number }> {
    const formData = new FormData()
    formData.append('file', file)

    const headers: Record<string, string> = {
      ...apiClient.getSessionHeaders(),
    }

    if (this.apiKey) {
      headers['Authorization'] = `Bearer ${this.apiKey}`
    }

    const response = await fetch(`${this.baseUrl}/api/v2/upload/media`, {
      method: 'POST',
      body: formData,
      headers,
      credentials: 'include',
    })

    if (!response.ok) {
      throw new Error('Failed to upload media')
    }

    return response.json()
  }
}

// Export singleton instance
export const whatsAppService = new WhatsAppService()
export default whatsAppService
