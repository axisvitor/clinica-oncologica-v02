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
import { createMonthlyQuizApi } from "./monthly-quiz";
import { createAnalyticsApi } from "./analytics";
import { createLogger } from "../logger";
import { API_BASE_URL } from "../../config";

const logger = createLogger("ApiClient");

// Re-export core types
export type { ApiResponse, PaginatedResponse, RequestOptions } from "./core";
export { ApiError } from "./core";

// Re-export domain types
export type * from "./auth";
export type * from "./patients";
export type * from "./monthly-quiz";
export type * from "./analytics";

/**
 * Main API Client class
 * Extends core with domain-specific modules
 */
export class ApiClient extends ApiClientCore {
  // Domain modules
  public readonly auth: ReturnType<typeof createAuthApi>;
  public readonly patients: ReturnType<typeof createPatientsApi>;
  public readonly monthlyQuiz: ReturnType<typeof createMonthlyQuizApi>;
  public readonly analytics: ReturnType<typeof createAnalyticsApi>;

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

  constructor(baseURL: string) {
    super(baseURL);

    // Initialize domain modules
    this.auth = createAuthApi(this);
    this.patients = createPatientsApi(this);
    this.monthlyQuiz = createMonthlyQuizApi(this);
    this.analytics = createAnalyticsApi(this);

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

    logger.log("API Client initialized with modular architecture");
  }

  /**
   * Messages API (inline implementation)
   */
  private createMessagesApi(): MessagesApi {
    return {
      list: (options: MessagesListOptions = {}) => {
        const { page = 1, size = 20, ...filters } = options;
        return this.get("/api/v1/messages", { page, size, ...filters });
      },

      get: (messageId: string) => this.get(`/api/v1/messages/${messageId}`),

      send: (data: any) => this.post("/api/v1/messages", data),

      markAsRead: (messageId: string) => this.patch(`/api/v1/messages/${messageId}/read`),

      delete: (messageId: string) => this.delete(`/api/v1/messages/${messageId}`),

      getConversation: (patientId: string) =>
        this.get(`/api/v1/messages/conversations/${patientId}`),

      sendBulk: (data: { patient_ids: string[]; content: string }) =>
        this.post("/api/v1/messages/bulk", data),

      retry: (messageId: string) => this.post(`/api/v1/messages/${messageId}/retry`),
    };
  }

  /**
   * Flows API (inline implementation)
   */
  private createFlowsApi(): FlowsApi {
    return {
      list: (options: Record<string, any> = {}) => this.get("/api/v1/flows", options),

      get: (flowId: string) => this.get(`/api/v1/flows/${flowId}`),

      create: (data: any) => this.post("/api/v1/flows", data),

      update: (flowId: string, data: any) => this.put(`/api/v1/flows/${flowId}`, data),

      delete: (flowId: string) => this.delete(`/api/v1/flows/${flowId}`),

      activate: (flowId: string) => this.post(`/api/v1/flows/${flowId}/activate`),

      deactivate: (flowId: string) => this.post(`/api/v1/flows/${flowId}/deactivate`),

      execute: (flowId: string, data?: any) => this.post(`/api/v1/flows/${flowId}/execute`, data),

      getExecutions: (flowId: string) => this.get(`/api/v1/flows/${flowId}/executions`),

      getState: (patientId: string) => this.get(`/api/v1/flows/${patientId}/state`),

      // Compatibility methods used by FlowEngine/TemplateManager
      start: (patientId: string, flowType: string) =>
        this.post("/api/v1/flows/start", { patient_id: patientId, flow_type: flowType }),

      advance: (patientId: string, day?: number) =>
        this.post(`/api/v1/flows/${patientId}/advance`, day ? { day } : undefined),

      pause: async (patientId: string) => {
        // If backend endpoint not available yet, fall back to state fetch
        try {
          return await this.post(`/api/v1/flows/${patientId}/pause`)
        } catch {
          return this.get(`/api/v1/flows/${patientId}/state`)
        }
      },

      resume: async (patientId: string) => {
        try {
          return await this.post(`/api/v1/flows/${patientId}/resume`)
        } catch {
          return this.get(`/api/v1/flows/${patientId}/state`)
        }
      },

      processResponse: (
        patientId: string,
        responseText: string,
        metadata?: Record<string, any>,
      ) => this.post("/api/v1/flows/process-response", { patient_id: patientId, response_text: responseText, metadata }),

      getAnalytics: () => this.get("/api/v1/flows/analytics"),

      // Templates management
      getTemplates: () => this.get("/api/v1/flows/templates"),
      createTemplate: (template: any) => this.post("/api/v1/flows/templates", template),
      updateTemplate: (templateId: string, data: any) =>
        this.put(`/api/v1/flows/templates/${templateId}`, data),
      deleteTemplate: (templateId: string) => this.delete(`/api/v1/flows/templates/${templateId}`),
    };
  }

  /**
   * Alerts API (inline implementation)
   */
  private createAlertsApi(): AlertsApi {
    return {
      list: (options: AlertsListOptions = {}) => {
        const { page = 1, size = 20, ...filters } = options;
        return this.get("/api/v1/alerts", { page, size, ...filters });
      },

      get: (alertId: string) => this.get(`/api/v1/alerts/${alertId}`),

      create: (data: any) => this.post("/api/v1/alerts", data),

      update: (alertId: string, data: any) => this.put(`/api/v1/alerts/${alertId}`, data),

      delete: (alertId: string) => this.delete(`/api/v1/alerts/${alertId}`),

      markAsRead: (alertId: string) => this.patch(`/api/v1/alerts/${alertId}/read`),

      markAllAsRead: () => this.post("/api/v1/alerts/read-all"),

      getUnreadCount: () => this.get("/api/v1/alerts/unread-count"),

      acknowledge: (alertId: string) => this.post(`/api/v1/alerts/${alertId}/acknowledge`),

      resolve: (alertId: string) => this.post(`/api/v1/alerts/${alertId}/resolve`),
    };
  }

  /**
   * Reports API (inline implementation)
   */
  private createReportsApi(): ReportsApi {
    return {
      list: async (options: ReportsListOptions = {}) => {
        const { page = 1, size = 20, ...filters } = options;
        const res: any = await this.get("/api/v1/reports", { page, size, ...filters });
        if (Array.isArray(res)) {
          return { items: res };
        }
        if (Array.isArray(res?.data)) {
          return { items: res.data, total: res.total ?? res.total_count ?? res.data.length };
        }
        return res;
      },

      generate: (patientId: string, reportType: string, config?: Record<string, any>) =>
        this.post("/api/v1/reports/generate", {
          patient_id: patientId,
          type: reportType,
          config,
        }),

      download: async (reportId: string, format: "pdf" | "excel" | "csv" = "pdf") => {
        const response = await fetch(
          `${this.getBaseURL()}/api/v1/reports/${reportId}/download?format=${format}`,
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

      delete: (reportId: string) => this.delete(`/api/v1/reports/${reportId}`),

      schedule: (data: {
        report_type: string;
        frequency: "daily" | "weekly" | "monthly";
        recipients: string[];
        parameters?: any;
      }) => this.post("/api/v1/reports/schedule", data),

      getScheduled: () => this.get("/api/v1/reports/scheduled"),
    };
  }

  /**
   * Admin API (inline implementation)
   */
  private createAdminApi(): AdminApi {
    return {
      users: {
        list: (page = 1, size = 20) => this.get("/api/v1/admin/users", { page, size }),

        get: (userId: string) => this.get(`/api/v1/admin/users/${userId}`),

        create: (data: any) => this.post("/api/v1/admin/users", data),

        update: (userId: string, data: any) => this.put(`/api/v1/admin/users/${userId}`, data),

        delete: (userId: string) => this.delete(`/api/v1/admin/users/${userId}`),

        resetPassword: (userId: string) =>
          this.post(`/api/v1/admin/users/${userId}/reset-password`),

        toggleStatus: (userId: string) => this.patch(`/api/v1/admin/users/${userId}/toggle-status`),
      },

      roles: {
        list: () => this.get("/api/v1/admin/roles"),

        create: (data: any) => this.post("/api/v1/admin/roles", data),

        update: (roleId: string, data: any) => this.put(`/api/v1/admin/roles/${roleId}`, data),

        delete: (roleId: string) => this.delete(`/api/v1/admin/roles/${roleId}`),
      },

      audit: {
        list: (page = 1, size = 20, filters?: any) =>
          this.get("/api/v1/admin/audit", { page, size, ...filters }),

        get: (auditId: string) => this.get(`/api/v1/admin/audit/${auditId}`),

        export: async (filters?: any) => {
          const queryParams = new URLSearchParams(filters as any);
          const response = await fetch(
            `${this.getBaseURL()}/api/v1/admin/audit/export?${queryParams}`,
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
        get: () => this.get("/api/v1/admin/settings"),

        update: (data: any) => this.put("/api/v1/admin/settings", data),

        reset: () => this.post("/api/v1/admin/settings/reset"),
      },

      system: {
        getHealth: () => this.get("/api/v1/admin/system/health"),

        getMetrics: () => this.get("/api/v1/admin/system/metrics"),

        systemStats: () => this.get("/api/v1/admin/system/stats"),

        clearCache: () => this.post("/api/v1/admin/system/clear-cache"),

        runMaintenance: () => this.post("/api/v1/admin/system/maintenance"),
      },
    };
  }

  private createAdminUsersApi(): AdminUsersApi {
    return {
      list: (options: AdminUsersListOptions = {}) => {
        const { page = 1, size = 20, ...filters } = options;
        return this.get("/api/v1/admin/users", { page, size, ...filters });
      },

      get: (userId: string) => this.get(`/api/v1/admin/users/${userId}`),

      create: (data: any) => this.post("/api/v1/admin/users", data),

      update: (userId: string, data: any) => this.put(`/api/v1/admin/users/${userId}`, data),

      delete: (userId: string) => this.delete(`/api/v1/admin/users/${userId}`),

      activate: (userId: string) => this.post(`/api/v1/admin/users/${userId}/activate`),

      deactivate: (userId: string) => this.post(`/api/v1/admin/users/${userId}/deactivate`),

      updatePermissions: (userId: string, permissions: string[]) =>
        this.put(`/api/v1/admin/users/${userId}/permissions`, { permissions }),

      updateRole: (userId: string, role: string) =>
        this.put(`/api/v1/admin/users/${userId}/role`, { role }),

      getActivity: (userId: string, options: AdminUserActivityOptions = {}) => {
        const { page = 1, size = 20, ...filters } = options;
        return this.get(`/api/v1/admin/users/${userId}/activity`, { page, size, ...filters });
      },

      resetPassword: (userId: string, payload: { new_password: string; force_change: boolean }) =>
        this.post(`/api/v1/admin/users/${userId}/reset-password`, payload),

      unlock: (userId: string) => this.post(`/api/v1/admin/users/${userId}/unlock`),

      enable2FA: (userId: string) => this.post(`/api/v1/admin/users/${userId}/2fa/enable`),

      disable2FA: (userId: string) => this.post(`/api/v1/admin/users/${userId}/2fa/disable`),
    };
  }

  private createAiApi(): AiApi {
    return {
      chat: (message: string, context?: any) =>
        this.post("/api/v1/ai/chat", { message, context }),

      analyze: (data: any, analysisType: string) =>
        this.post("/api/v1/ai/analyze", { data, analysis_type: analysisType }),

      generateResponse: (patientId: string, messageHistory: any[], intent?: string) =>
        this.post("/api/v1/ai/generate-response", {
          patient_id: patientId,
          message_history: messageHistory,
          intent,
        }),

      sentiment: (text: string) => this.post("/api/v1/ai/sentiment", { text }),

      insights: (patientId: string, timeframe?: string) =>
        this.get(`/api/v1/ai/insights/${patientId}`, timeframe ? { timeframe } : undefined),

      recommendations: (patientId: string) =>
        this.get(`/api/v1/ai/recommendations/${patientId}`),
    };
  }

  private createQuizApi(): QuizApi {
    return {
      templates: async () => {
        const res: any = await this.get("/api/v1/quiz/templates")
        return Array.isArray(res) ? { items: res } : res
      },

      // Create a new quiz session (v2)
      start: (patientId: string, quizTemplateId: string) =>
        this.post("/api/v2/quiz", {
          patient_id: patientId,
          quiz_template_id: quizTemplateId,
        }),

      // Get session by ID (v2)
      getSession: (sessionId: string) => this.get(`/api/v2/quiz/${sessionId}`),

      submitResponse: (
        sessionId: string,
        questionId: string,
        answer: string,
        responseMetadata?: Record<string, any>,
      ) => {
        const params: Record<string, string> = {
          question_id: questionId,
          answer,
        };
        if (responseMetadata) {
          params["response_metadata"] = JSON.stringify(responseMetadata);
        }
        return this.post(`/api/v1/quiz/sessions/${sessionId}/submit`, undefined, params);
      },

      // List sessions (v2) with cursor pagination; keep backward-compatible shape
      sessions: async (filters: Record<string, any> = {}) => {
        const { page, size, limit, cursor, ...rest } = filters || {}
        const effLimit = limit ?? size ?? 20
        const params: Record<string, any> = { limit: effLimit, ...(cursor ? { cursor } : {}), ...rest }
        const res: any = await this.get("/api/v2/quiz", params)
        const items = Array.isArray(res?.data) ? res.data : (res?.items ?? [])
        const total = res?.total ?? 0
        const has_more = res?.has_more ?? false
        const next_cursor = res?.next_cursor ?? null
        return { items, total, has_more, next_cursor }
      },

      getPatientResponses: (
        patientId: string,
        options: Record<string, any> = {},
      ) => this.get(`/api/v1/patients/${patientId}/quiz-responses`, options),

      // Responses/analysis remain on v1 for now
      getSessionResponses: (sessionId: string) =>
        this.get(`/api/v1/quiz/sessions/${sessionId}/responses`),

      getSessionAnalysis: (sessionId: string) =>
        this.get(`/api/v1/quiz/sessions/${sessionId}/analysis`),
    };
  }

  private createQuizTemplatesApi(): QuizTemplatesApi {
    return {
      list: () => this.quiz.templates(),
      listTemplates: () => this.quiz.templates(),
      createTemplate: (template: any) => this.post("/api/v1/quiz/templates", template),
      create: (template: any) => this.post("/api/v1/quiz/templates", template),
      updateTemplate: (templateId: string, data: any) =>
        this.put(`/api/v1/quiz/templates/${templateId}`, data),
      deleteTemplate: (templateId: string) =>
        this.delete(`/api/v1/quiz/templates/${templateId}`),
      getTemplateAnalytics: (templateId: string) =>
        this.get(`/api/v1/quiz/templates/${templateId}/analytics`),
    };
  }

  private createNotificationsApi(): NotificationsApi {
    return {
      list: () => this.get("/api/v1/auth/notifications"),
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
        return this.get("/api/v1/physician/risk-assessments", params);
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
interface MessagesListOptions {
  page?: number;
  size?: number;
  [key: string]: any;
}

interface MessagesApi {
  list: (options?: MessagesListOptions) => Promise<any>;
  get: (messageId: string) => Promise<any>;
  send: (data: any) => Promise<any>;
  markAsRead: (messageId: string) => Promise<any>;
  delete: (messageId: string) => Promise<any>;
  getConversation: (patientId: string) => Promise<any>;
  sendBulk: (data: { patient_ids: string[]; content: string }) => Promise<any>;
  retry: (messageId: string) => Promise<any>;
}

interface FlowsApi {
  list: (options?: Record<string, any>) => Promise<any>;
  get: (flowId: string) => Promise<any>;
  create: (data: any) => Promise<any>;
  update: (flowId: string, data: any) => Promise<any>;
  delete: (flowId: string) => Promise<any>;
  activate: (flowId: string) => Promise<any>;
  deactivate: (flowId: string) => Promise<any>;
  execute: (flowId: string, data?: any) => Promise<any>;
  getExecutions: (flowId: string) => Promise<any>;
  getState: (patientId: string) => Promise<any>;
  start: (patientId: string, flowType: string) => Promise<any>;
  advance: (patientId: string, day?: number) => Promise<any>;
  pause: (patientId: string) => Promise<any>;
  resume: (patientId: string) => Promise<any>;
  processResponse: (patientId: string, responseText: string, metadata?: Record<string, any>) => Promise<any>;
  getAnalytics: () => Promise<any>;
  getTemplates: () => Promise<any>;
  createTemplate: (template: any) => Promise<any>;
  updateTemplate: (templateId: string, data: any) => Promise<any>;
  deleteTemplate: (templateId: string) => Promise<any>;
}

interface AlertsListOptions {
  page?: number;
  size?: number;
  [key: string]: any;
}

interface AlertsApi {
  list: (options?: AlertsListOptions) => Promise<any>;
  get: (alertId: string) => Promise<any>;
  create: (data: any) => Promise<any>;
  update: (alertId: string, data: any) => Promise<any>;
  delete: (alertId: string) => Promise<any>;
  markAsRead: (alertId: string) => Promise<any>;
  markAllAsRead: () => Promise<any>;
  getUnreadCount: () => Promise<any>;
  acknowledge: (alertId: string) => Promise<any>;
  resolve: (alertId: string) => Promise<any>;
}

interface ReportsListOptions {
  page?: number;
  size?: number;
  [key: string]: any;
}

interface ReportsApi {
  list: (options?: ReportsListOptions) => Promise<any>;
  generate: (patientId: string, reportType: string, config?: Record<string, any>) => Promise<any>;
  download: (reportId: string, format?: "pdf" | "excel" | "csv") => Promise<Blob>;
  delete: (reportId: string) => Promise<any>;
  schedule: (data: {
    report_type: string;
    frequency: "daily" | "weekly" | "monthly";
    recipients: string[];
    parameters?: any;
  }) => Promise<any>;
  getScheduled: () => Promise<any>;
}

interface AdminApi {
  users: {
    list: (page?: number, size?: number) => Promise<any>;
    get: (userId: string) => Promise<any>;
    create: (data: any) => Promise<any>;
    update: (userId: string, data: any) => Promise<any>;
    delete: (userId: string) => Promise<any>;
    resetPassword: (userId: string) => Promise<any>;
    toggleStatus: (userId: string) => Promise<any>;
  };
  roles: {
    list: () => Promise<any>;
    create: (data: any) => Promise<any>;
    update: (roleId: string, data: any) => Promise<any>;
    delete: (roleId: string) => Promise<any>;
  };
  audit: {
    list: (page?: number, size?: number, filters?: any) => Promise<any>;
    get: (auditId: string) => Promise<any>;
    export: (filters?: any) => Promise<Blob>;
  };
  settings: {
    get: () => Promise<any>;
    update: (data: any) => Promise<any>;
    reset: () => Promise<any>;
  };
  system: {
    getHealth: () => Promise<any>;
    getMetrics: () => Promise<any>;
    systemStats: () => Promise<any>;
    clearCache: () => Promise<any>;
    runMaintenance: () => Promise<any>;
  };
}

interface AdminUsersListOptions {
  page?: number;
  size?: number;
  search?: string;
  role?: string;
  status?: string;
  [key: string]: any;
}

interface AdminUserActivityOptions {
  page?: number;
  size?: number;
  [key: string]: any;
}

interface AdminUsersApi {
  list: (options?: AdminUsersListOptions) => Promise<any>;
  get: (userId: string) => Promise<any>;
  create: (data: any) => Promise<any>;
  update: (userId: string, data: any) => Promise<any>;
  delete: (userId: string) => Promise<any>;
  activate: (userId: string) => Promise<any>;
  deactivate: (userId: string) => Promise<any>;
  updatePermissions: (userId: string, permissions: string[]) => Promise<any>;
  updateRole: (userId: string, role: string) => Promise<any>;
  getActivity: (userId: string, options?: AdminUserActivityOptions) => Promise<any>;
  resetPassword: (userId: string, payload: { new_password: string; force_change: boolean }) => Promise<any>;
  unlock: (userId: string) => Promise<any>;
  enable2FA: (userId: string) => Promise<any>;
  disable2FA: (userId: string) => Promise<any>;
}

interface AiApi {
  chat: (message: string, context?: any) => Promise<any>;
  analyze: (data: any, analysisType: string) => Promise<any>;
  generateResponse: (patientId: string, messageHistory: any[], intent?: string) => Promise<any>;
  sentiment: (text: string) => Promise<any>;
  insights: (patientId: string, timeframe?: string) => Promise<any>;
  recommendations: (patientId: string) => Promise<any>;
}

interface QuizApi {
  templates: () => Promise<any>;
  start: (patientId: string, quizTemplateId: string) => Promise<any>;
  getSession: (sessionId: string) => Promise<any>;
  submitResponse: (
    sessionId: string,
    questionId: string,
    answer: string,
    responseMetadata?: Record<string, any>,
  ) => Promise<any>;
  sessions: (filters?: Record<string, any>) => Promise<any>;
  getPatientResponses: (patientId: string, options?: Record<string, any>) => Promise<any>;
  getSessionResponses: (sessionId: string) => Promise<any>;
  getSessionAnalysis: (sessionId: string) => Promise<any>;
}

interface QuizTemplatesApi {
  list: () => Promise<any>;
  listTemplates: () => Promise<any>;
  createTemplate: (template: any) => Promise<any>;
  create: (template: any) => Promise<any>;
  updateTemplate: (templateId: string, data: any) => Promise<any>;
  deleteTemplate: (templateId: string) => Promise<any>;
  getTemplateAnalytics: (templateId: string) => Promise<any>;
}

interface NotificationsApi {
  list: () => Promise<any>;
}

interface PhysicianApi {
  riskAssessments: (patientId?: string, daysLookback?: number) => Promise<any>;
}

// Create singleton instance
const getApiUrl = () => {
  return (
    API_BASE_URL ||
    import.meta.env["VITE_API_URL"] ||
    "https://clinica-oncologica-v02-production.up.railway.app"
  );
};

export const apiClient = new ApiClient(getApiUrl());

// Default export
export default apiClient;
