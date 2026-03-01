/**
 * API Client - Main Entry Point
 *
 * This is the refactored API client with modular architecture.
 * Each domain (auth, patients, quiz, etc.) has its own module.
 *
 * Usage:
 * ```typescript
 * import { apiClient } from '@/lib/api-client'
 *
 * // Authentication
 * await apiClient.auth.login({ email, password })
 *
 * // Patients
 * const patients = await apiClient.patients.list()
 *
 * // Monthly Quiz
 * await apiClient.monthlyQuiz.createLink({ patient_id, quiz_template_id })
 * ```
 */

import { ApiClientCore } from "./core";
import { createAuthApi } from "./auth";
import { createPatientsApi } from "./patients";
import { createAppointmentsApi } from "./appointments";
import { createTreatmentsApi } from "./treatments";
import { createMedicationsApi } from "./medications";
import { createMonthlyQuizApi } from "./monthly-quiz";
import { createAnalyticsApi } from "./analytics";
import { createAdminApi } from "./admin";
import { createDashboardApi } from "./dashboard";
import { createTasksApi, TasksApi } from "./tasks";
import { createHiveMindApi } from "./hive-mind";
import { createLogger } from "../logger";
import { API_BASE_URL } from "../../config";
import type {
  Message,
  MessageListFilters,
  SendMessageRequest,
  BulkMessageRequest,
  BulkMessageResponse,
  ConversationResponse,
  FlowTemplate,
  FlowState,
  FlowListFilters,
  CreateFlowTemplateRequest,
  UpdateFlowTemplateRequest,
  FlowAdvanceRequest,
  FlowPauseRequest as _FlowPauseRequest,
  FlowProcessResponseRequest as _FlowProcessResponseRequest,
  FlowAnalytics,
  Alert,
  AlertListFilters,
  CreateAlertRequest,
  UpdateAlertRequest,
  UnreadCountResponse,
  Report,
  ReportListFilters,
  GenerateReportRequest as _GenerateReportRequest,
  ScheduleReportRequest,
  ScheduledReport,
  AdminUser,
  AdminUserListFilters,
  CreateUserRequest,
  UpdateUserRequest,
  CreateAdminUserRequest,
  UpdateAdminUserRequest,
  ResetPasswordRequest,
  UserActivityEntry,
  UserActivityFilters,
  Role,
  CreateRoleRequest,
  AuditLogEntry,
  AuditLogFilters,
  SystemSettings,
  SystemHealth,
  SystemMetrics,
  SystemStats,
  AIChatRequest as _AIChatRequest,
  AIChatResponse,
  AIHealthResponse,
  AIAnalysisRequest as _AIAnalysisRequest,
  AIAnalysisResponse,
  HumanizeRequest,
  HumanizeResponse,
  AIGenerateResponseRequest as _AIGenerateResponseRequest,
  AIGenerateResponseResponse,
  SentimentAnalysisRequest as _SentimentAnalysisRequest,
  SentimentAnalysisResponse,
  AIInsights,
  AIRecommendations,
  QuizTemplate,
  QuizTemplateResponse,
  QuizSessionStartRequest as _QuizSessionStartRequest,
  QuizSession,
  QuizSubmitRequest as _QuizSubmitRequest,
  QuizSessionListFilters,
  QuizSessionResponses,
  QuizSessionAnalysis,
  PatientQuizResponses,
  NotificationListResponse,
  RiskAssessmentRequest as _RiskAssessmentRequest,
  RiskAssessmentsResponse as _RiskAssessmentsResponse,
  PhysicianRiskAssessmentsResponse,
  PaginatedResponse,
  MessageResponse,
  ResponseResult,
} from './types';

const logger = createLogger("ApiClient");

// Re-export core types
export type { ApiResponse, PaginatedResponse, RequestOptions } from "./core";
export { ApiError } from "./core";

// Re-export domain types
export type * from "./auth";
export type * from "./patients";
export type * from "./appointments";
export type * from "./treatments";
export type {
  Medication,
  MedicationCreate,
  MedicationUpdate,
  MedicationFilters,
  MedicationStats,
  MedicationRoute,
  MedicationSchedule,
  MedicationsApi
} from "./medications";
export type * from "./monthly-quiz";
export type * from "./analytics";
export type * from "./admin";
export type * from "./dashboard";
export type * from "./tasks";
export type * from "./hive-mind";

/**
 * Main API Client class
 * Extends core with domain-specific modules
 */
export class ApiClient extends ApiClientCore {
  // Domain modules
  public readonly auth: ReturnType<typeof createAuthApi>;
  public readonly patients: ReturnType<typeof createPatientsApi>;
  public readonly appointments: ReturnType<typeof createAppointmentsApi>;
  public readonly treatments: ReturnType<typeof createTreatmentsApi>;
  public readonly medications: ReturnType<typeof createMedicationsApi>;
  public readonly monthlyQuiz: ReturnType<typeof createMonthlyQuizApi>;
  public readonly analytics: ReturnType<typeof createAnalyticsApi>;
  public readonly adminV2: ReturnType<typeof createAdminApi>;
  public readonly dashboard: ReturnType<typeof createDashboardApi>;
  public readonly tasks: TasksApi;

  // Additional namespaces (lightweight inline implementations)
  public readonly messages: MessagesApi;
  public readonly flows: FlowsApi;
  public readonly alerts: AlertsApi;
  public readonly reports: ReportsApi;
  public readonly admin: AdminApi;
  public readonly adminUsers: AdminUsersApi;
  public readonly ai: AiApi;
  public readonly quiz: QuizApi;
  public readonly quizzes: QuizTemplatesApi;
  public readonly notifications: NotificationsApi;
  public readonly physician: PhysicianApi;
  public readonly hiveMind: ReturnType<typeof createHiveMindApi>;

  constructor(baseURL: string) {
    super(baseURL);

    // Initialize domain modules
    this.auth = createAuthApi(this);
    this.patients = createPatientsApi(this);
    this.appointments = createAppointmentsApi(this);
    this.treatments = createTreatmentsApi(this);
    this.medications = createMedicationsApi(this);
    this.monthlyQuiz = createMonthlyQuizApi(this);
    this.analytics = createAnalyticsApi(this);
    this.adminV2 = createAdminApi(this);
    this.dashboard = createDashboardApi(this);
    this.tasks = createTasksApi(this);

    // Initialize inline modules (simpler domains)
    this.messages = this.createMessagesApi();
    this.flows = this.createFlowsApi();
    this.alerts = this.createAlertsApi();
    this.reports = this.createReportsApi();
    this.admin = this.createAdminApi();
    this.adminUsers = this.createAdminUsersApi();
    this.ai = this.createAiApi();
    this.quiz = this.createQuizApi();
    this.quizzes = this.createQuizTemplatesApi();
    this.notifications = this.createNotificationsApi();
    this.physician = this.createPhysicianApi();
    this.hiveMind = createHiveMindApi(this);

    logger.log("API Client initialized with modular architecture");
  }

  /**
   * Messages API V2 (Migrated from V1)
   * All endpoints now use V2 with cursor pagination
   */
  private createMessagesApi(): MessagesApi {
    return {
      list: async (options: MessagesListOptions = {}) => {
        const { size, cursor, limit, ...filters } = options;
        const effLimit = limit ?? size ?? 20;
        const params: Record<string, string | number | boolean> = { limit: effLimit, ...(cursor ? { cursor } : {}), ...filters };
        const res = await this.get<PaginatedResponse<Message>>("/api/v2/messages", params);
        const items = Array.isArray(res?.data) ? res.data : (res?.items ?? []);
        return { data: items, items, total: res?.total ?? 0, has_more: res?.has_more, next_cursor: res?.next_cursor };
      },

      get: (messageId: string) => this.get(`/api/v2/messages/${messageId}`),

      send: (data: SendMessageRequest) => this.post("/api/v2/messages", data),

      markAsRead: (messageId: string) => this.patch(`/api/v2/messages/${messageId}/read`),

      delete: (messageId: string) => this.delete(`/api/v2/messages/${messageId}`),

      getConversation: (patientId: string) =>
        this.get(`/api/v2/messages/conversations/${patientId}`),

      sendBulk: (data: { patient_ids: string[]; content: string }) =>
        this.post("/api/v2/messages/bulk", data),

      // retry endpoint is available in V2
      retry: (messageId: string) => this.post(`/api/v2/messages/${messageId}/retry`),
    };
  }

  /**
   * Flows API V2 (migrated from V1)
   * Backend V2 provides 32 endpoints with enhanced features
   */
  private createFlowsApi(): FlowsApi {
    return {
      // Flow Instances (V2: /api/v2/flows)
      list: (options?: FlowListFilters) => this.get("/api/v2/flows", options as Record<string, string | number | boolean>),

      get: (flowId: string) => this.get(`/api/v2/templates/flows/${flowId}`),

      create: (data: CreateFlowTemplateRequest) => this.post<FlowTemplate>("/api/v2/templates/flows", data),

      update: (flowId: string, data: UpdateFlowTemplateRequest) => this.put<FlowTemplate>(`/api/v2/templates/flows/${flowId}`, data),

      delete: (flowId: string) => this.delete(`/api/v2/templates/flows/${flowId}`),

      // V2 doesn't have separate activate/deactivate for templates
      // Templates are activated when assigned to patients
      activate: (flowId: string) =>
        this.put(`/api/v2/templates/flows/${flowId}`, { is_active: true }),

      deactivate: (flowId: string) =>
        this.put(`/api/v2/templates/flows/${flowId}`, { is_active: false }),

      // Execute not directly available in V2 - use advance instead
      execute: (flowId: string, data?: FlowAdvanceRequest) =>
        this.post(`/api/v2/flows/${flowId}/advance`, data),

      // History endpoint replaces executions
      getExecutions: (flowId: string) => this.get(`/api/v2/flows/${flowId}/history`),

      processResponse: (patientId: string, responseText: string, metadata?: Record<string, unknown>) =>
        this.post<ResponseResult>(`/api/v2/flows/${patientId}/response`, {
          response_text: responseText,
          metadata
        }),


      // Flow State Operations (V2: /api/v2/flows/{patient_id}/state)
      getState: (patientId: string) => this.get(`/api/v2/flows/${patientId}/state`),

      start: (patientId: string, flowType: string) =>
        this.post(`/api/v2/flows/start`, {
          patient_id: patientId,
          flow_type: flowType
        }),

      // Flow state control (V2: enhanced with request bodies)
      advance: (patientId: string, day?: number) =>
        this.post(`/api/v2/flows/${patientId}/advance`, {
          target_day: day,
          skip_conditions: false
        }),

      pause: (patientId: string) =>
        this.post(`/api/v2/flows/${patientId}/pause`, {
          reason: "Manual pause"
        }),

      resume: (patientId: string) =>
        this.post(`/api/v2/flows/${patientId}/resume`),

      getAnalytics: () => this.get("/api/v2/flows/analytics"),

      // Templates management
      getTemplates: () => this.get("/api/v2/templates/flows"),
      createTemplate: (template: CreateFlowTemplateRequest) => this.post("/api/v2/templates/flows", template),
      updateTemplate: (templateId: string, data: UpdateFlowTemplateRequest) =>
        this.put(`/api/v2/templates/flows/${templateId}`, data),
      deleteTemplate: (templateId: string) => this.delete(`/api/v2/templates/flows/${templateId}`),
    };
  }

  /**
   * Alerts API V2 (Migrated from V1)
   * All endpoints now use V2 with cursor pagination
   */
  private createAlertsApi(): AlertsApi {
    return {
      list: async (options: AlertsListOptions = {}) => {
        const { size, cursor, limit, ...filters } = options;
        const effLimit = limit ?? size ?? 20;
        const params: Record<string, string | number | boolean> = { limit: effLimit, ...(cursor ? { cursor } : {}), ...filters };
        const res = await this.get<PaginatedResponse<Alert>>("/api/v2/alerts", params);
        const items = Array.isArray(res?.data) ? res.data : (res?.items ?? []);
        return { data: items, items, total: res?.total ?? 0, has_more: res?.has_more, next_cursor: res?.next_cursor };
      },

      get: (alertId: string) => this.get(`/api/v2/alerts/${alertId}`),

      create: (data: CreateAlertRequest) => this.post<Alert>("/api/v2/alerts", data),

      update: (alertId: string, data: UpdateAlertRequest) => this.patch<Alert>(`/api/v2/alerts/${alertId}`, data),

      delete: (alertId: string) => this.delete(`/api/v2/alerts/${alertId}`),

      markAsRead: (alertId: string) => this.patch(`/api/v2/alerts/${alertId}/read`, {}),

      markAllAsRead: () => this.post("/api/v2/alerts/read-all"),

      // Fixed: acknowledge uses the /read endpoint (PATCH)
      // Backend only has 'acknowledged' status, no separate 'resolve'
      getUnreadCount: () => this.get("/api/v2/alerts/unread-count"),
      acknowledge: (alertId: string) => this.patch(`/api/v2/alerts/${alertId}/read`, {}),
      resolve: (alertId: string) => this.patch(`/api/v2/alerts/${alertId}/read`, { notes: 'Resolved' }),
    };
  }

  /**
   * Reports API V2 (Migrated from V1)
   * All endpoints now use V2 with cursor pagination
   */
  private createReportsApi(): ReportsApi {
    return {
      list: async (options: ReportsListOptions = {}) => {
        const { size, cursor, limit, ...filters } = options;
        const effLimit = limit ?? size ?? 20;
        const params: Record<string, string | number | boolean> = { limit: effLimit, ...(cursor ? { cursor } : {}), ...filters };
        const res = await this.get<PaginatedResponse<Report>>("/api/v2/reports", params);
        const items = Array.isArray(res?.data) ? res.data : (res?.items ?? []);
        return { data: items, items, total: res?.total ?? 0, has_more: res?.has_more, next_cursor: res?.next_cursor };
      },

      generate: (patientId: string, reportType: string, config?: ReportGenerationConfig) => {
        const rawTitle = typeof config?.title === "string" ? config.title.trim() : "";
        const params: Record<string, string | number | boolean> = {
          title: rawTitle || `Relatorio ${reportType}`,
          report_type: reportType,
        };

        if (patientId) {
          params['patient_ids'] = patientId;
        }

        if (typeof config?.format === "string" && config.format.trim()) {
          params['format'] = config.format.trim();
        }

        if (typeof config?.start_date === "string" && config.start_date) {
          params['date_from'] = config.start_date;
        }

        if (typeof config?.end_date === "string" && config.end_date) {
          params['date_to'] = config.end_date;
        }

        if (typeof config?.include_messages === "boolean") {
          params['include_messages'] = config.include_messages;
        }

        if (typeof config?.include_quizzes === "boolean") {
          params['include_quizzes'] = config.include_quizzes;
        }

        if (typeof config?.include_alerts === "boolean") {
          params['include_alerts'] = config.include_alerts;
        }

        if (typeof config?.include_timeline === "boolean") {
          params['include_timeline'] = config.include_timeline;
        }

        return this.post("/api/v2/reports/generate", undefined, params);
      },

      download: async (reportId: string, format: "pdf" | "excel" | "csv" = "pdf") => {
        const response = await fetch(
          `${this.getBaseURL()}/api/v2/reports/${reportId}/download?format=${format}`,
          {
            method: "GET",
            headers: {
              ...this.getSessionHeaders(),
            },
            credentials: "include",
          },
        );

        if (!response.ok) {
          throw new Error("Failed to download report");
        }

        return response.blob();
      },

      // WARNING: delete endpoint NOT IMPLEMENTED in backend v2
      // Throws error to prevent silent API failure in production
      delete: (_reportId: string) => {
        throw new Error("Delete report not implemented in backend v2");
      },

      schedule: (data: ScheduleReportRequest) => this.post<ScheduledReport>("/api/v2/reports/schedule", data),

      // WARNING: getScheduled endpoint NOT IMPLEMENTED in backend v2
      // Throws error to prevent silent API failure in production
      getScheduled: () => {
        throw new Error("Get scheduled reports not implemented in backend v2");
      },
    };
  }

  /**
   * Admin API V2 (Migrated from V1)
   * User management with cursor pagination
   */
  private createAdminApi(): AdminApi {
    return {
      users: {
        list: async (_page = 1, size = 20) => {
          const params: Record<string, string | number | boolean> = { limit: size };
          const res = await this.get<PaginatedResponse<AdminUser>>("/api/v2/admin/users", params);
          return Array.isArray(res?.data) ? res.data : (res?.items ?? []);
        },

        get: (userId: string) => this.get<AdminUser>(`/api/v2/admin/users/${userId}`),

        create: (data: CreateAdminUserRequest) => this.post<AdminUser>("/api/v2/admin/users", data),

        update: (userId: string, data: UpdateAdminUserRequest) => this.put<AdminUser>(`/api/v2/admin/users/${userId}`, data),

        delete: (userId: string) => this.delete(`/api/v2/admin/users/${userId}`),

        resetPassword: (userId: string, payload?: ResetPasswordRequest) =>
          this.post(`/api/v2/admin/users/${userId}/reset-password`, payload ?? {}),

        // toggleStatus replaced with activate/deactivate in V2
        toggleStatus: (userId: string) => this.post(`/api/v2/admin/users/${userId}/deactivate`),
      },

      // roles/audit/settings are served by V2 admin endpoints
      roles: {
        list: () => this.get<Role[]>("/api/v2/admin/roles"),

        create: (data: CreateRoleRequest) => this.post<Role>("/api/v2/admin/roles", data),

        update: (roleId: string, data: Partial<CreateRoleRequest>) => this.put<Role>(`/api/v2/admin/roles/${roleId}`, data),

        delete: (roleId: string) => this.delete(`/api/v2/admin/roles/${roleId}`),
      },

      audit: {
        list: (page = 1, size = 20, filters?: AuditLogFilters) =>
          this.get<PaginatedResponse<AuditLogEntry>>("/api/v2/admin/audit", { page, size, ...filters }),

        get: (auditId: string) => this.get<AuditLogEntry>(`/api/v2/admin/audit/${auditId}`),

        export: async (filters?: AuditLogFilters) => {
          const queryParams = new URLSearchParams(filters as Record<string, string>);
          const response = await fetch(
            `${this.getBaseURL()}/api/v2/admin/audit/export?${queryParams}`,
            {
              method: "GET",
              headers: {
                ...this.getSessionHeaders(),
              },
              credentials: "include",
            },
          );

          if (!response.ok) {
            throw new Error("Failed to export audit logs");
          }

          return response.blob();
        },
      },

      settings: {
        get: () => this.get<SystemSettings>("/api/v2/admin/settings"),

        update: (data: Partial<SystemSettings>) => this.put<SystemSettings>("/api/v2/admin/settings", data),

        reset: () => this.post("/api/v2/admin/settings/reset"),
      },

      system: {
        getHealth: () => this.get<SystemHealth>("/api/v2/admin/system/health"),

        getMetrics: () => this.get<SystemMetrics>("/api/v2/admin/system/metrics"),

        // Use the correct endpoint name from backend
        systemStats: () => this.get<SystemStats>("/api/v2/admin/system-stats"),

        clearCache: () => this.post<MessageResponse>("/api/v2/admin/system/clear-cache"),

        runMaintenance: () => this.post<MessageResponse>("/api/v2/admin/system/maintenance"),
      },
    };
  }

  private createAdminUsersApi(): AdminUsersApi {
    return {
      list: (options: AdminUsersListOptions = {}) => {
        const { page = 1, size = 20, ...filters } = options;
        return this.get<PaginatedResponse<AdminUser>>("/api/v2/admin/users", { page, size, ...filters });
      },

      get: (userId: string) => this.get<AdminUser>(`/api/v2/admin/users/${userId}`),

      create: (data: CreateAdminUserRequest) => this.post<AdminUser>("/api/v2/admin/users", data),

      update: (userId: string, data: UpdateAdminUserRequest) => this.put<AdminUser>(`/api/v2/admin/users/${userId}`, data),

      delete: (userId: string) => this.delete<MessageResponse>(`/api/v2/admin/users/${userId}`),

      activate: (userId: string) => this.post(`/api/v2/admin/users/${userId}/activate`),

      deactivate: (userId: string) => this.post(`/api/v2/admin/users/${userId}/deactivate`),

      updatePermissions: (userId: string, permissions: string[]) =>
        this.put(`/api/v2/admin/users/${userId}/permissions`, { permissions }),

      updateRole: (userId: string, role: string) =>
        this.put(`/api/v2/admin/users/${userId}/role`, { role }),

      getActivity: (userId: string, options: AdminUserActivityOptions = {}) => {
        const { page = 1, size = 20, ...filters } = options;
        return this.get(`/api/v2/admin/users/${userId}/activity`, { page, size, ...filters });
      },

      resetPassword: (userId: string, payload: ResetPasswordRequest) =>
        this.post(`/api/v2/admin/users/${userId}/reset-password`, {
          new_password: payload.new_password,
          force_change: payload.force_change ?? false
        }),

      unlock: (userId: string) => this.post(`/api/v2/admin/users/${userId}/unlock`),

      enable2FA: (userId: string) => this.post(`/api/v2/admin/users/${userId}/2fa/enable`),

      disable2FA: (userId: string) => this.post(`/api/v2/admin/users/${userId}/2fa/disable`),
    };
  }

  private createAiApi(): AiApi {
    const timeframeToDays = (timeframe?: string) => {
      switch (timeframe) {
        case "day":
          return 1;
        case "week":
          return 7;
        case "month":
          return 30;
        case "quarter":
          return 90;
        default:
          return undefined;
      }
    };

    const buildHumanizeRequest = (
      message: string,
      context?: HumanizeContext,
      overrides?: Partial<HumanizeRequest>,
    ): HumanizeRequest => {
      const patientId =
        typeof context?.patient_id === "string"
          ? context.patient_id
          : typeof context?.patientId === "string"
            ? context.patientId
            : undefined;
      const messageType =
        typeof context?.message_type === "string"
          ? context.message_type
          : typeof context?.messageType === "string"
            ? context.messageType
            : undefined;
      const tone =
        typeof context?.tone === "string"
          ? context.tone
          : typeof context?.tone_type === "string"
            ? context.tone_type
            : undefined;
      const maxLength =
        typeof context?.max_length === "number"
          ? context.max_length
          : typeof context?.maxLength === "number"
            ? context.maxLength
            : undefined;
      const useCache =
        typeof context?.use_cache === "boolean"
          ? context.use_cache
          : typeof context?.useCache === "boolean"
            ? context.useCache
            : undefined;

      return {
        message,
        ...(patientId && patientId !== "all" ? { patient_id: patientId } : {}),
        message_type: messageType as HumanizeRequest["message_type"] | undefined,
        tone: tone as HumanizeRequest["tone"] | undefined,
        max_length: maxLength,
        use_cache: useCache ?? true,
        ...overrides,
      };
    };

    return {
      health: () => this.get<AIHealthResponse>("/api/v2/ai/health"),

      chat: async (message: string, context?: HumanizeContext) => {
        const response = await this.post<HumanizeResponse>(
          "/api/v2/ai/humanize",
          buildHumanizeRequest(message, context),
        );
        const confidence = Math.max(
          0,
          Math.min(1, (response.readability_score ?? 0) / 100),
        );
        return {
          response: response.humanized_message,
          message: response.humanized_message,
          confidence,
          metadata: {
            personalization_notes: response.personalization_notes,
            tone_analysis: response.tone_analysis,
            cache_info: response.cache_info,
            token_usage: response.token_usage,
          },
        } as AIChatResponse;
      },

      analyze: async (data: unknown, analysisType: 'sentiment' | 'risk' | 'response') => {
        if (analysisType === "sentiment") {
          const payload = data as SentimentAnalysisPayload;
          const message =
            (typeof payload?.message === "string" && payload.message) ||
            (typeof payload?.text === "string" && payload.text) ||
            "";
          const response = await this.post<Record<string, unknown>>(
            "/api/v2/ai/analyze/sentiment",
            {
              message,
              patient_id: payload?.patient_id,
              include_medical_concerns: payload?.include_medical_concerns ?? true,
              include_urgency: payload?.include_urgency ?? true,
            },
          );
          return { type: "sentiment", result: response } as AIAnalysisResponse;
        }
        if (analysisType === "risk") {
          const response = await this.post<Record<string, unknown>>(
            "/api/v2/ai/analyze/risk",
            data,
          );
          return { type: "risk", result: response } as AIAnalysisResponse;
        }
        if (analysisType === "response") {
          const response = await this.post<Record<string, unknown>>(
            "/api/v2/ai/analyze/response",
            data,
          );
          return { type: "response", result: response } as AIAnalysisResponse;
        }
        throw new Error(`Unsupported analysis type: ${analysisType}`);
      },

      generateResponse: async (
        patientId: string,
        messageHistory: Array<{ role: string; content: string }>,
        intent?: string,
      ) => {
        const lastMessage = [...messageHistory]
          .reverse()
          .find((entry) => entry.content?.trim())?.content;
        const template =
          lastMessage ||
          (intent
            ? `Gerar uma resposta empatica para o contexto: ${intent}`
            : "Responder de forma empatica e profissional.");
        const response = await this.post<HumanizeResponse>(
          "/api/v2/ai/humanize",
          buildHumanizeRequest(template, { patient_id: patientId }, { use_cache: false }),
        );
        return {
          generated_response: response.humanized_message,
          confidence: Math.max(
            0,
            Math.min(1, (response.readability_score ?? 0) / 100),
          ),
          alternative_responses: [],
        } as AIGenerateResponseResponse;
      },

      sentiment: async (text: string) => {
        const response = await this.post<{
          sentiment?: string;
          confidence?: number;
        }>("/api/v2/ai/analyze/sentiment", { message: text });
        const sentiment = response.sentiment === "positive" || response.sentiment === "negative"
          ? response.sentiment
          : "neutral";
        const score =
          sentiment === "positive" ? 0.8 : sentiment === "negative" ? 0.2 : 0.5;
        return {
          sentiment,
          score,
          confidence: response.confidence ?? 0,
        } as SentimentAnalysisResponse;
      },

      insights: (patientId: string, timeframe?: string) => {
        if (!patientId || patientId === "all") {
          return Promise.reject(
            new Error("patientId is required for AI insights"),
          );
        }
        const days = timeframeToDays(timeframe);
        return this.get<AIInsights>(
          `/api/v2/ai/insights/${patientId}`,
          days ? { days } : undefined,
        );
      },

      recommendations: (patientId: string) =>
        this.get<AIRecommendations>(`/api/v2/ai/recommendations/${patientId}`),

      // Patient Summary API
      generateSummary: (request: import('@/types/api').GenerateSummaryRequest) =>
        this.post<import('@/types/api').PatientSummaryResponse>('/api/v2/ai/summary', request),

      getSummaries: (patientId: string, limit = 10, offset = 0) =>
        this.get<import('@/types/api').PatientSummaryListResponse>(
          `/api/v2/ai/summary/patient/${patientId}`,
          { limit, offset }
        ),

      getSummary: (summaryId: string) =>
        this.get<import('@/types/api').PatientSummaryResponse>(`/api/v2/ai/summary/${summaryId}`),

      exportSummaryPdf: async (summaryId: string): Promise<Blob> => {
        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
        };
        Object.assign(headers, this.getSessionHeaders());
        const response = await fetch(`${this.getBaseURL()}/api/v2/ai/summary/${summaryId}/pdf`, {
          method: 'GET',
          headers,
          credentials: 'include',
        });
        if (!response.ok) {
          throw new Error(`Failed to export PDF: ${response.statusText}`);
        }
        return response.blob();
      },
    };
  }

  /**
   * Quiz API using V2 endpoints
   * Session/template operations and response/analysis methods map to /api/v2 routes.
   */
  private createQuizApi(): QuizApi {
    return {
      // Templates migrated to V2
      templates: async (params?: Record<string, string | number | boolean>): Promise<QuizTemplateResponse> => {
        const res = await this.get<unknown>("/api/v2/templates/quizzes", params)
        return Array.isArray(res) ? { items: res as QuizTemplate[] } : res as QuizTemplateResponse
      },

      // Create a new quiz session (V2)
      start: (patientId: string, quizTemplateId: string) =>
        this.post("/api/v2/quiz", {
          patient_id: patientId,
          quiz_template_id: quizTemplateId,
        }),
      // List sessions (V2) with cursor pagination; keep backward-compatible shape
      sessions: async (options?: QuizSessionListFilters) => {
        const { size, limit, cursor, patient_id, ...rest } = options || {};
        const effLimit = limit ?? size ?? 20;
        const params: Record<string, string | number | boolean> = { limit: effLimit, ...(cursor ? { cursor } : {}), ...rest };

        const endpoint = patient_id
          ? `/api/v2/quiz/patients/${patient_id}/quiz-responses`
          : `/api/v2/quiz/sessions`;

        const res = await this.get<PaginatedResponse<QuizSession>>(endpoint, params);
        const items = Array.isArray(res?.data) ? res.data : (res?.items ?? []);
        return { data: items, items, total: res?.total ?? 0, has_more: res?.has_more, next_cursor: res?.next_cursor };
      },

      // Session responses - migrated to V2
      getSessionResponses: (sessionId: string) =>
        this.get(`/api/v2/quiz/${sessionId}/responses`),

      // Session analysis - migrated to V2
      getSessionAnalysis: (sessionId: string) =>
        this.get(`/api/v2/quiz/${sessionId}/analysis`),

      // Missing methods implementation
      getSession: (sessionId: string) =>
        this.get(`/api/v2/quiz/sessions/${sessionId}`),

      submitResponse: (sessionId: string, questionId: string, answer: string | string[], responseMetadata?: Record<string, unknown>) =>
        this.post(`/api/v2/quiz/sessions/${sessionId}/responses`, {
          question_id: questionId,
          answer,
          metadata: responseMetadata
        }),

      getPatientResponses: async (patientId: string, options?: Record<string, unknown>): Promise<PatientQuizResponses> => {
        const res = await this.get<PaginatedResponse<QuizSession>>(`/api/v2/quiz-extensions/responses`, { patient_id: patientId, ...options as Record<string, string | number | boolean> });
        const items = Array.isArray(res?.data) ? res.data : (res?.items ?? []);
        return {
          patient_id: patientId,
          sessions: items,
          total: res?.total ?? 0
        };
      }
    };
  }

  /**
   * Quiz Templates API (Migrated to V2)
   */
  private createQuizTemplatesApi(): QuizTemplatesApi {
    return {
      list: (options) => this.quiz.templates(options),
      listTemplates: (options) => this.quiz.templates(options),

      // Template CRUD - Fixed: uses /quizzes (plural) to match backend
      createTemplate: (template: CreateQuizTemplateRequest) => this.post<QuizTemplate>("/api/v2/templates/quizzes", template as unknown as CreateFlowTemplateRequest),
      create: (template: CreateQuizTemplateRequest) => this.post<QuizTemplate>("/api/v2/templates/quizzes", template),

      updateTemplate: (templateId: string, data: UpdateFlowTemplateRequest) =>
        this.put(`/api/v2/templates/quizzes/${templateId}`, data),

      deleteTemplate: (templateId: string) =>
        this.delete(`/api/v2/templates/quizzes/${templateId}`),

      // Analytics endpoint
      getTemplateAnalytics: (templateId: string) =>
        this.get(`/api/v2/templates/quizzes/${templateId}/analytics`),
    };
  }

  private createNotificationsApi(): NotificationsApi {
    return {
      list: () => this.get("/api/v2/notifications"),
    };
  }

  private createPhysicianApi(): PhysicianApi {
    return {
      riskAssessments: (patientId?: string, daysLookback?: number) => {
        const params: Record<string, string | number> = {};
        if (patientId) {
          params["patient_id"] = patientId;
        }
        if (daysLookback) {
          params["days_lookback"] = daysLookback;
        }
        return this.get<PhysicianRiskAssessmentsResponse>("/api/v2/physician/risk-assessments", params);
      },
    };
  }

  /**
   * Clear all cached data
   */
  clearCache(): void {
    // Override if needed in the future for client-side caching
    logger.log("Cache cleared");
  }
}

// Type definitions for inline APIs
interface MessagesListOptions extends MessageListFilters {
  page?: number;
  size?: number;
  cursor?: string;
  limit?: number;
}

interface MessagesApi {
  list: (options?: MessagesListOptions) => Promise<PaginatedResponse<Message>>;
  get: (messageId: string) => Promise<Message>;
  send: (data: SendMessageRequest) => Promise<Message>;
  markAsRead: (messageId: string) => Promise<MessageResponse>;
  delete: (messageId: string) => Promise<MessageResponse>;
  getConversation: (patientId: string) => Promise<ConversationResponse>;
  sendBulk: (data: BulkMessageRequest) => Promise<BulkMessageResponse>;
  retry: (messageId: string) => Promise<Message>;
}

interface FlowsApi {
  list: (options?: FlowListFilters) => Promise<PaginatedResponse<FlowState>>;
  get: (flowId: string) => Promise<FlowTemplate>;
  create: (data: CreateFlowTemplateRequest) => Promise<FlowTemplate>;
  update: (flowId: string, data: UpdateFlowTemplateRequest) => Promise<FlowTemplate>;
  delete: (flowId: string) => Promise<MessageResponse>;
  activate: (flowId: string) => Promise<FlowTemplate>;
  deactivate: (flowId: string) => Promise<FlowTemplate>;
  execute: (flowId: string, data?: FlowAdvanceRequest) => Promise<FlowState>;
  getExecutions: (flowId: string) => Promise<Array<Record<string, unknown>>>;
  getState: (patientId: string) => Promise<FlowState>;
  start: (patientId: string, flowType: string) => Promise<FlowState>;
  advance: (patientId: string, day?: number) => Promise<FlowState>;
  pause: (patientId: string) => Promise<FlowState>;
  resume: (patientId: string) => Promise<FlowState>;
  processResponse: (patientId: string, responseText: string, metadata?: Record<string, unknown>) => Promise<ResponseResult>;
  getAnalytics: () => Promise<FlowAnalytics>;
  getTemplates: () => Promise<FlowTemplate[]>;
  createTemplate: (template: CreateFlowTemplateRequest) => Promise<FlowTemplate>;
  updateTemplate: (templateId: string, data: UpdateFlowTemplateRequest) => Promise<FlowTemplate>;
  deleteTemplate: (templateId: string) => Promise<MessageResponse>;
}

interface AlertsListOptions extends AlertListFilters {
  page?: number;
  size?: number;
  cursor?: string;
  limit?: number;
}

interface AlertsApi {
  list: (options?: AlertsListOptions) => Promise<PaginatedResponse<Alert>>;
  get: (alertId: string) => Promise<Alert>;
  create: (data: CreateAlertRequest) => Promise<Alert>;
  update: (alertId: string, data: UpdateAlertRequest) => Promise<Alert>;
  delete: (alertId: string) => Promise<MessageResponse>;
  markAsRead: (alertId: string) => Promise<MessageResponse>;
  markAllAsRead: () => Promise<MessageResponse>;
  getUnreadCount: () => Promise<UnreadCountResponse>;
  acknowledge: (alertId: string) => Promise<MessageResponse>;
  resolve: (alertId: string) => Promise<MessageResponse>;
}

interface ReportsListOptions extends ReportListFilters {
  page?: number;
  size?: number;
  cursor?: string;
  limit?: number;
}

type ReportGenerationConfig = {
  title?: string;
  format?: string;
  start_date?: string;
  end_date?: string;
  include_messages?: boolean;
  include_quizzes?: boolean;
  include_alerts?: boolean;
  include_timeline?: boolean;
};

interface ReportsApi {
  list: (options?: ReportsListOptions) => Promise<PaginatedResponse<Report>>;
  generate: (patientId: string, reportType: string, config?: ReportGenerationConfig) => Promise<Report>;
  download: (reportId: string, format?: "pdf" | "excel" | "csv") => Promise<Blob>;
  delete: (reportId: string) => Promise<MessageResponse>;
  schedule: (data: ScheduleReportRequest) => Promise<ScheduledReport>;
  getScheduled: () => Promise<ScheduledReport[]>;
}

interface AdminApi {
  users: {
    list: (page?: number, size?: number) => Promise<AdminUser[]>;
    get: (userId: string) => Promise<AdminUser>;
    create: (data: CreateUserRequest) => Promise<AdminUser>;
    update: (userId: string, data: UpdateUserRequest) => Promise<AdminUser>;
    delete: (userId: string) => Promise<MessageResponse>;
    resetPassword: (userId: string, payload?: ResetPasswordRequest) => Promise<MessageResponse>;
    toggleStatus: (userId: string) => Promise<MessageResponse>;
  };
  roles: {
    list: () => Promise<Role[]>;
    create: (data: CreateRoleRequest) => Promise<Role>;
    update: (roleId: string, data: Partial<CreateRoleRequest>) => Promise<Role>;
    delete: (roleId: string) => Promise<MessageResponse>;
  };
  audit: {
    list: (page?: number, size?: number, filters?: AuditLogFilters) => Promise<PaginatedResponse<AuditLogEntry>>;
    get: (auditId: string) => Promise<AuditLogEntry>;
    export: (filters?: AuditLogFilters) => Promise<Blob>;
  };
  settings: {
    get: () => Promise<SystemSettings>;
    update: (data: Partial<SystemSettings>) => Promise<SystemSettings>;
    reset: () => Promise<MessageResponse>;
  };
  system: {
    getHealth: () => Promise<SystemHealth>;
    getMetrics: () => Promise<SystemMetrics>;
    systemStats: () => Promise<SystemStats>;
    clearCache: () => Promise<MessageResponse>;
    runMaintenance: () => Promise<MessageResponse>;
  };
}

interface AdminUsersListOptions extends AdminUserListFilters {
  page?: number;
  size?: number;
}

interface AdminUserActivityOptions extends UserActivityFilters {
  page?: number;
  size?: number;
}

interface AdminUsersApi {
  list: (options?: AdminUsersListOptions) => Promise<PaginatedResponse<AdminUser>>;
  get: (userId: string) => Promise<AdminUser>;
  create: (data: CreateUserRequest) => Promise<AdminUser>;
  update: (userId: string, data: UpdateUserRequest) => Promise<AdminUser>;
  delete: (userId: string) => Promise<MessageResponse>;
  activate: (userId: string) => Promise<MessageResponse>;
  deactivate: (userId: string) => Promise<MessageResponse>;
  updatePermissions: (userId: string, permissions: string[]) => Promise<MessageResponse>;
  updateRole: (userId: string, role: string) => Promise<MessageResponse>;
  getActivity: (userId: string, options?: AdminUserActivityOptions) => Promise<PaginatedResponse<UserActivityEntry>>;
  resetPassword: (userId: string, payload: ResetPasswordRequest) => Promise<MessageResponse>;
  unlock: (userId: string) => Promise<MessageResponse>;
  enable2FA: (userId: string) => Promise<MessageResponse>;
  disable2FA: (userId: string) => Promise<MessageResponse>;
}

type HumanizeContext = {
  patient_id?: string;
  patientId?: string;
  message_type?: string;
  messageType?: string;
  tone?: string;
  tone_type?: string;
  max_length?: number;
  maxLength?: number;
  use_cache?: boolean;
  useCache?: boolean;
};

type SentimentAnalysisPayload = {
  message?: string;
  text?: string;
  patient_id?: string;
  include_medical_concerns?: boolean;
  include_urgency?: boolean;
};

interface AiApi {
  health: () => Promise<AIHealthResponse>;
  chat: (message: string, context?: HumanizeContext) => Promise<AIChatResponse>;
  analyze: (data: unknown, analysisType: 'sentiment' | 'risk' | 'response') => Promise<AIAnalysisResponse>;
  generateResponse: (patientId: string, messageHistory: Array<{ role: string; content: string }>, intent?: string) => Promise<AIGenerateResponseResponse>;
  sentiment: (text: string) => Promise<SentimentAnalysisResponse>;
  insights: (patientId: string, timeframe?: string) => Promise<AIInsights>;
  recommendations: (patientId: string) => Promise<AIRecommendations>;
  // Patient Summary API
  generateSummary: (request: import('@/types/api').GenerateSummaryRequest) => Promise<import('@/types/api').PatientSummaryResponse>;
  getSummaries: (patientId: string, limit?: number, offset?: number) => Promise<import('@/types/api').PatientSummaryListResponse>;
  getSummary: (summaryId: string) => Promise<import('@/types/api').PatientSummaryResponse>;
  exportSummaryPdf: (summaryId: string) => Promise<Blob>;
}

interface QuizApi {
  templates: (params?: Record<string, string | number | boolean>) => Promise<QuizTemplateResponse>;
  start: (patientId: string, quizTemplateId: string) => Promise<QuizSession>;
  getSession: (sessionId: string) => Promise<QuizSession>;
  submitResponse: (
    sessionId: string,
    questionId: string,
    answer: string | string[],
    responseMetadata?: Record<string, unknown>,
  ) => Promise<MessageResponse>;
  sessions: (filters?: QuizSessionListFilters) => Promise<PaginatedResponse<QuizSession>>;
  getPatientResponses: (patientId: string, options?: Record<string, unknown>) => Promise<PatientQuizResponses>;
  getSessionResponses: (sessionId: string) => Promise<QuizSessionResponses>;
  getSessionAnalysis: (sessionId: string) => Promise<QuizSessionAnalysis>;
}

interface QuizTemplatesApi {
  list: (params?: Record<string, string | number | boolean>) => Promise<QuizTemplateResponse>;
  listTemplates: (params?: Record<string, string | number | boolean>) => Promise<QuizTemplateResponse>;
  createTemplate: (template: CreateQuizTemplateRequest) => Promise<QuizTemplate>;
  create: (template: CreateQuizTemplateRequest) => Promise<QuizTemplate>;
  updateTemplate: (templateId: string, data: UpdateQuizTemplateRequest) => Promise<QuizTemplate>;
  deleteTemplate: (templateId: string) => Promise<MessageResponse>;
  getTemplateAnalytics: (templateId: string) => Promise<QuizTemplateAnalytics>;
}

interface CreateQuizTemplateRequest {
  name: string;
  description?: string;
  questions: Array<{
    question_text: string;
    question_type: string;
    options?: string[];
    required?: boolean;
  }>;
}

interface UpdateQuizTemplateRequest extends Partial<CreateQuizTemplateRequest> {
  is_active?: boolean;
}

// QuizTemplate type imported from types.ts

interface QuizTemplateAnalytics {
  template_id: string;
  total_sessions: number;
  completed_sessions: number;
  completion_rate: number;
  average_score?: number;
}

interface NotificationsApi {
  list: () => Promise<NotificationListResponse>;
}

interface PhysicianApi {
  riskAssessments: (patientId?: string, daysLookback?: number) => Promise<PhysicianRiskAssessmentsResponse>;
}

/**
 * Get API URL with proper environment variable resolution
 *
 * Priority order:
 * 1. Runtime config API_BASE_URL (loaded async from config.ts)
 * 2. VITE_API_BASE_URL environment variable (base domain)
 * 3. VITE_API_URL environment variable (full API URL)
 * 4. Auto-detect from window location in production
 * 5. Localhost fallback for development
 */
const getApiUrl = (): string => {
  // 1. Check runtime config (may be empty on initial load)
  if (API_BASE_URL && API_BASE_URL.length > 0) {
    logger.debug('Using API_BASE_URL from runtime config:', API_BASE_URL);
    return API_BASE_URL;
  }

  // 2. Check VITE_API_BASE_URL (preferred for base domain)
  if (import.meta.env["VITE_API_BASE_URL"]) {
    const baseUrl = import.meta.env["VITE_API_BASE_URL"];
    logger.debug('Using VITE_API_BASE_URL:', baseUrl);
    return baseUrl;
  }

  // 3. Check VITE_API_URL (full URL with /api/v2)
  if (import.meta.env["VITE_API_URL"]) {
    const apiUrl = import.meta.env["VITE_API_URL"];
    // Extract base URL by removing /api/v2 suffix
    const baseUrl = apiUrl.replace(/\/api\/v2$/, '');
    logger.debug('Using VITE_API_URL (extracted base):', baseUrl);
    return baseUrl;
  }

  // 4. Auto-detect in production based on window location
  if (typeof window !== 'undefined') {
    const { protocol, hostname } = window.location;

    // Production environments (Railway, custom domains)
    if (hostname !== 'localhost' && hostname !== '127.0.0.1') {
      const detectedUrl = `${protocol}//${hostname}`;
      logger.debug('Auto-detected API URL from window location:', detectedUrl);
      return detectedUrl;
    }
  }

  // 5. Development fallback
  logger.debug('Using localhost fallback for development');
  return import.meta.env.VITE_API_BASE_URL || (import.meta.env.VITE_API_URL || "http://localhost:8000");
};

// Create singleton instance
export const apiClient = new ApiClient(getApiUrl());

// Default export
export default apiClient;
