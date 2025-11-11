import { useQuery, UseQueryOptions, UseQueryResult } from '@tanstack/react-query';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createLogger } from '@/lib/logger';

export interface QueryPerformanceMetrics {
  queryKey: string;
  startTime: number;
  endTime: number;
  duration: number;
  fromCache: boolean;
  success: boolean;
  error?: string | undefined;
}

export interface LoadingState {
  isInitialLoading: boolean;
  isRefetching: boolean;
  isFirstFetch: boolean;
  hasEverSucceeded: boolean;
}

interface DedupeCacheEntry<TData> {
  timestamp: number;
  data?: TData;
}

type QueryFunctionType<TData, TError> = NonNullable<UseQueryOptions<TData, TError>['queryFn']>;

type ExecutableQueryFn<TData, TError> = (...args: any[]) => Promise<TData> | TData;

function isExecutableQueryFn<TData, TError>(
  fn?: QueryFunctionType<TData, TError>
): fn is ExecutableQueryFn<TData, TError> {
  return typeof fn === 'function';
}

const metricsStore: QueryPerformanceMetrics[] = [];
const MAX_METRICS_STORED = 100;
const logger = createLogger('useOptimizedQuery');

export function getQueryMetrics(): QueryPerformanceMetrics[] {
  return [...metricsStore];
}

export function getAverageQueryDuration(queryKey: string): number {
  const relevantMetrics = metricsStore.filter(m => m.queryKey === queryKey);
  if (relevantMetrics.length === 0) return 0;

  const totalDuration = relevantMetrics.reduce((sum, m) => sum + m.duration, 0);
  return totalDuration / relevantMetrics.length;
}

export function getCacheHitRate(queryKey: string): number {
  const relevantMetrics = metricsStore.filter(m => m.queryKey === queryKey);
  if (relevantMetrics.length === 0) return 0;

  const cacheHits = relevantMetrics.filter(m => m.fromCache).length;
  return (cacheHits / relevantMetrics.length) * 100;
}

export function clearQueryMetrics(): void {
  metricsStore.length = 0;
}

export function useConfiguredQuery<TData, TError>(
  queryOptions: UseQueryOptions<TData, TError>,
  dedupeAwareQueryFn?: QueryFunctionType<TData, TError>
) {
  return useQuery({
    ...queryOptions,
    queryFn: dedupeAwareQueryFn ?? queryOptions.queryFn,
    staleTime: queryOptions.staleTime ?? 30000,
    gcTime: queryOptions.gcTime ?? 300000,
    refetchOnWindowFocus: queryOptions.refetchOnWindowFocus ?? false,
    refetchOnReconnect: queryOptions.refetchOnReconnect ?? true,
    retry: queryOptions.retry ?? 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });
}

interface DedupeHookParams<TData, TError> {
  queryKeyString: string;
  deduplicationWindow: number;
  originalQueryFn?: QueryFunctionType<TData, TError>;
}

export function useDedupeAwareQueryFn<TData, TError>({
  queryKeyString,
  deduplicationWindow,
  originalQueryFn,
}: DedupeHookParams<TData, TError>) {
  const dedupeCacheRef = useRef<Record<string, DedupeCacheEntry<TData>>>({});
  const dedupeWindowMs = Math.max(deduplicationWindow, 0);

  useEffect(() => {
    const cacheReference = dedupeCacheRef.current;
    return () => {
      delete cacheReference[queryKeyString];
    };
  }, [queryKeyString]);

  return useMemo(() => {
    if (!isExecutableQueryFn(originalQueryFn)) {
      return originalQueryFn;
    }

    const executableFn = originalQueryFn;

    return (async (...args: Parameters<typeof executableFn>) => {
      const now = Date.now();
      const cacheEntry = dedupeCacheRef.current[queryKeyString];

      if (
        dedupeWindowMs > 0 &&
        cacheEntry &&
        now - cacheEntry.timestamp < dedupeWindowMs &&
        cacheEntry.data !== undefined
      ) {
        logger.debug('[useOptimizedQuery] Deduplicated query execution skipped', {
          queryKey: queryKeyString,
          dedupeWindowMs,
        });
        return cacheEntry.data;
      }

      const result = await executableFn(...args);
      dedupeCacheRef.current[queryKeyString] = {
        timestamp: now,
        data: result,
      };
      return result;
    }) as typeof executableFn;
  }, [originalQueryFn, queryKeyString, dedupeWindowMs]);
}

interface PerformanceTrackingParams<TError> {
  enableMetrics: boolean;
  isFetching: boolean;
  isSuccess: boolean;
  isError: boolean;
  error: TError | null;
  queryKeyString: string;
}

export function usePerformanceMetricsTracking<TError>({
  enableMetrics,
  isFetching,
  isSuccess,
  isError,
  error,
  queryKeyString,
}: PerformanceTrackingParams<TError>) {
  const startTimeRef = useRef<number>(0);
  const [metrics, setMetrics] = useState<QueryPerformanceMetrics | undefined>();

  useEffect(() => {
    if (!enableMetrics) return;

    if (isFetching && startTimeRef.current === 0) {
      startTimeRef.current = Date.now();
    }

    if (!isFetching && startTimeRef.current > 0) {
      const endTime = Date.now();
      const duration = endTime - startTimeRef.current;
      const fromCache = duration < 10;

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
  }, [enableMetrics, isFetching, isSuccess, isError, error, queryKeyString]);

  return metrics;
}

interface SuccessTrackerParams<TData> {
  isSuccess: boolean;
  data: TData | undefined;
  onSuccess?: (data: TData) => void;
}

export function useSuccessTracker<TData>({ isSuccess, data, onSuccess }: SuccessTrackerParams<TData>) {
  const hasEverSucceededRef = useRef(false);

  useEffect(() => {
    if (isSuccess && data !== undefined) {
      hasEverSucceededRef.current = true;
      onSuccess?.(data);
    }
  }, [isSuccess, data, onSuccess]);

  return hasEverSucceededRef.current;
}

interface ErrorNotifierParams<TError> {
  isError: boolean;
  error: TError | null;
  onError?: (error: TError) => void;
}

export function useErrorNotifier<TError>({ isError, error, onError }: ErrorNotifierParams<TError>) {
  useEffect(() => {
    if (isError && error) {
      onError?.(error);
    }
  }, [isError, error, onError]);
}

interface LoadingStateParams {
  isLoading: boolean;
  isFetching: boolean;
  hasEverSucceeded: boolean;
}

export function getLoadingState({
  isLoading,
  isFetching,
  hasEverSucceeded,
}: LoadingStateParams): LoadingState {
  return {
    isInitialLoading: isLoading && !hasEverSucceeded,
    isRefetching: isFetching && hasEverSucceeded,
    isFirstFetch: !hasEverSucceeded,
    hasEverSucceeded,
  };
}

export function useSafeRefetch<TData, TError>(
  refetch: UseQueryResult<TData, TError>['refetch'],
  onError?: (error: TError) => void
) {
  return useCallback(async () => {
    try {
      await refetch();
    } catch (err) {
      logger.error('[useOptimizedQuery] Refetch failed', err);
      onError?.(err as TError);
    }
  }, [refetch, onError]);
}

function storeMetrics(metrics: QueryPerformanceMetrics): void {
  metricsStore.push(metrics);

  if (metricsStore.length > MAX_METRICS_STORED) {
    metricsStore.shift();
  }

  if (import.meta.env.DEV) {
    const color = metrics.success ? 'green' : 'red';
    const cacheIndicator = metrics.fromCache ? '💾' : '🌐';
    logger.debug(
      `%c[Query ${cacheIndicator}] ${metrics.queryKey} - ${metrics.duration}ms`,
      `color: ${color}; font-weight: bold`,
      metrics
    );
  }
}
