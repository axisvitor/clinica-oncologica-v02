/**
 * Production Provider Component
 *
 * Wraps the app with production-ready features including error boundaries,
 * performance monitoring, and React 19 optimizations
 */

import React, { useEffect, memo, Suspense } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
// import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { Toaster } from '@/components/ui/toaster'
import { ErrorBoundary } from '@/components/error/ErrorBoundary'
import { HealthStatusMonitor } from '@/components/system/HealthStatusMonitor'
import { PageSkeleton } from '@/components/ui/skeletons'
import { environment, PRODUCTION_FLAGS, RAILWAY_CONFIG } from '@/lib/environment'
import { initializeReact19Optimizations } from '@/lib/react-optimizations'

// Query client configuration optimized for production
const createQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: {
      // Stale time based on environment
      staleTime: environment.isProduction ? 5 * 60 * 1000 : 1000, // 5min in prod, 1s in dev

      // Cache time optimized for Railway
      gcTime: environment.isRailway ? 10 * 60 * 1000 : 5 * 60 * 1000, // 10min on Railway

      // Retry configuration for production stability
      retry: environment.isProduction ? 3 : 1,
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),

      // Background refetch optimized for Railway
      refetchOnWindowFocus: !environment.isProduction,
      refetchOnReconnect: true,
      refetchInterval: false, // Only manual refetch in production
    },
    mutations: {
      retry: environment.isProduction ? 2 : 0,
      retryDelay: 1000,
    },
  },
})

interface ProductionProviderProps {
  children: React.ReactNode
}

// Performance monitoring wrapper
const PerformanceWrapper = memo<{ children: React.ReactNode }>(({ children }) => {
  useEffect(() => {
    // Initialize React 19 optimizations on mount
    initializeReact19Optimizations()

    // Monitor performance in production
    if (environment.enablePerformanceMonitoring) {
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          // Log slow components or operations
          if (entry.duration > 100) {
            console.warn('Slow operation detected:', {
              name: entry.name,
              duration: entry.duration,
              timestamp: entry.startTime
            })
          }
        }
      })

      observer.observe({ entryTypes: ['measure', 'navigation'] })

      return () => observer.disconnect()
    }
    
    // Return cleanup function even when performance monitoring is disabled
    return () => {}
  }, [])

  return <>{children}</>
})

PerformanceWrapper.displayName = 'PerformanceWrapper'

// Global error fallback component
const GlobalErrorFallback = memo<{ error: Error }>(({ error }) => (
  <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
    <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-8 text-center">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          Sistema Temporariamente Indisponível
        </h1>
        <p className="text-gray-600">
          Estamos trabalhando para resolver o problema.
        </p>
      </div>

      {environment.isDevelopment && (
        <details className="text-left mb-4">
          <summary className="cursor-pointer text-sm font-medium text-gray-700">
            Detalhes Técnicos (Desenvolvimento)
          </summary>
          <pre className="mt-2 text-xs bg-gray-100 p-2 rounded overflow-auto">
            {error.stack}
          </pre>
        </details>
      )}

      <button
        onClick={() => window.location.reload()}
        className="w-full bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700 transition-colors"
      >
        Recarregar Página
      </button>

      <div className="mt-4 text-xs text-gray-500">
        <p>
          Ambiente: {environment.isProduction ? 'Produção' : 'Desenvolvimento'}
          {environment.isRailway && ' (Railway)'}
        </p>
        <p>Versão: {environment.appVersion}</p>
      </div>
    </div>
  </div>
))

GlobalErrorFallback.displayName = 'GlobalErrorFallback'

// App loading fallback
const AppLoadingFallback = memo(() => (
  <PageSkeleton
    showHeader={true}
    showNavigation={true}
    className="animate-pulse"
  >
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="h-32 bg-gray-200 rounded-lg" />
        ))}
      </div>
      <div className="h-64 bg-gray-200 rounded-lg" />
      <div className="h-48 bg-gray-200 rounded-lg" />
    </div>
  </PageSkeleton>
))

AppLoadingFallback.displayName = 'AppLoadingFallback'

export const ProductionProvider = memo<ProductionProviderProps>(({ children }) => {
  const queryClient = React.useMemo(() => createQueryClient(), [])

  useEffect(() => {
    // Log environment info
    if (environment.enableDebugLogs) {
      console.log('🚀 Production Provider initialized:', {
        environment: environment.isProduction ? 'production' : 'development',
        railway: environment.isRailway,
        features: PRODUCTION_FLAGS,
        railwayConfig: RAILWAY_CONFIG
      })
    }

    // Setup global error handlers
    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      console.error('Unhandled promise rejection:', event.reason)

      // Prevent default behavior (showing error overlay)
      event.preventDefault()

      // Check if it's a WebSocket error (common and non-critical)
      if (event.reason?.message?.includes('WebSocket') || 
          event.reason?.message?.includes('ws://') ||
          event.reason?.message?.includes('wss://')) {
        console.warn('WebSocket error handled gracefully:', event.reason.message)
        return
      }

      if (environment.enableErrorReporting) {
        // Report to monitoring service
        if ((window as any).Sentry) {
          (window as any).Sentry.captureException(event.reason)
        }
      }
    }

    const handleError = (event: ErrorEvent) => {
      console.error('Global error:', event.error)

      if (environment.enableErrorReporting) {
        // Report to monitoring service
        if ((window as any).Sentry) {
          (window as any).Sentry.captureException(event.error)
        }
      }
    }

    window.addEventListener('unhandledrejection', handleUnhandledRejection)
    window.addEventListener('error', handleError)

    return () => {
      window.removeEventListener('unhandledrejection', handleUnhandledRejection)
      window.removeEventListener('error', handleError)
    }
  }, [])

  return (
    <ErrorBoundary
      level="critical"
      enableReporting={environment.enableErrorReporting}
      fallback={<GlobalErrorFallback error={new Error('Critical application error')} />}
    >
      <QueryClientProvider client={queryClient}>
        <PerformanceWrapper>
          <Suspense fallback={<AppLoadingFallback />}>
            {children}

            {/* Health monitoring in production */}
            {environment.isProduction && (
              <div className="fixed bottom-4 right-4 max-w-sm">
                <HealthStatusMonitor />
              </div>
            )}

            {/* Global toast notifications */}
            <Toaster />

            {/* React Query DevTools (development only) */}
            {/* ReactQueryDevtools disabled due to module not found */}
            {/* {environment.isDevelopment && PRODUCTION_FLAGS.ENABLE_DEVTOOLS && (
              <ReactQueryDevtools initialIsOpen={false} />
            )} */}
          </Suspense>
        </PerformanceWrapper>
      </QueryClientProvider>
    </ErrorBoundary>
  )
})

ProductionProvider.displayName = 'ProductionProvider'

export default ProductionProvider