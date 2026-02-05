/**
 * Enhanced App Provider Component
 *
 * Integrates all frontend improvements including:
 * - Optimized React Query configuration
 * - Enhanced error boundaries
 * - Connection monitoring
 * - Performance monitoring
 * - Toast notifications
 */

import React, { memo, Suspense } from 'react'
import { BrowserRouter } from 'react-router-dom'
import { ErrorBoundary } from '@/components/error/ErrorBoundary'
import { OptimizedQueryProvider } from '@/app/providers/OptimizedQueryProvider'
import { AuthProvider } from '@/app/providers/AuthContext'
import { Toaster } from '@/components/ui/toaster'
import { ConnectionMonitor } from './ConnectionMonitor'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { initializeReact19Optimizations } from '@/lib/react-optimizations'
import { createLogger } from '@/lib/logger'

const logger = createLogger('AppProvider')

interface AppProviderProps {
  children: React.ReactNode
}

// Initialize React 19 optimizations
initializeReact19Optimizations()

const AppLoadingFallback = memo(() => (
  <div className="min-h-screen bg-gray-50 flex items-center justify-center">
    <div className="text-center space-y-4">
      <LoadingSpinner size="lg" />
      <div className="space-y-2">
        <h2 className="text-xl font-semibold text-gray-900">Carregando aplicação</h2>
        <p className="text-gray-600">Inicializando componentes...</p>
      </div>
    </div>
  </div>
))

AppLoadingFallback.displayName = 'AppLoadingFallback'

const AppErrorFallback = memo<{ error: Error }>(({ error }) => (
  <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
    <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-6 text-center">
      <div className="text-red-600 mb-4">
        <svg className="h-12 w-12 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.732-.833-2.5 0L4.268 16.5c-.77.833.192 2.5 1.732 2.5z" />
        </svg>
      </div>
      <h1 className="text-xl font-bold text-gray-900 mb-2">
        Erro na Aplicação
      </h1>
      <p className="text-gray-600 mb-4">
        Ocorreu um erro inesperado. Nossa equipe foi notificada.
      </p>
      <button
        onClick={() => window.location.reload()}
        className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-blue-500"
      >
        Recarregar Página
      </button>
      {process.env['NODE_ENV'] === 'development' && (
        <details className="mt-4 text-left">
          <summary className="cursor-pointer text-sm text-gray-500">
            Detalhes do erro (desenvolvimento)
          </summary>
          <pre className="mt-2 text-xs text-red-600 bg-red-50 p-2 rounded overflow-auto">
            {error.message}
            {error.stack && `\n\n${error.stack}`}
          </pre>
        </details>
      )}
    </div>
  </div>
))

AppErrorFallback.displayName = 'AppErrorFallback'

export const AppProvider = memo<AppProviderProps>(({ children }) => {
  logger.debug('AppProvider rendering with enhanced optimizations')

  return (
    <ErrorBoundary

      fallback={<AppErrorFallback error={new Error('Critical application error')} />}
      onError={(error, errorInfo) => {
        logger.error('Critical app error:', { error, errorInfo })
      }}
    >
      <BrowserRouter>
        <OptimizedQueryProvider>
          <AuthProvider>
            <Suspense fallback={<AppLoadingFallback />}>
              <ErrorBoundary


                onError={(error, errorInfo) => {
                  logger.warn('Page-level error:', { error, errorInfo })
                }}
              >
                {children}
              </ErrorBoundary>
            </Suspense>

            {/* Connection monitoring overlay */}
            <ConnectionMonitor />

            {/* Toast notifications */}
            <Toaster />
          </AuthProvider>
        </OptimizedQueryProvider>
      </BrowserRouter>
    </ErrorBoundary>
  )
})

AppProvider.displayName = 'AppProvider'

export default AppProvider
