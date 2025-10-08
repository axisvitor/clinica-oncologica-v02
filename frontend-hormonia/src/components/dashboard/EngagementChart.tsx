import React, { Suspense } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from '@/components/charts/LazyRechartsComponents'
import { ChartSkeleton } from '@/components/ui/chart-skeleton'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

interface ChartData {
  date: string
  messages_sent: number
  responses_received: number
  response_rate: number
}

interface EngagementChartProps {
  data: ChartData[]
}

export function EngagementChart({ data }: EngagementChartProps) {
  // Format data for chart
  const chartData = data.map(item => ({
    ...item,
    date: new Date(item.date).toLocaleDateString('pt-BR', {
      day: '2-digit',
      month: '2-digit'
    })
  }))

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white p-3 border border-gray-200 rounded-lg shadow-lg">
          <p className="font-medium text-gray-900 mb-2">{`Data: ${label}`}</p>
          {payload.map((entry: any, index: number) => (
            <p key={index} style={{ color: entry.color }} className="text-sm">
              {entry.name}: {entry.value}
              {entry.dataKey === 'response_rate' && '%'}
            </p>
          ))}
        </div>
      )
    }
    return null
  }

  if (!data || data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Engajamento dos Pacientes</CardTitle>
          <CardDescription>
            Mensagens enviadas e taxa de resposta
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[300px] flex items-center justify-center">
            <p className="text-gray-500">Dados insuficientes para exibir o gráfico</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Engajamento dos Pacientes</CardTitle>
        <CardDescription>
          Mensagens enviadas e taxa de resposta nos últimos 7 dias
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-[300px]">
          <Suspense fallback={<ChartSkeleton height="300px" />}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis 
                dataKey="date" 
                stroke="#666"
                fontSize={12}
              />
              <YAxis 
                yAxisId="left"
                stroke="#666"
                fontSize={12}
              />
              <YAxis 
                yAxisId="right"
                orientation="right"
                stroke="#666"
                fontSize={12}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="messages_sent"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={{ fill: '#3b82f6', strokeWidth: 2, r: 4 }}
                name="Mensagens Enviadas"
              />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="responses_received"
                stroke="#10b981"
                strokeWidth={2}
                dot={{ fill: '#10b981', strokeWidth: 2, r: 4 }}
                name="Respostas Recebidas"
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="response_rate"
                stroke="#f59e0b"
                strokeWidth={2}
                dot={{ fill: '#f59e0b', strokeWidth: 2, r: 4 }}
                name="Taxa de Resposta (%)"
              />
            </LineChart>
          </ResponsiveContainer>
          </Suspense>
        </div>
      </CardContent>
    </Card>
  )
}
