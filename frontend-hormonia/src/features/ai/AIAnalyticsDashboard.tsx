import React, { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Brain,
  TrendingUp,
  MessageSquare,
  Users,
  Target,
  AlertTriangle,
  Lightbulb
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { apiClient } from '../../lib/api-client'
import { AIAnalyticsDashboard as AIAnalyticsData, AIInsight, AIRecommendation, PerformanceTrend, PatientEngagementMetrics } from '@/types/api'
import type { AIInsights, AIRecommendations } from '@/lib/api-client/types'
import { InsightType } from '@/types/api'
import type { Priority } from '@/types/shared'
import { FEATURES } from '../../config'
import { createLogger } from '@/lib/logger'
import { toAnalyticsDashboard } from '@/lib/ai-adapters'

const logger = createLogger('AIAnalyticsDashboard')

interface AIAnalyticsDashboardProps {
  patientId?: string
  timeframe?: 'day' | 'week' | 'month' | 'quarter'
  className?: string
  insights?: AIInsights
  recommendations?: AIRecommendations
}

export function AIAnalyticsDashboard({
  patientId,
  timeframe = 'week',
  className,
  insights,
  recommendations
}: AIAnalyticsDashboardProps) {
  const hasPatient = Boolean(patientId)
  const insightsEnabled = FEATURES.AI_INSIGHTS
  const analyticsEnabled = FEATURES.AI_ANALYTICS
  const canUsePrefetched = hasPatient && Boolean(insights) && insightsEnabled
  const shouldFetch = hasPatient && analyticsEnabled && insightsEnabled && !canUsePrefetched

  const { data: analyticsData, isLoading, error } = useQuery({
    queryKey: ['ai-analytics', patientId, timeframe],
    queryFn: async () => {
      if (!patientId) {
        throw new Error('Missing patientId')
      }
      try {
        const insightsPromise = apiClient.ai.insights(patientId, timeframe)
        const recommendationsPromise = FEATURES.AI_RECOMMENDATIONS
          ? apiClient.ai.recommendations(patientId)
          : Promise.resolve(undefined)
        const [insights, recommendations] = await Promise.all([
          insightsPromise,
          recommendationsPromise
        ])
        return toAnalyticsDashboard(insights, recommendations)
      } catch (error) {
        logger.error('Failed to fetch AI analytics:', error)
        throw error
      }
    },
    staleTime: 300000, // 5 minutes
    refetchInterval: 600000, // 10 minutes
    retry: 2,
    retryDelay: 1000,
    enabled: shouldFetch
  })

  const resolvedData = useMemo(() => {
    if (!hasPatient) {
      return undefined
    }
    if (canUsePrefetched && insights) {
      return toAnalyticsDashboard(insights, recommendations)
    }
    if (!analyticsEnabled) {
      return getMockAnalyticsData()
    }
    return analyticsData
  }, [analyticsData, analyticsEnabled, canUsePrefetched, hasPatient, insights, recommendations])

  const isLoadingState = shouldFetch && isLoading
  const errorState = shouldFetch ? error : null

  if (!hasPatient) {
    return (
      <Card className={className}>
        <CardContent className="pt-6">
          <div className="text-center text-muted-foreground">
            <AlertTriangle className="mx-auto h-8 w-8 mb-2" />
            <p>Selecione um paciente para ver analytics de IA</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!insightsEnabled) {
    return (
      <Card className={className}>
        <CardContent className="pt-6">
          <div className="text-center text-muted-foreground">
            <AlertTriangle className="mx-auto h-8 w-8 mb-2" />
            <p>Análises automatizadas desativadas</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (isLoadingState) {
    return (
      <Card className={className}>
        <CardContent className="pt-6">
          <div className="text-center">
            <LoadingSpinner size="lg" />
            <p className="text-muted-foreground mt-2">Carregando analytics de IA...</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (errorState) {
    return (
      <Card className={className}>
        <CardContent className="pt-6">
          <div className="text-center text-red-500">
            <AlertTriangle className="mx-auto h-8 w-8 mb-2" />
            <p>Erro ao carregar analytics</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!resolvedData) {
    return (
      <Card className={className}>
        <CardContent className="pt-6">
          <div className="text-center text-muted-foreground">
            <AlertTriangle className="mx-auto h-8 w-8 mb-2" />
            <p>Dados de analytics indisponíveis</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  const data = resolvedData as AIAnalyticsData

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Conversas Totais</CardTitle>
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{data.overview.total_conversations}</div>
            <p className="text-xs text-muted-foreground">
              +12% em relação ao período anterior
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Sentimento Médio</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(data.overview.avg_sentiment * 100).toFixed(1)}%
            </div>
            <Progress value={data.overview.avg_sentiment * 100} className="mt-2" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Precisão de Resposta</CardTitle>
            <Target className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(data.overview.response_accuracy * 100).toFixed(1)}%
            </div>
            <p className="text-xs text-muted-foreground">
              {data.overview.response_accuracy > 0.9 ? 'Excelente' : 'Bom'}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Taxa de Transferência</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(data.overview.human_handoff_rate * 100).toFixed(1)}%
            </div>
            <p className="text-xs text-muted-foreground">
              {data.overview.human_handoff_rate < 0.1 ? 'Baixa' : 'Moderada'}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Detailed Analytics */}
      <Tabs defaultValue="insights" className="space-y-4">
        <TabsList>
          <TabsTrigger value="insights">Insights</TabsTrigger>
          <TabsTrigger value="recommendations">Recomendações</TabsTrigger>
          <TabsTrigger value="engagement">Engajamento</TabsTrigger>
          <TabsTrigger value="performance">Performance</TabsTrigger>
        </TabsList>

        <TabsContent value="insights" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Lightbulb className="h-5 w-5" />
                Análises automatizadas
              </CardTitle>
              <CardDescription>
                Padrões e anomalias detectados automaticamente
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {data.insights.map((insight) => (
                  <InsightCard key={insight.id} insight={insight} />
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="recommendations" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Brain className="h-5 w-5" />
                Recomendações de IA
              </CardTitle>
              <CardDescription>
                Sugestões baseadas em análise de dados
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {data.recommendations.map((recommendation) => (
                  <RecommendationCard key={recommendation.id} recommendation={recommendation} />
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="engagement" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Métricas de Engajamento</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {data.engagement_metrics.map((metric) => (
                  <EngagementMetricCard key={metric.patient_id} metric={metric} />
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="performance" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Tendências de Performance</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {data.performance_trends.map((trend) => (
                  <PerformanceTrendCard
                    key={`${trend.patient_id ?? 'patient'}-${trend.date}`}
                    trend={trend}
                  />
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

// Helper Components
function InsightCard({ insight }: { insight: AIInsight }) {
  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical': return 'destructive'
      case 'high': return 'destructive'
      case 'medium': return 'default'
      case 'low': return 'secondary'
      default: return 'secondary'
    }
  }

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'pattern': return <TrendingUp className="h-4 w-4" />
      case 'anomaly': return <AlertTriangle className="h-4 w-4" />
      case 'trend': return <TrendingUp className="h-4 w-4" />
      case 'recommendation': return <Lightbulb className="h-4 w-4" />
      default: return <Brain className="h-4 w-4" />
    }
  }

  return (
    <div className="border rounded-lg p-4 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {getTypeIcon(insight.type)}
          <h4 className="font-medium">{insight.title}</h4>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={getPriorityColor(String(insight.priority)) as 'default' | 'secondary' | 'destructive' | 'outline'}>
            {String(insight.priority)}
          </Badge>
          <Badge variant="outline">
            {Math.round(insight.confidence * 100)}%
          </Badge>
        </div>
      </div>
      <p className="text-sm text-muted-foreground">{insight.description}</p>
      <p className="text-xs text-muted-foreground">
        {new Date(insight.created_at).toLocaleString('pt-BR')}
      </p>
    </div>
  )
}

function RecommendationCard({ recommendation }: { recommendation: AIRecommendation }) {
  return (
    <div className="border rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="font-medium">{recommendation.title}</h4>
        <div className="flex items-center gap-2">
          <Badge variant={recommendation.priority === 'high' ? 'destructive' : 'default'}>
            {recommendation.priority}
          </Badge>
          <Badge variant="outline">
            {Math.round(recommendation.confidence * 100)}%
          </Badge>
        </div>
      </div>
      <p className="text-sm text-muted-foreground">{recommendation.description}</p>
      <p className="text-xs text-muted-foreground italic">{recommendation.rationale}</p>
      <div className="flex flex-wrap gap-2">
        {recommendation.actions.map((action) => (
          <Badge key={action.id} variant="outline" className="text-xs">
            {action.title}
          </Badge>
        ))}
      </div>
    </div>
  )
}

function EngagementMetricCard({ metric }: { metric: PatientEngagementMetrics }) {
  return (
    <div className="border rounded-lg p-4 space-y-2">
      <div className="flex items-center justify-between">
        <h4 className="font-medium">Paciente {metric.patient_id}</h4>
        <Badge variant={metric.engagement_score > 80 ? 'default' : 'secondary'}>
          {metric.engagement_score}/100
        </Badge>
      </div>
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="text-muted-foreground">Taxa de Resposta:</span>
          <span className="ml-2 font-medium">{(metric.response_rate * 100).toFixed(1)}%</span>
        </div>
        <div>
          <span className="text-muted-foreground">Tempo Médio:</span>
          <span className="ml-2 font-medium">{metric.avg_response_time}min</span>
        </div>
      </div>
      <Progress value={metric.engagement_score} className="mt-2" />
    </div>
  )
}

function PerformanceTrendCard({ trend }: { trend: PerformanceTrend }) {
  return (
    <div className="border rounded-lg p-4 space-y-2">
      <div className="flex items-center justify-between">
        <h4 className="font-medium">{new Date(trend.date).toLocaleDateString('pt-BR')}</h4>
        <Badge variant="outline">{trend.conversations} conversas</Badge>
      </div>
      <div className="grid grid-cols-3 gap-4 text-sm">
        <div>
          <span className="text-muted-foreground">Sentimento:</span>
          <span className="ml-2 font-medium">{(trend.avg_sentiment * 100).toFixed(1)}%</span>
        </div>
        <div>
          <span className="text-muted-foreground">Precisão:</span>
          <span className="ml-2 font-medium">{(trend.response_accuracy * 100).toFixed(1)}%</span>
        </div>
        <div>
          <span className="text-muted-foreground">Resolução:</span>
          <span className="ml-2 font-medium">{(trend.resolution_rate * 100).toFixed(1)}%</span>
        </div>
      </div>
    </div>
  )
}

// Mock data for demo
function getMockAnalyticsData(): AIAnalyticsData {
  return {
    overview: {
      total_conversations: 1247,
      avg_sentiment: 0.78,
      response_accuracy: 0.92,
      human_handoff_rate: 0.08
    },
    engagement_metrics: [
      {
        patient_id: 'PAT001',
        response_rate: 0.95,
        avg_response_time: 12,
        sentiment_trend: [],
        engagement_score: 88,
        last_interaction: '2025-01-20T10:30:00-03:00',
        total_interactions: 45
      },
      {
        patient_id: 'PAT002',
        response_rate: 0.82,
        avg_response_time: 18,
        sentiment_trend: [],
        engagement_score: 72,
        last_interaction: '2025-01-20T09:15:00-03:00',
        total_interactions: 32
      }
    ],
    insights: [
      {
        id: 'insight-1',
        type: InsightType.PATTERN,
        title: 'Padrão de Engajamento Matinal',
        description: 'Pacientes respondem 40% mais rápido entre 8h-10h',
        confidence: 0.89,
        priority: 'medium' as Priority,
        metadata: {},
        created_at: '2025-01-20T08:00:00-03:00',

        patient_id: 'all'
      },
      {
        id: 'insight-2',
        type: InsightType.ANOMALY,
        title: 'Queda no Sentimento - Fins de Semana',
        description: 'Sentimento médio cai 15% aos fins de semana',
        confidence: 0.76,
        priority: 'high' as Priority,
        metadata: {},
        created_at: '2025-01-19T16:00:00-03:00',

        patient_id: 'all'
      }
    ],
    recommendations: [
      {
        id: 'rec-1',
        type: 'communication',
        title: 'Otimizar Horário de Envio',
        description: 'Enviar mensagens preferencialmente entre 8h-10h',
        rationale: 'Baseado no padrão de engajamento matinal identificado',
        confidence: 0.89,
        priority: 'medium',
        actions: [
          {
            id: 'action-1',
            type: 'message',
            title: 'Ajustar agendamento',
            description: 'Configurar envios para horário otimizado',
            urgency: 'medium'
          }
        ],
        created_at: '2025-01-20T08:00:00-03:00',
        updated_at: '2025-01-20T08:00:00-03:00',
        patient_id: 'all'
      }
    ],
    performance_trends: [
      {
        patient_id: 'all',
        date: '2025-01-19',
        conversations: 156,
        avg_sentiment: 0.82,
        response_accuracy: 0.94,
        resolution_rate: 0.87
      },
      {
        patient_id: 'all',
        date: '2025-01-18',
        conversations: 142,
        avg_sentiment: 0.79,
        response_accuracy: 0.91,
        resolution_rate: 0.85
      }
    ]
  }
}
