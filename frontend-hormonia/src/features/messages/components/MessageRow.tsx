/**
 * MessageRow Component - Virtual scroll row renderer
 *
 * Renders either a date separator or message bubble based on item type
 */

import React, { memo } from 'react'
import type { UseMutationResult } from '@tanstack/react-query'
import { DateSeparator } from './DateSeparator'
import { MessageBubble } from './MessageBubble'
import type { ListItem } from '../hooks/useMessageGroups'

export interface MessageRowData {
  items: ListItem[]
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  retryMutation: UseMutationResult<any, unknown, string, unknown>
}

export interface MessageRowProps extends MessageRowData {
  style: React.CSSProperties
  index: number
}

/**
 * Row component for react-window virtual scrolling
 */
export const MessageRow = memo<MessageRowProps>(({
  style,
  index,
  items,
  retryMutation
}) => {
  const item = items[index]

  if (!item) {
    return null
  }

  // Render date separator
  if (item.type === 'date' && item.date) {
    return <DateSeparator date={item.date} style={style} />
  }

  // Render message bubble
  if (item.type === 'message' && item.message) {
    const isOutbound = item.message.direction === 'outbound'

    return (
      <div
        style={style}
        className={`flex px-4 py-1 ${
          isOutbound ? 'justify-end' : 'justify-start'
        }`}
      >
        <MessageBubble
          message={item.message}
          retryMutation={retryMutation}
        />
      </div>
    )
  }

  return null
})

MessageRow.displayName = 'MessageRow'
