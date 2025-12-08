import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { wsManager } from '../../lib/websocket'

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3

  public readyState = MockWebSocket.CONNECTING
  public onopen: ((event: Event) => void) | null = null
  public onclose: ((event: CloseEvent) => void) | null = null
  public onmessage: ((event: MessageEvent) => void) | null = null
  public onerror: ((event: Event) => void) | null = null

  private messageQueue: string[] = []

  constructor(public url: string) {
    // Simulate connection opening
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN
      this.onopen?.(new Event('open'))
      this.processQueue()
    }, 10)
  }

  send(data: string) {
    if (this.readyState === MockWebSocket.OPEN) {
      // In a real WebSocket, this would send to server
      console.log('WebSocket send:', data)
    } else {
      this.messageQueue.push(data)
    }
  }

  close(code?: number, reason?: string) {
    this.readyState = MockWebSocket.CLOSING
    setTimeout(() => {
      this.readyState = MockWebSocket.CLOSED
      this.onclose?.(new CloseEvent('close', { code: code || 1000, reason: reason || '' }))
    }, 10)
  }

  private processQueue() {
    while (this.messageQueue.length > 0) {
      const message = this.messageQueue.shift()!
      this.send(message)
    }
  }

  // Helper method to simulate receiving messages
  simulateMessage(data: any) {
    if (this.readyState === MockWebSocket.OPEN) {
      const event = new MessageEvent('message', {
        data: JSON.stringify(data)
      })
      this.onmessage?.(event)
    }
  }

  // Helper method to simulate connection error
  simulateError() {
    this.onerror?.(new Event('error'))
  }

  // Helper method to simulate connection close
  simulateClose(code = 1000, reason = '') {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.(new CloseEvent('close', { code, reason }))
  }
}

// Replace global WebSocket with mock
global.WebSocket = MockWebSocket as any

describe('WebSocket Manager Integration Tests', () => {
  let mockWebSocket: MockWebSocket
  const testToken = 'test-token-123'

  beforeEach(() => {
    vi.clearAllMocks()
    // Reset WebSocket manager state
    wsManager.disconnect()
  })

  afterEach(() => {
    wsManager.disconnect()
    vi.clearAllTimers()
  })

  describe('connection management', () => {
    it('should connect successfully with token', async () => {
      const connectPromise = wsManager.connect(testToken)

      // Wait for connection to complete
      await new Promise(resolve => setTimeout(resolve, 20))
      await connectPromise

      expect(wsManager.isConnected).toBe(true)
      expect(wsManager.connectionState).toBe('connected')
    })

    it('should include token in WebSocket URL', async () => {
      const originalWebSocket = global.WebSocket
      const mockConstructor = vi.fn().mockImplementation((...args) => {
        return new originalWebSocket(...args)
      })
      global.WebSocket = mockConstructor

      await wsManager.connect(testToken)
      await new Promise(resolve => setTimeout(resolve, 20))

      expect(mockConstructor).toHaveBeenCalledWith(`ws://localhost:8000/ws?token=${testToken}`)

      global.WebSocket = originalWebSocket
    })

    it('should handle connection errors', async () => {
      const originalWebSocket = global.WebSocket
      global.WebSocket = vi.fn().mockImplementation(() => {
        const mock = new originalWebSocket('ws://localhost:8000/ws')
        setTimeout(() => mock.simulateError(), 5)
        return mock
      })

      await expect(wsManager.connect(testToken)).rejects.toThrow()

      global.WebSocket = originalWebSocket
    })

    it('should disconnect properly', async () => {
      await wsManager.connect(testToken)
      await new Promise(resolve => setTimeout(resolve, 20))

      expect(wsManager.isConnected).toBe(true)

      wsManager.disconnect()

      expect(wsManager.isConnected).toBe(false)
      expect(wsManager.connectionState).toBe('closed')
    })

    it('should prevent multiple concurrent connections', async () => {
      const promise1 = wsManager.connect(testToken)
      const promise2 = wsManager.connect(testToken)

      const [result1, result2] = await Promise.all([promise1, promise2])

      // Both promises should resolve to the same connection
      expect(result1).toBe(result2)
      expect(wsManager.isConnected).toBe(true)
    })

    it('should return existing connection if already connected', async () => {
      await wsManager.connect(testToken)
      await new Promise(resolve => setTimeout(resolve, 20))

      const secondConnect = await wsManager.connect(testToken)

      expect(wsManager.isConnected).toBe(true)
      expect(secondConnect).toBeUndefined() // Returns void for existing connection
    })
  })

  describe('message handling', () => {
    beforeEach(async () => {
      await wsManager.connect(testToken)
      await new Promise(resolve => setTimeout(resolve, 20))
    })

    it('should receive and parse JSON messages', (done) => {
      const testMessage = {
        event: 'test:message',
        data: { id: 1, content: 'Hello' },
        timestamp: new Date().toISOString()
      }

      wsManager.on('test:message', (data) => {
        expect(data).toEqual({ id: 1, content: 'Hello' })
        done()
      })

      // Simulate receiving message
      const ws = (wsManager as any).ws as MockWebSocket
      ws.simulateMessage(testMessage)
    })

    it('should handle patient room events', (done) => {
      const testMessage = {
        event: 'patient:status_update',
        data: { status: 'active' },
        patient_id: 'patient-123',
        timestamp: new Date().toISOString()
      }

      wsManager.on('patient:status_update', (data) => {
        expect(data).toEqual({ status: 'active', patient_id: 'patient-123' })
        done()
      })

      const ws = (wsManager as any).ws as MockWebSocket
      ws.simulateMessage(testMessage)
    })

    it('should handle quiz events', (done) => {
      const testMessage = {
        event: 'quiz:completed',
        data: { score: 85 },
        session_id: 'session-456',
        timestamp: new Date().toISOString()
      }

      wsManager.on('quiz:completed', (data) => {
        expect(data).toEqual({ score: 85, session_id: 'session-456' })
        done()
      })

      const ws = (wsManager as any).ws as MockWebSocket
      ws.simulateMessage(testMessage)
    })

    it('should handle malformed JSON gracefully', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      const ws = (wsManager as any).ws as MockWebSocket
      const event = new MessageEvent('message', { data: 'invalid json' })
      ws.onmessage?.(event)

      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to parse WebSocket message:',
        expect.any(SyntaxError)
      )

      consoleSpy.mockRestore()
    })

    it('should handle event handler errors', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      wsManager.on('test:error', () => {
        throw new Error('Handler error')
      })

      const testMessage = {
        event: 'test:error',
        data: {},
        timestamp: new Date().toISOString()
      }

      const ws = (wsManager as any).ws as MockWebSocket
      ws.simulateMessage(testMessage)

      expect(consoleSpy).toHaveBeenCalledWith(
        'Error in WebSocket event handler for test:error:',
        expect.any(Error)
      )

      consoleSpy.mockRestore()
    })
  })

  describe('event subscription', () => {
    beforeEach(async () => {
      await wsManager.connect(testToken)
      await new Promise(resolve => setTimeout(resolve, 20))
    })

    it('should add event listeners', () => {
      const handler = vi.fn()
      const unsubscribe = wsManager.on('test:event', handler)

      expect(typeof unsubscribe).toBe('function')

      const testMessage = {
        event: 'test:event',
        data: { test: true },
        timestamp: new Date().toISOString()
      }

      const ws = (wsManager as any).ws as MockWebSocket
      ws.simulateMessage(testMessage)

      expect(handler).toHaveBeenCalledWith({ test: true })
    })

    it('should remove event listeners', () => {
      const handler = vi.fn()
      const unsubscribe = wsManager.on('test:event', handler)

      unsubscribe()

      const testMessage = {
        event: 'test:event',
        data: { test: true },
        timestamp: new Date().toISOString()
      }

      const ws = (wsManager as any).ws as MockWebSocket
      ws.simulateMessage(testMessage)

      expect(handler).not.toHaveBeenCalled()
    })

    it('should remove all listeners for an event', () => {
      const handler1 = vi.fn()
      const handler2 = vi.fn()

      wsManager.on('test:event', handler1)
      wsManager.on('test:event', handler2)

      wsManager.off('test:event')

      const testMessage = {
        event: 'test:event',
        data: { test: true },
        timestamp: new Date().toISOString()
      }

      const ws = (wsManager as any).ws as MockWebSocket
      ws.simulateMessage(testMessage)

      expect(handler1).not.toHaveBeenCalled()
      expect(handler2).not.toHaveBeenCalled()
    })

    it('should remove specific handler', () => {
      const handler1 = vi.fn()
      const handler2 = vi.fn()

      wsManager.on('test:event', handler1)
      wsManager.on('test:event', handler2)

      wsManager.off('test:event', handler1)

      const testMessage = {
        event: 'test:event',
        data: { test: true },
        timestamp: new Date().toISOString()
      }

      const ws = (wsManager as any).ws as MockWebSocket
      ws.simulateMessage(testMessage)

      expect(handler1).not.toHaveBeenCalled()
      expect(handler2).toHaveBeenCalled()
    })
  })

  describe('room management', () => {
    beforeEach(async () => {
      await wsManager.connect(testToken)
      await new Promise(resolve => setTimeout(resolve, 20))
    })

    it('should join patient room', () => {
      const sendSpy = vi.spyOn(wsManager, 'send')

      wsManager.joinPatientRoom('patient-123')

      expect(sendSpy).toHaveBeenCalledWith('join:patient', { patient_id: 'patient-123' })
    })

    it('should leave patient room', () => {
      const sendSpy = vi.spyOn(wsManager, 'send')

      wsManager.leavePatientRoom('patient-123')

      expect(sendSpy).toHaveBeenCalledWith('leave:patient', { patient_id: 'patient-123' })
    })

    it('should subscribe to quiz events', () => {
      const sendSpy = vi.spyOn(wsManager, 'send')

      wsManager.subscribeToQuizEvents('session-456')

      expect(sendSpy).toHaveBeenCalledWith('subscribe:quiz', { session_id: 'session-456' })
    })

    it('should subscribe to flow events', () => {
      const sendSpy = vi.spyOn(wsManager, 'send')

      wsManager.subscribeToFlowEvents('flow-789')

      expect(sendSpy).toHaveBeenCalledWith('subscribe:flow', { flow_id: 'flow-789' })
    })

    it('should rejoin rooms after reconnection', async () => {
      // Join some rooms
      wsManager.joinPatientRoom('patient-123')
      wsManager.subscribeToQuizEvents('session-456')

      const sendSpy = vi.spyOn(wsManager, 'send')
      sendSpy.mockClear()

      // Simulate disconnect and reconnect
      const ws = (wsManager as any).ws as MockWebSocket
      ws.simulateClose(1006, 'Connection lost') // Abnormal closure

      // Wait for reconnection attempt
      await new Promise(resolve => setTimeout(resolve, 1100)) // Wait for reconnect delay

      // Verify rooms were rejoined
      expect(sendSpy).toHaveBeenCalledWith('join:patient', { patient_id: 'patient-123' })
      expect(sendSpy).toHaveBeenCalledWith('subscribe:quiz', { session_id: 'session-456' })
    })
  })

  describe('sending messages', () => {
    beforeEach(async () => {
      await wsManager.connect(testToken)
      await new Promise(resolve => setTimeout(resolve, 20))
    })

    it('should send messages when connected', () => {
      const ws = (wsManager as any).ws as MockWebSocket
      const sendSpy = vi.spyOn(ws, 'send')

      const testData = { action: 'test', payload: { id: 1 } }
      wsManager.send('test:action', testData)

      expect(sendSpy).toHaveBeenCalledWith(
        JSON.stringify({
          event: 'test:action',
          data: testData,
          timestamp: expect.any(String)
        })
      )
    })

    it('should not send messages when disconnected', () => {
      wsManager.disconnect()

      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

      wsManager.send('test:action', { data: 'test' })

      expect(consoleSpy).toHaveBeenCalledWith(
        'WebSocket is not connected. Cannot send message:',
        'test:action',
        { data: 'test' }
      )

      consoleSpy.mockRestore()
    })
  })

  describe('reconnection logic', () => {
    it('should attempt reconnection on abnormal close', async () => {
      vi.useFakeTimers()

      await wsManager.connect(testToken)
      await new Promise(resolve => setTimeout(resolve, 20))

      const connectSpy = vi.spyOn(wsManager, 'connect')

      // Simulate connection loss
      const ws = (wsManager as any).ws as MockWebSocket
      ws.simulateClose(1006, 'Connection lost')

      // Fast-forward timers to trigger reconnection
      vi.advanceTimersByTime(1000)

      expect(connectSpy).toHaveBeenCalledWith(testToken)

      vi.useRealTimers()
    })

    it('should not reconnect on normal close', async () => {
      await wsManager.connect(testToken)
      await new Promise(resolve => setTimeout(resolve, 20))

      const connectSpy = vi.spyOn(wsManager, 'connect')

      // Simulate normal close
      const ws = (wsManager as any).ws as MockWebSocket
      ws.simulateClose(1000, 'Normal closure')

      // Wait a bit
      await new Promise(resolve => setTimeout(resolve, 1100))

      expect(connectSpy).not.toHaveBeenCalled()
    })

    it('should exponentially backoff reconnection attempts', async () => {
      vi.useFakeTimers()

      // Mock connection to always fail
      const originalWebSocket = global.WebSocket
      global.WebSocket = vi.fn().mockImplementation(() => {
        const mock = new originalWebSocket('ws://localhost:8000/ws')
        setTimeout(() => mock.simulateError(), 5)
        return mock
      })

      try {
        await wsManager.connect(testToken)
      } catch (error) {
        // Expected to fail
      }

      const reconnectAttempts = (wsManager as any).reconnectAttempts

      // Should start with 0 attempts, then increase
      expect(reconnectAttempts).toBeGreaterThan(0)

      global.WebSocket = originalWebSocket
      vi.useRealTimers()
    })

    it('should stop reconnecting after max attempts', async () => {
      vi.useFakeTimers()

      // Mock connection to always fail
      global.WebSocket = vi.fn().mockImplementation(() => {
        throw new Error('Connection failed')
      })

      const maxAttemptHandler = vi.fn()
      wsManager.on('max_reconnect_attempts', maxAttemptHandler)

      try {
        await wsManager.connect(testToken)
      } catch (error) {
        // Expected to fail
      }

      // Fast-forward through all reconnection attempts
      for (let i = 0; i < 10; i++) {
        vi.advanceTimersByTime(5000 * Math.pow(2, i))
      }

      expect(maxAttemptHandler).toHaveBeenCalled()

      // Reset WebSocket mock
      global.WebSocket = MockWebSocket as any
      vi.useRealTimers()
    })
  })

  describe('token updates', () => {
    it('should reconnect with new token', async () => {
      await wsManager.connect(testToken)
      await new Promise(resolve => setTimeout(resolve, 20))

      expect(wsManager.isConnected).toBe(true)

      const newToken = 'new-token-456'
      const connectSpy = vi.spyOn(wsManager, 'connect')

      wsManager.updateToken(newToken)

      expect(wsManager.isConnected).toBe(false) // Should disconnect first
      expect(connectSpy).toHaveBeenCalledWith(newToken)
    })

    it('should disconnect when token is set to null', async () => {
      await wsManager.connect(testToken)
      await new Promise(resolve => setTimeout(resolve, 20))

      expect(wsManager.isConnected).toBe(true)

      wsManager.updateToken(null)

      expect(wsManager.isConnected).toBe(false)
    })
  })
})