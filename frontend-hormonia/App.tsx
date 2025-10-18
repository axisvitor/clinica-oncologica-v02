import React, { Suspense, lazy, useEffect } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from "react-router-dom";
import { Toaster } from "@/components/ui/toaster";
import { AuthProvider } from "@/contexts/AuthContext";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { Layout } from "@/components/layout/Layout";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { LoadingSpinner } from "@/components/ui/loading-spinner";
import { LandingRoute } from "@/pages/LandingRoute";
import { queryClient, persister } from "@/lib/react-query/queryClient";
import { prefetchCriticalRoutes } from "@/utils/route-prefetch";

// Lazy load pages for better performance
const LoginPage = lazy(() => import("@/pages/LoginPage").then((m) => ({ default: m.LoginPage })));
const DashboardPage = lazy(() =>
  import("@/pages/DashboardPage").then((m) => ({ default: m.DashboardPage })),
);
const PatientsPage = lazy(() =>
  import("@/pages/PatientsPage").then((m) => ({ default: m.PatientsPage })),
);
const PatientDetailPage = lazy(() =>
  import("@/pages/PatientDetailPage").then((m) => ({ default: m.PatientDetailPage })),
);
const MessagesPage = lazy(() =>
  import("@/pages/MessagesPage").then((m) => ({ default: m.MessagesPage })),
);
const QuizPage = lazy(() => import("@/pages/QuizPage").then((m) => ({ default: m.QuizPage })));
const MonthlyQuizDashboard = lazy(() =>
  import("@/pages/MonthlyQuizDashboard").then((m) => ({ default: m.MonthlyQuizDashboard })),
);
const ReportsPage = lazy(() =>
  import("@/pages/ReportsPage").then((m) => ({ default: m.ReportsPage })),
);
const AlertsPage = lazy(() =>
  import("@/pages/AlertsPage").then((m) => ({ default: m.AlertsPage })),
);
const AnalyticsPage = lazy(() =>
  import("@/pages/AnalyticsPage").then((m) => ({ default: m.AnalyticsPage })),
);
const SettingsPage = lazy(() =>
  import("@/pages/SettingsPage").then((m) => ({ default: m.SettingsPage })),
);
const FlowsPage = lazy(() => import("@/pages/FlowsPage").then((m) => ({ default: m.FlowsPage })));
const QuestionariosPage = lazy(() =>
  import("@/pages/QuestionariosPage").then((m) => ({ default: m.QuestionariosPage })),
);
// Physician dashboard
const PhysicianDashboard = lazy(() =>
  import("@/pages/PhysicianDashboard").then((m) => ({ default: m.default })),
);
// Admin system import
const AdminApp = lazy(() => import("@/AdminApp"));
const WhatsAppPage = lazy(() =>
  import("@/pages/WhatsAppPage").then((m) => ({ default: m.WhatsAppPage })),
);
const DLQDashboard = lazy(() =>
  import("@/pages/DLQDashboard").then((m) => ({ default: m.DLQDashboard })),
);

// Loading component for Suspense
const PageLoader = () => (
  <div className="min-h-screen flex items-center justify-center">
    <LoadingSpinner size="lg" color="primary" />
  </div>
);

// 404 Not Found component with React Router navigation
const NotFoundPage = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">404</h1>
        <p className="text-lg text-gray-600 mb-8">Página não encontrada</p>
        <button
          onClick={() => navigate("/dashboard")}
          className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
        >
          Voltar ao Dashboard
        </button>
      </div>
    </div>
  );
};

/**
 * React Query Configuration - Phase 2.2 Enhanced with IndexedDB Persistence
 *
 * Configuration is now imported from @/lib/react-query/queryClient
 * for better modularity and testability.
 *
 * Phase 2.2 Performance improvements:
 * 1. IndexedDB persistence: 7-day offline cache with automatic expiration
 * 2. Enhanced deduplication: 30s window (up from 5s) = 40-60% fewer API calls
 * 3. Optimized cache time: 5min memory cache (down from 15min) for better memory management
 * 4. Query batching: Reduces network overhead
 * 5. Smart retries: Exponential backoff for better error handling
 *
 * Expected Phase 2.2 impact:
 * - 40-60% reduction in API calls (deduplication)
 * - 30-50% reduction in component re-renders (React.memo)
 * - Offline-first data access (IndexedDB)
 * - Faster perceived performance (persistent cache)
 * - Lower bandwidth usage (~50% reduction)
 * - Better memory management (optimized gcTime)
 */

function App() {
  // Prefetch critical routes after initial load for better performance
  useEffect(() => {
    // Only prefetch in production or when explicitly enabled
    if (import.meta.env.PROD || import.meta.env.VITE_ENABLE_PREFETCH === "true") {
      console.log("[App] Initializing critical route prefetch");
      prefetchCriticalRoutes();
    }
  }, []);

  return (
    <ErrorBoundary>
      {/* Phase 2.2: PersistQueryClientProvider for IndexedDB persistence */}
      <PersistQueryClientProvider client={queryClient} persistOptions={{ persister }}>
        <AuthProvider>
          <Router>
            <div className="min-h-screen bg-background">
              <Suspense fallback={<PageLoader />}>
                <Routes>
                  <Route path="/login" element={<LoginPage />} />
                  {/* Smart routing: shows loading spinner, then redirects based on auth state and role */}
                  <Route path="/" element={<LandingRoute />} />

                  {/* Protected Routes with Suspense */}
                  <Route
                    path="/dashboard"
                    element={
                      <ProtectedRoute>
                        <Layout>
                          <Suspense fallback={<PageLoader />}>
                            <DashboardPage />
                          </Suspense>
                        </Layout>
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/patients"
                    element={
                      <ProtectedRoute>
                        <Layout>
                          <Suspense fallback={<PageLoader />}>
                            <PatientsPage />
                          </Suspense>
                        </Layout>
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/patients/:id"
                    element={
                      <ProtectedRoute>
                        <Layout>
                          <Suspense fallback={<PageLoader />}>
                            <PatientDetailPage />
                          </Suspense>
                        </Layout>
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/messages"
                    element={
                      <ProtectedRoute>
                        <Layout>
                          <Suspense fallback={<PageLoader />}>
                            <MessagesPage />
                          </Suspense>
                        </Layout>
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/quiz"
                    element={
                      <ProtectedRoute>
                        <Layout>
                          <Suspense fallback={<PageLoader />}>
                            <QuizPage />
                          </Suspense>
                        </Layout>
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/monthly-quiz"
                    element={
                      <ProtectedRoute>
                        <Layout>
                          <Suspense fallback={<PageLoader />}>
                            <MonthlyQuizDashboard />
                          </Suspense>
                        </Layout>
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/reports"
                    element={
                      <ProtectedRoute>
                        <Layout>
                          <Suspense fallback={<PageLoader />}>
                            <ReportsPage />
                          </Suspense>
                        </Layout>
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/alerts"
                    element={
                      <ProtectedRoute>
                        <Layout>
                          <Suspense fallback={<PageLoader />}>
                            <AlertsPage />
                          </Suspense>
                        </Layout>
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/analytics"
                    element={
                      <ProtectedRoute>
                        <Layout>
                          <Suspense fallback={<PageLoader />}>
                            <AnalyticsPage />
                          </Suspense>
                        </Layout>
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/settings"
                    element={
                      <ProtectedRoute>
                        <Layout>
                          <Suspense fallback={<PageLoader />}>
                            <SettingsPage />
                          </Suspense>
                        </Layout>
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/flows"
                    element={
                      <ProtectedRoute>
                        <Layout>
                          <Suspense fallback={<PageLoader />}>
                            <FlowsPage />
                          </Suspense>
                        </Layout>
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/questionarios"
                    element={
                      <ProtectedRoute>
                        <Layout>
                          <Suspense fallback={<PageLoader />}>
                            <QuestionariosPage />
                          </Suspense>
                        </Layout>
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/dlq"
                    element={
                      <ProtectedRoute>
                        <Layout>
                          <Suspense fallback={<PageLoader />}>
                            <DLQDashboard />
                          </Suspense>
                        </Layout>
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/admin/*"
                    element={
                      <ProtectedRoute>
                        <Suspense fallback={<PageLoader />}>
                          <AdminApp />
                        </Suspense>
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/whatsapp"
                    element={
                      <ProtectedRoute>
                        <Layout>
                          <Suspense fallback={<PageLoader />}>
                            <WhatsAppPage />
                          </Suspense>
                        </Layout>
                      </ProtectedRoute>
                    }
                  />

                  {/* Physician Dashboard Routes */}
                  <Route
                    path="/physician/dashboard"
                    element={
                      <ProtectedRoute requiredRoles={["PHYSICIAN", "DOCTOR", "ADMIN"]}>
                        <Layout>
                          <Suspense fallback={<PageLoader />}>
                            <PhysicianDashboard />
                          </Suspense>
                        </Layout>
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/physician/patients/:id"
                    element={
                      <ProtectedRoute requiredRoles={["PHYSICIAN", "DOCTOR", "ADMIN"]}>
                        <Layout>
                          <Suspense fallback={<PageLoader />}>
                            <PatientDetailPage />
                          </Suspense>
                        </Layout>
                      </ProtectedRoute>
                    }
                  />

                  {/* 404 Catch-all Route */}
                  <Route path="*" element={<NotFoundPage />} />
                </Routes>
              </Suspense>
            </div>
            <Toaster />
          </Router>
        </AuthProvider>
      </PersistQueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
