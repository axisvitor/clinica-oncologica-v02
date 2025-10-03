import React, { Suspense, lazy } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { Toaster } from '@/components/ui/toaster'
import { AuthProvider } from '@/contexts/AuthContext'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import { Layout } from '@/components/layout/Layout'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { LoadingSpinner } from '@/components/ui/loading-spinner'

// Lazy load pages for better performance
const LoginPage = lazy(() => import('@/pages/LoginPage').then(m => ({ default: m.LoginPage })))
const DashboardPage = lazy(() => import('@/pages/DashboardPage').then(m => ({ default: m.DashboardPage })))
const PatientsPage = lazy(() => import('@/pages/PatientsPage').then(m => ({ default: m.PatientsPage })))
const PatientDetailPage = lazy(() => import('@/pages/PatientDetailPage').then(m => ({ default: m.PatientDetailPage })))
const MessagesPage = lazy(() => import('@/pages/MessagesPage').then(m => ({ default: m.MessagesPage })))
const QuizPage = lazy(() => import('@/pages/QuizPage').then(m => ({ default: m.QuizPage })))
const MonthlyQuizDashboard = lazy(() => import('@/pages/MonthlyQuizDashboard').then(m => ({ default: m.MonthlyQuizDashboard })))
const ReportsPage = lazy(() => import('@/pages/ReportsPage').then(m => ({ default: m.ReportsPage })))
const AlertsPage = lazy(() => import('@/pages/AlertsPage').then(m => ({ default: m.AlertsPage })))
const AnalyticsPage = lazy(() => import('@/pages/AnalyticsPage').then(m => ({ default: m.AnalyticsPage })))
const SettingsPage = lazy(() => import('@/pages/SettingsPage').then(m => ({ default: m.SettingsPage })))
const FlowsPage = lazy(() => import('@/pages/FlowsPage').then(m => ({ default: m.FlowsPage })))
const QuestionariosPage = lazy(() => import('@/pages/QuestionariosPage').then(m => ({ default: m.QuestionariosPage })))
// Physician dashboard
const PhysicianDashboard = lazy(() => import('@/pages/PhysicianDashboard').then(m => ({ default: m.default })))
// Admin system import
const AdminApp = lazy(() => import('@/AdminApp'))
const WhatsAppPage = lazy(() => import('@/pages/WhatsAppPage').then(m => ({ default: m.WhatsAppPage })))

// Loading component for Suspense
const PageLoader = () => (
  <div className="min-h-screen flex items-center justify-center">
    <LoadingSpinner size="lg" color="primary" />
  </div>
)

// 404 Not Found component with React Router navigation
const NotFoundPage = () => {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">404</h1>
        <p className="text-lg text-gray-600 mb-8">Página não encontrada</p>
        <button
          onClick={() => navigate('/dashboard')}
          className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
        >
          Voltar ao Dashboard
        </button>
      </div>
    </div>
  )
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 3 * 60 * 1000, // 3 minutes - balanced freshness
      gcTime: 15 * 60 * 1000, // 15 minutes - reduced memory usage
      retry: (failureCount, error: unknown) => {
        const status = (error as { status?: number })?.status
        if (status === 401 || status === 403 || status === 404) {
          return false // Don't retry auth, forbidden, or not found errors
        }
        return failureCount < 2
      },
      refetchOnWindowFocus: false,
      refetchOnMount: false,
      refetchOnReconnect: true,
      networkMode: 'online',
    },
    mutations: {
      retry: 1,
      networkMode: 'online',
      onError: (error) => {
        console.error('Mutation error:', error)
      },
    }
  }
})

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <Router>
            <div className="min-h-screen bg-background">
              <Suspense fallback={<PageLoader />}>
                <Routes>
                  <Route path="/login" element={<LoginPage />} />
                  <Route path="/" element={<Navigate to="/dashboard" replace />} />

                  {/* Protected Routes with Suspense */}
                  <Route path="/dashboard" element={
                    <ProtectedRoute>
                      <Layout>
                        <Suspense fallback={<PageLoader />}>
                          <DashboardPage />
                        </Suspense>
                      </Layout>
                    </ProtectedRoute>
                  } />
                  <Route path="/patients" element={
                    <ProtectedRoute>
                      <Layout>
                        <Suspense fallback={<PageLoader />}>
                          <PatientsPage />
                        </Suspense>
                      </Layout>
                    </ProtectedRoute>
                  } />
                  <Route path="/patients/:id" element={
                    <ProtectedRoute>
                      <Layout>
                        <Suspense fallback={<PageLoader />}>
                          <PatientDetailPage />
                        </Suspense>
                      </Layout>
                    </ProtectedRoute>
                  } />
                  <Route path="/messages" element={
                    <ProtectedRoute>
                      <Layout>
                        <Suspense fallback={<PageLoader />}>
                          <MessagesPage />
                        </Suspense>
                      </Layout>
                    </ProtectedRoute>
                  } />
                  <Route path="/quiz" element={
                    <ProtectedRoute>
                      <Layout>
                        <Suspense fallback={<PageLoader />}>
                          <QuizPage />
                        </Suspense>
                      </Layout>
                    </ProtectedRoute>
                  } />
                  <Route path="/monthly-quiz" element={
                    <ProtectedRoute>
                      <Layout>
                        <Suspense fallback={<PageLoader />}>
                          <MonthlyQuizDashboard />
                        </Suspense>
                      </Layout>
                    </ProtectedRoute>
                  } />
                  <Route path="/reports" element={
                    <ProtectedRoute>
                      <Layout>
                        <Suspense fallback={<PageLoader />}>
                          <ReportsPage />
                        </Suspense>
                      </Layout>
                    </ProtectedRoute>
                  } />
                  <Route path="/alerts" element={
                    <ProtectedRoute>
                      <Layout>
                        <Suspense fallback={<PageLoader />}>
                          <AlertsPage />
                        </Suspense>
                      </Layout>
                    </ProtectedRoute>
                  } />
                  <Route path="/analytics" element={
                    <ProtectedRoute>
                      <Layout>
                        <Suspense fallback={<PageLoader />}>
                          <AnalyticsPage />
                        </Suspense>
                      </Layout>
                    </ProtectedRoute>
                  } />
                  <Route path="/settings" element={
                    <ProtectedRoute>
                      <Layout>
                        <Suspense fallback={<PageLoader />}>
                          <SettingsPage />
                        </Suspense>
                      </Layout>
                    </ProtectedRoute>
                  } />
                  <Route path="/flows" element={
                    <ProtectedRoute>
                      <Layout>
                        <Suspense fallback={<PageLoader />}>
                          <FlowsPage />
                        </Suspense>
                      </Layout>
                    </ProtectedRoute>
                  } />
                  <Route path="/questionarios" element={
                    <ProtectedRoute>
                      <Layout>
                        <Suspense fallback={<PageLoader />}>
                          <QuestionariosPage />
                        </Suspense>
                      </Layout>
                    </ProtectedRoute>
                  } />
                  <Route path="/admin/*" element={
                    <Suspense fallback={<PageLoader />}>
                      <AdminApp />
                    </Suspense>
                  } />
                  <Route path="/whatsapp" element={
                    <ProtectedRoute>
                      <Layout>
                        <Suspense fallback={<PageLoader />}>
                          <WhatsAppPage />
                        </Suspense>
                      </Layout>
                    </ProtectedRoute>
                  } />

                  {/* Physician Dashboard Routes */}
                  <Route path="/physician/dashboard" element={
                    <ProtectedRoute requiredRoles={['PHYSICIAN', 'DOCTOR', 'ADMIN']}>
                      <Layout>
                        <Suspense fallback={<PageLoader />}>
                          <PhysicianDashboard />
                        </Suspense>
                      </Layout>
                    </ProtectedRoute>
                  } />
                  <Route path="/physician/patients/:id" element={
                    <ProtectedRoute requiredRoles={['PHYSICIAN', 'DOCTOR', 'ADMIN']}>
                      <Layout>
                        <Suspense fallback={<PageLoader />}>
                          <PatientDetailPage />
                        </Suspense>
                      </Layout>
                    </ProtectedRoute>
                  } />

                  {/* 404 Catch-all Route */}
                  <Route path="*" element={<NotFoundPage />} />
                </Routes>
              </Suspense>
            </div>
            <Toaster />
          </Router>
        </AuthProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}

export default App
