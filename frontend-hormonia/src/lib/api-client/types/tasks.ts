import type { BaseFilters } from './common'

export enum TaskStatus {
  PENDING = 'PENDING',
  RUNNING = 'RUNNING',
  SUCCESS = 'SUCCESS',
  FAILURE = 'FAILURE',
  RETRY = 'RETRY',
  CANCELLED = 'CANCELLED',
}

export enum TaskType {
  CUSTOM = 'custom',
  DAILY_FLOW = 'daily_flow',
  MONTHLY_QUIZ = 'monthly_quiz',
  REPORT_GENERATION = 'report_generation',
  DATA_EXPORT = 'data_export',
  SYSTEM_MAINTENANCE = 'system_maintenance',
}

export enum TaskPriority {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  CRITICAL = 'critical',
}

export interface Task {
  id: string
  celery_task_id: string
  task_name: string
  task_type: string
  status: TaskStatus
  priority: TaskPriority
  description?: string
  metadata?: Record<string, unknown>
  progress?: {
    current: number
    total: number
    percent: number
    message?: string
    eta_seconds?: number
  }
  result?: unknown
  error?: string
  traceback?: string
  retry_count: number
  worker_name?: string
  queue_name?: string
  created_at: string
  started_at?: string
  completed_at?: string
  scheduled_at?: string
  timeout_seconds?: number
  user_id?: string
  runtime_seconds?: number
}

export interface TaskListFilters extends BaseFilters {
  status?: TaskStatus
  task_type?: TaskType
  priority?: TaskPriority
  user_id?: string
  start_date?: string
  end_date?: string
}

export interface QueueStatusV2 {
  queue_name: string
  pending_count: number
  active_count: number
  workers: string[]
  avg_processing_time?: number
}

export interface TaskStatisticsV2 {
  total_tasks: number
  pending_tasks: number
  running_tasks: number
  completed_tasks: number
  failed_tasks: number
  cancelled_tasks: number
  retry_tasks: number
  avg_runtime_seconds: number
  avg_wait_time_seconds: number
  success_rate: number
  tasks_by_type: Record<string, number>
  tasks_by_priority: Record<string, number>
  slowest_tasks: Array<{ task_name: string; runtime_seconds: number }>
  analysis_period_hours: number
}
