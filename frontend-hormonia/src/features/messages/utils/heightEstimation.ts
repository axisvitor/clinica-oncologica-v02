/**
 * Height Estimation - Calculate virtual scroll heights for messages
 *
 * Provides consistent height estimation for virtual scrolling performance
 */

// Height constants for virtual scrolling
export const HEIGHT_CONSTANTS = {
  DATE_SEPARATOR: 40,
  MESSAGE_BASE: 60, // padding + metadata
  MESSAGE_LINE_HEIGHT: 20,
  CHARS_PER_LINE: 45, // approximate chars that fit in one line
  MIN_MESSAGE_HEIGHT: 80,
  MAX_MESSAGE_HEIGHT: 300,
} as const

/**
 * Estimate message bubble height based on content length
 */
export const estimateMessageHeight = (contentLength: number): number => {
  const estimatedLines = Math.ceil(contentLength / HEIGHT_CONSTANTS.CHARS_PER_LINE)
  const calculatedHeight = HEIGHT_CONSTANTS.MESSAGE_BASE + (estimatedLines * HEIGHT_CONSTANTS.MESSAGE_LINE_HEIGHT)

  // Clamp between min and max
  return Math.min(
    Math.max(calculatedHeight, HEIGHT_CONSTANTS.MIN_MESSAGE_HEIGHT),
    HEIGHT_CONSTANTS.MAX_MESSAGE_HEIGHT
  )
}

/**
 * Get height for date separator
 */
export const getDateSeparatorHeight = (): number => {
  return HEIGHT_CONSTANTS.DATE_SEPARATOR
}
