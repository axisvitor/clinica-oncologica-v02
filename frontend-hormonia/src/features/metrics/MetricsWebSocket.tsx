/**
 * WebSocket Hook for Real-time Metrics
 *
 * Provides real-time metrics streaming with automatic reconnection,
 * connection state management, and message handling for the healthcare dashboard.
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { createLogger } from '../../lib/logger'
import { apiClient } from '@/lib/api-client'

const logger = createLogger('metrics:websocket')

interface WebSocketOptions {
  onMessage?: (data: unknown) => void
  onError?: (error: Event) => void
  onConnect?: () => void
  onDisconnect?: () => void
  reconnectInterval?: number
  maxReconnectAttempts?: number
}

interface MetricsWebSocketReturn {
  isConnected: boolean
  isConnecting: boolean
  error: string | null
  lastMessage: unknown
  connect: () => void
  disconnect: () => void
  reconnectAttempts: number
}

/**
 * NOTE: The backend WebSocket endpoint /api/v2/metrics/live does not exist.
 * This hook now uses HTTP polling as a fallback instead of WebSocket.
 * When the backend implements the WebSocket endpoint, set WEBSOCKET_ENABLED to true.
 */
const WEBSOCKET_ENABLED = false // Disable until backend implements the endpoint

export const MetricsWebSocket = ({
  onMessage,
  onError,
  onConnect,
  onDisconnect,
  reconnectInterval = 5000,
  maxReconnectAttempts = 10,
}: WebSocketOptions = {}): MetricsWebSocketReturn => {
  const [isConnected, setIsConnected] = useState(false)
  const [isConnecting, setIsConnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastMessage, setLastMessage] = useState<unknown>(null)
  const [reconnectAttempts, setReconnectAttempts] = useState(0)

  const ws = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<NodeJS.Timeout | null>(null)
  const pollingTimer = useRef<NodeJS.Timeout | null>(null)
  const isManualDisconnect = useRef(false)

  const getWebSocketUrl = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    // WebSocket connections automatically include cookies
    return `${protocol}//${host}/api/v2/metrics/live`
  }, [])

  // Polling fallback when WebSocket is not available
  const startPolling = useCallback(() => {
    if (pollingTimer.current) return

    const poll = async () => {
      try {
        const response = await fetch(
          `${apiClient.getBaseURL()}/api/v2/enhanced-analytics/realtime-stream`,
          {
            credentials: 'include',
            headers: {
              ...apiClient.getSessionHeaders(),
            },
          }
        )
        if (response.ok) {
          const data = await response.json()
          setLastMessage(data)
          onMessage?.(data)
        }
      } catch (err) {
        logger.warn('Polling failed', { error: err })
      }
    }

    // Initial poll
    poll()

    // Set up interval
    pollingTimer.current = setInterval(poll, reconnectInterval)
    setIsConnected(true)
    onConnect?.()
  }, [onMessage, onConnect, reconnectInterval])

  const stopPolling = useCallback(() => {
    if (pollingTimer.current) {
      clearInterval(pollingTimer.current)
      pollingTimer.current = null
    }
    setIsConnected(false)
    onDisconnect?.()
  }, [onDisconnect])

  const handleOpen = useCallback(() => {
    logger.info('Metrics WebSocket connected')
    setIsConnected(true)
    setIsConnecting(false)
    setError(null)
    setReconnectAttempts(0)

    onConnect?.()
  }, [onConnect])

  const handleMessage = useCallback(
    (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data)
        setLastMessage(data)
        onMessage?.(data)
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
      setIsConnected(false)
      setIsConnecting(false)

      onError?.(event)
    },
    [onError]
  )

  const handleClose = useCallback(
    (event: CloseEvent) => {
      logger.info('Metrics WebSocket closed', { code: event.code, reason: event.reason })
      setIsConnected(false)
      setIsConnecting(false)

      // Clear any existing reconnect timer
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current)
        reconnectTimer.current = null
      }

      onDisconnect?.()

      // Handle different close codes
      if (event.code === 4001) {
        setError('Acesso negado - token inválido')
        return
      }

      if (event.code === 4000) {
        setError('Erro de autenticação')
        return
      }

      // Only attempt to reconnect if it wasn't a manual disconnect
      if (!isManualDisconnect.current && reconnectAttempts < maxReconnectAttempts) {
        setError(`Conexão perdida. Tentativa ${reconnectAttempts + 1}/${maxReconnectAttempts}...`)

        reconnectTimer.current = setTimeout(() => {
          setReconnectAttempts((prev) => prev + 1)
          connect()
        }, reconnectInterval)
      } else if (reconnectAttempts >= maxReconnectAttempts) {
        setError('Falha na conexão após múltiplas tentativas')
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps -- connect is intentionally excluded to prevent circular dependency
    },
    [reconnectAttempts, maxReconnectAttempts, reconnectInterval, onDisconnect]
  )

  const connect = useCallback(() => {
    // Don't connect if already connected or connecting
    if (isConnected || isConnecting) {
      return
    }

    // Use polling fallback if WebSocket is disabled
    if (!WEBSOCKET_ENABLED) {
      logger.info('WebSocket disabled, using polling fallback')
      startPolling()
      return
    }

    // Clear any existing connection
    if (ws.current) {
      ws.current.removeEventListener('open', handleOpen)
      ws.current.removeEventListener('message', handleMessage)
      ws.current.removeEventListener('error', handleError)
      ws.current.removeEventListener('close', handleClose)
      ws.current.close()
    }

    try {
      setIsConnecting(true)
      setError(null)
      isManualDisconnect.current = false

      const wsUrl = getWebSocketUrl()
      ws.current = new WebSocket(wsUrl)

      ws.current.addEventListener('open', handleOpen)
      ws.current.addEventListener('message', handleMessage)
      ws.current.addEventListener('error', handleError)
      ws.current.addEventListener('close', handleClose)

      // Connection timeout
      const connectionTimeout = setTimeout(() => {
        if (isConnecting && !isConnected) {
          setError('Timeout na conexão')
          setIsConnecting(false)
          ws.current?.close()
        }
      }, 10000) // 10 seconds timeout

      ws.current.addEventListener('open', () => {
        clearTimeout(connectionTimeout)
      })
    } catch (err) {
      logger.error('Error creating WebSocket connection', { error: err })
      setError('Erro ao criar conexão WebSocket')
      setIsConnecting(false)
    }
  }, [
    isConnected,
    isConnecting,
    getWebSocketUrl,
    handleOpen,
    handleMessage,
    handleError,
    handleClose,
    startPolling,
  ])

  const disconnect = useCallback(() => {
    isManualDisconnect.current = true

    // Stop polling if active
    stopPolling()

    // Clear reconnect timer
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current)
      reconnectTimer.current = null
    }

    // Close WebSocket connection
    if (ws.current) {
      ws.current.removeEventListener('open', handleOpen)
      ws.current.removeEventListener('message', handleMessage)
      ws.current.removeEventListener('error', handleError)
      ws.current.removeEventListener('close', handleClose)

      // Use code 1000 for normal closure
      ws.current.close(1000, 'Manual disconnect')
      ws.current = null
    }

    setIsConnected(false)
    setIsConnecting(false)
    setError(null)
    setReconnectAttempts(0)
  }, [handleOpen, handleMessage, handleError, handleClose, stopPolling])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect()
    }
  }, [disconnect])

  // Handle visibility change - pause/resume connection
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        // Page is hidden, disconnect to save resources
        if (isConnected) {
          disconnect()
        }
      } else if (document.visibilityState === 'visible') {
        // Page is visible again, reconnect
        if (!isConnected && !isConnecting) {
          setTimeout(connect, 1000) // Small delay to ensure page is fully loaded
        }
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [isConnected, isConnecting, connect, disconnect])

  // Handle online/offline status
  useEffect(() => {
    const handleOnline = () => {
      if (!isConnected && !isConnecting) {
        setTimeout(connect, 1000)
      }
    }

    const handleOffline = () => {
      setError('Sem conexão com a internet')
      disconnect()
    }

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [isConnected, isConnecting, connect, disconnect])

  // Heartbeat mechanism to detect stale connections
  useEffect(() => {
    if (!isConnected) return

    const heartbeatInterval = setInterval(() => {
      if (ws.current && ws.current.readyState === WebSocket.OPEN) {
        try {
          ws.current.send(JSON.stringify({ type: 'ping' }))
        } catch (err) {
          logger.error('Heartbeat failed', { error: err })
          setError('Conexão instável')
          disconnect()
        }
      }
    }, 30000) // Send ping every 30 seconds

    return () => {
      clearInterval(heartbeatInterval)
    }
  }, [isConnected, disconnect])

  return {
    isConnected,
    isConnecting,
    error,
    lastMessage,
    connect,
    disconnect,
    reconnectAttempts,
  }
}
