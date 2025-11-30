/**
 * useFlows Hook
 *
 * Hook for managing flow data and operations.
 * Connects to V2 API endpoints for flow management.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type { FlowState, FlowAnalytics } from '@/lib/api-client/types';
import { apiClient } from '@/lib/api-client';
import { createLogger } from '@/utils/logger';

const logger = createLogger('useFlows');

/**
 * Flow data interface with UI-specific fields
 */
export interface FlowData extends FlowState {
  // Additional UI-specific fields can be added here
}

/**
 * Hook options interface
 */
export interface UseFlowsOptions {
  flowType?: string;
  isActive?: boolean;
  search?: string;
  limit?: number;
  enabled?: boolean;
}

/**
 * Hook return type
 */
export interface UseFlowsReturn {
  data: FlowData[];
  flows: FlowData[]; // Legacy alias
  analytics: FlowAnalytics | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
  hasMore: boolean;
  total: number | null;
}

/**
 * Flow stats return type
 */
export interface UseFlowStatsReturn {
  data: FlowAnalytics | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

/**
 * Hook for managing flows - connects to /api/v2/flows
 */
export function useFlows(options?: UseFlowsOptions): UseFlowsReturn {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['flows', options?.flowType, options?.isActive, options?.search, options?.limit],
    queryFn: async () => {
      logger.debug('Fetching flows', { options });
      const response = await apiClient.flows.list({
        flow_type: options?.flowType,
        is_active: options?.isActive,
        search: options?.search,
        limit: options?.limit ?? 50,
      });
      return response;
    },
    enabled: options?.enabled !== false,
    staleTime: 30000, // 30 seconds
    refetchInterval: 60000, // 1 minute
  });

  const flows = (data?.data ?? data?.items ?? []) as FlowData[];

  return {
    data: flows,
    flows, // Legacy alias
    analytics: null, // Use useFlowStats for analytics
    isLoading,
    error: error as Error | null,
    refetch,
    hasMore: data?.has_more ?? false,
    total: data?.total ?? null,
  };
}

/**
 * Hook for fetching flow statistics - connects to /api/v2/flows/analytics
 */
export function useFlowStats(): UseFlowStatsReturn {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['flow-stats'],
    queryFn: async () => {
      logger.debug('Fetching flow statistics');
      const analytics = await apiClient.flows.getAnalytics();
      return analytics as FlowAnalytics;
    },
    staleTime: 60000, // 1 minute
    refetchInterval: 300000, // 5 minutes
  });

  return {
    data: data ?? null,
    isLoading,
    error: error as Error | null,
    refetch,
  };
}

/**
 * Hook for pausing a flow - POST /api/v2/flows/{patientId}/pause
 */
export function usePauseFlow() {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: async (patientId: string) => {
      logger.debug(`Pausing flow for patient: ${patientId}`);
      return await apiClient.flows.pause(patientId);
    },
    onSuccess: (data, patientId) => {
      logger.info(`Flow paused successfully for patient: ${patientId}`);
      // Invalidate relevant queries
      queryClient.invalidateQueries({ queryKey: ['flows'] });
      queryClient.invalidateQueries({ queryKey: ['flow-state', patientId] });
      queryClient.invalidateQueries({ queryKey: ['flow-stats'] });
      // Update cache with new state
      queryClient.setQueryData(['flow-state', patientId], data);
    },
    onError: (error, patientId) => {
      logger.error(`Failed to pause flow for patient: ${patientId}`, { error });
    },
  });

  return {
    mutate: mutation.mutate,
    mutateAsync: mutation.mutateAsync,
    isPending: mutation.isPending,
    isError: mutation.isError,
    error: mutation.error,
    isSuccess: mutation.isSuccess,
    reset: mutation.reset,
  };
}

/**
 * Hook for resuming a flow - POST /api/v2/flows/{patientId}/resume
 */
export function useResumeFlow() {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: async (patientId: string) => {
      logger.debug(`Resuming flow for patient: ${patientId}`);
      return await apiClient.flows.resume(patientId);
    },
    onSuccess: (data, patientId) => {
      logger.info(`Flow resumed successfully for patient: ${patientId}`);
      // Invalidate relevant queries
      queryClient.invalidateQueries({ queryKey: ['flows'] });
      queryClient.invalidateQueries({ queryKey: ['flow-state', patientId] });
      queryClient.invalidateQueries({ queryKey: ['flow-stats'] });
      // Update cache with new state
      queryClient.setQueryData(['flow-state', patientId], data);
    },
    onError: (error, patientId) => {
      logger.error(`Failed to resume flow for patient: ${patientId}`, { error });
    },
  });

  return {
    mutate: mutation.mutate,
    mutateAsync: mutation.mutateAsync,
    isPending: mutation.isPending,
    isError: mutation.isError,
    error: mutation.error,
    isSuccess: mutation.isSuccess,
    reset: mutation.reset,
  };
}

/**
 * Hook for getting a single flow state - GET /api/v2/flows/{patientId}/state
 */
export function useFlowState(patientId: string) {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['flow-state', patientId],
    queryFn: async () => {
      logger.debug(`Fetching flow state for patient: ${patientId}`);
      return await apiClient.flows.getState(patientId);
    },
    enabled: !!patientId,
    staleTime: 30000, // 30 seconds
    refetchInterval: 60000, // 1 minute
  });

  return {
    data: data as FlowState | null,
    isLoading,
    error: error as Error | null,
    refetch,
  };
}
