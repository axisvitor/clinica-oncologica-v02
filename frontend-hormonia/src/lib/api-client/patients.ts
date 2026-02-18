/**
 * Patients API Module
 *
 * Handles all patient-related API calls:
 * - CRUD operations for patients
 * - Patient search and filtering
 * - Patient medical history
 * - Patient appointments
 * - Patient documents
 */

import type { ApiClientCore, PaginatedResponse } from './core'
import type { TimelineEvent } from '@/types/api'
import { normalizePatient, denormalizePatient, normalizePatientList } from './normalizers'
import type { BackendPatient, FrontendPatient } from './normalizers'

/**
 * Patient type - uses FrontendPatient from normalizers
 * This ensures consistent typing across the application
 */
export type Patient = FrontendPatient

export interface PatientCreate {
  name: string
  email?: string
  phone: string
  cpf?: string
  birth_date?: string
  gender?: 'M' | 'F' | 'other'
  address?: Patient['address']
  medical_info?: Patient['medical_info']
  doctor_id: string
  treatment_type?: string
  treatment_start_date?: string
  doctor_notes?: string
  timezone?: string
}

export interface PatientUpdate extends Partial<PatientCreate> {
  status?: 'active' | 'inactive' | 'archived' | 'paused' | 'completed'
}

export interface PatientFilters {
  search?: string
  status?: 'active' | 'inactive' | 'archived'
  doctor_id?: string
  created_after?: string
  created_before?: string
}

export interface PatientAppointment {
  id: string
  patient_id: string
  doctor_id: string
  scheduled_at: string
  duration_minutes?: number
  type?: string
  status: 'scheduled' | 'completed' | 'cancelled' | 'no_show'
  notes?: string
  created_at: string
  updated_at: string
}

export interface PatientDocument {
  id: string
  patient_id: string
  name: string
  type: string
  file_url: string
  file_size: number
  uploaded_by: string
  uploaded_at: string
}

export interface PatientMedicalHistory {
  patient_id: string
  entries: Array<{
    id: string
    date: string
    type: 'consultation' | 'exam' | 'prescription' | 'note'
    title: string
    description?: string
    doctor_id?: string
    created_at: string
  }>
}

export interface PatientStats {
  total_patients: number
  active_patients: number
  inactive_patients: number
  new_this_month: number
  by_status: Record<string, number>
  by_doctor?: Record<string, number>
}

type BackendTimelineEvent = {
  id?: string
  patient_id?: string
  type?: string
  event?: string
  event_type?: string
  title?: string
  description?: string
  details?: string
  date?: string
  timestamp?: string
  created_at?: string
  metadata?: Record<string, unknown>
}

const normalizeTimelineDate = (value?: unknown): string | undefined => {
  if (value instanceof Date) {
    return value.toISOString()
  }
  if (typeof value === 'number') {
    const date = new Date(value)
    return Number.isNaN(date.getTime()) ? undefined : date.toISOString()
  }
  if (typeof value !== 'string') {
    return undefined
  }
  const trimmed = value.trim()
  if (!trimmed) {
    return undefined
  }
  return trimmed.replace(/(\.\d{3})\d+/, '$1')
}

const normalizeTimelineEventType = (rawType?: string): TimelineEvent['event_type'] => {
  const normalized = (rawType || '').toLowerCase()
  if (!normalized) {
    return 'system'
  }
  if (normalized.includes('message')) {
    return 'message'
  }
  if (normalized.includes('appointment')) {
    return 'appointment'
  }
  if (normalized.includes('note')) {
    return 'note'
  }
  if (normalized.includes('quiz')) {
    return 'quiz'
  }
  if (normalized.includes('alert')) {
    return 'alert'
  }
  if (normalized.includes('report')) {
    return 'report'
  }
  if (
    normalized.includes('flow') ||
    normalized.includes('saga') ||
    normalized.includes('patient') ||
    normalized.includes('status_change') ||
    normalized.includes('treatment_start') ||
    normalized.includes('archived') ||
    normalized.includes('created')
  ) {
    return 'flow_change'
  }
  return 'system'
}

const getTimelineDate = (event: BackendTimelineEvent): string | undefined => {
  const metadata = event.metadata ?? {}
  const candidates: Array<unknown> = [
    event.timestamp,
    event.created_at,
    event.date,
    metadata['timestamp'],
    metadata['created_at'],
    metadata['date']
  ]
  for (const candidate of candidates) {
    const normalized = normalizeTimelineDate(candidate)
    if (normalized) {
      return normalized
    }
  }
  return undefined
}

const normalizeTimelineEvent = (
  event: BackendTimelineEvent,
  patientId: string,
  index: number
): TimelineEvent => {
  const eventType = normalizeTimelineEventType(event.type ?? event.event_type ?? event.event)
  const createdAt = getTimelineDate(event) ?? ''
  const title = event.title ?? event.type ?? event.event ?? 'Evento'
  const description = event.description ?? event.details ?? ''

  return {
    id: event.id ?? `${patientId}-${eventType}-${index}`,
    patient_id: event.patient_id ?? patientId,
    event_type: eventType,
    title,
    description,
    metadata: event.metadata ?? {},
    created_at: createdAt
  }
}



/**
 * Patients API methods
 */
export function createPatientsApi(client: ApiClientCore) {
  return {
    /**
     * List patients with pagination and filters
     */
    list: async (
      pageOrOptions: number | (PatientFilters & { page?: number; size?: number; cursor?: string; limit?: number }) = 1,
      size: number = 20,
      filters?: PatientFilters
    ): Promise<PaginatedResponse<Patient>> => {
      // Support both legacy page/size and v2 cursor/limit
      let page = 1
      let limit = 20
      let cursor: string | undefined
      let rest: Record<string, unknown> = {}

      if (typeof pageOrOptions === 'number') {
        page = pageOrOptions
        limit = size ?? 20
        rest = { ...(filters || {}) }
      } else {
        const { page: optPage = 1, size: optionSize = 20, cursor: optCursor, limit: optLimit, ...other } = pageOrOptions
        page = optPage
        limit = (optLimit ?? optionSize) ?? 20
        cursor = optCursor
        rest = other
      }

      const query = {
        limit,
        ...(cursor ? { cursor } : {}),
        ...rest
      }

      const res = await client.get<{ data?: BackendPatient[]; items?: BackendPatient[]; total?: number; total_count?: number; pages?: number; has_more?: boolean; next_cursor?: string }>('/api/v2/patients/', query)

      // Normalize to keep backward compatibility with components expecting `items`
      const rawItems = Array.isArray(res?.data) ? res.data : (res?.items ?? [])
      const items = normalizePatientList(rawItems as BackendPatient[])
      const total = res?.total ?? res?.total_count ?? items.length ?? 0
      const has_more = res?.has_more ?? (typeof res?.pages === 'number' && page < res.pages)
      const next_cursor = res?.next_cursor ?? null
      const normalized: PaginatedResponse<Patient> & { data: Patient[]; has_more: boolean; next_cursor: string | null } = {
        items,
        total,
        page,
        size: limit,
        pages: total ? Math.ceil(total / Math.max(1, limit)) : (res?.pages ?? undefined),
        has_more,
        next_cursor,
        // keep v2 shape as well for newer consumers
        data: items
      }

      return normalized as PaginatedResponse<Patient>
    },

    /**
     * Get patient by ID
     */
    get: async (patientId: string): Promise<Patient> => {
      const patient = await client.get<BackendPatient>(`/api/v2/patients/${patientId}`)
      return normalizePatient(patient)
    },

    /**
     * Create new patient
     */
    create: async (
      data: PatientCreate,
      options?: { headers?: Record<string, string> }
    ): Promise<Patient> => {
      if (!data?.doctor_id) {
        throw new Error('doctor_id is required to create a patient')
      }
      // Denormalize frontend data to backend format before sending
      const backendData = denormalizePatient(data as PatientCreate | PatientUpdate)

      if (options?.headers) {
        const patient = await client.request<BackendPatient>('/api/v2/patients/', {
          method: 'POST',
          body: JSON.stringify(backendData),
          headers: {
            ...options.headers
          }
        })
        return normalizePatient(patient)
      }

      const patient = await client.post<BackendPatient>('/api/v2/patients/', backendData)
      return normalizePatient(patient)
    },

    /**
     * Update patient
     */
    update: async (patientId: string, data: PatientUpdate, options?: { headers?: Record<string, string> }): Promise<Patient> => {
      // Denormalize frontend data to backend format before sending
      const backendData = denormalizePatient(data as PatientCreate | PatientUpdate)

      // If options.headers provided, we need to pass them through request options
      // Since patch doesn't support options, we'll call request directly
      if (options?.headers) {
        const patient = await client.request<BackendPatient>(`/api/v2/patients/${patientId}`, {
          method: 'PATCH',
          body: JSON.stringify(backendData),
          headers: {
            'Content-Type': 'application/json',
            ...options.headers
          }
        })
        return normalizePatient(patient)
      }

      const patient = await client.patch<BackendPatient>(`/api/v2/patients/${patientId}`, backendData)
      return normalizePatient(patient)
    },

    /**
     * Delete patient (soft delete)
     */
    delete: async (patientId: string): Promise<{ message: string }> => {
      return client.delete<{ message: string }>(`/api/v2/patients/${patientId}`)
    },

    /**
     * Alias for delete to match component usage
     */
    deletePatient: async (patientId: string): Promise<{ message: string }> => {
      return client.delete<{ message: string }>(`/api/v2/patients/${patientId}`)
    },

    /**
     * Activate patient
     */
    activate: async (patientId: string): Promise<Patient> => {
      // Using update to set status to active
      const backendData = denormalizePatient({ status: 'active' } as PatientUpdate)
      const patient = await client.patch<BackendPatient>(`/api/v2/patients/${patientId}`, backendData)
      return normalizePatient(patient)
    },

    /**
     * Deactivate (pause) patient
     */
    deactivate: async (patientId: string): Promise<Patient> => {
      // Using update to set status to paused
      const backendData = denormalizePatient({ status: 'paused' } as PatientUpdate)
      const patient = await client.patch<BackendPatient>(`/api/v2/patients/${patientId}`, backendData)
      return normalizePatient(patient)
    },

    /**
     * Get patient timeline
     */
    timeline: async (patientId: string): Promise<{ events: TimelineEvent[] }> => {
      const response = await client.get<{
        patient_id?: string
        events?: BackendTimelineEvent[]
        items?: BackendTimelineEvent[]
      }>(`/api/v2/patients/${patientId}/timeline`)
      const rawEvents = Array.isArray(response?.events)
        ? response.events
        : (response?.items ?? [])
      const resolvedPatientId = response?.patient_id ?? patientId
      return {
        events: rawEvents.map((event, index) => normalizeTimelineEvent(event, resolvedPatientId, index))
      }
    },


    /**
     * REMOVED: Medical History, Appointments, Documents
     * These methods were defined but never used in any frontend component.
     * If needed in the future, implement in V2 backend first.
     *
     * Removed methods (unused code):
     * - getMedicalHistory()
     * - addMedicalHistoryEntry()
     * - getAppointments()
     * - scheduleAppointment()
     * - getDocuments()
     * - uploadDocument()
     * - deleteDocument()
     */

    /**
     * Get patient statistics
     */
    getStats: async (filters?: {
      doctor_id?: string
      start_date?: string
      end_date?: string
    }): Promise<PatientStats> => {
      return client.get<PatientStats>('/api/v2/patients/stats/', filters)
    },

    /**
     * Export patients to CSV (V2)
     */
    exportToCsv: async (filters?: PatientFilters): Promise<Blob> => {
      const response = await fetch(
        `${client.getBaseURL()}/api/v2/patients/export?${new URLSearchParams(filters as Record<string, string>)}`,
        {
          method: 'GET',
          headers: {
            ...client.getSessionHeaders(),
          },
          credentials: 'include'
        }
      )

      if (!response.ok) {
        throw new Error('Failed to export patients')
      }

      return response.blob()
    },

    /**
     * Import patients from CSV (V2)
     */
    importFromCsv: async (file: File): Promise<{
      success: number
      failed: number
      errors?: Array<{ row: number; message: string }>
    }> => {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch(
        `${client.getBaseURL()}/api/v2/patients/import`,
        {
          method: 'POST',
          headers: {
            ...client.getSessionHeaders(),
          },
          credentials: 'include',
          body: formData
        }
      )

      if (!response.ok) {
        throw new Error('Failed to import patients')
      }

      return response.json()
    },

    /**
     * Validate CPF (Brazilian tax ID)
     */
    validateCpf: async (cpf: string): Promise<{ valid: boolean; message?: string }> => {
      return client.post<{ valid: boolean; message?: string }>(
        '/api/v2/patients/validate-cpf',
        { cpf }
      )
    },

    /**
     * Check if email is already registered
     */
    checkEmailExists: async (email: string): Promise<{ exists: boolean }> => {
      return client.get<{ exists: boolean }>('/api/v2/patients/check-email/', { email })
    },

    /**
     * Import patients from CSV/Excel file
     *
     * Backend returns: { success: number, failed: number, errors: Array<{row: number, message: string}> }
     */
    importPatients: async (
      file: File,
      options?: {
        skipDuplicates?: boolean;
        updateExisting?: boolean;
        validateOnly?: boolean;
      }
    ): Promise<{
      success: number;
      failed: number;
      errors: Array<{ row: number; message: string }>;
    }> => {
      const formData = new FormData()
      formData.append('file', file)

      // Add options as query params
      const params = new URLSearchParams()
      if (options?.skipDuplicates) params.append('skip_duplicates', 'true')
      if (options?.updateExisting) params.append('update_existing', 'true')
      if (options?.validateOnly) params.append('validate_only', 'true')

      const queryString = params.toString() ? `?${params.toString()}` : ''

      const response = await fetch(
        `${client.getBaseURL()}/api/v2/patients/import${queryString}`,
        {
          method: 'POST',
          headers: {
            ...client.getSessionHeaders(),
          },
          credentials: 'include',
          body: formData
        }
      )

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Import failed' }))
        throw new Error(error.detail || 'Failed to import patients')
      }

      // Backend returns { success, failed, errors }
      const result = await response.json()
      return {
        success: result.success || 0,
        failed: result.failed || 0,
        errors: result.errors || []
      }
    },

    /**
     * Validate import file without importing
     */
    validateImport: async (file: File): Promise<{
      valid: boolean;
      totalRows: number;
      validRows: number;
      errorRows: number;
      warningRows: number;
      errors: Array<{ row: number; column?: string; message: string; severity: 'error' | 'warning' }>;
      warnings: Array<{ row: number; column?: string; message: string }>;
      preview: Array<{ row: number; name: string; email?: string; phone?: string; cpf?: string }>;
      format: 'csv' | 'xlsx';
      fileSize: number;
    }> => {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch(
        `${client.getBaseURL()}/api/v2/patients/import/validate`,
        {
          method: 'POST',
          headers: {
            ...client.getSessionHeaders(),
          },
          credentials: 'include',
          body: formData
        }
      )

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Validation failed' }))
        throw new Error(error.detail || 'Failed to validate import file')
      }

      return response.json()
    },

    /**
     * Download CSV/Excel template for patient import
     */
    downloadTemplate: async (format: 'csv' | 'xlsx' = 'csv'): Promise<Blob> => {
      const response = await fetch(
        `${client.getBaseURL()}/api/v2/patients/import/template?format=${format}`,
        {
          method: 'GET',
          headers: {
            ...client.getSessionHeaders(),
          },
          credentials: 'include'
        }
      )

      if (!response.ok) {
        throw new Error('Failed to download template')
      }

      return response.blob()
    },

    /**
     * Get import history
     */
    getImportHistory: async (filters?: {
      userId?: string;
      status?: 'pending' | 'processing' | 'completed' | 'failed';
      startDate?: string;
      endDate?: string;
      page?: number;
      size?: number;
    }): Promise<{
      items: Array<{
        id: string;
        userId: string;
        userName: string;
        filename: string;
        format: 'csv' | 'xlsx';
        status: 'pending' | 'processing' | 'completed' | 'failed';
        totalRows: number;
        successfulRows: number;
        failedRows: number;
        skippedRows: number;
        startedAt: string;
        completedAt?: string;
        duration?: number;
      }>;
      total: number;
      page: number;
      size: number;
      pages: number;
    }> => {
      const params: Record<string, string | number> = {}
      if (filters?.userId) params['user_id'] = filters.userId
      if (filters?.status) params['status'] = filters.status
      if (filters?.startDate) params['start_date'] = filters.startDate
      if (filters?.endDate) params['end_date'] = filters.endDate
      if (filters?.page) params['page'] = filters.page
      if (filters?.size) params['size'] = filters.size

      return client.get('/api/v2/patients/import/history/', params)
    }
  }
}

// Export types
export type PatientsApi = ReturnType<typeof createPatientsApi>
