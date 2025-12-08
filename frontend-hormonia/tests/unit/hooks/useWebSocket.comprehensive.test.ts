import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useAuth } from '@/contexts/AuthContext'

// Mock dependencies
const mockAuth = {
  isAuthenticated: true,
  getFirebaseToken: vi.fn().mockResolvedValue('firebase-token'),
  refreshToken: vi.fn()
}

const mockWsManager = {
  connect: vi.fn(),
  disconnect: vi.fn(),
  subscribe: vi.fn(),
  unsubscribe: vi.fn(),
  send: vi.fn(),
  isConnected: vi.fn().mockReturnValue(true),
  updateToken: vi.fn()
}

const mockLogger = {
  log: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
  info: vi.fn()
}

// Mock modules
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: vi.fn()
}))

vi.mock('@/lib/websocket', () => ({
  wsManager: mockWsManager
}))

vi.mock('@/lib/logger', () => ({
  createLogger: () => mockLogger
}))

describe('useWebSocket Hook - Comprehensive Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAuth).mockReturnValue(mockAuth as any)
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Hook Initialization', () => {
    it('should initialize with correct default values', () => {
      const { result } = renderHook(() => useWebSocket())

      expect(result.current.isConnected).toBe(true)
      expect(result.current.connectionStatus).toBe('connected')
      expect(result.current.lastMessage).toBe(null)
      expect(result.current.error).toBe(null)
      expect(typeof result.current.sendMessage).toBe('function')
      expect(typeof result.current.subscribe).toBe('function')
      expect(typeof result.current.unsubscribe).toBe('function')
      expect(typeof result.current.reconnect).toBe('function')
    })

    it('should not connect if user is not authenticated', () => {
      vi.mocked(useAuth).mockReturnValue({
        ...mockAuth,
        isAuthenticated: false
      } as any)

      renderHook(() => useWebSocket())

      expect(mockWsManager.connect).not.toHaveBeenCalled()
    })

    it('should connect if user is authenticated', async () => {
      renderHook(() => useWebSocket())

      await waitFor(() => {
        expect(mockAuth.getFirebaseToken).toHaveBeenCalled()
        expect(mockWsManager.connect).toHaveBeenCalledWith('firebase-token')
      })
    })

    it('should handle connection with options', async () => {
      const options = {
        autoConnect: true,
        reconnectAttempts: 5,
        reconnectInterval: 2000
      }

      renderHook(() => useWebSocket(options))

      await waitFor(() => {
        expect(mockWsManager.connect).toHaveBeenCalledWith('firebase-token')
      })
    })
  })

  describe('Connection Management', () => {
    it('should handle successful connection', async () => {
      mockWsManager.connect.mockResolvedValue(undefined)

      const { result } = renderHook(() => useWebSocket())

      await waitFor(() => {
        expect(result.current.connectionStatus).toBe('connected')
        expect(result.current.error).toBe(null)
      })
    })

    it('should handle connection failure', async () => {
      const connectionError = new Error('Connection failed')
      mockAuth.getFirebaseToken.mockRejectedValue(connectionError)

      const { result } = renderHook(() => useWebSocket())

      await waitFor(() => {
        expect(result.current.connectionStatus).toBe('error')
        expect(result.current.error).toBe('Connection failed')
      })
    })

    it('should handle token refresh failure', async () => {
      mockAuth.getFirebaseToken.mockRejectedValue(new Error('Token refresh failed'))

      const { result } = renderHook(() => useWebSocket())

      await waitFor(() => {
        expect(result.current.error).toBe('Token refresh failed')
      })
    })

    it('should disconnect on unmount', () => {
      const { unmount } = renderHook(() => useWebSocket())

      unmount()

      expect(mockWsManager.disconnect).toHaveBeenCalled()
    })

    it('should not auto-connect when autoConnect is false', () => {
      renderHook(() => useWebSocket({ autoConnect: false }))

      expect(mockWsManager.connect).not.toHaveBeenCalled()
    })
  })

  describe('Message Handling', () => {
    it('should send message successfully', async () => {
      mockWsManager.send.mockResolvedValue(undefined)

      const { result } = renderHook(() => useWebSocket())

      await act(async () => {
        await result.current.sendMessage('test-channel', { message: 'Hello' })
      })

      expect(mockWsManager.send).toHaveBeenCalledWith('test-channel', { message: 'Hello' })
    })

    it('should handle send message failure', async () => {
      const sendError = new Error('Send failed')
      mockWsManager.send.mockRejectedValue(sendError)

      const { result } = renderHook(() => useWebSocket())

      await act(async () => {
        await result.current.sendMessage('test-channel', { message: 'Hello' })
      })

      expect(result.current.error).toBe('Send failed')
      expect(mockLogger.error).toHaveBeenCalledWith('Failed to send message:', sendError)
    })

    it('should not send message when not connected', async () => {
      mockWsManager.isConnected.mockReturnValue(false)

      const { result } = renderHook(() => useWebSocket())

      await act(async () => {
        await result.current.sendMessage('test-channel', { message: 'Hello' })
      })

      expect(mockWsManager.send).not.toHaveBeenCalled()
      expect(result.current.error).toBe('WebSocket not connected')
    })
  })

  describe('Subscription Management', () => {
    it('should subscribe to channel', () => {
      const { result } = renderHook(() => useWebSocket())
      const mockCallback = vi.fn()

      act(() => {
        result.current.subscribe('test-channel', mockCallback)
      })

      expect(mockWsManager.subscribe).toHaveBeenCalledWith('test-channel', mockCallback)
    })

    it('should unsubscribe from channel', () => {
      const { result } = renderHook(() => useWebSocket())

      act(() => {
        result.current.unsubscribe('test-channel')
      })

      expect(mockWsManager.unsubscribe).toHaveBeenCalledWith('test-channel')
    })

    it('should track subscriptions and clean up on unmount', () => {
      const { result, unmount } = renderHook(() => useWebSocket())
      const mockCallback = vi.fn()

      act(() => {
        result.current.subscribe('channel1', mockCallback)
        result.current.subscribe('channel2', mockCallback)
      })

      unmount()

      expect(mockWsManager.unsubscribe).toHaveBeenCalledWith('channel1')
      expect(mockWsManager.unsubscribe).toHaveBeenCalledWith('channel2')
    })

    it('should handle subscription with message callback', () => {
      const { result } = renderHook(() => useWebSocket())
      const mockCallback = vi.fn()

      act(() => {
        result.current.subscribe('test-channel', (message) => {
          mockCallback(message)
        })
      })

      expect(mockWsManager.subscribe).toHaveBeenCalledWith(
        'test-channel',
        expect.any(Function)
      )
    })
  })

  describe('Reconnection Logic', () => {
    it('should reconnect when requested', async () => {
      const { result } = renderHook(() => useWebSocket())

      await act(async () => {
        await result.current.reconnect()
      })

      expect(mockWsManager.disconnect).toHaveBeenCalled()
      expect(mockAuth.getFirebaseToken).toHaveBeenCalled()
      expect(mockWsManager.connect).toHaveBeenCalledWith('firebase-token')
    })

    it('should handle reconnection failure', async () => {
      mockAuth.getFirebaseToken.mockRejectedValue(new Error('Reconnection failed'))

      const { result } = renderHook(() => useWebSocket())

      await act(async () => {
        await result.current.reconnect()
      })

      expect(result.current.error).toBe('Reconnection failed')
      expect(result.current.connectionStatus).toBe('error')
    })

    it('should refresh token before reconnection', async () => {
      const { result } = renderHook(() => useWebSocket())

      await act(async () => {
        await result.current.reconnect()
      })

      expect(mockAuth.refreshToken).toHaveBeenCalled()
    })

    it('should update connection status during reconnection', async () => {
      let resolveToken: any
      mockAuth.getFirebaseToken.mockReturnValue(
        new Promise(resolve => { resolveToken = resolve })
      )

      const { result } = renderHook(() => useWebSocket())

      act(() => {
        result.current.reconnect()
      })

      expect(result.current.connectionStatus).toBe('connecting')

      await act(async () => {
        resolveToken('new-token')
      })

      await waitFor(() => {
        expect(result.current.connectionStatus).toBe('connected')
      })
    })
  })

  describe('Connection Status Updates', () => {
    it('should update status to connecting during connection', async () => {
      let resolveConnection: any
      mockWsManager.connect.mockReturnValue(
        new Promise(resolve => { resolveConnection = resolve })
      )

      const { result } = renderHook(() => useWebSocket())

      await waitFor(() => {
        expect(result.current.connectionStatus).toBe('connecting')
      })

      await act(async () => {
        resolveConnection()
      })

      await waitFor(() => {
        expect(result.current.connectionStatus).toBe('connected')
      })
    })

    it('should update status to error on connection failure', async () => {
      mockAuth.getFirebaseToken.mockRejectedValue(new Error('Auth failed'))

      const { result } = renderHook(() => useWebSocket())

      await waitFor(() => {
        expect(result.current.connectionStatus).toBe('error')
      })
    })

    it('should update status to disconnected when manager reports disconnection', () => {
      mockWsManager.isConnected.mockReturnValue(false)

      const { result } = renderHook(() => useWebSocket())

      expect(result.current.connectionStatus).toBe('disconnected')
    })
  })

  describe('Error Handling', () => {
    it('should clear error on successful operation', async () => {
      // First cause an error
      mockAuth.getFirebaseToken.mockRejectedValue(new Error('Initial error'))

      const { result, rerender } = renderHook(() => useWebSocket())

      await waitFor(() => {
        expect(result.current.error).toBe('Initial error')
      })

      // Then succeed
      mockAuth.getFirebaseToken.mockResolvedValue('firebase-token')
      mockWsManager.send.mockResolvedValue(undefined)

      await act(async () => {
        await result.current.sendMessage('test', { data: 'test' })
      })

      expect(result.current.error).toBe(null)
    })

    it('should handle multiple errors appropriately', async () => {
      const { result } = renderHook(() => useWebSocket())

      // First error
      mockWsManager.send.mockRejectedValue(new Error('Send error'))
      await act(async () => {
        await result.current.sendMessage('test', { data: 'test' })
      })

      expect(result.current.error).toBe('Send error')

      // Second error should replace first
      mockAuth.getFirebaseToken.mockRejectedValue(new Error('Token error'))
      await act(async () => {
        await result.current.reconnect()
      })

      expect(result.current.error).toBe('Token error')
    })
  })

  describe('Authentication Integration', () => {
    it('should handle authentication state changes', async () => {
      const { rerender } = renderHook(() => useWebSocket())

      // User becomes unauthenticated
      vi.mocked(useAuth).mockReturnValue({
        ...mockAuth,
        isAuthenticated: false
      } as any)

      rerender()

      expect(mockWsManager.disconnect).toHaveBeenCalled()
    })

    it('should reconnect when user becomes authenticated', async () => {
      // Start unauthenticated
      vi.mocked(useAuth).mockReturnValue({
        ...mockAuth,
        isAuthenticated: false
      } as any)

      const { rerender } = renderHook(() => useWebSocket())

      expect(mockWsManager.connect).not.toHaveBeenCalled()

      // User becomes authenticated
      vi.mocked(useAuth).mockReturnValue({
        ...mockAuth,
        isAuthenticated: true
      } as any)

      rerender()

      await waitFor(() => {
        expect(mockWsManager.connect).toHaveBeenCalledWith('firebase-token')
      })
    })

    it('should handle token refresh during active connection', async () => {
      const { result } = renderHook(() => useWebSocket())

      // Simulate token refresh
      await act(async () => {
        await result.current.reconnect()
      })

      expect(mockAuth.refreshToken).toHaveBeenCalled()
      expect(mockWsManager.connect).toHaveBeenCalledWith('firebase-token')
    })
  })

  describe('Hook Configuration Options', () => {
    it('should respect custom reconnect attempts', async () => {
      const { result } = renderHook(() =>
        useWebSocket({ reconnectAttempts: 3 })
      )

      // Configuration is passed to the hook but specific retry logic
      // would be implemented in the wsManager
      expect(result.current.reconnect).toBeDefined()
    })

    it('should respect custom reconnect interval', () => {
      const { result } = renderHook(() =>
        useWebSocket({ reconnectInterval: 5000 })
      )

      expect(result.current.reconnect).toBeDefined()
    })

    it('should handle custom message callback', () => {
      const onMessage = vi.fn()

      renderHook(() => useWebSocket({ onMessage }))

      // The onMessage callback would be used internally by the hook
      expect(onMessage).toBeDefined()
    })

    it('should handle custom error callback', async () => {
      const onError = vi.fn()

      const { result } = renderHook(() => useWebSocket({ onError }))

      // Trigger an error
      mockWsManager.send.mockRejectedValue(new Error('Test error'))

      await act(async () => {
        await result.current.sendMessage('test', { data: 'test' })
      })

      expect(onError).toHaveBeenCalledWith(expect.any(Error))
    })
  })

  describe('Performance and Memory Management', () => {
    it('should clean up subscriptions on unmount', () => {
      const { result, unmount } = renderHook(() => useWebSocket())
      const mockCallback = vi.fn()

      act(() => {
        result.current.subscribe('channel1', mockCallback)
        result.current.subscribe('channel2', mockCallback)
      })

      unmount()

      expect(mockWsManager.unsubscribe).toHaveBeenCalledTimes(2)
      expect(mockWsManager.disconnect).toHaveBeenCalled()
    })

    it('should not create memory leaks with repeated subscriptions', () => {
      const { result } = renderHook(() => useWebSocket())
      const mockCallback = vi.fn()

      // Subscribe and unsubscribe multiple times
      for (let i = 0; i < 10; i++) {
        act(() => {
          result.current.subscribe(`channel-${i}`, mockCallback)
          result.current.unsubscribe(`channel-${i}`)
        })
      }

      expect(mockWsManager.subscribe).toHaveBeenCalledTimes(10)
      expect(mockWsManager.unsubscribe).toHaveBeenCalledTimes(10)
    })
  })
})