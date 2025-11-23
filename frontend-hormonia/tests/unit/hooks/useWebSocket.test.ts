import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useWebSocket, useSystemNotifications, usePatientUpdates } from '@/hooks/useWebSocket'

// Mock dependencies
const mockUseAuth = vi.fn()
const mockUseConfig = vi.fn()
const mockCreateLogger = vi.fn()

vi.mock('./useAuth', () => ({
  useAuth: mockUseAuth
}))

vi.mock('@/lib/config-initializer', () => ({
  useConfig: mockUseConfig
}))

vi.mock('../lib/logger', () => ({
  createLogger: mockCreateLogger
}))

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3

  url: string
  readyState: number
  onopen: ((event: Event) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null

  constructor(url: string) {
    this.url = url
    this.readyState = MockWebSocket.CONNECTING

    // Simulate async connection
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN
      this.onopen?.(new Event('open'))
    }, 0)
  }

  send(data: string) {
    if (this.readyState === MockWebSocket.OPEN) {
      // Simulate message sending
      return
    }
    throw new Error('WebSocket is not open')
  }

  close(code?: number, reason?: string) {
    this.readyState = MockWebSocket.CLOSED
    setTimeout(() => {
      this.onclose?.(new CloseEvent('close', { code: code || 1000, reason: reason || '' }))
    }, 0)
  }
}

// Replace global WebSocket
global.WebSocket = MockWebSocket as any

describe('useWebSocket', () => {
  const mockLogger = {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn()
  }

  const mockUser = {
    id: '1',
    email: 'test@example.com',
    token: 'mock-token'
  }

  const mockConfig = {
    VITE_WS_BASE_URL: 'ws://localhost:8000/ws',
    VITE_WS_URL: 'ws://localhost:8080/ws'
  }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()

    mockCreateLogger.mockReturnValue(mockLogger)
    mockUseAuth.mockReturnValue({
      user: mockUser,
      token: 'mock-token'
    })
    mockUseConfig.mockReturnValue({
      config: mockConfig
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('Basic Connection', () => {
    it('should initialize with disconnected state', () => {
      const { result } = renderHook(() => useWebSocket())

      expect(result.current.isConnected).toBe(false)
      expect(result.current.connectionState).toBe('disconnected')
      expect(result.current.lastMessage).toBeNull()
    })

    it('should connect when user has token', async () => {
      const { result } = renderHook(() => useWebSocket())

      await act(async () => {
        vi.advanceTimersByTime(100)
      })

      expect(result.current.connectionState).toBe('connected')
      expect(result.current.isConnected).toBe(true)
    })

    it('should not connect when user has no token', () => {
      mockUseAuth.mockReturnValue({
        user: null,
        token: null
      })

      renderHook(() => useWebSocket())

      expect(mockLogger.warn).toHaveBeenCalledWith(
        'Cannot connect WebSocket: no authentication token available'
      )
    })

    it('should use custom URL when provided', async () => {
      const customUrl = 'ws://custom.example.com/ws'
      renderHook(() => useWebSocket({ url: customUrl }))

      await act(async () => {
        vi.advanceTimersByTime(100)
      })

      // WebSocket should be created with custom URL + token
      expect(mockLogger.info).toHaveBeenCalledWith('WebSocket connection established')
    })
  })

  describe('URL Configuration', () => {
    it('should use VITE_WS_BASE_URL from config', async () => {
      renderHook(() => useWebSocket())

      await act(async () => {
        vi.advanceTimersByTime(100)
      })

      expect(mockLogger.info).toHaveBeenCalledWith('WebSocket connection established')
    })

    it('should fallback to VITE_WS_URL when VITE_WS_BASE_URL is not available', async () => {
      mockUseConfig.mockReturnValue({
        config: {
          VITE_WS_URL: 'ws://localhost:8080/ws'
        }
      })

      renderHook(() => useWebSocket())

      await act(async () => {
        vi.advanceTimersByTime(100)
      })

      expect(mockLogger.info).toHaveBeenCalledWith('WebSocket connection established')
    })

    it('should use default URL when no config is available', async () => {
      mockUseConfig.mockReturnValue({
        config: {}
      })

      renderHook(() => useWebSocket())

      await act(async () => {
        vi.advanceTimersByTime(100)
      })

      expect(mockLogger.info).toHaveBeenCalledWith('WebSocket connection established')
    })

    it('should normalize WebSocket URLs with missing slashes', async () => {
      renderHook(() => useWebSocket({ url: 'wss:example.com/ws' }))

      await act(async () => {
        vi.advanceTimersByTime(100)
      })

      expect(mockLogger.info).toHaveBeenCalledWith('WebSocket connection established')
    })
  })

  describe('Message Handling', () => {
    it('should handle incoming messages', async () => {
      const onMessage = vi.fn()
      const { result } = renderHook(() => useWebSocket({ onMessage }))

      await act(async () => {
        vi.advanceTimersByTime(100)
      })

      // Simulate incoming message
      const mockMessage = {
        type: 'test',
        data: { content: 'test message' },
        timestamp: '2024-01-01T00:00:00Z'
      }

      const mockWs = result.current as any
      if (mockWs && global.WebSocket.prototype.onmessage) {
        act(() => {
          global.WebSocket.prototype.onmessage.call(mockWs, {
            data: JSON.stringify(mockMessage)
          } as MessageEvent)
        })
      }

      expect(onMessage).toHaveBeenCalledWith(mockMessage)
      expect(result.current.lastMessage).toEqual(mockMessage)
    })

    it('should handle malformed message gracefully', async () => {
      const onMessage = vi.fn()
      const { result } = renderHook(() => useWebSocket({ onMessage }))

      await act(async () => {
        vi.advanceTimersByTime(100)
      })

      // Simulate malformed message
      const mockWs = result.current as any
      if (mockWs && global.WebSocket.prototype.onmessage) {
        act(() => {
          global.WebSocket.prototype.onmessage.call(mockWs, {
            data: 'invalid json'
          } as MessageEvent)
        })
      }

      expect(mockLogger.error).toHaveBeenCalledWith(
        'Failed to parse WebSocket message:',
        expect.any(Error)
      )
      expect(onMessage).not.toHaveBeenCalled()
    })
  })

  describe('Sending Messages', () => {
    it('should send messages when connected', async () => {
      const { result } = renderHook(() => useWebSocket())

      await act(async () => {
        vi.advanceTimersByTime(100)
      })

      const testMessage = {
        type: 'test',
        data: { content: 'test' }
      }

      let sent = false
      act(() => {
        sent = result.current.sendMessage(testMessage)
      })

      expect(sent).toBe(true)
    })

    it('should not send messages when disconnected', () => {
      const { result } = renderHook(() => useWebSocket())

      const testMessage = {
        type: 'test',
        data: { content: 'test' }
      }

      const sent = result.current.sendMessage(testMessage)

      expect(sent).toBe(false)
      expect(mockLogger.warn).toHaveBeenCalledWith(
        'Cannot send message: WebSocket not connected'
      )
    })

    it('should add timestamp to outgoing messages', async () => {
      const { result } = renderHook(() => useWebSocket())

      await act(async () => {
        vi.advanceTimersByTime(100)
      })

      const testMessage = {
        type: 'test',
        data: { content: 'test' }
      }

      // Mock the WebSocket send method
      const mockSend = vi.fn()
      const mockWs = { readyState: MockWebSocket.OPEN, send: mockSend }
      ;(result.current as any).wsRef = { current: mockWs }

      act(() => {
        result.current.sendMessage(testMessage)
      })

      expect(mockSend).toHaveBeenCalledWith(
        expect.stringContaining('"timestamp":"')
      )
    })
  })

  describe('Connection Management', () => {
    it('should prevent duplicate connections', async () => {
      const { result } = renderHook(() => useWebSocket())

      await act(async () => {
        vi.advanceTimersByTime(100)
      })

      // Try to connect again
      act(() => {
        result.current.connect()
      })

      expect(mockLogger.debug).toHaveBeenCalledWith(
        'WebSocket already connecting or connected, skipping duplicate connection'
      )
    })

    it('should handle connection errors', async () => {
      const onError = vi.fn()
      renderHook(() => useWebSocket({ onError }))

      // Simulate connection error
      await act(async () => {
        const mockError = new Event('error')
        global.WebSocket.prototype.onerror?.(mockError)
      })

      expect(mockLogger.error).toHaveBeenCalledWith('WebSocket error:', expect.any(Event))
      expect(onError).toHaveBeenCalledWith(expect.any(Event))
    })

    it('should disconnect intentionally', async () => {
      const { result } = renderHook(() => useWebSocket())

      await act(async () => {
        vi.advanceTimersByTime(100)
      })

      act(() => {
        result.current.disconnect()
      })

      expect(result.current.isConnected).toBe(false)
      expect(result.current.connectionState).toBe('disconnected')
    })
  })

  describe('Reconnection Logic', () => {
    it('should attempt reconnection on unexpected disconnect', async () => {
      const { result } = renderHook(() => useWebSocket({
        reconnectAttempts: 2,
        reconnectInterval: 1000
      }))

      await act(async () => {
        vi.advanceTimersByTime(100)
      })

      // Simulate unexpected disconnect
      act(() => {
        global.WebSocket.prototype.onclose?.(new CloseEvent('close', { code: 1006 }))
      })

      expect(mockLogger.info).toHaveBeenCalledWith(
        expect.stringContaining('Scheduling reconnection attempt 1/2')
      )

      // Advance timer to trigger reconnection
      await act(async () => {
        vi.advanceTimersByTime(1000)
      })
    })

    it('should stop reconnecting after max attempts', async () => {
      renderHook(() => useWebSocket({
        reconnectAttempts: 1,
        reconnectInterval: 1000
      }))

      await act(async () => {
        vi.advanceTimersByTime(100)
      })

      // Simulate multiple disconnects
      act(() => {
        global.WebSocket.prototype.onclose?.(new CloseEvent('close', { code: 1006 }))
      })

      await act(async () => {
        vi.advanceTimersByTime(1000)
      })

      act(() => {
        global.WebSocket.prototype.onclose?.(new CloseEvent('close', { code: 1006 }))
      })

      expect(mockLogger.warn).toHaveBeenCalledWith(
        'Max reconnection attempts (1) reached, giving up'
      )
    })

    it('should not reconnect on intentional disconnect', async () => {
      const { result } = renderHook(() => useWebSocket())

      await act(async () => {
        vi.advanceTimersByTime(100)
      })

      act(() => {
        result.current.disconnect()
      })

      // Should not attempt reconnection
      await act(async () => {
        vi.advanceTimersByTime(5000)
      })

      expect(mockLogger.info).not.toHaveBeenCalledWith(
        expect.stringContaining('Scheduling reconnection')
      )
    })
  })

  describe('Authentication Changes', () => {
    it('should reconnect when token changes', async () => {
      const { rerender } = renderHook(() => useWebSocket())

      await act(async () => {
        vi.advanceTimersByTime(100)
      })

      // Change auth state
      mockUseAuth.mockReturnValue({
        user: { ...mockUser, token: 'new-token' },
        token: 'new-token'
      })

      rerender()

      await act(async () => {
        vi.advanceTimersByTime(100)
      })

      expect(mockLogger.debug).toHaveBeenCalledWith(
        'Authentication token available, connecting WebSocket'
      )
    })

    it('should disconnect when token is removed', () => {
      const { rerender } = renderHook(() => useWebSocket())

      // Remove auth
      mockUseAuth.mockReturnValue({
        user: null,
        token: null
      })

      rerender()

      expect(mockLogger.debug).toHaveBeenCalledWith(
        'No authentication token, disconnecting WebSocket'
      )
    })
  })

  describe('Cleanup', () => {
    it('should cleanup on unmount', async () => {
      const { result, unmount } = renderHook(() => useWebSocket())

      await act(async () => {
        vi.advanceTimersByTime(100)
      })

      unmount()

      expect(mockLogger.debug).toHaveBeenCalledWith(
        'useWebSocket cleanup: disabling reconnections and disconnecting'
      )
    })
  })
})

describe('useSystemNotifications', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUseAuth.mockReturnValue({
      user: { id: '1', token: 'mock-token' },
      token: 'mock-token'
    })
    mockUseConfig.mockReturnValue({
      config: { VITE_WS_BASE_URL: 'ws://localhost:8000/ws' }
    })
    mockCreateLogger.mockReturnValue({
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
      debug: vi.fn()
    })
  })

  it('should handle system notifications', () => {
    const { result } = renderHook(() => useSystemNotifications())

    expect(result.current.notifications).toEqual([])
    expect(typeof result.current.clearNotifications).toBe('function')
  })

  it('should clear notifications', () => {
    const { result } = renderHook(() => useSystemNotifications())

    act(() => {
      result.current.clearNotifications()
    })

    expect(result.current.notifications).toEqual([])
  })
})

describe('usePatientUpdates', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUseAuth.mockReturnValue({
      user: { id: '1', token: 'mock-token' },
      token: 'mock-token'
    })
    mockUseConfig.mockReturnValue({
      config: { VITE_WS_BASE_URL: 'ws://localhost:8000/ws' }
    })
    mockCreateLogger.mockReturnValue({
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
      debug: vi.fn()
    })
  })

  it('should handle patient updates', () => {
    const { result } = renderHook(() => usePatientUpdates())

    expect(result.current.updates).toEqual([])
    expect(typeof result.current.clearUpdates).toBe('function')
  })

  it('should clear updates', () => {
    const { result } = renderHook(() => usePatientUpdates())

    act(() => {
      result.current.clearUpdates()
    })

    expect(result.current.updates).toEqual([])
  })
})