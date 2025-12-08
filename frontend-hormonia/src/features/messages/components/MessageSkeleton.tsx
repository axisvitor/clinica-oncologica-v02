/**
 * MessageSkeleton Component - Loading skeleton for messages
 *
 * Displays skeleton UI while messages are loading
 */

import React from 'react'

export const MessageSkeleton: React.FC = () => {
  return (
    <div className="space-y-4 animate-pulse p-4">
      {/* Inbound message skeleton */}
      <div className="flex justify-start">
        <div className="bg-gray-200 rounded-2xl rounded-bl-sm h-16 w-64" />
      </div>

      {/* Outbound message skeleton */}
      <div className="flex justify-end">
        <div className="bg-blue-200 rounded-2xl rounded-br-sm h-16 w-56" />
      </div>

      {/* Inbound message skeleton */}
      <div className="flex justify-start">
        <div className="bg-gray-200 rounded-2xl rounded-bl-sm h-20 w-72" />
      </div>

      {/* Outbound message skeleton */}
      <div className="flex justify-end">
        <div className="bg-blue-200 rounded-2xl rounded-br-sm h-12 w-48" />
      </div>
    </div>
  )
}
