/**
 * Appointments API Module
 *
 * Handles all appointment-related API calls:
 * - CRUD operations for appointments
 * - Appointment search and filtering
 * - Status management (cancel, complete)
 * - Conflict detection
 * - Date range queries
 */

import type { ApiClientCore, PaginatedResponse } from './core'

/**
 * Appointment status values
 */
export type AppointmentStatus =
  | 'scheduled'
  | 'confirmed'
  | 'in_progress'
  | 'completed'
  | 'cancelled'
  | 'no_show'

/**
 * Appointment type values
 */
export type AppointmentType =
  | 'consultation'
  | 'followup'
  | 'treatment'
  | 'exam'
  | 'emergency'
  | 'telemedicine'

/**
 * Appointment interface
 */
export interface Appointment {
  id: string
  patient_id: string
  practitioner_id?: string | null
  appointment_type: AppointmentType
  status: AppointmentStatus
  scheduled_at?: string
  duration_minutes: number
  cancelled_at?: string | null
  completed_at?: string | null
  pre_appointment_notes?: string | null
  post_appointment_notes?: string | null
  reminder_sent?: boolean
  confirmation_sent?: boolean
  created_at: string
  updated_at: string
  // Eager-loaded relationships (when include param is used)
  patient?: {
    id: string
    name: string
    email?: string
    phone?: string
  }
  practitioner?: {
    id: string
    name: string
    email?: string
  }
}

/**
 * Create appointment request
 */
export interface AppointmentCreate {
  patient_id: string
  practitioner_id?: string
  appointment_type: AppointmentType
  status?: AppointmentStatus
  scheduled_at: string
  duration_minutes?: number
  pre_appointment_notes?: string
}

/**
 * Update appointment request (partial update)
 */
export interface AppointmentUpdate {
  practitioner_id?: string
  appointment_type?: AppointmentType
  status?: AppointmentStatus
  scheduled_at?: string
  duration_minutes?: number
  pre_appointment_notes?: string
  post_appointment_notes?: string
}

/**
 * Appointment filters for list queries
 */
export interface AppointmentFilters {
  search?: string
  patient_id?: string
  practitioner_id?: string
  status?: AppointmentStatus
  appointment_type?: AppointmentType
  date_from?: string
  date_to?: string
  fields?: string[]
  include?: string[]
  cursor?: string
  limit?: number
}

/**
 * Conflict check request
 */
export interface ConflictCheckRequest {
  practitioner_id: string
  scheduled_at: string
  duration_minutes?: number
  exclude_appointment_id?: string
}

/**
 * Conflict check response
 */
export interface ConflictCheckResponse {
  has_conflict: boolean
  conflicting_appointments: Array<{
    id: string
    patient_id: string
    scheduled_at: string
    duration_minutes: number
    status: string
  }>
}

/**
 * Appointments API methods
 */
export function createAppointmentsApi(client: ApiClientCore) {
  return {
    /**
     * List appointments with pagination and filters
     *
     * @param filters - Optional filters for appointments
     * @returns Paginated list of appointments
     *
     * @example
     * ```typescript
     * // List all appointments
     * const appointments = await api.appointments.list()
     *
     * // Filter by patient
     * const patientAppointments = await api.appointments.list({
     *   patient_id: 'patient-123'
     * })
     *
     * // Filter by date range
     * const upcomingAppointments = await api.appointments.list({
     *   date_from: '2025-11-01',
     *   date_to: '2025-11-30',
     *   status: 'scheduled'
     * })
     *
     * // Include related entities
     * const appointmentsWithPatient = await api.appointments.list({
     *   include: ['patient', 'practitioner']
     * })
     * ```
     */
    list: async (
      filters?: AppointmentFilters
    ): Promise<PaginatedResponse<Appointment>> => {
      const { cursor, limit = 20, fields, include, ...otherFilters } = filters || {}

      const params: Record<string, string | number | boolean> = {
        limit,
        ...(cursor ? { cursor } : {}),
        ...otherFilters,
      }

      // Add field selection if provided
      if (fields && fields.length > 0) {
        params['fields'] = fields.join(',')
      }

      // Add eager loading if provided
      if (include && include.length > 0) {
        params['include'] = include.join(',')
      }

      const response = await client.get<{
        data: Appointment[]
        total?: number
        has_more?: boolean
        next_cursor?: string | null
      }>('/api/v2/appointments', params)

      // Normalize response to match PaginatedResponse interface
      const normalized: PaginatedResponse<Appointment> & {
        has_more?: boolean
        next_cursor?: string | null
        data?: Appointment[]
      } = {
        items: response.data || [],
        total: response.total || 0,
        page: 1, // Cursor-based pagination doesn't use page numbers
        size: limit,
        pages: response.total ? Math.ceil(response.total / limit) : 1,
        has_more: response.has_more,
        next_cursor: response.next_cursor,
        data: response.data || [], // V2 compatibility
      }

      return normalized
    },

    /**
     * Get appointment by ID
     *
     * @param appointmentId - The appointment UUID
     * @param options - Optional field selection and eager loading
     * @returns The appointment
     *
     * @example
     * ```typescript
     * // Get appointment
     * const appointment = await api.appointments.get('appointment-123')
     *
     * // Get with related entities
     * const appointmentWithPatient = await api.appointments.get('appointment-123', {
     *   include: ['patient', 'practitioner']
     * })
     * ```
     */
    get: async (
      appointmentId: string,
      options?: { fields?: string[]; include?: string[] }
    ): Promise<Appointment> => {
      const params: Record<string, string> = {}

      if (options?.fields && options.fields.length > 0) {
        params['fields'] = options.fields.join(',')
      }

      if (options?.include && options.include.length > 0) {
        params['include'] = options.include.join(',')
      }

      return client.get<Appointment>(`/api/v2/appointments/${appointmentId}`, params)
    },

    /**
     * Create new appointment
     *
     * @param data - Appointment data
     * @returns The created appointment
     *
     * @example
     * ```typescript
     * const appointment = await api.appointments.create({
     *   patient_id: 'patient-123',
     *   practitioner_id: 'doctor-456',
     *   appointment_type: 'consultation',
     *   scheduled_at: '2025-11-20T10:00:00-03:00',
     *   duration_minutes: 30,
     *   pre_appointment_notes: 'First consultation'
     * })
     * ```
     */
    create: async (data: AppointmentCreate): Promise<Appointment> => {
      return client.post<Appointment>('/api/v2/appointments', data)
    },

    /**
     * Update appointment (partial update)
     *
     * @param appointmentId - The appointment UUID
     * @param data - Partial appointment data to update
     * @returns The updated appointment
     *
     * @example
     * ```typescript
     * // Reschedule appointment
     * const updated = await api.appointments.update('appointment-123', {
     *   scheduled_at: '2025-11-21T14:00:00-03:00'
     * })
     *
     * // Update status
     * const confirmed = await api.appointments.update('appointment-123', {
     *   status: 'confirmed'
     * })
     * ```
     */
    update: async (
      appointmentId: string,
      data: AppointmentUpdate
    ): Promise<Appointment> => {
      return client.patch<Appointment>(`/api/v2/appointments/${appointmentId}`, data)
    },

    /**
     * Delete appointment (soft delete - sets status to cancelled)
     *
     * @param appointmentId - The appointment UUID
     * @returns Success message
     *
     * @example
     * ```typescript
     * await api.appointments.delete('appointment-123')
     * ```
     */
    delete: async (appointmentId: string): Promise<void> => {
      return client.delete<void>(`/api/v2/appointments/${appointmentId}`)
    },

    /**
     * Cancel appointment
     *
     * Sets status to CANCELLED and records cancellation timestamp.
     * Can only cancel appointments in SCHEDULED or CONFIRMED status.
     *
     * @param appointmentId - The appointment UUID
     * @returns The cancelled appointment
     *
     * @example
     * ```typescript
     * const cancelled = await api.appointments.cancel('appointment-123')
     * ```
     */
    cancel: async (appointmentId: string): Promise<Appointment> => {
      return client.patch<Appointment>(`/api/v2/appointments/${appointmentId}/cancel`)
    },

    /**
     * Complete appointment
     *
     * Sets status to COMPLETED and records completion timestamp.
     * Can only complete appointments in IN_PROGRESS status.
     *
     * @param appointmentId - The appointment UUID
     * @param postAppointmentNotes - Optional notes after appointment completion
     * @returns The completed appointment
     *
     * @example
     * ```typescript
     * const completed = await api.appointments.complete('appointment-123', {
     *   post_appointment_notes: 'Patient responded well to treatment'
     * })
     * ```
     */
    complete: async (
      appointmentId: string,
      postAppointmentNotes?: string
    ): Promise<Appointment> => {
      const params = postAppointmentNotes
        ? { post_appointment_notes: postAppointmentNotes }
        : undefined

      return client.patch<Appointment>(
        `/api/v2/appointments/${appointmentId}/complete`,
        undefined,
        params
      )
    },

    /**
     * Check for scheduling conflicts
     *
     * Checks if a practitioner has any appointments that overlap with the
     * specified time window. Useful for preventing double-booking.
     *
     * @param request - Conflict check parameters
     * @returns Conflict information
     *
     * @example
     * ```typescript
     * const conflicts = await api.appointments.checkConflicts({
     *   practitioner_id: 'doctor-456',
     *   scheduled_at: '2025-11-20T10:00:00-03:00',
     *   duration_minutes: 30
     * })
     *
     * if (conflicts.has_conflict) {
     *   console.log('Conflicts found:', conflicts.conflicting_appointments)
     * }
     *
     * // When editing an appointment, exclude it from conflict check
     * const conflicts = await api.appointments.checkConflicts({
     *   practitioner_id: 'doctor-456',
     *   scheduled_at: '2025-11-20T10:00:00-03:00',
     *   duration_minutes: 30,
     *   exclude_appointment_id: 'appointment-123'
     * })
     * ```
     */
    checkConflicts: async (
      request: ConflictCheckRequest
    ): Promise<ConflictCheckResponse> => {
      const {
        practitioner_id,
        scheduled_at,
        duration_minutes = 30,
        exclude_appointment_id
      } = request

      const params: Record<string, string | number> = {
        practitioner_id,
        scheduled_at,
        duration_minutes,
      }

      if (exclude_appointment_id) {
        params['exclude_appointment_id'] = exclude_appointment_id
      }

      return client.get<ConflictCheckResponse>('/api/v2/appointments/conflicts', params)
    },
  }
}

// Export type
export type AppointmentsApi = ReturnType<typeof createAppointmentsApi>
