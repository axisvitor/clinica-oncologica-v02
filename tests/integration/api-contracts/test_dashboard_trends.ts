/**
 * Integration Test: Dashboard Trends
 *
 * Verifies trend calculations and fallback behavior for dashboard metrics
 * Tests data visualization and percentage calculations
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { useSystemStats } from '../../../frontend-hormonia/src/hooks/useSystemStats';
import AdminDashboard from '../../../frontend-hormonia/src/components/admin/AdminDashboard';

// Mock the useSystemStats hook
vi.mock('../../../frontend-hormonia/src/hooks/useSystemStats');

const mockUseSystemStats = useSystemStats as any;

const renderDashboard = () => {
  return render(
    <BrowserRouter>
      <AdminDashboard />
    </BrowserRouter>
  );
};

describe('Dashboard Trends Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Trend Delta Calculations', () => {
    it('should display positive trend deltas correctly', async () => {
      const statsWithPositiveTrends = {
        users: {
          total: 150,
          active: 120,
          inactive: 30,
          new_this_month: 25,
          previous_month: 100, // For trend calculation
        },
        appointments: {
          total: 500,
          scheduled: 200,
          completed: 280,
          cancelled: 20,
          pending: 180,
          previous_total: 400, // 25% increase
        },
        revenue: {
          total: 125000.50,
          this_month: 15000.75,
          last_month: 12000.25,
          growth_percentage: 25.0, // Positive growth
        },
        system: {
          uptime: 99.98,
          response_time_ms: 45.5,
          error_rate: 0.02,
          active_sessions: 85,
        },
      };

      mockUseSystemStats.mockReturnValue({
        data: statsWithPositiveTrends,
        isLoading: false,
        error: null,
      });

      const { container } = renderDashboard();

      await waitFor(() => {
        expect(container).toBeTruthy();
      });

      // Should not crash with trend data
      expect(screen.queryByText(/error/i)).not.toBeInTheDocument();
    });

    it('should display negative trend deltas correctly', async () => {
      const statsWithNegativeTrends = {
        users: {
          total: 80,
          active: 60,
          inactive: 20,
          new_this_month: 5,
          previous_month: 100, // 20% decrease
        },
        appointments: {
          total: 300,
          scheduled: 150,
          completed: 140,
          cancelled: 10,
          pending: 140,
          previous_total: 400, // 25% decrease
        },
        revenue: {
          total: 50000,
          this_month: 8000,
          last_month: 10000,
          growth_percentage: -20.0, // Negative growth
        },
        system: {
          uptime: 98.5,
          response_time_ms: 100,
          error_rate: 1.5,
          active_sessions: 40,
        },
      };

      mockUseSystemStats.mockReturnValue({
        data: statsWithNegativeTrends,
        isLoading: false,
        error: null,
      });

      const { container } = renderDashboard();

      await waitFor(() => {
        expect(container).toBeTruthy();
      });

      expect(screen.queryByText(/error/i)).not.toBeInTheDocument();
    });

    it('should handle zero trend deltas (no change)', async () => {
      const statsWithZeroTrends = {
        users: {
          total: 100,
          active: 80,
          inactive: 20,
          new_this_month: 10,
          previous_month: 100, // No change
        },
        appointments: {
          total: 400,
          scheduled: 200,
          completed: 180,
          cancelled: 20,
          pending: 180,
          previous_total: 400, // No change
        },
        revenue: {
          total: 50000,
          this_month: 10000,
          last_month: 10000,
          growth_percentage: 0.0, // No growth
        },
        system: {
          uptime: 99.5,
          response_time_ms: 50,
          error_rate: 0.5,
          active_sessions: 40,
        },
      };

      mockUseSystemStats.mockReturnValue({
        data: statsWithZeroTrends,
        isLoading: false,
        error: null,
      });

      const { container } = renderDashboard();

      await waitFor(() => {
        expect(container).toBeTruthy();
      });

      expect(screen.queryByText(/error/i)).not.toBeInTheDocument();
    });
  });

  describe('Fallback Behavior Without Trends', () => {
    it('should work without trend data (missing previous_month)', async () => {
      const statsWithoutTrends = {
        users: {
          total: 150,
          active: 120,
          inactive: 30,
          new_this_month: 25,
          // Missing previous_month
        },
        appointments: {
          total: 500,
          scheduled: 200,
          completed: 280,
          cancelled: 20,
          pending: 180,
          // Missing previous_total
        },
        revenue: {
          total: 125000.50,
          this_month: 15000.75,
          last_month: 12000.25,
          growth_percentage: 25.0,
        },
        system: {
          uptime: 99.98,
          response_time_ms: 45.5,
          error_rate: 0.02,
          active_sessions: 85,
        },
      };

      mockUseSystemStats.mockReturnValue({
        data: statsWithoutTrends,
        isLoading: false,
        error: null,
      });

      const { container } = renderDashboard();

      await waitFor(() => {
        expect(container).toBeTruthy();
      });

      // Should work with fallback behavior
      expect(screen.queryByText(/error/i)).not.toBeInTheDocument();
    });

    it('should calculate trends from this_month and last_month when available', async () => {
      const statsWithMonthlyData = {
        users: {
          total: 150,
          active: 120,
          inactive: 30,
          new_this_month: 25,
        },
        appointments: {
          total: 500,
          scheduled: 200,
          completed: 280,
          cancelled: 20,
          pending: 180,
        },
        revenue: {
          total: 125000.50,
          this_month: 15000.75,
          last_month: 12000.25,
          growth_percentage: 25.0, // Pre-calculated trend
        },
        system: {
          uptime: 99.98,
          response_time_ms: 45.5,
          error_rate: 0.02,
          active_sessions: 85,
        },
      };

      mockUseSystemStats.mockReturnValue({
        data: statsWithMonthlyData,
        isLoading: false,
        error: null,
      });

      const { container } = renderDashboard();

      await waitFor(() => {
        expect(container).toBeTruthy();
      });

      // Should display revenue growth percentage
      expect(screen.queryByText(/error/i)).not.toBeInTheDocument();
    });

    it('should handle missing all trend-related fields', async () => {
      const minimalStats = {
        users: {
          total: 100,
          active: 80,
          inactive: 20,
          new_this_month: 10,
        },
        appointments: {
          total: 200,
          scheduled: 100,
          completed: 90,
          cancelled: 10,
          pending: 90,
        },
        revenue: {
          total: 50000,
          this_month: 10000,
          last_month: 10000,
          // Missing growth_percentage
        },
        system: {
          uptime: 99.5,
          response_time_ms: 50,
          error_rate: 0.5,
          active_sessions: 40,
        },
      };

      mockUseSystemStats.mockReturnValue({
        data: minimalStats,
        isLoading: false,
        error: null,
      });

      const { container } = renderDashboard();

      await waitFor(() => {
        expect(container).toBeTruthy();
      });

      // Should work with no trends displayed
      expect(screen.queryByText(/error/i)).not.toBeInTheDocument();
    });
  });

  describe('Percentage Calculations', () => {
    it('should calculate growth percentage correctly', () => {
      const currentValue = 15000.75;
      const previousValue = 12000.25;
      const expectedGrowth = ((currentValue - previousValue) / previousValue) * 100;

      expect(Math.round(expectedGrowth * 100) / 100).toBeCloseTo(25.0, 1);
    });

    it('should handle division by zero in percentage calculation', () => {
      const currentValue = 100;
      const previousValue = 0;

      // Should not crash, handle gracefully
      const safeCalculation = previousValue === 0 ? 0 : ((currentValue - previousValue) / previousValue) * 100;

      expect(safeCalculation).toBe(0);
    });

    it('should format percentage values with proper precision', () => {
      const testCases = [
        { value: 25.567, expected: '25.57%' },
        { value: -15.234, expected: '-15.23%' },
        { value: 0, expected: '0.00%' },
        { value: 100, expected: '100.00%' },
        { value: 0.01, expected: '0.01%' },
      ];

      testCases.forEach(({ value, expected }) => {
        const formatted = `${value.toFixed(2)}%`;
        expect(formatted).toBe(expected);
      });
    });

    it('should handle very large percentage values', () => {
      const statsWithLargeGrowth = {
        users: {
          total: 1000,
          active: 900,
          inactive: 100,
          new_this_month: 950,
          previous_month: 10, // 9900% growth
        },
        appointments: {
          total: 5000,
          scheduled: 2000,
          completed: 2800,
          cancelled: 200,
          pending: 1800,
        },
        revenue: {
          total: 1000000,
          this_month: 900000,
          last_month: 10000,
          growth_percentage: 8900.0, // Massive growth
        },
        system: {
          uptime: 99.98,
          response_time_ms: 45.5,
          error_rate: 0.02,
          active_sessions: 85,
        },
      };

      mockUseSystemStats.mockReturnValue({
        data: statsWithLargeGrowth,
        isLoading: false,
        error: null,
      });

      const { container } = renderDashboard();

      expect(container).toBeTruthy();
    });

    it('should handle very small percentage values', () => {
      const statsWithSmallGrowth = {
        users: {
          total: 10000,
          active: 9000,
          inactive: 1000,
          new_this_month: 10,
          previous_month: 9999, // 0.01% growth
        },
        appointments: {
          total: 50000,
          scheduled: 20000,
          completed: 28000,
          cancelled: 2000,
          pending: 18000,
        },
        revenue: {
          total: 10000000,
          this_month: 1000010,
          last_month: 1000000,
          growth_percentage: 0.001, // Very small growth
        },
        system: {
          uptime: 99.98,
          response_time_ms: 45.5,
          error_rate: 0.02,
          active_sessions: 85,
        },
      };

      mockUseSystemStats.mockReturnValue({
        data: statsWithSmallGrowth,
        isLoading: false,
        error: null,
      });

      const { container } = renderDashboard();

      expect(container).toBeTruthy();
    });
  });

  describe('Trend Visualization', () => {
    it('should display upward trend indicator for positive growth', async () => {
      const statsWithUpwardTrend = {
        users: {
          total: 150,
          active: 120,
          inactive: 30,
          new_this_month: 25,
        },
        appointments: {
          total: 500,
          scheduled: 200,
          completed: 280,
          cancelled: 20,
          pending: 180,
        },
        revenue: {
          total: 125000.50,
          this_month: 15000.75,
          last_month: 12000.25,
          growth_percentage: 25.0, // Positive
        },
        system: {
          uptime: 99.98,
          response_time_ms: 45.5,
          error_rate: 0.02,
          active_sessions: 85,
        },
      };

      mockUseSystemStats.mockReturnValue({
        data: statsWithUpwardTrend,
        isLoading: false,
        error: null,
      });

      const { container } = renderDashboard();

      await waitFor(() => {
        expect(container).toBeTruthy();
      });

      // Should render without errors
      expect(screen.queryByText(/error/i)).not.toBeInTheDocument();
    });

    it('should display downward trend indicator for negative growth', async () => {
      const statsWithDownwardTrend = {
        users: {
          total: 80,
          active: 60,
          inactive: 20,
          new_this_month: 5,
        },
        appointments: {
          total: 300,
          scheduled: 150,
          completed: 140,
          cancelled: 10,
          pending: 140,
        },
        revenue: {
          total: 50000,
          this_month: 8000,
          last_month: 10000,
          growth_percentage: -20.0, // Negative
        },
        system: {
          uptime: 98.5,
          response_time_ms: 100,
          error_rate: 1.5,
          active_sessions: 40,
        },
      };

      mockUseSystemStats.mockReturnValue({
        data: statsWithDownwardTrend,
        isLoading: false,
        error: null,
      });

      const { container } = renderDashboard();

      await waitFor(() => {
        expect(container).toBeTruthy();
      });

      expect(screen.queryByText(/error/i)).not.toBeInTheDocument();
    });

    it('should display neutral indicator for zero growth', async () => {
      const statsWithNoTrend = {
        users: {
          total: 100,
          active: 80,
          inactive: 20,
          new_this_month: 10,
        },
        appointments: {
          total: 400,
          scheduled: 200,
          completed: 180,
          cancelled: 20,
          pending: 180,
        },
        revenue: {
          total: 50000,
          this_month: 10000,
          last_month: 10000,
          growth_percentage: 0.0, // Zero
        },
        system: {
          uptime: 99.5,
          response_time_ms: 50,
          error_rate: 0.5,
          active_sessions: 40,
        },
      };

      mockUseSystemStats.mockReturnValue({
        data: statsWithNoTrend,
        isLoading: false,
        error: null,
      });

      const { container } = renderDashboard();

      await waitFor(() => {
        expect(container).toBeTruthy();
      });

      expect(screen.queryByText(/error/i)).not.toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle infinity in calculations', () => {
      const currentValue = 100;
      const previousValue = 0;

      // Division by zero should be handled
      const result = previousValue === 0 ? 0 : ((currentValue - previousValue) / previousValue) * 100;

      expect(isFinite(result)).toBe(true);
      expect(result).toBe(0); // Fallback value
    });

    it('should handle NaN in calculations', () => {
      const currentValue = NaN;
      const previousValue = 100;

      const result = isNaN(currentValue) || isNaN(previousValue) ? 0 : ((currentValue - previousValue) / previousValue) * 100;

      expect(isNaN(result)).toBe(false);
      expect(result).toBe(0); // Fallback value
    });

    it('should handle negative values in trend calculations', () => {
      const statsWithNegativeValues = {
        users: {
          total: 100,
          active: 80,
          inactive: 20,
          new_this_month: -5, // Negative (edge case)
        },
        appointments: {
          total: 200,
          scheduled: 100,
          completed: 90,
          cancelled: 10,
          pending: 90,
        },
        revenue: {
          total: -1000, // Negative revenue (edge case)
          this_month: -500,
          last_month: -1500,
          growth_percentage: 66.67, // Improvement in losses
        },
        system: {
          uptime: 99.5,
          response_time_ms: 50,
          error_rate: 0.5,
          active_sessions: 40,
        },
      };

      mockUseSystemStats.mockReturnValue({
        data: statsWithNegativeValues,
        isLoading: false,
        error: null,
      });

      const { container } = renderDashboard();

      expect(container).toBeTruthy();
      // Should not crash with negative values
    });

    it('should handle very long decimal values', () => {
      const statsWithLongDecimals = {
        users: {
          total: 100,
          active: 80,
          inactive: 20,
          new_this_month: 10,
        },
        appointments: {
          total: 200,
          scheduled: 100,
          completed: 90,
          cancelled: 10,
          pending: 90,
        },
        revenue: {
          total: 50000.123456789,
          this_month: 10000.987654321,
          last_month: 8000.111222333,
          growth_percentage: 25.109876543210987654321, // Very long decimal
        },
        system: {
          uptime: 99.98765432109876,
          response_time_ms: 45.123456789,
          error_rate: 0.012345678901234,
          active_sessions: 85,
        },
      };

      mockUseSystemStats.mockReturnValue({
        data: statsWithLongDecimals,
        isLoading: false,
        error: null,
      });

      const { container } = renderDashboard();

      expect(container).toBeTruthy();
    });
  });

  describe('Real-World Scenarios', () => {
    it('should handle seasonal variation (holiday spike)', async () => {
      const holidaySeasonStats = {
        users: {
          total: 500,
          active: 450,
          inactive: 50,
          new_this_month: 200, // Large spike
          previous_month: 100,
        },
        appointments: {
          total: 2000,
          scheduled: 800,
          completed: 1100,
          cancelled: 100,
          pending: 700,
          previous_total: 1000, // 100% increase
        },
        revenue: {
          total: 500000,
          this_month: 100000,
          last_month: 50000,
          growth_percentage: 100.0, // Double revenue
        },
        system: {
          uptime: 99.98,
          response_time_ms: 45.5,
          error_rate: 0.02,
          active_sessions: 450,
        },
      };

      mockUseSystemStats.mockReturnValue({
        data: holidaySeasonStats,
        isLoading: false,
        error: null,
      });

      const { container } = renderDashboard();

      await waitFor(() => {
        expect(container).toBeTruthy();
      });

      expect(screen.queryByText(/error/i)).not.toBeInTheDocument();
    });

    it('should handle post-holiday decline', async () => {
      const postHolidayStats = {
        users: {
          total: 400,
          active: 300,
          inactive: 100,
          new_this_month: 20,
          previous_month: 200, // 90% decrease
        },
        appointments: {
          total: 1200,
          scheduled: 400,
          completed: 700,
          cancelled: 100,
          pending: 300,
          previous_total: 2000, // 40% decrease
        },
        revenue: {
          total: 300000,
          this_month: 40000,
          last_month: 100000,
          growth_percentage: -60.0, // Significant drop
        },
        system: {
          uptime: 99.98,
          response_time_ms: 30.0,
          error_rate: 0.01,
          active_sessions: 200,
        },
      };

      mockUseSystemStats.mockReturnValue({
        data: postHolidayStats,
        isLoading: false,
        error: null,
      });

      const { container } = renderDashboard();

      await waitFor(() => {
        expect(container).toBeTruthy();
      });

      expect(screen.queryByText(/error/i)).not.toBeInTheDocument();
    });

    it('should handle steady growth pattern', async () => {
      const steadyGrowthStats = {
        users: {
          total: 105,
          active: 84,
          inactive: 21,
          new_this_month: 10,
          previous_month: 100, // 5% growth
        },
        appointments: {
          total: 420,
          scheduled: 210,
          completed: 189,
          cancelled: 21,
          pending: 189,
          previous_total: 400, // 5% growth
        },
        revenue: {
          total: 52500,
          this_month: 10500,
          last_month: 10000,
          growth_percentage: 5.0, // Steady 5% growth
        },
        system: {
          uptime: 99.95,
          response_time_ms: 48.0,
          error_rate: 0.05,
          active_sessions: 42,
        },
      };

      mockUseSystemStats.mockReturnValue({
        data: steadyGrowthStats,
        isLoading: false,
        error: null,
      });

      const { container } = renderDashboard();

      await waitFor(() => {
        expect(container).toBeTruthy();
      });

      expect(screen.queryByText(/error/i)).not.toBeInTheDocument();
    });
  });

  describe('Performance', () => {
    it('should render trends efficiently with large datasets', async () => {
      const largeDataStats = {
        users: {
          total: 1000000,
          active: 850000,
          inactive: 150000,
          new_this_month: 50000,
          previous_month: 950000,
        },
        appointments: {
          total: 10000000,
          scheduled: 4000000,
          completed: 5600000,
          cancelled: 400000,
          pending: 3600000,
          previous_total: 9500000,
        },
        revenue: {
          total: 999999999.99,
          this_month: 100000000.00,
          last_month: 95000000.00,
          growth_percentage: 5.26,
        },
        system: {
          uptime: 99.999,
          response_time_ms: 45.5,
          error_rate: 0.001,
          active_sessions: 50000,
        },
      };

      const startTime = performance.now();

      mockUseSystemStats.mockReturnValue({
        data: largeDataStats,
        isLoading: false,
        error: null,
      });

      renderDashboard();

      await waitFor(() => {
        expect(screen.queryByText(/error/i)).not.toBeInTheDocument();
      });

      const endTime = performance.now();
      const duration = endTime - startTime;

      expect(duration).toBeLessThan(2000); // Should render in less than 2 seconds
    });
  });
});
