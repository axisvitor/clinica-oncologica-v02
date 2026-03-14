/**
 * API Data Normalizers
 *
 * This module provides transformation functions to normalize backend API responses
 * to match frontend type expectations. It handles field naming inconsistencies
 * between backend and frontend.
 *
 * KEY MAPPINGS:
 * - Backend `full_name` -> Frontend `name` (User)
 * - Backend `flow_state` -> Frontend `status` (Patient)
 * - Bidirectional compatibility for both field names
 *
 * @module normalizers
 */

// ============================================================================
// USER NORMALIZATION
// ============================================================================

export interface BackendUser {
  id: string
  email: string
  full_name?: string | null
  name?: string | null
  role: string
  permissions?: string[]
  is_active: boolean
  created_at: string
  updated_at?: string
  session_id?: string
  token?: string
  avatar_url?: string
}

export interface FrontendUser {
  id: string
  email: string
  name: string
  full_name: string
  role: string
  permissions: string[]
  is_active: boolean
  created_at: string
  updated_at?: string
  session_id?: string
  token?: string
  avatar_url?: string
}

/**
 * Normalizes backend User to frontend User
 *
 * MAPPING:
 * - full_name (backend) -> name (frontend primary display name)
 * - full_name (backend) -> full_name (frontend for compatibility)
 * - Ensures permissions array exists
 *
 * @param backendUser - User data from backend API
 * @returns Normalized user for frontend consumption
 *
 * @example
 * ```typescript
 * const backendUser = {
 *   id: "123",
 *   email: "doctor@example.com",
 *   full_name: "Dr. Maria Silva",
 *   role: "doctor",
 *   is_active: true,
 *   created_at: "2025-01-01T00:00:00-03:00"
 * }
 *
 * const frontendUser = normalizeUser(backendUser)
 * // {
 * //   id: "123",
 * //   email: "doctor@example.com",
 * //   name: "Dr. Maria Silva",
 * //   full_name: "Dr. Maria Silva",
 * //   role: "doctor",
 * //   permissions: [],
 * //   is_active: true,
 * //   created_at: "2025-01-01T00:00:00-03:00"
 * // }
 * ```
 */
export function normalizeUser(backendUser: BackendUser): FrontendUser {
  // Priority: full_name > name > email
  const displayName = backendUser.full_name || backendUser.name || backendUser.email

  return {
    id: backendUser.id,
    email: backendUser.email,
    name: displayName, // Primary display name
    full_name: displayName, // Keep for backward compatibility
    role: backendUser.role,
    permissions: backendUser.permissions || [],
    is_active: backendUser.is_active,
    created_at: backendUser.created_at,
    updated_at: backendUser.updated_at,
    session_id: backendUser.session_id,
    token: backendUser.token,
    avatar_url: backendUser.avatar_url,
  }
}

/**
 * Denormalizes frontend User to backend User for API requests
 *
 * MAPPING:
 * - name (frontend) -> full_name (backend)
 * - Removes frontend-only fields
 *
 * @param frontendUser - User data from frontend
 * @returns Backend-compatible user object
 */
export function denormalizeUser(frontendUser: Partial<FrontendUser>): Partial<BackendUser> {
  const { name, ...rest } = frontendUser

  return {
    ...rest,
    full_name: frontendUser.full_name || name, // Use full_name if available, fallback to name
  }
}

// ============================================================================
// PATIENT NORMALIZATION
// ============================================================================

export type PatientStatus =
  | 'active'
  | 'inactive'
  | 'paused'
  | 'completed'
  | 'cancelled'
  | 'archived'
export type FlowState = 'onboarding' | 'active' | 'paused' | 'completed' | 'cancelled'

export interface BackendPatient {
  id: string
  name: string
  email?: string | null
  phone?: string | null
  cpf?: string | null
  birth_date?: string | null
  treatment_type?: string | null
  treatment_start_date?: string | null
  doctor_notes?: string | null
  diagnosis?: string | null
  treatment_phase?: string | null
  gender?: 'M' | 'F' | 'other'
  address?: Record<string, unknown>
  medical_info?: Record<string, unknown>
  flow_state?: string | null
  status?: string | null
  created_at?: string
  updated_at?: string
  doctor_id?: string | null
  current_day?: number | null
  timezone?: string
}

export interface FrontendPatient {
  id: string
  name: string
  email?: string
  phone?: string
  cpf?: string
  birth_date?: string
  treatment_type?: string
  treatment_start_date?: string
  doctor_notes?: string
  diagnosis?: string
  treatment_phase?: string
  gender?: 'M' | 'F' | 'other'
  address?: Record<string, unknown>
  medical_info?: Record<string, unknown>
  status: PatientStatus
  flow_state: string
  created_at?: string
  updated_at?: string
  doctor_id?: string
  current_day?: number
  last_contact?: string
  unread_count?: number
  timezone?: string
}

/**
 * Normalizes backend Patient to frontend Patient
 *
 * MAPPING:
 * - flow_state (backend) -> status (frontend primary status field)
 * - flow_state (backend) -> flow_state (frontend for compatibility)
 * - Handles null values and provides defaults
 *
 * @param backendPatient - Patient data from backend API
 * @returns Normalized patient for frontend consumption
 *
 * @example
 * ```typescript
 * const backendPatient = {
 *   id: "456",
 *   name: "João Silva",
 *   phone: "(11) 98765-4321",
 *   doctor_id: "789",
 *   flow_state: "active"
 * }
 *
 * const frontendPatient = normalizePatient(backendPatient)
 * // {
 * //   id: "456",
 * //   name: "João Silva",
 * //   phone: "(11) 98765-4321",
 * //   doctor_id: "789",
 * //   status: "active",
 * //   flow_state: "active"
 * // }
 * ```
 */
export function normalizePatient(backendPatient: BackendPatient): FrontendPatient {
  // Priority: flow_state > status > 'active' (default)
  const statusValue = (backendPatient.flow_state ||
    backendPatient.status ||
    'active') as PatientStatus
  const flowStateValue = backendPatient.flow_state || backendPatient.status || 'active'

  return {
    id: backendPatient.id,
    name: backendPatient.name,
    email: backendPatient.email ?? undefined,
    phone: backendPatient.phone ?? undefined,
    cpf: backendPatient.cpf ?? undefined,
    birth_date: backendPatient.birth_date ?? undefined,
    treatment_type: backendPatient.treatment_type ?? undefined,
    treatment_start_date: backendPatient.treatment_start_date ?? undefined,
    doctor_notes: backendPatient.doctor_notes ?? undefined,
    diagnosis: backendPatient.diagnosis ?? undefined,
    treatment_phase: backendPatient.treatment_phase ?? undefined,
    gender: backendPatient.gender,
    address: backendPatient.address,
    medical_info: backendPatient.medical_info,
    status: statusValue, // Primary status field for frontend
    flow_state: flowStateValue, // Keep for backend compatibility
    created_at: backendPatient.created_at,
    updated_at: backendPatient.updated_at,
    doctor_id: backendPatient.doctor_id ?? undefined,
    current_day: backendPatient.current_day ?? undefined,
    timezone: backendPatient.timezone ?? 'America/Sao_Paulo',
  }
}

/**
 * Denormalizes frontend Patient to backend Patient for API requests
 *
 * MAPPING:
 * - status (frontend) -> flow_state (backend)
 * - Removes frontend-only fields
 *
 * @param frontendPatient - Patient data from frontend
 * @returns Backend-compatible patient object
 */
export function denormalizePatient(
  frontendPatient: Partial<FrontendPatient>
): Partial<BackendPatient> {
  const { status, ...rest } = frontendPatient

  return {
    ...rest,
    flow_state: frontendPatient.flow_state || status, // Use flow_state if available, fallback to status
  }
}

/**
 * Normalizes array of backend patients
 */
export function normalizePatientList(backendPatients: BackendPatient[]): FrontendPatient[] {
  return backendPatients.map(normalizePatient)
}

// ============================================================================
// GENERIC NORMALIZATION HELPERS
// ============================================================================

/**
 * Normalizes date strings to ISO format
 * Handles various date formats from backend
 */
export function normalizeDate(date: string | null | undefined): string | undefined {
  if (!date) return undefined

  try {
    return new Date(date).toISOString()
  } catch {
    return undefined
  }
}

/**
 * Normalizes boolean values from various backend representations
 * Handles: true, false, "true", "false", 1, 0, null, undefined
 */
export function normalizeBoolean(value: unknown, defaultValue = false): boolean {
  if (value === null || value === undefined) return defaultValue
  if (typeof value === 'boolean') return value
  if (typeof value === 'string') return value.toLowerCase() === 'true'
  if (typeof value === 'number') return value !== 0
  return defaultValue
}

/**
 * Normalizes array values, ensuring they're always arrays
 * Handles: null, undefined, single values, arrays
 */
export function normalizeArray<T>(value: T | T[] | null | undefined, defaultValue: T[] = []): T[] {
  if (value === null || value === undefined) return defaultValue
  return Array.isArray(value) ? value : [value]
}

/**
 * Normalizes enum values with fallback
 * Ensures value is one of allowed values or returns default
 */
export function normalizeEnum<T extends string>(
  value: string | null | undefined,
  allowedValues: readonly T[],
  defaultValue: T
): T {
  if (!value) return defaultValue
  return allowedValues.includes(value as T) ? (value as T) : defaultValue
}

// ============================================================================
// TYPE GUARDS
// ============================================================================

/**
 * Type guard to check if object has backend User shape
 */
export function isBackendUser(obj: unknown): obj is BackendUser {
  if (!obj || typeof obj !== 'object') return false
  const user = obj as Record<string, unknown>
  return (
    typeof user['id'] === 'string' &&
    typeof user['email'] === 'string' &&
    typeof user['role'] === 'string' &&
    typeof user['is_active'] === 'boolean'
  )
}

/**
 * Type guard to check if object has backend Patient shape
 */
export function isBackendPatient(obj: unknown): obj is BackendPatient {
  if (!obj || typeof obj !== 'object') return false
  const patient = obj as Record<string, unknown>
  return typeof patient['id'] === 'string' && typeof patient['name'] === 'string'
}

// ============================================================================
// BATCH NORMALIZATION
// ============================================================================

/**
 * Normalizes paginated response with data normalization
 * Handles both v1 (items) and v2 (data) pagination formats
 */
export interface PaginatedResponse<T> {
  items?: T[]
  data?: T[]
  total: number
  page?: number
  size?: number
  pages?: number
  has_more?: boolean
  next_cursor?: string | null
}

export function normalizePaginatedResponse<B, F>(
  response: PaginatedResponse<B>,
  normalizer: (item: B) => F
): PaginatedResponse<F> {
  const rawItems = response.data || response.items || []
  const normalizedItems = rawItems.map(normalizer)

  return {
    ...response,
    data: normalizedItems,
    items: normalizedItems, // Keep both for compatibility
  }
}

// ============================================================================
// EXPORT ALL NORMALIZERS
// ============================================================================

export const normalizers = {
  user: {
    normalize: normalizeUser,
    denormalize: denormalizeUser,
    isValid: isBackendUser,
  },
  patient: {
    normalize: normalizePatient,
    denormalize: denormalizePatient,
    normalizeList: normalizePatientList,
    isValid: isBackendPatient,
  },
  helpers: {
    date: normalizeDate,
    boolean: normalizeBoolean,
    array: normalizeArray,
    enum: normalizeEnum,
  },
  pagination: {
    normalize: normalizePaginatedResponse,
  },
}

export default normalizers
