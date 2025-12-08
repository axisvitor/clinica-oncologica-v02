/**
 * DateSeparator Component - Display date divider between message groups
 *
 * Shows formatted date (Hoje, Ontem, or full date) as a centered separator
 */

import React from 'react'
import { formatDateSeparator } from '../utils/messageFormatters'

interface DateSeparatorProps {
  date: string
  style?: React.CSSProperties
}

export const DateSeparator: React.FC<DateSeparatorProps> = ({ date, style }) => {
  return (
    <div style={style} className="flex items-center justify-center py-2">
      <div className="bg-gray-200 text-gray-600 text-xs font-medium px-3 py-1 rounded-full">
        {formatDateSeparator(date)}
      </div>
    </div>
  )
}
