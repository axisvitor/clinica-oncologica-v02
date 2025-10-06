import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from './useAuth'
import { useConfig } from '@/lib/config-initializer'
import { createLogger } from '../lib/logger'

const logger = createLogger('useWebSocket')

interface WebSocketMessage {
  type: string
  data?: any
  timestamp: string
}

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
    onClose
  } = options

  const { user, token } = useAuth()
  const [isConnected, setIsConnected] = useState(false)
  const [connectionState, setConnectionState] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected')
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectCountRef = useRef(0)
  const shouldReconnectRef = useRef(true)

  const connect = useCallback(() => {
    // Use the token from user or direct token
    const authToken = user?.token || token
    if (!authToken) {
      logger.warn('Cannot connect WebSocket: no authentication token available')
      return
    }

    // CRITICAL FIX: Prevent duplicate connections
    // Check if WebSocket is already connecting or open
    if (wsRef.current?.readyState === WebSocket.CONNECTING || wsRef.current?.readyState === WebSocket.OPEN) {
      logger.debug('WebSocket already connecting or connected, skipping duplicate connection')
      return
    }

    try {
      setConnectionState('connecting')

      // Build WebSocket URL - handle both absolute URLs and relative paths
      let wsUrl: URL
      if (url.startsWith('ws://') || url.startsWith('wss://')) {
        // Absolute WebSocket URL
        wsUrl = new URL(url)
      } else {
        // Relative path - backend only exposes /ws/connect, ignore path from component
        // All WebSocket connections go to the same endpoint, use rooms for routing
        const baseWsUrl = config?.VITE_WS_BASE_URL || config?.VITE_WS_URL || 'ws://localhost:8000/ws/connect'
        wsUrl = new URL(baseWsUrl)
      }

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
        logger.info(`WebSocket connection closed (code: ${event.code}, reason: ${event.reason || 'none'})`)
        setIsConnected(false)
        setConnectionState('disconnected')
        onClose?.()

        // Only reconnect if:
        // 1. shouldReconnect flag is true
        // 2. Haven't exceeded max reconnect attempts
        if (shouldReconnectRef.current && reconnectCountRef.current < reconnectAttempts) {
          reconnectCountRef.current++
          logger.info(`Scheduling reconnection attempt ${reconnectCountRef.current}/${reconnectAttempts} in ${reconnectInterval}ms`)
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
  }, [url, user?.token, token, reconnectAttempts, reconnectInterval, onMessage, onError, onOpen, onClose])

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
        timestamp: new Date().toISOString()
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
    const authToken = user?.token || token
    if (authToken) {
      logger.debug('Authentication token available, connecting WebSocket')
      shouldReconnectRef.current = true  // Enable reconnections
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.token, token])
  // NOTE: connect/disconnect are intentionally NOT in dependencies
  // They are stable via useCallback and adding them causes unnecessary reconnections
  // ESLint warning is safe to ignore in this specific case

  return {
    isConnected,
    connectionState,
    lastMessage,
    connect,
    disconnect,
    sendMessage
  }
}

export function useSystemNotifications() {
  const [notifications, setNotifications] = useState<any[]>([])

  const handleMessage = useCallback((message: WebSocketMessage) => {
    if (message.type === 'system_notification') {
      setNotifications(prev => [message.data, ...prev.slice(0, 49)]) // Keep last 50
    }
  }, [])

  const { isConnected } = useWebSocket({
    onMessage: handleMessage
  })

  return {
    notifications,
    isConnected,
    clearNotifications: () => setNotifications([])
  }
}

export function usePatientUpdates() {
  const [updates, setUpdates] = useState<any[]>([])

  const handleMessage = useCallback((message: WebSocketMessage) => {
    if (message.type === 'patient_update') {
      setUpdates(prev => [message.data, ...prev.slice(0, 99)]) // Keep last 100
    }
  }, [])

  const { isConnected } = useWebSocket({
    onMessage: handleMessage
  })

  return {
    updates,
    isConnected,
    clearUpdates: () => setUpdates([])
  }
}