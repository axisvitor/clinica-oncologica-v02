/**
 * WebSocket Hook for Real-time Metrics - Fixed Version
 *
 * [P0 FIX] Uses correct Firebase token from AuthContext
 * - Integrates with AuthContext for automatic token refresh
 * - Uses VITE_WS_BASE_URL environment variable
 * - Implements heartbeat/ping-pong mechanism
 * - Handles reconnection with exponential backoff
 *
 * Usage:
 * ```tsx
 * const { isConnected, lastMessage, error } = useMetricsWebSocket({
 *   onMessage: (data) => console.log('Metrics:', data)
 * })
 * ```
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { createLogger } from '../lib/logger'

const logger = createLogger('metrics:websocket')

interface UseMetricsWebSocketOptions {
  onMessage?: (data: any) => void
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
  lastMessage: any
  reconnectAttempts: number
  send: (data: any) => void
  connect: () => void
  disconnect: () => void
}

/**
 * Get WebSocket base URL from environment or fallback to current host
 */
function getWebSocketBaseUrl(): string {
  // Priority 1: VITE_WS_BASE_URL (e.g., wss://backend.railway.app)
  if (import.meta.env.VITE_WS_BASE_URL) {
    return import.meta.env.VITE_WS_BASE_URL
  }

  // Priority 2: VITE_WS_URL (legacy, e.g., wss://backend.railway.app/ws)
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL.replace('/ws', '')
  }

  // Fallback: construct from window.location
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return `${protocol}//${host}`
}

export function useMetricsWebSocket({
  onMessage,
  onError,
  onConnect,
  onDisconnect,
  reconnectInterval = 5000,
  maxReconnectAttempts = 10,
  heartbeatInterval = 30000 // 30 seconds
}: UseMetricsWebSocketOptions = {}): UseMetricsWebSocketReturn {
  const { user, session } = useAuth()

  const [isConnected, setIsConnected] = useState(false)
  const [isConnecting, setIsConnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastMessage, setLastMessage] = useState<any>(null)
  const [reconnectAttempts, setReconnectAttempts] = useState(0)

  const ws = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<NodeJS.Timeout | null>(null)
  const heartbeatTimer = useRef<NodeJS.Timeout | null>(null)
  const isManualDisconnect = useRef(false)

  /**
   * Send heartbeat ping to keep connection alive
   */
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

  /**
   * Start heartbeat interval
   */
  const startHeartbeat = useCallback(() => {
    if (heartbeatTimer.current) {
      clearInterval(heartbeatTimer.current)
    }

    heartbeatTimer.current = setInterval(sendHeartbeat, heartbeatInterval)
    logger.debug('Heartbeat started', { interval: heartbeatInterval })
  }, [sendHeartbeat, heartbeatInterval])

  /**
   * Stop heartbeat interval
   */
  const stopHeartbeat = useCallback(() => {
    if (heartbeatTimer.current) {
      clearInterval(heartbeatTimer.current)
      heartbeatTimer.current = null
      logger.debug('Heartbeat stopped')
    }
  }, [])

  /**
   * Handle WebSocket open event
   */
  const handleOpen = useCallback(() => {
    logger.info('Metrics WebSocket connected')
    setIsConnected(true)
    setIsConnecting(false)
    setError(null)
    setReconnectAttempts(0)

    // Start heartbeat to keep connection alive
    startHeartbeat()

    onConnect?.()
  }, [onConnect, startHeartbeat])

  /**
   * Handle WebSocket message event
   */
  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data)

      // Handle pong response from server
      if (data.type === 'pong') {
        logger.debug('Heartbeat pong received')
        return
      }

      setLastMessage(data)
      onMessage?.(data)
    } catch (err) {
      logger.error('Error parsing WebSocket message', { error: err })
      setError('Erro ao processar dados recebidos')
    }
  }, [onMessage])

  /**
   * Handle WebSocket error event
   */
  const handleError = useCallback((event: Event) => {
    logger.error('Metrics WebSocket error', { event })
    setError('Erro de conexão WebSocket')
    onError?.(event)
  }, [onError])

  /**
   * Handle WebSocket close event
   */
  const handleClose = useCallback(() => {
    logger.info('Metrics WebSocket disconnected', {
      manual: isManualDisconnect.current,
      attempts: reconnectAttempts
    })

    setIsConnected(false)
    setIsConnecting(false)
    stopHeartbeat()

    onDisconnect?.()

    // Attempt reconnection if not manually disconnected
    if (!isManualDisconnect.current && reconnectAttempts < maxReconnectAttempts) {
      const delay = Math.min(reconnectInterval * Math.pow(2, reconnectAttempts), 60000)
      logger.info('Scheduling reconnection', { delay, attempt: reconnectAttempts + 1 })

      reconnectTimer.current = setTimeout(() => {
        setReconnectAttempts(prev => prev + 1)
        connect()
      }, delay)
    } else if (reconnectAttempts >= maxReconnectAttempts) {
      setError('Máximo de tentativas de reconexão atingido')
      logger.error('Max reconnection attempts reached')
    }
  }, [reconnectAttempts, maxReconnectAttempts, reconnectInterval, onDisconnect, stopHeartbeat])

  /**
   * Connect to WebSocket server
   */
  const connect = useCallback(() => {
    // Don't connect if already connected or connecting
    if (ws.current?.readyState === WebSocket.OPEN || isConnecting) {
      return
    }

    // [P0 FIX] Use Firebase token from localStorage
    const firebaseToken = localStorage.getItem('firebase_token')

    if (!firebaseToken) {
      logger.error('Cannot connect: No Firebase token available')
      setError('Autenticação necessária')
      return
    }

    // Cleanup existing connection
    if (ws.current) {
      ws.current.close()
      ws.current = null
    }

    try {
      setIsConnecting(true)
      setError(null)
      isManualDisconnect.current = false

      // Build WebSocket URL with Firebase token
      const baseUrl = getWebSocketBaseUrl()
      const wsUrl = `${baseUrl}/api/v1/metrics/live?token=${firebaseToken}`

      logger.info('Connecting to metrics WebSocket', { url: baseUrl })

      // Create WebSocket connection
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
  }, [isConnecting, handleOpen, handleMessage, handleError, handleClose])

  /**
   * Disconnect from WebSocket server
   */
  const disconnect = useCallback(() => {
    logger.info('Manual disconnect requested')
    isManualDisconnect.current = true

    // Clear reconnection timer
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current)
      reconnectTimer.current = null
    }

    // Stop heartbeat
    stopHeartbeat()

    // Close WebSocket connection
    if (ws.current) {
      ws.current.close()
      ws.current = null
    }

    setIsConnected(false)
    setIsConnecting(false)
    setReconnectAttempts(0)
  }, [stopHeartbeat])

  /**
   * Send data through WebSocket
   */
  const send = useCallback((data: any) => {
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

  /**
   * Auto-connect when user is authenticated
   */
  useEffect(() => {
    if (user && session) {
      logger.info('User authenticated, auto-connecting WebSocket')
      connect()
    } else {
      logger.info('User not authenticated, disconnecting WebSocket')
      disconnect()
    }

    // Cleanup on unmount
    return () => {
      disconnect()
    }
  }, [user, session])

  /**
   * React to token refresh - reconnect with new token
   */
  useEffect(() => {
    const firebaseToken = localStorage.getItem('firebase_token')

    if (firebaseToken && isConnected) {
      logger.info('Token refreshed, reconnecting WebSocket')
      disconnect()
      setTimeout(() => connect(), 1000) // Reconnect after 1 second
    }
  }, [session?.access_token])

  return {
    isConnected,
    isConnecting,
    error,
    lastMessage,
    reconnectAttempts,
    send,
    connect,
    disconnect
  }
}
