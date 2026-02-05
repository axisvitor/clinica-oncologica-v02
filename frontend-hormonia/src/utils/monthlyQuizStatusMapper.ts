/**
 * Monthly Quiz Status Mapper Utility
 *
 * Unifies status values between backend and frontend components.
 * Maps backend status values to consistent UI status values.
 */

import { createLogger } from '../lib/logger'

const logger = createLogger('MonthlyQuizStatusMapper')

export type BackendStatus = 'active' | 'expired' | 'used' | 'cancelled' | string
export type UIStatus = 'active' | 'expired' | 'completed' | 'pending' | 'not_sent' | 'sent' | 'accessed'

/**
 * Maps backend status to UI status following the mapping rules:
 * - active → active
 * - expired → expired
 * - used → completed
 * - cancelled → expired
 *
 * @param status - The backend status value
 * @returns The corresponding UI status value
 */
export function mapBackendStatus(status: string): string {
  if (!status || typeof status !== 'string') {
    return 'pending'
  }

  const normalizedStatus = status.toLowerCase().trim()

  switch (normalizedStatus) {
    case 'active':
      return 'active'
    case 'expired':
      return 'expired'
    case 'used':
      return 'completed'
    case 'cancelled':
      return 'expired'
    case 'completed':
      return 'completed'
    case 'pending':
      return 'pending'
    case 'sent':
      return 'sent'
    case 'accessed':
      return 'accessed'
    case 'not_sent':
      return 'not_sent'
    default:
      // For unknown statuses, return as-is but log for debugging
      logger.warn(`Unknown status received: ${status}. Mapping to 'pending'.`)
      return 'pending'
  }
}

/**
 * Maps UI status back to backend status (reverse mapping)
 * Useful for API calls that require backend status format
 *
 * @param uiStatus - The UI status value
 * @returns The corresponding backend status value
 */
export function mapUIToBackendStatus(uiStatus: string): string {
  if (!uiStatus || typeof uiStatus !== 'string') {
    return 'active'
  }

  const normalizedStatus = uiStatus.toLowerCase().trim()

  switch (normalizedStatus) {
    case 'active':
      return 'active'
    case 'expired':
      return 'expired'
    case 'completed':
      return 'used'
    case 'pending':
      return 'active'
    case 'sent':
      return 'active'
    case 'accessed':
      return 'active'
    case 'not_sent':
      return 'active'
    default:
      return 'active'
  }
}

/**
 * Validates if a status is a valid UI status
 *
 * @param status - The status to validate
 * @returns True if the status is valid
 */
export function isValidUIStatus(status: string): boolean {
  const validStatuses: UIStatus[] = [
    'active',
    'expired',
    'completed',
    'pending',
    'not_sent',
    'sent',
    'accessed'
  ]

  return validStatuses.includes(status as UIStatus)
}

/**
 * Gets a human-readable label for a status
 *
 * @param status - The status value
 * @returns Human-readable label in Portuguese
 */
export function getStatusLabel(status: string): string {
  const mappedStatus = mapBackendStatus(status)

  switch (mappedStatus) {
    case 'active':
      return 'Ativo'
    case 'expired':
      return 'Expirado'
    case 'completed':
      return 'Completado'
    case 'pending':
      return 'Pendente'
    case 'not_sent':
      return 'Não Enviado'
    case 'sent':
      return 'Enviado'
    case 'accessed':
      return 'Acessado'
    default:
      return 'Desconhecido'
  }
}

/**
 * Type guard to check if a value is a valid backend status
 */
export function isBackendStatus(value: unknown): value is BackendStatus {
  return typeof value === 'string' && ['active', 'expired', 'used', 'cancelled'].includes(value.toLowerCase())
}

/**
 * Type guard to check if a value is a valid UI status
 */
export function isUIStatus(value: unknown): value is UIStatus {
  return typeof value === 'string' && isValidUIStatus(value)
}