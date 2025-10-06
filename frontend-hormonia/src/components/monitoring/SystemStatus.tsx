import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { CheckCircle, XCircle, AlertCircle, Activity } from 'lucide-react'
import { apiClient } from '@/lib/api-client'

interface HealthCheckResponse {
  status: string
  configured: boolean
  connected: boolean
  realtimeConnected: boolean
  error?: string
}

export function SystemStatus() {
  const { data: status, isLoading } = useQuery<HealthCheckResponse>({
    queryKey: ['system-status'],
    queryFn: async () => {
      const response: any = await apiClient.get('/api/v1/health')
      return response.data as HealthCheckResponse
    },
    refetchInterval: 30000
  })

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5 animate-spin" />
            Status do Sistema
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Verificando status...</p>
        </CardContent>
      </Card>
    )
  }

  const getStatusIcon = (connected: boolean) => {
    return connected ? (
      <CheckCircle className="h-4 w-4 text-green-500" />
    ) : (
      <XCircle className="h-4 w-4 text-red-500" />
    )
  }

  const getStatusBadge = (connected: boolean) => {
    return (
      <Badge variant={connected ? 'default' : 'destructive'}>
        {connected ? 'Online' : 'Offline'}
      </Badge>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Status do Sistema</CardTitle>
        <CardDescription>
          Monitoramento em tempo real dos serviços
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {getStatusIcon(status?.configured || false)}
            <span className="text-sm">Configuração</span>
          </div>
          {getStatusBadge(status?.configured || false)}
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {getStatusIcon(status?.connected || false)}
            <span className="text-sm">Banco de Dados</span>
          </div>
          {getStatusBadge(status?.connected || false)}
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {getStatusIcon(status?.realtimeConnected || false)}
            <span className="text-sm">Real-time</span>
          </div>
          {getStatusBadge(status?.realtimeConnected || false)}
        </div>

        {status?.error && (
          <div className="flex items-start gap-2 p-3 bg-red-50 rounded-lg">
            <AlertCircle className="h-4 w-4 text-red-500 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-red-800">Erro</p>
              <p className="text-xs text-red-600">{status.error}</p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
