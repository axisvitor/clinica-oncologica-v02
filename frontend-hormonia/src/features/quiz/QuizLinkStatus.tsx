import React from 'react'
import { Badge } from '@/components/ui/badge'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { CircleCheck as CheckCircle2, Clock, Circle as XCircle, Send } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { mapBackendStatus, getStatusLabel } from '@/utils/monthlyQuizStatusMapper'

export interface QuizLinkStatusProps {
  patientId: string
  lastSent?: Date
  lastResponse?: Date
  linkStatus: 'active' | 'expired' | 'completed' | 'pending' | string // Allow backend status values
  expiresAt?: Date
}

export function QuizLinkStatus({
  patientId,
  lastSent,
  lastResponse,
  linkStatus,
  expiresAt
}: QuizLinkStatusProps) {
  // Map backend status to UI status
  const mappedStatus = mapBackendStatus(linkStatus)

  const getStatusConfig = () => {
    switch (mappedStatus) {
      case 'active':
        return {
          icon: Clock,
          label: 'Ativo',
          className: 'bg-blue-100 text-blue-800 border-blue-200',
          iconClassName: 'text-blue-600'
        }
      case 'expired':
        return {
          icon: XCircle,
          label: 'Expirado',
          className: 'bg-red-100 text-red-800 border-red-200',
          iconClassName: 'text-red-600'
        }
      case 'completed':
        return {
          icon: CheckCircle2,
          label: 'Completado',
          className: 'bg-green-100 text-green-800 border-green-200',
          iconClassName: 'text-green-600'
        }
      case 'pending':
        return {
          icon: Send,
          label: 'Pendente',
          className: 'bg-gray-100 text-gray-800 border-gray-200',
          iconClassName: 'text-gray-600'
        }
      default:
        return {
          icon: Clock,
          label: getStatusLabel(linkStatus),
          className: 'bg-gray-100 text-gray-800 border-gray-200',
          iconClassName: 'text-gray-600'
        }
    }
  }

  const config = getStatusConfig()
  const Icon = config.icon

  const formatTimeRemaining = () => {
    if (!expiresAt) return null

    try {
      const now = new Date()
      const expires = new Date(expiresAt)

      if (expires <= now) {
        return 'Expirado'
      }

      return `Expira ${formatDistanceToNow(expires, {
        addSuffix: true,
        locale: ptBR
      })}`
    } catch {
      return 'Data inválida'
    }
  }

  const formatDate = (date?: Date) => {
    if (!date) return 'Nunca'

    try {
      return formatDistanceToNow(new Date(date), {
        addSuffix: true,
        locale: ptBR
      })
    } catch {
      return 'Data inválida'
    }
  }

  const tooltipContent = (
    <div className="space-y-1 text-xs">
      <div>
        <span className="font-semibold">Status:</span> {config.label}
      </div>
      {lastSent && (
        <div>
          <span className="font-semibold">Enviado:</span> {formatDate(lastSent)}
        </div>
      )}
      {lastResponse && (
        <div>
          <span className="font-semibold">Respondido:</span> {formatDate(lastResponse)}
        </div>
      )}
      {mappedStatus === 'active' && expiresAt && (
        <div>
          <span className="font-semibold">Validade:</span> {formatTimeRemaining()}
        </div>
      )}
    </div>
  )

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge className={`${config.className} border cursor-help text-xs`}>
            <Icon className={`h-3 w-3 mr-1 flex-shrink-0 ${config.iconClassName}`} />
            <span className="hidden sm:inline">{config.label}</span>
            <span className="sm:hidden">{config.label.substring(0, 4)}</span>
          </Badge>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-[200px] sm:max-w-xs">
          {tooltipContent}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}