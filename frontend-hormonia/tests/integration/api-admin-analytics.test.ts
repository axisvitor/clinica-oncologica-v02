/**
 * API Integration Tests - Admin & Analytics
 *
 * Tests for:
 * - Admin user management
 * - Admin operations
 * - Analytics endpoints
 * - Dashboard metrics
 * - Risk assessments
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { apiClient, ApiError } from '@/lib/api-client'

const mockFetch = vi.fn()
global.fetch = mockFetch

const setCsrfToken = (token: string | null) => {
  const apiClientAny = apiClient as any
  apiClientAny.csrfToken = token
  apiClientAny.csrfTokenPromise = null
}

beforeEach(() => {
  setCsrfToken('csrf-token')
})

afterEach(() => {
  setCsrfToken(null)
})

describe('API Connection Tests - Admin Operations', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiClient.setBaseURL('http://localhost:8000')
  })

  describe('Admin User Management', () => {
    it('should list admin users with pagination', async () => {
      const mockResponse = {
        items: [
          {
            id: 'admin-1',
            email: 'admin@example.com',
            full_name: 'Admin User',
            role: 'admin',
            is_active: true,
            permissions: ['user:read', 'user:write'],
            created_at: '2024-01-01T00:00:00-03:00'
          }
        ],
        total: 1
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockResponse
      })

      const result = await apiClient.adminUsers.list({ page: 1, size: 20 })

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v2/admin/users'),
        expect.any(Object)
      )
      expect(result.items).toBeDefined()
      expect(result.total).toBe(1)
    })

    it('should get single admin user', async () => {
      const mockUser = {
        id: 'admin-1',
        email: 'admin@example.com',
        full_name: 'Admin User',
        role: 'admin',
        is_active: true,
        permissions: ['user:read', 'user:write'],
        created_at: '2024-01-01T00:00:00-03:00'
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockUser
      })

      const result = await apiClient.adminUsers.get('admin-1')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/admin/users/admin-1',
        expect.any(Object)
      )
      expect(result.email).toBe('admin@example.com')
    })

    it('should create admin user', async () => {
      const userData = {
        email: 'newadmin@example.com',
        full_name: 'New Admin',
        password: 'SecurePass123!',
        role: 'doctor'
      }

      const mockResponse = {
        id: 'admin-new',
        ...userData,
        is_active: true,
        permissions: [],
        created_at: '2024-01-15T00:00:00-03:00'
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockResponse
      })

      const result = await apiClient.adminUsers.create(userData)

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/admin/users',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(userData)
        })
      )
      expect(result.id).toBe('admin-new')
    })

    it('should update admin user', async () => {
      const updateData = {
        full_name: 'Updated Name',
        is_active: false
      }

      const mockResponse = {
        id: 'admin-1',
        email: 'admin@example.com',
        full_name: 'Updated Name',
        role: 'admin',
        is_active: false,
        permissions: ['user:read'],
        created_at: '2024-01-01T00:00:00-03:00',
        updated_at: '2024-01-15T00:00:00-03:00'
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockResponse
      })

      const result = await apiClient.adminUsers.update('admin-1', updateData)

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/admin/users/admin-1',
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify(updateData)
        })
      )
      expect(result.full_name).toBe('Updated Name')
    })

    it('should delete admin user', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({ message: 'User deleted successfully' })
      })

      const result = await apiClient.adminUsers.delete('admin-1')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/admin/users/admin-1',
        expect.objectContaining({
          method: 'DELETE'
        })
      )
      expect(result.message).toContain('deleted')
    })

    it('should activate user', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({ message: 'User activated' })
      })

      await apiClient.adminUsers.activate('admin-1')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/admin/users/admin-1/activate',
        expect.objectContaining({
          method: 'POST'
        })
      )
    })

    it('should deactivate user', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({ message: 'User deactivated' })
      })

      await apiClient.adminUsers.deactivate('admin-1')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/admin/users/admin-1/deactivate',
        expect.objectContaining({
          method: 'POST'
        })
      )
    })

    it('should update user permissions', async () => {
      const permissions = ['user:read', 'user:write', 'patient:read']

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({ message: 'Permissions updated' })
      })

      await apiClient.adminUsers.updatePermissions('admin-1', permissions)

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/admin/users/admin-1/permissions',
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({ permissions })
        })
      )
    })

    it('should update user role', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({ message: 'Role updated' })
      })

      await apiClient.adminUsers.updateRole('admin-1', 'doctor')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/admin/users/admin-1/role',
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({ role: 'doctor' })
        })
      )
    })

    it('should get user activity', async () => {
      const mockActivity = {
        items: [
          {
            id: 'activity-1',
            user_id: 'admin-1',
            action: 'login',
            timestamp: '2024-01-15T10:00:00-03:00',
            details: {
              ip: '192.168.1.1',
              user_agent: 'Mozilla/5.0'
            }
          }
        ],
        total: 1
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockActivity
      })

      const result = await apiClient.adminUsers.getActivity('admin-1', { page: 1, size: 20 })

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v2/admin/users/admin-1/activity'),
        expect.any(Object)
      )
      expect(result.items).toHaveLength(1)
    })

    it('should reset user password', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({ message: 'Password reset successfully' })
      })

      await apiClient.adminUsers.resetPassword('admin-1', {
        new_password: 'NewSecure123!',
        force_change: true
      })

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/admin/users/admin-1/reset-password',
        expect.objectContaining({
          method: 'POST'
        })
      )
    })
  })

  describe('Admin System Operations', () => {
    it('should get system health', async () => {
      const mockHealth = {
        status: 'healthy',
        database: 'ok',
        redis: 'ok',
        celery: 'ok',
        timestamp: '2024-01-15T10:00:00-03:00'
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockHealth
      })

      const result = await apiClient.admin.system.getHealth()

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/admin/system/health',
        expect.any(Object)
      )
      expect(result.status).toBe('healthy')
    })

    it('should get system metrics', async () => {
      const mockMetrics = {
        cpu_usage: 45.2,
        memory_usage: 62.8,
        disk_usage: 38.5,
        active_connections: 42,
        requests_per_minute: 150
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockMetrics
      })

      const result = await apiClient.admin.system.getMetrics()

      expect(result.cpu_usage).toBeDefined()
      expect(result.memory_usage).toBeDefined()
    })

    it('should clear cache', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({ message: 'Cache cleared successfully' })
      })

      await apiClient.admin.system.clearCache()

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/admin/system/clear-cache',
        expect.objectContaining({
          method: 'POST'
        })
      )
    })
  })
})

describe('API Connection Tests - Analytics', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiClient.setBaseURL('http://localhost:8000')
  })

  describe('Dashboard Analytics', () => {
    it('should get dashboard metrics', async () => {
      // Mock all required endpoints for dashboard
      const mockOverview = {
        total_patients: 150,
        total_quizzes: 500,
        completed_quizzes: 375,
        completion_rate: 75,
        active_patients_30d: 120,
        period: {
          start_date: '2024-01-01',
          end_date: '2024-01-31'
        }
      }

      const mockStatus = {
        distribution: {
          completed: 375,
          pending: 100,
          cancelled: 25
        },
        total: 500
      }

      const mockTrend = {
        trend: [
          {
            year: 2024,
            month: 1,
            total: 100,
            completed: 75,
            completion_rate: 75
          }
        ]
      }

      const mockEngagement = {
        engagement_levels: {
          no_quizzes: 30,
          low_engagement: 60,
          high_engagement: 60
        },
        average_quizzes_per_patient: 3.3,
        total_active_patients: 150
      }

      let callCount = 0
      mockFetch.mockImplementation(() => {
        callCount++
        const responses = [mockOverview, mockStatus, mockTrend, mockEngagement]
        const response = responses[callCount - 1]
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Map([['content-type', 'application/json']]),
          json: async () => response
        })
      })

      const result = await apiClient.analytics.dashboard()

      expect(result.total_patients).toBe(150)
      expect(result.active_patients).toBe(120)
      expect(result.response_rate).toBe(75)
      expect(result.engagement_chart).toBeDefined()
    })

    it('should get engagement analytics', async () => {
      const mockEngagement = {
        engagement_levels: {
          no_quizzes: 30,
          low_engagement: 60,
          high_engagement: 60
        },
        average_quizzes_per_patient: 3.3,
        total_active_patients: 150
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockEngagement
      })

      const result = await apiClient.analytics.engagement()

      expect(result.total_active_patients).toBe(150)
      expect(result.average_quizzes_per_patient).toBe(3.3)
      expect(result.distribution).toBeDefined()
      expect(result.distribution).toHaveLength(3)
    })

    it('should get treatment distribution', async () => {
      const mockDistribution = {
        period: '30d',
        total_patients: 150,
        distribution: [
          {
            treatment_type: 'Quimioterapia',
            count: 80,
            percentage: 53.3,
            color: '#2563eb'
          },
          {
            treatment_type: 'Radioterapia',
            count: 45,
            percentage: 30,
            color: '#10b981'
          },
          {
            treatment_type: 'Imunoterapia',
            count: 25,
            percentage: 16.7,
            color: '#f59e0b'
          }
        ],
        trend_data: [
          {
            week: '2024-W01',
            count: 150
          }
        ],
        last_updated: '2024-01-15T00:00:00-03:00'
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockDistribution
      })

      const result = await apiClient.analytics.treatmentDistribution('30d')

      expect(result.total_patients).toBe(150)
      expect(result.distribution).toHaveLength(3)
      expect(result.distribution[0]?.treatment_type).toBe('Quimioterapia')
    })

    it('should get risk assessment', async () => {
      const mockRiskAssessment = {
        success: true,
        risk_level_filter: 'high',
        risk_assessments: [
          {
            id: 'risk-1',
            patient_id: 'patient-1',
            name: 'High Risk Patient',
            risk_level: 'high' as const,
            risk_factors: ['Missed 3 quizzes', 'No response in 30 days'],
            last_response: '2023-12-01T00:00:00-03:00',
            recommended_actions: ['Contact immediately', 'Schedule consultation']
          }
        ],
        total_patients: 1,
        generated_at: '2024-01-15T00:00:00-03:00',
        lookback_days: 30
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockRiskAssessment
      })

      const result = await apiClient.analytics.riskAssessment({
        risk_level: 'high',
        limit: 10,
        lookback_days: 30
      })

      expect(result.success).toBe(true)
      expect(result.risk_assessments).toHaveLength(1)
      expect(result.risk_assessments[0]?.risk_level).toBe('high')
    })
  })

  describe('Analytics Error Handling', () => {
    it('should handle analytics endpoint errors', async () => {
      const apiClientAny = apiClient as any
      const originalShouldRetry = apiClientAny.shouldRetry
      apiClientAny.shouldRetry = () => false

      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({
          detail: 'Internal server error',
          message: 'Database connection failed'
        })
      })

      try {
        await apiClient.analytics.treatmentDistribution('30d')
        expect.fail('Should have thrown error')
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError)
        expect((error as ApiError).status).toBe(500)
      } finally {
        apiClientAny.shouldRetry = originalShouldRetry
      }
    })

    it('should handle invalid period parameters', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({
          detail: 'Invalid period',
          message: 'Period must be 7d, 30d, 90d, or 365d'
        })
      })

      try {
        await apiClient.analytics.treatmentDistribution('invalid' as any)
        expect.fail('Should have thrown error')
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError)
        expect((error as ApiError).status).toBe(400)
      }
    })
  })
})

describe('API Connection Tests - Messages & Flows', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiClient.setBaseURL('http://localhost:8000')
  })

  describe('Messages API', () => {
    it('should list messages with pagination', async () => {
      const mockResponse = {
        items: [
          {
            id: 'msg-1',
            patient_id: 'patient-1',
            content: 'Test message',
            type: 'text',
            status: 'sent',
            created_at: '2024-01-15T10:00:00-03:00'
          }
        ],
        total: 1,
        has_more: false
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockResponse
      })

      const result = await apiClient.messages.list({ page: 1, size: 20 })

      expect(result.items).toHaveLength(1)
      expect(result.total).toBe(1)
    })

    it('should send message', async () => {
      const messageData = {
        patient_id: 'patient-1',
        content: 'Hello patient',
        type: 'text'
      }

      const mockResponse = {
        id: 'msg-new',
        ...messageData,
        status: 'sent',
        created_at: '2024-01-15T10:00:00-03:00'
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockResponse
      })

      const result = await apiClient.messages.send(messageData)

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/messages',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(messageData)
        })
      )
      expect(result.id).toBe('msg-new')
    })

    it('should mark message as read', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({ message: 'Message marked as read' })
      })

      await apiClient.messages.markAsRead('msg-1')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/messages/msg-1/read',
        expect.objectContaining({
          method: 'PATCH'
        })
      )
    })
  })

  describe('Flows API', () => {
    it('should list flow templates', async () => {
      const mockTemplates = {
        items: [
          {
            id: 'template-1',
            name: 'Onboarding Flow',
            description: 'Welcome flow for new patients',
            is_active: true,
            created_at: '2024-01-01T00:00:00-03:00'
          }
        ],
        total: 1
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockTemplates
      })

      const result = await apiClient.flows.getTemplates()

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/templates/flows',
        expect.any(Object)
      )
      expect(result.items).toHaveLength(1)
    })

    it('should get flow state', async () => {
      const mockState = {
        patient_id: 'patient-1',
        template_id: 'template-1',
        current_day: 5,
        status: 'active',
        started_at: '2024-01-10T00:00:00-03:00'
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockState
      })

      const result = await apiClient.flows.getState('patient-1')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/flows/patient-1/state',
        expect.any(Object)
      )
      expect(result.current_day).toBe(5)
    })

    it('should advance flow', async () => {
      const mockState = {
        patient_id: 'patient-1',
        current_day: 6,
        status: 'active'
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockState
      })

      const result = await apiClient.flows.advance('patient-1', 6)

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/flows/patient-1/advance',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            target_day: 6,
            skip_conditions: false
          })
        })
      )
      expect(result.current_day).toBe(6)
    })

    it('should pause flow', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({
          patient_id: 'patient-1',
          status: 'paused'
        })
      })

      const result = await apiClient.flows.pause('patient-1')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/flows/patient-1/pause',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            reason: 'Manual pause'
          })
        })
      )
      expect(result.status).toBe('paused')
    })

    it('should resume flow', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({
          patient_id: 'patient-1',
          status: 'active'
        })
      })

      const result = await apiClient.flows.resume('patient-1')

      expect(result.status).toBe('active')
    })
  })
})
