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

export interface Patient {
  id: string
  name: string
  email?: string
  phone?: string
  cpf?: string
  birth_date?: string
  treatment_type?: string
  treatment_start_date?: string
  doctor_notes?: string
  diagnosis?: string
  treatment_phase?: string
  gender?: 'M' | 'F' | 'other'
  address?: {
    street?: string
    number?: string
    complement?: string
    neighborhood?: string
    city?: string
    state?: string
    zip_code?: string
  }
  medical_info?: {
    diagnosis?: string
    treatment_start_date?: string
    allergies?: string[]
    medications?: string[]
    notes?: string
  }
  status?: 'active' | 'inactive' | 'archived' | 'paused' | 'completed'
  created_at?: string
  updated_at?: string
  doctor_id?: string
  current_day?: number
  flow_state?: string
}

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

type PatientApiResponse = Patient & { flow_state?: string }

const normalizePatientResponse = (patient: PatientApiResponse): Patient => {
  if (!patient) {
    return patient
  }
  const flowState = patient.flow_state ?? patient.status
  const normalizedStatus = (flowState || patient.status || 'active') as Patient['status']
  return {
    ...patient,
    flow_state: flowState,
    status: normalizedStatus
  }
}

const normalizePatientList = (patients: PatientApiResponse[] = []): Patient[] =>
  patients.map((patient) => normalizePatientResponse(patient))

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
      let rest: Record<string, any> = {}

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

      const res: any = await client.get<any>('/api/v2/patients', query)

      // Normalize to keep backward compatibility with components expecting `items`
      const rawItems = Array.isArray(res?.data) ? res.data : (res?.items ?? [])
      const items = normalizePatientList(rawItems as PatientApiResponse[])
      const total = res?.total ?? res?.total_count ?? items.length ?? 0
      const has_more = res?.has_more ?? (typeof res?.pages === 'number' && page < res.pages)
      const next_cursor = res?.next_cursor ?? null
      const normalized: any = {
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
      const patient = await client.get<PatientApiResponse>(`/api/v2/patients/${patientId}`)
      return normalizePatientResponse(patient)
    },

    /**
     * Create new patient
     */
    create: async (data: PatientCreate): Promise<Patient> => {
      if (!data?.doctor_id) {
        throw new Error('doctor_id is required to create a patient')
      }
      const patient = await client.post<PatientApiResponse>('/api/v2/patients', data)
      return normalizePatientResponse(patient)
    },

    /**
     * Update patient
     */
    update: async (patientId: string, data: PatientUpdate): Promise<Patient> => {
      const patient = await client.patch<PatientApiResponse>(`/api/v2/patients/${patientId}`, data)
      return normalizePatientResponse(patient)
    },

    /**
     * Delete patient (soft delete)
     */
    delete: async (patientId: string): Promise<{ message: string }> => {
      return client.delete<{ message: string }>(`/api/v2/patients/${patientId}`)
    },

    deletePatient: async (patientId: string): Promise<{ message: string }> => {
      return client.delete<{ message: string }>(`/api/v2/patients/${patientId}`)
    },

    activate: async (patientId: string): Promise<Patient> => {
      const patient = await client.post<PatientApiResponse>(`/api/v2/patients/${patientId}/activate`)
      return normalizePatientResponse(patient)
    },

    deactivate: async (patientId: string): Promise<Patient> => {
      const patient = await client.post<PatientApiResponse>(`/api/v2/patients/${patientId}/deactivate`)
      return normalizePatientResponse(patient)
    },

    /**
     * Archive patient
     */
    archive: async (patientId: string): Promise<Patient> => {
      return client.patch<Patient>(`/api/v1/patients/${patientId}/archive`)
    },

    /**
     * Restore archived patient
     */
    restore: async (patientId: string): Promise<Patient> => {
      const patient = await client.post<PatientApiResponse>(`/api/v2/patients/${patientId}/restore`)
      return normalizePatientResponse(patient)
    },

    /**
     * Get patient timeline events
     */
    timeline: async (patientId: string): Promise<{ patient_id: string; events: TimelineEvent[] }> => {
      return client.get<{ patient_id: string; events: TimelineEvent[] }>(`/api/v2/patients/${patientId}/timeline`)
    },

    /**
     * Search patients
     */
    search: async (query: string): Promise<Patient[]> => {
      return client.get<Patient[]>(`/api/v2/patients/search`, { q: query })
    },

    /**
     * Get patient medical history
     */
    getMedicalHistory: async (patientId: string): Promise<PatientMedicalHistory> => {
      return client.get<PatientMedicalHistory>(`/api/v1/patients/${patientId}/medical-history`)
    },

    /**
     * Add medical history entry
     */
    addMedicalHistoryEntry: async (
      patientId: string,
      entry: {
        type: 'consultation' | 'exam' | 'prescription' | 'note'
        title: string
        description?: string
        date?: string
      }
    ): Promise<{ id: string; message: string }> => {
      return client.post(`/api/v1/patients/${patientId}/medical-history`, entry)
    },

    /**
     * Get patient appointments
     */
    getAppointments: async (
      patientId: string,
      filters?: {
        status?: PatientAppointment['status']
        from_date?: string
        to_date?: string
      }
    ): Promise<PatientAppointment[]> => {
      return client.get<PatientAppointment[]>(
        `/api/v1/patients/${patientId}/appointments`,
        filters
      )
    },

    /**
     * Schedule appointment for patient
     */
    scheduleAppointment: async (
      patientId: string,
      data: {
        doctor_id: string
        scheduled_at: string
        duration_minutes?: number
        type?: string
        notes?: string
      }
    ): Promise<PatientAppointment> => {
      return client.post<PatientAppointment>(
        `/api/v1/patients/${patientId}/appointments`,
        data
      )
    },

    /**
     * Get patient documents
     */
    getDocuments: async (patientId: string): Promise<PatientDocument[]> => {
      return client.get<PatientDocument[]>(`/api/v1/patients/${patientId}/documents`)
    },

    /**
     * Upload document for patient
     */
    uploadDocument: async (
      patientId: string,
      file: File,
      metadata?: { name?: string; type?: string }
    ): Promise<PatientDocument> => {
      const formData = new FormData()
      formData.append('file', file)
      if (metadata?.name) formData.append('name', metadata.name)
      if (metadata?.type) formData.append('type', metadata.type)

      const response = await fetch(
        `${client.getBaseURL()}/api/v1/patients/${patientId}/documents`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${client.getAuthToken()}`
          },
          credentials: 'include',
          body: formData
        }
      )

      if (!response.ok) {
        throw new Error('Failed to upload document')
      }

      return response.json()
    },

    /**
     * Delete patient document
     */
    deleteDocument: async (
      patientId: string,
      documentId: string
    ): Promise<{ message: string }> => {
      return client.delete<{ message: string }>(
        `/api/v1/patients/${patientId}/documents/${documentId}`
      )
    },

    /**
     * Get patient statistics
     */
    getStats: async (filters?: {
      doctor_id?: string
      start_date?: string
      end_date?: string
    }): Promise<PatientStats> => {
      return client.get<PatientStats>('/api/v2/patients/stats', filters)
    },

    /**
     * Export patients to CSV
     */
    exportToCsv: async (filters?: PatientFilters): Promise<Blob> => {
      const response = await fetch(
        `${client.getBaseURL()}/api/v1/patients/export?${new URLSearchParams(filters as any)}`,
        {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${client.getAuthToken()}`
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
     * Import patients from CSV
     */
    importFromCsv: async (file: File): Promise<{
      success: number
      failed: number
      errors?: Array<{ row: number; message: string }>
    }> => {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch(
        `${client.getBaseURL()}/api/v1/patients/import`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${client.getAuthToken()}`
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
      return client.get<{ exists: boolean }>('/api/v2/patients/check-email', { email })
    }
  }
}

// Export types
export type PatientsApi = ReturnType<typeof createPatientsApi>
