/**
 * API Client - Main Entry Point
 *
 * This is the refactored API client with modular architecture.
 * Each domain (auth, patients, quiz, etc.) has its own module.
 *
 * Usage:
 * ```typescript
 * import { apiClient } from '@/lib/api-client'
 *
 * // Authentication
 * await apiClient.auth.login({ email, password })
 *
 * // Patients
 * const patients = await apiClient.patients.list()
 *
 * // Monthly Quiz
 * await apiClient.monthlyQuiz.createLink({ patient_id, quiz_template_id })
 * ```
 */

import { ApiClientCore } from './core'
import { createAuthApi } from './auth'
import { createPatientsApi } from './patients'
import { createAppointmentsApi } from './appointments'
import { createTreatmentsApi } from './treatments'
import { createMedicationsApi } from './medications'
import { createMonthlyQuizApi } from './monthly-quiz'
import { createAnalyticsApi } from './analytics'
import { createAdminApi } from './admin'
import { createDashboardApi } from './dashboard'
import { createMessagesApi, type MessagesApi } from './messages'
import { createFlowsApi, type FlowsApi } from './flows'
import { createAlertsApi, type AlertsApi } from './alerts'
import { createReportsApi, type ReportsApi } from './reports'
import { createLegacyAdminApi, type LegacyAdminApi } from './admin-legacy'
import { createAdminUsersApi, type AdminUsersApi } from './admin-users'
import { createAiApi, type AiApi } from './ai'
import { createQuizApi, type QuizApi } from './quiz'
import { createQuizTemplatesApi, type QuizTemplatesApi } from './quizzes'
import { createNotificationsApi, type NotificationsApi } from './notifications'
import { createPhysicianApi, type PhysicianApi } from './physician'
import { createTasksApi, TasksApi } from './tasks'
import { createHiveMindApi } from './hive-mind'
import { createLogger } from '../logger'
import * as appConfig from '../../config'

const logger = createLogger('ApiClient')

// Re-export core types
export type { ApiResponse, PaginatedResponse, RequestOptions } from './core'
export { ApiError } from './core'

// Re-export domain types
export type * from './auth'
export type * from './patients'
export type * from './appointments'
export type * from './treatments'
export type {
  Medication,
  MedicationCreate,
  MedicationUpdate,
  MedicationFilters,
  MedicationStats,
  MedicationRoute,
  MedicationSchedule,
  MedicationsApi,
} from './medications'
export type * from './monthly-quiz'
export type * from './analytics'
export type * from './admin'
export type * from './dashboard'
export type * from './tasks'
export type * from './hive-mind'

/**
 * Main API Client class
 * Extends core with domain-specific modules
 */
export class ApiClient extends ApiClientCore {
  // Domain modules
  public readonly auth: ReturnType<typeof createAuthApi>
  public readonly patients: ReturnType<typeof createPatientsApi>
  public readonly appointments: ReturnType<typeof createAppointmentsApi>
  public readonly treatments: ReturnType<typeof createTreatmentsApi>
  public readonly medications: ReturnType<typeof createMedicationsApi>
  public readonly monthlyQuiz: ReturnType<typeof createMonthlyQuizApi>
  public readonly analytics: ReturnType<typeof createAnalyticsApi>
  public readonly adminV2: ReturnType<typeof createAdminApi>
  public readonly dashboard: ReturnType<typeof createDashboardApi>
  public readonly tasks: TasksApi

  // Additional namespaces
  public readonly messages: MessagesApi
  public readonly flows: FlowsApi
  public readonly alerts: AlertsApi
  public readonly reports: ReportsApi
  public readonly admin: LegacyAdminApi
  public readonly adminUsers: AdminUsersApi
  public readonly ai: AiApi
  public readonly quiz: QuizApi
  public readonly quizzes: QuizTemplatesApi
  public readonly notifications: NotificationsApi
  public readonly physician: PhysicianApi
  public readonly hiveMind: ReturnType<typeof createHiveMindApi>

  constructor(baseURL: string) {
    super(baseURL)

    // Initialize domain modules
    this.auth = createAuthApi(this)
    this.patients = createPatientsApi(this)
    this.appointments = createAppointmentsApi(this)
    this.treatments = createTreatmentsApi(this)
    this.medications = createMedicationsApi(this)
    this.monthlyQuiz = createMonthlyQuizApi(this)
    this.analytics = createAnalyticsApi(this)
    this.adminV2 = createAdminApi(this)
    this.dashboard = createDashboardApi(this)
    this.tasks = createTasksApi(this)

    // Initialize additional namespaces
    this.messages = createMessagesApi(this)
    this.flows = createFlowsApi(this)
    this.alerts = createAlertsApi(this)
    this.reports = createReportsApi(this)
    this.admin = createLegacyAdminApi(this)
    this.adminUsers = createAdminUsersApi(this)
    this.ai = createAiApi(this)
    this.quiz = createQuizApi(this)
    this.quizzes = createQuizTemplatesApi(this)
    this.notifications = createNotificationsApi(this)
    this.physician = createPhysicianApi(this)
    this.hiveMind = createHiveMindApi(this)

    logger.log('API Client initialized with modular architecture')
  }

  /**
   * Clear all cached data
   */
  clearCache(): void {
    // Override if needed in the future for client-side caching
    logger.log('Cache cleared')
  }
}

/**
 * Get API URL with proper environment variable resolution
 *
 * Priority order:
 * 1. Runtime config API_BASE_URL (loaded async from config.ts)
 * 2. VITE_API_BASE_URL environment variable (base domain)
 * 3. VITE_API_URL environment variable (full API URL)
 * 4. Auto-detect from window location in production
 * 5. Localhost fallback for development
 */
const getApiUrl = (): string => {
  const configRecord = appConfig as unknown as Record<string, unknown>
  const runtimeApiBaseUrl =
    'API_BASE_URL' in configRecord && typeof configRecord['API_BASE_URL'] === 'string'
      ? configRecord['API_BASE_URL']
      : ''
  const compatGetApiUrl =
    'getApiUrl' in configRecord && typeof configRecord['getApiUrl'] === 'function'
      ? (configRecord['getApiUrl'] as () => string)
      : undefined

  // 1. Check runtime config (may be empty on initial load)
  if (runtimeApiBaseUrl.length > 0) {
    logger.debug('Using API_BASE_URL from runtime config:', runtimeApiBaseUrl)
    return runtimeApiBaseUrl
  }

  if (typeof compatGetApiUrl === 'function') {
    const compatUrl = compatGetApiUrl()
    if (typeof compatUrl === 'string' && compatUrl.length > 0) {
      const baseUrl = compatUrl.replace(/\/api\/v2$/, '')
      logger.debug('Using compat config getApiUrl():', baseUrl)
      return baseUrl
    }
  }

  // 2. Check VITE_API_BASE_URL (preferred for base domain)
  if (import.meta.env['VITE_API_BASE_URL']) {
    const baseUrl = import.meta.env['VITE_API_BASE_URL']
    logger.debug('Using VITE_API_BASE_URL:', baseUrl)
    return baseUrl
  }

  // 3. Check VITE_API_URL (full URL with /api/v2)
  if (import.meta.env['VITE_API_URL']) {
    const apiUrl = import.meta.env['VITE_API_URL']
    // Extract base URL by removing /api/v2 suffix
    const baseUrl = apiUrl.replace(/\/api\/v2$/, '')
    logger.debug('Using VITE_API_URL (extracted base):', baseUrl)
    return baseUrl
  }

  // 4. Auto-detect in production based on window location
  if (typeof window !== 'undefined') {
    const { protocol, hostname } = window.location

    // Production environments (Railway, custom domains)
    if (hostname !== 'localhost' && hostname !== '127.0.0.1') {
      const detectedUrl = `${protocol}//${hostname}`
      logger.debug('Auto-detected API URL from window location:', detectedUrl)
      return detectedUrl
    }
  }

  // 5. Development fallback
  logger.debug('Using localhost fallback for development')
  return (
    import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || 'http://localhost:8000'
  )
}

// Create singleton instance
export const apiClient = new ApiClient(getApiUrl())

// Default export
export default apiClient
