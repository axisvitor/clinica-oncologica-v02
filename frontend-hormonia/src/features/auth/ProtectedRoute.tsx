import React, { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { LoadingSpinner } from "@/components/ui/loading-spinner";
import {
  getRolePermissions,
  isAdmin,
  isDoctor,
  type RolePermissions,
} from "@/types/shared";

interface ProtectedRouteProps {
  children: ReactNode;
  /**
   * Required permission key from RolePermissions
   * @example "canAccessAdmin", "canManageUsers", "canManagePatients"
   */
  requiredPermission?: keyof RolePermissions;
  /**
   * Redirect path for unauthorized access (default: /unauthorized)
   */
  redirectTo?: string;
}

/**
 * ProtectedRoute Component
 *
 * Protects routes based on authentication and role-based permissions.
 *
 * System Roles:
 * - ADMIN: Full system access (all permissions)
 * - DOCTOR: Clinical operations (patients, reports)
 *
 * @example
 * // Protect admin-only route
 * <ProtectedRoute requiredPermission="canAccessAdmin">
 *   <AdminPanel />
 * </ProtectedRoute>
 *
 * @example
 * // Protect doctor + admin route
 * <ProtectedRoute requiredPermission="canManagePatients">
 *   <PatientsPage />
 * </ProtectedRoute>
 *
 * @example
 * // Just check authentication (any authenticated user)
 * <ProtectedRoute>
 *   <DashboardPage />
 * </ProtectedRoute>
 */
export function ProtectedRoute({
  children,
  requiredPermission,
  redirectTo = "/unauthorized",
}: ProtectedRouteProps) {
  const auth = useAuth();
  const { isAuthenticated, isInitializing, user } = auth;
  const location = useLocation();
  const isLoading = isInitializing || (auth as { isLoading?: boolean }).isLoading || false;

  // Show loading spinner while checking authentication
  if (isLoading) {
    return (
      <div
        data-testid="loading-spinner"
        className="flex items-center justify-center min-h-screen"
      >
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Get user role (with fallback)
  const userRole = user?.role || "";

  // Permission-based access control (NEW - Preferred)
  if (requiredPermission) {
    const rolePermissions = getRolePermissions(userRole);
    const permissionKey = String(requiredPermission);
    const hasRoleScopedPermission = Object.prototype.hasOwnProperty.call(rolePermissions, permissionKey);
    const hasAccess = hasRoleScopedPermission
      ? Boolean(rolePermissions[requiredPermission])
      : auth.hasPermission(permissionKey);
    if (!hasAccess) {
      return (
        <Navigate
          to={redirectTo}
          state={{ from: location, requiredPermission, userRole }}
          replace
        />
      );
    }
  }

  // All checks passed - render children
  return <>{children}</>;
}

/**
 * Hook for checking permissions in components
 *
 * @example
 * const { canAccess, permissions } = useRoleGuard();
 *
 * if (!permissions.canAccessAdmin) {
 *   return <Unauthorized />;
 * }
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useRoleGuard() {
  const { user, isAuthenticated } = useAuth();
  const userRole = user?.role || "";
  const permissions = getRolePermissions(userRole);

  return {
    isAuthenticated,
    userRole,
    permissions,
    isAdmin: isAdmin(userRole),
    isDoctor: isDoctor(userRole),
    /**
     * Check if user can access a specific permission
     */
    canAccess: (permission: keyof RolePermissions) => permissions[permission],
    /**
     * Check if user has admin role
     */
    hasAdminAccess: () => isAdmin(userRole),
    /**
     * Check if user has doctor role
     */
    hasDoctorAccess: () => isDoctor(userRole),
  };
}

/**
 * Component for conditional rendering based on permissions
 *
 * @example
 * <PermissionGate permission="canManageUsers">
 *   <Button>Create User</Button>
 * </PermissionGate>
 *
 * @example
 * <PermissionGate permission="canAccessAdmin" fallback={<p>Admins only</p>}>
 *   <AdminPanel />
 * </PermissionGate>
 */
export function PermissionGate({
  permission,
  children,
  fallback = null,
}: {
  permission: keyof RolePermissions;
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const { canAccess } = useRoleGuard();

  if (!canAccess(permission)) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
}
