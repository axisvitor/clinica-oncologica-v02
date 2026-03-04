import React from 'react'
import {
  ComposedChart,
  BarChart,
  PieChart,
  LineChart,
} from '@/components/ui/charts/LazyRechartsComponents'
import {
  Area,
  Bar,
  Pie,
  Cell,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from '@/components/ui/charts/RechartsPrimitives'
import { SafeChartContainer } from '@/components/ui/charts/SafeChartContainer'
import { ChartSkeleton } from '@/components/ui/chart-skeleton'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { FlowAnalytics } from '@/lib/api-client/types'

interface FlowAnalyticsDashboardProps {
  stats?: FlowAnalytics | null
  isLoading?: boolean
}

const CHART_COLORS = ['#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']

const STATUS_LABELS: Record<string, string> = {
  active: 'Ativos',
  paused: 'Pausados',
  completed: 'Concluidos',
  cancelled: 'Cancelados',
}

const formatDate = (value: string) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })
}

const formatPercent = (value: number) => `${value.toFixed(1)}%`

const formatDuration = (value: number) => {
  if (!Number.isFinite(value)) return '0d'
  if (value < 1) return `${Math.round(value * 24)}h`
  return `${value.toFixed(1)}d`
}

export function FlowAnalyticsDashboard({ stats, isLoading }: FlowAnalyticsDashboardProps) {
  if (isLoading) {
    return (
      <div className="grid gap-6 lg:grid-cols-2">
        {[0, 1, 2, 3].map((idx) => (
          <Card key={`flow-chart-skeleton-${idx}`}>
            <CardHeader>
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-3 w-56" />
            </CardHeader>
            <CardContent>
              <ChartSkeleton height={260} />
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  if (!stats) {
    return null
  }

  const activeTrendData = (stats.daily_metrics || []).map((metric) => ({
    date: formatDate(metric.date),
    active: metric.active_flows ?? metric.new_enrollments ?? 0,
    completions: metric.completions ?? 0,
  }))

  const completionRateData = (stats.template_completion_rates || []).map((template) => ({
    name: template.template_name || `${template.kind_key} v${template.version_number}`,
    rate: template.completion_rate * 100,
    total: template.total,
  }))

  const durationData = (stats.template_duration_days || []).map((template) => ({
    name: template.template_name || `${template.kind_key} v${template.version_number}`,
    duration: template.average_duration_days,
  }))

  const statusDistribution = Object.entries(stats.status_distribution || {}).map(
    ([status, value]) => ({
      name: STATUS_LABELS[status] || status,
      value,
    })
  )

  const hasActiveTrend = activeTrendData.length > 0
  const hasCompletionRates = completionRateData.length > 0
  const hasDurations = durationData.length > 0
  const hasStatusDistribution = statusDistribution.length > 0

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Fluxos ativos no tempo</CardTitle>
          <CardDescription>Visao das evolucoes diarias do acompanhamento</CardDescription>
        </CardHeader>
        <CardContent>
          {hasActiveTrend ? (
            <SafeChartContainer height={260}>
              <ComposedChart
                data={activeTrendData}
                margin={{ top: 10, right: 24, left: 0, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="flowActiveGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#2563eb" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#2563eb" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} stroke="#94a3b8" />
                <YAxis tick={{ fontSize: 12 }} stroke="#94a3b8" />
                <Tooltip
                  formatter={(value: number, name: string) => [
                    value,
                    name === 'active' ? 'Fluxos ativos' : 'Conclusoes',
                  ]}
                />
                <Area
                  type="monotone"
                  dataKey="active"
                  stroke="#2563eb"
                  fill="url(#flowActiveGradient)"
                  strokeWidth={2}
                />
                <Line type="monotone" dataKey="completions" stroke="#10b981" strokeWidth={2} />
              </ComposedChart>
            </SafeChartContainer>
          ) : (
            <p className="text-sm text-muted-foreground">Sem dados para exibir o historico.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Taxa de conclusao por template</CardTitle>
          <CardDescription>Comparativo entre versoes publicadas</CardDescription>
        </CardHeader>
        <CardContent>
          {hasCompletionRates ? (
            <SafeChartContainer height={260}>
              <BarChart
                data={completionRateData}
                margin={{ top: 10, right: 24, left: 0, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 11 }}
                  stroke="#94a3b8"
                  interval={0}
                  angle={-15}
                  textAnchor="end"
                  height={60}
                />
                <YAxis
                  tickFormatter={(value: number) => `${value}%`}
                  tick={{ fontSize: 12 }}
                  stroke="#94a3b8"
                />
                <Tooltip
                  formatter={(
                    value: number,
                    _name: string,
                    { payload }: { payload?: { total?: number } }
                  ) => [formatPercent(value), `Conclusao (Total: ${payload?.total ?? 0})`]}
                />
                <Bar dataKey="rate" radius={[6, 6, 0, 0]} fill="#10b981" />
              </BarChart>
            </SafeChartContainer>
          ) : (
            <p className="text-sm text-muted-foreground">Nenhuma versao com dados suficientes.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Distribuicao de status</CardTitle>
          <CardDescription>Panorama dos fluxos por estado atual</CardDescription>
        </CardHeader>
        <CardContent>
          {hasStatusDistribution ? (
            <SafeChartContainer height={260}>
              <PieChart>
                <Tooltip formatter={(value: number, name: string) => [value, name]} />
                <Pie
                  data={statusDistribution}
                  dataKey="value"
                  nameKey="name"
                  outerRadius={90}
                  innerRadius={50}
                  paddingAngle={2}
                >
                  {statusDistribution.map((entry, index) => (
                    <Cell
                      key={`status-${entry.name}`}
                      fill={CHART_COLORS[index % CHART_COLORS.length]}
                    />
                  ))}
                </Pie>
              </PieChart>
            </SafeChartContainer>
          ) : (
            <p className="text-sm text-muted-foreground">Sem distribuicao registrada.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Duracao media por template</CardTitle>
          <CardDescription>Tempo medio ate conclusao por versao</CardDescription>
        </CardHeader>
        <CardContent>
          {hasDurations ? (
            <SafeChartContainer height={260}>
              <LineChart data={durationData} margin={{ top: 10, right: 24, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 11 }}
                  stroke="#94a3b8"
                  interval={0}
                  angle={-15}
                  textAnchor="end"
                  height={60}
                />
                <YAxis
                  tickFormatter={(value: number) => formatDuration(value)}
                  tick={{ fontSize: 12 }}
                  stroke="#94a3b8"
                />
                <Tooltip formatter={(value: number) => [formatDuration(value), 'Duracao media']} />
                <Line
                  type="monotone"
                  dataKey="duration"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  dot={{ r: 4 }}
                />
              </LineChart>
            </SafeChartContainer>
          ) : (
            <p className="text-sm text-muted-foreground">Sem duracoes suficientes para analise.</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
