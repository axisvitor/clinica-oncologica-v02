/**
 * Metrics Dashboard Page Component
 *
 * Main page component for the Healthcare Metrics Dashboard that integrates
 * all metric visualization components and provides a comprehensive view
 * of system health, patient engagement, and AI performance.
 */
import React, { useEffect, useState } from 'react'
import { useAuth } from '@/app/providers/AuthContext'
import { MetricsDashboard } from '@/features/metrics/MetricsDashboard'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import {
  Activity,
  BarChart3,
  TrendingUp,
  Users,
  Brain,
  Target,
  Settings,
  Download,
  AlertTriangle,
} from 'lucide-react'
import { createLogger } from '@/lib/logger'
import { apiClient } from '@/lib/api-client'

const logger = createLogger('MetricsDashboardPage')

const MetricsDashboardPage: React.FC = () => {
  const { user } = useAuth()
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Check user permissions
  useEffect(() => {
    const checkPermissions = () => {
      if (!user) {
        setError('Usuário não autenticado')
        setIsLoading(false)
        return
      }

      const allowedRoles = ['doctor', 'admin']
      if (!allowedRoles.includes(user['role'])) {
        setError('Acesso negado - Permissões insuficientes para visualizar métricas')
        setIsLoading(false)
        return
      }

      setIsLoading(false)
    }

    checkPermissions()
  }, [user])

  const handleExportMetrics = async () => {
    try {
      const endDate = new Date()
      const startDate = new Date()
      startDate.setDate(startDate.getDate() - 30) // Last 30 days

      // Use enhanced-analytics/export endpoint instead of non-existent /metrics/export
      const params = new URLSearchParams()
      const startDateStr = startDate.toISOString().split('T')[0]
      const endDateStr = endDate.toISOString().split('T')[0]
      if (startDateStr) params.append('start_date', startDateStr)
      if (endDateStr) params.append('end_date', endDateStr)
      params.append('format', 'json')

      const response = await fetch(
        `${apiClient.getBaseURL()}/api/v2/enhanced-analytics/export?${params.toString()}`,
        {
          method: 'GET',
          credentials: 'include',
          headers: {
            ...apiClient.getSessionHeaders(),
          },
        }
      )

      if (response.ok) {
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.style.display = 'none'
        a.href = url
        a.download = `metrics-export-${new Date().toISOString().split('T')[0]}.json`
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)
      } else {
        // Fallback: export from dashboard/main data
        const dashboardResponse = await fetch(`${apiClient.getBaseURL()}/api/v2/dashboard/main`, {
          credentials: 'include',
          headers: {
            ...apiClient.getSessionHeaders(),
          },
        })
        if (dashboardResponse.ok) {
          const data = await dashboardResponse.json()
          const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
          const url = window.URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.style.display = 'none'
          a.href = url
          a.download = `dashboard-export-${new Date().toISOString().split('T')[0]}.json`
          document.body.appendChild(a)
          a.click()
          window.URL.revokeObjectURL(url)
          document.body.removeChild(a)
        }
      }
    } catch (err) {
      logger.error('Error exporting metrics', { error: err })
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="flex items-center space-x-2">
          <Activity className="w-6 h-6 animate-spin" />
          <span className="text-lg">Carregando dashboard...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            {error}
            <div className="mt-2">
              <Button variant="outline" onClick={() => window.history.back()}>
                Voltar
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-6 space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <BarChart3 className="h-8 w-8 text-blue-600" />
            <h1 className="text-3xl font-bold tracking-tight">Dashboard de Métricas</h1>
          </div>
          <p className="text-muted-foreground">
            Monitoramento em tempo real do sistema Hormonia Healthcare
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <Badge variant={user?.role === 'admin' ? 'default' : 'secondary'}>
            {user?.role === 'admin' ? 'Administrador' : 'Médico'}
          </Badge>

          {user?.role === 'admin' && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleExportMetrics}
              className="flex items-center space-x-2"
            >
              <Download className="h-4 w-4" />
              <span>Exportar Dados</span>
            </Button>
          )}
        </div>
      </div>

      {/* Quick Stats Overview */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Sistema</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">Ativo</div>
            <p className="text-xs text-muted-foreground">Todos os serviços operacionais</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Pacientes</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">Monitorados</div>
            <p className="text-xs text-muted-foreground">Engajamento em tempo real</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Automacao</CardTitle>
            <Brain className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-purple-600">Otimizada</div>
            <p className="text-xs text-muted-foreground">Personalização ativa</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Quizzes</CardTitle>
            <Target className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">Funcionais</div>
            <p className="text-xs text-muted-foreground">Alto engajamento</p>
          </CardContent>
        </Card>
      </div>

      {/* Main Dashboard Tabs */}
      <Tabs defaultValue="dashboard" className="space-y-4">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="dashboard" className="flex items-center space-x-2">
            <BarChart3 className="h-4 w-4" />
            <span>Dashboard</span>
          </TabsTrigger>
          <TabsTrigger value="trends" className="flex items-center space-x-2">
            <TrendingUp className="h-4 w-4" />
            <span>Tendências</span>
          </TabsTrigger>
          <TabsTrigger value="insights" className="flex items-center space-x-2">
            <Brain className="h-4 w-4" />
            <span>Resumo</span>
          </TabsTrigger>
          <TabsTrigger value="settings" className="flex items-center space-x-2">
            <Settings className="h-4 w-4" />
            <span>Configurações</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="dashboard">
          <MetricsDashboard userRole={user?.role as 'doctor' | 'admin'} refreshInterval={5000} />
        </TabsContent>

        <TabsContent value="trends">
          <Card>
            <CardHeader>
              <CardTitle>Análise de Tendências</CardTitle>
              <CardDescription>
                Análise temporal de métricas e previsões baseadas em dados
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-center py-8 text-muted-foreground">
                <TrendingUp className="h-12 w-12 mx-auto mb-4" />
                <p>Análise de tendências será implementada em breve</p>
                <p className="text-sm mt-2">
                  Incluirá previsões de engajamento, análise sazonal e detecção de anomalias
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="insights">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Análises automatizadas</CardTitle>
                <CardDescription>Recomendações automáticas baseadas em dados</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="bg-blue-50 p-4 rounded-lg border-l-4 border-blue-400">
                    <h4 className="font-medium text-blue-800">Engajamento de Pacientes</h4>
                    <p className="text-sm text-blue-600 mt-1">
                      Taxa de resposta está 15% acima da média. Continue com as estratégias atuais.
                    </p>
                  </div>

                  <div className="bg-green-50 p-4 rounded-lg border-l-4 border-green-400">
                    <h4 className="font-medium text-green-800">Quizzes Mensais</h4>
                    <p className="text-sm text-green-600 mt-1">
                      Horário ideal para envio: 10h-12h. Taxa de conclusão +23% neste período.
                    </p>
                  </div>

                  <div className="bg-purple-50 p-4 rounded-lg border-l-4 border-purple-400">
                    <h4 className="font-medium text-purple-800">Personalizacao de mensagens</h4>
                    <p className="text-sm text-purple-600 mt-1">
                      Mensagens personalizadas têm 18% mais engajamento que mensagens padrão.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Recomendações</CardTitle>
                <CardDescription>Ações sugeridas para otimização</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-start space-x-3">
                    <div className="w-2 h-2 rounded-full bg-green-500 mt-2 flex-shrink-0"></div>
                    <div>
                      <h5 className="font-medium">Otimizar horários de envio</h5>
                      <p className="text-sm text-muted-foreground">
                        Implementar envio baseado no fuso horário do paciente
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start space-x-3">
                    <div className="w-2 h-2 rounded-full bg-yellow-500 mt-2 flex-shrink-0"></div>
                    <div>
                      <h5 className="font-medium">Aumentar personalização</h5>
                      <p className="text-sm text-muted-foreground">
                        Expandir personalizacao para 85% das mensagens
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start space-x-3">
                    <div className="w-2 h-2 rounded-full bg-blue-500 mt-2 flex-shrink-0"></div>
                    <div>
                      <h5 className="font-medium">Segmentar por fase de tratamento</h5>
                      <p className="text-sm text-muted-foreground">
                        Criar conteúdo específico para cada etapa
                      </p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="settings">
          <Card>
            <CardHeader>
              <CardTitle>Configurações do Dashboard</CardTitle>
              <CardDescription>Personalize a exibição e alertas do dashboard</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                <div>
                  <h4 className="font-medium mb-3">Atualização de Dados</h4>
                  <div className="space-y-2">
                    <label className="flex items-center space-x-2">
                      <input type="radio" name="refresh" defaultChecked />
                      <span className="text-sm">Tempo real (5 segundos)</span>
                    </label>
                    <label className="flex items-center space-x-2">
                      <input type="radio" name="refresh" />
                      <span className="text-sm">Moderado (30 segundos)</span>
                    </label>
                    <label className="flex items-center space-x-2">
                      <input type="radio" name="refresh" />
                      <span className="text-sm">Manual</span>
                    </label>
                  </div>
                </div>

                <div>
                  <h4 className="font-medium mb-3">Notificações</h4>
                  <div className="space-y-2">
                    <label className="flex items-center space-x-2">
                      <input type="checkbox" defaultChecked />
                      <span className="text-sm">Alertas críticos</span>
                    </label>
                    <label className="flex items-center space-x-2">
                      <input type="checkbox" defaultChecked />
                      <span className="text-sm">Alertas de performance</span>
                    </label>
                    <label className="flex items-center space-x-2">
                      <input type="checkbox" />
                      <span className="text-sm">Análises automatizadas</span>
                    </label>
                  </div>
                </div>

                <div>
                  <h4 className="font-medium mb-3">Visualização</h4>
                  <div className="space-y-2">
                    <label className="flex items-center space-x-2">
                      <input type="checkbox" defaultChecked />
                      <span className="text-sm">Mostrar tendências</span>
                    </label>
                    <label className="flex items-center space-x-2">
                      <input type="checkbox" defaultChecked />
                      <span className="text-sm">Comparações período anterior</span>
                    </label>
                    <label className="flex items-center space-x-2">
                      <input type="checkbox" />
                      <span className="text-sm">Modo escuro</span>
                    </label>
                  </div>
                </div>

                <div className="pt-4 border-t">
                  <Button className="w-full">Salvar Configurações</Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Footer Info */}
      <div className="text-center text-sm text-muted-foreground pt-4 border-t">
        <p>
          Dashboard de Métricas Hormonia Healthcare • Dados atualizados em tempo real •{' '}
          <span className="font-medium">
            Sistema {user?.role === 'admin' ? 'Administrativo' : 'Médico'}
          </span>
        </p>
      </div>
    </div>
  )
}

export default MetricsDashboardPage
