import React from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Shield, AlertTriangle, Clock } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { useAuth } from '@/app/providers/AuthContext'
import { AdminPermissionError } from '@/types/admin'

interface AdminProtectedRouteProps {
  children: React.ReactNode
  requiredPermissions?: string[]
  requiresTwoFactor?: boolean
  fallbackComponent?: React.ComponentType
}

const LoadingScreen: React.FC = () => (
  <div className="min-h-screen bg-gray-50 flex items-center justify-center">
    <div className="text-center space-y-4">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
      <div className="space-y-2">
        <h2 className="text-xl font-semibold text-gray-900">Verifying Access</h2>
        <p className="text-gray-600">Please wait while we authenticate your session...</p>
      </div>
    </div>
  </div>
)

const UnauthorizedScreen: React.FC<{
  reason: string
  description: string
  action?: () => void
  actionLabel?: string
}> = ({ reason, description, action, actionLabel }) => (
  <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
    <Card className="w-full max-w-md">
      <CardHeader className="text-center">
        <div className="mx-auto w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mb-4">
          <Shield className="w-6 h-6 text-red-600" />
        </div>
        <CardTitle className="text-xl text-gray-900">Access Denied</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Alert className="border-red-200 bg-red-50">
          <AlertTriangle className="h-4 w-4 text-red-600" />
          <AlertDescription className="text-red-800">
            <div className="space-y-2">
              <p className="font-medium">{reason}</p>
              <p className="text-sm">{description}</p>
            </div>
          </AlertDescription>
        </Alert>

        {action && actionLabel && (
          <Button onClick={action} className="w-full">
            {actionLabel}
          </Button>
        )}

        <div className="text-center">
          <Button variant="outline" onClick={() => window.history.back()}>
            Go Back
          </Button>
        </div>
      </CardContent>
    </Card>
  </div>
)

const InsufficientPermissionsScreen: React.FC<{
  requiredPermissions: string[]
  userPermissions: string[]
}> = ({ requiredPermissions, userPermissions }) => (
  <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
    <Card className="w-full max-w-lg">
      <CardHeader className="text-center">
        <div className="mx-auto w-12 h-12 bg-yellow-100 rounded-full flex items-center justify-center mb-4">
          <Shield className="w-6 h-6 text-yellow-600" />
        </div>
        <CardTitle className="text-xl text-gray-900">Insufficient Permissions</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Alert className="border-yellow-200 bg-yellow-50">
          <AlertTriangle className="h-4 w-4 text-yellow-600" />
          <AlertDescription className="text-yellow-800">
            You don't have the required permissions to access this resource.
          </AlertDescription>
        </Alert>

        <div className="space-y-3">
          <div>
            <h4 className="text-sm font-medium text-gray-900 mb-2">Required Permissions:</h4>
            <div className="flex flex-wrap gap-2">
              {requiredPermissions.map(permission => (
                <Badge key={permission} variant="destructive">
                  {permission}
                </Badge>
              ))}
            </div>
          </div>

          <div>
            <h4 className="text-sm font-medium text-gray-900 mb-2">Your Permissions:</h4>
            <div className="flex flex-wrap gap-2">
              {userPermissions.length > 0 ? (
                userPermissions.map(permission => (
                  <Badge
                    key={permission}
                    variant={requiredPermissions.includes(permission) ? "default" : "secondary"}
                  >
                    {permission}
                  </Badge>
                ))
              ) : (
                <span className="text-sm text-gray-500">No permissions granted</span>
              )}
            </div>
          </div>
        </div>

        <div className="text-center text-sm text-gray-600">
          Contact your administrator to request the necessary permissions.
        </div>

        <div className="text-center">
          <Button variant="outline" onClick={() => window.history.back()}>
            Go Back
          </Button>
        </div>
      </CardContent>
    </Card>
  </div>
)

const TwoFactorRequiredScreen: React.FC = () => {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mb-4">
            <Shield className="w-6 h-6 text-blue-600" />
          </div>
          <CardTitle className="text-xl text-gray-900">Two-Factor Authentication Required</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Alert className="border-blue-200 bg-blue-50">
            <Clock className="h-4 w-4 text-blue-600" />
            <AlertDescription className="text-blue-800">
              This resource requires two-factor authentication to be enabled on your account.
            </AlertDescription>
          </Alert>

          <div className="space-y-2 text-sm text-gray-600">
            <p>Two-factor authentication adds an extra layer of security to your account by requiring:</p>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li>Your password</li>
              <li>A verification code from your mobile device</li>
            </ul>
          </div>

          <div className="space-y-3">
            <Button onClick={() => navigate('/admin/security/two-factor-setup')} className="w-full">
              Set Up Two-Factor Authentication
            </Button>
            <Button variant="outline" onClick={() => window.history.back()} className="w-full">
              Go Back
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export const AdminProtectedRoute: React.FC<AdminProtectedRouteProps> = ({
  children,
  requiredPermissions = [],
  requiresTwoFactor = false,
  fallbackComponent: FallbackComponent
}) => {
  const { user, isLoading, isAuthenticated, hasPermission } = useAuth()
  const location = useLocation()

  // Show loading while checking authentication
  if (isLoading) {
    return <LoadingScreen />
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated || !user) {
    return <Navigate to="/admin/login" state={{ from: location }} replace />
  }

  // Check if user account is active
  if (!user.is_active) {
    return (
      <UnauthorizedScreen
        reason="Account Disabled"
        description="Your administrator account has been disabled. Please contact your system administrator."
      />
    )
  }

  // Check if user account is locked (if this field exists)
  if ((user as any).locked_until && new Date((user as any).locked_until) > new Date()) {
    const lockoutEnd = new Date((user as any).locked_until)
    return (
      <UnauthorizedScreen
        reason="Account Temporarily Locked"
        description={`Your account is locked until ${lockoutEnd.toLocaleString()} due to multiple failed login attempts.`}
      />
    )
  }

  // Check two-factor authentication requirement (if this field exists)
  if (requiresTwoFactor && !(user as any).two_factor_enabled) {
    return <TwoFactorRequiredScreen />
  }

  // Check permissions using AuthContext hasPermission
  if (requiredPermissions.length > 0) {
    const hasRequiredPermissions = requiredPermissions.some(permission =>
      hasPermission(permission)
    )

    if (!hasRequiredPermissions) {
      // Use custom fallback component if provided
      if (FallbackComponent) {
        return <FallbackComponent />
      }

      return (
        <InsufficientPermissionsScreen
          requiredPermissions={requiredPermissions}
          userPermissions={user.permissions || []}
        />
      )
    }
  }

  // All checks passed, render the protected content
  return <>{children}</>
}

// Higher-order component for easier use
export const withAdminProtection = <P extends object>(
  Component: React.ComponentType<P>,
  options: Omit<AdminProtectedRouteProps, 'children'> = {}
) => {
  const ProtectedComponent = (props: P) => (
    <AdminProtectedRoute {...options}>
      <Component {...props} />
    </AdminProtectedRoute>
  )

  ProtectedComponent.displayName = `withAdminProtection(${Component.displayName || Component.name || 'Component'})`

  return ProtectedComponent
}

export default AdminProtectedRoute