import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import { apiClient, ApiError } from '@/lib/api-client'

vi.mock('@/config', () => ({
  getApiUrl: () => 'http://localhost:8000',
}))

const mockFetch = vi.fn()
global.fetch = mockFetch

const setBaseUrl = () => {
  apiClient.setBaseURL('http://localhost:8000')
}

const seedCsrfToken = () => {
  ;(apiClient as unknown as { csrfToken: string | null }).csrfToken = 'csrf-test-token'
}

const jsonResponse = (
  data: unknown,
  init: {
    ok?: boolean
    status?: number
    statusText?: string
    headers?: Headers
  } = {}
) => ({
  ok: init.ok ?? true,
  status: init.status ?? 200,
  statusText: init.statusText ?? 'OK',
  headers:
    init.headers ?? new Headers({ 'content-type': 'application/json', 'content-length': '1' }),
  json: vi.fn().mockResolvedValue(data),
})

describe('ApiClient Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiClient.setAuthToken(null)
    setBaseUrl()
    seedCsrfToken()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('request method', () => {
    it('should make successful GET request', async () => {
      const mockData = { id: 1, name: 'Test' }
      mockFetch.mockResolvedValueOnce(jsonResponse(mockData))

      const result = await apiClient.request('/test')

      expect(mockFetch).toHaveBeenCalledTimes(1)
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8000/test', expect.any(Object))

      const [, requestOptions] = mockFetch.mock.calls[0] as [string, RequestInit & {
        headers: Record<string, string>
      }]

      expect(requestOptions.credentials).toBe('include')
      expect(requestOptions.headers['Content-Type']).toBe('application/json')
      expect(requestOptions.signal).toBeInstanceOf(AbortSignal)
      expect(result).toEqual(mockData)
    })

    it('should make successful POST request with body', async () => {
      const mockData = { id: 1, name: 'Test' }
      const postData = { name: 'New Test' }
      mockFetch.mockResolvedValueOnce(jsonResponse(mockData, { status: 201 }))

      const result = await apiClient.request('/test', {
        method: 'POST',
        body: JSON.stringify(postData),
      })

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/test',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(postData),
          credentials: 'include',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
            'X-CSRF-Token': 'csrf-test-token',
          }),
        })
      )
      expect(result).toEqual(mockData)
    })

    it('should include auth token when set', async () => {
      const token = 'test-token'
      apiClient.setAuthToken(token)
      mockFetch.mockResolvedValueOnce(jsonResponse({}))

      await apiClient.request('/test')

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: `Bearer ${token}`,
            'X-Session-ID': token,
          }),
        })
      )
    })

    it('should handle query parameters', async () => {
      mockFetch.mockResolvedValueOnce(jsonResponse({}))

      await apiClient.request('/test', {
        params: {
          page: 1,
          size: 10,
          active: true,
          search: 'test query',
        },
      })

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/test?page=1&size=10&active=true&search=test+query',
        expect.any(Object)
      )
    })

    it('should filter out null and undefined parameters', async () => {
      mockFetch.mockResolvedValueOnce(jsonResponse({}))

      await apiClient.request('/test', {
        params: {
          page: 1,
          size: null as never,
          active: undefined as never,
          search: 'test',
        },
      })

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/test?page=1&search=test',
        expect.any(Object)
      )
    })
  })

  describe('error handling', () => {
    it('should throw ApiError for HTTP errors', async () => {
      const errorData = { message: 'Not found', code: 'NOT_FOUND', detail: 'Not found' }
      mockFetch.mockResolvedValueOnce(
        jsonResponse(errorData, {
          ok: false,
          status: 404,
          statusText: 'Not Found',
        })
      )

      await expect(apiClient.request('/test')).rejects.toThrow(ApiError)

      mockFetch.mockResolvedValueOnce(
        jsonResponse(errorData, {
          ok: false,
          status: 404,
          statusText: 'Not Found',
        })
      )

      try {
        await apiClient.request('/test')
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError)
        expect((error as ApiError).status).toBe(404)
        expect((error as ApiError).data).toEqual(errorData)
        expect((error as ApiError).message).toBe('Not found')
      }
    })

    it('should handle error responses without JSON body', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        headers: new Headers(),
        json: vi.fn().mockRejectedValue(new Error('No JSON body')),
      })

      try {
        await apiClient.request('/test', { retries: 3 })
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError)
        expect((error as ApiError).status).toBe(500)
        expect((error as ApiError).message).toBe('Internal Server Error')
      }
    })

    it('should handle network errors', async () => {
      mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'))

      try {
        await apiClient.request('/test', { retries: 3 })
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError)
        expect((error as ApiError).status).toBe(0)
        expect((error as ApiError).message).toBe('Failed to fetch')
        expect((error as ApiError).userFriendlyMessage).toContain(
          'Não foi possível conectar ao servidor'
        )
      }
    })

    it('should handle timeout aborts', async () => {
      vi.useFakeTimers()
      mockFetch.mockImplementationOnce(
        (_url: string, init?: RequestInit) =>
          new Promise((_, reject) => {
            init?.signal?.addEventListener('abort', () => {
              reject(new DOMException('Request aborted', 'AbortError'))
            })
          })
      )

      const requestPromise = apiClient.request('/test', {
        timeout: 10,
        retries: 3,
      })

      vi.advanceTimersByTime(11)
      await expect(requestPromise).rejects.toMatchObject({
        name: 'ApiError',
        status: 0,
      })
    })
  })

  describe('response handling', () => {
    it('should handle JSON responses', async () => {
      const mockData = { test: 'data' }
      mockFetch.mockResolvedValueOnce(jsonResponse(mockData))

      const result = await apiClient.request('/test')
      expect(result).toEqual(mockData)
    })

    it('should handle empty responses without JSON parsing', async () => {
      const jsonSpy = vi.fn().mockRejectedValue(new Error('Should not be called'))
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
        headers: new Headers(),
        json: jsonSpy,
      })

      const result = await apiClient.request('/test', {
        method: 'DELETE',
      })

      expect(result).toBeUndefined()
      expect(jsonSpy).not.toHaveBeenCalled()
    })
  })

  describe('auth token management', () => {
    it('should set and use auth token', async () => {
      const token = 'test-auth-token'
      apiClient.setAuthToken(token)
      mockFetch.mockResolvedValueOnce(jsonResponse({}))

      await apiClient.request('/test')

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: `Bearer ${token}`,
            'X-Session-ID': token,
          }),
        })
      )
    })

    it('should handle session token setting', () => {
      const session = {
        access_token: 'session-token',
        refresh_token: 'refresh-token',
      }

      apiClient.setSessionToken(session)

      expect((apiClient as unknown as { authToken: string | null }).authToken).toBe('session-token')
    })

    it('should clear token when session is null', () => {
      apiClient.setSessionToken(null)
      expect((apiClient as unknown as { authToken: string | null }).authToken).toBe(null)
    })
  })
})

describe('ApiClient Endpoints Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiClient.setAuthToken(null)
    setBaseUrl()
    seedCsrfToken()
    mockFetch.mockImplementation(() => Promise.resolve(jsonResponse({ success: true })))
  })

  describe('auth endpoints', () => {
    it('should call verify-session for the me endpoint', async () => {
      await apiClient.auth.me()

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/auth/verify-session',
        expect.objectContaining({
          method: 'GET',
          credentials: 'include',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
        })
      )
    })

    it('should call logout endpoint with DELETE', async () => {
      await apiClient.auth.logout()

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/auth/logout',
        expect.objectContaining({
          method: 'DELETE',
          headers: expect.objectContaining({
            'X-CSRF-Token': 'csrf-test-token',
          }),
        })
      )
    })
  })

  describe('patients endpoints', () => {
    it('should list patients with canonical cursor/limit parameters', async () => {
      await apiClient.patients.list({ page: 1, size: 10, search: 'john', status: 'active' })

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/patients/?limit=10&search=john&status=active',
        expect.any(Object)
      )
    })

    it('should get single patient', async () => {
      const patientId = 'patient-123'

      await apiClient.patients.get(patientId)

      expect(mockFetch).toHaveBeenCalledWith(
        `http://localhost:8000/api/v2/patients/${patientId}`,
        expect.any(Object)
      )
    })

    it('should create patient', async () => {
      const patientData = {
        name: 'John Doe',
        email: 'john@example.com',
        phone: '+5511999999999',
        doctor_id: 'doc-123',
      }

      await apiClient.patients.create(patientData)

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/patients/',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(patientData),
        })
      )
    })

    it('should update patient', async () => {
      const patientId = 'patient-123'
      const updateData = { name: 'Jane Doe' }

      await apiClient.patients.update(patientId, updateData)

      expect(mockFetch).toHaveBeenCalledWith(
        `http://localhost:8000/api/v2/patients/${patientId}`,
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify(updateData),
        })
      )
    })

    it('should delete patient', async () => {
      const patientId = 'patient-123'

      await apiClient.patients.deletePatient(patientId)

      expect(mockFetch).toHaveBeenCalledWith(
        `http://localhost:8000/api/v2/patients/${patientId}`,
        expect.objectContaining({
          method: 'DELETE',
        })
      )
    })

    it('should get patient timeline', async () => {
      const patientId = 'patient-123'

      await apiClient.patients.timeline(patientId)

      expect(mockFetch).toHaveBeenCalledWith(
        `http://localhost:8000/api/v2/patients/${patientId}/timeline`,
        expect.any(Object)
      )
    })

    it('should activate patient through patch semantics', async () => {
      const patientId = 'patient-123'

      await apiClient.patients.activate(patientId)

      expect(mockFetch).toHaveBeenCalledWith(
        `http://localhost:8000/api/v2/patients/${patientId}`,
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ flow_state: 'active' }),
        })
      )
    })
  })

  describe('messages endpoints', () => {
    it('should list messages with limit-based filters', async () => {
      await apiClient.messages.list({ patient_id: 'patient-123', page: 1, size: 20 })

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/messages?limit=20&patient_id=patient-123&page=1',
        expect.any(Object)
      )
    })

    it('should send message', async () => {
      const messageData = {
        patient_id: 'patient-123',
        content: 'Hello patient',
        type: 'text' as const,
      }

      await apiClient.messages.send(messageData)

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/messages',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(messageData),
        })
      )
    })

    it('should retry message', async () => {
      const messageId = 'message-123'

      await apiClient.messages.retry(messageId)

      expect(mockFetch).toHaveBeenCalledWith(
        `http://localhost:8000/api/v2/messages/${messageId}/retry`,
        expect.objectContaining({
          method: 'POST',
        })
      )
    })
  })

  describe('flows endpoints', () => {
    it('should list flows', async () => {
      await apiClient.flows.list({ patient_id: 'patient-123', status: 'active' })

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/flows?patient_id=patient-123&status=active',
        expect.any(Object)
      )
    })

    it('should start flow', async () => {
      const patientId = 'patient-123'
      const flowType = 'onboarding'

      await apiClient.flows.start(patientId, flowType)

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/flows/start',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ patient_id: patientId, flow_type: flowType }),
        })
      )
    })

    it('should get flow state', async () => {
      const patientId = 'patient-123'

      await apiClient.flows.getState(patientId)

      expect(mockFetch).toHaveBeenCalledWith(
        `http://localhost:8000/api/v2/flows/${patientId}/state`,
        expect.any(Object)
      )
    })

    it('should advance flow with the v2 payload', async () => {
      const patientId = 'patient-123'
      const forceDay = 3

      await apiClient.flows.advance(patientId, forceDay)

      expect(mockFetch).toHaveBeenCalledWith(
        `http://localhost:8000/api/v2/flows/${patientId}/advance`,
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ target_day: forceDay, skip_conditions: false }),
        })
      )
    })
  })

  describe('error handling in endpoints', () => {
    it('should propagate API errors from endpoints', async () => {
      mockFetch.mockResolvedValueOnce(
        jsonResponse(
          { message: 'Validation error', field: 'name' },
          { ok: false, status: 400, statusText: 'Bad Request' }
        )
      )

      await expect(
        apiClient.patients.create({
          name: 'Erro Paciente',
          phone: '+5511999999999',
          doctor_id: 'doc-error',
        })
      ).rejects.toThrow(ApiError)
    })

    it('should handle network errors in endpoints', async () => {
      mockFetch.mockRejectedValue(new TypeError('Failed to fetch'))

      await expect(apiClient.patients.list({})).rejects.toThrow(ApiError)
    })
  })
})
