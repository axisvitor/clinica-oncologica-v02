/**
 * Comprehensive API Connection Integration Tests
 *
 * Tests all API connections to validate:
 * - Authentication flows
 * - Patient CRUD operations
 * - Quiz/Assessment flows
 * - Admin operations
 * - Analytics endpoints
 * - Messages and Flows
 * - Error handling scenarios
 * - Type safety validation
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { apiClient, ApiError } from '@/lib/api-client'

// Mock fetch globally
const mockFetch = vi.fn()
global.fetch = mockFetch

describe('API Connection Tests - Authentication', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiClient.setAuthToken(null)
    apiClient.setBaseURL('http://localhost:8000')
  })

  afterEach(() => {
    vi.clearAllTimers()
  })

  describe('Session Management', () => {
    it('should validate session successfully', async () => {
      const mockSessionResponse = {
        valid: true,
        user: {
          id: 'user-123',
          email: 'test@example.com',
          full_name: 'Test User',
          role: 'doctor',
          permissions: ['patient:read', 'patient:write'],
          is_active: true,
          created_at: '2024-01-01T00:00:00Z'
        },
        session_data: {
          last_activity: '2024-01-15T10:00:00Z'
        }
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockSessionResponse
      })

      const session = await apiClient.auth.getSession()

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/auth/verify-session',
        expect.objectContaining({
          method: 'GET',
          credentials: 'include'
        })
      )
      expect(session.valid).toBe(true)
      expect(session.user?.email).toBe('test@example.com')
    })

    it('should create session with Firebase token', async () => {
      const mockResponse = {
        valid: true,
        session_id: 'session-123',
        message: 'Login successful'
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockResponse
      })

      const result = await apiClient.auth.createSession(
        'firebase-token-123',
        { user_agent: 'Mozilla/5.0', timestamp: '2024-01-15T10:00:00Z' }
      )

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/auth/firebase/verify',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            id_token: 'firebase-token-123'
          })
        })
      )
      expect(result.valid).toBe(true)
      expect(result.session_id).toBe('session-123')
    })

    it('should logout successfully', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({
          success: true,
          message: 'Logged out successfully'
        })
      })

      const result = await apiClient.auth.logout()

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/auth/logout',
        expect.objectContaining({
          method: 'DELETE'
        })
      )
      expect(result.success).toBe(true)
      expect(apiClient.getAuthToken()).toBeNull()
    })

    it('should get current user from session', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({
          valid: true,
          user: {
            id: 'user-123',
            email: 'test@example.com',
            full_name: 'Test User',
            role: 'doctor',
            permissions: ['patient:read'],
            is_active: true,
            created_at: '2024-01-01T00:00:00Z'
          }
        })
      })

      const user = await apiClient.auth.getCurrentUser()

      expect(user.id).toBe('user-123')
      expect(user.email).toBe('test@example.com')
      expect(user.role).toBe('doctor')
    })

    it('should handle invalid session', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({
          valid: false,
          user: null
        })
      })

      await expect(apiClient.auth.getCurrentUser()).rejects.toThrow('Not authenticated')
    })

    it('should check auth status', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({
          valid: true,
          user: {
            id: 'user-123',
            email: 'test@example.com',
            full_name: 'Test User',
            role: 'doctor',
            is_active: true
          }
        })
      })

      const authStatus = await apiClient.auth.checkAuth()

      expect(authStatus.authenticated).toBe(true)
      expect(authStatus.user).toBeDefined()
      expect(authStatus.user?.email).toBe('test@example.com')
    })

    it('should invalidate all sessions', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({
          success: true,
          sessions_deleted: 3,
          message: 'Logged out from all devices'
        })
      })

      const result = await apiClient.auth.invalidateAllSessions()

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/auth/logout-all',
        expect.objectContaining({
          method: 'DELETE'
        })
      )
      expect(result.sessions_deleted).toBe(3)
    })
  })

  describe('Authentication Error Handling', () => {
    it('should handle 401 Unauthorized', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({
          detail: 'Unauthorized',
          message: 'Session expired'
        })
      })

      try {
        await apiClient.auth.getCurrentUser()
        expect.fail('Should have thrown error')
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError)
        expect((error as ApiError).status).toBe(401)
        expect((error as ApiError).userFriendlyMessage).toContain('sessão expirou')
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
        await apiClient.auth.createSession('invalid-token')
        expect.fail('Should have thrown error')
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError)
        expect((error as ApiError).status).toBe(403)
        expect((error as ApiError).userFriendlyMessage).toContain('permissão')
      }
    })

    it('should handle network errors', async () => {
      mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'))

      try {
        await apiClient.auth.getSession()
        expect.fail('Should have thrown error')
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError)
        expect((error as ApiError).status).toBe(0)
        expect((error as ApiError).userFriendlyMessage).toContain('conexão')
      }
    })
  })
})

describe('API Connection Tests - Patients', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Map([['content-type', 'application/json']]),
      json: async () => ({ success: true })
    })
  })

  describe('Patient CRUD Operations', () => {
    it('should list patients with pagination', async () => {
      const mockResponse = {
        items: [
          {
            id: 'patient-1',
            name: 'Patient One',
            email: 'patient1@example.com',
            phone: '+5511999999999',
            status: 'active',
            created_at: '2024-01-01T00:00:00Z'
          },
          {
            id: 'patient-2',
            name: 'Patient Two',
            email: 'patient2@example.com',
            phone: '+5511988888888',
            status: 'active',
            created_at: '2024-01-02T00:00:00Z'
          }
        ],
        total: 2,
        has_more: false
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockResponse
      })

      const result = await apiClient.patients.list(1, 20)

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/patients?limit=20',
        expect.any(Object)
      )
      expect(result.items).toHaveLength(2)
      expect(result.total).toBe(2)
    })

    it('should get single patient', async () => {
      const mockPatient = {
        id: 'patient-123',
        name: 'Test Patient',
        email: 'test@example.com',
        phone: '+5511999999999',
        status: 'active',
        doctor_id: 'doctor-123',
        created_at: '2024-01-01T00:00:00Z'
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockPatient
      })

      const result = await apiClient.patients.get('patient-123')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/patients/patient-123',
        expect.any(Object)
      )
      expect(result.id).toBe('patient-123')
      expect(result.name).toBe('Test Patient')
    })

    it('should create patient', async () => {
      const patientData = {
        name: 'New Patient',
        email: 'new@example.com',
        phone: '+5511999999999',
        doctor_id: 'doctor-123'
      }

      const mockResponse = {
        id: 'patient-new',
        ...patientData,
        status: 'active',
        created_at: '2024-01-15T00:00:00Z'
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockResponse
      })

      const result = await apiClient.patients.create(patientData)

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/patients',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(patientData)
        })
      )
      expect(result.id).toBe('patient-new')
      expect(result.name).toBe('New Patient')
    })

    it('should require doctor_id when creating patient', async () => {
      await expect(
        apiClient.patients.create({
          name: 'New Patient',
          phone: '+5511999999999',
          doctor_id: '' // Invalid
        } as any)
      ).rejects.toThrow('doctor_id is required')
    })

    it('should update patient', async () => {
      const updateData = {
        name: 'Updated Name',
        status: 'inactive' as const
      }

      const mockResponse = {
        id: 'patient-123',
        name: 'Updated Name',
        email: 'test@example.com',
        phone: '+5511999999999',
        status: 'inactive',
        doctor_id: 'doctor-123',
        updated_at: '2024-01-15T00:00:00Z'
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockResponse
      })

      const result = await apiClient.patients.update('patient-123', updateData)

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/patients/patient-123',
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify(updateData)
        })
      )
      expect(result.name).toBe('Updated Name')
      expect(result.status).toBe('inactive')
    })

    it('should delete patient', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({ message: 'Patient deleted successfully' })
      })

      const result = await apiClient.patients.delete('patient-123')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/patients/patient-123',
        expect.objectContaining({
          method: 'DELETE'
        })
      )
      expect(result.message).toContain('deleted')
    })

    it('should activate patient', async () => {
      const mockResponse = {
        id: 'patient-123',
        name: 'Test Patient',
        status: 'active',
        email: 'test@example.com',
        phone: '+5511999999999'
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockResponse
      })

      const result = await apiClient.patients.activate('patient-123')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/patients/patient-123/activate',
        expect.objectContaining({
          method: 'POST'
        })
      )
      expect(result.status).toBe('active')
    })

    it('should deactivate patient', async () => {
      const mockResponse = {
        id: 'patient-123',
        name: 'Test Patient',
        status: 'inactive',
        email: 'test@example.com',
        phone: '+5511999999999'
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockResponse
      })

      const result = await apiClient.patients.deactivate('patient-123')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/patients/patient-123/deactivate',
        expect.objectContaining({
          method: 'POST'
        })
      )
      expect(result.status).toBe('inactive')
    })

    it('should get patient timeline', async () => {
      const mockTimeline = {
        patient_id: 'patient-123',
        events: [
          {
            id: 'event-1',
            type: 'quiz_completed',
            title: 'Quiz Completed',
            description: 'Patient completed monthly quiz',
            timestamp: '2024-01-15T10:00:00Z'
          },
          {
            id: 'event-2',
            type: 'message_sent',
            title: 'Message Sent',
            description: 'Welcome message sent',
            timestamp: '2024-01-01T09:00:00Z'
          }
        ]
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockTimeline
      })

      const result = await apiClient.patients.timeline('patient-123')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/patients/patient-123/timeline',
        expect.any(Object)
      )
      expect(result.patient_id).toBe('patient-123')
      expect(result.events).toHaveLength(2)
    })

    it('should search patients', async () => {
      const mockResults = [
        {
          id: 'patient-1',
          name: 'John Doe',
          email: 'john@example.com',
          phone: '+5511999999999'
        }
      ]

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockResults
      })

      const result = await apiClient.patients.search('John')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/patients/search?q=John',
        expect.any(Object)
      )
      expect(result).toHaveLength(1)
      expect(result[0]?.name).toBe('John Doe')
    })
  })

  describe('Patient Error Handling', () => {
    it('should handle 404 Not Found', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({
          detail: 'Patient not found',
          message: 'Patient with ID patient-999 not found'
        })
      })

      try {
        await apiClient.patients.get('patient-999')
        expect.fail('Should have thrown error')
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError)
        expect((error as ApiError).status).toBe(404)
      }
    })

    it('should handle 400 Bad Request', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({
          detail: 'Invalid patient data',
          errors: {
            phone: ['Invalid phone format']
          }
        })
      })

      try {
        await apiClient.patients.create({
          name: 'Test',
          phone: 'invalid',
          doctor_id: 'doc-1'
        })
        expect.fail('Should have thrown error')
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError)
        expect((error as ApiError).status).toBe(400)
      }
    })
  })
})

describe('API Connection Tests - Quiz/Assessments', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Monthly Quiz Operations', () => {
    it('should create quiz link', async () => {
      const mockLink = {
        id: 'link-123',
        quiz_session_id: 'session-123',
        patient_id: 'patient-123',
        quiz_template_id: 'template-123',
        token: 'abc123',
        link: 'https://quiz.example.com/abc123',
        delivery_method: 'whatsapp' as const,
        status: 'pending' as const,
        expires_at: '2024-01-30T00:00:00Z',
        created_at: '2024-01-15T00:00:00Z',
        updated_at: '2024-01-15T00:00:00Z'
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockLink
      })

      const result = await apiClient.monthlyQuiz.createLink({
        patient_id: 'patient-123',
        quiz_template_id: 'template-123',
        delivery_method: 'whatsapp'
      })

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/monthly-quiz/links',
        expect.objectContaining({
          method: 'POST'
        })
      )
      expect(result.id).toBe('link-123')
      expect(result.delivery_method).toBe('whatsapp')
    })

    it('should create bulk quiz links', async () => {
      const mockResponse = {
        success: 2,
        failed: 0,
        links: [
          {
            id: 'link-1',
            quiz_session_id: 'session-1',
            patient_id: 'patient-1',
            quiz_template_id: 'template-1',
            token: 'token1',
            link: 'https://quiz.example.com/token1',
            delivery_method: 'whatsapp' as const,
            status: 'pending' as const,
            expires_at: '2024-01-30T00:00:00Z',
            created_at: '2024-01-15T00:00:00Z',
            updated_at: '2024-01-15T00:00:00Z'
          },
          {
            id: 'link-2',
            quiz_session_id: 'session-2',
            patient_id: 'patient-2',
            quiz_template_id: 'template-1',
            token: 'token2',
            link: 'https://quiz.example.com/token2',
            delivery_method: 'whatsapp' as const,
            status: 'pending' as const,
            expires_at: '2024-01-30T00:00:00Z',
            created_at: '2024-01-15T00:00:00Z',
            updated_at: '2024-01-15T00:00:00Z'
          }
        ],
        errors: []
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockResponse
      })

      const result = await apiClient.monthlyQuiz.bulkCreate({
        patient_ids: ['patient-1', 'patient-2'],
        quiz_template_id: 'template-1',
        delivery_method: 'whatsapp'
      })

      expect(result.success).toBe(2)
      expect(result.failed).toBe(0)
      expect(result.links).toHaveLength(2)
    })

    it('should get quiz link status', async () => {
      const mockStatus = {
        quiz_session_id: 'session-123',
        patient_name: 'Test Patient',
        status: 'completed' as const,
        link: 'https://quiz.example.com/abc123',
        expires_at: '2024-01-30T00:00:00Z',
        sent_at: '2024-01-15T00:00:00Z',
        accessed_at: '2024-01-15T10:00:00Z',
        completed_at: '2024-01-15T10:30:00Z',
        can_resend: false,
        can_cancel: false
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockStatus
      })

      const result = await apiClient.monthlyQuiz.getStatus('session-123')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/monthly-quiz/links/session-123/status',
        expect.any(Object)
      )
      expect(result.status).toBe('completed')
      expect(result.completed_at).toBeDefined()
    })

    it('should get quiz statistics', async () => {
      const mockStats = {
        total_sent: 100,
        total_completed: 75,
        total_expired: 10,
        total_active: 15,
        average_score: 85.5,
        completion_rate: 75,
        expiration_rate: 10
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockStats
      })

      const result = await apiClient.monthlyQuiz.getStats()

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/monthly-quiz/stats/dashboard',
        expect.any(Object)
      )
      expect(result.total_sent).toBe(100)
      expect(result.completion_rate).toBe(75)
    })

    it('should list quiz templates', async () => {
      const mockTemplates = [
        {
          id: 'template-1',
          name: 'Monthly Health Check',
          description: 'General health assessment',
          questions_count: 10,
          is_active: true,
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z'
        }
      ]

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockTemplates
      })

      const result = await apiClient.monthlyQuiz.listTemplates(true)

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/monthly-quiz/templates?active_only=true',
        expect.any(Object)
      )
      expect(result).toHaveLength(1)
      expect(result[0]?.name).toBe('Monthly Health Check')
    })

    it('should resend quiz link', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({
          message: 'Quiz link resent successfully',
          sent_at: '2024-01-15T12:00:00Z'
        })
      })

      const result = await apiClient.monthlyQuiz.resend('session-123', 'email')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/monthly-quiz/links/session-123/resend',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ delivery_method: 'email' })
        })
      )
      expect(result.message).toContain('resent')
    })

    it('should cancel quiz link', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({
          message: 'Quiz link cancelled successfully'
        })
      })

      const result = await apiClient.monthlyQuiz.cancel('session-123')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/monthly-quiz/links/session-123/cancel',
        expect.objectContaining({
          method: 'POST'
        })
      )
      expect(result.message).toContain('cancelled')
    })
  })

  describe('Quiz Session Operations', () => {
    it('should get quiz session', async () => {
      const mockSession = {
        id: 'session-123',
        patient_id: 'patient-123',
        quiz_template_id: 'template-123',
        status: 'completed' as const,
        started_at: '2024-01-15T10:00:00Z',
        completed_at: '2024-01-15T10:30:00Z',
        score: 85,
        total_questions: 10,
        answered_questions: 10,
        created_at: '2024-01-15T00:00:00Z',
        updated_at: '2024-01-15T10:30:00Z'
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockSession
      })

      const result = await apiClient.monthlyQuiz.getSession('session-123')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/monthly-quiz/sessions/session-123',
        expect.any(Object)
      )
      expect(result.status).toBe('completed')
      expect(result.score).toBe(85)
    })

    it('should get session responses', async () => {
      const mockResponses = [
        {
          id: 'response-1',
          quiz_session_id: 'session-123',
          question_id: 'q1',
          question_text: 'How are you feeling?',
          response_value: 'Great',
          answered_at: '2024-01-15T10:05:00Z'
        }
      ]

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockResponses
      })

      const result = await apiClient.monthlyQuiz.getSessionResponses('session-123')

      expect(result).toHaveLength(1)
      expect(result[0]?.question_text).toBe('How are you feeling?')
    })
  })
})
