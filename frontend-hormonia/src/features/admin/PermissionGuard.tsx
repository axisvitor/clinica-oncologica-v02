import React from 'react'
import { useAuth } from '@/app/providers/AuthContext'
import type { User } from '@/types/auth'

const RESTRICTED_ADMIN_PERMISSIONS = [
  'admin.system.delete',
  'admin.users.delete_admin',
  'admin.backup.delete'
]

type PermissionLevel = 'none' | 'read' | 'write' | 'admin'

interface PermissionGuardProps {
  permissions?: string[]
  roles?: string[]
  resource?: string
  action?: string
  requireAll?: boolean
  customCheck?: (user: User | null) => boolean
  fallback?: React.ReactNode
  children: React.ReactNode
  allowUnauthenticated?: boolean
}

interface AccessHelpers {
  hasAnyPermission: (permissions: string[]) => boolean
  hasAllPermissions: (permissions: string[]) => boolean
  hasAnyRole: (roles: string[]) => boolean
  isAdminUser: () => boolean
  isSuperAdminUser: () => boolean
  canAccessResource: (resource?: string, action?: string) => boolean
  getPermissionLevel: (resource: string) => PermissionLevel
}

const createHelpers = (hasPermission: (permission: string) => boolean, hasRole: (role: string) => boolean): AccessHelpers => {
  const hasAnyPermission = (permissions: string[]) => permissions.some(permission => hasPermission(permission))
  const hasAllPermissions = (permissions: string[]) => permissions.every(permission => hasPermission(permission))
  const hasAnyRole = (roles: string[]) => roles.some(role => hasRole(role))
  const isAdminUser = () => hasRole('admin')
  const isSuperAdminUser = () => hasRole('super_admin') || hasRole('superadmin')
  const canAccessResource = (resource?: string, action: string = 'read') => {
    if (!resource) {
      return false
    }
    return hasPermission(`${resource}.${action}`) || hasPermission(`${resource}.*`)
  }
  const getPermissionLevel = (resource: string): PermissionLevel => {
    if (!resource) {
      return 'none'
    }

    if (isSuperAdminUser()) {
      return 'admin'
    }

    if (
      isAdminUser() ||
      hasPermission(`${resource}.admin`) ||
      hasPermission(`${resource}.manage`)
    ) {
      return 'admin'
    }

    if (
      hasPermission(`${resource}.write`) ||
      hasPermission(`${resource}.edit`)
    ) {
      return 'write'
    }

    if (
      hasPermission(`${resource}.read`) ||
      hasPermission(`${resource}.view`)
    ) {
      return 'read'
    }

    return 'none'
  }

  return {
    hasAnyPermission,
    hasAllPermissions,
    hasAnyRole,
    isAdminUser,
    isSuperAdminUser,
    canAccessResource,
    getPermissionLevel
  }
}

export function PermissionGuard({
  permissions = [],
  roles = [],
  resource,
  action = 'read',
  requireAll = false,
  customCheck,
  fallback = null,
  children,
  allowUnauthenticated = false
}: PermissionGuardProps) {
  const auth = useAuth()
  const {
    user,
    isAuthenticated,
    isLoading,
    hasPermission,
    hasRole
  } = auth

  const helpers = React.useMemo(
    () => createHelpers(hasPermission, hasRole),
    [hasPermission, hasRole]
  )

  if (isLoading && !allowUnauthenticated) {
    return <>{fallback}</>
  }

  if (!allowUnauthenticated && !isAuthenticated) {
    return <>{fallback}</>
  }

  if (
    permissions.length === 0 &&
    roles.length === 0 &&
    !resource &&
    !customCheck
  ) {
    return <>{children}</>
  }

  if (user && helpers.isSuperAdminUser()) {
    return <>{children}</>
  }

  let hasAccess = false

  if (customCheck) {
    hasAccess = customCheck(user)
  } else {
    if (resource) {
      hasAccess = helpers.canAccessResource(resource, action)
    }

    if (permissions.length > 0) {
      hasAccess =
        hasAccess ||
        (requireAll
          ? helpers.hasAllPermissions(permissions)
          : helpers.hasAnyPermission(permissions))
    }

    if (roles.length > 0) {
      hasAccess =
        hasAccess ||
        (requireAll
          ? roles.every(role => hasRole(role))
          : helpers.hasAnyRole(roles))
    }

    if (!hasAccess && helpers.isAdminUser()) {
      const hasRestrictedPermission = permissions.some(permission =>
        RESTRICTED_ADMIN_PERMISSIONS.includes(permission)
      )

      if (!hasRestrictedPermission) {
        hasAccess = true
      }
    }
  }

  if (hasAccess) {
    return <>{children}</>
  }

  return <>{fallback}</>
}

export function withPermissionGuard<T extends object>(
  Component: React.ComponentType<T>,
  guardProps: Omit<PermissionGuardProps, 'children'>
) {
  return function GuardedComponent(props: T) {
    return (
      <PermissionGuard {...guardProps}>
        <Component {...props} />
      </PermissionGuard>
    )
  }
}

export function usePermissionGuard() {
  const auth = useAuth()
  const helpers = React.useMemo(
    () => createHelpers(auth.hasPermission, auth.hasRole),
    [auth.hasPermission, auth.hasRole]
  )

  const checkAccess = React.useCallback(
    (guardProps: Omit<PermissionGuardProps, 'children' | 'fallback'>) => {
      const {
        permissions = [],
        roles = [],
        resource,
        action = 'read',
        requireAll = false,
        customCheck,
        allowUnauthenticated = false
      } = guardProps

      const { user, isAuthenticated } = auth

      if (!allowUnauthenticated && !isAuthenticated) {
        return false
      }

      if (
        permissions.length === 0 &&
        roles.length === 0 &&
        !resource &&
        !customCheck
      ) {
        return true
      }

      if (user && helpers.isSuperAdminUser()) {
        return true
      }

      let hasAccess = false

      if (customCheck) {
        hasAccess = customCheck(user)
      } else {
        if (resource) {
          hasAccess = helpers.canAccessResource(resource, action)
        }

        if (permissions.length > 0) {
          hasAccess =
            hasAccess ||
            (requireAll
              ? helpers.hasAllPermissions(permissions)
              : helpers.hasAnyPermission(permissions))
        }

        if (roles.length > 0) {
          hasAccess =
            hasAccess ||
            (requireAll
              ? roles.every(role => auth.hasRole(role))
              : helpers.hasAnyRole(roles))
        }

        if (!hasAccess && helpers.isAdminUser()) {
          const hasRestrictedPermission = permissions.some(permission =>
            RESTRICTED_ADMIN_PERMISSIONS.includes(permission)
          )

          if (!hasRestrictedPermission) {
            hasAccess = true
          }
        }
      }

      return hasAccess
    },
    [auth, helpers]
  )

  return React.useMemo(
    () => ({
      checkAccess,
      ...auth
    }),
    [auth, checkAccess]
  )
}

interface PermissionLevelProps {
  read?: React.ReactNode
  write?: React.ReactNode
  admin?: React.ReactNode
  resource: string
  fallback?: React.ReactNode
}

export function PermissionLevel({
  read,
  write,
  admin,
  resource,
  fallback = null
}: PermissionLevelProps) {
  const auth = useAuth()
  const helpers = React.useMemo(
    () => createHelpers(auth.hasPermission, auth.hasRole),
    [auth.hasPermission, auth.hasRole]
  )

  const level = helpers.getPermissionLevel(resource)

  switch (level) {
    case 'admin':
      return <>{admin || write || read || fallback}</>
    case 'write':
      return <>{write || read || fallback}</>
    case 'read':
      return <>{read || fallback}</>
    default:
      return <>{fallback}</>
  }
}
