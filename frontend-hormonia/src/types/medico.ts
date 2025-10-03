// ============================================================================
// MEDICO TYPES
// ============================================================================

import type { AdminUser } from './admin'

/**
 * Médico User Interface
 * Extends AdminUser with medico-specific fields
 */
export interface MedicoUser extends AdminUser {
  /** CRM do médico */
  crm: string

  /** Especialidade médica */
  especialidade: string

  /** Conselho regional (ex: CRM-SC, CRM-SP) */
  conselho_regional: string

  /** IDs dos pacientes atribuídos a este médico */
  pacientes_atribuidos: string[]
}

/**
 * Medico Authentication State
 */
export interface MedicoAuthState {
  /** Current logged-in medico user */
  user: MedicoUser | null

  /** Whether user is authenticated */
  isAuthenticated: boolean

  /** Loading state during authentication */
  isLoading: boolean

  /** Authentication error message */
  error: string | null

  /** Session expiry timestamp */
  sessionExpiry: Date | null

  /** Cached list of paciente IDs */
  pacientes: string[]

  // Backward compatibility properties
  /** @deprecated Use 'user' instead */
  medico?: MedicoUser | null

  /** @deprecated Firebase handles tokens internally */
  token?: string | undefined
}

/**
 * Medico Login Credentials
 */
export interface MedicoLoginCredentials {
  /** Email address */
  email: string

  /** Password */
  password: string

  /** Remember me flag for persistent session */
  rememberMe?: boolean
}

/**
 * Medico Login Response
 */
export interface MedicoLoginResponse {
  /** Whether login was successful */
  success: boolean

  /** Authenticated medico user (if successful) */
  user?: MedicoUser

  /** Access token (JWT) */
  token?: string

  /** Refresh token for session renewal */
  refreshToken?: string

  /** Error message (if failed) */
  error?: string

  /** Redirect URL after successful login */
  redirectTo?: string
}

/**
 * Medico Profile Update Data
 */
export interface MedicoProfileUpdate {
  /** Full name */
  full_name?: string

  /** CRM number */
  crm?: string

  /** Medical specialty */
  especialidade?: string

  /** Regional council */
  conselho_regional?: string

  /** Email address */
  email?: string

  /** Phone number */
  phone?: string

  /** Profile picture URL */
  avatar_url?: string
}

/**
 * Medico Session Info
 */
export interface MedicoSessionInfo {
  /** Session ID */
  id: string

  /** Medico user ID */
  medico_id: string

  /** Session start timestamp */
  started_at: Date

  /** Session expiry timestamp */
  expires_at: Date

  /** Last activity timestamp */
  last_activity: Date

  /** Whether session is valid */
  is_valid: boolean
}

/**
 * Paciente Assignment
 */
export interface PacienteAssignment {
  /** Patient ID */
  paciente_id: string

  /** Medico ID */
  medico_id: string

  /** Assignment date */
  assigned_at: Date

  /** Whether assignment is active */
  is_active: boolean

  /** Assignment notes */
  notes?: string
}

/**
 * Medico Permissions
 */
export const MEDICO_PERMISSIONS = {
  /** Read patient records */
  READ_PACIENTES: 'read:pacientes',

  /** Write consultation notes */
  WRITE_CONSULTAS: 'write:consultas',

  /** Read exam results */
  READ_EXAMES: 'read:exames',

  /** Write prescriptions */
  WRITE_PRESCRICOES: 'write:prescricoes',

  /** Read treatment protocols */
  READ_PROTOCOLOS: 'read:protocolos',

  /** Write treatment protocols */
  WRITE_PROTOCOLOS: 'write:protocolos',

  /** Read medical history */
  READ_HISTORICO: 'read:historico',

  /** Request lab tests */
  REQUEST_EXAMES: 'request:exames',

  /** Schedule appointments */
  SCHEDULE_CONSULTAS: 'schedule:consultas',

  /** Access medical reports */
  READ_RELATORIOS: 'read:relatorios'
} as const

/**
 * Medico Permission Type
 */
export type MedicoPermission = typeof MEDICO_PERMISSIONS[keyof typeof MEDICO_PERMISSIONS]

/**
 * Medico Role Validation
 * Note: Firebase custom claims may use 'medico' but TypeScript types use 'doctor'
 */
export interface MedicoRoleValidation {
  /** Whether user has valid medico role */
  isValid: boolean

  /** Role name (Firebase claims use 'medico', TypeScript types use 'doctor') */
  role: 'medico' | 'doctor' | string

  /** Custom claims from Firebase */
  claims: Record<string, unknown>

  /** Error message if invalid */
  error?: string
}

// ============================================================================
// TYPE GUARDS
// ============================================================================

/**
 * Type guard to check if a user is a MedicoUser
 */
export function isMedicoUser(user: unknown): user is MedicoUser {
  if (!user || typeof user !== 'object') return false

  const u = user as Record<string, unknown>

  return (
    typeof u['id'] === 'string' &&
    typeof u['email'] === 'string' &&
    typeof u['role'] === 'string' &&
    u['role'] === 'doctor' &&
    typeof u['crm'] === 'string' &&
    typeof u['especialidade'] === 'string' &&
    typeof u['conselho_regional'] === 'string' &&
    Array.isArray(u['pacientes_atribuidos'])
  )
}

/**
 * Type guard to check if a response is a successful MedicoLoginResponse
 */
export function isSuccessfulMedicoLogin(
  response: MedicoLoginResponse
): response is Required<Pick<MedicoLoginResponse, 'success' | 'user' | 'token'>> & MedicoLoginResponse {
  return response.success === true && !!response.user && !!response.token
}

// ============================================================================
// UTILITY TYPES
// ============================================================================

/**
 * Medico creation data (for registration/admin creation)
 */
export type MedicoCreateData = Omit<
  MedicoUser,
  'id' | 'created_at' | 'updated_at' | 'last_login' | 'login_count' | 'failed_login_attempts' | 'locked_until'
>

/**
 * Medico update data (partial updates allowed)
 */
export type MedicoUpdateData = Partial<
  Pick<
    MedicoUser,
    | 'full_name'
    | 'email'
    | 'crm'
    | 'especialidade'
    | 'conselho_regional'
    | 'is_active'
    | 'two_factor_enabled'
    | 'pacientes_atribuidos'
  >
>