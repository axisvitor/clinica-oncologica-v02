import React, { useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Separator } from '@/components/ui/separator'
import { QuickStats } from '@/components/dashboard/QuickStats'
import { AlertsPanel } from '@/components/dashboard/AlertsPanel'
import { RecentActivity } from '@/components/dashboard/RecentActivity'
import { EngagementChart } from '@/components/dashboard/EngagementChart'
import { MetricCard } from '@/components/dashboard/MetricCard'
import { useSystemNotifications, usePatientUpdates } from '@/hooks/useWebSocket'
import { ConnectionStatus, DashboardSkeleton } from '@/components/common/LoadingStates'
import { useToast } from '@/hooks/use-toast'
import { apiClient } from '@/lib/api-client'
import {
  Activity,
  Users,
  MessageSquare,
  AlertTriangle,
  TrendingUp,
  Calendar,
  Clock,
  Target,
  Zap,
  RefreshCw,
  Bell,
  BellOff,
  Settings
} from 'lucide-react'

interface DashboardData {
  overview: {
    totalPatients: number
    activePatients: number
    totalMessages: number
    messagesThisWeek: number
    responseRate: number
    averageEngagement: number
  }
  analytics: {
    patientsGrowth: number
    messagesGrowth: number
    engagementTrend: number
    newThisWeek: number
  }
  alerts: any[]
  recentActivity: any[]
  upcomingTasks: any[]
}

interface ChartData {
  date: string
  messages_sent: number
  responses_received: number
  response_rate: number
}

export function EnhancedDashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date())
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [refreshInterval, setRefreshInterval] = useState(30000) // 30 seconds

  const { toast } = useToast()
  const { isConnected: systemConnected, notifications } = useSystemNotifications()
  const { isConnected: patientConnected, updates } = usePatientUpdates()

  const fetchDashboardData = async () => {
    try {
      const [overview, analytics, alerts, activity] = await Promise.all([
        apiClient.analytics.dashboard(),
        apiClient.analytics.engagement({ start_date: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString() }),
        apiClient.alerts.list({ page: 1, size: 10 }),
        apiClient.patients.list({ page: 1, size: 5 })
      ])

      setData({
        overview: {
          totalPatients: overview.totalPatients || 0,
          activePatients: overview.activePatients || 0,
          totalMessages: overview.totalMessages || 0,
          messagesThisWeek: overview.messagesThisWeek || 0,
          responseRate: overview.responseRate || 0,
          averageEngagement: overview.averageEngagement || 0
        },
        analytics: {
          patientsGrowth: analytics.patientsGrowth || 0,
          messagesGrowth: analytics.messagesGrowth || 0,
          engagementTrend: analytics.engagementTrend || 0,
          newThisWeek: analytics.newThisWeek || 0
        },
        alerts: alerts.items || [],
        recentActivity: activity.items || [],
        upcomingTasks: overview.upcomingTasks || []
      })

      setLastUpdate(new Date())
    } catch (error: any) {
      console.error('Failed to fetch dashboard data:', error)
      toast({
        title: "Erro ao carregar dashboard",
        description: error.message || "Não foi possível carregar os dados do dashboard",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  // Initial data fetch
  useEffect(() => {
    fetchDashboardData()
  }, [])

  // Auto-refresh functionality
  useEffect(() => {
    if (!autoRefresh) return

    const interval = setInterval(() => {
      if (document.visibilityState === 'visible') {
        fetchDashboardData()
      }
    }, refreshInterval)

    return () => clearInterval(interval)
  }, [autoRefresh, refreshInterval])

  // Handle real-time updates
  useEffect(() => {
    if (updates.length > 0) {
      const latestUpdate = updates[0]
      if (latestUpdate && latestUpdate.type === 'dashboard_update') {
        // Update specific metrics based on real-time data
        setData(prev => prev ? {
          ...prev,
          overview: {
            ...prev.overview,
            ...latestUpdate.data?.overview
          }
        } : null)
      }
    }
  }, [updates])

  // Handle system notifications
  useEffect(() => {
    if (notifications.length > 0) {
      const latestNotification = notifications[0]
      if (latestNotification && !latestNotification.read) {
        toast({
          title: latestNotification.title,
          description: latestNotification.message,
          variant: latestNotification.type === 'error' ? 'destructive' : 'default'
        })
      }
    }
  }, [notifications, toast])

  const handleRefresh = () => {
    setLoading(true)
    fetchDashboardData()
  }

  const toggleAutoRefresh = () => {
    setAutoRefresh(!autoRefresh)
    toast({
      title: autoRefresh ? "Auto-atualização desativada" : "Auto-atualização ativada",
      description: autoRefresh
        ? "O dashboard não será mais atualizado automaticamente"
        : `O dashboard será atualizado a cada ${refreshInterval / 1000} segundos`,
      variant: "default"
    })
  }

  if (loading && !data) {
    return <DashboardSkeleton />
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-600">
            Visão geral em tempo real da clínica oncológica
          </p>
        </div>

        <div className="flex items-center gap-3">
          <ConnectionStatus isConnected={systemConnected && patientConnected} />

          <Button
            variant="outline"
            size="sm"
            onClick={toggleAutoRefresh}
            className={`gap-2 ${autoRefresh ? 'text-green-600' : 'text-gray-600'}`}
          >
            {autoRefresh ? <Bell className="h-4 w-4" /> : <BellOff className="h-4 w-4" />}
            Auto-refresh
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={loading}
            className="gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Atualizar
          </Button>
        </div>
      </div>

      {/* System Status Alert */}
      {notifications.length > 0 && notifications[0]?.type === 'system_alert' && (
        <Alert className="border-yellow-200 bg-yellow-50">
          <AlertTriangle className="h-4 w-4 text-yellow-600" />
          <AlertDescription className="text-yellow-800">
            {notifications[0]?.message || 'Sistema com problemas.'}
          </AlertDescription>
        </Alert>
      )}

      {/* Quick Stats */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Total de Pacientes"
          value={data?.overview.totalPatients || 0}
          change={data?.analytics.patientsGrowth || 0}
          icon={Users}
          trend="up"
          description="Total de pacientes cadastrados"
        />

        <MetricCard
          title="Pacientes Ativos"
          value={data?.overview.activePatients || 0}
          change={((data?.overview.activePatients || 0) / (data?.overview.totalPatients || 1)) * 100}
          icon={Activity}
          trend="up"
          description="Pacientes em tratamento ativo"
          format="percentage"
        />

        <MetricCard
          title="Mensagens Esta Semana"
          value={data?.overview.messagesThisWeek || 0}
          change={data?.analytics.messagesGrowth || 0}
          icon={MessageSquare}
          trend="up"
          description="Mensagens enviadas nos últimos 7 dias"
        />

        <MetricCard
          title="Taxa de Resposta"
          value={data?.overview.responseRate || 0}
          change={data?.analytics.engagementTrend || 0}
          icon={Target}
          trend="up"
          description="Porcentagem de pacientes que respondem"
          format="percentage"
        />
      </div>

      {/* Main Content */}
      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview">
            <Activity className="mr-2 h-4 w-4" />
            Visão Geral
          </TabsTrigger>
          <TabsTrigger value="patients">
            <Users className="mr-2 h-4 w-4" />
            Pacientes
          </TabsTrigger>
          <TabsTrigger value="messages">
            <MessageSquare className="mr-2 h-4 w-4" />
            Mensagens
          </TabsTrigger>
          <TabsTrigger value="analytics">
            <TrendingUp className="mr-2 h-4 w-4" />
            Analytics
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-3">
            {/* Alerts */}
            <div className="lg:col-span-1">
              <AlertsPanel alerts={data?.alerts || []} />
            </div>

            {/* Recent Activity */}
            <div className="lg:col-span-2">
              <RecentActivity activities={data?.recentActivity || []} />
            </div>
          </div>

          {/* Engagement Chart */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5" />
                Engajamento dos Pacientes
              </CardTitle>
              <CardDescription>
                Análise de engajamento e resposta dos pacientes nos últimos 30 dias
              </CardDescription>
            </CardHeader>
            <CardContent>
              <EngagementChart data={data?.analytics ? [{
                date: new Date().toISOString(),
                messages_sent: data.analytics.messagesGrowth || 0,
                responses_received: data.analytics.engagementTrend || 0,
                response_rate: data.overview.responseRate || 0
              }] : []} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="patients" className="space-y-6">
          <QuickStats />
        </TabsContent>

        <TabsContent value="messages" className="space-y-6">
          <QuickStats />
        </TabsContent>

        <TabsContent value="analytics" className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Crescimento de Pacientes</CardTitle>
                <CardDescription>
                  Evolução do número de pacientes cadastrados
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-center py-8">
                  <TrendingUp className="h-12 w-12 text-green-500 mx-auto mb-4" />
                  <div className="text-3xl font-bold text-green-600">
                    +{data?.analytics.patientsGrowth || 0}%
                  </div>
                  <p className="text-gray-600">Crescimento esta semana</p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Eficiência de Mensagens</CardTitle>
                <CardDescription>
                  Taxa de sucesso e engajamento das mensagens
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-center py-8">
                  <Zap className="h-12 w-12 text-blue-500 mx-auto mb-4" />
                  <div className="text-3xl font-bold text-blue-600">
                    {data?.overview.averageEngagement || 0}%
                  </div>
                  <p className="text-gray-600">Taxa média de engajamento</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      {/* Footer Info */}
      <Card className="bg-gray-50">
        <CardContent className="pt-6">
          <div className="flex items-center justify-between text-sm text-gray-600">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4" />
                <span>Última atualização: {lastUpdate.toLocaleTimeString('pt-BR')}</span>
              </div>
              <Separator orientation="vertical" className="h-4" />
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4" />
                <span>
                  Status: {systemConnected && patientConnected ? (
                    <Badge variant="default" className="bg-green-100 text-green-800">Online</Badge>
                  ) : (
                    <Badge variant="destructive">Offline</Badge>
                  )}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {autoRefresh && (
                <>
                  <span>Próxima atualização em {refreshInterval / 1000}s</span>
                  <Separator orientation="vertical" className="h-4" />
                </>
              )}
              <Button variant="ghost" size="sm" className="gap-2">
                <Settings className="h-4 w-4" />
                Configurar
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}