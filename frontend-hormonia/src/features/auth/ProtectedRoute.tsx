import React, { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/app/providers/AuthContext";
import { LoadingSpinner } from "@/components/ui/loading-spinner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AlertTriangle } from "lucide-react";
import {
  getRolePermissions,
  isAdmin,
  isDoctor,
  type RolePermissions,
} from "@/types/shared";

interface ProtectedRouteProps {
  children: ReactNode;
  /**
   * @deprecated Use requiredPermission instead. Will be removed in next version.
   * Required role for accessing this route (legacy)
   */
  requiredRole?: string;
  /**
   * @deprecated Use requiredPermission instead. Will be removed in next version.
   * Multiple roles (any match) for accessing this route (legacy)
   */
  requiredRoles?: string[];
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
  requiredRole,
  requiredRoles,
  requiredPermission,
  redirectTo: _redirectTo = "/unauthorized",
}: ProtectedRouteProps) {
  const { isAuthenticated, isInitializing, user } = useAuth();
  const location = useLocation();

  // Show loading spinner while checking authentication
  if (isInitializing) {
    return (
      <div className="flex items-center justify-center min-h-screen">
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
    const permissions = getRolePermissions(userRole);

    if (!permissions[requiredPermission]) {
      return (
        <div className="container mx-auto p-6">
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Acesso Negado</AlertTitle>
            <AlertDescription>
              Você não tem permissão para acessar esta página.
              {user && (
                <>
                  <br />
                  <span className="text-sm mt-2 block">
                    Sua role: <strong>{userRole}</strong>
                  </span>
                  <span className="text-sm block">
                    Permissão necessária: <strong>{requiredPermission}</strong>
                  </span>
                </>
              )}
            </AlertDescription>
          </Alert>
        </div>
      );
    }
  }

  // Legacy: Single role check (DEPRECATED)
  if (requiredRole) {
    const normalizedRequired = requiredRole.toLowerCase();
    const normalizedUser = userRole.toLowerCase();

    // Map legacy roles to new system
    const isAuthorized =
      normalizedUser === normalizedRequired ||
      // Legacy role mappings
      (normalizedRequired === "physician" && isDoctor(userRole)) ||
      (normalizedRequired === "super_admin" && isAdmin(userRole)) ||
      // Admin has access to everything
      isAdmin(userRole);

    if (!isAuthorized) {
      return (
        <div className="container mx-auto p-6">
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Acesso Negado</AlertTitle>
            <AlertDescription>
              Você não tem permissão para acessar esta página.
              {user && (
                <>
                  <br />
                  <span className="text-sm mt-2 block">
                    Role necessária: <strong>{requiredRole}</strong>
                  </span>
                  <span className="text-sm block">
                    Sua role atual: <strong>{userRole}</strong>
                  </span>
                  <span className="text-xs mt-2 block text-muted-foreground">
                    ⚠️ Este componente usa API legada. Migre para requiredPermission.
                  </span>
                </>
              )}
            </AlertDescription>
          </Alert>
        </div>
      );
    }
  }

  // Legacy: Multiple roles check (DEPRECATED)
  if (requiredRoles && requiredRoles.length > 0) {
    const normalizedUser = userRole.toLowerCase();

    const isAuthorized = requiredRoles.some((role) => {
      const normalizedRequired = role.toLowerCase();

      return (
        normalizedUser === normalizedRequired ||
        // Legacy role mappings
        (normalizedRequired === "physician" && isDoctor(userRole)) ||
        (normalizedRequired === "super_admin" && isAdmin(userRole)) ||
        // Admin has access to everything
        isAdmin(userRole)
      );
    });

    if (!isAuthorized) {
      return (
        <div className="container mx-auto p-6">
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Acesso Negado</AlertTitle>
            <AlertDescription>
              Você não tem permissão para acessar esta página.
              {user && (
                <>
                  <br />
                  <span className="text-sm mt-2 block">
                    Roles necessárias: <strong>{requiredRoles.join(", ")}</strong>
                  </span>
                  <span className="text-sm block">
                    Sua role atual: <strong>{userRole}</strong>
                  </span>
                  <span className="text-xs mt-2 block text-muted-foreground">
                    ⚠️ Este componente usa API legada. Migre para requiredPermission.
                  </span>
                </>
              )}
            </AlertDescription>
          </Alert>
        </div>
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
