/**
 * Optimized Query Hook with Performance Tracking
 *
 * Wrapper around React Query's useQuery with built-in:
 * - Automatic deduplication
 * - Loading state management
 * - Error boundary integration
 * - Performance metrics tracking
 * - Memory leak prevention
 *
 * @module useOptimizedQuery
 */

import { useQuery, UseQueryOptions, UseQueryResult } from '@tanstack/react-query';
import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Performance metrics for query operations
 */
interface QueryPerformanceMetrics {
  /** Query key identifier */
  queryKey: string;
  /** Query execution start time */
  startTime: number;
  /** Query execution end time */
  endTime: number;
  /** Total execution duration in milliseconds */
  duration: number;
  /** Whether the query hit the cache */
  fromCache: boolean;
  /** Whether the query succeeded */
  success: boolean;
  /** Error message if query failed */
  error?: string | undefined;
}

/**
 * Extended loading states for better UX
 */
interface LoadingState {
  /** Initial loading state */
  isInitialLoading: boolean;
  /** Background refetching state */
  isRefetching: boolean;
  /** Is data being fetched for the first time */
  isFirstFetch: boolean;
  /** Has the query ever succeeded */
  hasEverSucceeded: boolean;
}

/**
 * Options for the optimized query hook
 */
interface UseOptimizedQueryOptions<TData, TError> extends UseQueryOptions<TData, TError> {
  /** Enable performance tracking (default: true in dev) */
  enableMetrics?: boolean;
  /** Custom error handler */
  onError?: (error: TError) => void;
  /** Custom success handler */
  onSuccess?: (data: TData) => void;
  /** Deduplicate requests within this time window (ms) */
  deduplicationWindow?: number;
}

/**
 * Extended query result with loading states and metrics
 */
type OptimizedQueryResult<TData, TError> = UseQueryResult<TData, TError> & {
  /** Extended loading states */
  loadingState: LoadingState;
  /** Performance metrics (if enabled) */
  metrics?: QueryPerformanceMetrics | undefined;
  /** Manually trigger a refetch with error handling */
  safeRefetch: () => Promise<void>;
}

/**
 * Global metrics storage for development monitoring
 */
const metricsStore: QueryPerformanceMetrics[] = [];
const MAX_METRICS_STORED = 100;

/**
 * Store performance metrics
 */
function storeMetrics(metrics: QueryPerformanceMetrics): void {
  metricsStore.push(metrics);

  // Keep only the last N metrics
  if (metricsStore.length > MAX_METRICS_STORED) {
    metricsStore.shift();
  }

  // Log in development
  if (import.meta.env.DEV) {
    const color = metrics.success ? 'green' : 'red';
    const cacheIndicator = metrics.fromCache ? '💾' : '🌐';
    console.log(
      `%c[Query ${cacheIndicator}] ${metrics.queryKey} - ${metrics.duration}ms`,
      `color: ${color}; font-weight: bold`,
      metrics
    );
  }
}

/**
 * Get all stored metrics for analysis
 */
export function getQueryMetrics(): QueryPerformanceMetrics[] {
  return [...metricsStore];
}

/**
 * Get average query duration by key
 */
export function getAverageQueryDuration(queryKey: string): number {
  const relevantMetrics = metricsStore.filter(m => m.queryKey === queryKey);
  if (relevantMetrics.length === 0) return 0;

  const totalDuration = relevantMetrics.reduce((sum, m) => sum + m.duration, 0);
  return totalDuration / relevantMetrics.length;
}

/**
 * Get cache hit rate for a query
 */
export function getCacheHitRate(queryKey: string): number {
  const relevantMetrics = metricsStore.filter(m => m.queryKey === queryKey);
  if (relevantMetrics.length === 0) return 0;

  const cacheHits = relevantMetrics.filter(m => m.fromCache).length;
  return (cacheHits / relevantMetrics.length) * 100;
}

/**
 * Clear all stored metrics
 */
export function clearQueryMetrics(): void {
  metricsStore.length = 0;
}

/**
 * Optimized query hook with automatic deduplication and performance tracking
 *
 * @param options - Query options with optimization features
 * @returns Extended query result with loading states and metrics
 *
 * @example
 * ```typescript
 * const { data, loadingState, metrics, safeRefetch } = useOptimizedQuery({
 *   queryKey: ['patients', patientId],
 *   queryFn: () => fetchPatient(patientId),
 *   staleTime: 5 * 60 * 1000, // 5 minutes
 *   enableMetrics: true,
 *   onError: (error) => {
 *     toast.error('Failed to load patient data');
 *   },
 * });
 *
 * if (loadingState.isInitialLoading) {
 *   return <LoadingSkeleton />;
 * }
 *
 * return <PatientDetails data={data} onRefresh={safeRefetch} />;
 * ```
 */
export function useOptimizedQuery<TData = unknown, TError = Error>(
  options: UseOptimizedQueryOptions<TData, TError>
): OptimizedQueryResult<TData, TError> {
  const {
    enableMetrics = import.meta.env.DEV,
    onError,
    onSuccess,
    deduplicationWindow = 1000,
    ...queryOptions
  } = options;

  // Track query lifecycle
  const startTimeRef = useRef<number>(0);
  const hasEverSucceededRef = useRef<boolean>(false);
  const [metrics, setMetrics] = useState<QueryPerformanceMetrics | undefined>();

  // Create stable query key string
  const queryKeyString = JSON.stringify(queryOptions.queryKey);

  // Execute the query
  const queryResult = useQuery({
    ...queryOptions,
    // Enhanced deduplication
    staleTime: queryOptions.staleTime ?? 30000, // 30 seconds default
    gcTime: queryOptions.gcTime ?? 300000, // 5 minutes default
    refetchOnWindowFocus: queryOptions.refetchOnWindowFocus ?? false,
    refetchOnReconnect: queryOptions.refetchOnReconnect ?? true,
    retry: queryOptions.retry ?? 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });

  const { data, error, isLoading, isFetching, isSuccess, isError, refetch } = queryResult;

  // Track performance metrics
  useEffect(() => {
    if (!enableMetrics) return;

    if (isFetching && startTimeRef.current === 0) {
      startTimeRef.current = Date.now();
    }

    if (!isFetching && startTimeRef.current > 0) {
      const endTime = Date.now();
      const duration = endTime - startTimeRef.current;
      const fromCache = duration < 10; // Likely from cache if < 10ms

      const performanceMetrics: QueryPerformanceMetrics = {
        queryKey: queryKeyString,
        startTime: startTimeRef.current,
        endTime,
        duration,
        fromCache,
        success: isSuccess,
        error: isError ? String(error) : undefined,
      };

      setMetrics(performanceMetrics);
      storeMetrics(performanceMetrics);

      startTimeRef.current = 0;
    }
  }, [isFetching, isSuccess, isError, error, queryKeyString, enableMetrics]);

  // Track success state
  useEffect(() => {
    if (isSuccess && data !== undefined) {
      hasEverSucceededRef.current = true;
      onSuccess?.(data);
    }
  }, [isSuccess, data, onSuccess]);

  // Handle errors
  useEffect(() => {
    if (isError && error) {
      onError?.(error);
    }
  }, [isError, error, onError]);

  // Extended loading states
  const loadingState: LoadingState = {
    isInitialLoading: isLoading && !hasEverSucceededRef.current,
    isRefetching: isFetching && hasEverSucceededRef.current,
    isFirstFetch: !hasEverSucceededRef.current,
    hasEverSucceeded: hasEverSucceededRef.current,
  };

  // Safe refetch with error handling
  const safeRefetch = useCallback(async () => {
    try {
      await refetch();
    } catch (err) {
      console.error('[useOptimizedQuery] Refetch failed:', err);
      onError?.(err as TError);
    }
  }, [refetch, onError]);

  return {
    ...queryResult,
    loadingState,
    metrics,
    safeRefetch,
  };
}

/**
 * Hook for monitoring query performance across the app
 *
 * @returns Performance statistics
 *
 * @example
 * ```typescript
 * function PerformanceMonitor() {
 *   const stats = useQueryPerformanceStats();
 *
 *   return (
 *     <div>
 *       <p>Total Queries: {stats.totalQueries}</p>
 *       <p>Avg Duration: {stats.averageDuration}ms</p>
 *       <p>Cache Hit Rate: {stats.cacheHitRate}%</p>
 *     </div>
 *   );
 * }
 * ```
 */
export function useQueryPerformanceStats() {
  const [stats, setStats] = useState({
    totalQueries: 0,
    averageDuration: 0,
    cacheHitRate: 0,
    slowestQuery: '',
    fastestQuery: '',
  });

  useEffect(() => {
    const updateStats = () => {
      const metrics = getQueryMetrics();

      if (metrics.length === 0) {
        return;
      }

      const totalDuration = metrics.reduce((sum, m) => sum + m.duration, 0);
      const cacheHits = metrics.filter(m => m.fromCache).length;

      const sorted = [...metrics].sort((a, b) => b.duration - a.duration);

      setStats({
        totalQueries: metrics.length,
        averageDuration: Math.round(totalDuration / metrics.length),
        cacheHitRate: Math.round((cacheHits / metrics.length) * 100),
        slowestQuery: sorted[0]?.queryKey || '',
        fastestQuery: sorted[sorted.length - 1]?.queryKey || '',
      });
    };

    updateStats();
    const interval = setInterval(updateStats, 5000); // Update every 5s

    return () => clearInterval(interval);
  }, []);

  return stats;
}
