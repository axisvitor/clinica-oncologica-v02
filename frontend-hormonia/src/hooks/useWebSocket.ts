import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from './useAuth'
import { useConfig } from '@/lib/config-initializer'
import { createLogger } from '../lib/logger'
import type { WebSocketMessage, SystemNotification, PatientUpdate } from './types'

const logger = createLogger('useWebSocket')

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

export function useWebSocket(options: WebSocketHookOptions = {}) {
  const { config } = useConfig()
  const {
    // Use VITE_WS_BASE_URL (standardized) with fallback to VITE_WS_URL
    // Default port changed to 8000 (backend port) instead of 8080
    url = config?.VITE_WS_BASE_URL || config?.VITE_WS_URL || 'ws://localhost:8000/ws',
    reconnectAttempts = 5,
    reconnectInterval = 3000,
    onMessage,
    onError,
    onOpen,
    onClose,
  } = options

  const { user, token, websocketToken, refreshToken } = useAuth()
  const [isConnected, setIsConnected] = useState(false)
  const [connectionState, setConnectionState] = useState<
    'connecting' | 'connected' | 'disconnected' | 'error'
  >('disconnected')
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectCountRef = useRef(0)
  const shouldReconnectRef = useRef(true)

  const connect = useCallback(async () => {
    // Force refresh Firebase token before connecting to prevent expired token errors
    if (refreshToken) {
      try {
        await refreshToken()
        logger.debug('Firebase token refreshed before WebSocket connection')
      } catch (error) {
        logger.warn('Failed to refresh token before WebSocket connection:', error)
        // Continue anyway - token might still be valid
      }
    }

    // Use the token from user or direct token (after refresh)
    const authToken = websocketToken || user?.token || token
    if (!authToken) {
      logger.warn('Cannot connect WebSocket: no authentication token available')
      return
    }

    // CRITICAL FIX: Prevent duplicate connections
    // Check if WebSocket is already connecting or open
    if (
      wsRef.current?.readyState === WebSocket.CONNECTING ||
      wsRef.current?.readyState === WebSocket.OPEN
    ) {
      logger.debug('WebSocket already connecting or connected, skipping duplicate connection')
      return
    }

    try {
      setConnectionState('connecting')

      // Build WebSocket URL - handle both absolute URLs and relative paths
      let finalUrl: string
      if (url.startsWith('ws://') || url.startsWith('wss://')) {
        // Absolute WebSocket URL
        finalUrl = url
      } else {
        // Relative path - backend only exposes /ws/connect, ignore path from component
        // All WebSocket connections go to the same endpoint, use rooms for routing
        finalUrl =
          config?.VITE_WS_BASE_URL || config?.VITE_WS_URL || 'ws://localhost:8000/ws/connect'
      }

      // Normalize URL to ensure proper protocol format (wss:// not wss:)
      finalUrl = finalUrl.replace(/^wss:(?!\/\/)/, 'wss://').replace(/^ws:(?!\/\/)/, 'ws://')

      const wsUrl = new URL(finalUrl)
      wsUrl.searchParams.set('token', authToken)

      wsRef.current = new WebSocket(wsUrl.toString())

      wsRef.current.onopen = () => {
        logger.info('WebSocket connection established')
        setIsConnected(true)
        setConnectionState('connected')
        reconnectCountRef.current = 0
        onOpen?.()
      }

      wsRef.current.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)
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

        // Only reconnect if:
        // 1. shouldReconnect flag is true
        // 2. Haven't exceeded max reconnect attempts
        if (shouldReconnectRef.current && reconnectCountRef.current < reconnectAttempts) {
          reconnectCountRef.current++
          logger.info(
            `Scheduling reconnection attempt ${reconnectCountRef.current}/${reconnectAttempts} in ${reconnectInterval}ms`
          )
          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
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
    // eslint-disable-next-line react-hooks/exhaustive-deps -- config is stable and adding it causes infinite reconnection loops
  }, [
    url,
    user?.token,
    token,
    websocketToken,
    refreshToken,
    reconnectAttempts,
    reconnectInterval,
    onMessage,
    onError,
    onOpen,
    onClose,
  ])

  const disconnect = useCallback(() => {
    logger.info('Disconnecting WebSocket (intentional)')
    shouldReconnectRef.current = false

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    if (wsRef.current) {
      // Close with code 1000 (normal closure) to indicate intentional disconnect
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

  // CRITICAL FIX: Removed connect/disconnect from dependencies to prevent unnecessary reconnections
  // Only reconnect when authentication token actually changes
  useEffect(() => {
    const authToken = websocketToken || user?.token || token
    if (authToken) {
      logger.debug('Authentication token available, connecting WebSocket')
      shouldReconnectRef.current = true // Enable reconnections
      connect()
    } else {
      logger.debug('No authentication token, disconnecting WebSocket')
      disconnect()
    }

    return () => {
      logger.debug('useWebSocket cleanup: disabling reconnections and disconnecting')
      shouldReconnectRef.current = false
      disconnect()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- connect/disconnect are stable via useCallback; including them causes infinite reconnection loops
  }, [user?.token, token, websocketToken])

  return {
    isConnected,
    connectionState,
    lastMessage,
    connect,
    disconnect,
    sendMessage,
  }
}

/**
 * Hook for system notifications via WebSocket
 * @returns notifications array, connection status, and clear function
 */
export function useSystemNotifications() {
  const [notifications, setNotifications] = useState<SystemNotification[]>([])

  const handleMessage = useCallback((message: WebSocketMessage<SystemNotification>) => {
    if (message.type === 'system_notification' && message.data) {
      setNotifications((prev) => [message.data!, ...prev.slice(0, 49)]) // Keep last 50
    }
  }, [])

  const { isConnected } = useWebSocket({
    onMessage: handleMessage as (message: WebSocketMessage<unknown>) => void,
  })

  return {
    notifications,
    isConnected,
    clearNotifications: () => setNotifications([]),
  }
}

/**
 * Hook for patient update events via WebSocket
 * @returns updates array, connection status, and clear function
 */
export function usePatientUpdates() {
  const [updates, setUpdates] = useState<PatientUpdate[]>([])

  const handleMessage = useCallback((message: WebSocketMessage<PatientUpdate>) => {
    if (message.type === 'patient_update' && message.data) {
      setUpdates((prev) => [message.data!, ...prev.slice(0, 99)]) // Keep last 100
    }
  }, [])

  const { isConnected } = useWebSocket({
    onMessage: handleMessage as (message: WebSocketMessage<unknown>) => void,
  })

  return {
    updates,
    isConnected,
    clearUpdates: () => setUpdates([]),
  }
}
