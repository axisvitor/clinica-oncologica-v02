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

export interface Patient {
  id: string
  name: string
  email?: string
  phone?: string
  cpf?: string
  birth_date?: string
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
  status?: 'active' | 'inactive' | 'archived'
  created_at?: string
  updated_at?: string
  doctor_id?: string
}

export interface PatientCreate {
  name: string
  email?: string
  phone?: string
  cpf?: string
  birth_date?: string
  gender?: 'M' | 'F' | 'other'
  address?: Patient['address']
  medical_info?: Patient['medical_info']
  doctor_id?: string
}

export interface PatientUpdate extends Partial<PatientCreate> {
  status?: 'active' | 'inactive' | 'archived'
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

/**
 * Patients API methods
 */
export function createPatientsApi(client: ApiClientCore) {
  return {
    /**
     * List patients with pagination and filters
     */
    list: async (
      page: number = 1,
      size: number = 20,
      filters?: PatientFilters
    ): Promise<PaginatedResponse<Patient>> => {
      return client.get<PaginatedResponse<Patient>>('/api/v2/patients', {
        page,
        size,
        ...filters
      })
    },

    /**
     * Get patient by ID
     */
    get: async (patientId: string): Promise<Patient> => {
      return client.get<Patient>(`/api/v2/patients/${patientId}`)
    },

    /**
     * Create new patient
     */
    create: async (data: PatientCreate): Promise<Patient> => {
      return client.post<Patient>('/api/v2/patients', data)
    },

    /**
     * Update patient
     */
    update: async (patientId: string, data: PatientUpdate): Promise<Patient> => {
      return client.patch<Patient>(`/api/v2/patients/${patientId}`, data)
    },

    /**
     * Delete patient (soft delete)
     */
    delete: async (patientId: string): Promise<{ message: string }> => {
      return client.delete<{ message: string }>(`/api/v2/patients/${patientId}`)
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
      return client.patch<Patient>(`/api/v1/patients/${patientId}/restore`)
    },

    /**
     * Search patients
     */
    search: async (query: string): Promise<Patient[]> => {
      return client.get<Patient[]>('/api/v1/patients/search', { q: query })
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
      return client.get<PatientStats>('/api/v1/patients/stats', filters)
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
        '/api/v1/patients/validate-cpf',
        { cpf }
      )
    },

    /**
     * Check if email is already registered
     */
    checkEmailExists: async (email: string): Promise<{ exists: boolean }> => {
      return client.get<{ exists: boolean }>('/api/v1/patients/check-email', { email })
    }
  }
}

// Export types
export type PatientsApi = ReturnType<typeof createPatientsApi>
