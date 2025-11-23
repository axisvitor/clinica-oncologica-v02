/**
 * Trend Analysis Chart Component
 * Visualizes time series data with forecasting and anomaly detection
 */

import React, { useMemo } from 'react';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceDot,
  ReferenceArea,
} from 'recharts';
import { TrendData, Anomaly } from '../../types/enhanced-analytics';

export interface TrendAnalysisChartProps {
  trendData: TrendData;
  height?: number;
  showForecast?: boolean;
  showAnomalies?: boolean;
  showConfidenceInterval?: boolean;
  chartType?: 'line' | 'area';
}

export const TrendAnalysisChart: React.FC<TrendAnalysisChartProps> = ({
  trendData,
  height = 400,
  showForecast = true,
  showAnomalies = true,
  showConfidenceInterval = true,
  chartType = 'line',
}) => {
  // Prepare chart data
  const chartData = useMemo(() => {
    const data = trendData.data_points.map((point, index) => ({
      timestamp: new Date(point.timestamp).toLocaleDateString(),
      actual: point.value as number | undefined,
      trend: trendData.trend_line[index],
      forecast: undefined as number | undefined,
      lowerBound: undefined as number | undefined,
      upperBound: undefined as number | undefined,
    }));

    // Add forecast points
    if (showForecast && trendData.forecast.length > 0) {
      trendData.forecast.forEach((forecast) => {
        data.push({
          timestamp: new Date(forecast.timestamp).toLocaleDateString(),
          actual: undefined,
          trend: undefined,
          forecast: forecast.predicted_value,
          lowerBound: showConfidenceInterval ? forecast.lower_bound : undefined,
          upperBound: showConfidenceInterval ? forecast.upper_bound : undefined,
        });
      });
    }

    return data;
  }, [trendData, showForecast, showConfidenceInterval]);

  // Find anomalies for highlighting
  const anomalyPoints = useMemo(() => {
    if (!showAnomalies) return [];

    return trendData.anomalies.map((anomaly) => {
      const dataIndex = chartData.findIndex(
        (d) => d.timestamp === new Date(anomaly.timestamp).toLocaleDateString()
      );
      return {
        ...anomaly,
        x: chartData[dataIndex]?.timestamp,
        y: anomaly.actual_value,
      };
    });
  }, [trendData.anomalies, chartData, showAnomalies]);

  // Custom tooltip
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload) return null;

    return (
      <div className="bg-white p-4 border border-gray-200 rounded shadow-lg">
        <p className="font-semibold text-gray-800">{label}</p>
        {payload.map((entry: any, index: number) => (
          <p key={index} style={{ color: entry.color }} className="text-sm">
            {entry.name}: {entry.value?.toFixed(2)}
          </p>
        ))}
      </div>
    );
  };

  // Custom legend
  const renderLegend = (props: any) => {
    const { payload } = props;
    return (
      <div className="flex justify-center gap-4 mt-4">
        {payload.map((entry: any, index: number) => (
          <div key={index} className="flex items-center gap-2">
            <div
              className="w-3 h-3 rounded"
              style={{ backgroundColor: entry.color }}
            />
          </div>
        ))}
      </div>
    );
  };

  const ChartComponent = chartType === 'area' ? AreaChart : LineChart;
  const DataComponent = (chartType === 'area' ? Area : Line) as any;

  return (
    <div className="w-full">
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-gray-800">{trendData.metric}</h3>
        <p className="text-sm text-gray-600">Period: {trendData.period}</p>
      </div>

      <ResponsiveContainer width="100%" height={height}>
        <ChartComponent data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis
            dataKey="timestamp"
            tick={{ fontSize: 12 }}
            angle={-45}
            textAnchor="end"
            height={80}
          />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip content={<CustomTooltip />} />
          <Legend content={renderLegend} />

          {/* Confidence interval area */}
          {showConfidenceInterval && (
            <DataComponent
              type="monotone"
              dataKey="upperBound"
              stroke="transparent"
              fill="#e3f2fd"
              fillOpacity={0.3}
            />
          )}

          {/* Actual values */}
          <DataComponent
            type="monotone"
            dataKey="actual"
            stroke="#2196f3"
            strokeWidth={2}
            dot={{ r: 3 }}
            name="Actual"
            fill="#2196f3"
            fillOpacity={chartType === 'area' ? 0.3 : 1}
          />

          {/* Trend line */}
          <DataComponent
            type="monotone"
            dataKey="trend"
            stroke="#ff9800"
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={false}
            name="Trend"
            fill="#ff9800"
            fillOpacity={0}
          />

          {/* Forecast */}
          {showForecast && (
            <DataComponent
              type="monotone"
              dataKey="forecast"
              stroke="#4caf50"
              strokeWidth={2}
              strokeDasharray="3 3"
              dot={{ r: 3 }}
              name="Forecast"
              fill="#4caf50"
              fillOpacity={chartType === 'area' ? 0.2 : 1}
            />
          )}

          {/* Lower confidence bound */}
          {showConfidenceInterval && (
            <DataComponent
              type="monotone"
              dataKey="lowerBound"
              stroke="transparent"
              fill="transparent"
            />
          )}

          {/* Anomaly markers */}
          {showAnomalies &&
            anomalyPoints.map((anomaly, index) => (
              <ReferenceDot
                key={index}
                x={anomaly.x}
                y={anomaly.y}
                r={6}
                fill={
                  anomaly.severity === 'critical'
                    ? '#f44336'
                    : anomaly.severity === 'high'
                      ? '#ff9800'
                      : '#ffc107'
                }
                stroke="white"
                strokeWidth={2}
              />
            ))}
        </ChartComponent>
      </ResponsiveContainer>

      {/* Statistics */}
      < div className="mt-4 grid grid-cols-5 gap-4" >
        <div className="bg-gray-50 p-3 rounded">
          <p className="text-xs text-gray-600">Mean</p>
          <p className="text-lg font-semibold text-gray-800">
            {trendData.statistics.mean.toFixed(2)}
          </p>
        </div>
        <div className="bg-gray-50 p-3 rounded">
          <p className="text-xs text-gray-600">Median</p>
          <p className="text-lg font-semibold text-gray-800">
            {trendData.statistics.median.toFixed(2)}
          </p>
        </div>
        <div className="bg-gray-50 p-3 rounded">
          <p className="text-xs text-gray-600">Std Dev</p>
          <p className="text-lg font-semibold text-gray-800">
            {trendData.statistics.std_dev.toFixed(2)}
          </p>
        </div>
        <div className="bg-gray-50 p-3 rounded">
          <p className="text-xs text-gray-600">Min</p>
          <p className="text-lg font-semibold text-gray-800">
            {trendData.statistics.min.toFixed(2)}
          </p>
        </div>
        <div className="bg-gray-50 p-3 rounded">
          <p className="text-xs text-gray-600">Max</p>
          <p className="text-lg font-semibold text-gray-800">
            {trendData.statistics.max.toFixed(2)}
          </p>
        </div>
      </div>

      {/* Anomalies list */}
      {
        showAnomalies && trendData.anomalies.length > 0 && (
          <div className="mt-4">
            <h4 className="text-sm font-semibold text-gray-700 mb-2">Detected Anomalies</h4>
            <div className="space-y-2">
              {trendData.anomalies.slice(0, 5).map((anomaly, index) => (
                <div
                  key={index}
                  className={`p-2 rounded border-l-4 ${anomaly.severity === 'critical'
                    ? 'bg-red-50 border-red-500'
                    : anomaly.severity === 'high'
                      ? 'bg-orange-50 border-orange-500'
                      : 'bg-yellow-50 border-yellow-500'
                    }`}
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-sm font-medium text-gray-800">{anomaly.description}</p>
                      <p className="text-xs text-gray-600">
                        {new Date(anomaly.timestamp).toLocaleString()}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-gray-600">Expected: {anomaly.expected_value.toFixed(2)}</p>
                      <p className="text-xs text-gray-600">Actual: {anomaly.actual_value.toFixed(2)}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )
      }
    </div >
  );
};

export default TrendAnalysisChart;
