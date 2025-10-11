import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import AdminDashboard from '../components/admin/AdminDashboard'
import AdminLoginForm from '../components/admin/AdminLoginForm'
import AdminProtectedRoute from '../components/admin/AdminProtectedRoute'
import AdminUserActivityMonitor from '../components/admin/AdminUserActivityMonitor'
import { useAuth } from '../contexts/AuthContext'
import { createLogger } from '../lib/logger'
import { AdminLoginCredentials, AdminLoginResponse, AdminUser } from '../types/admin'

const logger = createLogger('AdminRoutes')

// Placeholder components for routes that will be implemented later
const AdminUsersPage = () => (
  <div className="p-6">
    <h1 className="text-2xl font-bold mb-4">User Management</h1>
    <p className="text-gray-600">User management interface will be implemented here.</p>
  </div>
)

const AdminSecurityPage = () => (
  <div className="p-6">
    <h1 className="text-2xl font-bold mb-4">Security</h1>
    <p className="text-gray-600">Security management interface will be implemented here.</p>
  </div>
)

const AdminAuditLogsPage = () => (
  <div className="p-6">
    <h1 className="text-2xl font-bold mb-4">Audit Logs</h1>
    <AdminUserActivityMonitor />
  </div>
)

const AdminSystemPage = () => (
  <div className="p-6">
    <h1 className="text-2xl font-bold mb-4">System Management</h1>
    <p className="text-gray-600">System management interface will be implemented here.</p>
  </div>
)

const AdminReportsPage = () => (
  <div className="p-6">
    <h1 className="text-2xl font-bold mb-4">Reports</h1>
    <p className="text-gray-600">Reports interface will be implemented here.</p>
  </div>
)

const AdminSettingsPage = () => (
  <div className="p-6">
    <h1 className="text-2xl font-bold mb-4">Settings</h1>
    <p className="text-gray-600">Settings interface will be implemented here.</p>
  </div>
)

const AdminProfilePage = () => (
  <div className="p-6">
    <h1 className="text-2xl font-bold mb-4">Profile Settings</h1>
    <p className="text-gray-600">Profile settings interface will be implemented here.</p>
  </div>
)

// Login page component
const AdminLoginPage: React.FC = () => {
  const { login, user } = useAuth()

  const handleLogin = async (credentials: AdminLoginCredentials): Promise<AdminLoginResponse> => {
    try {
      await login(credentials.email, credentials.password, credentials.rememberMe)

      // Return success response in AdminLoginResponse format
      const response: AdminLoginResponse = {
        success: true
      }

      if (user) {
        response.user = user as AdminUser
      }

      return response
    } catch (error) {
      logger.error('Login failed:', error)

      // Return error response in AdminLoginResponse format
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Login failed'
      }
    }
  }

  const handleForgotPassword = (email: string) => {
    logger.log('Forgot password for:', email)
    // TODO: Implement forgot password functionality
    alert('Forgot password functionality will be implemented')
  }

  return (
    <AdminLoginForm
      onLogin={handleLogin}
      onForgotPassword={handleForgotPassword}
    />
  )
}

// Main admin routes configuration
export const AdminRoutes: React.FC = () => {
  return (
    <Routes>
      {/* Public admin routes */}
      <Route path="/login" element={<AdminLoginPage />} />

      {/* Protected admin routes */}
      <Route
        path="/"
        element={
          <AdminProtectedRoute requiredPermissions={['admin.read']}>
            <AdminDashboard />
          </AdminProtectedRoute>
        }
      >
        {/* Nested routes under the dashboard layout */}
        <Route index element={<Navigate to="/admin" replace />} />

        <Route
          path="users"
          element={
            <AdminProtectedRoute requiredPermissions={['users.read']}>
              <AdminUsersPage />
            </AdminProtectedRoute>
          }
        />

        <Route
          path="users/locked"
          element={
            <AdminProtectedRoute requiredPermissions={['users.read']}>
              <AdminUsersPage />
            </AdminProtectedRoute>
          }
        />

        <Route
          path="users/roles"
          element={
            <AdminProtectedRoute requiredPermissions={['users.roles.read']}>
              <AdminUsersPage />
            </AdminProtectedRoute>
          }
        />

        <Route
          path="security"
          element={
            <AdminProtectedRoute requiredPermissions={['security.read']}>
              <AdminSecurityPage />
            </AdminProtectedRoute>
          }
        />

        <Route
          path="security/audit"
          element={
            <AdminProtectedRoute requiredPermissions={['security.audit.read']}>
              <AdminAuditLogsPage />
            </AdminProtectedRoute>
          }
        />

        <Route
          path="security/sessions"
          element={
            <AdminProtectedRoute requiredPermissions={['security.sessions.read']}>
              <AdminSecurityPage />
            </AdminProtectedRoute>
          }
        />

        <Route
          path="security/blocked-ips"
          element={
            <AdminProtectedRoute requiredPermissions={['security.blocked.read']}>
              <AdminSecurityPage />
            </AdminProtectedRoute>
          }
        />

        <Route
          path="security/settings"
          element={
            <AdminProtectedRoute requiredPermissions={['security.settings.write']}>
              <AdminSecurityPage />
            </AdminProtectedRoute>
          }
        />

        <Route
          path="system"
          element={
            <AdminProtectedRoute requiredPermissions={['system.read']}>
              <AdminSystemPage />
            </AdminProtectedRoute>
          }
        />

        <Route
          path="system/health"
          element={
            <AdminProtectedRoute requiredPermissions={['system.health.read']}>
              <AdminSystemPage />
            </AdminProtectedRoute>
          }
        />

        <Route
          path="system/logs"
          element={
            <AdminProtectedRoute requiredPermissions={['system.logs.read']}>
              <AdminSystemPage />
            </AdminProtectedRoute>
          }
        />

        <Route
          path="system/backup"
          element={
            <AdminProtectedRoute requiredPermissions={['system.backup.read']}>
              <AdminSystemPage />
            </AdminProtectedRoute>
          }
        />

        <Route
          path="reports"
          element={
            <AdminProtectedRoute requiredPermissions={['reports.read']}>
              <AdminReportsPage />
            </AdminProtectedRoute>
          }
        />

        <Route
          path="reports/security"
          element={
            <AdminProtectedRoute requiredPermissions={['reports.security.read']}>
              <AdminReportsPage />
            </AdminProtectedRoute>
          }
        />

        <Route
          path="reports/users"
          element={
            <AdminProtectedRoute requiredPermissions={['reports.users.read']}>
              <AdminReportsPage />
            </AdminProtectedRoute>
          }
        />

        <Route
          path="reports/system"
          element={
            <AdminProtectedRoute requiredPermissions={['reports.system.read']}>
              <AdminReportsPage />
            </AdminProtectedRoute>
          }
        />

        <Route
          path="settings"
          element={
            <AdminProtectedRoute requiredPermissions={['settings.read']}>
              <AdminSettingsPage />
            </AdminProtectedRoute>
          }
        />

        <Route
          path="settings/general"
          element={
            <AdminProtectedRoute requiredPermissions={['settings.general.read']}>
              <AdminSettingsPage />
            </AdminProtectedRoute>
          }
        />

        <Route
          path="settings/notifications"
          element={
            <AdminProtectedRoute requiredPermissions={['settings.notifications.read']}>
              <AdminSettingsPage />
            </AdminProtectedRoute>
          }
        />

        <Route
          path="settings/integrations"
          element={
            <AdminProtectedRoute requiredPermissions={['settings.integrations.read']}>
              <AdminSettingsPage />
            </AdminProtectedRoute>
          }
        />

        <Route
          path="profile"
          element={
            <AdminProtectedRoute>
              <AdminProfilePage />
            </AdminProtectedRoute>
          }
        />
      </Route>

      {/* Catch all other admin routes */}
      <Route path="*" element={<Navigate to="/admin" replace />} />
    </Routes>
  )
}

export default AdminRoutes