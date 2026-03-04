/**
 * Treatments API Module
 *
 * Handles all treatment-related API calls:
 * - CRUD operations for treatments
 * - Treatment search and filtering
 * - Patient-specific treatment retrieval
 * - Treatment statistics and analytics
 *
 * Backend endpoints (v2):
 * - GET    /api/v2/treatments - List treatments with pagination
 * - GET    /api/v2/treatments/statistics - Get treatment statistics
 * - GET    /api/v2/treatments/{id} - Get treatment by ID
 * - POST   /api/v2/treatments - Create new treatment
 * - PATCH  /api/v2/treatments/{id} - Update treatment
 * - DELETE /api/v2/treatments/{id} - Delete treatment (soft delete)
 * - PATCH  /api/v2/treatments/{id}/activate - Activate treatment
 * - PATCH  /api/v2/treatments/{id}/complete - Complete treatment
 * - PATCH  /api/v2/treatments/{id}/suspend - Suspend treatment
 */

import type { ApiClientCore, PaginatedResponse } from './core'

/**
 * Treatment status enumeration
 */
export type TreatmentStatus = 'planned' | 'active' | 'completed' | 'suspended' | 'cancelled'

/**
 * Treatment type enumeration
 */
export type TreatmentType =
  | 'quimioterapia'
  | 'radioterapia'
  | 'hormonioterapia'
  | 'imunoterapia'
  | 'cirurgia'
  | 'outros'

/**
 * Brief patient information for treatment response
 */
export interface PatientBrief {
  id: string
  name: string
  email?: string
}

/**
 * Brief doctor information for treatment response
 */
export interface DoctorBrief {
  id: string
  name: string
  email?: string
}

/**
 * Brief medication information for treatment response
 */
export interface MedicationBrief {
  id: string
  name: string
  dosage: string
  frequency: string
  is_active: boolean
}

/**
 * Treatment entity
 */
export interface Treatment {
  id: string
  patient_id: string
  doctor_id?: string
  treatment_type: TreatmentType
  status: TreatmentStatus
  start_date?: string
  end_date?: string
  planned_sessions?: string
  completed_sessions?: string
  diagnosis?: string
  protocol?: string
  notes?: string
  is_active: boolean
  created_at: string
  updated_at: string

  // Optional relationships (included based on query params)
  patient?: PatientBrief
  doctor?: DoctorBrief
  medications?: MedicationBrief[]
}

/**
 * Treatment creation request
 */
export interface TreatmentCreate {
  patient_id: string
  doctor_id?: string
  treatment_type: TreatmentType
  status?: TreatmentStatus
  start_date: string // ISO date string (YYYY-MM-DD)
  end_date?: string // ISO date string (YYYY-MM-DD)
  planned_sessions?: string
  completed_sessions?: string
  diagnosis?: string
  protocol?: string
  notes?: string
  is_active?: boolean
}

/**
 * Treatment update request (partial update)
 */
export interface TreatmentUpdate {
  doctor_id?: string
  treatment_type?: TreatmentType
  status?: TreatmentStatus
  start_date?: string // ISO date string (YYYY-MM-DD)
  end_date?: string // ISO date string (YYYY-MM-DD)
  planned_sessions?: string
  completed_sessions?: string
  diagnosis?: string
  protocol?: string
  notes?: string
  is_active?: boolean
}

/**
 * Treatment list filters
 */
export interface TreatmentFilters {
  search?: string
  patient_id?: string
  doctor_id?: string
  treatment_type?: TreatmentType
  status?: TreatmentStatus
  start_date_from?: string // ISO date string
  start_date_to?: string // ISO date string
  fields?: string[] // Field selection
  include?: string[] // Eager loading (patient, doctor, medications)
}

/**
 * Treatment statistics response
 */
export interface TreatmentStats {
  total_treatments: number
  active_treatments: number
  completed_treatments: number
  planned_treatments: number
  by_status: Record<TreatmentStatus, number>
  by_type: Record<TreatmentType, number>
  completion_rate: number
}

/**
 * Treatments API methods
 */
export function createTreatmentsApi(client: ApiClientCore) {
  return {
    /**
     * List treatments with pagination and filters
     *
     * @param pageOrOptions - Page number or filter options with pagination
     * @param size - Page size (default: 20)
     * @param filters - Additional filters
     * @returns Paginated list of treatments
     *
     * @example
     * ```typescript
     * // V1 style (page/size)
     * const page1 = await api.treatments.list(1, 20)
     *
     * // V2 style (cursor pagination)
     * const page2 = await api.treatments.list({
     *   patient_id: 'patient-123',
     *   status: 'active',
     *   include: ['patient', 'medications']
     * })
     *
     * // Field selection
     * const filtered = await api.treatments.list({
     *   fields: ['id', 'treatment_type', 'status'],
     *   include: ['patient']
     * })
     * ```
     */
    list: async (
      pageOrOptions:
        | number
        | (TreatmentFilters & {
            page?: number
            size?: number
            cursor?: string
            limit?: number
          }) = 1,
      size: number = 20,
      filters?: TreatmentFilters
    ): Promise<PaginatedResponse<Treatment>> => {
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
        const {
          page: optPage = 1,
          size: optionSize = 20,
          cursor: optCursor,
          limit: optLimit,
          fields,
          include,
          ...other
        } = pageOrOptions
        page = optPage
        limit = optLimit ?? optionSize ?? 20
        cursor = optCursor

        // Handle field selection and eager loading
        if (fields && fields.length > 0) {
          rest['fields'] = fields.join(',')
        }
        if (include && include.length > 0) {
          rest['include'] = include.join(',')
        }

        rest = { ...rest, ...other }
      }

      const query = {
        limit,
        ...(cursor ? { cursor } : {}),
        ...rest,
      }

      const res = await client.get<{
        data?: Treatment[]
        items?: Treatment[]
        total?: number
        total_count?: number
        pages?: number
        has_more?: boolean
        next_cursor?: string
      }>('/api/v2/treatments', query)

      // Normalize to keep backward compatibility
      const rawItems = Array.isArray(res?.data) ? res.data : (res?.items ?? [])
      const items = rawItems as Treatment[]
      const total = res?.total ?? res?.total_count ?? items.length ?? 0
      const has_more = res?.has_more ?? (typeof res?.pages === 'number' && page < res.pages)
      const next_cursor = res?.next_cursor ?? null

      const normalized: PaginatedResponse<Treatment> & {
        data: Treatment[]
        has_more: boolean
        next_cursor: string | null
      } = {
        items,
        total,
        page,
        size: limit,
        pages: total ? Math.ceil(total / Math.max(1, limit)) : (res?.pages ?? undefined),
        has_more,
        next_cursor,
        data: items,
      }

      return normalized as PaginatedResponse<Treatment>
    },

    /**
     * Get treatment by ID
     *
     * @param treatmentId - Treatment UUID
     * @param options - Field selection and eager loading options
     * @returns Treatment details
     *
     * @example
     * ```typescript
     * // Basic get
     * const treatment = await api.treatments.get('treatment-123')
     *
     * // With relationships
     * const full = await api.treatments.get('treatment-123', {
     *   include: ['patient', 'doctor', 'medications']
     * })
     *
     * // With field selection
     * const minimal = await api.treatments.get('treatment-123', {
     *   fields: ['id', 'treatment_type', 'status']
     * })
     * ```
     */
    get: async (
      treatmentId: string,
      options?: { fields?: string[]; include?: string[] }
    ): Promise<Treatment> => {
      const query: Record<string, string> = {}

      if (options?.fields && options.fields.length > 0) {
        query['fields'] = options.fields.join(',')
      }
      if (options?.include && options.include.length > 0) {
        query['include'] = options.include.join(',')
      }

      return client.get<Treatment>(
        `/api/v2/treatments/${treatmentId}`,
        Object.keys(query).length > 0 ? query : undefined
      )
    },

    /**
     * Get treatments for a specific patient
     *
     * @param patientId - Patient UUID
     * @param options - Additional filter options
     * @returns List of patient treatments
     *
     * @example
     * ```typescript
     * const treatments = await api.treatments.getByPatient('patient-123')
     *
     * // With filters
     * const active = await api.treatments.getByPatient('patient-123', {
     *   status: 'active',
     *   include: ['medications']
     * })
     * ```
     */
    getByPatient: async (patientId: string, options?: TreatmentFilters): Promise<Treatment[]> => {
      const query: Record<string, string | number | boolean> = {
        patient_id: patientId,
      }

      // Add filter options
      if (options) {
        if (options.search) query['search'] = options.search
        if (options.doctor_id) query['doctor_id'] = options.doctor_id
        if (options.treatment_type) query['treatment_type'] = options.treatment_type
        if (options.status) query['status'] = options.status
        if (options.start_date_from) query['start_date_from'] = options.start_date_from
        if (options.start_date_to) query['start_date_to'] = options.start_date_to

        // Convert arrays to comma-separated strings
        if (options.fields && options.fields.length > 0) {
          query['fields'] = options.fields.join(',')
        }
        if (options.include && options.include.length > 0) {
          query['include'] = options.include.join(',')
        }
      }

      const res = await client.get<{ data?: Treatment[]; items?: Treatment[] }>(
        '/api/v2/treatments',
        query
      )
      const items = Array.isArray(res?.data) ? res.data : (res?.items ?? [])
      return items as Treatment[]
    },

    /**
     * Create new treatment
     *
     * @param data - Treatment creation data
     * @returns Created treatment
     *
     * @example
     * ```typescript
     * const treatment = await api.treatments.create({
     *   patient_id: 'patient-123',
     *   treatment_type: 'hormonioterapia',
     *   start_date: '2025-11-10',
     *   diagnosis: 'Câncer de próstata',
     *   protocol: 'ADT (Androgen Deprivation Therapy)'
     * })
     * ```
     */
    create: async (data: TreatmentCreate): Promise<Treatment> => {
      return client.post<Treatment>('/api/v2/treatments', data)
    },

    /**
     * Update treatment (partial update)
     *
     * @param treatmentId - Treatment UUID
     * @param data - Fields to update
     * @returns Updated treatment
     *
     * @example
     * ```typescript
     * const updated = await api.treatments.update('treatment-123', {
     *   status: 'active',
     *   completed_sessions: '3 sessões'
     * })
     * ```
     */
    update: async (treatmentId: string, data: TreatmentUpdate): Promise<Treatment> => {
      return client.patch<Treatment>(`/api/v2/treatments/${treatmentId}`, data)
    },

    /**
     * Delete treatment (soft delete)
     *
     * Sets is_active=False and status=cancelled
     *
     * @param treatmentId - Treatment UUID
     *
     * @example
     * ```typescript
     * await api.treatments.delete('treatment-123')
     * ```
     */
    delete: async (treatmentId: string): Promise<void> => {
      return client.delete<void>(`/api/v2/treatments/${treatmentId}`)
    },

    /**
     * Activate treatment
     *
     * Changes status from PLANNED to ACTIVE
     *
     * @param treatmentId - Treatment UUID
     * @returns Updated treatment
     *
     * @example
     * ```typescript
     * const activated = await api.treatments.activate('treatment-123')
     * ```
     */
    activate: async (treatmentId: string): Promise<Treatment> => {
      return client.patch<Treatment>(`/api/v2/treatments/${treatmentId}/activate`)
    },

    /**
     * Complete treatment
     *
     * Changes status to COMPLETED and sets end_date to today if not set
     *
     * @param treatmentId - Treatment UUID
     * @returns Updated treatment
     *
     * @example
     * ```typescript
     * const completed = await api.treatments.complete('treatment-123')
     * ```
     */
    complete: async (treatmentId: string): Promise<Treatment> => {
      return client.patch<Treatment>(`/api/v2/treatments/${treatmentId}/complete`)
    },

    /**
     * Suspend treatment
     *
     * Changes status to SUSPENDED
     *
     * @param treatmentId - Treatment UUID
     * @returns Updated treatment
     *
     * @example
     * ```typescript
     * const suspended = await api.treatments.suspend('treatment-123')
     * ```
     */
    suspend: async (treatmentId: string): Promise<Treatment> => {
      return client.patch<Treatment>(`/api/v2/treatments/${treatmentId}/suspend`)
    },

    /**
     * Get treatment statistics
     *
     * Returns aggregated statistics including:
     * - Total, active, completed, planned treatments
     * - Breakdown by status and type
     * - Completion rate
     *
     * @returns Treatment statistics
     *
     * @example
     * ```typescript
     * const stats = await api.treatments.getStatistics()
     * console.log(`Active treatments: ${stats.active_treatments}`)
     * console.log(`Completion rate: ${stats.completion_rate}%`)
     * ```
     */
    getStatistics: async (): Promise<TreatmentStats> => {
      return client.get<TreatmentStats>('/api/v2/treatments/statistics')
    },
  }
}

// Export types
export type TreatmentsApi = ReturnType<typeof createTreatmentsApi>
