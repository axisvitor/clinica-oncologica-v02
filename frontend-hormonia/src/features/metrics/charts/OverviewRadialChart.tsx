import React, { Suspense } from 'react'
import { RadialBarChart } from '@/components/ui/charts/LazyRechartsComponents'
import {
  Legend,
  ResponsiveContainer,
  RadialBar,
  Tooltip,
} from '@/components/ui/charts/RechartsPrimitives'
import type { ValueType } from 'recharts/types/component/DefaultTooltipContent'
import { ChartSkeleton } from '@/components/ui/chart-skeleton'

interface OverviewRadialChartProps<TData extends Record<string, unknown>> {
  data: TData[]
  valueKey: string
  tooltipLabel: string
  formatValue?: (value: ValueType) => string
}

export function OverviewRadialChart<TData extends Record<string, unknown>>({
  data,
  valueKey,
  tooltipLabel,
  formatValue = (value) => `${Number(value).toFixed(1)}%`,
}: OverviewRadialChartProps<TData>) {
  return (
    <div className="h-64">
      <Suspense fallback={<ChartSkeleton />}>
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            cx="50%"
            cy="50%"
            innerRadius="20%"
            outerRadius="90%"
            data={data}
            startAngle={180}
            endAngle={0}
          >
            <RadialBar
              label={{ position: 'insideStart', fill: '#fff', fontSize: 12 }}
              background
              dataKey={valueKey}
            />
            <Legend
              iconSize={10}
              width={120}
              height={140}
              layout="vertical"
              verticalAlign="middle"
              align="right"
            />
            <Tooltip formatter={(value: ValueType) => [formatValue(value), tooltipLabel]} />
          </RadialBarChart>
        </ResponsiveContainer>
      </Suspense>
    </div>
  )
}
