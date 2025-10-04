// WebSocket configuration resolution (lazy, non-fatal)
import { getRuntimeConfigSync } from './runtime-config'

function resolveWsBaseUrl(): string | null {
  const envUrl = (import.meta.env as any).VITE_WS_BASE_URL as string | undefined
  if (envUrl && envUrl.length) return envUrl

  const runtime = getRuntimeConfigSync()
  if (runtime?.VITE_WS_BASE_URL) return runtime.VITE_WS_BASE_URL

  // Fallback to current host proxy (/ws) if available
  if (typeof window !== 'undefined') {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    return `${proto}://${window.location.host}/ws`
  }
  return null
}

let WS_BASE_URL: string | null = resolveWsBaseUrl()

if (!WS_BASE_URL && import.meta.env.MODE === 'production') {
  // Do not throw — disable WS gracefully and allow UI to render
  console.warn('[WebSocket] VITE_WS_BASE_URL not set; WebSocket features disabled')
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
        if (import.meta.env.DEV) {
          console.warn('WS base URL missing; skipping WebSocket connect')
        }
        this.isConnecting = false
        this.shouldReconnect = false
        return resolve()
      }

      const wsUrl = `${base}?token=${token}`

      try {
        this.ws = new WebSocket(wsUrl)

        this.ws.onopen = () => {
          if (import.meta.env.DEV) {
            console.log('WebSocket connected')
          }
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
            console.error('Failed to parse WebSocket message:', error)
          }
        }

        this.ws.onclose = (event) => {
          if (import.meta.env.DEV) {
            console.log('WebSocket disconnected:', event.code, event.reason)
          }
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
          console.error('WebSocket error:', error)
          this.isConnecting = false
          this.emit('error', { error })
          reject(error)
        }
      } catch (error) {
        console.error('Failed to create WebSocket connection:', error)
        this.isConnecting = false
        this.emit('error', { error })
        reject(error)
      }
    })

    return this.connectionPromise
  }

  private handleMessage(message: WebSocketMessage) {
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
          console.error(`Error in WebSocket event handler for ${message.event}:`, error)
        }
      })
    }
  }

  private attemptReconnect(token: string) {
    if (this.reconnectAttempts >= APP_CONFIG.reconnectAttempts) {
      if (import.meta.env.DEV) {
        console.log('Max reconnection attempts reached')
      }
      this.emit('max_reconnect_attempts', {})
      this.shouldReconnect = false
      return
    }

    const delay = APP_CONFIG.reconnectDelay * Math.pow(2, this.reconnectAttempts)
    this.reconnectAttempts++

    if (import.meta.env.DEV) {
      console.log(`Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`)
    }

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
          console.error(`Error in event handler for ${event}:`, error)
        }
      })
    }
  }

  send(event: string, data: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const message: WebSocketMessage = {
        event,
        data,
        timestamp: new Date().toISOString()
      }
      this.ws.send(JSON.stringify(message))
    } else {
      if (import.meta.env.DEV) {
        console.warn('WebSocket is not connected. Cannot send message:', event, data)
      }
    }
  }

  // Room management methods
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
    this.send('subscribe:quiz', { session_id: sessionId })
  }

  unsubscribeFromQuizEvents(sessionId: string) {
    const roomKey = `quiz:${sessionId}`
    this.roomSubscriptions.delete(roomKey)
    this.send('unsubscribe:quiz', { session_id: sessionId })
  }

  subscribeToFlowEvents(flowId: string) {
    const roomKey = `flow:${flowId}`
    this.roomSubscriptions.add(roomKey)
    this.send('subscribe:flow', { flow_id: flowId })
  }

  unsubscribeFromFlowEvents(flowId: string) {
    const roomKey = `flow:${flowId}`
    this.roomSubscriptions.delete(roomKey)
    this.send('unsubscribe:flow', { flow_id: flowId })
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