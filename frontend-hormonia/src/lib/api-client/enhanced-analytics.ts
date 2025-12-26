/**
 * Enhanced Analytics API Client
 * Handles AI-powered analytics endpoints
 */

import axios, { AxiosInstance } from 'axios';
import { createLogger } from '@/utils/logger';

const logger = createLogger('EnhancedAnalytics');
import {
  EnhancedDashboard,
  Prediction,
  TrendData,
  CustomReport,
  DashboardFilters,
  ReportConfig,
  DashboardResponse,
  PredictionsResponse,
  TrendsResponse,
  ReportResponse,
} from '../../types/enhanced-analytics';

export class EnhancedAnalyticsApi {
  private client: AxiosInstance;
  private baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || process.env['REACT_APP_API_URL'] || import.meta.env.VITE_API_BASE_URL || (import.meta.env.VITE_API_URL || "http://localhost:8000");
    this.client = axios.create({
      baseURL: `${this.baseUrl}/api/v2/enhanced-analytics/`,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 30000, // AI operations may take longer
    });

    // Add auth token interceptor
    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem('auth_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    // Add response error handler
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          // Redirect to login or refresh token
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }

  /**
   * Get AI-powered dashboard with insights and predictions
   */
  async getDashboard(filters?: DashboardFilters): Promise<EnhancedDashboard> {
    try {
      const response = await this.client.get<DashboardResponse>('dashboard', {
        params: filters,
      });

      if (!response.data.success) {
        throw new Error(response.data.error || 'Failed to fetch dashboard');
      }

      return response.data.data;
    } catch (error) {
      logger.error('Error fetching enhanced dashboard', error instanceof Error ? error : undefined);
      throw this.handleError(error);
    }
  }

  /**
   * Get AI predictions for patients
   */
  async getPredictions(
    patientId?: string,
    predictionType?: string,
    page = 1,
    pageSize = 50
  ): Promise<Prediction[]> {
    try {
      const response = await this.client.get<PredictionsResponse>('predictions', {
        params: {
          patient_id: patientId,
          prediction_type: predictionType,
          page,
          page_size: pageSize,
        },
      });

      if (!response.data.success) {
        throw new Error(response.data.error || 'Failed to fetch predictions');
      }

      return response.data.data;
    } catch (error) {
      logger.error('Error fetching predictions', error instanceof Error ? error : undefined);
      throw this.handleError(error);
    }
  }

  /**
   * Get trend analysis for a specific metric
   */
  async getTrends(metric: string, period: string, filters?: DashboardFilters): Promise<TrendData> {
    try {
      const response = await this.client.get<TrendsResponse>('trends', {
        params: {
          metric,
          period,
          ...filters,
        },
      });

      if (!response.data.success) {
        throw new Error(response.data.error || 'Failed to fetch trends');
      }

      return response.data.data;
    } catch (error) {
      logger.error('Error fetching trends', error instanceof Error ? error : undefined);
      throw this.handleError(error);
    }
  }

  /**
   * Generate custom analytics report
   */
  async generateCustomReport(config: ReportConfig): Promise<CustomReport> {
    try {
      const response = await this.client.post<ReportResponse>('custom-report', config);

      if (!response.data.success) {
        throw new Error(response.data.error || 'Failed to generate report');
      }

      return response.data.data;
    } catch (error) {
      logger.error('Error generating custom report', error instanceof Error ? error : undefined);
      throw this.handleError(error);
    }
  }

  /**
   * Download report file
   */
  async downloadReport(reportId: string, format: 'pdf' | 'csv' | 'json'): Promise<Blob> {
    try {
      const response = await this.client.get(`/reports/${reportId}/download`, {
        params: { format },
        responseType: 'blob',
      });

      return response.data;
    } catch (error) {
      logger.error('Error downloading report', error instanceof Error ? error : undefined);
      throw this.handleError(error);
    }
  }

  /**
   * Get available metrics for trend analysis
   */
  async getAvailableMetrics(): Promise<string[]> {
    try {
      const response = await this.client.get<{ success: boolean; data: string[] }>('metrics');

      if (!response.data.success) {
        throw new Error('Failed to fetch available metrics');
      }

      return response.data.data;
    } catch (error) {
      logger.error('Error fetching available metrics', error instanceof Error ? error : undefined);
      throw this.handleError(error);
    }
  }

  /**
   * Acknowledge an analytics alert
   */
  async acknowledgeAlert(alertId: string): Promise<void> {
    try {
      await this.client.post(`/alerts/${alertId}/acknowledge`);
    } catch (error) {
      logger.error('Error acknowledging alert', error instanceof Error ? error : undefined);
      throw this.handleError(error);
    }
  }

  /**
   * Export dashboard data
   */
  async exportDashboard(filters?: DashboardFilters, format: 'pdf' | 'csv' = 'pdf'): Promise<Blob> {
    try {
      const response = await this.client.post(
        'dashboard/export',
        { filters },
        {
          params: { format },
          responseType: 'blob',
        }
      );

      return response.data;
    } catch (error) {
      logger.error('Error exporting dashboard', error instanceof Error ? error : undefined);
      throw this.handleError(error);
    }
  }

  /**
   * Refresh predictions for a specific patient
   */
  async refreshPredictions(patientId: string): Promise<Prediction[]> {
    try {
      const response = await this.client.post<PredictionsResponse>(
        `/predictions/${patientId}/refresh`
      );

      if (!response.data.success) {
        throw new Error(response.data.error || 'Failed to refresh predictions');
      }

      return response.data.data;
    } catch (error) {
      logger.error('Error refreshing predictions', error instanceof Error ? error : undefined);
      throw this.handleError(error);
    }
  }

  /**
   * Error handler
   */
  private handleError(error: unknown): Error {
    if (axios.isAxiosError(error)) {
      const message = error.response?.data?.message || error.message;
      return new Error(`API Error: ${message}`);
    }
    if (error instanceof Error) {
      return error;
    }
    return new Error('An unknown error occurred');
  }
}

// Export singleton instance
export const enhancedAnalyticsApi = new EnhancedAnalyticsApi();
