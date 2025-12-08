/**
 * React Query Key Factories
 *
 * PERFORMANCE OPTIMIZATION (Wave 2):
 * Centralized query key management for better cache control and deduplication
 *
 * Benefits:
 * - Prevents duplicate requests for the same data
 * - Enables smart cache invalidation
 * - Type-safe query keys across the app
 * - Easy cache debugging and monitoring
 *
 * Usage:
 * ```tsx
 * const { data } = useQuery({
 *   queryKey: queryKeys.patients.list({ page: 1, status: 'active' }),
 *   queryFn: () => apiClient.patients.list({ page: 1, status: 'active' })
 * });
 * ```
 */

// Base query keys
const PATIENTS = 'patients' as const;
const ANALYTICS = 'analytics' as const;
const MESSAGES = 'messages' as const;
const QUIZ = 'quiz' as const;
const FLOWS = 'flows' as const;
const ALERTS = 'alerts' as const;
const REPORTS = 'reports' as const;
const ADMIN = 'admin' as const;
const AUTH = 'auth' as const;

/**
 * Query Key Factories
 * Each factory returns a hierarchical key structure for React Query
 */
export const queryKeys = {
  /**
   * Authentication queries
   */
  auth: {
    all: [AUTH] as const,
    me: () => [AUTH, 'me'] as const,
    session: () => [AUTH, 'session'] as const,
    permissions: (userId: string) => [AUTH, 'permissions', userId] as const,
  },

  /**
   * Patient queries
   */
  patients: {
    all: [PATIENTS] as const,
    lists: () => [PATIENTS, 'list'] as const,
    list: (filters: { page?: number; size?: number; search?: string; status?: string; treatment_type?: string }) =>
      [PATIENTS, 'list', filters] as const,
    details: () => [PATIENTS, 'detail'] as const,
    detail: (id: string) => [PATIENTS, 'detail', id] as const,
    timeline: (id: string) => [PATIENTS, 'timeline', id] as const,
    stats: (id: string) => [PATIENTS, 'stats', id] as const,
    riskAssessment: (id: string) => [PATIENTS, 'risk', id] as const,
  },

  /**
   * Analytics queries
   */
  analytics: {
    all: [ANALYTICS] as const,
    dashboard: () => [ANALYTICS, 'dashboard'] as const,
    patients: (params: { start_date?: string; end_date?: string }) =>
      [ANALYTICS, 'patients', params] as const,
    engagement: (params: { start_date?: string; end_date?: string }) =>
      [ANALYTICS, 'engagement', params] as const,
    treatmentDistribution: () => [ANALYTICS, 'treatment-distribution'] as const,
  },

  /**
   * Message queries
   */
  messages: {
    all: [MESSAGES] as const,
    lists: () => [MESSAGES, 'list'] as const,
    list: (filters: { patient_id?: string; page?: number; size?: number }) =>
      [MESSAGES, 'list', filters] as const,
    detail: (id: string) => [MESSAGES, 'detail', id] as const,
  },

  /**
   * Quiz queries
   */
  quiz: {
    all: [QUIZ] as const,
    templates: () => [QUIZ, 'templates'] as const,
    template: (id: string) => [QUIZ, 'template', id] as const,
    sessions: (filters: { patient_id?: string; status?: string }) =>
      [QUIZ, 'sessions', filters] as const,
    session: (id: string) => [QUIZ, 'session', id] as const,
    monthlyStats: (params?: { start_date?: string; end_date?: string }) =>
      [QUIZ, 'monthly-stats', params] as const,
  },

  /**
   * Flow queries
   */
  flows: {
    all: [FLOWS] as const,
    lists: () => [FLOWS, 'list'] as const,
    list: (filters: { patient_id?: string; status?: string }) =>
      [FLOWS, 'list', filters] as const,
    detail: (id: string) => [FLOWS, 'detail', id] as const,
    state: (patientId: string) => [FLOWS, 'state', patientId] as const,
    analytics: () => [FLOWS, 'analytics'] as const,
  },

  /**
   * Alert queries
   */
  alerts: {
    all: [ALERTS] as const,
    lists: () => [ALERTS, 'list'] as const,
    list: (filters: { page?: number; size?: number; severity?: string; acknowledged?: boolean }) =>
      [ALERTS, 'list', filters] as const,
    detail: (id: string) => [ALERTS, 'detail', id] as const,
  },

  /**
   * Report queries
   */
  reports: {
    all: [REPORTS] as const,
    lists: () => [REPORTS, 'list'] as const,
    list: (filters: { page?: number; size?: number }) =>
      [REPORTS, 'list', filters] as const,
    detail: (id: string) => [REPORTS, 'detail', id] as const,
    preview: (id: string) => [REPORTS, 'preview', id] as const,
  },

  /**
   * Admin queries
   */
  admin: {
    all: [ADMIN] as const,
    users: (filters: { page?: number; size?: number; search?: string; role?: string; is_active?: boolean }) =>
      [ADMIN, 'users', filters] as const,
    user: (id: string) => [ADMIN, 'user', id] as const,
    activity: (userId: string, filters?: { page?: number; size?: number }) =>
      [ADMIN, 'activity', userId, filters] as const,
    auditLogs: (filters?: { page?: number; size?: number }) =>
      [ADMIN, 'audit-logs', filters] as const,
  },
} as const;

/**
 * Cache invalidation helpers
 */
export const invalidateQueries = {
  /**
   * Invalidate all patient queries
   */
  allPatients: (queryClient: any) => {
    queryClient.invalidateQueries({ queryKey: queryKeys.patients.all });
  },

  /**
   * Invalidate specific patient
   */
  patient: (queryClient: any, id: string) => {
    queryClient.invalidateQueries({ queryKey: queryKeys.patients.detail(id) });
    queryClient.invalidateQueries({ queryKey: queryKeys.patients.timeline(id) });
    queryClient.invalidateQueries({ queryKey: queryKeys.patients.stats(id) });
  },

  /**
   * Invalidate analytics
   */
  analytics: (queryClient: any) => {
    queryClient.invalidateQueries({ queryKey: queryKeys.analytics.all });
  },

  /**
   * Invalidate messages for a patient
   */
  patientMessages: (queryClient: any, patientId: string) => {
    queryClient.invalidateQueries({
      queryKey: queryKeys.messages.lists(),
      predicate: (query: any) => {
        const filters = query.queryKey[2] as { patient_id?: string };
        return filters?.patient_id === patientId;
      }
    });
  },
};

/**
 * Prefetch helpers for optimistic loading
 */
export const prefetchQueries = {
  /**
   * Prefetch patient details when hovering over patient card
   */
  patientDetail: async (queryClient: any, apiClient: any, id: string) => {
    await queryClient.prefetchQuery({
      queryKey: queryKeys.patients.detail(id),
      queryFn: () => apiClient.patients.get(id),
      staleTime: 5 * 60 * 1000, // 5 minutes
    });
  },

  /**
   * Prefetch dashboard analytics on app load
   */
  dashboardAnalytics: async (queryClient: any, apiClient: any) => {
    await queryClient.prefetchQuery({
      queryKey: queryKeys.analytics.dashboard(),
      queryFn: () => apiClient.analytics.dashboard(),
      staleTime: 3 * 60 * 1000, // 3 minutes
    });
  },
};
