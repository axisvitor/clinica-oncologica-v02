/**
 * Route Definitions
 *
 * Declarative route definitions with lazy loading, authentication,
 * and permission requirements.
 */

import React, { lazy, Suspense, ReactNode } from 'react';
import { ProtectedRoute } from '@/features/auth/ProtectedRoute';
import { Layout } from '@/components/layout/Layout';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { LandingRoute } from '@/pages/LandingRoute';
import { ROUTES } from './routeConfig';

/**
 * Route definition type for rendering
 */
export interface RouteDefinition {
  path: string;
  element: ReactNode;
}

// Lazy load pages for better performance
const LoginPage = lazy(() => import('@/pages/LoginPage').then((m) => ({ default: m.LoginPage })));
const DashboardPage = lazy(() =>
  import('@/pages/DashboardPage').then((m) => ({ default: m.DashboardPage })),
);
const PatientsPage = lazy(() =>
  import('@/pages/PatientsPage').then((m) => ({ default: m.PatientsPage })),
);
const PatientDetailPage = lazy(() =>
  import('@/pages/PatientDetailPage').then((m) => ({ default: m.PatientDetailPage })),
);
const PatientImport = lazy(() =>
  import('@/pages/PatientImport').then((m) => ({ default: m.PatientImport })),
);
const MessagesPage = lazy(() =>
  import('@/pages/MessagesPage').then((m) => ({ default: m.MessagesPage })),
);
const QuizPage = lazy(() => import('@/pages/QuizPage').then((m) => ({ default: m.QuizPage })));
const MonthlyQuizDashboard = lazy(() =>
  import('@/pages/MonthlyQuizDashboard').then((m) => ({ default: m.MonthlyQuizDashboard })),
);
const ReportsPage = lazy(() =>
  import('@/pages/ReportsPage').then((m) => ({ default: m.ReportsPage })),
);
const AlertsPage = lazy(() =>
  import('@/pages/AlertsPage').then((m) => ({ default: m.AlertsPage })),
);
const AnalyticsPage = lazy(() =>
  import('@/pages/AnalyticsPage').then((m) => ({ default: m.AnalyticsPage })),
);
const SettingsPage = lazy(() =>
  import('@/pages/SettingsPage').then((m) => ({ default: m.SettingsPage })),
);
const FlowsPage = lazy(() => import('@/pages/FlowsPage').then((m) => ({ default: m.FlowsPage })));
const QuestionariosPage = lazy(() =>
  import('@/pages/QuestionariosPage').then((m) => ({ default: m.QuestionariosPage })),
);
const PhysicianDashboard = lazy(() =>
  import('@/pages/PhysicianDashboard').then((m) => ({ default: m.default })),
);
const AdminApp = lazy(() => import('@/AdminApp'));
const WhatsAppPage = lazy(() =>
  import('@/pages/WhatsAppPage').then((m) => ({ default: m.WhatsAppPage })),
);
const DLQDashboard = lazy(() =>
  import('@/pages/DLQDashboard').then((m) => ({ default: m.DLQDashboard })),
);
const UnauthorizedPage = lazy(() =>
  import('@/pages/UnauthorizedPage').then((m) => ({ default: m.default })),
);
const HiveMindPage = lazy(() =>
  import('@/pages/HiveMindPage').then((m) => ({ default: m.HiveMindPage })),
);

// Loading component for Suspense
export const PageLoader = () => (
  <div className="min-h-screen flex items-center justify-center">
    <LoadingSpinner size="lg" color="primary" />
  </div>
);

/**
 * Helper to wrap a component with Layout and Suspense
 */
const withLayoutAndSuspense = (Component: React.LazyExoticComponent<React.ComponentType<any>>) => (
  <Layout>
    <Suspense fallback={<PageLoader />}>
      <Component />
    </Suspense>
  </Layout>
);

/**
 * Helper to wrap a component with only Suspense
 */
const withSuspense = (Component: React.LazyExoticComponent<React.ComponentType<any>>) => (
  <Suspense fallback={<PageLoader />}>
    <Component />
  </Suspense>
);

/**
 * Public routes (no authentication required)
 */
export const publicRoutes: RouteDefinition[] = [
  {
    path: ROUTES.ROOT,
    element: <LandingRoute />,
  },
  {
    path: ROUTES.LOGIN,
    element: withSuspense(LoginPage),
  },
  {
    path: ROUTES.UNAUTHORIZED,
    element: withSuspense(UnauthorizedPage),
  },
];

/**
 * Protected routes (authentication required)
 */
export const protectedRoutes: RouteDefinition[] = [
  {
    path: ROUTES.DASHBOARD,
    element: (
      <ProtectedRoute>
        {withLayoutAndSuspense(DashboardPage)}
      </ProtectedRoute>
    ),
  },
  {
    path: ROUTES.PATIENTS.LIST,
    element: (
      <ProtectedRoute>
        {withLayoutAndSuspense(PatientsPage)}
      </ProtectedRoute>
    ),
  },
  {
    path: ROUTES.PATIENTS.DETAIL,
    element: (
      <ProtectedRoute>
        {withLayoutAndSuspense(PatientDetailPage)}
      </ProtectedRoute>
    ),
  },
  {
    path: ROUTES.PATIENTS.IMPORT,
    element: (
      <ProtectedRoute requiredPermission="canImportPatients">
        {withLayoutAndSuspense(PatientImport)}
      </ProtectedRoute>
    ),
  },
  {
    path: ROUTES.MESSAGES,
    element: (
      <ProtectedRoute>
        {withLayoutAndSuspense(MessagesPage)}
      </ProtectedRoute>
    ),
  },
  {
    path: ROUTES.QUIZ,
    element: (
      <ProtectedRoute>
        {withLayoutAndSuspense(QuizPage)}
      </ProtectedRoute>
    ),
  },
  {
    path: ROUTES.MONTHLY_QUIZ,
    element: (
      <ProtectedRoute>
        {withLayoutAndSuspense(MonthlyQuizDashboard)}
      </ProtectedRoute>
    ),
  },
  {
    path: ROUTES.REPORTS,
    element: (
      <ProtectedRoute>
        {withLayoutAndSuspense(ReportsPage)}
      </ProtectedRoute>
    ),
  },
  {
    path: ROUTES.ALERTS,
    element: (
      <ProtectedRoute>
        {withLayoutAndSuspense(AlertsPage)}
      </ProtectedRoute>
    ),
  },
  {
    path: ROUTES.ANALYTICS,
    element: (
      <ProtectedRoute>
        {withLayoutAndSuspense(AnalyticsPage)}
      </ProtectedRoute>
    ),
  },
  {
    path: ROUTES.SETTINGS,
    element: (
      <ProtectedRoute requiredPermission="canManageSettings">
        {withLayoutAndSuspense(SettingsPage)}
      </ProtectedRoute>
    ),
  },
  {
    path: ROUTES.FLOWS,
    element: (
      <ProtectedRoute requiredPermission="canManageFlows">
        {withLayoutAndSuspense(FlowsPage)}
      </ProtectedRoute>
    ),
  },
  {
    path: ROUTES.QUESTIONARIOS,
    element: (
      <ProtectedRoute>
        {withLayoutAndSuspense(QuestionariosPage)}
      </ProtectedRoute>
    ),
  },
  {
    path: ROUTES.HIVE_MIND,
    element: (
      <ProtectedRoute requiredPermission="canAccessHiveMind">
        {withLayoutAndSuspense(HiveMindPage)}
      </ProtectedRoute>
    ),
  },
  {
    path: ROUTES.DLQ,
    element: (
      <ProtectedRoute>
        {withLayoutAndSuspense(DLQDashboard)}
      </ProtectedRoute>
    ),
  },
  {
    path: ROUTES.WHATSAPP,
    element: (
      <ProtectedRoute>
        {withLayoutAndSuspense(WhatsAppPage)}
      </ProtectedRoute>
    ),
  },
];

/**
 * Admin routes (admin permission required)
 */
export const adminRoutes: RouteDefinition[] = [
  {
    path: ROUTES.ADMIN.ROOT,
    element: (
      <ProtectedRoute requiredPermission="canAccessAdmin">
        {withSuspense(AdminApp)}
      </ProtectedRoute>
    ),
  },
];

/**
 * Physician routes (physician role required)
 */
export const physicianRoutes: RouteDefinition[] = [
  {
    path: ROUTES.PHYSICIAN.DASHBOARD,
    element: (
      <ProtectedRoute requiredPermission="canViewPhysicianDashboard">
        {withLayoutAndSuspense(PhysicianDashboard)}
      </ProtectedRoute>
    ),
  },
  {
    path: ROUTES.PHYSICIAN.PATIENT_DETAIL,
    element: (
      <ProtectedRoute requiredPermission="canViewPhysicianPatients">
        {withLayoutAndSuspense(PatientDetailPage)}
      </ProtectedRoute>
    ),
  },
];

/**
 * All routes combined for easy consumption
 */
export const allRoutes: RouteDefinition[] = [
  ...publicRoutes,
  ...protectedRoutes,
  ...adminRoutes,
  ...physicianRoutes,
];
