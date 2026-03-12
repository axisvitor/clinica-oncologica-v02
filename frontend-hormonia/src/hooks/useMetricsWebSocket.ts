import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { useAuth } from '@/app/providers/AuthContext'
import { apiClient } from '@/lib/api-client'
import { createLogger } from '../lib/logger'
import type { WebSocketAuthDiagnostics } from '@/types/websocket'
import type { MetricsWebSocketData } from './types'

const logger = createLogger('metrics:websocket')
const SESSION_INVALID_ERROR = 'AUTH_WEBSOCKET_SESSION_INVALID'
const SESSION_LOOKUP_FAILED_ERROR = 'AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED'

interface UseMetricsWebSocketOptions {
  onMessage?: (data: MetricsWebSocketData) => void
  onError?: (error: Event) => void
  onConnect?: () => void
  onDisconnect?: () => void
  reconnectInterval?: number
  maxReconnectAttempts?: number
  heartbeatInterval?: number
}

interface UseMetricsWebSocketReturn {
  isConnected: boolean
  isConnecting: boolean
  error: string | null
  lastMessage: MetricsWebSocketData | null
  reconnectAttempts: number
  send: (data: MetricsWebSocketData) => void
  connect: () => void
  disconnect: () => void
}

function getWebSocketBaseUrl(): string {
  if (import.meta.env.VITE_WS_BASE_URL) {
    return import.meta.env.VITE_WS_BASE_URL
  }

  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL.replace('/ws', '')
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return `${protocol}//${host}`
}

function normalizeSessionQueryFallback(value?: string | null): string | null {
  if (typeof value !== 'string') {
    return null
  }

  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : null
}

function isLikelyJwt(value: string): boolean {
  return value.split('.').length === 3
}

function buildMetricsWebSocketUrl(baseUrl: string, sessionId: string | null): string {
  const url = new URL(`${baseUrl}/api/v2/metrics/live`)
  if (sessionId && !isLikelyJwt(sessionId)) {
    url.searchParams.set('session_id', sessionId)
  }
  return url.toString()
}

function extractAuthDiagnostics(data: unknown): WebSocketAuthDiagnostics | null {
  if (!data || typeof data !== 'object') {
    return null
  }

  const record = data as Record<string, unknown>
  const errorCode = typeof record['error'] === 'string' ? record['error'] : null
  if (!errorCode) {
    return null
  }

  if (errorCode !== SESSION_INVALID_ERROR && errorCode !== SESSION_LOOKUP_FAILED_ERROR) {
    return null
  }

  const details =
    typeof record['details'] === 'object' && record['details'] !== null
      ? (record['details'] as Record<string, unknown>)
      : undefined

  return {
    error: errorCode,
    message:
      typeof record['message'] === 'string' ? record['message'] : 'WebSocket authentication failed',
    details,
  }
}

export function useMetricsWebSocket({
  onMessage,
  onError,
  onConnect,
  onDisconnect,
  reconnectInterval = 5000,
  maxReconnectAttempts = 10,
  heartbeatInterval = 30000,
}: UseMetricsWebSocketOptions = {}): UseMetricsWebSocketReturn {
  const { user, session } = useAuth()

  const [isConnected, setIsConnected] = useState(false)
  const [isConnecting, setIsConnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastMessage, setLastMessage] = useState<MetricsWebSocketData | null>(null)
  const [reconnectAttempts, setReconnectAttempts] = useState(0)

  const ws = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<NodeJS.Timeout | null>(null)
  const heartbeatTimer = useRef<NodeJS.Timeout | null>(null)
  const isManualDisconnect = useRef(false)
  const connectRef = useRef<() => void>(() => undefined)

  const sessionQueryId = useMemo(
    () => normalizeSessionQueryFallback(session?.session_id || apiClient.getAuthToken()),
    [session?.session_id]
  )

  const sendHeartbeat = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      try {
        ws.current.send(JSON.stringify({ type: 'ping' }))
        logger.debug('Heartbeat ping sent')
      } catch (err) {
        logger.error('Failed to send heartbeat', { error: err })
      }
    }
  }, [])

  const startHeartbeat = useCallback(() => {
    if (heartbeatTimer.current) {
      clearInterval(heartbeatTimer.current)
    }

    heartbeatTimer.current = setInterval(sendHeartbeat, heartbeatInterval)
    logger.debug('Heartbeat started', { interval: heartbeatInterval })
  }, [heartbeatInterval, sendHeartbeat])

  const stopHeartbeat = useCallback(() => {
    if (heartbeatTimer.current) {
      clearInterval(heartbeatTimer.current)
      heartbeatTimer.current = null
      logger.debug('Heartbeat stopped')
    }
  }, [])

  const handleOpen = useCallback(() => {
    logger.info('Metrics WebSocket connected')
    setIsConnected(true)
    setIsConnecting(false)
    setError(null)
    setReconnectAttempts(0)
    startHeartbeat()
    onConnect?.()
  }, [onConnect, startHeartbeat])

  const handleMessage = useCallback(
    (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data) as MetricsWebSocketData | Record<string, unknown>

        if ((data as MetricsWebSocketData).type === 'pong') {
          logger.debug('Heartbeat pong received')
          return
        }

        const authDiagnostics = extractAuthDiagnostics(data)
        if (authDiagnostics) {
          logger.warn('Metrics websocket auth diagnostics received', {
            error: authDiagnostics.error,
            connection_id: authDiagnostics.details?.connection_id,
          })
          setError(authDiagnostics.message)
          if (authDiagnostics.error === SESSION_INVALID_ERROR) {
            isManualDisconnect.current = true
          }
        }

        setLastMessage(data as MetricsWebSocketData)
        onMessage?.(data as MetricsWebSocketData)
      } catch (err) {
        logger.error('Error parsing WebSocket message', { error: err })
        setError('Erro ao processar dados recebidos')
      }
    },
    [onMessage]
  )

  const handleError = useCallback(
    (event: Event) => {
      logger.error('Metrics WebSocket error', { event })
      setError('Erro de conexão WebSocket')
      onError?.(event)
    },
    [onError]
  )

  const handleClose = useCallback(
    (event: CloseEvent) => {
      logger.info('Metrics WebSocket disconnected', {
        manual: isManualDisconnect.current,
        attempts: reconnectAttempts,
        code: event.code,
        reason: event.reason,
      })

      setIsConnected(false)
      setIsConnecting(false)
      stopHeartbeat()
      onDisconnect?.()

      if (!isManualDisconnect.current && reconnectAttempts < maxReconnectAttempts) {
        const delay = Math.min(reconnectInterval * Math.pow(2, reconnectAttempts), 60000)
        logger.info('Scheduling reconnection', { delay, attempt: reconnectAttempts + 1 })

        reconnectTimer.current = setTimeout(() => {
          setReconnectAttempts((prev) => prev + 1)
          connectRef.current()
        }, delay)
      } else if (reconnectAttempts >= maxReconnectAttempts) {
        setError('Máximo de tentativas de reconexão atingido')
        logger.error('Max reconnection attempts reached')
      }
    },
    [maxReconnectAttempts, onDisconnect, reconnectAttempts, reconnectInterval, stopHeartbeat]
  )

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN || isConnecting) {
      return
    }

    if (!user && !sessionQueryId) {
      logger.error('Cannot connect: no authenticated session available')
      setError('Autenticação necessária')
      return
    }

    if (ws.current) {
      ws.current.close()
      ws.current = null
    }

    try {
      setIsConnecting(true)
      setError(null)
      isManualDisconnect.current = false

      const baseUrl = getWebSocketBaseUrl()
      const wsUrl = buildMetricsWebSocketUrl(baseUrl, sessionQueryId)

      logger.info('Connecting to metrics WebSocket', { url: baseUrl })

      const socket = new WebSocket(wsUrl)
      socket.addEventListener('open', handleOpen)
      socket.addEventListener('message', handleMessage)
      socket.addEventListener('error', handleError)
      socket.addEventListener('close', handleClose)

      ws.current = socket
    } catch (err) {
      logger.error('Failed to create WebSocket connection', { error: err })
      setError('Falha ao conectar ao servidor')
      setIsConnecting(false)
    }
  }, [handleClose, handleError, handleMessage, handleOpen, isConnecting, sessionQueryId, user])

  useEffect(() => {
    connectRef.current = connect
  }, [connect])

  const disconnect = useCallback(() => {
    logger.info('Manual disconnect requested')
    isManualDisconnect.current = true

    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current)
      reconnectTimer.current = null
    }

    stopHeartbeat()

    if (ws.current) {
      ws.current.close()
      ws.current = null
    }

    setIsConnected(false)
    setIsConnecting(false)
    setReconnectAttempts(0)
  }, [stopHeartbeat])

  const send = useCallback((data: MetricsWebSocketData) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      try {
        ws.current.send(JSON.stringify(data))
        logger.debug('Message sent', { data })
      } catch (err) {
        logger.error('Failed to send message', { error: err })
        setError('Falha ao enviar mensagem')
      }
    } else {
      logger.warn('Cannot send message: WebSocket not connected')
      setError('WebSocket não conectado')
    }
  }, [])

  useEffect(() => {
    if (user || sessionQueryId) {
      logger.info('Authenticated session available, auto-connecting metrics WebSocket')
      connect()
    } else {
      logger.info('No authenticated session available, disconnecting metrics WebSocket')
      disconnect()
    }

    return () => {
      disconnect()
    }
  }, [connect, disconnect, sessionQueryId, user])

  return {
    isConnected,
    isConnecting,
    error,
    lastMessage,
    reconnectAttempts,
    send,
    connect,
    disconnect,
  }
}
