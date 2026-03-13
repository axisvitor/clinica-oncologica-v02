import type { ApiClientCore } from './core'
import type {
  Report,
  ReportListFilters,
  ScheduleReportRequest,
  ScheduledReport,
  PaginatedResponse,
  MessageResponse,
} from './types'

export interface ReportsListOptions extends ReportListFilters {
  page?: number
  size?: number
  cursor?: string
  limit?: number
}

export interface ReportGenerationConfig {
  title?: string
  format?: string
  start_date?: string
  end_date?: string
  include_messages?: boolean
  include_quizzes?: boolean
  include_alerts?: boolean
  include_timeline?: boolean
}

export interface ReportsApi {
  list: (options?: ReportsListOptions) => Promise<PaginatedResponse<Report>>
  generate: (
    patientId: string,
    reportType: string,
    config?: ReportGenerationConfig
  ) => Promise<Report>
  download: (reportId: string, format?: 'pdf' | 'excel' | 'csv') => Promise<Blob>
  delete: (reportId: string) => Promise<MessageResponse>
  schedule: (data: ScheduleReportRequest) => Promise<ScheduledReport>
  getScheduled: () => Promise<ScheduledReport[]>
}

export function createReportsApi(client: ApiClientCore): ReportsApi {
  return {
    list: async (options: ReportsListOptions = {}) => {
      const { size, cursor, limit, ...filters } = options
      const effLimit = limit ?? size ?? 20
      const params: Record<string, string | number | boolean> = {
        limit: effLimit,
        ...(cursor ? { cursor } : {}),
        ...filters,
      }
      const res = await client.get<PaginatedResponse<Report>>('/api/v2/reports', params)
      const items = Array.isArray(res?.data) ? res.data : (res?.items ?? [])
      return {
        data: items,
        items,
        total: res?.total ?? 0,
        has_more: res?.has_more,
        next_cursor: res?.next_cursor,
      }
    },

    generate: (patientId: string, reportType: string, config?: ReportGenerationConfig) => {
      const rawTitle = typeof config?.title === 'string' ? config.title.trim() : ''
      const params: Record<string, string | number | boolean> = {
        title: rawTitle || `Relatorio ${reportType}`,
        report_type: reportType,
      }

      if (patientId) {
        params['patient_ids'] = patientId
      }

      if (typeof config?.format === 'string' && config.format.trim()) {
        params['format'] = config.format.trim()
      }

      if (typeof config?.start_date === 'string' && config.start_date) {
        params['date_from'] = config.start_date
      }

      if (typeof config?.end_date === 'string' && config.end_date) {
        params['date_to'] = config.end_date
      }

      if (typeof config?.include_messages === 'boolean') {
        params['include_messages'] = config.include_messages
      }

      if (typeof config?.include_quizzes === 'boolean') {
        params['include_quizzes'] = config.include_quizzes
      }

      if (typeof config?.include_alerts === 'boolean') {
        params['include_alerts'] = config.include_alerts
      }

      if (typeof config?.include_timeline === 'boolean') {
        params['include_timeline'] = config.include_timeline
      }

      return client.post<Report>('/api/v2/reports/generate', undefined, params)
    },

    download: async (reportId: string, format: 'pdf' | 'excel' | 'csv' = 'pdf') => {
      const response = await fetch(
        `${client.getBaseURL()}/api/v2/reports/${reportId}/download?format=${format}`,
        {
          method: 'GET',
          headers: {
            ...client.getSessionHeaders(),
          },
          credentials: 'include',
        }
      )

      if (!response.ok) {
        throw new Error('Failed to download report')
      }

      return response.blob()
    },

    delete: (_reportId: string) => {
      throw new Error('Delete report not implemented in backend v2')
    },

    schedule: (data: ScheduleReportRequest) =>
      client.post<ScheduledReport>('/api/v2/reports/schedule', data),

    getScheduled: () => {
      throw new Error('Get scheduled reports not implemented in backend v2')
    },
  }
}
