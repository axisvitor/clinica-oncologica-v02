/// <reference types="vite/client" />

import { apiClient } from './api-client'
import { getRuntimeConfigSync } from './runtime-config'
import { createLogger } from './logger'
import type { WebSocketAuthDiagnostics } from '@/types/websocket'

const logger = createLogger('WebSocket')
const SESSION_INVALID_ERROR = 'AUTH_WEBSOCKET_SESSION_INVALID'
const SESSION_LOOKUP_FAILED_ERROR = 'AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED'
export const WS_MANAGER_MESSAGE_EVENT = '__ws_message__'
export const WS_MANAGER_AUTH_ERROR_EVENT = '__ws_auth_error__'

/**
 * Automatically upgrades WebSocket protocol based on page protocol.
 */
function upgradeWebSocketProtocol(wsUrl: string): string {
  if (typeof window === 'undefined') {
    return wsUrl
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return wsUrl.replace(/^(ws|wss):/, protocol)
}

function resolveWsBaseUrl(): string | null {
  const env = import.meta.env as ImportMetaEnv & {
    VITE_WS_BASE_URL?: string
    VITE_WS_URL?: string
  }

  if (env.VITE_WS_BASE_URL) {
    return upgradeWebSocketProtocol(env.VITE_WS_BASE_URL)
  }

  if (env.VITE_WS_URL) {
    return upgradeWebSocketProtocol(env.VITE_WS_URL)
  }

  const runtime = getRuntimeConfigSync()
  if (runtime?.VITE_WS_BASE_URL) {
    return upgradeWebSocketProtocol(runtime.VITE_WS_BASE_URL)
  }

  if (runtime?.VITE_WS_URL) {
    return upgradeWebSocketProtocol(runtime.VITE_WS_URL)
  }

  if (typeof window !== 'undefined') {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    return `${proto}://${window.location.host}/ws/connect`
  }

  return null
}

const WS_BASE_URL: string | null = resolveWsBaseUrl()

if (!WS_BASE_URL && import.meta.env.MODE === 'production') {
  logger.warn('VITE_WS_URL not set; WebSocket features disabled')
}

const APP_CONFIG = {
  reconnectAttempts: 5,
  reconnectDelay: 1000,
}

export interface WebSocketMessage {
  event: string
  data: Record<string, unknown>
  timestamp?: string
  patient_id?: string
  session_id?: string
}

export type WebSocketEventHandler<T = unknown> = (data: T) => void

interface BackendMessage {
  type: string
  data: Record<string, unknown>
}

const PROTOCOL_MAP: Record<string, string> = {
  'join:patient': 'join_room',
  'leave:patient': 'leave_room',
  'subscribe:quiz': 'subscribe',
  'unsubscribe:quiz': 'unsubscribe',
  'subscribe:flow': 'subscribe',
  'unsubscribe:flow': 'unsubscribe',
  ping: 'ping',
  pong: 'pong',
}

function normalizeSessionFallback(value?: string | null): string | null {
  if (typeof value !== 'string') {
    return null
  }

  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : null
}

function isLikelyJwt(value: string): boolean {
  return value.split('.').length === 3
}

function resolveSessionFallback(sessionId?: string | null): string | null {
  return normalizeSessionFallback(sessionId) ?? normalizeSessionFallback(apiClient.getAuthToken())
}

function buildWebSocketUrl(base: string, sessionId?: string | null): string {
  const url = new URL(base)
  const sessionFallback = resolveSessionFallback(sessionId)

  if (sessionFallback && !isLikelyJwt(sessionFallback)) {
    url.searchParams.set('session_id', sessionFallback)
  } else if (sessionFallback) {
    logger.warn('Ignoring legacy websocket JWT fallback; relying on first-party session state')
  }

  return url.toString()
}

class WebSocketManager {
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private eventHandlers: Map<string, Set<WebSocketEventHandler>> = new Map()
  private roomSubscriptions: Set<string> = new Set()
  private isConnecting = false
  private shouldReconnect = true
  private currentSessionFallback: string | null = null
  private connectionPromise: Promise<void> | null = null

  async connect(sessionId?: string | null): Promise<void> {
    if (this.isConnecting && this.connectionPromise) {
      return this.connectionPromise
    }

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      return Promise.resolve()
    }

    this.currentSessionFallback = resolveSessionFallback(sessionId)
    this.isConnecting = true
    this.shouldReconnect = true

    this.connectionPromise = new Promise((resolve, reject) => {
      const base = WS_BASE_URL || resolveWsBaseUrl()
      if (!base) {
        logger.warn('WS base URL missing; skipping WebSocket connect')
        this.isConnecting = false
        this.shouldReconnect = false
        this.connectionPromise = null
        return resolve()
      }

      const wsUrl = buildWebSocketUrl(base, this.currentSessionFallback)

      try {
        this.ws = new WebSocket(wsUrl)

        this.ws.onopen = () => {
          logger.log('WebSocket connected')
          this.isConnecting = false
          this.reconnectAttempts = 0
          this.emit('connected', {})

          this.roomSubscriptions.forEach((room) => {
            const [type, id] = room.split(':')
            if (type === 'patient' && id) {
              this.joinPatientRoom(id)
            } else if (type === 'quiz' && id) {
              this.subscribeToQuizEvents(id)
            } else if (type === 'flow' && id) {
              this.subscribeToFlowEvents(id)
            }
          })

          resolve()
        }

        this.ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data) as WebSocketMessage | BackendMessage
            this.handleMessage(message)
          } catch (error) {
            logger.error('Failed to parse WebSocket message:', error)
          }
        }

        this.ws.onclose = (event) => {
          logger.log('WebSocket disconnected:', event.code, event.reason)
          this.isConnecting = false
          this.ws = null
          this.connectionPromise = null
          this.emit('disconnected', { code: event.code, reason: event.reason })

          if (this.shouldReconnect) {
            this.attemptReconnect(this.currentSessionFallback)
          }

          if (event.code !== 1000 && event.code !== 1001) {
            logger.warn('WebSocket closed unexpectedly:', event.code, event.reason)
          }
        }

        this.ws.onerror = (error) => {
          logger.error('WebSocket error:', error)
          this.isConnecting = false
          this.emit('error', { error })
          logger.warn('WebSocket connection failed, continuing without real-time features')
          reject(error instanceof Error ? error : new Error('WebSocket connection failed'))
        }
      } catch (error) {
        logger.error('Failed to create WebSocket connection:', error)
        this.isConnecting = false
        this.emit('error', { error })
        this.connectionPromise = null
        reject(error)
      }
    })

    return this.connectionPromise
  }

  private extractAuthDiagnostics(message: WebSocketMessage): WebSocketAuthDiagnostics | null {
    if (message.event !== 'system:error') {
      return null
    }

    const errorCode = typeof message.data['error'] === 'string' ? message.data['error'] : null
    if (!errorCode) {
      return null
    }

    const details =
      typeof message.data['details'] === 'object' && message.data['details'] !== null
        ? (message.data['details'] as Record<string, unknown>)
        : undefined
    const connectionId =
      details && typeof details['connection_id'] === 'string'
        ? details['connection_id']
        : undefined
    const messageText =
      typeof message.data['message'] === 'string'
        ? message.data['message']
        : 'WebSocket authentication failed'

    if (errorCode === SESSION_INVALID_ERROR || errorCode === SESSION_LOOKUP_FAILED_ERROR) {
      logger.warn('WebSocket session-auth diagnostics', {
        error: errorCode,
        connection_id: connectionId,
      })

      if (errorCode === SESSION_INVALID_ERROR) {
        this.shouldReconnect = false
      }

      return {
        error: errorCode,
        message: messageText,
        details,
      }
    }

    return null
  }

  private handleMessage(messageOrBackend: WebSocketMessage | BackendMessage) {
    let message: WebSocketMessage

    if ('type' in messageOrBackend && !('event' in messageOrBackend)) {
      const backendMsg = messageOrBackend as BackendMessage
      message = this.convertBackendToFrontend(backendMsg)
    } else {
      message = messageOrBackend as WebSocketMessage
    }

    this.emit(WS_MANAGER_MESSAGE_EVENT, message)

    const authDiagnostics = this.extractAuthDiagnostics(message)
    if (authDiagnostics) {
      this.emit(WS_MANAGER_AUTH_ERROR_EVENT, authDiagnostics)
    }

    if (message.event.startsWith('system:')) {
      this.emit(message.event, message.data)
    }

    if (message.event.startsWith('patient:')) {
      this.emit(message.event, { ...message.data, patient_id: message.patient_id })
    }

    if (message.event.startsWith('quiz:')) {
      this.emit(message.event, { ...message.data, session_id: message.session_id })
    }

    if (message.event.startsWith('flow:')) {
      this.emit(message.event, message.data)
    }

    if (message.event.startsWith('message:')) {
      this.emit(message.event, message.data)
    }

    const handlers = this.eventHandlers.get(message.event)
    if (handlers) {
      handlers.forEach((handler) => {
        try {
          handler(message.data)
        } catch (error) {
          logger.error(`Error in WebSocket event handler for ${message.event}:`, error)
        }
      })
    }
  }

  private convertBackendToFrontend(backendMsg: BackendMessage): WebSocketMessage {
    const typeToEvent: Record<string, string> = {
      connected: 'system:connected',
      disconnected: 'system:disconnected',
      authenticated: 'system:authenticated',
      ping: 'system:ping',
      pong: 'system:pong',
      error: 'system:error',
      patient_updated: 'patient:updated',
      patient_flow_changed: 'patient:flow_changed',
      patient_status_changed: 'patient:status_changed',
      flow_state_changed: 'flow:state_changed',
      flow_message_sent: 'flow:message_sent',
      flow_progression: 'flow:progression',
      quiz_started: 'quiz:started',
      quiz_response_submitted: 'quiz:response_submitted',
      quiz_completed: 'quiz:completed',
      new_message: 'message:new',
      message_status_updated: 'message:status_updated',
    }

    const data = backendMsg.data || {}

    return {
      event: typeToEvent[backendMsg.type] || backendMsg.type,
      data,
      timestamp: (data['timestamp'] as string) || new Date().toISOString(),
      patient_id: data['patient_id'] as string,
      session_id: data['session_id'] as string,
    }
  }

  private attemptReconnect(sessionId?: string | null) {
    if (this.reconnectAttempts >= APP_CONFIG.reconnectAttempts) {
      logger.log('Max reconnection attempts reached')
      this.emit('max_reconnect_attempts', {})
      this.shouldReconnect = false
      return
    }

    const delay = APP_CONFIG.reconnectDelay * Math.pow(2, this.reconnectAttempts)
    this.reconnectAttempts++

    logger.log(`Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`)

    this.reconnectTimer = setTimeout(() => {
      if (this.shouldReconnect) {
        void this.connect(sessionId)
      }
    }, delay)
  }

  on(event: string, handler: WebSocketEventHandler): () => void {
    if (!this.eventHandlers.has(event)) {
      this.eventHandlers.set(event, new Set())
    }
    this.eventHandlers.get(event)!.add(handler)

    return () => {
      const handlers = this.eventHandlers.get(event)
      if (handlers) {
        handlers.delete(handler)
        if (handlers.size === 0) {
          this.eventHandlers.delete(event)
        }
      }
    }
  }

  off(event: string, handler?: WebSocketEventHandler) {
    if (!handler) {
      this.eventHandlers.delete(event)
    } else {
      const handlers = this.eventHandlers.get(event)
      if (handlers) {
        handlers.delete(handler)
        if (handlers.size === 0) {
          this.eventHandlers.delete(event)
        }
      }
    }
  }

  private emit(event: string, data: unknown) {
    const handlers = this.eventHandlers.get(event)
    if (handlers) {
      handlers.forEach((handler) => {
        try {
          handler(data)
        } catch (error) {
          logger.error(`Error in event handler for ${event}:`, error)
        }
      })
    }
  }

  send(event: string, data: Record<string, unknown>) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const backendType = PROTOCOL_MAP[event] || event

      const backendMessage: BackendMessage = {
        type: backendType,
        data: {
          ...data,
          timestamp: new Date().toISOString(),
        },
      }

      this.ws.send(JSON.stringify(backendMessage))
      logger.log(`Sent: ${event} -> ${backendType}`, data)
    } else {
      logger.warn('WebSocket is not connected. Cannot send message:', event, data)
    }
  }

  joinPatientRoom(patientId: string) {
    const roomKey = `patient:${patientId}`
    this.roomSubscriptions.add(roomKey)
    this.send('join:patient', { patient_id: patientId })
  }

  leavePatientRoom(patientId: string) {
    const roomKey = `patient:${patientId}`
    this.roomSubscriptions.delete(roomKey)
    this.send('leave:patient', { patient_id: patientId })
  }

  subscribeToQuizEvents(sessionId: string) {
    const roomKey = `quiz:${sessionId}`
    this.roomSubscriptions.add(roomKey)
    this.send('subscribe:quiz', {
      channel: `quiz:${sessionId}`,
      session_id: sessionId,
    })
  }

  unsubscribeFromQuizEvents(sessionId: string) {
    const roomKey = `quiz:${sessionId}`
    this.roomSubscriptions.delete(roomKey)
    this.send('unsubscribe:quiz', {
      channel: `quiz:${sessionId}`,
      session_id: sessionId,
    })
  }

  subscribeToFlowEvents(flowId: string) {
    const roomKey = `flow:${flowId}`
    this.roomSubscriptions.add(roomKey)
    this.send('subscribe:flow', {
      channel: `flow:${flowId}`,
      flow_id: flowId,
    })
  }

  unsubscribeFromFlowEvents(flowId: string) {
    const roomKey = `flow:${flowId}`
    this.roomSubscriptions.delete(roomKey)
    this.send('unsubscribe:flow', {
      channel: `flow:${flowId}`,
      flow_id: flowId,
    })
  }

  disconnect() {
    this.shouldReconnect = false

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect')
      this.ws = null
    }

    this.eventHandlers.clear()
    this.roomSubscriptions.clear()
    this.reconnectAttempts = 0
    this.isConnecting = false
    this.currentSessionFallback = null
    this.connectionPromise = null
  }

  get isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN
  }

  get connectionState(): string {
    if (!this.ws) return 'disconnected'

    switch (this.ws.readyState) {
      case WebSocket.CONNECTING:
        return 'connecting'
      case WebSocket.OPEN:
        return 'connected'
      case WebSocket.CLOSING:
        return 'closing'
      case WebSocket.CLOSED:
        return 'closed'
      default:
        return 'unknown'
    }
  }

  updateToken(sessionId: string | null) {
    this.currentSessionFallback = resolveSessionFallback(sessionId)

    if (!sessionId) {
      this.shouldReconnect = false
      if (this.ws) {
        this.disconnect()
      }
      return
    }

    if (this.ws) {
      this.disconnect()
    }

    this.shouldReconnect = true
    void this.connect(sessionId)
  }
}

export const wsManager = new WebSocketManager()
