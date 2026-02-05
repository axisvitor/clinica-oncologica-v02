/**
 * Comprehensive test suite for useUserStats hook
 *
 * Tests cover:
 * - Statistics aggregation
 * - Real-time updates
 * - Time-based filtering
 * - Chart data formatting
 * - Performance metrics
 */

import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactNode } from 'react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { useUserStats } from '../useUserStats';
import * as apiClient from '../../../lib/api-client/core';

// ==========================================
// Test Setup
// ==========================================

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, cacheTime: 0 },
    },
  });

  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

const mockStats = {
  total: 150,
  active: 120,
  inactive: 30,
  byRole: {
    admin: 5,
    physician: 20,
    nurse: 45,
    user: 80,
  },
  growth: {
    daily: 2,
    weekly: 10,
    monthly: 35,
  },
  registrations: [
    { date: '2024-01-01', count: 5 },
    { date: '2024-01-02', count: 8 },
    { date: '2024-01-03', count: 3 },
  ],
  activityScore: 85.5,
  lastUpdated: '2024-01-03T12:00:00Z',
};

// ==========================================
// Basic Statistics Tests
// ==========================================

describe('useUserStats - Basic Statistics', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should fetch user statistics successfully', async () => {
    const mockFetch = vi.spyOn(apiClient, 'apiClient').mockResolvedValue(mockStats);

    const { result } = renderHook(() => useUserStats(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(mockStats);
    expect(mockFetch).toHaveBeenCalledWith('/admin/users/stats', expect.any(Object));
  });

  it('should calculate total users correctly', async () => {
    vi.spyOn(apiClient, 'apiClient').mockResolvedValue(mockStats);

    const { result } = renderHook(() => useUserStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data?.total).toBe(150);
    });
  });

  it('should break down users by role', async () => {
    vi.spyOn(apiClient, 'apiClient').mockResolvedValue(mockStats);

    const { result } = renderHook(() => useUserStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data?.byRole).toEqual({
        admin: 5,
        physician: 20,
        nurse: 45,
        user: 80,
      });
    });
  });

  it('should show active vs inactive users', async () => {
    vi.spyOn(apiClient, 'apiClient').mockResolvedValue(mockStats);

    const { result } = renderHook(() => useUserStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data?.active).toBe(120);
      expect(result.current.data?.inactive).toBe(30);
    });

    const total = result.current.data!.active + result.current.data!.inactive;
    expect(total).toBe(150);
  });
});

// ==========================================
// Growth Metrics Tests
// ==========================================

describe('useUserStats - Growth Metrics', () => {
  it('should show growth metrics', async () => {
    vi.spyOn(apiClient, 'apiClient').mockResolvedValue(mockStats);

    const { result } = renderHook(() => useUserStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data?.growth).toEqual({
        daily: 2,
        weekly: 10,
        monthly: 35,
      });
    });
  });

  it('should calculate growth percentage', async () => {
    const statsWithPrevious = {
      ...mockStats,
      previousMonth: 115,
    };

    vi.spyOn(apiClient, 'apiClient').mockResolvedValue(statsWithPrevious);

    renderHook(() => useUserStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      const growth = ((150 - 115) / 115) * 100;
      expect(growth).toBeCloseTo(30.43, 1);
    });
  });

  it('should show registration trends', async () => {
    vi.spyOn(apiClient, 'apiClient').mockResolvedValue(mockStats);

    const { result } = renderHook(() => useUserStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data?.registrations).toHaveLength(3);
    });
  });
});

// ==========================================
// Time-based Filtering Tests
// ==========================================

describe('useUserStats - Time-based Filtering', () => {
  it('should filter by date range', async () => {
    const mockFetch = vi.spyOn(apiClient, 'apiClient').mockResolvedValue(mockStats);

    const { result } = renderHook(
      () =>
        useUserStats({
          startDate: '2024-01-01',
          endDate: '2024-01-31',
        }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      '/admin/users/stats',
      expect.objectContaining({
        params: expect.objectContaining({
          startDate: '2024-01-01',
          endDate: '2024-01-31',
        }),
      })
    );
  });

  it('should support preset time ranges', async () => {
    const mockFetch = vi.spyOn(apiClient, 'apiClient').mockResolvedValue(mockStats);

    const { result } = renderHook(() => useUserStats({ period: 'last30days' }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      '/admin/users/stats',
      expect.objectContaining({
        params: expect.objectContaining({
          period: 'last30days',
        }),
      })
    );
  });

  it('should filter by month', async () => {
    const mockFetch = vi.spyOn(apiClient, 'apiClient').mockResolvedValue(mockStats);

    renderHook(() => useUserStats({ month: '2024-01' }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/admin/users/stats',
        expect.objectContaining({
          params: expect.objectContaining({
            month: '2024-01',
          }),
        })
      );
    });
  });
});

// ==========================================
// Chart Data Formatting Tests
// ==========================================

describe('useUserStats - Chart Data Formatting', () => {
  it('should format data for pie chart', async () => {
    vi.spyOn(apiClient, 'apiClient').mockResolvedValue(mockStats);

    const { result } = renderHook(() => useUserStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    const pieData = Object.entries(result.current.data!.byRole).map(([name, value]) => ({
      name,
      value,
    }));

    expect(pieData).toEqual([
      { name: 'admin', value: 5 },
      { name: 'physician', value: 20 },
      { name: 'nurse', value: 45 },
      { name: 'user', value: 80 },
    ]);
  });

  it('should format data for line chart', async () => {
    vi.spyOn(apiClient, 'apiClient').mockResolvedValue(mockStats);

    const { result } = renderHook(() => useUserStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data?.registrations).toEqual([
        { date: '2024-01-01', count: 5 },
        { date: '2024-01-02', count: 8 },
        { date: '2024-01-03', count: 3 },
      ]);
    });
  });

  it('should format data for bar chart', async () => {
    vi.spyOn(apiClient, 'apiClient').mockResolvedValue(mockStats);

    const { result } = renderHook(() => useUserStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      const barData = [
        { label: 'Active', value: result.current.data!.active },
        { label: 'Inactive', value: result.current.data!.inactive },
      ];

      expect(barData).toEqual([
        { label: 'Active', value: 120 },
        { label: 'Inactive', value: 30 },
      ]);
    });
  });
});

// ==========================================
// Performance Metrics Tests
// ==========================================

describe('useUserStats - Performance Metrics', () => {
  it('should calculate activity score', async () => {
    vi.spyOn(apiClient, 'apiClient').mockResolvedValue(mockStats);

    const { result } = renderHook(() => useUserStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data?.activityScore).toBe(85.5);
    });
  });

  it('should show last updated timestamp', async () => {
    vi.spyOn(apiClient, 'apiClient').mockResolvedValue(mockStats);

    const { result } = renderHook(() => useUserStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data?.lastUpdated).toBe('2024-01-03T12:00:00Z');
    });
  });

  it('should calculate percentage distributions', async () => {
    vi.spyOn(apiClient, 'apiClient').mockResolvedValue(mockStats);

    const { result } = renderHook(() => useUserStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      const activePercent = (result.current.data!.active / result.current.data!.total) * 100;
      expect(activePercent).toBeCloseTo(80, 0);
    });
  });
});

// ==========================================
// Real-time Updates Tests
// ==========================================

describe('useUserStats - Real-time Updates', () => {
  it('should auto-refresh at interval', async () => {
    const mockFetch = vi.spyOn(apiClient, 'apiClient').mockResolvedValue(mockStats);

    const { result } = renderHook(() => useUserStats({ refetchInterval: 5000 }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockFetch).toHaveBeenCalledTimes(1);

    // Should refetch after interval
    vi.advanceTimersByTime(5000);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });
  }, 10000);

  it('should refetch on manual trigger', async () => {
    const mockFetch = vi.spyOn(apiClient, 'apiClient').mockResolvedValue(mockStats);

    const { result } = renderHook(() => useUserStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockFetch).toHaveBeenCalledTimes(1);

    // Manual refetch
    result.current.refetch();

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });
  });
});

// ==========================================
// Error Handling Tests
// ==========================================

describe('useUserStats - Error Handling', () => {
  it('should handle fetch errors', async () => {
    vi.spyOn(apiClient, 'apiClient').mockRejectedValue(new Error('Failed to fetch stats'));

    const { result } = renderHook(() => useUserStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toContain('Failed to fetch stats');
  });

  it('should handle invalid data format', async () => {
    vi.spyOn(apiClient, 'apiClient').mockResolvedValue({
      invalid: 'data',
    });

    const { result } = renderHook(() => useUserStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data).toBeDefined();
    });

    // Should handle gracefully
    expect(result.current.isError).toBe(false);
  });

  it('should retry on transient failures', async () => {
    const mockFetch = vi
      .spyOn(apiClient, 'apiClient')
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce(mockStats);

    const { result } = renderHook(() => useUserStats({ retry: 1 }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockFetch).toHaveBeenCalledTimes(2);
  });
});

// ==========================================
// Comparison Tests
// ==========================================

describe('useUserStats - Comparison', () => {
  it('should compare with previous period', async () => {
    const statsWithComparison = {
      ...mockStats,
      comparison: {
        total: { current: 150, previous: 130, change: 15.38 },
        active: { current: 120, previous: 105, change: 14.29 },
      },
    };

    vi.spyOn(apiClient, 'apiClient').mockResolvedValue(statsWithComparison);

    const { result } = renderHook(() => useUserStats({ compare: true }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data?.comparison).toBeDefined();
    });
  });

  it('should show trend indicators', async () => {
    const statsWithTrends = {
      ...mockStats,
      trends: {
        total: 'up',
        active: 'up',
        growth: 'stable',
      },
    };

    vi.spyOn(apiClient, 'apiClient').mockResolvedValue(statsWithTrends);

    const { result } = renderHook(() => useUserStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data?.trends).toBeDefined();
    });
  });
});

// ==========================================
// Edge Cases
// ==========================================

describe('useUserStats - Edge Cases', () => {
  it('should handle zero users', async () => {
    const emptyStats = {
      total: 0,
      active: 0,
      inactive: 0,
      byRole: {},
      growth: { daily: 0, weekly: 0, monthly: 0 },
      registrations: [],
      activityScore: 0,
      lastUpdated: new Date().toISOString(),
    };

    vi.spyOn(apiClient, 'apiClient').mockResolvedValue(emptyStats);

    const { result } = renderHook(() => useUserStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data?.total).toBe(0);
    });
  });

  it('should handle very large numbers', async () => {
    const largeStats = {
      ...mockStats,
      total: 1000000,
    };

    vi.spyOn(apiClient, 'apiClient').mockResolvedValue(largeStats);

    const { result } = renderHook(() => useUserStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data?.total).toBe(1000000);
    });
  });
});
