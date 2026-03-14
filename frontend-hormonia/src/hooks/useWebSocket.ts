import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useAuth } from './useAuth'
import { useConfig } from '@/lib/config-initializer'
import { createLogger } from '../lib/logger'
import type { WebSocketAuthDiagnostics } from '@/types/websocket'
import type { WebSocketMessage, SystemNotification, PatientUpdate } from './types'

const logger = createLogger('useWebSocket')
const SESSION_INVALID_ERROR = 'AUTH_WEBSOCKET_SESSION_INVALID'
const SESSION_LOOKUP_FAILED_ERROR = 'AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED'

interface WebSocketHookOptions {
  url?: string
  reconnectAttempts?: number
  reconnectInterval?: number
  onMessage?: (message: WebSocketMessage) => void
  onError?: (error: Event) => void
  onOpen?: () => void
  onClose?: () => void
  autoConnect?: boolean
}

function normalizeSessionAuthValue(value?: string | null): string | null {
  if (typeof value !== 'string') {
    return null
  }

  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : null
}

function buildWebSocketUrl(requestedUrl: string, configUrl: string): string {
  const baseUrl =
    requestedUrl.startsWith('ws://') || requestedUrl.startsWith('wss://')
      ? requestedUrl
      : configUrl

  const normalizedBaseUrl = baseUrl
    .replace(/^wss:(?!\/\/)/, 'wss://')
    .replace(/^ws:(?!\/\/)/, 'ws://')

  const wsUrl = new URL(normalizedBaseUrl)
  return wsUrl.toString()
}

function normalizeIncomingMessage(raw: unknown): WebSocketMessage | null {
  if (!raw || typeof raw !== 'object') {
    return null
  }

  const record = raw as Record<string, unknown>
  const timestamp =
    typeof record['timestamp'] === 'string' ? record['timestamp'] : new Date().toISOString()
  const data =
    typeof record['data'] === 'object' && record['data'] !== null
      ? (record['data'] as Record<string, unknown>)
      : {}

  if (typeof record['type'] === 'string') {
    return {
      type: record['type'],
      data,
      timestamp,
    }
  }

  if (typeof record['event'] === 'string') {
    return {
      type: record['event'],
      data,
      timestamp,
    }
  }

  return null
}

function extractAuthDiagnostics(message: WebSocketMessage | null): WebSocketAuthDiagnostics | null {
  if (!message || message.type !== 'error') {
    return null
  }

  const payload =
    typeof message.data === 'object' && message.data !== null
      ? (message.data as Record<string, unknown>)
      : {}

  const errorCode = typeof payload['error'] === 'string' ? payload['error'] : null
  if (!errorCode) {
    return null
  }

  if (errorCode !== SESSION_INVALID_ERROR && errorCode !== SESSION_LOOKUP_FAILED_ERROR) {
    return null
  }

  const details =
    typeof payload['details'] === 'object' && payload['details'] !== null
      ? (payload['details'] as Record<string, unknown>)
      : undefined
  const connectionId =
    details && typeof details['connection_id'] === 'string'
      ? details['connection_id']
      : undefined

  return {
    error: errorCode,
    message:
      typeof payload['message'] === 'string'
        ? payload['message']
        : 'WebSocket authentication failed',
    details: {
      ...details,
      ...(connectionId ? { connection_id: connectionId } : {}),
    },
  }
}

export function useWebSocket(options: WebSocketHookOptions = {}) {
  const { config } = useConfig()
  const {
    url = config?.VITE_WS_BASE_URL || config?.VITE_WS_URL || 'ws://localhost:8000/ws/connect',
    reconnectAttempts = 5,
    reconnectInterval = 3000,
    onMessage,
    onError,
    onOpen,
    onClose,
    autoConnect = true,
  } = options

  const { user, token, sessionData } = useAuth()
  const [isConnected, setIsConnected] = useState(false)
  const [connectionState, setConnectionState] = useState<
    'connecting' | 'connected' | 'disconnected' | 'error'
  >('disconnected')
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectCountRef = useRef(0)
  const shouldReconnectRef = useRef(true)

  const connectionBaseUrl =
    config?.VITE_WS_BASE_URL || config?.VITE_WS_URL || 'ws://localhost:8000/ws/connect'

  const sessionAuthState = useMemo(
    () => normalizeSessionAuthValue(sessionData?.session_id || token),
    [sessionData?.session_id, token]
  )

  const connect = useCallback(async () => {
    if (
      wsRef.current?.readyState === WebSocket.CONNECTING ||
      wsRef.current?.readyState === WebSocket.OPEN
    ) {
      logger.debug('WebSocket already connecting or connected, skipping duplicate connection')
      return
    }

    if (!user && !sessionAuthState) {
      logger.warn('Cannot connect WebSocket: no authenticated session available')
      return
    }

    try {
      setConnectionState('connecting')
      const finalUrl = buildWebSocketUrl(url, connectionBaseUrl)
      wsRef.current = new WebSocket(finalUrl)

      wsRef.current.onopen = () => {
        logger.info('WebSocket connection established')
        setIsConnected(true)
        setConnectionState('connected')
        reconnectCountRef.current = 0
        onOpen?.()
      }

      wsRef.current.onmessage = (event) => {
        try {
          const rawMessage = JSON.parse(event.data) as unknown
          const message = normalizeIncomingMessage(rawMessage)

          if (!message) {
            throw new Error('Unsupported WebSocket message payload')
          }

          const authDiagnostics = extractAuthDiagnostics(message)
          if (authDiagnostics) {
            logger.warn('Stable websocket auth diagnostics received', {
              error: authDiagnostics.error,
              connection_id: authDiagnostics.details?.connection_id,
            })
            shouldReconnectRef.current = authDiagnostics.error !== SESSION_INVALID_ERROR
            setConnectionState('error')
          }

          setLastMessage(message)
          onMessage?.(message)
        } catch (error) {
          logger.error('Failed to parse WebSocket message:', error)
        }
      }

      wsRef.current.onclose = (event) => {
        logger.info(
          `WebSocket connection closed (code: ${event.code}, reason: ${event.reason || 'none'})`
        )
        setIsConnected(false)
        setConnectionState('disconnected')
        onClose?.()

        if (shouldReconnectRef.current && reconnectCountRef.current < reconnectAttempts) {
          reconnectCountRef.current++
          logger.info(
            `Scheduling reconnection attempt ${reconnectCountRef.current}/${reconnectAttempts} in ${reconnectInterval}ms`
          )
          reconnectTimeoutRef.current = setTimeout(() => {
            void connect()
          }, reconnectInterval)
        } else if (reconnectCountRef.current >= reconnectAttempts) {
          logger.warn(`Max reconnection attempts (${reconnectAttempts}) reached, giving up`)
        }
      }

      wsRef.current.onerror = (error) => {
        logger.error('WebSocket error:', error)
        setConnectionState('error')
        onError?.(error)
      }
    } catch (error) {
      logger.error('Failed to create WebSocket connection:', error)
      setConnectionState('error')
    }
  }, [
    connectionBaseUrl,
    onClose,
    onError,
    onMessage,
    onOpen,
    reconnectAttempts,
    reconnectInterval,
    sessionAuthState,
    url,
    user,
  ])

  const disconnect = useCallback(() => {
    logger.info('Disconnecting WebSocket (intentional)')
    shouldReconnectRef.current = false

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    if (wsRef.current) {
      wsRef.current.close(1000, 'Client disconnect')
      wsRef.current = null
    }

    setIsConnected(false)
    setConnectionState('disconnected')
  }, [])

  const sendMessage = useCallback((message: Omit<WebSocketMessage, 'timestamp'>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const fullMessage: WebSocketMessage = {
        ...message,
        timestamp: new Date().toISOString(),
      }
      wsRef.current.send(JSON.stringify(fullMessage))
      return true
    }
    logger.warn('Cannot send message: WebSocket not connected')
    return false
  }, [])

  useEffect(() => {
    if (!autoConnect) {
      return () => {
        shouldReconnectRef.current = false
        disconnect()
      }
    }

    if (user || sessionAuthState) {
      logger.debug('Session auth available, connecting WebSocket')
      shouldReconnectRef.current = true
      void connect()
    } else {
      logger.debug('No authenticated session, disconnecting WebSocket')
      disconnect()
    }

    return () => {
      logger.debug('useWebSocket cleanup: disabling reconnections and disconnecting')
      shouldReconnectRef.current = false
      disconnect()
    }
  }, [autoConnect, connect, disconnect, sessionAuthState, user])

  return {
    isConnected,
    connectionState,
    lastMessage,
    connect,
    disconnect,
    sendMessage,
  }
}

export function useSystemNotifications() {
  const [notifications, setNotifications] = useState<SystemNotification[]>([])

  const handleMessage = useCallback((message: WebSocketMessage<SystemNotification>) => {
    if (message.type === 'system_notification' && message.data) {
      setNotifications((prev) => [message.data!, ...prev.slice(0, 49)])
    }
  }, [])

  const { isConnected } = useWebSocket({
    onMessage: handleMessage as (message: WebSocketMessage) => void,
  })

  return {
    notifications,
    isConnected,
    clearNotifications: () => setNotifications([]),
  }
}

export function usePatientUpdates() {
  const [updates, setUpdates] = useState<PatientUpdate[]>([])

  const handleMessage = useCallback((message: WebSocketMessage<PatientUpdate>) => {
    if (message.type === 'patient_update' && message.data) {
      setUpdates((prev) => [message.data!, ...prev.slice(0, 99)])
    }
  }, [])

  const { isConnected } = useWebSocket({
    onMessage: handleMessage as (message: WebSocketMessage) => void,
  })

  return {
    updates,
    isConnected,
    clearUpdates: () => setUpdates([]),
  }
}
