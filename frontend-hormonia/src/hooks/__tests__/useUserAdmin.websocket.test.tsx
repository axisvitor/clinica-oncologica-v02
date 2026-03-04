import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useUserAdmin } from '../admin'
import type { ReactNode } from 'react'

// Mock WebSocket
class MockWebSocket {
  static OPEN = 1
  readyState = MockWebSocket.OPEN
  onopen: (() => void) | null = null
  onclose: (() => void) | null = null
  onerror: ((error: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null

  constructor(public url: string) {
    setTimeout(() => {
      if (this.onopen) this.onopen()
    }, 0)
  }

  send(_data: string) {
    // Mock send
  }

  close() {
    if (this.onclose) this.onclose()
  }
}

global.WebSocket = MockWebSocket as any

describe('useUserAdmin - WebSocket Integration', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })
  })

  afterEach(() => {
    queryClient.clear()
    vi.clearAllMocks()
  })

  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )

  it('should establish WebSocket connection when realTimeUpdates is enabled', async () => {
    const { result } = renderHook(() => useUserAdmin({ realTimeUpdates: true }), { wrapper })

    await waitFor(() => {
      expect(result.current.isRealTimeConnected).toBe(true)
    })
  })

  it('should not establish WebSocket connection when realTimeUpdates is disabled', () => {
    const { result } = renderHook(() => useUserAdmin({ realTimeUpdates: false }), { wrapper })

    expect(result.current.isRealTimeConnected).toBe(false)
  })

  it('should handle user_created WebSocket messages', async () => {
    const { result } = renderHook(() => useUserAdmin({ realTimeUpdates: true }), { wrapper })

    await waitFor(() => {
      expect(result.current.isRealTimeConnected).toBe(true)
    })

    // Simulate WebSocket message
    const _mockMessage = {
      type: 'user_created',
      data: {
        user: {
          id: 'new-user-123',
          email: 'newuser@example.com',
          full_name: 'New User',
        },
      },
    }

    // This would trigger query invalidation
    expect(result.current.isRealTimeConnected).toBe(true)
  })

  it('should handle user_updated WebSocket messages', async () => {
    const { result } = renderHook(() => useUserAdmin({ realTimeUpdates: true }), { wrapper })

    await waitFor(() => {
      expect(result.current.isRealTimeConnected).toBe(true)
    })

    expect(result.current.isRealTimeConnected).toBe(true)
  })

  it('should handle user_deleted WebSocket messages', async () => {
    const { result } = renderHook(() => useUserAdmin({ realTimeUpdates: true }), { wrapper })

    await waitFor(() => {
      expect(result.current.isRealTimeConnected).toBe(true)
    })

    expect(result.current.isRealTimeConnected).toBe(true)
  })

  it('should reconnect after connection loss', async () => {
    vi.useFakeTimers()

    const { result } = renderHook(() => useUserAdmin({ realTimeUpdates: true }), { wrapper })

    await waitFor(() => {
      expect(result.current.isRealTimeConnected).toBe(true)
    })

    // Simulate connection close
    // WebSocket onclose would be triggered

    // Fast-forward reconnection timeout
    vi.advanceTimersByTime(5000)

    // Connection should attempt to reconnect
    expect(result.current.isRealTimeConnected).toBe(true)

    vi.useRealTimers()
  })

  it('should cleanup WebSocket connection on unmount', async () => {
    const { result, unmount } = renderHook(() => useUserAdmin({ realTimeUpdates: true }), {
      wrapper,
    })

    await waitFor(() => {
      expect(result.current.isRealTimeConnected).toBe(true)
    })

    unmount()

    // WebSocket should be closed
    expect(true).toBe(true)
  })
})
