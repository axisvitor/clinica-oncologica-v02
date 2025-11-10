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

import React, { useState, useEffect } from 'react';
import type { UseQueryOptions, UseQueryResult } from '@tanstack/react-query';
import type { LoadingState, QueryPerformanceMetrics } from './useOptimizedQuery.helpers';
import {
  getLoadingState,
  getQueryMetrics,
  useConfiguredQuery,
  useDedupeAwareQueryFn,
  useErrorNotifier,
  usePerformanceMetricsTracking,
  useSafeRefetch,
  useSuccessTracker,
} from './useOptimizedQuery.helpers';

export { getQueryMetrics, getAverageQueryDuration, getCacheHitRate, clearQueryMetrics } from './useOptimizedQuery.helpers';

export type { QueryPerformanceMetrics, LoadingState } from './useOptimizedQuery.helpers';

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
/**
 * Get all stored metrics for analysis
 */
/**
 * Optimized query hook with automatic deduplication and performance tracking
 *
 * @param options - Query options with optimization features
 * @returns Extended query result with loading states and metrics
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

  const queryKeyString = JSON.stringify(queryOptions.queryKey);
  const dedupeAwareQueryFn = useDedupeAwareQueryFn<TData, TError>({
    queryKeyString,
    deduplicationWindow,
    originalQueryFn: queryOptions.queryFn,
  });

  const queryResult = useConfiguredQuery<TData, TError>(queryOptions, dedupeAwareQueryFn);

  const { data, error, isLoading, isFetching, isSuccess, isError, refetch } = queryResult;

  const metrics = usePerformanceMetricsTracking<TError>({
    enableMetrics,
    isFetching,
    isSuccess,
    isError,
    error,
    queryKeyString,
  });

  const hasEverSucceeded = useSuccessTracker({
    data,
    isSuccess,
    onSuccess,
  });

  useErrorNotifier({ isError, error, onError });

  const loadingState = getLoadingState({
    isLoading,
    isFetching,
    hasEverSucceeded,
  });

  const safeRefetch = useSafeRefetch(refetch, onError);

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
