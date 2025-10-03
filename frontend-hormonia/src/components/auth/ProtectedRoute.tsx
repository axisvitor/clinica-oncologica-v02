import React, { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { AlertTriangle } from 'lucide-react'

interface ProtectedRouteProps {
  children: ReactNode
  requiredRole?: string
  requiredRoles?: string[]
  requiredPermission?: string
}

export function ProtectedRoute({ children, requiredRole, requiredRoles, requiredPermission }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, user, hasRole, hasPermission } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (!isAuthenticated) {
    // Redirect to login page with return url
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  // Check role-based access (single role)
  if (requiredRole && !hasRole(requiredRole)) {
    return (
      <div className="container mx-auto p-6">
        <Alert className="bg-red-50">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Acesso Negado</AlertTitle>
          <AlertDescription>
            Você não tem permissão para acessar esta página. Role necessária: {requiredRole}.
            {user && <><br />Sua role atual: {user['role']}</>}
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  // Check role-based access (multiple roles - any match)
  if (requiredRoles && requiredRoles.length > 0) {
    const hasAnyRole = requiredRoles.some(role => hasRole(role))
    if (!hasAnyRole) {
      return (
        <div className="container mx-auto p-6">
          <Alert className="bg-red-50">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Acesso Negado</AlertTitle>
            <AlertDescription>
              Você não tem permissão para acessar esta página. Roles necessárias: {requiredRoles.join(', ')}.
              {user && <><br />Sua role atual: {user['role']}</>}
            </AlertDescription>
          </Alert>
        </div>
      )
    }
  }

  // Check permission-based access
  if (requiredPermission && !hasPermission(requiredPermission)) {
    return (
      <div className="container mx-auto p-6">
        <Alert className="bg-red-50">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Acesso Negado</AlertTitle>
          <AlertDescription>
            Você não tem permissão para acessar esta página. Permissão necessária: {requiredPermission}.
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  return <>{children}</>
}
