/**
 * useMessageGroups Hook - Group messages by date
 *
 * Manages message grouping logic with date separators for virtual scrolling
 */

import { useMemo } from 'react'
import { getDateString } from '../utils/messageFormatters'
import type { Message } from '@/lib/api-client/types'

export type { Message }

export interface ListItem {
  type: 'date' | 'message'
  date?: string
  message?: Message
}

/**
 * Hook to group messages by date with separators
 */
export function useMessageGroups(messages: Message[]): ListItem[] {
  return useMemo(() => {
    const result: ListItem[] = []
    let currentDate = ''

    messages.forEach((message) => {
      const messageDate = getDateString(message.created_at)

      // Add date separator when date changes
      if (messageDate !== currentDate) {
        currentDate = messageDate
        result.push({
          type: 'date',
          date: message.created_at,
        })
      }

      // Add message item
      result.push({
        type: 'message',
        message,
      })
    })

    return result
  }, [messages])
}
