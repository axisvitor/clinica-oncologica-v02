/**
 * Patient Engagement Chart Component
 *
 * Visualizes patient engagement metrics including response rates,
 * active users, and engagement trends over time.
 */
import React, { Suspense } from 'react';
import { LineChart, AreaChart, BarChart, PieChart } from '@/components/ui/charts/LazyRechartsComponents';
import {
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Area,
  Bar,
  Pie,
  Cell
} from '@/components/ui/charts/RechartsPrimitives';
import type { ValueType, NameType } from 'recharts/types/component/DefaultTooltipContent';
import { ChartSkeleton } from '@/components/ui/chart-skeleton';

interface EngagementData {
  total_patients: number;
  active_patients: number;
  engagement_rate: number;
  response_rate: number;
  avg_response_time_hours: number;
  daily_active_users: number;
  weekly_active_users: number;
  monthly_active_users: number;
  engagement_trend: Array<{
    date: string;
    active_users: number;
  }>;
}

interface EngagementChartProps {
  data: EngagementData;
  detailed?: boolean;
}

const _COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6'];

export const EngagementChart: React.FC<EngagementChartProps> = ({
  data,
  detailed = false
}) => {
  // Prepare data for different chart types
  const trendData = data.engagement_trend.map(point => ({
    ...point,
    date: new Date(point.date).toLocaleDateString('pt-BR', {
      month: 'short',
      day: '2-digit'
    })
  })).reverse(); // Show chronological order

  const userActivityData = [
    { period: 'Diário', users: data.daily_active_users, color: '#3B82F6' },
    { period: 'Semanal', users: data.weekly_active_users, color: '#10B981' },
    { period: 'Mensal', users: data.monthly_active_users, color: '#F59E0B' }
  ];

  const engagementBreakdown = [
    { name: 'Ativos', value: data.active_patients, color: '#10B981' },
    { name: 'Inativos', value: data['total_patients'] - data['active_patients'], color: '#E5E7EB' }
  ];

  const responseMetrics = [
    {
      metric: 'Taxa de Resposta',
      value: data.response_rate,
      unit: '%',
      color: '#3B82F6'
    },
    {
      metric: 'Tempo Médio Resposta',
      value: data.avg_response_time_hours,
      unit: 'h',
      color: '#8B5CF6'
    },
    {
      metric: 'Taxa de Engajamento',
      value: data.engagement_rate,
      unit: '%',
      color: '#10B981'
    }
  ];

  if (!detailed) {
    // Simple overview chart
    return (
      <div className="space-y-4">
        <div className="h-64">
          <Suspense fallback={<ChartSkeleton />}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={trendData}>
              <defs>
                <linearGradient id="colorUsers" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.8}/>
                  <stop offset="95%" stopColor="#3B82F6" stopOpacity={0.1}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 12 }}
                stroke="#6B7280"
              />
              <YAxis
                tick={{ fontSize: 12 }}
                stroke="#6B7280"
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#FFFFFF',
                  border: '1px solid #E5E7EB',
                  borderRadius: '8px',
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
                }}
                formatter={(value: ValueType) => [value, 'Usuários Ativos']}
                labelFormatter={(label: string) => `Data: ${label}`}
              />
              <Area
                type="monotone"
                dataKey="active_users"
                stroke="#3B82F6"
                fillOpacity={1}
                fill="url(#colorUsers)"
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
          </Suspense>
        </div>

        <div className="grid grid-cols-3 gap-4 text-center">
          <div className="bg-blue-50 p-3 rounded-lg">
            <div className="text-lg font-bold text-blue-600">{data.engagement_rate.toFixed(1)}%</div>
            <div className="text-sm text-blue-800">Engajamento</div>
          </div>
          <div className="bg-green-50 p-3 rounded-lg">
            <div className="text-lg font-bold text-green-600">{data.response_rate.toFixed(1)}%</div>
            <div className="text-sm text-green-800">Resposta</div>
          </div>
          <div className="bg-purple-50 p-3 rounded-lg">
            <div className="text-lg font-bold text-purple-600">{data.avg_response_time_hours.toFixed(1)}h</div>
            <div className="text-sm text-purple-800">Tempo Médio</div>
          </div>
        </div>
      </div>
    );
  }

  // Detailed view with multiple charts
  return (
    <div className="space-y-8">
      {/* Engagement Trend */}
      <div className="space-y-2">
        <h4 className="font-semibold text-lg">Tendência de Engajamento</h4>
        <div className="h-80">
          <Suspense fallback={<ChartSkeleton />}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 12 }}
                stroke="#6B7280"
              />
              <YAxis
                tick={{ fontSize: 12 }}
                stroke="#6B7280"
                label={{ value: 'Usuários Ativos', angle: -90, position: 'insideLeft' }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#FFFFFF',
                  border: '1px solid #E5E7EB',
                  borderRadius: '8px',
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
                }}
                formatter={(value: ValueType) => [value, 'Usuários Ativos']}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="active_users"
                stroke="#3B82F6"
                strokeWidth={3}
                dot={{ fill: '#3B82F6', strokeWidth: 2, r: 4 }}
                activeDot={{ r: 6, fill: '#1D4ED8' }}
                name="Usuários Ativos"
              />
            </LineChart>
          </ResponsiveContainer>
          </Suspense>
        </div>
      </div>

      {/* User Activity Breakdown */}
      <div className="grid md:grid-cols-2 gap-6">
        <div className="space-y-2">
          <h4 className="font-semibold text-lg">Atividade de Usuários</h4>
          <div className="h-64">
            <Suspense fallback={<ChartSkeleton />}>
          <ResponsiveContainer width="100%" height="100%">
              <BarChart data={userActivityData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis
                  dataKey="period"
                  tick={{ fontSize: 12 }}
                  stroke="#6B7280"
                />
                <YAxis
                  tick={{ fontSize: 12 }}
                  stroke="#6B7280"
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#FFFFFF',
                    border: '1px solid #E5E7EB',
                    borderRadius: '8px'
                  }}
                  formatter={(value: ValueType) => [value, 'Usuários']}
                />
                <Bar dataKey="users" radius={[4, 4, 0, 0]}>
                  {userActivityData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Suspense>
          </div>
        </div>

        <div className="space-y-2">
          <h4 className="font-semibold text-lg">Distribuição de Pacientes</h4>
          <div className="h-64">
            <Suspense fallback={<ChartSkeleton />}>
          <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={engagementBreakdown}
                  cx="50%"
                  cy="50%"
                  innerRadius={40}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {engagementBreakdown.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value: ValueType) => [value, 'Pacientes']}
                />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </Suspense>
          </div>
        </div>
      </div>

      {/* Response Metrics */}
      <div className="space-y-2">
        <h4 className="font-semibold text-lg">Métricas de Resposta</h4>
        <div className="h-64">
          <Suspense fallback={<ChartSkeleton />}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={responseMetrics}
              margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis
                dataKey="metric"
                tick={{ fontSize: 12 }}
                stroke="#6B7280"
                interval={0}
                angle={-45}
                textAnchor="end"
                height={80}
              />
              <YAxis
                tick={{ fontSize: 12 }}
                stroke="#6B7280"
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#FFFFFF',
                  border: '1px solid #E5E7EB',
                  borderRadius: '8px'
                }}
                formatter={(value: ValueType, name: NameType, item: { payload?: { unit: string; metric: string } }) => {
                  const payload = item.payload as { unit: string; metric: string };
                  return [`${Number(value).toFixed(1)}${payload.unit}`, payload.metric];
                }}
              />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {responseMetrics.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          </Suspense>
        </div>
      </div>

      {/* Summary Statistics */}
      <div className="grid md:grid-cols-4 gap-4">
        <div className="bg-gradient-to-r from-blue-50 to-blue-100 p-4 rounded-lg border border-blue-200">
          <div className="text-2xl font-bold text-blue-700">{data['total_patients']}</div>
          <div className="text-sm text-blue-600">Total de Pacientes</div>
        </div>

        <div className="bg-gradient-to-r from-green-50 to-green-100 p-4 rounded-lg border border-green-200">
          <div className="text-2xl font-bold text-green-700">{data.active_patients}</div>
          <div className="text-sm text-green-600">Pacientes Ativos</div>
        </div>

        <div className="bg-gradient-to-r from-purple-50 to-purple-100 p-4 rounded-lg border border-purple-200">
          <div className="text-2xl font-bold text-purple-700">{data.daily_active_users}</div>
          <div className="text-sm text-purple-600">Ativos Hoje</div>
        </div>

        <div className="bg-gradient-to-r from-orange-50 to-orange-100 p-4 rounded-lg border border-orange-200">
          <div className="text-2xl font-bold text-orange-700">{data.weekly_active_users}</div>
          <div className="text-sm text-orange-600">Ativos esta Semana</div>
        </div>
      </div>
    </div>
  );
};
