import React, { memo, useMemo, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Users,
  MessageSquare,
  AlertTriangle,
  CheckCircle
} from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import { useAuth } from '@/app/providers/AuthContext'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { Skeleton } from '@/components/ui/skeleton'

interface DashboardMetrics {
  active_patients?: number
  patients_change?: number
  active_patients_percentage?: number
  response_rate?: number
  response_rate_change?: number
  alerts_pending?: number
  alerts_change?: number
  completed_quizzes?: number
  quizzes_change?: number
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
        <CardTitle className="text-sm font-medium text-gray-600">
          {title}
        </CardTitle>
        <Icon className="h-4 w-4 text-gray-400" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold text-gray-900 mb-1">
          {value}
        </div>
        <div className="flex items-center justify-between">
          <p className="text-xs text-gray-500">
            {description}
          </p>
          {change !== 0 && (
            <div className={`flex items-center space-x-1 ${trendColor}`}>
              <TrendIcon className="h-3 w-3" />
              <span className="text-xs font-medium">
                {formatChange(change)}
              </span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
})

StatCard.displayName = 'StatCard'

const QuickStats = memo(() => {
  const { user, isLoading: authLoading } = useAuth()

  const { data: metrics, isLoading, error } = useQuery<DashboardMetrics>({
    queryKey: ['dashboard-metrics'],
    queryFn: () => apiClient.analytics.dashboard(),
    enabled: !!user && !authLoading, // Only run when authenticated
    refetchInterval: 60000, // Refresh every minute
    staleTime: 30000, // Consider data stale after 30 seconds
    gcTime: 5 * 60 * 1000, // Keep in cache for 5 minutes
    retry: 2
  })

  // Memoize stats configuration to prevent recreating on every render
  const stats = useMemo(() => [
    {
      title: 'Pacientes Ativos',
      value: metrics?.active_patients || 0,
      change: metrics?.patients_change || 0,
      icon: Users,
      description: `${metrics?.active_patients_percentage || 0}% do total`
    },
    {
      title: 'Taxa de Resposta',
      value: `${metrics?.response_rate || 0}%`,
      change: metrics?.response_rate_change || 0,
      icon: MessageSquare,
      description: 'Ultimos 7 dias'
    },
    {
      title: 'Alertas Ativos',
      value: metrics?.alerts_pending || 0,
      change: metrics?.alerts_change || 0,
      icon: AlertTriangle,
      description: 'Requerem atencao'
    },
    {
      title: 'Questionarios',
      value: metrics?.completed_quizzes || 0,
      change: metrics?.quizzes_change || 0,
      icon: CheckCircle,
      description: 'Completados esta semana'
    }
  ], [metrics])

  // Loading state with skeleton
  if (isLoading) {
    return <QuickStatsLoading />
  }

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

QuickStats.displayName = 'QuickStats';

export default QuickStats;
