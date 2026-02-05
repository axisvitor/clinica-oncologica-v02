/**
 * Lazy-Loaded Admin Routes
 *
 * Implements code splitting and lazy loading for admin routes to improve
 * initial bundle size and application performance.
 *
 * Features:
 * - React.lazy() for route components
 * - Suspense boundaries with loading states
 * - Error boundaries for graceful error handling
 * - Preloading support for better UX
 * - Loading skeletons for better perceived performance
 *
 * Performance Impact:
 * - Initial bundle: -40% (estimated)
 * - Time to interactive: -35% (estimated)
 * - Lighthouse score: +15 points (estimated)
 */

import React, { Suspense, lazy } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ErrorBoundary } from '@/components/error/ErrorBoundary';
import { createLogger } from '@/lib/logger';
import type { AdminLoginCredentials, AdminLoginResponse } from '@/types/admin';

import { UserRole, AuthProvider } from '@/types/rbac';

const logger = createLogger('AdminRoutes.lazy');

// ============================================================================
// Loading Components
// ============================================================================

/**
 * Page Loading Skeleton
 * Provides visual feedback while lazy components load
 */
const PageLoadingSkeleton: React.FC = () => (
  <div className="min-h-screen bg-gray-50 p-6 animate-pulse">
    <div className="max-w-7xl mx-auto">
      {/* Header skeleton */}
      <div className="h-8 bg-gray-200 rounded w-1/4 mb-6"></div>

      {/* Content skeleton */}
      <div className="space-y-4">
        <div className="h-32 bg-gray-200 rounded"></div>
        <div className="h-32 bg-gray-200 rounded"></div>
        <div className="h-32 bg-gray-200 rounded"></div>
      </div>
    </div>
  </div>
);

/**
 * Dashboard Loading Skeleton
 * Specialized skeleton for dashboard with stats cards
 */
const DashboardLoadingSkeleton: React.FC = () => (
  <div className="min-h-screen bg-gray-50 p-6 animate-pulse">
    <div className="max-w-7xl mx-auto">
      {/* Stats cards skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-24 bg-gray-200 rounded"></div>
        ))}
      </div>

      {/* Charts skeleton */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="h-64 bg-gray-200 rounded"></div>
        <div className="h-64 bg-gray-200 rounded"></div>
      </div>

      {/* Recent activity skeleton */}
      <div className="h-48 bg-gray-200 rounded"></div>
    </div>
  </div>
);

/**
 * Simple Loading Spinner
 * Lightweight fallback for smaller components
 */
const LoadingSpinner: React.FC = () => (
  <div className="flex items-center justify-center min-h-[400px]">
    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
  </div>
);

// ============================================================================
// Lazy-Loaded Components
// ============================================================================

// Core Pages (High Priority - preload on app start)
const AdminDashboard = lazy(() => {
  logger.info('Loading AdminDashboard...');
  return import('@/features/admin/AdminDashboard').then(module => {
    logger.info('AdminDashboard loaded successfully');
    return module;
  });
});

const AdminLoginForm = lazy(() => {
  logger.info('Loading AdminLoginForm...');
  return import('@/features/admin/AdminLoginForm');
});

const AdminProtectedRoute = lazy(() => {
  logger.info('Loading AdminProtectedRoute...');
  return import('@/features/admin/AdminProtectedRoute');
});

// Feature Pages (Medium Priority - load on demand)
export const TemplateManagementPage = lazy(() => {
  logger.info('Loading TemplateManagementPage...');
  return import('@/features/templates/TemplateManagementPage');
});

export const AdminUserActivityMonitor = lazy(() => {
  logger.info('Loading AdminUserActivityMonitor...');
  return import('@/features/admin/AdminUserActivityMonitor').then(module => ({ default: module.AdminUserActivityMonitor }));
});

// Placeholder pages can be inline (Low Priority)
const AdminUsersPage = lazy(() =>
  Promise.resolve({
    default: () => (
      <div className="p-6">
        <h1 className="text-2xl font-bold mb-4">User Management</h1>
        <p className="text-gray-600">User management interface will be implemented here.</p>
      </div>
    )
  })
);

const AdminSecurityPage = lazy(() =>
  Promise.resolve({
    default: () => (
      <div className="p-6">
        <h1 className="text-2xl font-bold mb-4">Security</h1>
        <p className="text-gray-600">Security management interface will be implemented here.</p>
      </div>
    )
  })
);

const AdminAuditLogsPage = lazy(() =>
  Promise.resolve({
    default: () => (
      <div className="p-6">
        <h1 className="text-2xl font-bold mb-4">Audit Logs</h1>
        <Suspense fallback={<LoadingSpinner />}>
          <AdminUserActivityMonitor />
        </Suspense>
      </div>
    )
  })
);

const AdminSystemPage = lazy(() =>
  Promise.resolve({
    default: () => (
      <div className="p-6">
        <h1 className="text-2xl font-bold mb-4">System Management</h1>
        <p className="text-gray-600">System management interface will be implemented here.</p>
      </div>
    )
  })
);

const AdminReportsPage = lazy(() =>
  Promise.resolve({
    default: () => (
      <div className="p-6">
        <h1 className="text-2xl font-bold mb-4">Reports</h1>
        <p className="text-gray-600">Reports interface will be implemented here.</p>
      </div>
    )
  })
);

const AdminTemplatesPage = lazy(() =>
  Promise.resolve({
    default: () => (
      <div className="p-0">
        <Suspense fallback={<PageLoadingSkeleton />}>
          <TemplateManagementPage />
        </Suspense>
      </div>
    )
  })
);

const AdminSettingsPage = lazy(() =>
  Promise.resolve({
    default: () => (
      <div className="p-6">
        <h1 className="text-2xl font-bold mb-4">Settings</h1>
        <p className="text-gray-600">Settings interface will be implemented here.</p>
      </div>
    )
  })
);

const AdminProfilePage = lazy(() =>
  Promise.resolve({
    default: () => (
      <div className="p-6">
        <h1 className="text-2xl font-bold mb-4">Profile Settings</h1>
        <p className="text-gray-600">Profile settings interface will be implemented here.</p>
      </div>
    )
  })
);

// ============================================================================
// Preloading Functions
// ============================================================================

/**
 * Preload critical components on app initialization
 * Call this in App.tsx after initial render
 */
// eslint-disable-next-line react-refresh/only-export-components
export const preloadCriticalComponents = () => {
  logger.info('Preloading critical components...');

  // Preload dashboard (most visited page)
  const dashboardPreload = import('@/features/admin/AdminDashboard');

  // Preload protected route wrapper
  const protectedRoutePreload = import('@/features/admin/AdminProtectedRoute');

  // Return promises for tracking if needed
  return Promise.all([dashboardPreload, protectedRoutePreload])
    .then(() => {
      logger.info('Critical components preloaded successfully');
    })
    .catch((error) => {
      logger.error('Failed to preload critical components:', error);
    });
};

/**
 * Preload component on hover (prefetch optimization)
 * Usage: onMouseEnter={() => preloadOnHover('dashboard')}
 */
// eslint-disable-next-line react-refresh/only-export-components
export const preloadOnHover = (route: string) => {
  logger.debug(`Preloading ${route} on hover...`);

  switch (route) {
    case 'dashboard':
      import('@/features/admin/AdminDashboard');
      break;
    case 'templates':
      import('@/features/templates/TemplateManagementPage');
      break;
    case 'users':
      // Already inline, no need to preload
      break;
    default:
      logger.warn(`Unknown route for preload: ${route}`);
  }
};

// ============================================================================
// Admin Login Page Component
// ============================================================================

const AdminLoginPage: React.FC = () => {
  const handleLogin = async (credentials: AdminLoginCredentials): Promise<AdminLoginResponse> => {
    // TODO: Implement admin login logic
    logger.info('Admin login', { email: credentials.email })
    return {
      success: true,
      user: {
        id: 'temp-admin-id',
        email: credentials.email,
        full_name: 'Admin',
        role: UserRole.ADMIN,
        is_active: true,
        permissions: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        last_login: new Date().toISOString(),
        two_factor_enabled: false,
        failed_login_attempts: 0,
        locked_until: null,
        // Missing fields
        firebase_uid: 'mock-firebase-uid',
        auth_provider: AuthProvider.LOCAL,
        firebase_last_sign_in: null,
        firebase_created_at: null,
        firebase_email_verified: true,
        firebase_display_name: 'Admin User',
        firebase_photo_url: null,
        firebase_custom_claims: {},
        last_firebase_sync: null,
        is_locked: false,
        force_change_password: false,
        last_password_change: null,
      },
      token: 'temp-token',
      refreshToken: 'temp-refresh',
    }
  }

  return (
    <ErrorBoundary>
      <Suspense fallback={<LoadingSpinner />}>
        <AdminLoginForm onLogin={handleLogin} />
      </Suspense>
    </ErrorBoundary>
  );
};

// ============================================================================
// Main Routes Component
// ============================================================================

/**
 * AdminRoutes with Lazy Loading
 *
 * All routes are wrapped in Suspense boundaries with appropriate
 * loading states. Error boundaries catch loading errors gracefully.
 */
const AdminRoutes: React.FC = () => {
  logger.debug('Rendering AdminRoutes with lazy loading');

  return (
    <Routes>
      {/* Public Route - Login */}
      <Route
        path="/login"
        element={<AdminLoginPage />}
      />

      {/* Protected Routes - All wrapped in lazy-loaded ProtectedRoute */}
      <Route
        path="/*"
        element={
          <ErrorBoundary>
            <Suspense fallback={<PageLoadingSkeleton />}>
              <AdminProtectedRoute>
                <Routes>
                  {/* Dashboard - Most visited, use specialized skeleton */}
                  <Route
                    path="/dashboard"
                    element={
                      <ErrorBoundary>
                        <Suspense fallback={<DashboardLoadingSkeleton />}>
                          <AdminDashboard />
                        </Suspense>
                      </ErrorBoundary>
                    }
                  />

                  {/* User Management */}
                  <Route
                    path="/users"
                    element={
                      <ErrorBoundary>
                        <Suspense fallback={<PageLoadingSkeleton />}>
                          <AdminUsersPage />
                        </Suspense>
                      </ErrorBoundary>
                    }
                  />

                  {/* Security */}
                  <Route
                    path="/security"
                    element={
                      <ErrorBoundary>
                        <Suspense fallback={<PageLoadingSkeleton />}>
                          <AdminSecurityPage />
                        </Suspense>
                      </ErrorBoundary>
                    }
                  />

                  {/* Audit Logs */}
                  <Route
                    path="/audit"
                    element={
                      <ErrorBoundary>
                        <Suspense fallback={<PageLoadingSkeleton />}>
                          <AdminAuditLogsPage />
                        </Suspense>
                      </ErrorBoundary>
                    }
                  />

                  {/* System Management */}
                  <Route
                    path="/system"
                    element={
                      <ErrorBoundary>
                        <Suspense fallback={<PageLoadingSkeleton />}>
                          <AdminSystemPage />
                        </Suspense>
                      </ErrorBoundary>
                    }
                  />

                  {/* Reports */}
                  <Route
                    path="/reports"
                    element={
                      <ErrorBoundary>
                        <Suspense fallback={<PageLoadingSkeleton />}>
                          <AdminReportsPage />
                        </Suspense>
                      </ErrorBoundary>
                    }
                  />

                  {/* Templates */}
                  <Route
                    path="/templates"
                    element={
                      <ErrorBoundary>
                        <Suspense fallback={<PageLoadingSkeleton />}>
                          <AdminTemplatesPage />
                        </Suspense>
                      </ErrorBoundary>
                    }
                  />

                  {/* Settings */}
                  <Route
                    path="/settings"
                    element={
                      <ErrorBoundary>
                        <Suspense fallback={<PageLoadingSkeleton />}>
                          <AdminSettingsPage />
                        </Suspense>
                      </ErrorBoundary>
                    }
                  />

                  {/* Profile */}
                  <Route
                    path="/profile"
                    element={
                      <ErrorBoundary>
                        <Suspense fallback={<PageLoadingSkeleton />}>
                          <AdminProfilePage />
                        </Suspense>
                      </ErrorBoundary>
                    }
                  />

                  {/* Default redirect to dashboard */}
                  <Route path="/" element={<Navigate to="/dashboard" replace />} />

                  {/* 404 - Not Found */}
                  <Route
                    path="*"
                    element={
                      <div className="p-6">
                        <h1 className="text-2xl font-bold mb-4">404 - Page Not Found</h1>
                        <p className="text-gray-600">The page you're looking for doesn't exist.</p>
                      </div>
                    }
                  />
                </Routes>
              </AdminProtectedRoute>
            </Suspense>
          </ErrorBoundary>
        }
      />
    </Routes>
  );
};

export default AdminRoutes;
