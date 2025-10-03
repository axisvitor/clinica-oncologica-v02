/**
 * AI Personalization Chart Component
 *
 * Visualizes AI personalization metrics including effectiveness rates,
 * safety interventions, and quality scores for healthcare communication.
 */
import React from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, AreaChart, Area, BarChart, Bar, RadialBarChart, RadialBar,
  ComposedChart, ScatterChart, Scatter, Cell
} from 'recharts';

interface AIPersonalizationData {
  total_messages_processed: number;
  personalized_messages: number;
  personalization_rate: number;
  avg_personalization_score: number;
  safety_interventions: number;
  fallback_rate: number;
  response_quality_score: number;
  personalization_impact: Array<{
    metric: string;
    value: number;
    unit: string;
  }>;
}

interface AIPersonalizationChartProps {
  data: AIPersonalizationData;
  detailed?: boolean;
}

const COLORS = ['#8B5CF6', '#3B82F6', '#10B981', '#F59E0B', '#EF4444'];

export const AIPersonalizationChart: React.FC<AIPersonalizationChartProps> = ({
  data,
  detailed = false
}) => {
  // Prepare data for different chart types
  const scoreData = [
    { name: 'Personalização', score: data.avg_personalization_score, fill: '#8B5CF6' },
    { name: 'Qualidade', score: data.response_quality_score, fill: '#3B82F6' },
    { name: 'Eficácia', score: data.personalization_rate, fill: '#10B981' }
  ];

  const processingData = [
    { category: 'Personalizadas', count: data.personalized_messages, color: '#10B981' },
    { category: 'Originais', count: data['total_messages_processed'] - data['personalized_messages'], color: '#E5E7EB' }
  ];

  const safetyData = [
    { metric: 'Mensagens Seguras', value: data['total_messages_processed'] - data['safety_interventions'] },
    { metric: 'Intervenções', value: data.safety_interventions }
  ];

  const impactMetrics = data.personalization_impact.map(impact => ({
    ...impact,
    displayValue: impact.unit === 'percent' ? `${impact.value}%` :
                 impact.unit === 'out_of_5' ? `${impact.value}/5` :
                 impact.value.toString()
  }));

  const performanceOverview = [
    {
      metric: 'Taxa de Personalização',
      value: data.personalization_rate,
      max: 100,
      color: '#8B5CF6'
    },
    {
      metric: 'Score de Qualidade',
      value: data.response_quality_score,
      max: 100,
      color: '#3B82F6'
    },
    {
      metric: 'Score Médio',
      value: data.avg_personalization_score,
      max: 100,
      color: '#10B981'
    }
  ];

  if (!detailed) {
    // Simple overview chart
    return (
      <div className="space-y-4">
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <RadialBarChart
              cx="50%"
              cy="50%"
              innerRadius="20%"
              outerRadius="90%"
              data={scoreData}
              startAngle={180}
              endAngle={0}
            >
              <RadialBar
                label={{ position: 'insideStart', fill: '#fff', fontSize: 12 }}
                background
                dataKey="score"
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
                formatter={(value: number) => [`${value.toFixed(1)}%`, 'Score']}
              />
            </RadialBarChart>
          </ResponsiveContainer>
        </div>

        <div className="grid grid-cols-3 gap-4 text-center">
          <div className="bg-purple-50 p-3 rounded-lg">
            <div className="text-lg font-bold text-purple-600">{data.personalization_rate.toFixed(1)}%</div>
            <div className="text-sm text-purple-800">Personalização</div>
          </div>
          <div className="bg-blue-50 p-3 rounded-lg">
            <div className="text-lg font-bold text-blue-600">{data.response_quality_score.toFixed(1)}</div>
            <div className="text-sm text-blue-800">Qualidade</div>
          </div>
          <div className="bg-red-50 p-3 rounded-lg">
            <div className="text-lg font-bold text-red-600">{data.safety_interventions}</div>
            <div className="text-sm text-red-800">Intervenções</div>
          </div>
        </div>
      </div>
    );
  }

  // Detailed view with multiple charts
  return (
    <div className="space-y-8">
      {/* Performance Overview */}
      <div className="space-y-2">
        <h4 className="font-semibold text-lg">Performance da IA</h4>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              data={performanceOverview}
              margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis
                dataKey="metric"
                tick={{ fontSize: 12 }}
                stroke="#6B7280"
                angle={-45}
                textAnchor="end"
                height={100}
              />
              <YAxis
                tick={{ fontSize: 12 }}
                stroke="#6B7280"
                domain={[0, 100]}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#FFFFFF',
                  border: '1px solid #E5E7EB',
                  borderRadius: '8px'
                }}
                formatter={(value: number) => [`${value.toFixed(1)}%`, 'Score']}
              />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {performanceOverview.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Bar>
              <Line
                type="monotone"
                dataKey="value"
                stroke="#6B7280"
                strokeWidth={2}
                dot={{ r: 4 }}
                strokeDasharray="5 5"
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Message Processing Breakdown */}
      <div className="grid md:grid-cols-2 gap-6">
        <div className="space-y-2">
          <h4 className="font-semibold text-lg">Processamento de Mensagens</h4>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={processingData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis
                  dataKey="category"
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
                  formatter={(value: number) => [value, 'Mensagens']}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {processingData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="space-y-2">
          <h4 className="font-semibold text-lg">Segurança e Intervenções</h4>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={safetyData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis
                  dataKey="metric"
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
                  formatter={(value: number) => [value, 'Mensagens']}
                />
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke="#EF4444"
                  fill="#FEE2E2"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Impact Metrics */}
      <div className="space-y-2">
        <h4 className="font-semibold text-lg">Impacto da Personalização</h4>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={impactMetrics}
              margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis
                dataKey="metric"
                tick={{ fontSize: 12 }}
                stroke="#6B7280"
                angle={-45}
                textAnchor="end"
                height={120}
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
                formatter={(value: number, name: string, props: any) => [
                  props.payload.displayValue,
                  props.payload.metric
                ]}
              />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {impactMetrics.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Detailed Score Comparison */}
      <div className="space-y-2">
        <h4 className="font-semibold text-lg">Comparação de Scores</h4>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <RadialBarChart
              cx="50%"
              cy="50%"
              innerRadius="10%"
              outerRadius="80%"
              data={scoreData}
              startAngle={90}
              endAngle={450}
            >
              <RadialBar
                label={{ fill: '#666', position: 'insideStart', fontSize: 14 }}
                background
                dataKey="score"
              />
              <Legend
                iconSize={12}
                width={150}
                height={140}
                layout="vertical"
                verticalAlign="middle"
                align="right"
                wrapperStyle={{ fontSize: '14px' }}
              />
              <Tooltip
                formatter={(value: number) => [`${value.toFixed(1)}%`, 'Score']}
                contentStyle={{
                  backgroundColor: '#FFFFFF',
                  border: '1px solid #E5E7EB',
                  borderRadius: '8px'
                }}
              />
            </RadialBarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Summary Statistics */}
      <div className="grid md:grid-cols-4 gap-4">
        <div className="bg-gradient-to-r from-purple-50 to-purple-100 p-4 rounded-lg border border-purple-200">
          <div className="text-2xl font-bold text-purple-700">{data.personalization_rate.toFixed(1)}%</div>
          <div className="text-sm text-purple-600">Taxa de Personalização</div>
        </div>

        <div className="bg-gradient-to-r from-blue-50 to-blue-100 p-4 rounded-lg border border-blue-200">
          <div className="text-2xl font-bold text-blue-700">{data.avg_personalization_score.toFixed(1)}</div>
          <div className="text-sm text-blue-600">Score Médio</div>
        </div>

        <div className="bg-gradient-to-r from-green-50 to-green-100 p-4 rounded-lg border border-green-200">
          <div className="text-2xl font-bold text-green-700">{data.response_quality_score.toFixed(1)}</div>
          <div className="text-sm text-green-600">Qualidade de Resposta</div>
        </div>

        <div className="bg-gradient-to-r from-red-50 to-red-100 p-4 rounded-lg border border-red-200">
          <div className="text-2xl font-bold text-red-700">{data.fallback_rate.toFixed(1)}%</div>
          <div className="text-sm text-red-600">Taxa de Fallback</div>
        </div>
      </div>

      {/* Insights and Analysis */}
      <div className="bg-gray-50 p-6 rounded-lg">
        <h4 className="font-semibold text-lg mb-4">Análise da IA</h4>
        <div className="grid md:grid-cols-2 gap-6 text-sm">
          <div className="space-y-3">
            <h5 className="font-medium text-gray-800">Performance</h5>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span>Mensagens processadas:</span>
                <span className="font-medium">{data['total_messages_processed'].toLocaleString()}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Taxa de sucesso:</span>
                <span className="font-medium text-green-600">
                  {((1 - data.fallback_rate / 100) * 100).toFixed(1)}%
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span>Eficácia média:</span>
                <span className="font-medium">{data.avg_personalization_score.toFixed(1)}/100</span>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <h5 className="font-medium text-gray-800">Segurança</h5>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span>Intervenções de segurança:</span>
                <span className="font-medium text-orange-600">{data.safety_interventions}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Taxa de intervenção:</span>
                <span className="font-medium">
                  {((data['safety_interventions'] / data['total_messages_processed']) * 100).toFixed(2)}%
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span>Mensagens seguras:</span>
                <span className="font-medium text-green-600">
                  {((1 - data['safety_interventions'] / data['total_messages_processed']) * 100).toFixed(1)}%
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Impact Highlights */}
        {impactMetrics.length > 0 && (
          <div className="mt-6 pt-4 border-t border-gray-200">
            <h5 className="font-medium text-gray-800 mb-3">Impactos Destacados</h5>
            <div className="flex flex-wrap gap-4">
              {impactMetrics.map((impact, index) => (
                <div key={index} className="bg-white p-3 rounded-lg border border-gray-200 min-w-0 flex-1">
                  <div className="text-lg font-bold" style={{ color: COLORS[index % COLORS.length] }}>
                    {impact.displayValue}
                  </div>
                  <div className="text-sm text-gray-600">{impact.metric}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
