import React from 'react'
import { Badge } from '@/components/ui/badge'
import { CheckCircle, Clock, X, AlertCircle } from 'lucide-react'

interface StatusBadgeProps {
  status: string
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const statusConfig = {
    connected: { color: 'bg-green-100 text-green-800', icon: CheckCircle },
    connecting: { color: 'bg-yellow-100 text-yellow-800', icon: Clock },
    disconnected: { color: 'bg-gray-100 text-gray-800', icon: X },
    error: { color: 'bg-red-100 text-red-800', icon: AlertCircle },
    pending: { color: 'bg-blue-100 text-blue-800', icon: Clock },
    sent: { color: 'bg-green-100 text-green-800', icon: CheckCircle },
    delivered: { color: 'bg-green-100 text-green-800', icon: CheckCircle },
    read: { color: 'bg-green-100 text-green-800', icon: CheckCircle },
    failed: { color: 'bg-red-100 text-red-800', icon: AlertCircle }
  }

  const config = statusConfig[status as keyof typeof statusConfig]
  if (!config) return <Badge variant="outline">{status}</Badge>

  const Icon = config.icon

  return (
    <Badge className={config.color}>
      <Icon className="w-3 h-3 mr-1" />
      {status}
    </Badge>
  )
}
