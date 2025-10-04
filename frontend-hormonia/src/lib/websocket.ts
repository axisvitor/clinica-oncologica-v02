// WebSocket configuration resolution (lazy, non-fatal)
import { getRuntimeConfigSync } from './runtime-config'
import { createLogger } from './logger'

const logger = createLogger('WebSocket')

function resolveWsBaseUrl(): string | null {
  const envUrl = (import.meta.env as any).VITE_WS_BASE_URL as string | undefined
  if (envUrl && envUrl.length) return envUrl

  const runtime = getRuntimeConfigSync()
  if (runtime?.VITE_WS_BASE_URL) return runtime.VITE_WS_BASE_URL

  // Fallback to current host proxy (/ws/connect) if available
  if (typeof window !== 'undefined') {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    return `${proto}://${window.location.host}/ws/connect`
  }
  return null
}

let WS_BASE_URL: string | null = resolveWsBaseUrl()

if (!WS_BASE_URL && import.meta.env.MODE === 'production') {
  // Do not throw — disable WS gracefully and allow UI to render
  logger.warn('VITE_WS_BASE_URL not set; WebSocket features disabled')
}

const APP_CONFIG = {
  reconnectAttempts: 5,
  reconnectDelay: 1000
}

export interface WebSocketMessage {
  event: string
  data: any
  timestamp?: string
  patient_id?: string
  session_id?: string
}

export type WebSocketEventHandler = (data: any) => void

// Backend protocol structures
interface BackendMessage {
  type: string
  data: Record<string, any>
}

// Protocol mapping: frontend events -> backend types
const PROTOCOL_MAP: Record<string, string> = {
  'join:patient': 'join_room',
  'leave:patient': 'leave_room',
  'subscribe:quiz': 'subscribe',
  'unsubscribe:quiz': 'unsubscribe',
  'subscribe:flow': 'subscribe',
  'unsubscribe:flow': 'unsubscribe',
  'ping': 'ping',
  'pong': 'pong'
}

class WebSocketManager {
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private eventHandlers: Map<string, Set<WebSocketEventHandler>> = new Map()
  private roomSubscriptions: Set<string> = new Set()
  private isConnecting = false
  private shouldReconnect = true
  private currentToken: string | null = null
  private connectionPromise: Promise<void> | null = null

  async connect(token: string): Promise<void> {
    if (this.isConnecting && this.connectionPromise) {
      return this.connectionPromise
    }

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      return Promise.resolve()
    }

    this.currentToken = token
    this.isConnecting = true

    this.connectionPromise = new Promise((resolve, reject) => {
      const base = WS_BASE_URL || resolveWsBaseUrl()
      if (!base) {
        logger.warn('WS base URL missing; skipping WebSocket connect')
        this.isConnecting = false
        this.shouldReconnect = false
        return resolve()
      }

      const wsUrl = `${base}?token=${token}`

      try {
        this.ws = new WebSocket(wsUrl)

        this.ws.onopen = () => {
          logger.log('WebSocket connected')
          this.isConnecting = false
          this.reconnectAttempts = 0
          this.emit('connected', {})

          // Rejoin rooms after reconnection
          this.roomSubscriptions.forEach(room => {
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
            const message: WebSocketMessage = JSON.parse(event.data)
            this.handleMessage(message)
          } catch (error) {
            logger.error('Failed to parse WebSocket message:', error)
          }
        }

        this.ws.onclose = (event) => {
          logger.log('WebSocket disconnected:', event.code, event.reason)
          this.isConnecting = false
          this.ws = null
          this.emit('disconnected', { code: event.code, reason: event.reason })

          if (this.shouldReconnect && this.currentToken) {
            this.attemptReconnect(this.currentToken)
          }

          if (event.code !== 1000) {
            reject(new Error(`WebSocket closed: ${event.reason || 'Unknown reason'}`))
          }
        }

        this.ws.onerror = (error) => {
          logger.error('WebSocket error:', error)
          this.isConnecting = false
          this.emit('error', { error })
          reject(error)
        }
      } catch (error) {
        logger.error('Failed to create WebSocket connection:', error)
        this.isConnecting = false
        this.emit('error', { error })
        reject(error)
      }
    })

    return this.connectionPromise
  }

  private handleMessage(messageOrBackend: WebSocketMessage | BackendMessage) {
    let message: WebSocketMessage

    // Convert backend protocol to frontend format for backward compatibility
    if ('type' in messageOrBackend && !('event' in messageOrBackend)) {
      const backendMsg = messageOrBackend as BackendMessage
      message = this.convertBackendToFrontend(backendMsg)
    } else {
      message = messageOrBackend as WebSocketMessage
    }

    // Handle system messages
    if (message.event.startsWith('system:')) {
      this.emit(message.event, message.data)
    }

    // Handle patient room events
    if (message.event.startsWith('patient:')) {
      this.emit(message.event, { ...message.data, patient_id: message.patient_id })
    }

    // Handle quiz events with session_id
    if (message.event.startsWith('quiz:')) {
      this.emit(message.event, { ...message.data, session_id: message.session_id })
    }

    // Handle flow events
    if (message.event.startsWith('flow:')) {
      this.emit(message.event, message.data)
    }

    // Handle message events
    if (message.event.startsWith('message:')) {
      this.emit(message.event, message.data)
    }

    // Handle generic events
    const handlers = this.eventHandlers.get(message.event)
    if (handlers) {
      handlers.forEach(handler => {
        try {
          handler(message.data)
        } catch (error) {
          logger.error(`Error in WebSocket event handler for ${message.event}:`, error)
        }
      })
    }
  }

  /**
   * Convert backend protocol message to frontend format
   */
  private convertBackendToFrontend(backendMsg: BackendMessage): WebSocketMessage {
    const typeToEvent: Record<string, string> = {
      'connected': 'system:connected',
      'disconnected': 'system:disconnected',
      'authenticated': 'system:authenticated',
      'ping': 'system:ping',
      'pong': 'system:pong',
      'error': 'system:error',
      'patient_updated': 'patient:updated',
      'patient_flow_changed': 'patient:flow_changed',
      'patient_status_changed': 'patient:status_changed',
      'flow_state_changed': 'flow:state_changed',
      'flow_message_sent': 'flow:message_sent',
      'flow_progression': 'flow:progression',
      'quiz_started': 'quiz:started',
      'quiz_response_submitted': 'quiz:response_submitted',
      'quiz_completed': 'quiz:completed',
      'new_message': 'message:new',
      'message_status_updated': 'message:status_updated'
    }

    return {
      event: typeToEvent[backendMsg.type] || backendMsg.type,
      data: backendMsg.data,
      timestamp: backendMsg.data['timestamp'] as string || new Date().toISOString(),
      patient_id: backendMsg.data['patient_id'] as string,
      session_id: backendMsg.data['session_id'] as string
    }
  }

  private attemptReconnect(token: string) {
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
        this.connect(token)
      }
    }, delay)
  }

  on(event: string, handler: WebSocketEventHandler): () => void {
    if (!this.eventHandlers.has(event)) {
      this.eventHandlers.set(event, new Set())
    }
    this.eventHandlers.get(event)!.add(handler)

    // Return unsubscribe function
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

  private emit(event: string, data: any) {
    const handlers = this.eventHandlers.get(event)
    if (handlers) {
      handlers.forEach(handler => {
        try {
          handler(data)
        } catch (error) {
          logger.error(`Error in event handler for ${event}:`, error)
        }
      })
    }
  }

  /**
   * Send message using backend protocol
   * Converts frontend event format to backend { type, data } format
   */
  send(event: string, data: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      // Map frontend event to backend type
      const backendType = PROTOCOL_MAP[event] || event

      // Create backend protocol message
      const backendMessage: BackendMessage = {
        type: backendType,
        data: {
          ...data,
          timestamp: new Date().toISOString()
        }
      }

      this.ws.send(JSON.stringify(backendMessage))

      logger.log(`Sent: ${event} -> ${backendType}`, data)
    } else {
      logger.warn('WebSocket is not connected. Cannot send message:', event, data)
    }
  }

  // Room management methods
  /**
   * Join patient room for real-time updates
   * Uses backend join_room message type
   */
  joinPatientRoom(patientId: string) {
    const roomKey = `patient:${patientId}`
    this.roomSubscriptions.add(roomKey)
    // Backend expects 'join:patient' -> 'join_room' with patient_id
    this.send('join:patient', { patient_id: patientId })
  }

  /**
   * Leave patient room
   * Uses backend leave_room message type
   */
  leavePatientRoom(patientId: string) {
    const roomKey = `patient:${patientId}`
    this.roomSubscriptions.delete(roomKey)
    // Backend expects 'leave:patient' -> 'leave_room' with patient_id
    this.send('leave:patient', { patient_id: patientId })
  }

  /**
   * Subscribe to quiz events using enhanced endpoint pattern
   * Uses backend subscribe message type with channel
   */
  subscribeToQuizEvents(sessionId: string) {
    const roomKey = `quiz:${sessionId}`
    this.roomSubscriptions.add(roomKey)
    // Enhanced endpoint uses 'subscribe' with channel parameter
    this.send('subscribe:quiz', {
      channel: `quiz:${sessionId}`,
      session_id: sessionId
    })
  }

  /**
   * Unsubscribe from quiz events
   */
  unsubscribeFromQuizEvents(sessionId: string) {
    const roomKey = `quiz:${sessionId}`
    this.roomSubscriptions.delete(roomKey)
    // Enhanced endpoint uses 'unsubscribe' with channel parameter
    this.send('unsubscribe:quiz', {
      channel: `quiz:${sessionId}`,
      session_id: sessionId
    })
  }

  /**
   * Subscribe to flow events using enhanced endpoint pattern
   */
  subscribeToFlowEvents(flowId: string) {
    const roomKey = `flow:${flowId}`
    this.roomSubscriptions.add(roomKey)
    // Enhanced endpoint uses 'subscribe' with channel parameter
    this.send('subscribe:flow', {
      channel: `flow:${flowId}`,
      flow_id: flowId
    })
  }

  /**
   * Unsubscribe from flow events
   */
  unsubscribeFromFlowEvents(flowId: string) {
    const roomKey = `flow:${flowId}`
    this.roomSubscriptions.delete(roomKey)
    // Enhanced endpoint uses 'unsubscribe' with channel parameter
    this.send('unsubscribe:flow', {
      channel: `flow:${flowId}`,
      flow_id: flowId
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
    this.currentToken = null
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

  updateToken(token: string | null) {
    this.currentToken = token

    if (this.ws) {
      // Reconnect with new token
      this.disconnect()
      if (token) {
        this.shouldReconnect = true
        this.connect(token)
      }
    }
  }
}

export const wsManager = new WebSocketManager()