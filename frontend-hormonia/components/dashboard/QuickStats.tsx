import React from 'react'
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
import { apiClient } from '../../lib/api-client'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { LoadingSpinner } from '../ui/loading-spinner'

export function QuickStats() {
  const { data: metrics, isLoading } = useQuery({
    queryKey: ['dashboard-metrics'],
    queryFn: () => apiClient.analytics.dashboard(),
    refetchInterval: 60000 // Refresh every minute
  })

  const getTrendIcon = (change: number) => {
    if (change > 0) return TrendingUp
    if (change < 0) return TrendingDown
    return Minus
  }

  const getTrendColor = (change: number) => {
    if (change > 0) return 'text-green-600'
    if (change < 0) return 'text-red-600'
    return 'text-gray-600'
  }

  const formatChange = (change: number) => {
    const sign = change >= 0 ? '+' : ''
    return `${sign}${change}%`
  }

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i}>
            <CardContent className="pt-6">
              <div className="flex items-center justify-center">
                <LoadingSpinner size="md" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  const stats = [
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
      description: 'Últimos 7 dias'
    },
    {
      title: 'Alertas Ativos',
      value: metrics?.active_alerts || 0,
      change: metrics?.alerts_change || 0,
      icon: AlertTriangle,
      description: 'Requerem atenção'
    },
    {
      title: 'Questionários',
      value: metrics?.completed_quizzes || 0,
      change: metrics?.quizzes_change || 0,
      icon: CheckCircle,
      description: 'Completados esta semana'
    }
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {stats.map((stat) => {
        const Icon = stat.icon
        const TrendIcon = getTrendIcon(stat.change)
        const trendColor = getTrendColor(stat.change)
        
        return (
          <Card key={stat.title} className="hover:shadow-md transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">
                {stat.title}
              </CardTitle>
              <Icon className="h-4 w-4 text-gray-400" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-gray-900 mb-1">
                {stat.value}
              </div>
              <div className="flex items-center justify-between">
                <p className="text-xs text-gray-500">
                  {stat.description}
                </p>
                {stat.change !== 0 && (
                  <div className={`flex items-center space-x-1 ${trendColor}`}>
                    <TrendIcon className="h-3 w-3" />
                    <span className="text-xs font-medium">
                      {formatChange(stat.change)}
                    </span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
