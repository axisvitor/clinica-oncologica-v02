/**
 * Authentication Context Helpers
 *
 * This module provides helper functions for managing authentication context,
 * user permissions, and auth-related state throughout the application.
 *
 * Features:
 * - Authentication state management
 * - Permission checking utilities
 * - Role-based access control
 * - Session validation
 * - Auth context providers
 */

import { createContext, useContext } from 'react'

// Removed Supabase imports - using generic types
type UserMetadata = {
  full_name?: string
  name?: string
  role?: string
  [key: string]: unknown
}

type User = {
  id: string
  email?: string | null
  user_metadata?: UserMetadata
  created_at: string
  last_sign_in_at?: string | null
}

type Session = {
  access_token?: string
  expires_at?: number
}

// Extended user interface with application-specific fields
export interface AppUser {
  id: string
  email: string
  full_name?: string
  role?: string
  is_active: boolean
  permissions?: string[]
  created_at: string
  last_sign_in_at?: string
  metadata?: Record<string, unknown>
}

// Permission and role definitions
export interface Permission {
  id: string
  name: string
  description: string
  resource: string
  action: string
}

export interface Role {
  id: string
  name: string
  description: string
  permissions: Permission[]
  hierarchy_level: number
}

// Auth context interface
export interface AuthContextValue {
  // User state
  user: AppUser | null
  session: Session | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null

  // Auth methods
  signIn: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  signUp: (email: string, password: string, metadata?: Record<string, unknown>) => Promise<void>
  resetPassword: (email: string) => Promise<void>
  updatePassword: (password: string) => Promise<void>
  refreshSession: () => Promise<void>

  // Permission methods
  hasPermission: (permission: string, resource?: string) => boolean
  hasRole: (role: string) => boolean
  hasAnyRole: (roles: string[]) => boolean
  hasAllPermissions: (permissions: string[]) => boolean
  hasAnyPermission: (permissions: string[]) => boolean
  canAccessResource: (resource: string, action: string) => boolean
  getPermissionLevel: (resource: string) => number

  // Utility methods
  isAdmin: () => boolean
  isSuperAdmin: () => boolean
  getDisplayName: () => string
  getUserInitials: () => string
  isSessionValid: () => boolean
  getSessionTimeLeft: () => number
}

// Create auth context
export const AuthContext = createContext<AuthContextValue | undefined>(undefined)

// Hook to use auth context
export function useAuthContext(): AuthContextValue {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuthContext must be used within an AuthProvider')
  }
  return context
}

// Default role hierarchy
const ROLE_HIERARCHY: Record<string, number> = {
  'super_admin': 100,
  'admin': 80,
  'manager': 60,
  'doctor': 50,
  'nurse': 40,
  'staff': 30,
  'reception': 20,
  'user': 10,
  'patient': 5
}

// Default permissions
const DEFAULT_PERMISSIONS: Record<string, Permission[]> = {
  super_admin: [
    { id: 'all', name: 'All Permissions', description: 'Full system access', resource: '*', action: '*' }
  ],
  admin: [
    { id: 'users.manage', name: 'Manage Users', description: 'Create, edit, delete users', resource: 'users', action: 'manage' },
    { id: 'patients.manage', name: 'Manage Patients', description: 'Full patient management', resource: 'patients', action: 'manage' },
    { id: 'system.configure', name: 'System Configuration', description: 'System settings', resource: 'system', action: 'configure' }
  ],
  manager: [
    { id: 'patients.manage', name: 'Manage Patients', description: 'Full patient management', resource: 'patients', action: 'manage' },
    { id: 'reports.view', name: 'View Reports', description: 'Access reports', resource: 'reports', action: 'view' }
  ],
  doctor: [
    { id: 'patients.read', name: 'View Patients', description: 'View patient information', resource: 'patients', action: 'read' },
    { id: 'patients.update', name: 'Update Patients', description: 'Update patient information', resource: 'patients', action: 'update' },
    { id: 'treatments.manage', name: 'Manage Treatments', description: 'Manage patient treatments', resource: 'treatments', action: 'manage' }
  ],
  nurse: [
    { id: 'patients.read', name: 'View Patients', description: 'View patient information', resource: 'patients', action: 'read' },
    { id: 'patients.update', name: 'Update Patients', description: 'Update patient information', resource: 'patients', action: 'update' }
  ],
  staff: [
    { id: 'patients.read', name: 'View Patients', description: 'View patient information', resource: 'patients', action: 'read' }
  ],
  reception: [
    { id: 'patients.read', name: 'View Patients', description: 'View patient information', resource: 'patients', action: 'read' },
    { id: 'appointments.manage', name: 'Manage Appointments', description: 'Schedule appointments', resource: 'appointments', action: 'manage' }
  ],
  user: [
    { id: 'profile.read', name: 'View Profile', description: 'View own profile', resource: 'profile', action: 'read' },
    { id: 'profile.update', name: 'Update Profile', description: 'Update own profile', resource: 'profile', action: 'update' }
  ],
  patient: [
    { id: 'profile.read', name: 'View Profile', description: 'View own profile', resource: 'profile', action: 'read' },
    { id: 'profile.update', name: 'Update Profile', description: 'Update own profile', resource: 'profile', action: 'update' },
    { id: 'appointments.view', name: 'View Appointments', description: 'View own appointments', resource: 'appointments', action: 'view' }
  ]
}

/**
 * Convert Supabase User to AppUser
 */
export function convertSupabaseUser(user: User): AppUser {
  return {
    id: user.id,
    email: user.email || '',
    full_name: user.user_metadata?.['full_name'] || user.user_metadata?.['name'] || '',
    role: user.user_metadata?.['role'] || 'user',
    is_active: true,
    permissions: getUserPermissions(user.user_metadata?.['role'] || 'user'),
    created_at: user.created_at,
    last_sign_in_at: user.last_sign_in_at as string,
    metadata: user.user_metadata
  }
}

/**
 * Get permissions for a role
 */
export function getUserPermissions(role: string): string[] {
  const permissions = DEFAULT_PERMISSIONS[role] || DEFAULT_PERMISSIONS['user']
  return (permissions || []).map(p => p.id)
}

/**
 * Check if user has a specific permission
 */
export function hasPermission(user: AppUser | null, permission: string, resource?: string): boolean {
  if (!user || !user.is_active) return false

  // Super admin has all permissions
  if (user.role === 'super_admin') return true

  // Check if user has the specific permission
  if (user.permissions?.includes(permission)) return true

  // Check if user has wildcard permission for resource
  if (resource && user.permissions?.includes(`${resource}.*`)) return true

  // Check if user has all permissions wildcard
  if (user.permissions?.includes('*') || user.permissions?.includes('all')) return true

  return false
}

/**
 * Check if user has a specific role
 */
export function hasRole(user: AppUser | null, role: string): boolean {
  if (!user || !user.is_active) return false
  return user.role === role
}

/**
 * Check if user has any of the specified roles
 */
export function hasAnyRole(user: AppUser | null, roles: string[]): boolean {
  if (!user || !user.is_active) return false
  return roles.includes(user.role || '')
}

/**
 * Check if user has all specified permissions
 */
export function hasAllPermissions(user: AppUser | null, permissions: string[]): boolean {
  if (!user || !user.is_active) return false
  return permissions.every(permission => hasPermission(user, permission))
}

/**
 * Check if user has any of the specified permissions
 */
export function hasAnyPermission(user: AppUser | null, permissions: string[]): boolean {
  if (!user || !user.is_active) return false
  return permissions.some(permission => hasPermission(user, permission))
}

/**
 * Check if user can access a resource with specific action
 */
export function canAccessResource(user: AppUser | null, resource: string, action: string): boolean {
  if (!user || !user.is_active) return false

  // Check specific permission
  if (hasPermission(user, `${resource}.${action}`, resource)) return true

  // Check manage permission (implies all actions)
  if (hasPermission(user, `${resource}.manage`, resource)) return true

  return false
}

/**
 * Get permission level for a resource (based on role hierarchy)
 */
export function getPermissionLevel(user: AppUser | null, resource: string): number {
  if (!user || !user.is_active) return 0

  const roleLevel = ROLE_HIERARCHY[user.role || 'user'] || 0

  // Check if user has specific permissions for this resource
  const resourcePermissions = user.permissions?.filter(p => p.startsWith(resource)) || []
  if (resourcePermissions.length > 0) {
    return roleLevel + 10 // Bonus for having specific permissions
  }

  return roleLevel
}

/**
 * Check if user is admin (admin or super_admin)
 */
export function isAdmin(user: AppUser | null): boolean {
  return hasAnyRole(user, ['admin', 'super_admin'])
}

/**
 * Check if user is super admin
 */
export function isSuperAdmin(user: AppUser | null): boolean {
  return hasRole(user, 'super_admin')
}

/**
 * Get user display name
 */
export function getDisplayName(user: AppUser | null): string {
  if (!user) return 'Guest'

  const fullName = user.full_name?.trim()
  if (fullName) {
    return fullName
  }

  const [emailLocalPart] = (user.email || '').split('@')
  if (emailLocalPart) {
    return emailLocalPart
  }

  return 'User'
}

/**
 * Get user initials for avatar
 */
export function getUserInitials(user: AppUser | null): string {
  if (!user) return 'G'

  const displayName = getDisplayName(user)
  const parts = displayName.split(' ')

  if (parts.length >= 2) {
    const firstInitial = parts[0]?.charAt(0) ?? ''
    const secondInitial = parts[1]?.charAt(0) ?? ''
    const initials = `${firstInitial}${secondInitial}`.trim()
    if (initials) {
      return initials.toUpperCase()
    }
  }

  return displayName.substring(0, Math.min(2, displayName.length)).toUpperCase()
}

/**
 * Check if session is valid
 */
export function isSessionValid(session: Session | null): boolean {
  if (!session) return false

  const now = Math.floor(Date.now() / 1000)
  const expiresAt = session.expires_at || 0

  return expiresAt > now
}

/**
 * Get time left in session (in seconds)
 */
export function getSessionTimeLeft(session: Session | null): number {
  if (!session) return 0

  const now = Math.floor(Date.now() / 1000)
  const expiresAt = session.expires_at || 0

  return Math.max(0, expiresAt - now)
}

/**
 * Check if session is expiring soon (within 5 minutes)
 */
export function isSessionExpiringSoon(session: Session | null): boolean {
  const timeLeft = getSessionTimeLeft(session)
  return timeLeft > 0 && timeLeft < 300 // 5 minutes
}

/**
 * Format role name for display
 */
export function formatRoleName(role: string): string {
  return role
    .replace(/_/g, ' ')
    .replace(/\b\w/g, l => l.toUpperCase())
}

/**
 * Get role description
 */
export function getRoleDescription(role: string): string {
  const descriptions: Record<string, string> = {
    super_admin: 'Full system access with all permissions',
    admin: 'Administrative access to manage users and system',
    manager: 'Management access to oversee operations',
    doctor: 'Medical professional with patient care access',
    nurse: 'Nursing staff with patient care access',
    staff: 'General staff with limited access',
    reception: 'Reception staff with appointment management',
    user: 'Standard user with basic access',
    patient: 'Patient with access to own information'
  }

  return descriptions[role] || 'Standard user access'
}

/**
 * Get available roles for user management
 */
export function getAvailableRoles(currentUserRole: string): string[] {
  const currentLevel = ROLE_HIERARCHY[currentUserRole] || 0

  return Object.entries(ROLE_HIERARCHY)
    .filter(([_, level]) => level < currentLevel)
    .map(([role, _]) => role)
    .sort((a, b) => (ROLE_HIERARCHY[b] || 0) - (ROLE_HIERARCHY[a] || 0))
}

/**
 * Check if current user can manage target user
 */
export function canManageUser(currentUser: AppUser | null, targetUserRole: string): boolean {
  if (!currentUser || !currentUser.is_active) return false

  const currentLevel = ROLE_HIERARCHY[currentUser.role || 'user'] || 0
  const targetLevel = ROLE_HIERARCHY[targetUserRole] || 0

  return currentLevel > targetLevel
}

/**
 * Validate permission string format
 */
export function isValidPermission(permission: string): boolean {
  // Permission format: resource.action or wildcard patterns
  const permissionRegex = /^(\*|[a-z_]+)\.(\*|[a-z_]+)$|^(\*|all)$/
  return permissionRegex.test(permission)
}

/**
 * Parse permission string
 */
export function parsePermission(permission: string): { resource: string; action: string } | null {
  if (permission === '*' || permission === 'all') {
    return { resource: '*', action: '*' }
  }

  const parts = permission.split('.')
  if (parts.length === 2) {
    const [resource, action] = parts
    if (resource && action) {
      return { resource, action }
    }
  }

  return null
}

/**
 * Create permission helpers for a specific user
 */
export function createUserPermissionHelpers(user: AppUser | null) {
  return {
    hasPermission: (permission: string, resource?: string) => hasPermission(user, permission, resource),
    hasRole: (role: string) => hasRole(user, role),
    hasAnyRole: (roles: string[]) => hasAnyRole(user, roles),
    hasAllPermissions: (permissions: string[]) => hasAllPermissions(user, permissions),
    hasAnyPermission: (permissions: string[]) => hasAnyPermission(user, permissions),
    canAccessResource: (resource: string, action: string) => canAccessResource(user, resource, action),
    getPermissionLevel: (resource: string) => getPermissionLevel(user, resource),
    isAdmin: () => isAdmin(user),
    isSuperAdmin: () => isSuperAdmin(user),
    getDisplayName: () => getDisplayName(user),
    getUserInitials: () => getUserInitials(user),
    canManageUser: (targetUserRole: string) => canManageUser(user, targetUserRole)
  }
}
