import React, { Suspense } from 'react'
import { BarChart } from '@/components/ui/charts/LazyRechartsComponents'
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Bar,
  Cell,
} from '@/components/ui/charts/RechartsPrimitives'
import type { ValueType, NameType } from 'recharts/types/component/DefaultTooltipContent'
import { ChartSkeleton } from '@/components/ui/chart-skeleton'

interface MetricBarChartCardProps<TData extends Record<string, unknown>> {
  title: string
  data: TData[]
  xDataKey: string
  yDataKey: string
  xAxisHeight: number
  tooltipFormatter: (
    value: ValueType,
    name: NameType,
    item: { payload?: TData }
  ) => [string | number, string]
  getBarColor: (entry: TData, index: number) => string
}

export function MetricBarChartCard<TData extends Record<string, unknown>>({
  title,
  data,
  xDataKey,
  yDataKey,
  xAxisHeight,
  tooltipFormatter,
  getBarColor,
}: MetricBarChartCardProps<TData>) {
  return (
    <div className="space-y-2">
      <h4 className="font-semibold text-lg">{title}</h4>
      <div className="h-64">
        <Suspense fallback={<ChartSkeleton />}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis
                dataKey={xDataKey}
                tick={{ fontSize: 12 }}
                stroke="#6B7280"
                angle={-45}
                textAnchor="end"
                height={xAxisHeight}
              />
              <YAxis tick={{ fontSize: 12 }} stroke="#6B7280" />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#FFFFFF',
                  border: '1px solid #E5E7EB',
                  borderRadius: '8px',
                }}
                formatter={tooltipFormatter}
              />
              <Bar dataKey={yDataKey} radius={[4, 4, 0, 0]}>
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={getBarColor(entry, index)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Suspense>
      </div>
    </div>
  )
}
