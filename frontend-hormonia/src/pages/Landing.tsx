import { Navigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { LoadingSpinner } from '@/components/ui/loading-spinner'

/**
 * Landing component for root route that intelligently redirects
 * based on authentication state.
 *
 * This prevents the previous issue where "/" always redirected to "/dashboard"
 * even for unauthenticated users, bypassing the login page.
 */
export function Landing() {
  const { isAuthenticated, isInitializing } = useAuth()

  // Show loader while checking authentication state
  if (isInitializing) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner size="lg" color="primary" />
      </div>
    )
  }

  // Smart redirect based on actual auth state
  return (
    <Navigate
      to={isAuthenticated ? '/dashboard' : '/login'}
      replace
    />
  )
}
