import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { apiClient, ApiError } from '../../lib/api-client'

// Mock fetch globally
const mockFetch = vi.fn()
global.fetch = mockFetch

describe('ApiClient Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiClient.setAuthToken(null)
  })

  afterEach(() => {
    vi.clearAllTimers()
  })

  describe('request method', () => {
    it('should make successful GET request', async () => {
      const mockData = { id: 1, name: 'Test' }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockData
      })

      const result = await apiClient.request('/test')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/test',
        expect.objectContaining({
          headers: expect.objectContaining({
            'Content-Type': 'application/json'
          })
        })
      )
      expect(result).toEqual(mockData)
    })

    it('should make successful POST request with body', async () => {
      const mockData = { id: 1, name: 'Test' }
      const postData = { name: 'New Test' }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockData
      })

      const result = await apiClient.request('/test', {
        method: 'POST',
        body: JSON.stringify(postData)
      })

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/test',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(postData),
          headers: expect.objectContaining({
            'Content-Type': 'application/json'
          })
        })
      )
      expect(result).toEqual(mockData)
    })

    it('should include auth token when set', async () => {
      const token = 'test-token'
      apiClient.setAuthToken(token)

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({})
      })

      await apiClient.request('/test')

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            ['Authorization']: `Bearer ${token}`
          })
        })
      )
    })

    it('should handle query parameters', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({})
      })

      await apiClient.request('/test', {
        params: {
          page: 1,
          size: 10,
          active: true,
          search: 'test query'
        }
      })

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/test?page=1&size=10&active=true&search=test+query',
        expect.any(Object)
      )
    })

    it('should filter out null and undefined parameters', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({})
      })

      await apiClient.request('/test', {
        params: {
          page: 1,
          size: null as any,
          active: undefined as any,
          search: 'test'
        }
      })

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/test?page=1&search=test',
        expect.any(Object)
      )
    })
  })

  describe('error handling', () => {
    it('should throw ApiError for HTTP errors', async () => {
      const errorData = { message: 'Not found', code: 'NOT_FOUND' }
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => errorData
      })

      await expect(apiClient.request('/test')).rejects.toThrow(ApiError)

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
        json: async () => { throw new Error('No JSON body') }
      })

      try {
        await apiClient.request('/test')
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError)
        expect((error as ApiError).status).toBe(500)
        expect((error as ApiError).data.message).toBe('HTTP 500: Internal Server Error')
      }
    })

    it('should handle network errors', async () => {
      mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'))

      try {
        await apiClient.request('/test')
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError)
        expect((error as ApiError).status).toBe(0)
        expect((error as ApiError).message).toContain('Não foi possível conectar ao servidor')
      }
    })

    it('should handle timeout errors', async () => {
      vi.useFakeTimers()

      mockFetch.mockImplementationOnce(() =>
        new Promise(resolve => setTimeout(resolve, 35000))
      )

      const requestPromise = apiClient.request('/test')

      // Fast-forward time to trigger timeout
      vi.advanceTimersByTime(30000)

      await expect(requestPromise).rejects.toThrow(ApiError)

      vi.useRealTimers()
    })
  })

  describe('content type handling', () => {
    it('should handle JSON responses', async () => {
      const mockData = { test: 'data' }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockData
      })

      const result = await apiClient.request('/test')
      expect(result).toEqual(mockData)
    })

    it('should handle blob responses', async () => {
      const mockBlob = new Blob(['test'], { type: 'text/plain' })
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'text/plain']]),
        blob: async () => mockBlob
      })

      const result = await apiClient.request('/test')
      expect(result).toBe(mockBlob)
    })

    it('should handle responses without content-type header', async () => {
      const mockResponse = { text: 'response text' }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map(),
        json: async () => { throw new Error('Not JSON') },
        text: async () => 'response text'
      } as any)

      const result = await apiClient.request('/test')
      expect(result).toEqual(mockResponse)
    })
  })

  describe('auth token management', () => {
    it('should set and use auth token', async () => {
      const token = 'test-auth-token'
      apiClient.setAuthToken(token)

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({})
      })

      await apiClient.request('/test')

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            ['Authorization']: `Bearer ${token}`
          })
        })
      )
    })

    it('should handle supabase token setting', () => {
      const session = {
        access_token: 'supabase-token',
        refresh_token: 'refresh-token'
      }

      apiClient.setSupabaseToken(session)

      // Verify internal auth token was set
      expect(apiClient['authToken']).toBe('supabase-token')
    })

    it('should clear token when session is null', () => {
      apiClient.setSupabaseToken(null)
      expect(apiClient['authToken']).toBe(null)
    })
  })
})

describe('ApiClient Endpoints Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Map([['content-type', 'application/json']]),
      json: async () => ({ success: true })
    })
  })

  describe('auth endpoints', () => {
    it('should call me endpoint', async () => {
      await apiClient.auth.me()

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/auth/me',
        expect.any(Object)
      )
    })

    it('should call logout endpoint', async () => {
      await apiClient.auth.logout()

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/auth/logout',
        expect.objectContaining({
          method: 'POST'
        })
      )
    })
  })

  describe('patients endpoints', () => {
    it('should list patients with parameters', async () => {
      const params = { page: 1, size: 10, search: 'john', status: 'active' }

      await apiClient.patients.list(params)

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/patients?page=1&size=10&search=john&status=active',
        expect.any(Object)
      )
    })

    it('should get single patient', async () => {
      const patientId = 'patient-123'

      await apiClient.patients.get(patientId)

      expect(mockFetch).toHaveBeenCalledWith(
        `http://localhost:8000/api/v1/patients/${patientId}`,
        expect.any(Object)
      )
    })

    it('should create patient', async () => {
      const patientData = { name: 'John Doe', email: 'john@example.com' }

      await apiClient.patients.create(patientData)

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/patients',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(patientData)
        })
      )
    })

    it('should update patient', async () => {
      const patientId = 'patient-123'
      const updateData = { name: 'Jane Doe' }

      await apiClient.patients.update(patientId, updateData)

      expect(mockFetch).toHaveBeenCalledWith(
        `http://localhost:8000/api/v1/patients/${patientId}`,
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify(updateData)
        })
      )
    })

    it('should delete patient', async () => {
      const patientId = 'patient-123'

      await apiClient.patients.deletePatient(patientId)

      expect(mockFetch).toHaveBeenCalledWith(
        `http://localhost:8000/api/v1/patients/${patientId}`,
        expect.objectContaining({
          method: 'DELETE'
        })
      )
    })

    it('should get patient timeline', async () => {
      const patientId = 'patient-123'

      await apiClient.patients.timeline(patientId)

      expect(mockFetch).toHaveBeenCalledWith(
        `http://localhost:8000/api/v1/patients/${patientId}/timeline`,
        expect.any(Object)
      )
    })

    it('should activate patient', async () => {
      const patientId = 'patient-123'

      await apiClient.patients.activate(patientId)

      expect(mockFetch).toHaveBeenCalledWith(
        `http://localhost:8000/api/v1/patients/${patientId}/activate`,
        expect.objectContaining({
          method: 'POST'
        })
      )
    })
  })

  describe('messages endpoints', () => {
    it('should list messages with filters', async () => {
      const params = { patient_id: 'patient-123', page: 1, size: 20 }

      await apiClient.messages.list(params)

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/messages?patient_id=patient-123&page=1&size=20',
        expect.any(Object)
      )
    })

    it('should send message', async () => {
      const messageData = {
        patient_id: 'patient-123',
        content: 'Hello patient',
        type: 'text'
      }

      await apiClient.messages.send(messageData)

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/messages/send',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(messageData)
        })
      )
    })

    it('should retry message', async () => {
      const messageId = 'message-123'

      await apiClient.messages.retry(messageId)

      expect(mockFetch).toHaveBeenCalledWith(
        `http://localhost:8000/api/v1/messages/${messageId}/retry`,
        expect.objectContaining({
          method: 'POST'
        })
      )
    })
  })

  describe('flows endpoints', () => {
    it('should list flows', async () => {
      const params = { patient_id: 'patient-123', status: 'active' }

      await apiClient.flows.list(params)

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/flows?patient_id=patient-123&status=active',
        expect.any(Object)
      )
    })

    it('should start flow', async () => {
      const patientId = 'patient-123'
      const flowType = 'onboarding'

      await apiClient.flows.start(patientId, flowType)

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/flows/start',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ patient_id: patientId, flow_type: flowType })
        })
      )
    })

    it('should get flow state', async () => {
      const patientId = 'patient-123'

      await apiClient.flows.getState(patientId)

      expect(mockFetch).toHaveBeenCalledWith(
        `http://localhost:8000/api/v1/flows/${patientId}/state`,
        expect.any(Object)
      )
    })

    it('should advance flow', async () => {
      const patientId = 'patient-123'
      const forceDay = 3

      await apiClient.flows.advance(patientId, forceDay)

      expect(mockFetch).toHaveBeenCalledWith(
        `http://localhost:8000/api/v1/flows/${patientId}/advance`,
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ force_day: forceDay })
        })
      )
    })
  })

  describe('error handling in endpoints', () => {
    it('should propagate API errors from endpoints', async () => {
      const errorResponse = {
        ok: false,
        status: 400,
        json: async () => ({ message: 'Validation error', field: 'name' })
      }

      mockFetch.mockResolvedValueOnce(errorResponse)

      await expect(apiClient.patients.create({})).rejects.toThrow(ApiError)
    })

    it('should handle network errors in endpoints', async () => {
      mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'))

      await expect(apiClient.patients.list({})).rejects.toThrow(ApiError)
    })
  })
})