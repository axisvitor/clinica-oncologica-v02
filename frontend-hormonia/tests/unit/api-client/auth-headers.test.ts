import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ApiClientCore } from '@/lib/api-client/core'

const createMockFetch = () =>
  vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    headers: new Headers({ 'Content-Length': '0' }),
    json: vi.fn(),
  })

const getRequestOptions = (mockFetch: ReturnType<typeof createMockFetch>) =>
  (mockFetch.mock.calls[0]?.[1] ?? {}) as RequestInit & { headers?: Record<string, string> }

const getRequestHeaders = (mockFetch: ReturnType<typeof createMockFetch>) =>
  (getRequestOptions(mockFetch).headers ?? {}) as Record<string, string>

describe('ApiClientCore session-first header proof', () => {
  let originalFetch: typeof global.fetch

  beforeEach(() => {
    originalFetch = global.fetch
  })

  afterEach(() => {
    global.fetch = originalFetch
    vi.restoreAllMocks()
  })

  it('keeps shared requests cookie-backed even when a legacy auth token is configured', async () => {
    const mockFetch = createMockFetch()
    global.fetch = mockFetch

    const client = new ApiClientCore('http://test.local')
    client.setAuthToken('legacy-session-token')

    await client.request('/api/v2/test')

    const requestOptions = getRequestOptions(mockFetch)
    const headers = getRequestHeaders(mockFetch)

    expect(requestOptions.credentials).toBe('include')
    expect(headers.Authorization).toBeUndefined()
    expect(headers['X-Session-ID']).toBeUndefined()
  })

  it('clearAuthToken leaves the shared request path free of legacy session headers', async () => {
    const mockFetch = createMockFetch()
    global.fetch = mockFetch

    const client = new ApiClientCore('http://test.local')
    client.setAuthToken('legacy-session-token')
    client.clearAuthToken()

    await client.request('/api/v2/test')

    const headers = getRequestHeaders(mockFetch)

    expect(headers.Authorization).toBeUndefined()
    expect(headers['X-Session-ID']).toBeUndefined()
  })

  it('does not reintroduce Authorization or X-Session-ID after login/restore token churn', async () => {
    const mockFetch = createMockFetch()
    global.fetch = mockFetch

    const client = new ApiClientCore('http://test.local')
    client.setAuthToken('login-session-token')
    client.clearAuthToken()
    client.setAuthToken('restore-session-token')

    await client.request('/api/v2/test')

    const headers = getRequestHeaders(mockFetch)

    expect(headers.Authorization).toBeUndefined()
    expect(headers['X-Session-ID']).toBeUndefined()
  })
})
