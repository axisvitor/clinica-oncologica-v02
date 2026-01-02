import { ApiClientCore } from "./core";
import {
    PaginatedResponse,
    Task,
    TaskListFilters,
    QueueStatusV2,
    TaskStatisticsV2,
    TaskType,
    TaskPriority
} from "./types";

export interface CreateTaskRequest {
    task_name: string;
    celery_task_name: string;
    task_type: TaskType;
    priority: TaskPriority;
    args?: unknown[];
    kwargs?: Record<string, unknown>;
    schedule_at?: string;
    timeout_seconds?: number;
    description?: string;
    metadata?: Record<string, unknown>;
    retry_config?: {
        max_retries: number;
        retry_strategy: 'immediate' | 'linear' | 'exponential' | 'fibonacci';
        base_delay: number;
        max_delay: number;
    };
}

export interface CancelTaskRequest {
    reason: string;
    force?: boolean;
}

export interface RetryTaskRequest {
    override_retry_limit?: boolean;
    delay_seconds?: number;
    notes?: string;
}

export interface TaskLogsResponse {
    id: string;
    logs: Array<{
        timestamp: string;
        level: string;
        message: string;
        context?: Record<string, unknown>;
    }>;
}

export interface TasksApi {
    list: (options?: TaskListFilters) => Promise<PaginatedResponse<Task>>;
    get: (taskId: string) => Promise<Task>;
    create: (data: CreateTaskRequest) => Promise<Task>;
    cancel: (taskId: string, data: CancelTaskRequest) => Promise<Task>;
    retry: (taskId: string, data: RetryTaskRequest) => Promise<Task>;
    getLogs: (taskId: string, limit?: number, level?: string) => Promise<TaskLogsResponse>;
    getStatistics: (hours?: number) => Promise<TaskStatisticsV2>;
    getQueueStatus: () => Promise<QueueStatusV2[]>;
    bulkCancel: (taskIds: string[]) => Promise<{
        success_count: number;
        failed_count: number;
        failed_ids: string[];
        errors: Record<string, string>;
    }>;
}

export function createTasksApi(client: ApiClientCore): TasksApi {
    return {
        list: async (options: TaskListFilters = {}) => {
            const { page: _page, size, cursor, limit, ...filters } = options;
            const effLimit = limit ?? size ?? 20;
            const params: Record<string, string | number | boolean> = {
                limit: effLimit,
                ...(cursor ? { cursor } : {}),
                ...filters
            };

            const res = await client.get<PaginatedResponse<Task>>("/api/v2/tasks", params);
            const items = Array.isArray(res?.data) ? res.data : (res?.items ?? []);

            return {
                data: items,
                items, // Backward compatibility
                total: res?.total ?? 0,
                has_more: res?.has_more,
                next_cursor: res?.next_cursor
            };
        },

        get: (taskId: string) => client.get<Task>(`/api/v2/tasks/${taskId}/`),

        create: (data: CreateTaskRequest) => client.post<Task>("/api/v2/tasks", data),

        cancel: (taskId: string, data: CancelTaskRequest) =>
            client.post<Task>(`/api/v2/tasks/${taskId}/cancel/`, data),

        retry: (taskId: string, data: RetryTaskRequest) =>
            client.post<Task>(`/api/v2/tasks/${taskId}/retry/`, data),

        getLogs: (taskId: string, limit = 100, level?: string) => {
            const params: Record<string, string | number | boolean> = { limit };
            if (level) params['level'] = level;
            return client.get<TaskLogsResponse>(`/api/v2/tasks/${taskId}/logs/`, params);
        },

        getStatistics: (hours = 24) =>
            client.get<TaskStatisticsV2>("/api/v2/tasks/statistics/overview", { hours }),

        getQueueStatus: () =>
            client.get<QueueStatusV2[]>("/api/v2/tasks/queue/status"),

        bulkCancel: (taskIds: string[]) =>
            client.post("/api/v2/tasks/bulk/cancel", {
                operation: "cancel",
                task_ids: taskIds
            }),
    };
}
