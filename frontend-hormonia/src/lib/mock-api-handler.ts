/**
 * Mock API Handler
 * Intercepts API requests and returns mock data
 */

import {
  getMockPatients,
  getMockPatientById,
  getMockMessages,
  getMockFlows,
  getMockFlowTemplates,
  getMockDashboardAnalytics,
  getMockEngagementData,
  getMockTreatmentDistribution,
  getMockAlerts,
  getMockQuizTemplates,
  getMockQuizSessions,
  getMockMonthlyQuizStats
} from '../mocks'
import { createLogger } from './logger'

const logger = createLogger('MockApiHandler')

/**
 * Simulate network delay
 */
async function simulateDelay(min: number = 200, max: number = 600): Promise<void> {
  const delay = Math.floor(Math.random() * (max - min + 1)) + min
  return new Promise<void>(resolve => setTimeout(resolve, delay))
}

/**
 * Simulate occasional errors (5% chance)
 */
function shouldSimulateError(): boolean {
  return Math.random() < 0.05
}

/**
 * Mock API Handler
 */
export class MockApiHandler {
  /**
   * Handle mock API request
   */
  async handleRequest<T>(endpoint: string, options?: RequestInit): Promise<T> {
    await simulateDelay()

    // Simulate occasional errors
    if (shouldSimulateError()) {
      throw new Error('Network error (simulated)')
    }

    const url = new URL(endpoint, 'http://localhost')
    const pathname = url.pathname
    const searchParams = url.searchParams
    const method = options?.method || 'GET'

    logger.debug(`${method} ${pathname}`)

    // Parse request body if present
    let body: unknown = null
    if (options?.body && typeof options.body === 'string') {
      try {
        body = JSON.parse(options.body)
      } catch (e) {
        logger.warn('Failed to parse request body', { error: e })
      }
    }

    // Route to appropriate handler
    if (pathname.startsWith('/api/v2/patients')) {
      return this.handlePatientsEndpoint(pathname, searchParams, method, body) as T
    } else if (pathname.startsWith('/api/v1/messages')) {
      return this.handleMessagesEndpoint(pathname, searchParams, method, body) as T
    } else if (pathname.startsWith('/api/v1/flows')) {
      return this.handleFlowsEndpoint(pathname, searchParams, method) as T
    } else if (pathname.startsWith('/api/v2/analytics')) {
      return this.handleAnalyticsEndpoint(pathname, searchParams) as T
    } else if (pathname.startsWith('/api/v1/alerts')) {
      return this.handleAlertsEndpoint(pathname, searchParams, method) as T
    } else if (pathname.startsWith('/api/v1/quiz')) {
      return this.handleQuizEndpoint(pathname, searchParams, method, body) as T
    } else if (pathname.startsWith('/api/v1/monthly-quiz')) {
      return this.handleMonthlyQuizEndpoint(pathname, searchParams, method, body) as T
    } else if (pathname.startsWith('/api/v1/reports')) {
      return this.handleReportsEndpoint(pathname, method) as T
    } else if (pathname.startsWith('/api/v1/admin/users')) {
      return this.handleAdminUsersEndpoint(pathname, searchParams, method, body) as T
    } else if (pathname.startsWith('/api/v1/ai')) {
      return this.handleAiEndpoint(pathname, method, body) as T
    }

    logger.warn('Unhandled endpoint', { pathname })
    return { message: 'Mock endpoint not implemented' } as T
  }

  /**
   * Handle patients endpoints
   */
  private handlePatientsEndpoint(pathname: string, params: URLSearchParams, method: string, body?: unknown): unknown {
    // GET /api/v2/patients - List patients
    if (pathname === '/api/v2/patients' && method === 'GET') {
      const search = params.get('search')
      const status = params.get('status')
      const treatmentType = params.get('treatment_type')

      return getMockPatients({
        page: parseInt(params.get('page') || '1'),
        size: parseInt(params.get('size') || '10'),
        ...(search && { search }),
        ...(status && { status }),
        ...(treatmentType && { treatment_type: treatmentType })
      })
    }

    // GET /api/v2/patients/:id - Get patient by ID
    const patientIdMatch = pathname.match(/^\/api\/v2\/patients\/([^/]+)$/)
    if (patientIdMatch && method === 'GET') {
      const patientId = patientIdMatch[1]
      if (patientId) {
        const patient = getMockPatientById(patientId)
        return patient || { error: 'Patient not found' }
      }
      return { error: 'Invalid patient ID' }
    }

    // POST /api/v2/patients - Create patient
    if (pathname === '/api/v2/patients' && method === 'POST') {
      const bodyData = (body as Record<string, unknown>) || {}
      return { id: `patient-${Date.now()}`, ...bodyData, created_at: new Date().toISOString() }
    }

    // PATCH /api/v2/patients/:id - Update patient
    if (patientIdMatch && method === 'PATCH') {
      const bodyData = (body as Record<string, unknown>) || {}
      return { id: patientIdMatch[1], ...bodyData, updated_at: new Date().toISOString() }
    }

    // DELETE /api/v2/patients/:id - Delete patient
    if (patientIdMatch && method === 'DELETE') {
      return { message: 'Patient deleted successfully' }
    }

    // GET /api/v2/patients/:id/timeline - Get patient timeline
    const timelineMatch = pathname.match(/^\/api\/v2\/patients\/([^/]+)\/timeline$/)
    if (timelineMatch && method === 'GET') {
      return { items: [], total: 0 }
    }

    return { error: 'Endpoint not found' }
  }

  /**
   * Handle messages endpoints
   */
  private handleMessagesEndpoint(pathname: string, params: URLSearchParams, method: string, body?: unknown): unknown {
    // GET /api/v1/messages - List messages
    if (pathname === '/api/v1/messages' && method === 'GET') {
      const patientId = params.get('patient_id')

      return getMockMessages({
        ...(patientId && { patient_id: patientId }),
        page: parseInt(params.get('page') || '1'),
        size: parseInt(params.get('size') || '20')
      })
    }

    // POST /api/v1/messages/send - Send message
    if (pathname === '/api/v1/messages/send' && method === 'POST') {
      const bodyData = (body as Record<string, unknown>) || {}
      return {
        id: `msg-${Date.now()}`,
        ...bodyData,
        status: 'sent',
        created_at: new Date().toISOString()
      }
    }

    return { error: 'Endpoint not found' }
  }

  /**
   * Handle flows endpoints
   */
  private handleFlowsEndpoint(pathname: string, params: URLSearchParams, method: string): unknown {
    // GET /api/v1/flows - List flows
    if (pathname === '/api/v1/flows' && method === 'GET') {
      const patientId = params.get('patient_id')
      const status = params.get('status')

      return getMockFlows({
        ...(patientId && { patient_id: patientId }),
        ...(status && { status })
      })
    }

    // GET /api/v1/flows/templates - List flow templates
    if (pathname === '/api/v1/flows/templates' && method === 'GET') {
      return getMockFlowTemplates()
    }

    // POST /api/v1/flows/start - Start flow
    if (pathname === '/api/v1/flows/start' && method === 'POST') {
      return {
        id: `flow-${Date.now()}`,
        status: 'active',
        started_at: new Date().toISOString()
      }
    }

    return { error: 'Endpoint not found' }
  }

  /**
   * Handle analytics endpoints
   */
  private handleAnalyticsEndpoint(pathname: string, params: URLSearchParams): unknown {
    if (pathname === '/api/v2/analytics/overview') {
      return getMockDashboardAnalytics()
    }

    if (pathname === '/api/v2/analytics/quiz-status') {
      return {
        distribution: { started: 35, completed: 310, cancelled: 18 },
        total: 363,
        filters: {}
      }
    }

    if (pathname === '/api/v2/analytics/completion-trend') {
      return {
        trend: [
          { year: 2024, month: 11, total: 60, completed: 52, completion_rate: 86.67 },
          { year: 2024, month: 12, total: 72, completed: 62, completion_rate: 86.11 },
          { year: 2025, month: 1, total: 80, completed: 70, completion_rate: 87.5 }
        ],
        period: { months: Number(params.get('months') || 6) }
      }
    }

    if (pathname === '/api/v2/analytics/patient-engagement') {
      return getMockEngagementData()
    }

    if (pathname === '/api/v2/analytics/treatment-distribution') {
      const period = (params.get('period') as '7d' | '30d' | '90d' | 'all') ?? '30d'
      return getMockTreatmentDistribution(period)
    }

    if (pathname === '/api/v2/analytics/risk-assessment') {
      return {
        success: true,
        risk_level_filter: params.get('risk_level') ?? 'all',
        lookback_days: Number(params.get('lookback_days') ?? 7),
        total_patients: 2,
        generated_at: new Date().toISOString(),
        risk_assessments: [
          {
            id: 'patient-1',
            patient_id: 'patient-1',
            name: 'João Silva',
            risk_level: 'high',
            risk_factors: ['Sem resposta há 5 dias'],
            last_response: new Date(Date.now() - 5 * 86400000).toISOString(),
            recommended_actions: ['Contato telefônico'],
          },
          {
            id: 'patient-2',
            patient_id: 'patient-2',
            name: 'Maria Santos',
            risk_level: 'medium',
            risk_factors: ['Baixo engajamento'],
            last_response: new Date(Date.now() - 2 * 86400000).toISOString(),
            recommended_actions: [],
          },
        ],
      }
    }

    return { error: 'Endpoint not found' }
  }

  /**
   * Handle alerts endpoints
   */
  private handleAlertsEndpoint(pathname: string, params: URLSearchParams, method: string): unknown {
    // GET /api/v1/alerts - List alerts
    if (pathname === '/api/v1/alerts' && method === 'GET') {
      const severity = params.get('severity')
      const acknowledgedParam = params.get('acknowledged')
      const acknowledged = acknowledgedParam === 'true' ? true : acknowledgedParam === 'false' ? false : undefined

      return getMockAlerts({
        page: parseInt(params.get('page') || '1'),
        size: parseInt(params.get('size') || '10'),
        ...(severity && { severity }),
        ...(acknowledged !== undefined && { acknowledged })
      })
    }

    // POST /api/v1/alerts/:id/acknowledge - Acknowledge alert
    const acknowledgeMatch = pathname.match(/^\/api\/v1\/alerts\/([^/]+)\/acknowledge$/)
    if (acknowledgeMatch && method === 'POST') {
      return { message: 'Alert acknowledged' }
    }

    // POST /api/v1/alerts/:id/resolve - Resolve alert
    const resolveMatch = pathname.match(/^\/api\/v1\/alerts\/([^/]+)\/resolve$/)
    if (resolveMatch && method === 'POST') {
      return { message: 'Alert resolved' }
    }

    return { error: 'Endpoint not found' }
  }

  /**
   * Handle quiz endpoints
   */
  private handleQuizEndpoint(pathname: string, params: URLSearchParams, method: string, body?: unknown): unknown {
    // GET /api/v1/quiz/templates - List quiz templates
    if (pathname === '/api/v1/quiz/templates' && method === 'GET') {
      return getMockQuizTemplates()
    }

    // POST /api/v1/quiz/templates - Create quiz template
    if (pathname === '/api/v1/quiz/templates' && method === 'POST') {
      const bodyData = (body as Record<string, unknown>) || {}
      return {
        id: `template-${Date.now()}`,
        ...bodyData,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }
    }

    // DELETE /api/v1/quiz/templates/:id - Delete quiz template
    const deleteTemplateMatch = pathname.match(/^\/api\/v1\/quiz\/templates\/([^/]+)$/)
    if (deleteTemplateMatch && method === 'DELETE') {
      return { message: 'Template deleted successfully' }
    }

    // GET /api/v1/quiz/templates/:id/analytics - Get template analytics
    const analyticsMatch = pathname.match(/^\/api\/v1\/quiz\/templates\/([^/]+)\/analytics$/)
    if (analyticsMatch && method === 'GET') {
      return {
        total_responses: Math.floor(Math.random() * 100),
        completion_rate: Math.floor(Math.random() * 100),
        average_completion_time: Math.floor(Math.random() * 30) + 5
      }
    }

    // GET /api/v1/quiz/sessions - List quiz sessions
    if (pathname === '/api/v1/quiz/sessions' && method === 'GET') {
      const patientId = params.get('patient_id')
      const status = params.get('status')

      return getMockQuizSessions({
        ...(patientId && { patient_id: patientId }),
        ...(status && { status })
      })
    }

    // POST /api/v1/quiz/sessions - Create quiz session
    if (pathname === '/api/v1/quiz/sessions' && method === 'POST') {
      const bodyData = (body as Record<string, unknown>) || {}
      return {
        id: `session-${Date.now()}`,
        ...bodyData,
        status: 'pending',
        link: `https://sistema.com/quiz/session-${Date.now()}`,
        created_at: new Date().toISOString(),
        expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString()
      }
    }

    return { error: 'Endpoint not found' }
  }

  /**
   * Handle monthly quiz endpoints
   */
  private handleMonthlyQuizEndpoint(pathname: string, params: URLSearchParams, method: string, body?: unknown): unknown {
    // GET /api/v1/monthly-quiz/stats/dashboard - Get monthly quiz stats
    if (pathname === '/api/v1/monthly-quiz/stats/dashboard' && method === 'GET') {
      return getMockMonthlyQuizStats()
    }

    // POST /api/v1/monthly-quiz/links - Create quiz link
    if (pathname === '/api/v1/monthly-quiz/links' && method === 'POST') {
      return {
        session_id: `session-${Date.now()}`,
        link: `https://sistema.com/quiz/session-${Date.now()}`,
        expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString()
      }
    }

    // POST /api/v1/monthly-quiz/links/bulk - Create bulk quiz links
    if (pathname === '/api/v1/monthly-quiz/links/bulk' && method === 'POST') {
      const bodyData = body as { patient_ids?: string[] } | null
      const patientIds = bodyData?.patient_ids || []
      return {
        created: patientIds.length,
        sessions: patientIds.map((id: string) => ({
          patient_id: id,
          session_id: `session-${Date.now()}-${id}`,
          link: `https://sistema.com/quiz/session-${Date.now()}-${id}`
        }))
      }
    }

    return { error: 'Endpoint not found' }
  }

  /**
   * Handle reports endpoints
   */
  private handleReportsEndpoint(pathname: string, method: string): unknown {
    // GET /api/v1/reports - List reports
    if (pathname === '/api/v1/reports' && method === 'GET') {
      return { items: [], total: 0, page: 1, size: 10, pages: 0 }
    }

    // POST /api/v1/reports/generate - Generate report
    if (pathname === '/api/v1/reports/generate' && method === 'POST') {
      return {
        id: `report-${Date.now()}`,
        status: 'pending',
        created_at: new Date().toISOString()
      }
    }

    return { error: 'Endpoint not found' }
  }

  /**
   * Handle admin users endpoints
   */
  private handleAdminUsersEndpoint(pathname: string, params: URLSearchParams, method: string, body?: unknown): unknown {
    // GET /api/v1/admin/users - List users
    if (pathname === '/api/v1/admin/users' && method === 'GET') {
      return { items: [], total: 0, page: 1, size: 10, pages: 0 }
    }

    // POST /api/v1/admin/users - Create user
    if (pathname === '/api/v1/admin/users' && method === 'POST') {
      const bodyData = (body as Record<string, unknown>) || {}
      return {
        id: `user-${Date.now()}`,
        ...bodyData,
        created_at: new Date().toISOString()
      }
    }

    return { error: 'Endpoint not found' }
  }

  /**
   * Handle AI endpoints
   */
  private handleAiEndpoint(pathname: string, method: string, _body?: unknown): unknown {
    // POST /api/v1/ai/chat - AI chat
    if (pathname === '/api/v1/ai/chat' && method === 'POST') {
      return {
        response: 'Esta é uma resposta mockada do AI. O sistema real de AI será integrado posteriormente.',
        confidence: 0.85
      }
    }

    // POST /api/v1/ai/analyze - AI analysis
    if (pathname === '/api/v1/ai/analyze' && method === 'POST') {
      return {
        analysis: 'Análise mockada dos dados fornecidos',
        insights: ['Insight 1', 'Insight 2']
      }
    }

    return { error: 'Endpoint not found' }
  }
}

export const mockApiHandler = new MockApiHandler()
