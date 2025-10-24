/**
 * API Client - Main Export
 *
 * This file re-exports the refactored modular API client.
 * It maintains backward compatibility while providing a cleaner architecture.
 *
 * The API client is now organized into modules:
 * - core.ts: Base HTTP client functionality
 * - auth.ts: Authentication methods
 * - patients.ts: Patient management
 * - monthly-quiz.ts: Monthly quiz operations
 * - analytics.ts: Analytics and metrics
 *
 * Usage remains the same:
 * ```typescript
 * import { apiClient } from '@/lib/api-client'
 *
 * await apiClient.auth.login({ email, password })
 * await apiClient.patients.list()
 * await apiClient.monthlyQuiz.createLink({ ... })
 * ```
 */

// Re-export everything from the modular API client
export {
  apiClient,
  ApiClient,
  ApiError,
  type ApiResponse,
  type PaginatedResponse,
  type RequestOptions,
  // Auth types
  type LoginCredentials,
  type RegisterData,
  type User,
  type AuthResponse,
  type PasswordResetRequest,
  type PasswordResetConfirm,
  type PasswordChange,
  type AuthApi,
  // Patient types
  type Patient,
  type PatientCreate,
  type PatientUpdate,
  type PatientFilters,
  type PatientAppointment,
  type PatientDocument,
  type PatientMedicalHistory,
  type PatientStats,
  type PatientsApi,
  // Monthly Quiz types
  type QuizLink,
  type QuizLinkCreate,
  type QuizLinkBulkCreate,
  type QuizSession,
  type QuizStats,
  type QuizLinkStatus,
  type QuizHistory,
  type QuizTemplate,
  type QuizResponse,
  type QuizAnalytics,
  type MonthlyQuizApi,
  // Analytics types
  type DashboardMetrics,
  type PatientsAnalytics,
  type PerformanceMetrics,
  type TimeSeriesData,
  type AnalyticsReport,
  type PatientEngagementData,
  type TreatmentOutcomes,
  type AnalyticsApi,
} from './api-client/index'

// Default export for convenience
export { apiClient as default } from './api-client/index'
