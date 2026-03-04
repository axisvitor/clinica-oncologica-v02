/**
 * Medications API Client Module
 *
 * Complete TypeScript client for interacting with the Medications API v2.
 * Supports all 6 backend endpoints with cursor pagination, field selection,
 * and eager loading capabilities.
 *
 * @module lib/api-client/medications
 */

import type { ApiClientCore } from './core'
import type { PaginatedResponse } from './core'

/**
 * Medication route of administration
 */
export type MedicationRoute =
  | 'oral'
  | 'intravenous'
  | 'topical'
  | 'subcutaneous'
  | 'intramuscular'
  | 'inhalation'
  | 'other'

/**
 * Brief patient information for medication response
 */
export interface PatientBrief {
  id: string
  name: string
  email?: string
}

/**
 * Brief prescriber information for medication response
 */
export interface PrescriberBrief {
  id: string
  name: string
  email?: string
}

/**
 * Brief treatment information for medication response
 */
export interface TreatmentBrief {
  id: string
  treatment_type: string
  status: string
  start_date?: string
}

/**
 * Medication schedule configuration
 * Used for tracking medication timing and adherence
 */
export interface MedicationSchedule {
  /** Frequency of medication (e.g., "1x ao dia", "a cada 8 horas") */
  frequency: string
  /** Start date for the medication */
  start_date: string
  /** Optional end date for the medication */
  end_date?: string
  /** Instructions for taking the medication */
  instructions?: string
  /** Time of day to take medication (e.g., ["08:00", "20:00"]) */
  schedule_times?: string[]
}

/**
 * Complete Medication entity
 */
export interface Medication {
  id: string
  patient_id: string
  prescribed_by_id?: string
  treatment_id?: string
  name: string
  active_ingredient?: string
  dosage: string
  frequency: string
  route?: MedicationRoute
  prescription_date: string
  start_date: string
  end_date?: string
  quantity?: number
  refills_allowed: number
  refills_remaining: number
  instructions?: string
  warnings?: string
  side_effects?: string
  is_active: boolean
  discontinued_date?: string
  discontinuation_reason?: string
  created_at: string
  updated_at: string

  // Optional eager-loaded relationships
  patient?: PatientBrief
  prescribed_by?: PrescriberBrief
  treatment?: TreatmentBrief
}

/**
 * Request schema for creating a new medication
 */
export interface MedicationCreate {
  patient_id: string
  prescribed_by_id?: string
  treatment_id?: string
  name: string
  active_ingredient?: string
  dosage: string
  frequency: string
  route?: MedicationRoute
  prescription_date: string
  start_date: string
  end_date?: string
  quantity?: number
  refills_allowed?: number
  refills_remaining?: number
  instructions?: string
  warnings?: string
  side_effects?: string
  is_active?: boolean
  discontinued_date?: string
  discontinuation_reason?: string
}

/**
 * Request schema for updating a medication (partial update)
 */
export interface MedicationUpdate {
  prescribed_by_id?: string
  treatment_id?: string
  name?: string
  active_ingredient?: string
  dosage?: string
  frequency?: string
  route?: MedicationRoute
  prescription_date?: string
  start_date?: string
  end_date?: string
  quantity?: number
  refills_allowed?: number
  refills_remaining?: number
  instructions?: string
  warnings?: string
  side_effects?: string
  is_active?: boolean
  discontinued_date?: string
  discontinuation_reason?: string
}

/**
 * Query filters for listing medications
 */
export interface MedicationFilters {
  /** Search by medication name */
  search?: string
  /** Filter by patient ID */
  patient_id?: string
  /** Filter by prescriber ID */
  prescribed_by_id?: string
  /** Filter by treatment ID */
  treatment_id?: string
  /** Filter by active status */
  is_active?: boolean
  /** Filter by route of administration */
  route?: MedicationRoute
  /** Cursor for pagination */
  cursor?: string
  /** Number of items per page (default: 20) */
  limit?: number
  /** Fields to include in response (e.g., "id,name,dosage") */
  fields?: string
  /** Relationships to eager-load (e.g., "patient,prescribed_by,treatment") */
  include?: string
}

/**
 * Medication statistics response
 */
export interface MedicationStats {
  total_medications: number
  active_medications: number
  discontinued_medications: number
  by_route: Record<string, number>
}

/**
 * Medications API client
 *
 * @example
 * ```typescript
 * // List medications
 * const medications = await apiClient.medications.list({
 *   patient_id: "123",
 *   is_active: true
 * });
 *
 * // Get single medication with relationships
 * const medication = await apiClient.medications.get("med-id", {
 *   include: "patient,prescribed_by"
 * });
 *
 * // Create new medication
 * const newMed = await apiClient.medications.create({
 *   patient_id: "patient-123",
 *   name: "Anastrozol",
 *   dosage: "1mg",
 *   frequency: "1x ao dia",
 *   route: "oral",
 *   prescription_date: "2025-11-07",
 *   start_date: "2025-11-08"
 * });
 *
 * // Update medication
 * const updated = await apiClient.medications.update("med-id", {
 *   dosage: "2mg"
 * });
 *
 * // Discontinue medication
 * const discontinued = await apiClient.medications.discontinue(
 *   "med-id",
 *   "Treatment completed"
 * );
 *
 * // Record refill
 * const refilled = await apiClient.medications.refill("med-id");
 * ```
 */
export class MedicationsApi {
  constructor(private client: ApiClientCore) {}

  /**
   * List medications with cursor-based pagination
   *
   * @param filters - Optional filters for searching and filtering medications
   * @returns Paginated list of medications
   *
   * @example
   * ```typescript
   * // Get all active medications for a patient
   * const medications = await apiClient.medications.list({
   *   patient_id: "patient-123",
   *   is_active: true,
   *   include: "patient,prescribed_by"
   * });
   *
   * // Search medications by name
   * const results = await apiClient.medications.list({
   *   search: "anastrozol"
   * });
   *
   * // Paginate through results
   * const firstPage = await apiClient.medications.list({ limit: 20 });
   * if (firstPage.has_more) {
   *   const secondPage = await apiClient.medications.list({
   *     cursor: firstPage.next_cursor
   *   });
   * }
   * ```
   */
  async list(filters?: MedicationFilters): Promise<PaginatedResponse<Medication>> {
    const params: Record<string, string | number | boolean> = {}

    if (filters?.search) params['search'] = filters.search
    if (filters?.patient_id) params['patient_id'] = filters.patient_id
    if (filters?.prescribed_by_id) params['prescribed_by_id'] = filters.prescribed_by_id
    if (filters?.treatment_id) params['treatment_id'] = filters.treatment_id
    if (filters?.is_active !== undefined) params['is_active'] = filters.is_active
    if (filters?.route) params['route'] = filters.route
    if (filters?.cursor) params['cursor'] = filters.cursor
    if (filters?.limit) params['limit'] = filters.limit
    if (filters?.fields) params['fields'] = filters.fields
    if (filters?.include) params['include'] = filters.include

    const response = await this.client.get<{
      data: Medication[]
      next_cursor?: string
      has_more: boolean
      total?: number
    }>('/api/v2/medications', params)

    return {
      items: response.data || [],
      total: response.total ?? 0,
      page: 1, // Cursor-based pagination doesn't use page numbers
      size: filters?.limit ?? 20,
      pages: 0, // Not applicable for cursor pagination
    }
  }

  /**
   * Get a single medication by ID
   *
   * @param medicationId - The medication UUID
   * @param options - Optional query parameters (fields, include)
   * @returns The medication entity
   *
   * @example
   * ```typescript
   * // Get medication with all fields
   * const medication = await apiClient.medications.get("med-123");
   *
   * // Get medication with specific fields and relationships
   * const medication = await apiClient.medications.get("med-123", {
   *   fields: "id,name,dosage,frequency",
   *   include: "patient,prescribed_by"
   * });
   * ```
   */
  async get(
    medicationId: string,
    options?: { fields?: string; include?: string }
  ): Promise<Medication> {
    const params: Record<string, string> = {}
    if (options?.fields) params['fields'] = options.fields
    if (options?.include) params['include'] = options.include

    return this.client.get<Medication>(
      `/api/v2/medications/${medicationId}`,
      Object.keys(params).length > 0 ? params : undefined
    )
  }

  /**
   * Get all medications for a specific patient
   *
   * @param patientId - The patient UUID
   * @param filters - Optional filters (active status, route, etc.)
   * @returns List of patient medications
   *
   * @example
   * ```typescript
   * // Get all medications for a patient
   * const medications = await apiClient.medications.getByPatient("patient-123");
   *
   * // Get only active medications
   * const activeMeds = await apiClient.medications.getByPatient("patient-123", {
   *   is_active: true
   * });
   * ```
   */
  async getByPatient(
    patientId: string,
    filters?: Omit<MedicationFilters, 'patient_id'>
  ): Promise<Medication[]> {
    const response = await this.list({
      ...filters,
      patient_id: patientId,
    })
    return response.items
  }

  /**
   * Create a new medication
   *
   * @param data - Medication creation data
   * @returns The created medication
   *
   * @example
   * ```typescript
   * const medication = await apiClient.medications.create({
   *   patient_id: "patient-123",
   *   name: "Anastrozol",
   *   active_ingredient: "Anastrozole",
   *   dosage: "1mg",
   *   frequency: "1x ao dia",
   *   route: "oral",
   *   prescription_date: "2025-11-07",
   *   start_date: "2025-11-08",
   *   end_date: "2026-11-08",
   *   refills_allowed: 12,
   *   refills_remaining: 12,
   *   instructions: "Tomar 1 comprimido pela manhã, após o café"
   * });
   * ```
   */
  async create(data: MedicationCreate): Promise<Medication> {
    return this.client.post<Medication>('/api/v2/medications', data)
  }

  /**
   * Update an existing medication (partial update)
   *
   * @param medicationId - The medication UUID
   * @param data - Fields to update
   * @returns The updated medication
   *
   * @example
   * ```typescript
   * // Update dosage
   * const updated = await apiClient.medications.update("med-123", {
   *   dosage: "2mg",
   *   frequency: "2x ao dia"
   * });
   *
   * // Update instructions
   * const updated = await apiClient.medications.update("med-123", {
   *   instructions: "Tomar com alimentos"
   * });
   * ```
   */
  async update(medicationId: string, data: MedicationUpdate): Promise<Medication> {
    return this.client.patch<Medication>(`/api/v2/medications/${medicationId}`, data)
  }

  /**
   * Delete a medication (soft delete)
   *
   * @param medicationId - The medication UUID
   * @returns void
   *
   * @example
   * ```typescript
   * await apiClient.medications.delete("med-123");
   * ```
   */
  async delete(medicationId: string): Promise<void> {
    return this.client.delete<void>(`/api/v2/medications/${medicationId}`)
  }

  /**
   * Discontinue a medication with reason
   *
   * @param medicationId - The medication UUID
   * @param reason - Reason for discontinuation
   * @returns The discontinued medication
   *
   * @example
   * ```typescript
   * const discontinued = await apiClient.medications.discontinue(
   *   "med-123",
   *   "Treatment completed successfully"
   * );
   * ```
   */
  async discontinue(medicationId: string, reason: string): Promise<Medication> {
    return this.client.patch<Medication>(
      `/api/v2/medications/${medicationId}/discontinue`,
      undefined,
      { reason }
    )
  }

  /**
   * Record a medication refill (decreases refills_remaining by 1)
   *
   * @param medicationId - The medication UUID
   * @returns The updated medication
   *
   * @example
   * ```typescript
   * const refilled = await apiClient.medications.refill("med-123");
   * console.log(`Refills remaining: ${refilled.refills_remaining}`);
   * ```
   */
  async refill(medicationId: string): Promise<Medication> {
    return this.client.patch<Medication>(`/api/v2/medications/${medicationId}/refill`)
  }

  /**
   * Get active medications only
   *
   * @param filters - Optional filters (patient_id, etc.)
   * @returns List of active medications
   *
   * @example
   * ```typescript
   * // Get all active medications
   * const activeMeds = await apiClient.medications.getActive();
   *
   * // Get active medications for a patient
   * const patientActiveMeds = await apiClient.medications.getActive({
   *   patient_id: "patient-123"
   * });
   * ```
   */
  async getActive(filters?: MedicationFilters): Promise<Medication[]> {
    const response = await this.client.get<{
      data: Medication[]
      total: number
    }>(
      '/api/v2/medications/active',
      filters as Record<string, string | number | boolean> | undefined
    )

    return response.data || []
  }

  /**
   * Search medications by name
   *
   * @param query - Search query
   * @param limit - Maximum number of results (default: 20, max: 50)
   * @returns List of matching medications
   *
   * @example
   * ```typescript
   * const results = await apiClient.medications.search("anastrozol");
   * const moreResults = await apiClient.medications.search("tamoxifen", 50);
   * ```
   */
  async search(query: string, limit: number = 20): Promise<Medication[]> {
    return this.client.get<Medication[]>('/api/v2/medications/search', {
      q: query,
      limit: Math.min(limit, 50),
    })
  }

  /**
   * Get medication statistics
   *
   * @returns Medication statistics summary
   *
   * @example
   * ```typescript
   * const stats = await apiClient.medications.getStats();
   * console.log(`Total: ${stats.total_medications}`);
   * console.log(`Active: ${stats.active_medications}`);
   * console.log(`By route:`, stats.by_route);
   * ```
   */
  async getStats(): Promise<MedicationStats> {
    return this.client.get<MedicationStats>('/api/v2/medications/stats')
  }

  /**
   * Helper method to create a medication schedule object
   *
   * @param medication - The medication entity
   * @returns Medication schedule configuration
   *
   * @example
   * ```typescript
   * const medication = await apiClient.medications.get("med-123");
   * const schedule = apiClient.medications.createSchedule(medication);
   * console.log(`Take ${schedule.frequency} starting ${schedule.start_date}`);
   * ```
   */
  createSchedule(medication: Medication): MedicationSchedule {
    return {
      frequency: medication.frequency,
      start_date: medication.start_date,
      end_date: medication.end_date,
      instructions: medication.instructions,
    }
  }
}

/**
 * Factory function to create MedicationsApi instance
 *
 * @param client - ApiClientCore instance
 * @returns MedicationsApi instance
 */
export function createMedicationsApi(client: ApiClientCore): MedicationsApi {
  return new MedicationsApi(client)
}
