/**
 * Type definitions for Healthcare Metrics Dashboard
 *
 * Comprehensive type definitions for all metrics-related data structures,
 * API responses, and component props used throughout the dashboard.
 */

export interface MetricsSummary {
  engagement_rate: number;
  quiz_completion_rate: number;
  ai_personalization_impact: number;
  active_patients: number;
  daily_messages: number;
  system_health_score: number;
  timestamp: string;
}

export interface EngagementMetrics {
  total_patients: number;
  active_patients: number;
  engagement_rate: number;
  response_rate: number;
  avg_response_time_hours: number;
  daily_active_users: number;
  weekly_active_users: number;
  monthly_active_users: number;
  engagement_trend: EngagementTrendPoint[];
}

export interface EngagementTrendPoint {
  date: string;
  active_users: number;
}

export interface QuizMetrics {
  total_quizzes_sent: number;
  completed_quizzes: number;
  completion_rate: number;
  avg_completion_time_minutes: number;
  quiz_types: Record<string, QuizTypeStats>;
  monthly_quiz_stats: MonthlyQuizStats;
  completion_trend: QuizCompletionTrendPoint[];
}

export interface QuizTypeStats {
  total_sessions: number;
  completed_sessions: number;
  completion_rate: number;
}

export interface MonthlyQuizStats {
  // New field names (primary - matches backend)
  total_sent: number;
  total_completed: number;
  total_expired: number;
  total_active: number;
  average_score: number;

  // Chart-specific fields
  completed: number;
  in_progress: number;
  expired: number;

  // Calculated metrics
  completion_rate: number;
  expiration_rate: number;
}

export interface QuizCompletionTrendPoint {
  date: string;
  completed_quizzes: number;
}

export interface AIPersonalizationMetrics {
  total_messages_processed: number;
  personalized_messages: number;
  personalization_rate: number;
  avg_personalization_score: number;
  safety_interventions: number;
  fallback_rate: number;
  response_quality_score: number;
  personalization_impact: PersonalizationImpact[];
}

export interface PersonalizationImpact {
  metric: string;
  value: number;
  unit: string;
}

export interface SystemPerformanceMetrics {
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  active_connections: number;
  response_time_ms: number;
  error_rate: number;
  uptime_seconds: number;
  throughput_rps: number;
}

export interface RealTimeMetrics {
  engagement: EngagementMetrics;
  quiz: QuizMetrics;
  ai_personalization: AIPersonalizationMetrics;
  system_performance: SystemPerformanceMetrics;
  alerts_count: number;
  last_updated: string;
}

export interface Alert {
  id: string;
  title: string;
  description: string;
  severity: AlertSeverity;
  category: AlertCategory;
  status: AlertStatus;
  created_at: string;
  acknowledged_at?: string;
  acknowledged_by?: string;
  resolved_at?: string;
  resolved_by?: string;
  current_value?: number;
  threshold_value?: number;
  source: string;
  metadata: Record<string, any>;
  escalation_level?: number;
  notification_channels?: string[];
}

export type AlertSeverity = 'low' | 'medium' | 'high' | 'critical';

export type AlertCategory =
  | 'system'
  | 'healthcare'
  | 'security'
  | 'performance'
  | 'data_integrity'
  | 'ai_service';

export type AlertStatus = 'active' | 'acknowledged' | 'resolved' | 'suppressed';

export interface AlertsResponse {
  alerts: Alert[];
  count: number;
  filters: {
    severity?: string;
  };
  generated_at: string;
}

export interface MetricsExportRequest {
  start_date: string;
  end_date: string;
  format: 'json' | 'csv';
}

export interface MetricsExportResponse {
  data: {
    metadata: {
      start_date: string;
      end_date: string;
      format: string;
      generated_at: string;
    };
    engagement: any;
    quiz_performance: any;
    ai_personalization: any;
    system_performance: any;
  };
  metadata: {
    start_date: string;
    end_date: string;
    format: string;
    exported_at: string;
    exported_by: string;
  };
}

export interface WebSocketMessage {
  type: 'metrics_update' | 'alert' | 'ping' | 'pong';
  data?: any;
  timestamp: string;
}

export interface MetricsWebSocketData {
  engagement?: Partial<EngagementMetrics>;
  quiz?: Partial<QuizMetrics>;
  ai_personalization?: Partial<AIPersonalizationMetrics>;
  system_performance?: Partial<SystemPerformanceMetrics>;
  alerts_count?: number;
  timestamp: string;
}

// Chart-specific data types
export interface ChartDataPoint {
  name: string;
  value: number;
  color?: string;
  [key: string]: any;
}

export interface TrendDataPoint {
  date: string;
  value: number;
  [key: string]: any;
}

export interface BarChartData {
  category: string;
  value: number;
  color?: string;
  target?: number;
  [key: string]: any;
}

export interface PieChartData {
  name: string;
  value: number;
  fill: string;
  [key: string]: any;
}

export interface RadialChartData {
  name: string;
  value: number;
  fill: string;
  max?: number;
  [key: string]: any;
}

// Component props interfaces
export interface MetricsDashboardProps {
  userRole: 'doctor' | 'admin';
  refreshInterval?: number;
}

export interface AlertsPanelProps {
  alerts: Alert[];
  onAcknowledge: (alertId: string) => Promise<void>;
  userRole: 'doctor' | 'admin';
}

export interface EngagementChartProps {
  data: EngagementMetrics;
  detailed?: boolean;
  height?: number;
}

export interface QuizCompletionChartProps {
  data: QuizMetrics;
  detailed?: boolean;
  height?: number;
}

export interface AIPersonalizationChartProps {
  data: AIPersonalizationMetrics;
  detailed?: boolean;
  height?: number;
}

export interface SystemHealthChartProps {
  data: SystemPerformanceMetrics;
  detailed?: boolean;
  height?: number;
}

// API response interfaces
export interface ApiResponse<T> {
  data: T;
  message?: string;
  timestamp: string;
}

export interface ApiError {
  error: string;
  detail?: string;
  code?: string;
  timestamp: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

// Filter and query interfaces
export interface MetricsFilters {
  period_days?: number;
  quiz_type?: string;
  severity?: AlertSeverity;
  category?: AlertCategory;
  start_date?: string;
  end_date?: string;
}

export interface MetricsQuery extends MetricsFilters {
  include_details?: boolean;
  include_trends?: boolean;
  group_by?: string;
}

// Health status types
export interface HealthStatus {
  status: 'healthy' | 'warning' | 'critical' | 'unknown';
  score: number;
  checks: HealthCheck[];
  last_updated: string;
}

export interface HealthCheck {
  name: string;
  status: 'pass' | 'fail' | 'warn';
  value?: number;
  unit?: string;
  threshold?: number;
  message?: string;
}

// Notification types
export interface NotificationPreferences {
  email_enabled: boolean;
  sms_enabled: boolean;
  dashboard_enabled: boolean;
  severity_threshold: AlertSeverity;
  quiet_hours: {
    enabled: boolean;
    start_time: string;
    end_time: string;
  };
}

// Theme and styling types
export interface ChartColors {
  primary: string;
  secondary: string;
  success: string;
  warning: string;
  error: string;
  info: string;
  [key: string]: string;
}

export interface ChartTheme {
  colors: ChartColors;
  fontFamily: string;
  fontSize: {
    small: number;
    medium: number;
    large: number;
  };
  spacing: {
    small: number;
    medium: number;
    large: number;
  };
}

// Utility types
export type DateRange = {
  start: Date;
  end: Date;
};

export type TimeUnit = 'minute' | 'hour' | 'day' | 'week' | 'month' | 'year';

export type AggregationType = 'sum' | 'avg' | 'min' | 'max' | 'count';

export type ChartType =
  | 'line'
  | 'area'
  | 'bar'
  | 'pie'
  | 'radial'
  | 'scatter'
  | 'composed';

// Advanced analytics types
export interface TrendAnalysis {
  direction: 'up' | 'down' | 'stable';
  change_percent: number;
  significance: 'low' | 'medium' | 'high';
  period: string;
}

export interface Anomaly {
  metric: string;
  timestamp: string;
  expected_value: number;
  actual_value: number;
  severity: number;
  description: string;
}

export interface Forecast {
  metric: string;
  predictions: Array<{
    timestamp: string;
    value: number;
    confidence_lower: number;
    confidence_upper: number;
  }>;
  model: string;
  accuracy: number;
}

// Performance monitoring types
export interface PerformanceBenchmark {
  metric: string;
  current: number;
  target: number;
  industry_average?: number;
  unit: string;
  status: 'above' | 'at' | 'below';
}

export interface SLA {
  name: string;
  target: number;
  current: number;
  unit: string;
  period: string;
  status: 'met' | 'warning' | 'violated';
}