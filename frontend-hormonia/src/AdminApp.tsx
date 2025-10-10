import React from 'react'
import { Toaster } from './components/ui/toaster'
import { AdminAuthProvider } from './contexts/AdminAuthContext'
import AdminRoutes from './routes/AdminRoutes'
import { ErrorBoundary } from './components/error/ErrorBoundary'

/**
 * AdminApp Component
 *
 * IMPORTANT: This component is loaded inside App.tsx which already provides:
 * - PersistQueryClientProvider (with IndexedDB persistence)
 * - AuthProvider (Firebase authentication)
 * - Router (React Router v6)
 *
 * Therefore, AdminApp should NOT duplicate these providers.
 * It only adds AdminAuthProvider for admin-specific authentication state.
 *
 * Provider Hierarchy (from App.tsx down):
 * - ErrorBoundary
 *   - PersistQueryClientProvider (shared queryClient)
 *     - AuthProvider (Firebase auth)
 *       - Router
 *         - AdminApp (lazy loaded)
 *           - AdminAuthProvider (admin-specific auth)
 *             - AdminRoutes
 */

const AdminApp: React.FC = () => {
  return (
    <ErrorBoundary>
      <AdminAuthProvider>
        <div className="admin-app">
          <AdminRoutes />
        </div>
        <Toaster />
      </AdminAuthProvider>
    </ErrorBoundary>
  )
}

export default AdminApp