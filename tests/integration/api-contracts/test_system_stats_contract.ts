/**
 * Integration Test: System Stats Contract
 *
 * Verifies that useSystemStats hook receives and processes correct data
 * from the /api/v1/admin/system-stats endpoint
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useSystemStats } from '../../../frontend-hormonia/src/hooks/useSystemStats';
import { apiClient } from '../../../frontend-hormonia/src/lib/api-client';

// Mock API client
vi.mock('../../../frontend-hormonia/src/lib/api-client', () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

describe('System Stats Contract Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Successful API Response', () => {
    it('should handle complete system stats response with all fields', async () => {
      const mockResponse = {
        data: {
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
            growth_percentage: 25.0,
          },
          system: {
            uptime: 99.98,
            response_time_ms: 45.5,
            error_rate: 0.02,
            active_sessions: 85,
          },
        },
      };

      (apiClient.get as any).mockResolvedValueOnce(mockResponse);

      const { result } = renderHook(() => useSystemStats());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual(mockResponse.data);
      expect(result.current.error).toBeNull();
      expect(apiClient.get).toHaveBeenCalledWith('/admin/system-stats');
    });

    it('should handle minimal valid response (only required fields)', async () => {
      const mockResponse = {
        data: {
          users: {
            total: 0,
            active: 0,
            inactive: 0,
            new_this_month: 0,
          },
          appointments: {
            total: 0,
            scheduled: 0,
            completed: 0,
            cancelled: 0,
            pending: 0,
          },
          revenue: {
            total: 0,
            this_month: 0,
            last_month: 0,
            growth_percentage: 0,
          },
          system: {
            uptime: 100.0,
            response_time_ms: 0,
            error_rate: 0,
            active_sessions: 0,
          },
        },
      };

      (apiClient.get as any).mockResolvedValueOnce(mockResponse);

      const { result } = renderHook(() => useSystemStats());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual(mockResponse.data);
      expect(result.current.data?.users.total).toBe(0);
      expect(result.current.error).toBeNull();
    });

    it('should handle response with extra optional fields', async () => {
      const mockResponse = {
        data: {
          users: {
            total: 100,
            active: 80,
            inactive: 20,
            new_this_month: 15,
            premium_users: 30, // Extra optional field
          },
          appointments: {
            total: 300,
            scheduled: 150,
            completed: 140,
            cancelled: 10,
            pending: 140,
            virtual_appointments: 50, // Extra optional field
          },
          revenue: {
            total: 50000,
            this_month: 10000,
            last_month: 8000,
            growth_percentage: 25.0,
            projected_next_month: 12000, // Extra optional field
          },
          system: {
            uptime: 99.5,
            response_time_ms: 50,
            error_rate: 0.5,
            active_sessions: 40,
            database_size_mb: 1024, // Extra optional field
          },
        },
      };

      (apiClient.get as any).mockResolvedValueOnce(mockResponse);

      const { result } = renderHook(() => useSystemStats());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual(mockResponse.data);
      expect(result.current.error).toBeNull();
    });
  });

  describe('Error Handling', () => {
    it('should handle network errors gracefully', async () => {
      const networkError = new Error('Network error');
      (apiClient.get as any).mockRejectedValueOnce(networkError);

      const { result } = renderHook(() => useSystemStats());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toBeNull();
      expect(result.current.error).toBeTruthy();
    });

    it('should handle 401 unauthorized errors', async () => {
      const unauthorizedError = {
        response: {
          status: 401,
          data: { detail: 'Unauthorized' },
        },
      };
      (apiClient.get as any).mockRejectedValueOnce(unauthorizedError);

      const { result } = renderHook(() => useSystemStats());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toBeNull();
      expect(result.current.error).toBeTruthy();
    });

    it('should handle 500 server errors', async () => {
      const serverError = {
        response: {
          status: 500,
          data: { detail: 'Internal server error' },
        },
      };
      (apiClient.get as any).mockRejectedValueOnce(serverError);

      const { result } = renderHook(() => useSystemStats());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toBeNull();
      expect(result.current.error).toBeTruthy();
    });

    it('should handle malformed JSON response', async () => {
      const malformedResponse = {
        data: 'invalid json string',
      };

      (apiClient.get as any).mockResolvedValueOnce(malformedResponse);

      const { result } = renderHook(() => useSystemStats());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Should handle gracefully without crashing
      expect(result.current.isLoading).toBe(false);
    });

    it('should handle missing required fields in response', async () => {
      const incompleteResponse = {
        data: {
          users: {
            total: 100,
            // Missing: active, inactive, new_this_month
          },
        },
      };

      (apiClient.get as any).mockResolvedValueOnce(incompleteResponse);

      const { result } = renderHook(() => useSystemStats());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Should handle gracefully without crashing
      expect(result.current.isLoading).toBe(false);
    });
  });

  describe('Data Type Validation', () => {
    it('should handle numeric fields as numbers', async () => {
      const mockResponse = {
        data: {
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
            growth_percentage: 25.0,
          },
          system: {
            uptime: 99.98,
            response_time_ms: 45.5,
            error_rate: 0.02,
            active_sessions: 85,
          },
        },
      };

      (apiClient.get as any).mockResolvedValueOnce(mockResponse);

      const { result } = renderHook(() => useSystemStats());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.data?.users.total).toBe('number');
      expect(typeof result.current.data?.revenue.total).toBe('number');
      expect(typeof result.current.data?.system.uptime).toBe('number');
    });

    it('should handle negative values gracefully', async () => {
      const mockResponse = {
        data: {
          users: {
            total: 100,
            active: 80,
            inactive: 20,
            new_this_month: -5, // Negative value (shouldn't happen but testing)
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
            last_month: 12000,
            growth_percentage: -16.67, // Negative growth
          },
          system: {
            uptime: 99.0,
            response_time_ms: 60,
            error_rate: 1.0,
            active_sessions: 50,
          },
        },
      };

      (apiClient.get as any).mockResolvedValueOnce(mockResponse);

      const { result } = renderHook(() => useSystemStats());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data?.revenue.growth_percentage).toBe(-16.67);
      expect(result.current.error).toBeNull();
    });
  });

  describe('Loading States', () => {
    it('should show loading state initially', () => {
      (apiClient.get as any).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      const { result } = renderHook(() => useSystemStats());

      expect(result.current.isLoading).toBe(true);
      expect(result.current.data).toBeNull();
      expect(result.current.error).toBeNull();
    });

    it('should transition from loading to loaded state', async () => {
      const mockResponse = {
        data: {
          users: { total: 100, active: 80, inactive: 20, new_this_month: 10 },
          appointments: { total: 200, scheduled: 100, completed: 90, cancelled: 10, pending: 90 },
          revenue: { total: 50000, this_month: 10000, last_month: 8000, growth_percentage: 25.0 },
          system: { uptime: 99.5, response_time_ms: 50, error_rate: 0.5, active_sessions: 40 },
        },
      };

      (apiClient.get as any).mockResolvedValueOnce(mockResponse);

      const { result } = renderHook(() => useSystemStats());

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual(mockResponse.data);
    });
  });

  describe('Performance', () => {
    it('should complete request within acceptable time', async () => {
      const mockResponse = {
        data: {
          users: { total: 100, active: 80, inactive: 20, new_this_month: 10 },
          appointments: { total: 200, scheduled: 100, completed: 90, cancelled: 10, pending: 90 },
          revenue: { total: 50000, this_month: 10000, last_month: 8000, growth_percentage: 25.0 },
          system: { uptime: 99.5, response_time_ms: 50, error_rate: 0.5, active_sessions: 40 },
        },
      };

      (apiClient.get as any).mockResolvedValueOnce(mockResponse);

      const startTime = performance.now();
      const { result } = renderHook(() => useSystemStats());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const endTime = performance.now();
      const duration = endTime - startTime;

      expect(duration).toBeLessThan(1000); // Should complete in less than 1 second
    });
  });
});
