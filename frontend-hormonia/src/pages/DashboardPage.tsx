import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { Users, MessageSquare, TrendingUp, TriangleAlert as AlertTriangle, Activity, Clock, CircleCheck as CheckCircle, Circle as XCircle, Calendar, FileText } from 'lucide-react'
import { apiClient } from '../lib/api-client'
import { useAuth } from '../contexts/AuthContext'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { LoadingSpinner } from '../components/ui/loading-spinner'
import { MetricCard } from '../components/dashboard/MetricCard'
import { RecentActivity } from '../components/dashboard/RecentActivity'
import { AlertsPanel } from '../components/dashboard/AlertsPanel'
import { EngagementChart } from '../components/dashboard/EngagementChart'
import { QuickStats } from '../components/dashboard/QuickStats'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

export function DashboardPage() {
  const { user, isLoading: authLoading } = useAuth()

  // Wait for authentication to be ready before making API calls
  const { data: metrics, isLoading, error } = useQuery({
    queryKey: ['dashboard-metrics'],
    queryFn: () => apiClient.analytics.dashboard(),
    enabled: !!user && !authLoading, // Only run when authenticated
    refetchInterval: 30000 // Refresh every 30 seconds
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6">
            <div className="text-center">
              <XCircle className="mx-auto h-12 w-12 text-red-500 mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                Erro ao carregar dashboard
              </h3>
              <p className="text-gray-500 mb-4">
                Não foi possível carregar as métricas do dashboard.
              </p>
              <Button onClick={() => window.location.reload()}>
                Tentar novamente
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-4 md:space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold font-heading text-gray-900">Dashboard</h1>
          <p className="text-sm md:text-base text-gray-600 mt-1 font-body">
            Visão geral do sistema
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="bg-green-50 text-green-700">
            Sistema Online
          </Badge>
          <Button variant="outline" size="sm" className="hidden sm:flex">
            <Calendar className="mr-2 h-4 w-4" />
            Hoje
          </Button>
        </div>
      </div>

      {/* Quick Stats */}
      <QuickStats />

      {/* Main Content Tabs */}
      <Tabs defaultValue="overview" className="space-y-4 md:space-y-6">
        <TabsList className="grid w-full grid-cols-2 md:grid-cols-4 gap-1">
          <TabsTrigger value="overview" className="text-xs sm:text-sm">Visão Geral</TabsTrigger>
          <TabsTrigger value="patients" className="text-xs sm:text-sm">Pacientes</TabsTrigger>
          <TabsTrigger value="engagement" className="text-xs sm:text-sm">Engajamento</TabsTrigger>
          <TabsTrigger value="alerts" className="text-xs sm:text-sm">Alertas</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4 md:space-y-6">
          {/* Metrics Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
            <MetricCard
              title="Total de Pacientes"
              value={metrics?.total_patients || 0}
              change={metrics?.patients_change || 0}
              icon={Users}
              trend="up"
            />
            <MetricCard
              title="Mensagens Enviadas"
              value={metrics?.messages_sent || 0}
              change={metrics?.messages_change || 0}
              icon={MessageSquare}
              trend="up"
            />
            <MetricCard
              title="Taxa de Resposta"
              value={`${metrics?.response_rate || 0}%`}
              change={metrics?.response_rate_change || 0}
              icon={TrendingUp}
              trend="up"
            />
            <MetricCard
              title="Alertas Ativos"
              value={metrics?.alerts_pending || 0}
              change={metrics?.alerts_change || 0}
              icon={AlertTriangle}
              trend="down"
              variant="warning"
            />
          </div>

          {/* Charts and Activity */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 md:gap-6">
            <EngagementChart data={metrics?.engagement_chart || []} />
            <RecentActivity activities={metrics?.recent_activity || []} />
          </div>
        </TabsContent>

        <TabsContent value="patients" className="space-y-4 md:space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 md:gap-6">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  Pacientes Ativos
                </CardTitle>
                <Activity className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold font-mono tabular-nums">{metrics?.active_patients || 0}</div>
                <p className="text-xs text-muted-foreground font-body">
                  {metrics?.active_patients_percentage || 0}% do total
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  Questionários Completados
                </CardTitle>
                <CheckCircle className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold font-mono tabular-nums">{metrics?.completed_quizzes || 0}</div>
                <p className="text-xs text-muted-foreground font-body">
                  +{metrics?.quizzes_change || 0} esta semana
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  Tempo Médio de Resposta
                </CardTitle>
                <Clock className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold font-mono tabular-nums">{metrics?.avg_response_time || 0}min</div>
                <p className="text-xs text-muted-foreground font-body">
                  Média dos últimos 7 dias
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Patient Status Distribution */}
          <Card>
            <CardHeader>
              <CardTitle>Distribuição de Status dos Pacientes</CardTitle>
              <CardDescription>
                Visão geral do status atual dos pacientes
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="text-center p-4 border rounded-lg">
                  <div className="text-2xl font-bold font-mono tabular-nums text-green-600">{metrics?.active_patients || 0}</div>
                  <p className="text-sm text-gray-600 font-body">Ativos</p>
                </div>
                <div className="text-center p-4 border rounded-lg">
                  <div className="text-2xl font-bold font-mono tabular-nums text-yellow-600">12</div>
                  <p className="text-sm text-gray-600 font-body">Pausados</p>
                </div>
                <div className="text-center p-4 border rounded-lg">
                  <div className="text-2xl font-bold font-mono tabular-nums text-blue-600">8</div>
                  <p className="text-sm text-gray-600 font-body">Concluídos</p>
                </div>
                <div className="text-center p-4 border rounded-lg">
                  <div className="text-2xl font-bold font-mono tabular-nums text-gray-600">3</div>
                  <p className="text-sm text-gray-600 font-body">Inativos</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="engagement" className="space-y-6">
          <EngagementChart data={metrics?.engagement_chart || []} />
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Métricas de Engajamento</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600 font-body">Taxa de resposta média</span>
                  <span className="font-medium font-mono tabular-nums">{metrics?.response_rate || 0}%</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600 font-body">Mensagens enviadas (7d)</span>
                  <span className="font-medium font-mono tabular-nums">{metrics?.messages_sent || 0}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600 font-body">Tempo médio de resposta</span>
                  <span className="font-medium font-mono tabular-nums">{metrics?.avg_response_time || 0}min</span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Questionários</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600 font-body">Completados esta semana</span>
                  <span className="font-medium font-mono tabular-nums">{metrics?.completed_quizzes || 0}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600 font-body">Em andamento</span>
                  <span className="font-medium font-mono tabular-nums">5</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600 font-body">Taxa de conclusão</span>
                  <span className="font-medium font-mono tabular-nums">85%</span>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="alerts" className="space-y-6">
          <AlertsPanel alerts={metrics?.recent_alerts || []} />
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Alertas por Severidade</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Críticos</span>
                  <Badge variant="destructive">2</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Altos</span>
                  <Badge className="bg-orange-100 text-orange-800">5</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Médios</span>
                  <Badge className="bg-yellow-100 text-yellow-800">12</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Baixos</span>
                  <Badge className="bg-blue-100 text-blue-800">8</Badge>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Alertas por Tipo</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Médicos</span>
                  <span className="font-medium">15</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Engajamento</span>
                  <span className="font-medium">8</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Sistema</span>
                  <span className="font-medium">4</span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Performance</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600 font-body">Tempo médio de resolução</span>
                  <span className="font-medium font-mono tabular-nums">2.5h</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600 font-body">Taxa de resolução</span>
                  <span className="font-medium font-mono tabular-nums">92%</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600 font-body">Alertas resolvidos hoje</span>
                  <span className="font-medium font-mono tabular-nums">18</span>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
