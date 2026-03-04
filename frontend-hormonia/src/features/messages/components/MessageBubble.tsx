/**
 * MessageBubble Component - Individual message display
 *
 * Renders message content with timestamp, status indicators, and retry button
 */

import React from 'react'
import { Check, CheckCheck, Clock, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { formatTime } from '../utils/messageFormatters'
import type { Message } from '../hooks/useMessageGroups'
import type { UseMutationResult } from '@tanstack/react-query'

interface MessageBubbleProps {
  message: Message
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  retryMutation: UseMutationResult<any, unknown, string, unknown>
}

/**
 * Get status icon for outbound messages
 */
const getMessageStatusIcon = (status: string) => {
  switch (status) {
    case 'sent':
      return <Check className="h-3 w-3" />
    case 'delivered':
      return <CheckCheck className="h-3 w-3" />
    case 'read':
      return <CheckCheck className="h-3 w-3 text-blue-400" />
    case 'failed':
      return <span className="text-red-400 text-xs">!</span>
    case 'pending':
      return <Clock className="h-3 w-3 animate-pulse" />
    default:
      return null
  }
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message, retryMutation }) => {
  const isOutbound = message.direction === 'outbound'
  const isFailed = message.status === 'failed'

  return (
    <div
      className={`max-w-xs lg:max-w-md px-4 py-2.5 rounded-2xl shadow-sm ${
        isOutbound
          ? 'bg-blue-600 text-white rounded-br-sm'
          : 'bg-gray-100 text-gray-900 rounded-bl-sm'
      }`}
    >
      <p className="text-sm leading-relaxed break-words">{message.content}</p>

      <div className="flex items-center justify-end mt-1.5 space-x-1">
        <span className={`text-xs ${isOutbound ? 'text-white/80' : 'text-gray-500'}`}>
          {formatTime(message.created_at)}
        </span>

        {isOutbound && (
          <div className="flex items-center space-x-1">
            {getMessageStatusIcon(message.status)}

            {isFailed && (
              <Button
                variant="ghost"
                size="sm"
                className="h-5 w-5 p-0 text-white hover:bg-blue-700 ml-1"
                onClick={() => retryMutation.mutate(message.id)}
                disabled={retryMutation.isPending}
                title="Reenviar mensagem"
              >
                <RefreshCw className="h-3 w-3" />
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
