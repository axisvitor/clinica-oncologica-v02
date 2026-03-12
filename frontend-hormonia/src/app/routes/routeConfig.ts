/**
 * Route Configuration
 *
 * Centralized route constants for type-safe navigation.
 * All route paths in the application should be defined here.
 */

export const ROUTES = {
  // Public routes
  ROOT: '/',
  LOGIN: '/login',
  UNAUTHORIZED: '/unauthorized',

  AUTH: {
    PASSWORD_RESET_REQUEST: '/auth/password/reset-request',
    PASSWORD_RESET_CONFIRM: '/auth/password/reset-confirm',
    LEGACY_RESET_PASSWORD: '/reset-password',
    FIRST_ACCESS: '/primeiro-acesso',
  },

  // Main dashboard
  DASHBOARD: '/dashboard',

  // Patient management
  PATIENTS: {
    LIST: '/patients',
    DETAIL: '/patients/:id',
    IMPORT: '/patients/import',
  },

  // Communication
  MESSAGES: '/messages',
  WHATSAPP: '/whatsapp',

  // Quiz system
  QUIZ: '/quiz',
  MONTHLY_QUIZ: '/monthly-quiz',
  QUESTIONARIOS: '/questionarios',

  // Reports and analytics
  REPORTS: '/reports',
  ANALYTICS: '/analytics',
  ALERTS: '/alerts',

  // System management
  SETTINGS: '/settings',
  FLOWS: '/flows',
  DLQ: '/dlq',
  HIVE_MIND: '/hive-mind',

  // Admin system
  ADMIN: {
    ROOT: '/admin/*',
  },

  // Legacy physician compatibility routes
  MEDICO: {
    ROOT: '/medico',
    LOGIN: '/medico/login',
    DASHBOARD: '/medico/dashboard',
    PATIENTS: '/medico/pacientes',
    RECORD: '/medico/prontuario/:pacienteId',
  },

  // Physician routes
  PHYSICIAN: {
    DASHBOARD: '/physician/dashboard',
    PATIENT_DETAIL: '/physician/patients/:id',
  },
} as const

/**
 * Helper function to build patient detail route
 */
export const buildPatientDetailRoute = (id: string | number): string => {
  return `/patients/${id}`
}

/**
 * Helper function to build physician patient detail route
 */
export const buildPhysicianPatientDetailRoute = (id: string | number): string => {
  return `/physician/patients/${id}`
}

/**
 * Type for route keys
 */
export type RouteKey = keyof typeof ROUTES
