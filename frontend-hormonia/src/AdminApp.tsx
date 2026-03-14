import React from 'react'
import { Toaster } from './components/ui/toaster'
import AdminRoutes from '@/app/routes/AdminRoutes'
import { ErrorBoundary } from './components/error/ErrorBoundary'

/**
 * AdminApp Component
 *
 * IMPORTANT: This component is loaded inside App.tsx which already provides:
 * - PersistQueryClientProvider (with IndexedDB persistence)
 * - AuthProvider (backend session auth via cookies + verify-session) ✅ UNIFIED AUTH
 * - Router (React Router v6)
 *
 * Provider Hierarchy (from App.tsx down):
 * - ErrorBoundary
 *   - PersistQueryClientProvider (shared queryClient)
 *     - AuthProvider (session-first auth) ✅ SINGLE SOURCE OF TRUTH
 *       - Router
 *         - AdminApp (lazy loaded)
 *           - AdminRoutes
 *
 * FIXED: Removed AdminAuthProvider duplication
 * All admin components now use the shared AuthProvider from App.tsx for backend-owned login,
 * restore, and verify-session flows.
 */

const AdminApp: React.FC = () => {
  return (
    <ErrorBoundary>
      <div className="admin-app">
        <AdminRoutes />
      </div>
      <Toaster />
    </ErrorBoundary>
  )
}

export default AdminApp
