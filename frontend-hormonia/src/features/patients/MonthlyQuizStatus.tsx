import React from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { Send, Clock, Eye, CheckCircle, XCircle, RefreshCw } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { mapBackendStatus, getStatusLabel } from '@/utils/monthlyQuizStatusMapper'

export type QuizLinkStatus = 'not_sent' | 'sent' | 'accessed' | 'completed' | 'expired'

export interface MonthlyQuizStatusProps {
  status: QuizLinkStatus | string // Allow backend status values
  lastSent?: Date | string
  accessDate?: Date | string
  completionDate?: Date | string
  expiresAt?: Date | string
  onResend?: () => void
  isResending?: boolean
}

export function MonthlyQuizStatus({
  status,
  lastSent,
  accessDate,
  completionDate,
  expiresAt,
  onResend,
  isResending = false
}: MonthlyQuizStatusProps) {
  // Map backend status to UI status
  const mappedStatus = mapBackendStatus(status)

  const getStatusConfig = () => {
    switch (mappedStatus) {
      case 'not_sent':
        return {
          icon: Send,
          label: 'Não Enviado',
          className: 'bg-gray-100 text-gray-700 border-gray-200',
          iconClassName: 'text-gray-600'
        }
      case 'sent':
        return {
          icon: Clock,
          label: 'Pendente',
          className: 'bg-yellow-100 text-yellow-700 border-yellow-200',
          iconClassName: 'text-yellow-600'
        }
      case 'accessed':
        return {
          icon: Eye,
          label: 'Acessado',
          className: 'bg-blue-100 text-blue-700 border-blue-200',
          iconClassName: 'text-blue-600'
        }
      case 'completed':
        return {
          icon: CheckCircle,
          label: 'Completado',
          className: 'bg-green-100 text-green-700 border-green-200',
          iconClassName: 'text-green-600'
        }
      case 'expired':
        return {
          icon: XCircle,
          label: 'Expirado',
          className: 'bg-red-100 text-red-700 border-red-200',
          iconClassName: 'text-red-600'
        }
      default:
        return {
          icon: Clock,
          label: getStatusLabel(status),
          className: 'bg-gray-100 text-gray-700 border-gray-200',
          iconClassName: 'text-gray-600'
        }
    }
  }

  const config = getStatusConfig()
  const Icon = config.icon

  const formatDate = (date?: Date | string) => {
    if (!date) return 'Não disponível'

    try {
      const dateObj = typeof date === 'string' ? new Date(date) : date
      return formatDistanceToNow(dateObj, {
        addSuffix: true,
        locale: ptBR
      })
    } catch {
      return 'Data inválida'
    }
  }

  const formatExpirationTime = () => {
    if (!expiresAt) return null

    try {
      const now = new Date()
      const expires = typeof expiresAt === 'string' ? new Date(expiresAt) : expiresAt

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

  const canResend = mappedStatus === 'expired' || mappedStatus === 'sent'

  const tooltipContent = (
    <div className="space-y-1.5 text-xs">
      <div>
        <span className="font-semibold">Status:</span> {config.label}
      </div>
      {lastSent && (
        <div>
          <span className="font-semibold">Enviado:</span> {formatDate(lastSent)}
        </div>
      )}
      {accessDate && (
        <div>
          <span className="font-semibold">Acessado:</span> {formatDate(accessDate)}
        </div>
      )}
      {completionDate && (
        <div>
          <span className="font-semibold">Completado:</span> {formatDate(completionDate)}
        </div>
      )}
      {expiresAt && mappedStatus !== 'completed' && (
        <div>
          <span className="font-semibold">Validade:</span> {formatExpirationTime()}
        </div>
      )}
      {canResend && onResend && (
        <div className="pt-1 border-t border-gray-200">
          <span className="text-gray-500">Clique para reenviar</span>
        </div>
      )}
    </div>
  )

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="flex items-center gap-2">
            <Badge className={`${config.className} border cursor-help`}>
              <Icon className={`h-3 w-3 mr-1 ${config.iconClassName}`} />
              {config.label}
            </Badge>
            {canResend && onResend && (
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation()
                  onResend()
                }}
                disabled={isResending}
                className="h-7 px-2"
                aria-label={isResending ? 'Reenviando quiz…' : 'Reenviar quiz'}
              >
                <RefreshCw className={`h-3 w-3 ${isResending ? 'animate-spin' : ''}`} />
              </Button>
            )}
          </div>
        </TooltipTrigger>
        <TooltipContent>
          {tooltipContent}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
