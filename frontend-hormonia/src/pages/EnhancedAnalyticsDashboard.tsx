/**
 * Enhanced Analytics Dashboard Page
 * AI-powered analytics with predictions, trends, and insights
 */

import React, { useState } from 'react';
import { useEnhancedAnalytics, usePredictions } from '@/hooks/useEnhancedAnalytics';
import { TrendAnalysisChart } from '@/features/analytics/TrendAnalysisChart';
import { AIPredictionsPanel } from '@/features/analytics/AIPredictionsPanel';
import {
  DashboardFilters,
  AIInsight,
  AnalyticsAlert,
  TrendSummary,
  ReportConfig,
} from '@/types/enhanced-analytics';

export const EnhancedAnalyticsDashboard: React.FC = () => {
  const [filters, setFilters] = useState<DashboardFilters>({});
  const [selectedMetric, setSelectedMetric] = useState<string>('patient_engagement');
  const [selectedPeriod, setSelectedPeriod] = useState<string>('30d');
  const [showReportBuilder, setShowReportBuilder] = useState(false);

  const {
    dashboard,
    loading: dashboardLoading,
    error: dashboardError,
    refresh,
    generateReport,
    exportDashboard,
    acknowledgeAlert,
  } = useEnhancedAnalytics({ filters, autoRefresh: true, refreshInterval: 300000 });

  const {
    predictions,
    loading: predictionsLoading,
    refreshForPatient,
  } = usePredictions({ autoRefresh: true, refreshInterval: 600000 });

  const handleExport = async (format: 'pdf' | 'csv') => {
    try {
      await exportDashboard(format);
    } catch (error) {
      console.error('Export failed:', error);
    }
  };

  const handleGenerateReport = async () => {
    const config: ReportConfig = {
      title: 'Custom Analytics Report',
      metrics: [selectedMetric],
      filters,
      format: 'pdf',
      include_visualizations: true,
      include_predictions: true,
      include_recommendations: true,
    };

    try {
      await generateReport(config);
      // Report generated successfully
      setShowReportBuilder(false);
    } catch (error) {
      console.error('Report generation failed:', error);
    }
  };

  const renderInsightCard = (insight: AIInsight) => {
    const severityColors = {
      low: 'border-blue-200 bg-blue-50',
      medium: 'border-yellow-200 bg-yellow-50',
      high: 'border-orange-200 bg-orange-50',
      critical: 'border-red-200 bg-red-50',
    };

    const severityIcons = {
      low: '💡',
      medium: '⚠️',
      high: '🔴',
      critical: '🚨',
    };

    return (
      <div
        key={insight.id}
        className={`p-4 rounded-lg border-l-4 ${severityColors[insight.severity]}`}
      >
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xl">{severityIcons[insight.severity]}</span>
              <h3 className="font-semibold text-gray-800">{insight.title}</h3>
            </div>
            <p className="text-sm text-gray-700 mb-2">{insight.description}</p>
            <div className="flex items-center gap-4 text-xs text-gray-600">
              <span>Type: {insight.type}</span>
              <span>Confidence: {(insight.confidence * 100).toFixed(0)}%</span>
              <span>{new Date(insight.created_at).toLocaleDateString()}</span>
            </div>
          </div>
        </div>

        {insight.actions && insight.actions.length > 0 && (
          <div className="mt-3 flex gap-2">
            {insight.actions.map((action, index) => (
              <button
                key={index}
                className="px-3 py-1 bg-white border border-gray-300 rounded text-sm hover:bg-gray-50"
              >
                {action.label}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  };

  const renderAlertCard = (alert: AnalyticsAlert) => {
    const severityColors = {
      low: 'bg-blue-100 text-blue-800',
      medium: 'bg-yellow-100 text-yellow-800',
      high: 'bg-orange-100 text-orange-800',
      critical: 'bg-red-100 text-red-800',
    };

    return (
      <div
        key={alert.id}
        className={`p-3 rounded-lg ${alert.acknowledged ? 'opacity-50' : ''
          } border border-gray-200`}
      >
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span
                className={`px-2 py-1 rounded text-xs font-semibold ${severityColors[alert.severity]
                  }`}
              >
                {alert.severity.toUpperCase()}
              </span>
              <span className="text-xs text-gray-600">{alert.type}</span>
            </div>
            <p className="text-sm text-gray-800 font-medium mb-1">{alert.message}</p>
            <div className="flex items-center gap-3 text-xs text-gray-600">
              <span>Metric: {alert.metric}</span>
              <span>Value: {alert.value.toFixed(2)}</span>
              {alert.threshold && <span>Threshold: {alert.threshold.toFixed(2)}</span>}
            </div>
          </div>

          {!alert.acknowledged && (
            <button
              onClick={() => acknowledgeAlert(alert.id)}
              className="ml-3 px-3 py-1 bg-gray-200 text-gray-700 rounded text-xs hover:bg-gray-300"
            >
              Acknowledge
            </button>
          )}
        </div>
      </div>
    );
  };

  const renderTrendSummary = (trend: TrendSummary) => {
    const directionIcons = {
      up: '📈',
      down: '📉',
      stable: '➡️',
    };

    const directionColors = {
      up: 'text-green-600',
      down: 'text-red-600',
      stable: 'text-gray-600',
    };

    return (
      <div key={trend.metric} className="bg-white p-4 rounded-lg border border-gray-200">
        <div className="flex items-center justify-between mb-2">
          <h4 className="font-medium text-gray-800">{trend.metric}</h4>
          <span className="text-2xl">{directionIcons[trend.direction]}</span>
        </div>
        <div className="flex items-end justify-between">
          <div>
            <p className={`text-2xl font-bold ${directionColors[trend.direction]}`}>
              {trend.change_percentage > 0 ? '+' : ''}
              {trend.change_percentage.toFixed(1)}%
            </p>
            <p className="text-xs text-gray-600">vs {trend.period}</p>
          </div>
          <span
            className={`px-2 py-1 rounded text-xs font-semibold ${trend.significance === 'high'
                ? 'bg-red-100 text-red-800'
                : trend.significance === 'medium'
                  ? 'bg-yellow-100 text-yellow-800'
                  : 'bg-gray-100 text-gray-800'
              }`}
          >
            {trend.significance}
          </span>
        </div>
      </div>
    );
  };

  if (dashboardError) {
    return (
      <div className="p-8 text-center">
        <div className="text-red-600 mb-4">
          <svg
            className="w-16 h-16 mx-auto mb-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <h2 className="text-xl font-semibold">Failed to load dashboard</h2>
          <p className="text-gray-600 mt-2">{dashboardError.message}</p>
        </div>
        <button
          onClick={refresh}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-8 py-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Enhanced Analytics</h1>
            <p className="text-gray-600 mt-1">AI-powered insights and predictions</p>
          </div>

          <div className="flex gap-3">
            <button
              onClick={refresh}
              disabled={dashboardLoading}
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 flex items-center gap-2"
            >
              <svg
                className={`w-5 h-5 ${dashboardLoading ? 'animate-spin' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
              Refresh
            </button>

            <button
              onClick={() => handleExport('pdf')}
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Export PDF
            </button>

            <button
              onClick={() => handleExport('csv')}
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Export CSV
            </button>

            <button
              onClick={() => setShowReportBuilder(!showReportBuilder)}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Generate Report
            </button>
          </div>
        </div>

        {/* Metadata */}
        {dashboard && (
          <div className="mt-4 flex gap-6 text-sm text-gray-600">
            <span>Last updated: {new Date(dashboard.metadata.generated_at).toLocaleString()}</span>
            <span>Period: {dashboard.metadata.period}</span>
            <span>Total Patients: {dashboard.metadata.total_patients}</span>
            <span>Active Flows: {dashboard.metadata.active_flows}</span>
          </div>
        )}
      </div>

      <div className="p-8">
        {dashboardLoading && !dashboard ? (
          <div className="flex items-center justify-center h-96">
            <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-blue-600" />
          </div>
        ) : (
          <div className="space-y-8">
            {/* Alerts Section */}
            {dashboard && dashboard.alerts.length > 0 && (
              <section>
                <h2 className="text-xl font-semibold text-gray-900 mb-4">Active Alerts</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {dashboard.alerts.map(renderAlertCard)}
                </div>
              </section>
            )}

            {/* Trends Summary */}
            {dashboard && dashboard.trends.length > 0 && (
              <section>
                <h2 className="text-xl font-semibold text-gray-900 mb-4">Trend Summary</h2>
                <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4">
                  {dashboard.trends.map(renderTrendSummary)}
                </div>
              </section>
            )}

            {/* AI Insights */}
            {dashboard && dashboard.insights.length > 0 && (
              <section>
                <h2 className="text-xl font-semibold text-gray-900 mb-4">AI Insights</h2>
                <div className="space-y-4">
                  {dashboard.insights.slice(0, 5).map(renderInsightCard)}
                </div>
              </section>
            )}

            {/* Trend Analysis Chart */}
            <section className="bg-white p-6 rounded-lg border border-gray-200">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-gray-900">Trend Analysis</h2>
                <div className="flex gap-3">
                  <select
                    value={selectedMetric}
                    onChange={(e) => setSelectedMetric(e.target.value)}
                    className="px-3 py-2 border border-gray-300 rounded-lg"
                  >
                    <option value="patient_engagement">Patient Engagement</option>
                    <option value="treatment_adherence">Treatment Adherence</option>
                    <option value="response_rate">Response Rate</option>
                    <option value="flow_completion">Flow Completion</option>
                  </select>
                  <select
                    value={selectedPeriod}
                    onChange={(e) => setSelectedPeriod(e.target.value)}
                    className="px-3 py-2 border border-gray-300 rounded-lg"
                  >
                    <option value="7d">Last 7 Days</option>
                    <option value="30d">Last 30 Days</option>
                    <option value="90d">Last 90 Days</option>
                    <option value="1y">Last Year</option>
                  </select>
                </div>
              </div>
              {/* Trend chart would be rendered here with actual data from API */}
              <div className="h-96 flex items-center justify-center bg-gray-50 rounded">
                <p className="text-gray-500">
                  Trend chart for {selectedMetric} over {selectedPeriod}
                </p>
              </div>
            </section>

            {/* AI Predictions */}
            <section>
              <h2 className="text-xl font-semibold text-gray-900 mb-4">AI Predictions</h2>
              <AIPredictionsPanel
                predictions={predictions}
                onRefresh={refreshForPatient}
                loading={predictionsLoading}
              />
            </section>
          </div>
        )}
      </div>

      {/* Report Builder Modal */}
      {showReportBuilder && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-2xl w-full mx-4">
            <h3 className="text-xl font-semibold mb-4">Generate Custom Report</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Report Title
                </label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  placeholder="Enter report title"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Metrics</label>
                <div className="space-y-2">
                  {['patient_engagement', 'treatment_adherence', 'response_rate'].map((metric) => (
                    <label key={metric} className="flex items-center gap-2">
                      <input type="checkbox" className="rounded" />
                      <span className="text-sm">{metric}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Format</label>
                <select className="w-full px-3 py-2 border border-gray-300 rounded-lg">
                  <option value="pdf">PDF</option>
                  <option value="csv">CSV</option>
                  <option value="json">JSON</option>
                </select>
              </div>

              <div className="flex gap-3 mt-6">
                <button
                  onClick={handleGenerateReport}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  Generate
                </button>
                <button
                  onClick={() => setShowReportBuilder(false)}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default EnhancedAnalyticsDashboard;
