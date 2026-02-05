/**
 * React 19 Optimizations and Performance Utilities
 *
 * Provides utilities for React 19 features and Railway deployment optimization
 */

import React, { useCallback, useRef, useEffect } from 'react'
import ReactDOM from 'react-dom'
import { QueryClient } from '@tanstack/react-query'
import { environment, REACT_19_FLAGS } from './environment'
import { createLogger } from '@/lib/logger'

const logger = createLogger('React19')

// React 19 transition utilities
export function useOptimizedTransition() {
  // Use React 19 startTransition if available, fallback to setTimeout
  const startTransition = useCallback((callback: () => void) => {
    if ('startTransition' in React && typeof React.startTransition === 'function') {
      React.startTransition(callback)
    } else {
      // Fallback for pre-React 19
      setTimeout(callback, 0)
    }
  }, [])

  return { startTransition }
}

// Optimized memo with React 19 features
export function createOptimizedMemo<P extends object>(
  Component: React.ComponentType<P>,
  areEqual?: (prev: Readonly<P>, next: Readonly<P>) => boolean
): React.MemoExoticComponent<React.ComponentType<P>> {
  if (REACT_19_FLAGS.ENABLE_CONCURRENT_FEATURES) {
    // Use React 19 enhanced memo if available
    return React.memo(Component, areEqual)
  }

  // Fallback to regular memo
  return React.memo(Component, areEqual)
}

// Performance monitoring hook
export function usePerformanceMonitoring(componentName: string) {
  const renderCount = useRef(0)

  useEffect(() => {
    renderCount.current += 1

    if (environment.enablePerformanceMonitoring) {
      // Mark performance measurements for React 19 profiler
      if ('mark' in performance) {
        performance.mark(`${componentName}-render-start`)
      }

      return () => {
        if ('mark' in performance && 'measure' in performance) {
          performance.mark(`${componentName}-render-end`)
          performance.measure(
            `${componentName}-render`,
            `${componentName}-render-start`,
            `${componentName}-render-end`
          )
        }
      }
    }

    // Return cleanup function even when performance monitoring is disabled
    return () => { }
  })

  const getMetrics = useCallback(() => ({
    renderCount: renderCount.current,
    componentName
  }), [componentName])

  return { getMetrics }
}

// Optimized state updates for React 19
export function useOptimizedState<T>(
  initialValue: T
): [T, (value: T | ((prev: T) => T)) => void] {
  const [state, setState] = React.useState(initialValue)

  const optimizedSetState = useCallback((value: T | ((prev: T) => T)) => {
    if (REACT_19_FLAGS.ENABLE_AUTOMATIC_BATCHING) {
      // React 19 automatically batches updates
      setState(value)
    } else {
      // Manual batching for older React versions
      const batchedUpdates = (React as { unstable_batchedUpdates?: (fn: () => void) => void }).unstable_batchedUpdates
      if (typeof batchedUpdates === 'function') {
        batchedUpdates(() => {
          setState(value)
        })
      } else {
        setState(value)
      }
    }
  }, [])

  return [state, optimizedSetState]
}

// Suspense-compatible data fetching
export function createSuspenseResource<T>(
  fetchFn: () => Promise<T>
): () => T {
  let status: 'pending' | 'success' | 'error' = 'pending'
  let result: T | unknown
  let suspender: Promise<T>

  const resource = () => {
    if (status === 'pending') {
      suspender = fetchFn().then(
        (data: T) => {
          status = 'success'
          result = data
          return data
        },
        (error: unknown) => {
          status = 'error'
          result = error
          throw error
        }
      ) as Promise<T>
      throw suspender
    } else if (status === 'error') {
      throw result
    } else if (status === 'success') {
      return result as T
    }
    throw new Error('Unexpected resource status')
  }

  return resource
}

// React 19 concurrent features wrapper
export function withConcurrentFeatures<P extends object>(
  Component: React.ComponentType<P>
) {
  if (!REACT_19_FLAGS.ENABLE_CONCURRENT_FEATURES) {
    return Component
  }

  const ConcurrentComponent = React.memo((props: P) => {
    usePerformanceMonitoring(Component.displayName || Component.name)

    return <Component {...props} />
  })

  ConcurrentComponent.displayName = `Concurrent(${Component.displayName || Component.name})`
  return ConcurrentComponent
}

// Railway deployment optimizations
export const RailwayOptimizations = {
  // Preload critical resources
  preloadCriticalResources: () => {
    if (typeof window !== 'undefined') {
      // Preload critical API endpoints
      const criticalEndpoints = [
        '/api/v2/auth/me',
        '/api/v2/analytics/overview'
      ]

      criticalEndpoints.forEach(endpoint => {
        const link = document.createElement('link')
        link.rel = 'prefetch'
        link.href = `${environment.apiUrl}${endpoint}`
        document.head.appendChild(link)
      })
    }
  },

  // Optimize bundle loading for Railway
  optimizeBundleLoading: () => {
    if (typeof window !== 'undefined' && environment.isRailway) {
      // Preload critical chunks
      // Preloading disabled due to type issues
      // const globModules = import.meta.glob('../pages/*.tsx', { eager: false })
      // Critical pages preloading would go here
    }
  },

  // Monitor Railway-specific metrics
  monitorRailwayMetrics: () => {
    if (environment.isRailway && environment.enablePerformanceMonitoring) {
      // Monitor connection quality specific to Railway
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (entry.entryType === 'navigation') {
            const nav = entry as PerformanceNavigationTiming

            // Log Railway-specific performance metrics
            logger.info('Railway Performance Metrics:', {
              dns: nav.domainLookupEnd - nav.domainLookupStart,
              connect: nav.connectEnd - nav.connectStart,
              ssl: nav.connectEnd - nav.secureConnectionStart,
              ttfb: nav.responseStart - nav.requestStart,
              response: nav.responseEnd - nav.responseStart,
              dom: nav.domContentLoadedEventEnd - nav.responseEnd,
              load: nav.loadEventEnd - nav.loadEventStart
            })
          }
        }
      })

      observer.observe({ entryTypes: ['navigation', 'resource'] })
    }
  }
}

// Error boundary for React 19
export function createReact19ErrorBoundary() {
  type ErrorBoundaryProps = {
    children: React.ReactNode
    fallback?: React.ComponentType<{ error: Error }>
  }

  return class React19ErrorBoundary extends React.Component<
    ErrorBoundaryProps,
    { hasError: boolean; error: Error | null }
  > {
    constructor(props: ErrorBoundaryProps) {
      super(props)
      this.state = { hasError: false, error: null }
    }

    static getDerivedStateFromError(error: Error) {
      return { hasError: true, error }
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
      // React 19 enhanced error logging
      if (environment.enableErrorReporting) {
        logger.error('React 19 Error Boundary:', {
          error,
          errorInfo,
          reactVersion: React.version,
          timestamp: new Date().toISOString()
        })
      }
    }

    render() {
      if (this.state.hasError) {
        const FallbackComponent = this.props.fallback
        if (FallbackComponent) {
          return <FallbackComponent error={this.state.error!} />
        }
        return <div>Something went wrong.</div>
      }

      return this.props.children
    }
  }
}

// React 19 feature detection
export const React19Features = {
  hasStartTransition: 'startTransition' in React,
  hasUseDeferredValue: 'useDeferredValue' in React,
  hasUseId: 'useId' in React,
  hasConcurrentFeatures: 'unstable_createRoot' in ReactDOM || 'createRoot' in ReactDOM,
  hasStrictEffects: REACT_19_FLAGS.ENABLE_STRICT_EFFECTS,

  // Log detected features
  logFeatures: () => {
    if (environment.enableDebugLogs) {
      logger.info('React 19 Feature Detection:', {
        reactVersion: React.version,
        features: {
          startTransition: React19Features.hasStartTransition,
          useDeferredValue: React19Features.hasUseDeferredValue,
          useId: React19Features.hasUseId,
          concurrentFeatures: React19Features.hasConcurrentFeatures,
          strictEffects: React19Features.hasStrictEffects
        }
      })
    }
  }
}

// Initialize React 19 optimizations
export function initializeReact19Optimizations() {
  if (environment.isProduction) {
    // Initialize Railway optimizations
    RailwayOptimizations.preloadCriticalResources()
    RailwayOptimizations.optimizeBundleLoading()
    RailwayOptimizations.monitorRailwayMetrics()
  }

  // Log React 19 features
  React19Features.logFeatures()

  // Enable React 19 profiler in development
  const profilingEnabled = Boolean(
    (REACT_19_FLAGS as { ENABLE_PROFILING?: boolean }).ENABLE_PROFILING
  )
  if (environment.isDevelopment && profilingEnabled) {
    if ('Profiler' in React) {
      logger.info('React 19 Profiler enabled for development')
    }
  }
}

// Optimized Query Client for React Query
export function createOptimizedQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 5 * 60 * 1000, // 5 minutes
        gcTime: 10 * 60 * 1000, // 10 minutes
        retry: (failureCount: number, error: unknown) => {
          const status = typeof error === 'object' && error !== null && 'status' in error
            ? (error as { status?: number }).status
            : undefined
          if (status === 404) return false
          return failureCount < 3
        },
        refetchOnWindowFocus: false,
        refetchOnReconnect: 'always'
      },
      mutations: {
        retry: 1
      }
    }
  })
}

// All functions are already exported individually above
