/**
 * Message Formatters - Utility functions for formatting message data
 *
 * Provides consistent formatting for timestamps, dates, and message status
 */

/**
 * Format timestamp to time string (HH:MM)
 */
export const formatTime = (timestamp: string): string => {
  try {
    return new Date(timestamp).toLocaleTimeString('pt-BR', {
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return ''
  }
}

/**
 * Format date separator (Hoje, Ontem, or full date)
 */
export const formatDateSeparator = (timestamp: string): string => {
  try {
    const date = new Date(timestamp)
    const today = new Date()
    const yesterday = new Date(today)
    yesterday.setDate(yesterday.getDate() - 1)

    if (date.toDateString() === today.toDateString()) {
      return 'Hoje'
    } else if (date.toDateString() === yesterday.toDateString()) {
      return 'Ontem'
    } else {
      return date.toLocaleDateString('pt-BR', {
        day: '2-digit',
        month: 'long',
        year: 'numeric',
      })
    }
  } catch {
    return ''
  }
}

/**
 * Get date string for grouping (YYYY-MM-DD)
 */
export const getDateString = (timestamp: string): string => {
  try {
    return new Date(timestamp).toDateString()
  } catch {
    return ''
  }
}
