import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from './useAuth'
import { useConfig } from '@/lib/config-initializer'

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
    url = config?.VITE_WS_BASE_URL || 'ws://localhost:8080/ws',
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
      console.warn('Cannot connect WebSocket: no authentication token available')
      return
    }

    if (wsRef.current?.readyState === WebSocket.CONNECTING || wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    try {
      setConnectionState('connecting')
      const wsUrl = new URL(url)
      wsUrl.searchParams.set('token', authToken)

      wsRef.current = new WebSocket(wsUrl.toString())

      wsRef.current.onopen = () => {
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
          console.error('Failed to parse WebSocket message:', error)
        }
      }

      wsRef.current.onclose = () => {
        setIsConnected(false)
        setConnectionState('disconnected')
        onClose?.()

        if (shouldReconnectRef.current && reconnectCountRef.current < reconnectAttempts) {
          reconnectCountRef.current++
          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
          }, reconnectInterval)
        }
      }

      wsRef.current.onerror = (error) => {
        setConnectionState('error')
        onError?.(error)
      }
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error)
      setConnectionState('error')
    }
  }, [url, user?.token, token, reconnectAttempts, reconnectInterval, onMessage, onError, onOpen, onClose])

  const disconnect = useCallback(() => {
    shouldReconnectRef.current = false

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    if (wsRef.current) {
      wsRef.current.close()
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
    return false
  }, [])

  useEffect(() => {
    const authToken = user?.token || token
    if (authToken) {
      connect()
    } else {
      disconnect()
    }

    return () => {
      shouldReconnectRef.current = false
      disconnect()
    }
  }, [user?.token, token, connect, disconnect])

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