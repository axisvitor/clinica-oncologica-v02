import React, { memo, useCallback } from 'react'
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Users,
  MessageSquare,
  AlertTriangle,
  CheckCircle,
} from 'lucide-react'
import type { DashboardMainData } from '@/lib/api-client/dashboard'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

interface QuickStatsProps {
  data?: DashboardMainData | null
  isLoading?: boolean
  error?: unknown
}

// Loading skeleton component for better UX
const QuickStatsLoading = memo(() => (
  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
    {Array.from({ length: 4 }, (_, i) => (
      <Card key={i}>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-4 rounded" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-8 w-16 mb-2" />
          <div className="flex items-center justify-between">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-3 w-12" />
          </div>
        </CardContent>
      </Card>
    ))}
  </div>
))

QuickStatsLoading.displayName = 'QuickStatsLoading'

// Memoized stat card component
const StatCard = memo<{
  title: string
  value: string | number
  change: number
  icon: React.ElementType
  description: string
}>(({ title, value, change, icon: Icon, description }) => {
  const getTrendIcon = useCallback((change: number) => {
    if (change > 0) return TrendingUp
    if (change < 0) return TrendingDown
    return Minus
  }, [])

  const getTrendColor = useCallback((change: number) => {
    if (change > 0) return 'text-green-600'
    if (change < 0) return 'text-red-600'
    return 'text-gray-600'
  }, [])

  const formatChange = useCallback((change: number) => {
    const sign = change >= 0 ? '+' : ''
    return `${sign}${change}%`
  }, [])

  const TrendIcon = getTrendIcon(change)
  const trendColor = getTrendColor(change)

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-gray-600">{title}</CardTitle>
        <Icon className="h-4 w-4 text-gray-400" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold text-gray-900 mb-1">{value}</div>
        <div className="flex items-center justify-between">
          <p className="text-xs text-gray-500">{description}</p>
          {change !== 0 && (
            <div className={`flex items-center space-x-1 ${trendColor}`}>
              <TrendIcon className="h-3 w-3" />
              <span className="text-xs font-medium">{formatChange(change)}</span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
})

StatCard.displayName = 'StatCard'

const QuickStats = memo(({ data, isLoading = false, error }: QuickStatsProps) => {
  const stats = [
    {
      title: 'Pacientes Ativos',
      value: data?.active_patients ?? 0,
      change: data?.patients_change ?? 0,
      icon: Users,
      description: `${data?.active_patients_percentage ?? 0}% do total`,
    },
    {
      title: 'Taxa de Resposta',
      value: `${data?.response_rate ?? 0}%`,
      change: data?.response_rate_change ?? 0,
      icon: MessageSquare,
      description: 'Ultimos 7 dias',
    },
    {
      title: 'Alertas Ativos',
      value: data?.alerts_pending ?? 0,
      change: data?.alerts_change ?? 0,
      icon: AlertTriangle,
      description: 'Requerem atencao',
    },
    {
      title: 'Questionarios',
      value: data?.completed_quizzes ?? 0,
      change: data?.quizzes_change ?? 0,
      icon: CheckCircle,
      description: 'Completados esta semana',
    },
  ]

  // Error state
  if (error) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="col-span-full">
          <CardContent className="pt-6">
            <div className="flex items-center justify-center text-red-600">
              <AlertTriangle className="h-5 w-5 mr-2" />
              <span>Erro ao carregar metricas do dashboard</span>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Loading state with skeleton
  if (isLoading) {
    return <QuickStatsLoading />
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {stats.map((stat) => (
        <StatCard
          key={stat.title}
          title={stat.title}
          value={stat.value}
          change={stat.change}
          icon={stat.icon}
          description={stat.description}
        />
      ))}
    </div>
  )
})

QuickStats.displayName = 'QuickStats'

export default QuickStats
