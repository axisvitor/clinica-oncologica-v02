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
  FlowPauseRequest,
  FlowProcessResponseRequest,
  FlowAnalytics,
  Alert,
  AlertListFilters,
  CreateAlertRequest,
  UpdateAlertRequest,
  UnreadCountResponse,
  Report,
  ReportListFilters,
  GenerateReportRequest,
  ScheduleReportRequest,
  ScheduledReport,
  AdminUser,
  AdminUserListFilters,
  CreateUserRequest,
  UpdateUserRequest,
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
  AIChatRequest,
  AIChatResponse,
  AIAnalysisRequest,
  AIAnalysisResponse,
  AIGenerateResponseRequest,
  AIGenerateResponseResponse,
  SentimentAnalysisRequest,
  SentimentAnalysisResponse,
  AIInsights,
  AIRecommendations,
  QuizTemplateResponse,
  QuizSessionStartRequest,
  QuizSession,
  QuizSubmitRequest,
  QuizSessionListFilters,
  QuizSessionResponses,
  QuizSessionAnalysis,
  PatientQuizResponses,
  NotificationListResponse,
  RiskAssessmentRequest,
  RiskAssessmentsResponse,
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
        const { page, size, cursor, limit, ...filters } = options;
        const effLimit = limit ?? size ?? 20;
        const params: Record<string, string | number | boolean> = { limit: effLimit, ...(cursor ? { cursor } : {}), ...filters };
        const res = await this.get<any>("/api/v2/messages", params);
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

      // retry endpoint stays on V1 (no V2 equivalent)
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

      get: (flowId: string) => this.get(`/api/v2/flows/templates/${flowId}`),

      create: (data: CreateFlowTemplateRequest) => this.post<FlowTemplate>("/api/v2/flows/templates", data),

      update: (flowId: string, data: UpdateFlowTemplateRequest) => this.put<FlowTemplate>(`/api/v2/flows/templates/${flowId}`, data),

      delete: (flowId: string) => this.delete(`/api/v2/flows/templates/${flowId}`),

      // V2 doesn't have separate activate/deactivate for templates
      // Templates are activated when assigned to patients
      activate: (flowId: string) =>
        this.put(`/api/v2/flows/templates/${flowId}`, { is_active: true }),

      deactivate: (flowId: string) =>
        this.put(`/api/v2/flows/templates/${flowId}`, { is_active: false }),

      // Execute not directly available in V2 - use advance instead
      execute: (flowId: string, data?: any) =>
        this.post(`/api/v2/flows/${flowId}/advance`, data),

      // History endpoint replaces executions
      getExecutions: (flowId: string) => this.get(`/api/v2/flows/${flowId}/history`),

      processResponse: (flowId: string, response: any) =>
        this.post<ResponseResult>(`/api/v2/flows/${flowId}/response`, response),


      // Flow State Operations (V2: /api/v2/flows/{patient_id}/state)
      getState: (patientId: string) => this.get(`/api/v2/flows/${patientId}/state`),

      // start() removed in V2 - flows are assigned through patient customization
      start: (patientId: string, flowType: string) =>
        this.post(`/api/v2/flows/${patientId}/customize`, {
          template_id: flowType,
          schedule_options: { start_immediately: true }
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
      getTemplates: () => this.get("/api/v2/flows/templates"),
      createTemplate: (template: CreateFlowTemplateRequest) => this.post("/api/v2/flows/templates", template),
      updateTemplate: (templateId: string, data: UpdateFlowTemplateRequest) =>
        this.put(`/api/v2/flows/templates/${templateId}`, data),
      deleteTemplate: (templateId: string) => this.delete(`/api/v2/flows/templates/${templateId}`),
    };
  }

  /**
   * Alerts API V2 (Migrated from V1)
   * All endpoints now use V2 with cursor pagination
   */
  private createAlertsApi(): AlertsApi {
    return {
      list: async (options: AlertsListOptions = {}) => {
        const { page, size, cursor, limit, ...filters } = options;
        const effLimit = limit ?? size ?? 20;
        const params: Record<string, string | number | boolean> = { limit: effLimit, ...(cursor ? { cursor } : {}), ...filters };
        const res = await this.get<any>("/api/v2/alerts", params);
        const items = Array.isArray(res?.data) ? res.data : (res?.items ?? []);
        return { data: items, items, total: res?.total ?? 0, has_more: res?.has_more, next_cursor: res?.next_cursor };
      },

      get: (alertId: string) => this.get(`/api/v2/alerts/${alertId}`),

      create: (data: CreateAlertRequest) => this.post<Alert>("/api/v2/alerts", data),

      update: (alertId: string, data: UpdateAlertRequest) => this.patch<Alert>(`/api/v2/alerts/${alertId}`, data),

      delete: (alertId: string) => this.delete(`/api/v2/alerts/${alertId}`),

      markAsRead: (alertId: string) => this.patch(`/api/v2/alerts/${alertId}/read`),

      markAllAsRead: () => this.post("/api/v2/alerts/read-all"),

      // unread count, acknowledge, resolve not in V2 (use list with filters)
      getUnreadCount: () => this.get("/api/v2/alerts/unread-count"),
      acknowledge: (alertId: string) => this.post(`/api/v2/alerts/${alertId}/acknowledge`),
      resolve: (alertId: string) => this.post(`/api/v2/alerts/${alertId}/resolve`),
    };
  }

  /**
   * Reports API V2 (Migrated from V1)
   * All endpoints now use V2 with cursor pagination
   */
  private createReportsApi(): ReportsApi {
    return {
      list: async (options: ReportsListOptions = {}) => {
        const { page, size, cursor, limit, ...filters } = options;
        const effLimit = limit ?? size ?? 20;
        const params: Record<string, string | number | boolean> = { limit: effLimit, ...(cursor ? { cursor } : {}), ...filters };
        const res = await this.get<any>("/api/v2/reports", params);
        const items = Array.isArray(res?.data) ? res.data : (res?.items ?? []);
        return { data: items, items, total: res?.total ?? 0, has_more: res?.has_more, next_cursor: res?.next_cursor };
      },

      generate: (patientId: string, reportType: string, config?: Record<string, unknown>) =>
        this.post("/api/v2/reports/generate", {
          patient_id: patientId,
          report_type: reportType,
          ...config,
        }),

      download: async (reportId: string, format: "pdf" | "excel" | "csv" = "pdf") => {
        const response = await fetch(
          `${this.getBaseURL()}/api/v2/reports/${reportId}/download?format=${format}`,
          {
            method: "GET",
            headers: {
              Authorization: `Bearer ${this.getAuthToken()}`,
            },
            credentials: "include",
          },
        );

        if (!response.ok) {
          throw new Error("Failed to download report");
        }

        return response.blob();
      },

      delete: (reportId: string) => this.delete(`/api/v2/reports/${reportId}`),

      schedule: (data: {
        report_type: string;
        frequency: "daily" | "weekly" | "monthly";
        recipients: string[];
        parameters?: any;
      }) => this.post("/api/v2/reports/schedule", data),

      // getScheduled not in V2 (use list with filter)
      getScheduled: () => this.get("/api/v2/reports/scheduled"),
    };
  }

  /**
   * Admin API V2 (Migrated from V1)
   * User management with cursor pagination
   */
  private createAdminApi(): AdminApi {
    return {
      users: {
        list: async (page = 1, size = 20) => {
          const params: Record<string, string | number | boolean> = { limit: size };
          const res = await this.get<any>("/api/v2/admin/users", params);
          return Array.isArray(res?.data) ? res.data : (res?.items ?? []);
        },

        get: (userId: string) => this.get(`/api/v2/admin/users/${userId}`),

        create: (data: any) => this.post("/api/v2/admin/users", data),

        update: (userId: string, data: any) => this.put(`/api/v2/admin/users/${userId}`, data),

        delete: (userId: string) => this.delete(`/api/v2/admin/users/${userId}`),

        resetPassword: (userId: string, payload?: any) =>
          this.post(`/api/v2/admin/users/${userId}/reset-password`, payload ?? {}),

        // toggleStatus replaced with activate/deactivate in V2
        toggleStatus: (userId: string) => this.post(`/api/v2/admin/users/${userId}/deactivate`),
      },

      // roles/audit/settings remain on V1 (not in V2 user management)
      roles: {
        list: () => this.get("/api/v2/admin/roles"),

        create: (data: any) => this.post("/api/v2/admin/roles", data),

        update: (roleId: string, data: any) => this.put(`/api/v2/admin/roles/${roleId}`, data),

        delete: (roleId: string) => this.delete(`/api/v2/admin/roles/${roleId}`),
      },

      audit: {
        list: (page = 1, size = 20, filters?: any) =>
          this.get("/api/v2/admin/audit", { page, size, ...filters }),

        get: (auditId: string) => this.get(`/api/v2/admin/audit/${auditId}`),

        export: async (filters?: any) => {
          const queryParams = new URLSearchParams(filters as any);
          const response = await fetch(
            `${this.getBaseURL()}/api/v2/admin/audit/export?${queryParams}`,
            {
              method: "GET",
              headers: {
                Authorization: `Bearer ${this.getAuthToken()}`,
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
        get: () => this.get("/api/v2/admin/settings"),

        update: (data: any) => this.put("/api/v2/admin/settings", data),

        reset: () => this.post("/api/v2/admin/settings/reset"),
      },

      system: {
        getHealth: () => this.get("/api/v2/admin/system/health"),

        getMetrics: () => this.get("/api/v2/admin/system/metrics"),

        // Use the correct endpoint name from backend
        systemStats: () => this.get("/api/v2/admin/system-stats"),

        clearCache: () => this.post("/api/v2/admin/system/clear-cache"),

        runMaintenance: () => this.post("/api/v2/admin/system/maintenance"),
      },
    };
  }

  private createAdminUsersApi(): AdminUsersApi {
    return {
      list: (options: AdminUsersListOptions = {}) => {
        const { page = 1, size = 20, ...filters } = options;
        return this.get("/api/v2/admin/users", { page, size, ...filters });
      },

      get: (userId: string) => this.get(`/api/v2/admin/users/${userId}`),

      create: (data: any) => this.post("/api/v2/admin/users", data),

      update: (userId: string, data: any) => this.put(`/api/v2/admin/users/${userId}`, data),

      delete: (userId: string) => this.delete(`/api/v2/admin/users/${userId}`),

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
    return {
      chat: (message: string, context?: any) =>
        this.post("/api/v2/ai/chat", { message, context }),

      analyze: (data: any, analysisType: string) =>
        this.post("/api/v2/ai/analyze", { data, analysis_type: analysisType }),

      generateResponse: (patientId: string, messageHistory: unknown[], intent?: string) =>
        this.post("/api/v2/ai/generate-response", {
          patient_id: patientId,
          message_history: messageHistory,
          intent,
        }),

      sentiment: (text: string) => this.post("/api/v2/ai/sentiment", { text }),

      insights: (patientId: string, timeframe?: string) =>
        this.get(`/api/v2/ai/insights/${patientId}`, timeframe ? { timeframe } : undefined),

      recommendations: (patientId: string) =>
        this.get(`/api/v2/ai/recommendations/${patientId}`),
    };
  }

  /**
   * Quiz API (Partially migrated to V2)
   * V2: quiz sessions, templates
   * V1: submitResponse, sessionResponses, analysis (no V2 equivalents)
   */
  private createQuizApi(): QuizApi {
    return {
      // Templates migrated to V2
      templates: async () => {
        const res: any = await this.get("/api/v2/templates/quiz")
        return Array.isArray(res) ? { items: res } : res
      },

      // Create a new quiz session (V2)
      start: (patientId: string, quizTemplateId: string) =>
        this.post("/api/v2/quiz", {
          patient_id: patientId,
          quiz_template_id: quizTemplateId,
        }),
      // List sessions (V2) with cursor pagination; keep backward-compatible shape
      sessions: async (options?: QuizSessionListFilters) => {
        const { page, size, limit, cursor, patient_id, ...rest } = options || {};
        const effLimit = limit ?? size ?? 20;
        const params: Record<string, string | number | boolean> = { limit: effLimit, ...(cursor ? { cursor } : {}), ...rest };

        const endpoint = patient_id
          ? `/api/v2/quiz/patients/${patient_id}/quiz-responses`
          : `/api/v2/quiz/sessions`;

        const res: any = await this.get(endpoint, params);
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
        const res: any = await this.get(`/api/v2/quiz/patients/${patientId}/responses`, options as any);
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
      list: () => this.quiz.templates(),
      listTemplates: () => this.quiz.templates(),

      // Template CRUD migrated to V2
      createTemplate: (template: CreateQuizTemplateRequest) => this.post("/api/v2/templates/quiz", template as unknown as CreateFlowTemplateRequest),
      create: (template: any) => this.post("/api/v2/templates/quiz", template),

      updateTemplate: (templateId: string, data: UpdateFlowTemplateRequest) =>
        this.put(`/api/v2/templates/quiz/${templateId}`, data),

      deleteTemplate: (templateId: string) =>
        this.delete(`/api/v2/templates/quiz/${templateId}`),

      // Analytics migrated to V2
      getTemplateAnalytics: (templateId: string) =>
        this.get(`/api/v2/quiz/templates/${templateId}/analytics`),
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
        return this.get("/api/v2/physician/risk-assessments", params);
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

interface ReportsApi {
  list: (options?: ReportsListOptions) => Promise<PaginatedResponse<Report>>;
  generate: (patientId: string, reportType: string, config?: Record<string, unknown>) => Promise<Report>;
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

interface AiApi {
  chat: (message: string, context?: Record<string, unknown>) => Promise<AIChatResponse>;
  analyze: (data: unknown, analysisType: string) => Promise<AIAnalysisResponse>;
  generateResponse: (patientId: string, messageHistory: Array<{ role: string; content: string }>, intent?: string) => Promise<AIGenerateResponseResponse>;
  sentiment: (text: string) => Promise<SentimentAnalysisResponse>;
  insights: (patientId: string, timeframe?: string) => Promise<AIInsights>;
  recommendations: (patientId: string) => Promise<AIRecommendations>;
}

interface QuizApi {
  templates: () => Promise<QuizTemplateResponse>;
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
  list: () => Promise<QuizTemplateResponse>;
  listTemplates: () => Promise<QuizTemplateResponse>;
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

interface QuizTemplate {
  id: string;
  name: string;
  description?: string;
  questions_count: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

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
  riskAssessments: (patientId?: string, daysLookback?: number) => Promise<RiskAssessmentsResponse>;
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
