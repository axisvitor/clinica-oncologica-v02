import { useCallback, useMemo } from 'react'
import { User, PermissionConfig } from './types'

interface UsePermissionsOptions {
  user: User | null
  strictMode?: boolean // If true, requires exact permission match
}

export function usePermissions({ user, strictMode = false }: UsePermissionsOptions) {
  // Early return if no user
  if (!user) {
    return {
      hasPermission: () => false,
      hasRole: () => false,
      hasAnyRole: () => false,
      hasAllPermissions: () => false,
      hasAnyPermission: () => false,
      isAdmin: () => false,
      isSuperAdmin: () => false,
      canAccessResource: () => false,
      getPermissionLevel: () => 'none' as const,
      permissionConfig: { permissions: [], role: 'guest' },
      permissionSummary: {
        isAdmin: false,
        isSuperAdmin: false,
        totalPermissions: 0,
        role: 'guest',
        isActive: false
      },
      user: null
    }
  }
  const hasPermission = useCallback((permission: string): boolean => {
    if (!user?.permissions) return false

    if (strictMode) {
      return user.permissions.includes(permission)
    }

    // Support wildcard permissions (e.g., "admin.*" grants "admin.users", "admin.settings")
    return user.permissions.some(userPerm => {
      if (userPerm === permission) return true
      if (userPerm.endsWith('.*')) {
        const basePermission = userPerm.slice(0, -2)
        return permission.startsWith(basePermission + '.')
      }
      return false
    })
  }, [user, strictMode])

  const hasRole = useCallback((role: string): boolean => {
    return user?.role === role
  }, [user])

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
    permissions: user?.permissions || [],
    role: user?.role || 'guest'
  }), [user])

  const permissionSummary = useMemo(() => ({
    isAdmin: isAdmin(),
    isSuperAdmin: isSuperAdmin(),
    totalPermissions: user?.permissions?.length || 0,
    role: user?.role || 'guest',
    isActive: user?.is_active || false
  }), [user, isAdmin, isSuperAdmin])

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