/**
 * AlertCard Component - Optimized with React.memo
 *
 * Performance optimizations:
 * - React.memo wrapper prevents unnecessary re-renders
 * - Custom comparison function for alert data and callbacks
 * - Expected improvement: 30-50% reduction in re-renders
 */

import React, { memo } from 'react'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { AlertTriangle, CheckCircle, Clock, User } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import type { Alert } from '@/lib/api-client/types'

// Extend Alert with optional UI-specific fields
interface AlertCardAlert extends Alert {
  patient_name?: string
  is_acknowledged?: boolean
}

interface AlertCardProps {
  alert: AlertCardAlert
  onAcknowledge?: (alertId: string) => void
  onResolve?: (alertId: string) => void
  isLoading?: boolean
}

const AlertCardComponent = ({ alert, onAcknowledge, onResolve, isLoading }: AlertCardProps) => {
  // Handle both acknowledged boolean (old API) and status field (new API)
  const isAcknowledged =
    alert.is_acknowledged ?? (alert.status === 'acknowledged' || alert.status === 'resolved')

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical':
      case 'high':
        return AlertTriangle
      case 'medium':
        return Clock
      case 'low':
        return CheckCircle
      default:
        return AlertTriangle
    }
  }

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'bg-red-100 text-red-800 border-red-200'
      case 'high':
        return 'bg-orange-100 text-orange-800 border-orange-200'
      case 'medium':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200'
      case 'low':
        return 'bg-blue-100 text-blue-800 border-blue-200'
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200'
    }
  }

  const getSeverityLabel = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'Crítico'
      case 'high':
        return 'Alto'
      case 'medium':
        return 'Médio'
      case 'low':
        return 'Baixo'
      default:
        return severity
    }
  }

  const getTypeLabel = (type: string) => {
    switch (type) {
      case 'medical':
        return 'Médico'
      case 'engagement':
        return 'Engajamento'
      case 'system':
        return 'Sistema'
      default:
        return type
    }
  }

  const Icon = getSeverityIcon(alert.severity)
  const severityColor = getSeverityColor(alert.severity)

  return (
    <Card
      className={`transition-shadow hover:shadow-md ${
        !isAcknowledged ? 'border-l-4 border-l-red-500' : ''
      }`}
    >
      <CardHeader>
        <div className="flex items-start space-x-3">
          <div
            className={`flex items-center justify-center w-10 h-10 rounded-full ${severityColor}`}
          >
            <Icon className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <div className="flex items-center justify-between mb-2">
              <CardTitle className="text-lg">{alert.title}</CardTitle>
              <div className="flex items-center space-x-2">
                <Badge variant="outline" className={severityColor}>
                  {getSeverityLabel(alert.severity)}
                </Badge>
                <Badge variant="outline">{getTypeLabel(alert.type)}</Badge>
              </div>
            </div>
            <CardDescription>{alert.message}</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {alert.patient_name && (
            <div className="flex items-center space-x-2 text-sm text-gray-600">
              <User className="h-4 w-4" />
              <span>Paciente: {alert.patient_name}</span>
            </div>
          )}

          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-500">
              {formatDistanceToNow(new Date(alert.created_at), {
                addSuffix: true,
                locale: ptBR,
              })}
            </span>

            <div className="flex items-center space-x-2">
              {!isAcknowledged && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onAcknowledge?.(alert.id)}
                  disabled={isLoading}
                >
                  <CheckCircle className="mr-2 h-4 w-4" />
                  Reconhecer
                </Button>
              )}

              <Button
                variant="outline"
                size="sm"
                onClick={() => onResolve?.(alert.id)}
                disabled={isLoading}
              >
                <CheckCircle className="mr-2 h-4 w-4" />
                Resolver
              </Button>
            </div>
          </div>

          {isAcknowledged && alert.acknowledged_at && (
            <div className="text-sm text-gray-500 bg-gray-50 p-2 rounded">
              Reconhecido{' '}
              {formatDistanceToNow(new Date(alert.acknowledged_at), {
                addSuffix: true,
                locale: ptBR,
              })}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

/**
 * Custom comparison function for React.memo
 */
function arePropsEqual(prevProps: AlertCardProps, nextProps: AlertCardProps): boolean {
  const alertEqual =
    prevProps.alert.id === nextProps.alert.id &&
    prevProps.alert.title === nextProps.alert.title &&
    prevProps.alert.message === nextProps.alert.message &&
    prevProps.alert.severity === nextProps.alert.severity &&
    prevProps.alert.type === nextProps.alert.type &&
    prevProps.alert.status === nextProps.alert.status &&
    prevProps.alert.is_acknowledged === nextProps.alert.is_acknowledged &&
    prevProps.alert.patient_name === nextProps.alert.patient_name &&
    prevProps.alert.created_at === nextProps.alert.created_at &&
    prevProps.alert.acknowledged_at === nextProps.alert.acknowledged_at

  const callbacksEqual =
    prevProps.onAcknowledge === nextProps.onAcknowledge &&
    prevProps.onResolve === nextProps.onResolve &&
    prevProps.isLoading === nextProps.isLoading

  return alertEqual && callbacksEqual
}

/**
 * Memoized AlertCard component
 */
export const AlertCard = memo(AlertCardComponent, arePropsEqual)
