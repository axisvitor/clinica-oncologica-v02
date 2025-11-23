import { useCallback, useMemo } from 'react'
import { User, PermissionConfig } from './types'

interface UsePermissionsOptions {
  user: User | null
  strictMode?: boolean // If true, requires exact permission match
}

export function usePermissions({ user, strictMode = false }: UsePermissionsOptions) {
  const permissions = useMemo(() => user?.permissions ?? [], [user])
  const role = user?.role ?? 'guest'
  const isActive = Boolean(user?.is_active)

  const hasPermission = useCallback((permission: string): boolean => {
    if (permissions.length === 0) return false

    if (strictMode) {
      return permissions.includes(permission)
    }

    // Support wildcard permissions (e.g., "admin.*" grants "admin.users", "admin.settings")
    return permissions.some(userPerm => {
      if (userPerm === permission) return true
      if (userPerm.endsWith('.*')) {
        const basePermission = userPerm.slice(0, -2)
        return permission.startsWith(basePermission + '.')
      }
      return false
    })
  }, [permissions, strictMode])

  const hasRole = useCallback((roleToCheck: string): boolean => {
    return role === roleToCheck
  }, [role])

  const hasAnyRole = useCallback((roles: string[]): boolean => {
    return roles.some(role => hasRole(role))
  }, [hasRole])

  const hasAllPermissions = useCallback((permissions: string[]): boolean => {
    return permissions.every(permission => hasPermission(permission))
  }, [hasPermission])

  const hasAnyPermission = useCallback((permissions: string[]): boolean => {
    return permissions.some(permission => hasPermission(permission))
  }, [hasPermission])

  const isAdmin = useCallback((): boolean => {
    return hasRole('admin') || hasPermission('admin.*')
  }, [hasRole, hasPermission])

  const isSuperAdmin = useCallback((): boolean => {
    return hasRole('superadmin') || hasPermission('superadmin.*')
  }, [hasRole, hasPermission])

  const canAccessResource = useCallback((resource: string, action: string = 'read'): boolean => {
    const permission = `${resource}.${action}`
    return hasPermission(permission) || isAdmin()
  }, [hasPermission, isAdmin])

  const getPermissionLevel = useCallback((basePermission: string): 'none' | 'read' | 'write' | 'admin' => {
    if (hasPermission(`${basePermission}.admin`) || isAdmin()) return 'admin'
    if (hasPermission(`${basePermission}.write`)) return 'write'
    if (hasPermission(`${basePermission}.read`)) return 'read'
    return 'none'
  }, [hasPermission, isAdmin])

  const permissionConfig: PermissionConfig = useMemo(() => ({
    permissions,
    role
  }), [permissions, role])

  const totalPermissions = permissions.length

  const permissionSummary = useMemo(() => ({
    isAdmin: isAdmin(),
    isSuperAdmin: isSuperAdmin(),
    totalPermissions,
    role,
    isActive
  }), [totalPermissions, role, isActive, isAdmin, isSuperAdmin])

  return {
    // Basic permission checks
    hasPermission,
    hasRole,
    hasAnyRole,
    hasAllPermissions,
    hasAnyPermission,

    // Convenience checks
    isAdmin,
    isSuperAdmin,
    canAccessResource,
    getPermissionLevel,

    // Data
    permissionConfig,
    permissionSummary,

    // Raw user data for advanced use cases
    user
  }
}
