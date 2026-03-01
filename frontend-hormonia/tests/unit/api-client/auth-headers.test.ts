import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ApiClientCore } from '@/lib/api-client/core'

const createMockFetch = () =>
  vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    headers: new Headers({ 'Content-Length': '0' }),
    json: vi.fn()
  })

describe('API Client - Auth Headers Configuration', () => {
  let originalFetch: typeof global.fetch

  beforeEach(() => {
    originalFetch = global.fetch
  })

  afterEach(() => {
    global.fetch = originalFetch
    vi.restoreAllMocks()
  })

  it('setAuthToken configura ambos headers (Authorization + X-Session-ID)', async () => {
    const mockFetch = createMockFetch()
    global.fetch = mockFetch

    const client = new ApiClientCore('http://test.local')
    client.setAuthToken('session-token')

    await client.request('/api/v2/test')

    const headers = mockFetch.mock.calls[0]?.[1]?.headers as Record<string, string>
    expect(headers).toMatchObject({
      Authorization: 'Bearer session-token',
      'X-Session-ID': 'session-token'
    })
  })

  it('setAuthToken(null) remove ambos headers', async () => {
    const mockFetch = createMockFetch()
    global.fetch = mockFetch

    const client = new ApiClientCore('http://test.local')
    client.setAuthToken('session-token')
    client.setAuthToken(null)

    await client.request('/api/v2/test')

    const headers = mockFetch.mock.calls[0]?.[1]?.headers as Record<string, string>
    expect(headers.Authorization).toBeUndefined()
    expect(headers['X-Session-ID']).toBeUndefined()
  })

  it('clearAuthToken remove ambos headers', async () => {
    const mockFetch = createMockFetch()
    global.fetch = mockFetch

    const client = new ApiClientCore('http://test.local')
    client.setAuthToken('session-token')
    client.clearAuthToken()

    await client.request('/api/v2/test')

    const headers = mockFetch.mock.calls[0]?.[1]?.headers as Record<string, string>
    expect(headers.Authorization).toBeUndefined()
    expect(headers['X-Session-ID']).toBeUndefined()
  })
})

describe('API Client - Request Headers', () => {
  let originalFetch: typeof global.fetch

  beforeEach(() => {
    originalFetch = global.fetch
  })

  afterEach(() => {
    global.fetch = originalFetch
    vi.restoreAllMocks()
  })

  it('request() envia ambos headers quando token configurado', async () => {
    const mockFetch = createMockFetch()
    global.fetch = mockFetch

    const client = new ApiClientCore('http://test.local')
    client.setAuthToken('session-token')

    await client.request('/api/v2/test')

    const headers = mockFetch.mock.calls[0]?.[1]?.headers as Record<string, string>
    expect(headers.Authorization).toBe('Bearer session-token')
    expect(headers['X-Session-ID']).toBe('session-token')
  })

  it('request() nao envia headers quando token nao configurado', async () => {
    const mockFetch = createMockFetch()
    global.fetch = mockFetch

    const client = new ApiClientCore('http://test.local')

    await client.request('/api/v2/test')

    const headers = mockFetch.mock.calls[0]?.[1]?.headers as Record<string, string>
    expect(headers.Authorization).toBeUndefined()
    expect(headers['X-Session-ID']).toBeUndefined()
  })

  it('Headers individuais sobrescrevem defaults', async () => {
    const mockFetch = createMockFetch()
    global.fetch = mockFetch

    const client = new ApiClientCore('http://test.local')
    client.setAuthToken('session-token')

    await client.request('/api/v2/test', {
      headers: {
        Authorization: 'Bearer override-token',
        'X-Session-ID': 'override-session'
      }
    })

    const headers = mockFetch.mock.calls[0]?.[1]?.headers as Record<string, string>
    expect(headers.Authorization).toBe('Bearer override-token')
    expect(headers['X-Session-ID']).toBe('override-session')
  })
})

describe('API Client - Integration with Auth Flow', () => {
  let originalFetch: typeof global.fetch

  beforeEach(() => {
    originalFetch = global.fetch
  })

  afterEach(() => {
    global.fetch = originalFetch
    vi.restoreAllMocks()
  })

  it('Login configura headers corretamente', async () => {
    const mockFetch = createMockFetch()
    global.fetch = mockFetch

    const client = new ApiClientCore('http://test.local')
    client.setAuthToken('login-session')

    await client.request('/api/v2/me')

    const headers = mockFetch.mock.calls[0]?.[1]?.headers as Record<string, string>
    expect(headers.Authorization).toBe('Bearer login-session')
    expect(headers['X-Session-ID']).toBe('login-session')
  })

  it('Logout limpa headers corretamente', async () => {
    const mockFetch = createMockFetch()
    global.fetch = mockFetch

    const client = new ApiClientCore('http://test.local')
    client.setAuthToken('login-session')
    client.clearAuthToken()

    await client.request('/api/v2/me')

    const headers = mockFetch.mock.calls[0]?.[1]?.headers as Record<string, string>
    expect(headers.Authorization).toBeUndefined()
    expect(headers['X-Session-ID']).toBeUndefined()
  })

  it('Session restore configura headers via cookie validation', async () => {
    const mockFetch = createMockFetch()
    global.fetch = mockFetch

    const client = new ApiClientCore('http://test.local')
    client.setAuthToken('restored-session')

    await client.request('/api/v2/session/validate')

    const headers = mockFetch.mock.calls[0]?.[1]?.headers as Record<string, string>
    expect(headers.Authorization).toBe('Bearer restored-session')
    expect(headers['X-Session-ID']).toBe('restored-session')
  })
})
