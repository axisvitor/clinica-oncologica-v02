import React from 'react'
import { Toaster } from './components/ui/toaster'
import AdminRoutes from '@/app/routes/AdminRoutes'
import { ErrorBoundary } from './components/error/ErrorBoundary'

/**
 * AdminApp Component
 *
 * IMPORTANT: This component is loaded inside App.tsx which already provides:
 * - PersistQueryClientProvider (with IndexedDB persistence)
 * - AuthProvider (Firebase authentication) ✅ UNIFIED AUTH
 * - Router (React Router v6)
 *
 * Provider Hierarchy (from App.tsx down):
 * - ErrorBoundary
 *   - PersistQueryClientProvider (shared queryClient)
 *     - AuthProvider (Firebase auth) ✅ SINGLE SOURCE OF TRUTH
 *       - Router
 *         - AdminApp (lazy loaded)
 *           - AdminRoutes
 *
 * FIXED: Removed AdminAuthProvider duplication
 * All admin components now use unified AuthProvider from App.tsx
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