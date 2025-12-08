/**
 * System Health Chart Component
 *
 * Visualizes system performance metrics including CPU, memory, disk usage,
 * response times, and overall system health indicators.
 */
import React, { Suspense } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, AreaChart, Area, BarChart, Bar, RadialBarChart, RadialBar,
  ComposedChart, ScatterChart, Scatter, Cell
} from '@/components/charts/LazyRechartsComponents';
import type { ValueType, NameType } from 'recharts/types/component/DefaultTooltipContent';
import { ChartSkeleton } from '@/components/ui/chart-skeleton';

interface SystemHealthData {
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  active_connections: number;
  response_time_ms: number;
  error_rate: number;
  uptime_seconds: number;
  throughput_rps: number;
}

interface SystemHealthChartProps {
  data: SystemHealthData;
  detailed?: boolean;
}

const COLORS = ['#10B981', '#F59E0B', '#EF4444', '#3B82F6', '#8B5CF6'];

const getHealthColor = (value: number, thresholds: { good: number; warning: number }) => {
  if (value <= thresholds.good) return '#10B981';
  if (value <= thresholds.warning) return '#F59E0B';
  return '#EF4444';
};

export const SystemHealthChart: React.FC<SystemHealthChartProps> = ({
  data,
  detailed = false
}) => {
  // Calculate uptime in readable format
  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  };

  // Prepare data for different chart types
  const resourceUsageData = [
    {
      resource: 'CPU',
      usage: data.cpu_usage,
      max: 100,
      color: getHealthColor(data.cpu_usage, { good: 70, warning: 85 }),
      threshold_warning: 85,
      threshold_critical: 95
    },
    {
      resource: 'Memória',
      usage: data.memory_usage,
      max: 100,
      color: getHealthColor(data.memory_usage, { good: 75, warning: 90 }),
      threshold_warning: 90,
      threshold_critical: 95
    },
    {
      resource: 'Disco',
      usage: data.disk_usage,
      max: 100,
      color: getHealthColor(data.disk_usage, { good: 80, warning: 90 }),
      threshold_warning: 90,
      threshold_critical: 95
    }
  ];

  const performanceMetrics = [
    {
      metric: 'Tempo de Resposta',
      value: data.response_time_ms,
      unit: 'ms',
      color: getHealthColor(data.response_time_ms, { good: 500, warning: 1000 }),
      target: 500
    },
    {
      metric: 'Taxa de Erro',
      value: data.error_rate,
      unit: '%',
      color: getHealthColor(data.error_rate, { good: 1, warning: 5 }),
      target: 1
    },
    {
      metric: 'Throughput',
      value: data.throughput_rps,
      unit: 'rps',
      color: '#3B82F6',
      target: 100
    }
  ];

  const systemOverview = [
    { name: 'CPU', value: data.cpu_usage, fill: getHealthColor(data.cpu_usage, { good: 70, warning: 85 }) },
    { name: 'Memória', value: data.memory_usage, fill: getHealthColor(data.memory_usage, { good: 75, warning: 90 }) },
    { name: 'Disco', value: data.disk_usage, fill: getHealthColor(data.disk_usage, { good: 80, warning: 90 }) }
  ];

  // Calculate overall health score
  const calculateHealthScore = () => {
    const cpuScore = Math.max(0, 100 - data.cpu_usage);
    const memoryScore = Math.max(0, 100 - data.memory_usage);
    const diskScore = Math.max(0, 100 - data.disk_usage);
    const responseScore = Math.max(0, 100 - (data.response_time_ms / 20)); // 2000ms = 0 score
    const errorScore = Math.max(0, 100 - (data.error_rate * 10)); // 10% error = 0 score

    return (cpuScore + memoryScore + diskScore + responseScore + errorScore) / 5;
  };

  const healthScore = calculateHealthScore();

  if (!detailed) {
    // Simple overview chart
    return (
      <div className="space-y-4">
        <div className="h-64">
          <Suspense fallback={<ChartSkeleton />}>
          <ResponsiveContainer width="100%" height="100%">
            <RadialBarChart
              cx="50%"
              cy="50%"
              innerRadius="20%"
              outerRadius="90%"
              data={systemOverview}
              startAngle={180}
              endAngle={0}
            >
              <RadialBar
                label={{ position: 'insideStart', fill: '#fff', fontSize: 12 }}
                background
                dataKey="value"
              />
              <Legend
                iconSize={10}
                width={120}
                height={140}
                layout="vertical"
                verticalAlign="middle"
                align="right"
              />
              <Tooltip
                formatter={(value: ValueType) => [`${Number(value).toFixed(1)}%`, 'Uso']}
              />
            </RadialBarChart>
          </ResponsiveContainer>
          </Suspense>
        </div>

        <div className="grid grid-cols-3 gap-4 text-center">
          <div className="bg-green-50 p-3 rounded-lg">
            <div className="text-lg font-bold text-green-600">{healthScore.toFixed(0)}%</div>
            <div className="text-sm text-green-800">Saúde</div>
          </div>
          <div className="bg-blue-50 p-3 rounded-lg">
            <div className="text-lg font-bold text-blue-600">{data.response_time_ms.toFixed(0)}ms</div>
            <div className="text-sm text-blue-800">Resposta</div>
          </div>
          <div className="bg-purple-50 p-3 rounded-lg">
            <div className="text-lg font-bold text-purple-600">{formatUptime(data.uptime_seconds)}</div>
            <div className="text-sm text-purple-800">Uptime</div>
          </div>
        </div>
      </div>
    );
  }

  // Detailed view with multiple charts
  return (
    <div className="space-y-8">
      {/* Overall Health Score */}
      <div className="text-center space-y-2">
        <h4 className="font-semibold text-lg">Score de Saúde do Sistema</h4>
        <div className="h-40">
          <Suspense fallback={<ChartSkeleton />}>
          <ResponsiveContainer width="100%" height="100%">
            <RadialBarChart
              cx="50%"
              cy="50%"
              innerRadius="60%"
              outerRadius="90%"
              data={[{
                name: 'Saúde',
                value: healthScore,
                fill: getHealthColor(100 - healthScore, { good: 20, warning: 40 })
              }]}
              startAngle={90}
              endAngle={450}
            >
              <RadialBar
                label={{ position: 'center', fontSize: 24, fontWeight: 'bold' }}
                background
                dataKey="value"
                cornerRadius={10}
                fill={getHealthColor(100 - healthScore, { good: 20, warning: 40 })}
              />
            </RadialBarChart>
          </ResponsiveContainer>
          </Suspense>
        </div>
      </div>

      {/* Resource Usage */}
      <div className="space-y-2">
        <h4 className="font-semibold text-lg">Uso de Recursos</h4>
        <div className="h-80">
          <Suspense fallback={<ChartSkeleton />}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              data={resourceUsageData}
              margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis
                dataKey="resource"
                tick={{ fontSize: 12 }}
                stroke="#6B7280"
              />
              <YAxis
                tick={{ fontSize: 12 }}
                stroke="#6B7280"
                domain={[0, 100]}
                label={{ value: 'Uso (%)', angle: -90, position: 'insideLeft' }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#FFFFFF',
                  border: '1px solid #E5E7EB',
                  borderRadius: '8px'
                }}
                formatter={(value: ValueType, name: NameType, item) => {
                  const payload = item.payload as { resource: string };
                  return [`${Number(value).toFixed(1)}%`, `Uso de ${payload.resource}`];
                }}
              />
              <Bar dataKey="usage" radius={[4, 4, 0, 0]}>
                {resourceUsageData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Bar>
              <Line
                type="monotone"
                dataKey="threshold_warning"
                stroke="#F59E0B"
                strokeWidth={2}
                strokeDasharray="5 5"
                dot={false}
                name="Limite de Alerta"
              />
              <Line
                type="monotone"
                dataKey="threshold_critical"
                stroke="#EF4444"
                strokeWidth={2}
                strokeDasharray="5 5"
                dot={false}
                name="Limite Crítico"
              />
              <Legend />
            </ComposedChart>
          </ResponsiveContainer>
          </Suspense>
        </div>
      </div>

      {/* Performance Metrics */}
      <div className="space-y-2">
        <h4 className="font-semibold text-lg">Métricas de Performance</h4>
        <div className="h-64">
          <Suspense fallback={<ChartSkeleton />}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={performanceMetrics}
              margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis
                dataKey="metric"
                tick={{ fontSize: 12 }}
                stroke="#6B7280"
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
                formatter={(value: ValueType, name: NameType, item) => {
                  const payload = item.payload as { unit: string; metric: string };
                  return [
                    `${Number(value).toFixed(payload.unit === 'ms' ? 0 : 2)}${payload.unit}`,
                    payload.metric
                  ];
                }}
              />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {performanceMetrics.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          </Suspense>
        </div>
      </div>

      {/* Resource Details Grid */}
      <div className="grid md:grid-cols-3 gap-6">
        {resourceUsageData.map((resource, index) => (
          <div key={index} className="bg-white p-4 rounded-lg border border-gray-200">
            <div className="flex items-center justify-between mb-3">
              <h5 className="font-medium">{resource.resource}</h5>
              <span className="text-2xl font-bold" style={{ color: resource.color }}>
                {resource.usage.toFixed(1)}%
              </span>
            </div>

            <div className="h-32">
              <Suspense fallback={<ChartSkeleton />}>
          <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={[{ usage: resource.usage, max: 100 }]}>
                  <defs>
                    <linearGradient id={`color${index}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={resource.color} stopOpacity={0.8}/>
                      <stop offset="95%" stopColor={resource.color} stopOpacity={0.1}/>
                    </linearGradient>
                  </defs>
                  <YAxis domain={[0, 100]} hide />
                  <Area
                    type="monotone"
                    dataKey="usage"
                    stroke={resource.color}
                    fillOpacity={1}
                    fill={`url(#color${index})`}
                    strokeWidth={3}
                  />
                </AreaChart>
              </ResponsiveContainer>
          </Suspense>
            </div>

            <div className="mt-3 space-y-1 text-xs text-gray-600">
              <div className="flex justify-between">
                <span>Alerta:</span>
                <span className="font-medium text-orange-600">{resource.threshold_warning}%</span>
              </div>
              <div className="flex justify-between">
                <span>Crítico:</span>
                <span className="font-medium text-red-600">{resource.threshold_critical}%</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* System Summary */}
      <div className="grid md:grid-cols-4 gap-4">
        <div className="bg-gradient-to-r from-green-50 to-green-100 p-4 rounded-lg border border-green-200">
          <div className="text-2xl font-bold text-green-700">{healthScore.toFixed(0)}%</div>
          <div className="text-sm text-green-600">Score de Saúde</div>
        </div>

        <div className="bg-gradient-to-r from-blue-50 to-blue-100 p-4 rounded-lg border border-blue-200">
          <div className="text-2xl font-bold text-blue-700">{data.response_time_ms.toFixed(0)}ms</div>
          <div className="text-sm text-blue-600">Tempo de Resposta</div>
        </div>

        <div className="bg-gradient-to-r from-purple-50 to-purple-100 p-4 rounded-lg border border-purple-200">
          <div className="text-2xl font-bold text-purple-700">{data.throughput_rps.toFixed(1)}</div>
          <div className="text-sm text-purple-600">Requests/seg</div>
        </div>

        <div className="bg-gradient-to-r from-orange-50 to-orange-100 p-4 rounded-lg border border-orange-200">
          <div className="text-2xl font-bold text-orange-700">{formatUptime(data.uptime_seconds)}</div>
          <div className="text-sm text-orange-600">Uptime</div>
        </div>
      </div>

      {/* System Analysis */}
      <div className="bg-gray-50 p-6 rounded-lg">
        <h4 className="font-semibold text-lg mb-4">Análise do Sistema</h4>
        <div className="grid md:grid-cols-2 gap-6 text-sm">
          <div className="space-y-3">
            <h5 className="font-medium text-gray-800">Estado dos Recursos</h5>
            <div className="space-y-2">
              {resourceUsageData.map((resource, index) => (
                <div key={index} className="flex items-center justify-between">
                  <span>{resource.resource}:</span>
                  <div className="flex items-center space-x-2">
                    <span className="font-medium">{resource.usage.toFixed(1)}%</span>
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: resource.color }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-3">
            <h5 className="font-medium text-gray-800">Performance</h5>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span>Conexões ativas:</span>
                <span className="font-medium">{data.active_connections}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Taxa de erro:</span>
                <span className="font-medium text-red-600">{data.error_rate.toFixed(2)}%</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Throughput:</span>
                <span className="font-medium">{data.throughput_rps.toFixed(1)} rps</span>
              </div>
            </div>
          </div>
        </div>

        {/* Health Recommendations */}
        <div className="mt-6 pt-4 border-t border-gray-200">
          <h5 className="font-medium text-gray-800 mb-3">Recomendações</h5>
          <div className="space-y-2 text-sm">
            {data.cpu_usage > 85 && (
              <div className="bg-red-50 p-3 rounded border-l-4 border-red-400">
                <span className="text-red-800">âš ï¸ CPU alta: considere otimização ou scaling</span>
              </div>
            )}
            {data.memory_usage > 90 && (
              <div className="bg-red-50 p-3 rounded border-l-4 border-red-400">
                <span className="text-red-800">âš ï¸ Memória alta: verificar vazamentos ou aumentar recursos</span>
              </div>
            )}
            {data.response_time_ms > 1000 && (
              <div className="bg-orange-50 p-3 rounded border-l-4 border-orange-400">
                <span className="text-orange-800">âš ï¸ Resposta lenta: otimizar queries ou cache</span>
              </div>
            )}
            {data.error_rate > 5 && (
              <div className="bg-red-50 p-3 rounded border-l-4 border-red-400">
                <span className="text-red-800">âš ï¸ Taxa de erro alta: investigar logs</span>
              </div>
            )}
            {healthScore > 80 && (
              <div className="bg-green-50 p-3 rounded border-l-4 border-green-400">
                <span className="text-green-800">âœ… Sistema operando normalmente</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
