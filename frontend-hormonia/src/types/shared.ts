/**
 * Shared types and constants for user roles and permissions
 *
 * IMPORTANT: This system has only 2 user roles:
 * - ADMIN: Full system access
 * - DOCTOR: Clinical operations
 *
 * Patients interact only via WhatsApp and quiz interface (no login required)
 */

export enum UserRole {
  ADMIN = 'admin',
  DOCTOR = 'doctor',
}

export const ROLE_LABELS: Record<UserRole, string> = {
  [UserRole.ADMIN]: 'Administrador',
  [UserRole.DOCTOR]: 'Médico',
}

export const ROLE_COLORS: Record<UserRole, string> = {
  [UserRole.ADMIN]: 'bg-purple-100 text-purple-800',
  [UserRole.DOCTOR]: 'bg-green-100 text-green-800',
}

/**
 * Get display label for a role
 */
export function getRoleLabel(role: string): string {
  if (!role) return role
  const normalizedRole = role.toLowerCase() as UserRole
  return ROLE_LABELS[normalizedRole] || role
}

/**
 * Get color classes for a role badge
 */
export function getRoleColor(role: string): string {
  if (!role) return 'bg-gray-100 text-gray-800'
  const normalizedRole = role.toLowerCase() as UserRole
  return ROLE_COLORS[normalizedRole] || 'bg-gray-100 text-gray-800'
}

/**
 * Check if a role string is valid
 */
export function isValidRole(role: string): boolean {
  if (!role) return false
  const normalizedRole = role.toLowerCase()
  return Object.values(UserRole).includes(normalizedRole as UserRole)
}

/**
 * Check if user has admin role
 */
export function isAdmin(role: string): boolean {
  if (!role) return false
  return role.toLowerCase() === UserRole.ADMIN
}

/**
 * Check if user has doctor role
 */
export function isDoctor(role: string): boolean {
  if (!role) return false
  return role.toLowerCase() === UserRole.DOCTOR
}

/**
 * Get all available roles
 */
export function getAllRoles(): UserRole[] {
  return Object.values(UserRole)
}

/**
 * Get role options for forms/dropdowns
 */
export function getRoleOptions(): Array<{ value: UserRole; label: string }> {
  return getAllRoles().map((role) => ({
    value: role,
    label: ROLE_LABELS[role],
  }))
}

/**
 * Validate role-based permissions
 */
export interface RolePermissions {
  canManageUsers: boolean
  canManagePatients: boolean
  canViewReports: boolean
  canManageFlows: boolean
  canAccessAdmin: boolean
  canManageSettings: boolean
  canImportPatients: boolean
  canAccessHiveMind: boolean
  canViewPhysicianDashboard: boolean
  canViewPhysicianPatients: boolean
}

/**
 * Get permissions for a specific role
 */
export function getRolePermissions(role: string): RolePermissions {
  if (!role) {
    return {
      canManageUsers: false,
      canManagePatients: false,
      canViewReports: false,
      canManageFlows: false,
      canAccessAdmin: false,
      canManageSettings: false,
      canImportPatients: false,
      canAccessHiveMind: false,
      canViewPhysicianDashboard: false,
      canViewPhysicianPatients: false,
    }
  }

  const normalizedRole = role.toLowerCase() as UserRole

  if (normalizedRole === UserRole.ADMIN) {
    return {
      canManageUsers: true,
      canManagePatients: true,
      canViewReports: true,
      canManageFlows: true,
      canAccessAdmin: true,
      canManageSettings: true,
      canImportPatients: true,
      canAccessHiveMind: true,
      canViewPhysicianDashboard: true,
      canViewPhysicianPatients: true,
    }
  }

  if (normalizedRole === UserRole.DOCTOR) {
    return {
      canManageUsers: false,
      canManagePatients: true,
      canViewReports: true,
      canManageFlows: false,
      canAccessAdmin: false,
      canManageSettings: false,
      canImportPatients: true,
      canAccessHiveMind: false,
      canViewPhysicianDashboard: true,
      canViewPhysicianPatients: true,
    }
  }

  // Default: no permissions
  return {
    canManageUsers: false,
    canManagePatients: false,
    canViewReports: false,
    canManageFlows: false,
    canAccessAdmin: false,
    canManageSettings: false,
    canImportPatients: false,
    canAccessHiveMind: false,
    canViewPhysicianDashboard: false,
    canViewPhysicianPatients: false,
  }
}

/**
 * Common pagination types
 */
export interface PaginationParams {
  page?: number
  size?: number
  limit?: number
}

/**
 * Common filter types
 */
export interface FilterParams {
  search?: string
  status?: string
  start_date?: string
  end_date?: string
}

/**
 * Common sort types
 */
export interface SortParams {
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

/**
 * Base entity interface
 */
export interface BaseEntity {
  id: string
  created_at: string
  updated_at: string
}

/**
 * Soft deletable entity interface
 */
export interface SoftDeletableEntity extends BaseEntity {
  deleted_at: string | null
}

/**
 * API response wrapper
 */
export interface ApiResponse<T = unknown> {
  success: boolean
  data?: T
  message?: string
  error?: string
  timestamp?: string
}

/**
 * Paginated response wrapper
 * Used for list endpoints that return paginated data
 */
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
  has_next?: boolean
  has_prev?: boolean
}

/**
 * API error response
 */
export interface ApiErrorResponse {
  error: string
  message: string
  status_code?: number
  details?: Record<string, unknown>
  timestamp?: string
}

/**
 * Query parameters for list endpoints
 */
export type ListQueryParams = PaginationParams & FilterParams & SortParams

/**
 * Status types
 */
export type Status = 'active' | 'inactive' | 'pending' | 'completed' | 'cancelled'

/**
 * Priority levels
 */
export type Priority = 'low' | 'medium' | 'high' | 'critical'

/**
 * Notification types
 */
export type NotificationType = 'info' | 'success' | 'warning' | 'error'

/**
 * Loading state
 */
export interface LoadingState {
  isLoading: boolean
  error: Error | null
}

/**
 * Form validation error
 */
export interface ValidationError {
  field: string
  message: string
}

/**
 * Audit metadata
 */
export interface AuditMetadata {
  created_by?: string
  updated_by?: string
  created_at: string
  updated_at: string
}
