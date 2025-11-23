/**
 * Enhanced Analytics Types
 * AI-powered analytics and predictions
 */

export interface PredictionFactor {
  name: string;
  impact: number; // -1 to 1
  value: string | number;
  description: string;
}

export interface Prediction {
  patient_id: string;
  prediction_type: 'risk' | 'adherence' | 'success' | 'outcome';
  value: number; // 0-1 probability
  confidence: number; // 0-1 confidence score
  explanation: string;
  factors: PredictionFactor[];
  created_at: string;
  valid_until: string;
}

export interface DataPoint {
  timestamp: string;
  value: number;
  metadata?: Record<string, unknown>;
}

export interface Anomaly {
  timestamp: string;
  expected_value: number;
  actual_value: number;
  severity: 'low' | 'medium' | 'high' | 'critical';
  description: string;
}

export interface ForecastPoint {
  timestamp: string;
  predicted_value: number;
  lower_bound: number;
  upper_bound: number;
  confidence: number;
}

export interface TrendData {
  metric: string;
  period: string;
  data_points: DataPoint[];
  trend_line: number[];
  anomalies: Anomaly[];
  forecast: ForecastPoint[];
  statistics: {
    mean: number;
    median: number;
    std_dev: number;
    min: number;
    max: number;
  };
}

export interface AIInsight {
  id: string;
  type: 'opportunity' | 'risk' | 'trend' | 'recommendation';
  title: string;
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  confidence: number;
  data: Record<string, unknown>;
  actions?: InsightAction[];
  created_at: string;
}

export interface InsightAction {
  label: string;
  action: string;
  params?: Record<string, unknown>;
}

export interface TrendSummary {
  metric: string;
  direction: 'up' | 'down' | 'stable';
  change_percentage: number;
  significance: 'low' | 'medium' | 'high';
  period: string;
}

export interface AnalyticsAlert {
  id: string;
  type: 'threshold' | 'anomaly' | 'prediction';
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  metric: string;
  value: number;
  threshold?: number;
  timestamp: string;
  acknowledged: boolean;
}

export interface EnhancedDashboard {
  insights: AIInsight[];
  predictions: Prediction[];
  trends: TrendSummary[];
  alerts: AnalyticsAlert[];
  metadata: {
    generated_at: string;
    period: string;
    total_patients: number;
    active_flows: number;
  };
}

export interface DashboardFilters {
  start_date?: string;
  end_date?: string;
  patient_ids?: string[];
  metric_types?: string[];
  severity_min?: 'low' | 'medium' | 'high' | 'critical';
}

export interface ReportConfig {
  title: string;
  description?: string;
  metrics: string[];
  filters: DashboardFilters;
  format: 'pdf' | 'csv' | 'json';
  include_visualizations?: boolean;
  include_predictions?: boolean;
  include_recommendations?: boolean;
}

export interface CustomReport {
  id: string;
  config: ReportConfig;
  data: {
    summary: Record<string, unknown>;
    metrics: Record<string, TrendData>;
    predictions?: Prediction[];
    insights?: AIInsight[];
  };
  download_url?: string;
  generated_at: string;
  expires_at: string;
}

export interface EnhancedInsight {
  category: string;
  insights: AIInsight[];
  priority: number;
}

// Chart configuration types
export interface ChartConfig {
  type: 'line' | 'bar' | 'scatter' | 'area' | 'heatmap';
  title: string;
  x_axis: string;
  y_axis: string;
  series: ChartSeries[];
  options?: Record<string, unknown>;
}

export interface ChartSeries {
  name: string;
  data: (number | { x: number; y: number })[];
  color?: string;
  type?: 'line' | 'bar' | 'scatter' | 'area';
}

// API Response types
export interface EnhancedAnalyticsResponse<T> {
  success: boolean;
  data: T;
  error?: string;
  metadata?: Record<string, unknown>;
}

export interface PredictionsResponse extends EnhancedAnalyticsResponse<Prediction[]> {
  total: number;
  page: number;
  page_size: number;
}

export interface TrendsResponse extends EnhancedAnalyticsResponse<TrendData> {
  available_metrics: string[];
  available_periods: string[];
}

export interface DashboardResponse extends EnhancedAnalyticsResponse<EnhancedDashboard> {
  cache_expires_at: string;
}

export interface ReportResponse extends EnhancedAnalyticsResponse<CustomReport> {
  processing_time_ms: number;
}
