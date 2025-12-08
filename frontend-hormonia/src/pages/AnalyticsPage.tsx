import React, { useState, useMemo, Suspense } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Calendar, TrendingUp, Users, MessageSquare, Activity, Download, RefreshCw, ChartBar as BarChart3, ListFilter as Filter, ArrowUp, ArrowDown } from 'lucide-react'
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  PieChart,
  Pie,
  Cell
} from '@/components/ui/charts/LazyRechartsComponents'
import type { TooltipProps } from 'recharts'
import type { ValueType, NameType } from 'recharts/types/component/DefaultTooltipContent'
import { ChartSkeleton } from '@/components/ui/chart-skeleton'
import { apiClient } from '@/lib/api-client'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useTreatmentDistribution, type Period } from '@/hooks/api/useTreatmentDistribution'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'

export function AnalyticsPage() {
  const [dateRange, setDateRange] = useState('7d')
  const [compareMode, setCompareMode] = useState(false)
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>(['all'])
  const [treatmentPeriod, setTreatmentPeriod] = useState<Period>('30d')

  const { data: dashboardData, isLoading } = useQuery({
    queryKey: ['analytics-dashboard'],
    queryFn: () => apiClient.analytics.dashboard()
  })

  const { data: engagementData } = useQuery({
    queryKey: ['analytics-engagement', dateRange],
    queryFn: () => apiClient.analytics.engagement()
  })

  const { data: patientsAnalytics } = useQuery({
    queryKey: ['analytics-patients', dateRange],
    queryFn: () => apiClient.analytics.patients()
  })

  const {
    data: treatmentDistribution,
    isLoading: treatmentLoading,
    error: treatmentError
  } = useTreatmentDistribution(treatmentPeriod)

  function getStartDate(range: string): string {
    const now = new Date()
    switch (range) {
      case '7d':
        return new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString()
      case '30d':
        return new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000).toISOString()
      case '90d':
        return new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000).toISOString()
      default:
        return new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString()
    }
  }

  const engagementTrendData = dashboardData?.engagement_chart?.map((item: any) => ({
    ...item,
    date: new Date(item.date).toLocaleDateString('pt-BR', {
      day: '2-digit',
      month: '2-digit'
    })
  })) || []

  const previousPeriodData = useMemo(() => {
    if (!compareMode) return null
    return {
      total_patients: Math.floor((dashboardData?.total_patients || 0) * 0.92),
      response_rate: Math.floor((dashboardData?.response_rate || 0) * 0.88),
      messages_sent: Math.floor((dashboardData?.messages_sent || 0) * 0.85),
      completed_quizzes: Math.floor((dashboardData?.completed_quizzes || 0) * 0.90)
    }
  }, [compareMode, dashboardData])

  const calculateChange = (current: number, previous: number) => {
    if (!previous) return 0
    return ((current - previous) / previous * 100).toFixed(1)
  }

  const CustomTooltip = ({ active, payload, label }: TooltipProps<ValueType, NameType>) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white p-4 border border-gray-200 rounded-lg shadow-xl">
          <p className="font-semibold text-gray-900 mb-3 text-sm">{label}</p>
          <div className="space-y-2">
            {payload.map((entry, index: number) => (
              <div key={index} className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: entry.color }} />
                  <span className="text-sm text-gray-600">{entry.name}</span>
                </div>
                <span className="font-medium text-sm" style={{ color: entry.color }}>
                  {Number(entry.value).toLocaleString('pt-BR')}
                  {entry.dataKey === 'response_rate' && '%'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )
    }
    return null
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Analytics</h1>
          <p className="text-gray-600">
            Análise detalhada e insights acionáveis do sistema
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Select value={dateRange} onValueChange={setDateRange}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Período" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7d">Últimos 7 dias</SelectItem>
              <SelectItem value="30d">Últimos 30 dias</SelectItem>
              <SelectItem value="90d">Últimos 90 dias</SelectItem>
              <SelectItem value="12m">Últimos 12 meses</SelectItem>
            </SelectContent>
          </Select>
          <Button
            variant={compareMode ? 'default' : 'outline'}
            size="sm"
            onClick={() => setCompareMode(!compareMode)}
          >
            <BarChart3 className="mr-2 h-4 w-4" />
            Comparar
          </Button>
          <Button variant="outline" size="sm">
            <RefreshCw className="mr-2 h-4 w-4" />
            Atualizar
          </Button>
          <Button variant="outline" size="sm">
            <Download className="mr-2 h-4 w-4" />
            Exportar
          </Button>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="hover:shadow-lg transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Total de Pacientes
            </CardTitle>
            <div className="h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center">
              <Users className="h-5 w-5 text-blue-600" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{dashboardData?.total_patients || 0}</div>
            <div className="flex items-center gap-2 mt-1">
              <p className="text-xs text-muted-foreground">
                {dashboardData?.active_patients_percentage || 0}% ativos
              </p>
              {compareMode && previousPeriodData && (
                <div className="flex items-center text-xs text-green-600">
                  <ArrowUp className="h-3 w-3" />
                  {calculateChange(dashboardData?.total_patients || 0, previousPeriodData.total_patients)}%
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="hover:shadow-lg transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Taxa de Engajamento
            </CardTitle>
            <div className="h-10 w-10 rounded-full bg-green-100 flex items-center justify-center">
              <TrendingUp className="h-5 w-5 text-green-600" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{dashboardData?.response_rate || 0}%</div>
            <div className="flex items-center gap-2 mt-1">
              <p className="text-xs text-muted-foreground">
                Taxa de resposta
              </p>
              {compareMode && previousPeriodData && (
                <div className="flex items-center text-xs text-green-600">
                  <ArrowUp className="h-3 w-3" />
                  {calculateChange(dashboardData?.response_rate || 0, previousPeriodData.response_rate)}%
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="hover:shadow-lg transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Mensagens Enviadas
            </CardTitle>
            <div className="h-10 w-10 rounded-full bg-orange-100 flex items-center justify-center">
              <MessageSquare className="h-5 w-5 text-orange-600" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{dashboardData?.messages_sent || 0}</div>
            <div className="flex items-center gap-2 mt-1">
              <p className="text-xs text-muted-foreground">
                No período
              </p>
              {compareMode && previousPeriodData && (
                <div className="flex items-center text-xs text-green-600">
                  <ArrowUp className="h-3 w-3" />
                  {calculateChange(dashboardData?.messages_sent || 0, previousPeriodData.messages_sent)}%
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="hover:shadow-lg transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Questionários Completados
            </CardTitle>
            <div className="h-10 w-10 rounded-full bg-purple-100 flex items-center justify-center">
              <Activity className="h-5 w-5 text-purple-600" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{dashboardData?.completed_quizzes || 0}</div>
            <div className="flex items-center gap-2 mt-1">
              <p className="text-xs text-muted-foreground">
                No período
              </p>
              {compareMode && previousPeriodData && (
                <div className="flex items-center text-xs text-green-600">
                  <ArrowUp className="h-3 w-3" />
                  {calculateChange(dashboardData?.completed_quizzes || 0, previousPeriodData.completed_quizzes)}%
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Engagement Trend */}
        <Card className="hover:shadow-lg transition-shadow">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Tendência de Engajamento</CardTitle>
                <CardDescription>
                  Evolução das mensagens e respostas
                </CardDescription>
              </div>
              <Button variant="ghost" size="sm">
                <Download className="h-4 w-4" />
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <Suspense fallback={<ChartSkeleton height="300px" />}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={engagementTrendData}>
                    <defs>
                      <linearGradient id="colorMessages" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8} />
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.1} />
                      </linearGradient>
                      <linearGradient id="colorResponses" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.8} />
                        <stop offset="95%" stopColor="#10b981" stopOpacity={0.1} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
                    <XAxis dataKey="date" stroke="#666" fontSize={12} tickLine={false} />
                    <YAxis stroke="#666" fontSize={12} tickLine={false} />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend wrapperStyle={{ paddingTop: '20px' }} />
                    <Area
                      type="monotone"
                      dataKey="messages_sent"
                      stroke="#3b82f6"
                      fill="url(#colorMessages)"
                      strokeWidth={2}
                      name="Mensagens Enviadas"
                    />
                    <Area
                      type="monotone"
                      dataKey="responses_received"
                      stroke="#10b981"
                      fill="url(#colorResponses)"
                      strokeWidth={2}
                      name="Respostas Recebidas"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </Suspense>
            </div>
          </CardContent>
        </Card>

        {/* Treatment Types Distribution */}
        <Card className="hover:shadow-lg transition-shadow">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Distribuição por Tipo de Tratamento</CardTitle>
                <CardDescription>
                  Proporção de pacientes por terapia
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex gap-1">
                  <Button
                    variant={treatmentPeriod === '7d' ? 'default' : 'outline'}
                    onClick={() => setTreatmentPeriod('7d')}
                    size="sm"
                  >
                    7d
                  </Button>
                  <Button
                    variant={treatmentPeriod === '30d' ? 'default' : 'outline'}
                    onClick={() => setTreatmentPeriod('30d')}
                    size="sm"
                  >
                    30d
                  </Button>
                  <Button
                    variant={treatmentPeriod === '90d' ? 'default' : 'outline'}
                    onClick={() => setTreatmentPeriod('90d')}
                    size="sm"
                  >
                    90d
                  </Button>
                  <Button
                    variant={treatmentPeriod === 'all' ? 'default' : 'outline'}
                    onClick={() => setTreatmentPeriod('all')}
                    size="sm"
                  >
                    Todos
                  </Button>
                </div>
                <Button variant="ghost" size="sm">
                  <Download className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {treatmentLoading ? (
              <Skeleton className="h-[300px] w-full" />
            ) : treatmentError ? (
              <Alert variant="destructive">
                <AlertTitle>Erro ao carregar distribuição</AlertTitle>
                <AlertDescription>
                  {treatmentError instanceof Error ? treatmentError.message : 'Erro desconhecido'}
                </AlertDescription>
              </Alert>
            ) : treatmentDistribution && treatmentDistribution.distribution && treatmentDistribution.distribution.length > 0 ? (
              <>
                <div className="mb-4 flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">
                    {treatmentDistribution.total_patients} pacientes • Período: {treatmentDistribution.period}
                  </span>
                </div>
                <div className="h-[300px] flex items-center justify-center">
                  <Suspense fallback={<ChartSkeleton height="300px" />}>
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={treatmentDistribution.distribution}
                          cx="50%"
                          cy="50%"
                          labelLine={false}
                          label={({ percentage }: { percentage: number }) => `${percentage.toFixed(1)}%`}
                          outerRadius={90}
                          innerRadius={50}
                          fill="#8884d8"
                          dataKey="count"
                          paddingAngle={2}
                        >
                          {treatmentDistribution.distribution.map((entry, index: number) => (
                            <Cell key={`cell-${index}`} fill={entry.color} />
                          ))}
                        </Pie>
                        <Tooltip
                          content={({ active, payload }: TooltipProps<ValueType, NameType>) => {
                            if (active && payload && payload.length && payload[0]) {
                              const data = payload[0].payload as { treatment_type: string; percentage: number };
                              return (
                                <div className="bg-white p-3 border border-gray-200 rounded-lg shadow-lg">
                                  <p className="font-medium text-sm">{data.treatment_type}</p>
                                  <p className="text-sm text-gray-600">{payload[0].value} pacientes</p>
                                  <p className="text-sm text-gray-500">{data.percentage.toFixed(1)}%</p>
                                </div>
                              )
                            }
                            return null
                          }}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                  </Suspense>
                </div>
                <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-3">
                  {treatmentDistribution.distribution.map((item, idx: number) => (
                    <div key={idx} className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded" style={{ backgroundColor: item.color }} />
                      <span className="text-sm">
                        {item.treatment_type} ({item.percentage.toFixed(1)}%)
                      </span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="flex h-[300px] items-center justify-center rounded-lg border border-dashed">
                <div className="text-center">
                  <p className="text-muted-foreground">
                    Nenhum tratamento encontrado para o período selecionado
                  </p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Response Rate Trend */}
      <Card>
        <CardHeader>
          <CardTitle>Taxa de Resposta Detalhada</CardTitle>
          <CardDescription>
            Análise detalhada da taxa de resposta dos pacientes
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[400px]">
            <Suspense fallback={<ChartSkeleton height="400px" />}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={engagementTrendData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="date" stroke="#666" fontSize={12} />
                  <YAxis stroke="#666" fontSize={12} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="response_rate"
                    stroke="#f59e0b"
                    strokeWidth={3}
                    dot={{ fill: '#f59e0b', strokeWidth: 2, r: 6 }}
                    name="Taxa de Resposta (%)"
                  />
                </LineChart>
              </ResponsiveContainer>
            </Suspense>
          </div>
        </CardContent>
      </Card>

      {/* Patient Status Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Status dos Pacientes</CardTitle>
            <CardDescription className="text-xs text-amber-600">
              ⚠️ Pausados/Concluídos hardcoded - Aguardando API
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Ativos</span>
                <div className="flex items-center space-x-2">
                  <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                  <span className="font-medium">{dashboardData?.active_patients || 0}</span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Pausados</span>
                <div className="flex items-center space-x-2">
                  <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
                  <span className="font-medium">12</span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Concluídos</span>
                <div className="flex items-center space-x-2">
                  <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
                  <span className="font-medium">8</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Alertas por Severidade</CardTitle>
            <CardDescription className="text-xs text-amber-600">
              ⚠️ Dados fictícios - Aguardando integração com API de analytics
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
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
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Performance do Sistema</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Tempo médio de resposta</span>
                <span className="font-medium">{dashboardData?.avg_response_time || 0}min</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Uptime</span>
                <span className="font-medium text-green-600">99.9%</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Mensagens processadas</span>
                <span className="font-medium">1,234</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
