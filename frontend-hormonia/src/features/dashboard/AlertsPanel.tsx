import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle, Clock, ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { apiClient } from '../../lib/api-client'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import type { Alert } from '@/lib/api-client/types'

type UISeverity = 'low' | 'medium' | 'high' | 'critical'
type UIAlert = {
  id: string
  type: string
  severity: UISeverity
  title: string
  message: string
  patient_name?: string
  is_acknowledged: boolean
  created_at: string
}

// Alert from API client has status instead of acknowledged boolean
type IncomingAlert = UIAlert | (Alert & { patient_name?: string; is_acknowledged?: boolean })

interface AlertsPanelProps {
  alerts?: IncomingAlert[]
}

function normalizeAlert(a: IncomingAlert): UIAlert {
  const inferredSeverity = ((): UISeverity => {
    const t = (a as any).severity || (a as any).type
    if (t === 'critical') return 'critical'
    if (t === 'high') return 'high'
    if (t === 'medium') return 'medium'
    return 'low'
  })()

  return {
    id: (a as any).id,
    type: (a as any).type || 'system',
    severity: (a as any).severity || inferredSeverity,
    title: (a as any).title,
    message: (a as any).message,
    patient_name: (a as any).patient_name,
    is_acknowledged: (a as any).is_acknowledged ?? (a as any).acknowledged ?? false,
    created_at: (a as any).created_at,
  }
}

export function AlertsPanel({ alerts: propAlerts }: AlertsPanelProps) {
  const { data: alertsData, isLoading } = useQuery({
    queryKey: ['alerts', { page: 1, size: 5 }],
    queryFn: () => apiClient.alerts.list({ page: 1, size: 5 }),
    refetchInterval: 30000 // Refresh every 30 seconds
  })

  const alerts: UIAlert[] = (propAlerts || alertsData?.items || []).map(normalizeAlert)

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

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Alertas Ativos</CardTitle>
            <CardDescription>
              Alertas que requerem atenção
            </CardDescription>
          </div>
          <Button variant="outline" size="sm" asChild>
            <Link to="/alerts">
              Ver todos
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <LoadingSpinner size="md" />
          </div>
        ) : alerts.length === 0 ? (
          <div className="text-center py-8">
            <CheckCircle className="mx-auto h-12 w-12 text-green-500 mb-4" />
            <p className="text-gray-500">Nenhum alerta ativo</p>
            <p className="text-sm text-gray-400">
              Todos os alertas foram resolvidos
            </p>
          </div>
        ) : (
          <ScrollArea className="h-[300px]">
            <div className="space-y-3">
              {alerts.map((alert) => {
                const Icon = getSeverityIcon(alert.severity)
                const severityColor = getSeverityColor(alert.severity)

                return (
                  <div
                    key={alert.id}
                    className="flex items-start space-x-3 p-3 rounded-lg border bg-white hover:bg-gray-50 transition-colors"
                  >
                    <div className={`flex items-center justify-center w-8 h-8 rounded-full ${severityColor}`}>
                      <Icon className="w-4 h-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <h4 className="text-sm font-medium text-gray-900 truncate">
                          {alert.title}
                        </h4>
                        <Badge
                          variant="outline"
                          className={`text-xs ${severityColor}`}
                        >
                          {getSeverityLabel(alert.severity)}
                        </Badge>
                      </div>
                      <p className="text-sm text-gray-600 mb-1">
                        {alert.message}
                      </p>
                      {alert.patient_name && (
                        <p className="text-xs text-gray-500">
                          Paciente: {alert.patient_name}
                        </p>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  )
}
