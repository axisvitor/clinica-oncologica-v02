/**
 * Patient Data Formatting Utilities
 * Shared formatters for patient information display
 */

import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'

/**
 * Generates initials from a person's full name
 * @param name - Full name of the person
 * @returns Two-letter uppercase initials
 * @example getInitials("João da Silva") // Returns "JS"
 */
export function getInitials(name: string): string {
  return name
    .split(' ')
    .map(n => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

/**
 * Formats a date string to relative time in Portuguese
 * @param lastContact - ISO date string of last contact
 * @returns Formatted relative time or "Nunca" if no contact
 * @example formatLastContact("2024-01-15") // Returns "há 15 dias"
 */
export function formatLastContact(lastContact?: string): string {
  if (!lastContact) return 'Nunca'

  try {
    return formatDistanceToNow(new Date(lastContact), {
      addSuffix: true,
      locale: ptBR
    })
  } catch {
    return 'Data inválida'
  }
}

/**
 * Patient status type definitions
 */
export type PatientStatus = 'active' | 'paused' | 'completed' | 'inactive' | 'cancelled'

/**
 * Status badge configuration for visual representation
 */
export interface StatusBadgeConfig {
  label: string
  className: string
}

/**
 * Maps patient status to badge configuration
 */
export const STATUS_BADGE_MAP: Record<PatientStatus, StatusBadgeConfig> = {
  active: {
    label: 'Ativo',
    className: 'bg-green-100 text-green-800'
  },
  paused: {
    label: 'Pausado',
    className: 'bg-yellow-100 text-yellow-800'
  },
  completed: {
    label: 'Concluído',
    className: 'bg-blue-100 text-blue-800'
  },
  inactive: {
    label: 'Inativo',
    className: 'bg-gray-100 text-gray-800'
  },
  cancelled: {
    label: 'Cancelado',
    className: 'bg-red-100 text-red-800'
  }
}

/**
 * Gets badge configuration for a patient status
 * @param status - Patient status string
 * @returns Status badge configuration
 */
export function getStatusBadgeConfig(status: string): StatusBadgeConfig {
  const config = STATUS_BADGE_MAP[status as PatientStatus]

  if (!config) {
    return {
      label: status,
      className: 'bg-gray-100 text-gray-800'
    }
  }

  return config
}
