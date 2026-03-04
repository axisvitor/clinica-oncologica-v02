/**
 * User WebSocket Hook - Real-time Updates
 *
 * Manages WebSocket connection for live user data updates
 * - Automatic reconnection with exponential backoff
 * - Connection state management
 * - Message broadcasting to query cache
 *
 * @module hooks/admin/useUserWebSocket
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { createLogger } from '@/utils/logger'

const logger = createLogger('useUserWebSocket')

export interface UseUserWebSocketOptions {
  /** Enable real-time updates */
  enabled?: boolean
  /** Maximum reconnection attempts before giving up */
  maxReconnectAttempts?: number
  /** Base delay for reconnection (ms) */
  reconnectDelay?: number
}

export interface WebSocketMessage {
  type: 'user_created' | 'user_updated' | 'user_deleted' | 'ping' | 'pong'
  data?: Record<string, unknown>
  timestamp?: string
}

/**
 * Hook for managing WebSocket connection to admin user updates
 *
 * @param options - Configuration options
 * @returns WebSocket connection state and utilities
 *
 * @example
 * ```tsx
 * const { isConnected, sendMessage } = useUserWebSocket({
 *   enabled: true,
 *   maxReconnectAttempts: 5
 * })
 *
 * // Send message when user is created
 * sendMessage({ type: 'user_created', data: { user } })
 * ```
 */
export function useUserWebSocket(options: UseUserWebSocketOptions = {}) {
  const { enabled = true, maxReconnectAttempts = 10, reconnectDelay = 1000 } = options

  const queryClient = useQueryClient()
  const [wsConnection, setWsConnection] = useState<WebSocket | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [reconnectAttempts, setReconnectAttempts] = useState(0)

  // Use refs to avoid recreating the connection on every render
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const heartbeatIntervalRef = useRef<NodeJS.Timeout | null>(null)

  /**
   * Clear reconnection timeout
   */
  const clearReconnectTimeout = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
  }, [])

  /**
   * Clear heartbeat interval
   */
  const clearHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current)
      heartbeatIntervalRef.current = null
    }
  }, [])

  /**
   * Setup heartbeat to keep connection alive
   */
  const setupHeartbeat = useCallback(
    (ws: WebSocket) => {
      clearHeartbeat()

      heartbeatIntervalRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }))
        }
      }, 30000) // Ping every 30 seconds
    },
    [clearHeartbeat]
  )

  /**
   * Handle incoming WebSocket messages
   */
  const handleMessage = useCallback(
    (event: MessageEvent) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data)

        // Handle different message types
        switch (message.type) {
          case 'user_created':
          case 'user_updated':
          case 'user_deleted':
            // Invalidate queries to refresh data
            queryClient.invalidateQueries({ queryKey: ['admin-users'] })
            queryClient.invalidateQueries({ queryKey: ['admin-stats'] })
            logger.debug(`Received ${message.type} event, invalidating queries`)
            break

          case 'pong':
            // Heartbeat response
            break

          default:
            logger.warn('Unknown message type:', message.type)
        }
      } catch (error) {
        logger.error('Error parsing WebSocket message', error instanceof Error ? error : undefined)
      }
    },
    [queryClient]
  )

  /**
   * Connect to WebSocket with exponential backoff
   */
  const connectWebSocket = useCallback(() => {
    if (!enabled) {
      logger.debug('WebSocket disabled, skipping connection')
      return
    }

    if (reconnectAttempts >= maxReconnectAttempts) {
      logger.error(`Max reconnection attempts (${maxReconnectAttempts}) reached`)
      return
    }

    clearReconnectTimeout()

    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}/ws/admin/users`

      logger.debug('Connecting to WebSocket:', wsUrl)
      const ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        logger.info('WebSocket connection established')
        setIsConnected(true)
        setWsConnection(ws)
        setReconnectAttempts(0)
        setupHeartbeat(ws)
      }

      ws.onmessage = handleMessage

      ws.onerror = (event) => {
        logger.error('WebSocket connection error:', event)
        setIsConnected(false)
      }

      ws.onclose = (event) => {
        logger.warn('WebSocket connection closed:', {
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean,
        })

        setIsConnected(false)
        setWsConnection(null)
        clearHeartbeat()

        // Attempt to reconnect with exponential backoff
        if (enabled && reconnectAttempts < maxReconnectAttempts) {
          const delay = reconnectDelay * Math.pow(2, reconnectAttempts)
          logger.debug(
            `Reconnecting in ${delay}ms (attempt ${reconnectAttempts + 1}/${maxReconnectAttempts})`
          )

          reconnectTimeoutRef.current = setTimeout(() => {
            setReconnectAttempts((prev) => prev + 1)
            connectWebSocket()
          }, delay)
        }
      }

      return ws
    } catch (error) {
      logger.error(
        'Failed to create WebSocket connection',
        error instanceof Error ? error : undefined
      )
      setIsConnected(false)
      return null
    }
  }, [
    enabled,
    reconnectAttempts,
    maxReconnectAttempts,
    reconnectDelay,
    handleMessage,
    setupHeartbeat,
    clearHeartbeat,
    clearReconnectTimeout,
  ])

  /**
   * Send message through WebSocket
   */
  const sendMessage = useCallback(
    (message: WebSocketMessage) => {
      if (wsConnection && isConnected && wsConnection.readyState === WebSocket.OPEN) {
        wsConnection.send(JSON.stringify(message))
        logger.debug('Message sent:', message.type)
      } else {
        logger.warn('Cannot send message: WebSocket not connected')
      }
    },
    [wsConnection, isConnected]
  )

  /**
   * Manually reconnect WebSocket
   */
  const reconnect = useCallback(() => {
    if (wsConnection) {
      wsConnection.close()
    }
    setReconnectAttempts(0)
    connectWebSocket()
  }, [wsConnection, connectWebSocket])

  /**
   * Disconnect WebSocket
   */
  const disconnect = useCallback(() => {
    clearReconnectTimeout()
    clearHeartbeat()

    if (wsConnection) {
      wsConnection.close()
      setWsConnection(null)
    }

    setIsConnected(false)
    setReconnectAttempts(0)
  }, [wsConnection, clearReconnectTimeout, clearHeartbeat])

  // Initialize connection
  useEffect(() => {
    if (!enabled) return

    const ws = connectWebSocket()

    return () => {
      clearReconnectTimeout()
      clearHeartbeat()

      if (ws) {
        ws.close()
      }
    }
  }, [enabled, connectWebSocket, clearReconnectTimeout, clearHeartbeat])

  return {
    /** Whether WebSocket is connected */
    isConnected,
    /** Number of reconnection attempts */
    reconnectAttempts,
    /** Send message through WebSocket */
    sendMessage,
    /** Manually reconnect */
    reconnect,
    /** Disconnect WebSocket */
    disconnect,
  }
}
