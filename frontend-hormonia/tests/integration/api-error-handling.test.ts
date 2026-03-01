/**
 * API Error Handling & Edge Cases Integration Tests
 *
 * Comprehensive tests for:
 * - HTTP status code handling (400, 401, 403, 404, 422, 429, 500, 502, 503, 504)
 * - Network errors and timeouts
 * - CSRF token validation
 * - Retry logic
 * - Rate limiting
 * - Malformed responses
 * - Type safety validation
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { apiClient, ApiError } from '@/lib/api-client'

const mockFetch = vi.fn()
global.fetch = mockFetch

describe('API Error Handling - HTTP Status Codes', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiClient.setBaseURL('http://localhost:8000')
      // Pre-set CSRF token to prevent implicit fetch in tests not testing CSRF
      ; (apiClient as any).csrfToken = 'test-csrf-token'
  })

  afterEach(() => {
    vi.clearAllTimers()
  })

  it('should handle 400 Bad Request', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({
        detail: 'Validation error',
        errors: {
          email: ['Invalid email format'],
          phone: ['Required field']
        }
      })
    })

    try {
      await apiClient.patients.create({
        name: 'Test',
        phone: '',
        doctor_id: 'doc-1'
      })
      expect.fail('Should have thrown error')
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      expect((error as ApiError).status).toBe(400)
      expect((error as ApiError).userFriendlyMessage).toContain('dados enviados')
      expect((error as ApiError).retryable).toBe(false)
    }
  })

  it('should handle 401 Unauthorized with retry disabled', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({
        detail: 'Unauthorized',
        message: 'Invalid credentials'
      })
    })

    try {
      await apiClient.auth.getCurrentUser()
      expect.fail('Should have thrown error')
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      expect((error as ApiError).status).toBe(401)
      expect((error as ApiError).userFriendlyMessage).toContain('sessão expirou')
      expect((error as ApiError).retryable).toBe(false)
    }
  })

  it('should handle 403 Forbidden', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 403,
      json: async () => ({
        detail: 'Forbidden',
        message: 'Insufficient permissions'
      })
    })

    try {
      await apiClient.adminUsers.delete('admin-1')
      expect.fail('Should have thrown error')
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      expect((error as ApiError).status).toBe(403)
      expect((error as ApiError).userFriendlyMessage).toContain('permissão')
    }
  })

  it('should handle 404 Not Found', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({
        detail: 'Not found',
        message: 'Patient not found'
      })
    })

    try {
      await apiClient.patients.get('nonexistent-id')
      expect.fail('Should have thrown error')
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      expect((error as ApiError).status).toBe(404)
      expect((error as ApiError).userFriendlyMessage).toContain('não foi encontrado')
    }
  })

  it('should handle 408 Request Timeout with retry', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 408,
      json: async () => ({
        detail: 'Request timeout',
        message: 'Request took too long'
      })
    })

    // After retry, succeed
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Map([['content-type', 'application/json']]),
      json: async () => ({ success: true })
    })

    const result = await apiClient.patients.list(1, 20)

    // Should have retried once
    expect(mockFetch).toHaveBeenCalledTimes(2)
  })

  it('should handle 422 Unprocessable Entity', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 422,
      json: async () => ({
        detail: 'Validation failed',
        errors: [
          {
            loc: ['body', 'email'],
            msg: 'Invalid email address',
            type: 'value_error.email'
          }
        ]
      })
    })

    try {
      await apiClient.patients.create({
        name: 'Test',
        email: 'invalid-email',
        phone: '+5511999999999',
        doctor_id: 'doc-1'
      })
      expect.fail('Should have thrown error')
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      expect((error as ApiError).status).toBe(422)
      expect((error as ApiError).userFriendlyMessage).toContain('processados')
    }
  })

  it('should handle 429 Rate Limit Exceeded with retry', async () => {
    vi.useFakeTimers()

    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 429,
      json: async () => ({
        detail: 'Too many requests',
        retry_after: 60
      })
    })

    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Map([['content-type', 'application/json']]),
      json: async () => ({ items: [], total: 0 })
    })

    const promise = apiClient.patients.list()

    // Fast forward through retry delay
    await vi.advanceTimersByTimeAsync(1000)

    const result = await promise

    expect(mockFetch).toHaveBeenCalledTimes(2)
    expect(result.items).toBeDefined()

    vi.useRealTimers()
  })

  it('should handle 500 Internal Server Error with retry', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({
          detail: 'Internal server error'
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({ items: [], total: 0 })
      })

    const result = await apiClient.patients.list()

    // Should have retried
    expect(mockFetch).toHaveBeenCalledTimes(2)
    expect(result.items).toBeDefined()
  })

  it('should handle 502 Bad Gateway with retry', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: false,
        status: 502,
        statusText: 'Bad Gateway',
        json: async () => { throw new Error('No JSON') }
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({ items: [], total: 0 })
      })

    const result = await apiClient.patients.list()

    expect(mockFetch).toHaveBeenCalledTimes(2)
  })

  it('should handle 503 Service Unavailable with retry', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: false,
        status: 503,
        json: async () => ({
          detail: 'Service unavailable',
          message: 'Server is down for maintenance'
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({ items: [], total: 0 })
      })

    const result = await apiClient.patients.list()

    expect(mockFetch).toHaveBeenCalledTimes(2)
  })

  it('should handle 504 Gateway Timeout with retry', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: false,
        status: 504,
        json: async () => ({
          detail: 'Gateway timeout'
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({ items: [], total: 0 })
      })

    const result = await apiClient.patients.list()

    expect(mockFetch).toHaveBeenCalledTimes(2)
  })

  it('should stop retrying after max retries', async () => {
    vi.useFakeTimers()

    // Fail 4 times (initial + 3 retries)
    for (let i = 0; i < 4; i++) {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'Server error' })
      })
    }

    try {
      const promise = apiClient.patients.list()

      // Fast forward through all retry delays
      for (let i = 0; i < 3; i++) {
        await vi.advanceTimersByTimeAsync(Math.pow(2, i) * 1000)
      }

      await promise
      expect.fail('Should have thrown error')
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      expect((error as ApiError).status).toBe(500)
      // Should have tried 4 times total (1 initial + 3 retries)
      expect(mockFetch).toHaveBeenCalledTimes(4)
    } finally {
      vi.useRealTimers()
    }
  })
})

describe('API Error Handling - Network & Timeout', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should handle network errors', async () => {
    mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'))

    try {
      await apiClient.patients.list()
      expect.fail('Should have thrown error')
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      expect((error as ApiError).status).toBe(0)
      expect((error as ApiError).userFriendlyMessage).toContain('conectar ao servidor')
      expect((error as ApiError).retryable).toBe(true)
    }
  })

  it('should handle DNS resolution failures', async () => {
    mockFetch.mockRejectedValueOnce(new TypeError('Network request failed'))

    try {
      await apiClient.auth.getSession()
      expect.fail('Should have thrown error')
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      expect((error as ApiError).status).toBe(0)
    }
  })

  it('should handle connection refused', async () => {
    mockFetch.mockRejectedValueOnce(new TypeError('Connection refused'))

    try {
      await apiClient.patients.get('patient-1')
      expect.fail('Should have thrown error')
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      expect((error as ApiError).userFriendlyMessage).toContain('conexão')
    }
  })

  it('should handle request timeout', async () => {
    vi.useFakeTimers()

    mockFetch.mockImplementationOnce(() =>
      new Promise(resolve => setTimeout(() => resolve({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({})
      }), 35000)) // Timeout after 30s
    )

    try {
      const promise = apiClient.patients.list()

      // Advance to timeout (30s)
      await vi.advanceTimersByTimeAsync(30000)

      await promise
      expect.fail('Should have thrown timeout error')
    } catch (error) {
      expect(error).toBeInstanceOf(Error)
    } finally {
      vi.useRealTimers()
    }
  })

  it('should retry network errors with backoff', async () => {
    vi.useFakeTimers()

    mockFetch
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({ items: [], total: 0 })
      })

    const promise = apiClient.patients.list()

    // Fast forward through retry delay
    await vi.advanceTimersByTimeAsync(1000)

    const result = await promise

    expect(mockFetch).toHaveBeenCalledTimes(2)
    expect(result.items).toBeDefined()

    vi.useRealTimers()
  })
})

describe('API Error Handling - Response Parsing', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should handle malformed JSON responses', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: async () => { throw new SyntaxError('Unexpected token') }
    })

    try {
      await apiClient.patients.list()
      expect.fail('Should have thrown error')
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      expect((error as ApiError).status).toBe(500)
      expect((error as ApiError).data.message).toContain('HTTP 500')
    }
  })

  it('should handle empty response bodies', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 204,
      headers: new Map([['content-length', '0']]),
      json: async () => null
    })

    const result = await apiClient.patients.delete('patient-1')

    expect(result).toBeUndefined()
  })

  it('should handle non-JSON responses', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Map([['content-type', 'text/html']]),
      text: async () => '<html>Error page</html>',
      json: async () => { throw new Error('Not JSON') }
    })

    const result = await apiClient.patients.list()

    // Should still process response gracefully
    expect(result).toBeDefined()
  })

  it('should handle responses with missing fields', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Map([['content-type', 'application/json']]),
      json: async () => ({
        // Missing 'items' and 'total' fields
        data: []
      })
    })

    const result = await apiClient.patients.list()

    // Should normalize response
    expect(result.items).toBeDefined()
    expect(Array.isArray(result.items)).toBe(true)
  })
})

describe('API Error Handling - CSRF Protection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should include CSRF token in state-changing requests', async () => {
    // Mock CSRF token fetch
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Map([['content-type', 'application/json']]),
      json: async () => ({ csrf_token: 'test-csrf-token' })
    })

    await apiClient.fetchCsrfToken()

    // Mock POST request
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      headers: new Map([['content-type', 'application/json']]),
      json: async () => ({ id: 'patient-1' })
    })

    await apiClient.patients.create({
      name: 'Test',
      phone: '+5511999999999',
      doctor_id: 'doc-1'
    })

    // Check that CSRF token was included
    expect(mockFetch).toHaveBeenLastCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({
          'X-CSRF-Token': 'test-csrf-token'
        })
      })
    )
  })

  it('should handle CSRF token fetch failure gracefully', async () => {
    mockFetch.mockRejectedValueOnce(new TypeError('Network error'))

    // Should not throw - CSRF fetch is non-blocking
    await apiClient.fetchCsrfToken()

    // Subsequent requests should still work
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Map([['content-type', 'application/json']]),
      json: async () => ({ items: [], total: 0 })
    })

    const result = await apiClient.patients.list()
    expect(result).toBeDefined()
  })
})

describe('API Error Handling - Type Safety', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should handle type mismatches in patient data', async () => {
    const invalidPatient = {
      id: 'patient-1',
      name: 'Test',
      // status is invalid type
      status: 'invalid-status' as any,
      email: 'test@example.com'
    }

    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Map([['content-type', 'application/json']]),
      json: async () => invalidPatient
    })

    const result = await apiClient.patients.get('patient-1')

    // Should normalize status
    expect(result.status).toBeDefined()
  })

  it('should handle null values in optional fields', async () => {
    const patientWithNulls = {
      id: 'patient-1',
      name: 'Test',
      email: null,
      phone: null,
      status: 'active'
    }

    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Map([['content-type', 'application/json']]),
      json: async () => patientWithNulls
    })

    const result = await apiClient.patients.get('patient-1')

    expect(result.id).toBe('patient-1')
    expect(result.name).toBe('Test')
  })

  it('should handle unexpected extra fields in responses', async () => {
    const patientWithExtra = {
      id: 'patient-1',
      name: 'Test',
      status: 'active',
      unexpected_field: 'value',
      another_field: 123
    }

    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Map([['content-type', 'application/json']]),
      json: async () => patientWithExtra
    })

    const result = await apiClient.patients.get('patient-1')

    // Should include expected fields
    expect(result.id).toBe('patient-1')
    expect(result.name).toBe('Test')
  })
})

describe('API Error Handling - Authentication Flow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should clear auth token on logout', async () => {
    apiClient.setAuthToken('test-token')

    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Map([['content-type', 'application/json']]),
      json: async () => ({
        success: true,
        sessions_deleted: 1,
        message: 'Logged out'
      })
    })

    await apiClient.auth.logout()

    expect(apiClient.getAuthToken()).toBeNull()
  })

  it('should handle invalid session gracefully', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Map([['content-type', 'application/json']]),
      json: async () => ({
        valid: false,
        user: null
      })
    })

    const authStatus = await apiClient.auth.checkAuth()

    expect(authStatus.authenticated).toBe(false)
    expect(authStatus.user).toBeUndefined()
  })
})
