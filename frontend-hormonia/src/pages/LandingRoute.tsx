import { useEffect } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '@/app/providers/AuthContext'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { createLogger } from '@/lib/logger'

const logger = createLogger('LandingRoute')

/**
 * LandingRoute - Smart landing page that handles auth state
 *
 * This component serves as the entry point (/) and handles:
 * - Loading state while auth initializes
 * - Redirecting to /login if not authenticated
 * - Redirecting to appropriate dashboard based on user role
 */
export function LandingRoute() {
  const { user, isInitializing } = useAuth()

  useEffect(() => {
    logger.log('LandingRoute mounted', { isInitializing, hasUser: !!user })
  }, [isInitializing, user])

  // Show loading state while auth initializes
  if (isInitializing) {
    logger.log('Auth loading, showing spinner')
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center space-y-4">
          <LoadingSpinner size="lg" color="primary" />
          <p className="text-muted-foreground text-sm">Verificando autenticação...</p>
        </div>
      </div>
    )
  }

  // Not authenticated - redirect to login
  if (!user) {
    logger.log('No user found, redirecting to /login')
    return <Navigate to="/login" replace />
  }

  // Authenticated - redirect to appropriate dashboard based on role
  logger.log('User authenticated, determining dashboard', { role: user.role })

  // Check for physician/medico role
  if (
    user.role === 'medico' ||
    user.role === 'physician' ||
    user.role === 'PHYSICIAN' ||
    user.role === 'DOCTOR'
  ) {
    logger.log('Redirecting to physician dashboard')
    return <Navigate to="/physician/dashboard" replace />
  }

  // Check for patient role
  if (user.role === 'patient' || user.role === 'paciente' || user.role === 'PATIENT') {
    logger.log('Redirecting to patient dashboard')
    return <Navigate to="/patients" replace />
  }

  // For admin, superadmin, and all other roles - redirect to appropriate dashboard
  // Admin users with ADMIN role go to /admin/dashboard
  // Regular users go to /dashboard
  if (user.role === 'admin' || user.role === 'ADMIN' || user.role === 'superadmin') {
    logger.log('Redirecting to admin dashboard', { role: user.role })
    return <Navigate to="/admin/dashboard" replace />
  }

  logger.log('Redirecting to main dashboard', { role: user.role })
  return <Navigate to="/dashboard" replace />
}
