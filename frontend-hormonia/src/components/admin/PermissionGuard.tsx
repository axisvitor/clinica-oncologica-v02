import React from 'react'
import { useAuth } from '@/hooks/useAuth'

interface PermissionGuardProps {
  /** Array of permissions required to show the children */
  permissions?: string[]
  /** Array of roles that can access the content */
  roles?: string[]
  /** Resource name for context-specific permissions */
  resource?: string
  /** Action for resource-based permissions (e.g., 'read', 'write', 'delete') */
  action?: string
  /** Require all permissions/roles instead of any */
  requireAll?: boolean
  /** Function to determine access based on user */
  customCheck?: (user: any) => boolean
  /** Fallback component to render when access is denied */
  fallback?: React.ReactNode
  /** Children to render when access is granted */
  children: React.ReactNode
  /** Render children even if not authenticated (for public components) */
  allowUnauthenticated?: boolean
}

/**
 * PermissionGuard component for protecting UI elements based on user permissions and roles
 *
 * Examples:
 * - <PermissionGuard permissions={['admin.users.create']}>Create User Button</PermissionGuard>
 * - <PermissionGuard roles={['admin']}>Admin Panel</PermissionGuard>
 * - <PermissionGuard resource="patients" action="delete">Delete Button</PermissionGuard>
 * - <PermissionGuard customCheck={(user) => user?.id === patient.createdBy}>Edit My Patient</PermissionGuard>
 */
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
  const {
    user,
    isAuthenticated,
    hasPermission,
    hasRole,
    hasAnyRole,
    hasAllPermissions,
    hasAnyPermission,
    canAccessResource,
    isAdmin,
    isSuperAdmin
  } = useAuth()

  // If not authenticated and not allowing unauthenticated access
  if (!allowUnauthenticated && !isAuthenticated) {
    return <>{fallback}</>
  }

  // If no conditions specified, allow access
  if (
    permissions.length === 0 &&
    roles.length === 0 &&
    !resource &&
    !customCheck
  ) {
    return <>{children}</>
  }

  // Super admin bypass (optional - can be configured)
  if (user && isSuperAdmin()) {
    return <>{children}</>
  }

  let hasAccess = false

  // Custom check has highest priority
  if (customCheck) {
    hasAccess = customCheck(user)
  } else {
    // Resource-based check
    if (resource) {
      hasAccess = canAccessResource(resource, action)
    }

    // Permission-based check
    if (permissions.length > 0) {
      if (requireAll) {
        hasAccess = hasAccess || hasAllPermissions(permissions)
      } else {
        hasAccess = hasAccess || hasAnyPermission(permissions)
      }
    }

    // Role-based check
    if (roles.length > 0) {
      if (requireAll) {
        // For requireAll with roles, check if user has all specified roles
        // Note: This is unusual as users typically have one role
        hasAccess = hasAccess || roles.every(role => hasRole(role))
      } else {
        hasAccess = hasAccess || hasAnyRole(roles)
      }
    }

    // Admin override for basic admin permissions
    if (!hasAccess && isAdmin()) {
      // Admins can access most resources unless explicitly restricted
      const restrictedPermissions = [
        'admin.system.delete',
        'admin.users.delete_admin',
        'admin.backup.delete'
      ]

      const hasRestrictedPermission = permissions.some(p =>
        restrictedPermissions.includes(p)
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

/**
 * Higher-order component version of PermissionGuard
 */
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

/**
 * Hook for checking permissions in component logic
 */
export function usePermissionGuard() {
  const auth = useAuth()

  const checkAccess = React.useCallback((guardProps: Omit<PermissionGuardProps, 'children' | 'fallback'>) => {
    const {
      permissions = [],
      roles = [],
      resource,
      action = 'read',
      requireAll = false,
      customCheck,
      allowUnauthenticated = false
    } = guardProps

    const {
      user,
      isAuthenticated,
      hasPermission,
      hasRole,
      hasAnyRole,
      hasAllPermissions,
      hasAnyPermission,
      canAccessResource,
      isAdmin,
      isSuperAdmin
    } = auth

    // If not authenticated and not allowing unauthenticated access
    if (!allowUnauthenticated && !isAuthenticated) {
      return false
    }

    // If no conditions specified, allow access
    if (
      permissions.length === 0 &&
      roles.length === 0 &&
      !resource &&
      !customCheck
    ) {
      return true
    }

    // Super admin bypass
    if (user && isSuperAdmin()) {
      return true
    }

    let hasAccess = false

    // Custom check has highest priority
    if (customCheck) {
      hasAccess = customCheck(user)
    } else {
      // Resource-based check
      if (resource) {
        hasAccess = canAccessResource(resource, action)
      }

      // Permission-based check
      if (permissions.length > 0) {
        if (requireAll) {
          hasAccess = hasAccess || hasAllPermissions(permissions)
        } else {
          hasAccess = hasAccess || hasAnyPermission(permissions)
        }
      }

      // Role-based check
      if (roles.length > 0) {
        if (requireAll) {
          hasAccess = hasAccess || roles.every(role => hasRole(role))
        } else {
          hasAccess = hasAccess || hasAnyRole(roles)
        }
      }

      // Admin override
      if (!hasAccess && isAdmin()) {
        const restrictedPermissions = [
          'admin.system.delete',
          'admin.users.delete_admin',
          'admin.backup.delete'
        ]

        const hasRestrictedPermission = permissions.some(p =>
          restrictedPermissions.includes(p)
        )

        if (!hasRestrictedPermission) {
          hasAccess = true
        }
      }
    }

    return hasAccess
  }, [auth])

  return {
    checkAccess,
    ...auth
  }
}

/**
 * Component for displaying different content based on permission levels
 */
interface PermissionLevelProps {
  /** Content for users with read permission */
  read?: React.ReactNode
  /** Content for users with write permission */
  write?: React.ReactNode
  /** Content for users with admin permission */
  admin?: React.ReactNode
  /** Base permission to check (e.g., 'users' will check 'users.read', 'users.write', 'users.admin') */
  resource: string
  /** Default content for users without any permission */
  fallback?: React.ReactNode
}

export function PermissionLevel({
  read,
  write,
  admin,
  resource,
  fallback = null
}: PermissionLevelProps) {
  const { getPermissionLevel } = useAuth()

  const level = getPermissionLevel(resource)

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