import React from 'react'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { AlertTriangle, CheckCircle, Clock, User } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

interface Alert {
  id: string
  patient_id?: string
  patient_name?: string
  type: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  title: string
  message: string
  is_acknowledged: boolean
  acknowledged_at?: string
  created_at: string
}

interface AlertCardProps {
  alert: Alert
  onAcknowledge?: (alertId: string) => void
  onResolve?: (alertId: string) => void
  isLoading?: boolean
}

export function AlertCard({ alert, onAcknowledge, onResolve, isLoading }: AlertCardProps) {
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
    <Card className={`transition-all hover:shadow-md ${
      !alert.is_acknowledged ? 'border-l-4 border-l-red-500' : ''
    }`}>
      <CardHeader>
        <div className="flex items-start space-x-3">
          <div className={`flex items-center justify-center w-10 h-10 rounded-full ${severityColor}`}>
            <Icon className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <div className="flex items-center justify-between mb-2">
              <CardTitle className="text-lg">{alert.title}</CardTitle>
              <div className="flex items-center space-x-2">
                <Badge variant="outline" className={severityColor}>
                  {getSeverityLabel(alert.severity)}
                </Badge>
                <Badge variant="outline">
                  {getTypeLabel(alert.type)}
                </Badge>
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
                locale: ptBR
              })}
            </span>
            
            <div className="flex items-center space-x-2">
              {!alert.is_acknowledged && (
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
          
          {alert.is_acknowledged && alert.acknowledged_at && (
            <div className="text-sm text-gray-500 bg-gray-50 p-2 rounded">
              Reconhecido {formatDistanceToNow(new Date(alert.acknowledged_at), {
                addSuffix: true,
                locale: ptBR
              })}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
