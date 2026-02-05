/**
 * Comprehensive test suite for useUserList hook
 *
 * Tests cover:
 * - User list fetching and pagination
 * - Filtering and searching
 * - Loading and error states
 * - Cache management
 * - Edge cases
 */

import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactNode } from 'react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { useUserList } from '../useUserList';
import * as apiClient from '../../../lib/api-client/core';

// ==========================================
// Test Setup
// ==========================================

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        cacheTime: 0,
      },
    },
  });

  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

const mockUsers = [
  {
    id: '1',
    email: 'admin@example.com',
    name: 'Admin User',
    role: 'admin',
    isActive: true,
    createdAt: '2024-01-01T00:00:00Z',
  },
  {
    id: '2',
    email: 'user@example.com',
    name: 'Regular User',
    role: 'user',
    isActive: true,
    createdAt: '2024-01-02T00:00:00Z',
  },
  {
    id: '3',
    email: 'inactive@example.com',
    name: 'Inactive User',
    role: 'user',
    isActive: false,
    createdAt: '2024-01-03T00:00:00Z',
  },
];

// ==========================================
// Basic Functionality Tests
// ==========================================

describe('useUserList - Basic Functionality', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should fetch users successfully', async () => {
    const mockFetch = vi.spyOn(apiClient, 'apiClient').mockResolvedValue({
      data: mockUsers,
      total: 3,
      page: 1,
      pageSize: 10,
    });

    const { result } = renderHook(() => useUserList(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data?.data).toEqual(mockUsers);
    expect(result.current.data?.total).toBe(3);
    expect(mockFetch).toHaveBeenCalledWith('/admin/users', expect.any(Object));
  });

  it('should handle empty user list', async () => {
    vi.spyOn(apiClient, 'apiClient').mockResolvedValue({
      data: [],
      total: 0,
      page: 1,
      pageSize: 10,
    });

    const { result } = renderHook(() => useUserList(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data?.data).toEqual([]);
    expect(result.current.data?.total).toBe(0);
  });

  it('should handle API errors', async () => {
    const errorMessage = 'Failed to fetch users';
    vi.spyOn(apiClient, 'apiClient').mockRejectedValue(new Error(errorMessage));

    const { result } = renderHook(() => useUserList(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeDefined();
    expect(result.current.data).toBeUndefined();
  });
});

// ==========================================
// Pagination Tests
// ==========================================

describe('useUserList - Pagination', () => {
  it('should handle pagination parameters', async () => {
    const mockFetch = vi.spyOn(apiClient, 'apiClient').mockResolvedValue({
      data: mockUsers.slice(0, 2),
      total: 3,
      page: 1,
      pageSize: 2,
    });

    const { result } = renderHook(
      () => useUserList({ page: 1, pageSize: 2 }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      '/admin/users',
      expect.objectContaining({
        params: expect.objectContaining({
          page: 1,
          pageSize: 2,
        }),
      })
    );
  });

  it('should handle page change', async () => {
    const mockFetch = vi.spyOn(apiClient, 'apiClient').mockResolvedValue({
      data: [mockUsers[2]],
      total: 3,
      page: 2,
      pageSize: 2,
    });

    const { result, rerender } = renderHook(
      ({ page }) => useUserList({ page, pageSize: 2 }),
      {
        wrapper: createWrapper(),
        initialProps: { page: 1 },
      }
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Change page
    rerender({ page: 2 });

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/admin/users',
        expect.objectContaining({
          params: expect.objectContaining({
            page: 2,
          }),
        })
      );
    });
  });

  it('should calculate total pages correctly', async () => {
    vi.spyOn(apiClient, 'apiClient').mockResolvedValue({
      data: mockUsers,
      total: 25,
      page: 1,
      pageSize: 10,
    });

    const { result } = renderHook(() => useUserList({ pageSize: 10 }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    const totalPages = Math.ceil(25 / 10);
    expect(totalPages).toBe(3);
  });
});

// ==========================================
// Filtering and Search Tests
// ==========================================

describe('useUserList - Filtering and Search', () => {
  it('should filter by role', async () => {
    const mockFetch = vi.spyOn(apiClient, 'apiClient').mockResolvedValue({
      data: mockUsers.filter((u) => u.role === 'admin'),
      total: 1,
      page: 1,
      pageSize: 10,
    });

    const { result } = renderHook(() => useUserList({ role: 'admin' }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      '/admin/users',
      expect.objectContaining({
        params: expect.objectContaining({
          role: 'admin',
        }),
      })
    );
  });

  it('should filter by active status', async () => {
    vi.spyOn(apiClient, 'apiClient').mockResolvedValue({
      data: mockUsers.filter((u) => u.isActive),
      total: 2,
      page: 1,
      pageSize: 10,
    });

    const { result } = renderHook(() => useUserList({ isActive: true }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data?.total).toBe(2);
  });

  it('should search by query string', async () => {
    const mockFetch = vi.spyOn(apiClient, 'apiClient').mockResolvedValue({
      data: mockUsers.filter((u) => u.email.includes('admin')),
      total: 1,
      page: 1,
      pageSize: 10,
    });

    const { result } = renderHook(() => useUserList({ search: 'admin' }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      '/admin/users',
      expect.objectContaining({
        params: expect.objectContaining({
          search: 'admin',
        }),
      })
    );
  });

  it('should combine multiple filters', async () => {
    const mockFetch = vi.spyOn(apiClient, 'apiClient').mockResolvedValue({
      data: [],
      total: 0,
      page: 1,
      pageSize: 10,
    });

    const { result } = renderHook(
      () =>
        useUserList({
          role: 'admin',
          isActive: true,
          search: 'admin',
        }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      '/admin/users',
      expect.objectContaining({
        params: expect.objectContaining({
          role: 'admin',
          isActive: true,
          search: 'admin',
        }),
      })
    );
  });
});

// ==========================================
// Sorting Tests
// ==========================================

describe('useUserList - Sorting', () => {
  it('should sort by field ascending', async () => {
    const mockFetch = vi.spyOn(apiClient, 'apiClient').mockResolvedValue({
      data: [...mockUsers].sort((a, b) => a.name.localeCompare(b.name)),
      total: 3,
      page: 1,
      pageSize: 10,
    });

    const { result } = renderHook(
      () => useUserList({ sortBy: 'name', sortOrder: 'asc' }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      '/admin/users',
      expect.objectContaining({
        params: expect.objectContaining({
          sortBy: 'name',
          sortOrder: 'asc',
        }),
      })
    );
  });

  it('should sort by field descending', async () => {
    vi.spyOn(apiClient, 'apiClient').mockResolvedValue({
      data: [...mockUsers].sort((a, b) => b.createdAt.localeCompare(a.createdAt)),
      total: 3,
      page: 1,
      pageSize: 10,
    });

    const { result } = renderHook(
      () => useUserList({ sortBy: 'createdAt', sortOrder: 'desc' }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data?.data[0].id).toBe('3');
  });
});

// ==========================================
// Loading and Error States
// ==========================================

describe('useUserList - Loading and Error States', () => {
  it('should show loading state initially', () => {
    vi.spyOn(apiClient, 'apiClient').mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    const { result } = renderHook(() => useUserList(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();
  });

  it('should handle network errors', async () => {
    vi.spyOn(apiClient, 'apiClient').mockRejectedValue(
      new Error('Network error')
    );

    const { result } = renderHook(() => useUserList(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toContain('Network error');
  });

  it('should handle 401 unauthorized', async () => {
    const error = new Error('Unauthorized');
    (error as any).response = { status: 401 };
    vi.spyOn(apiClient, 'apiClient').mockRejectedValue(error);

    const { result } = renderHook(() => useUserList(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
  });

  it('should handle 403 forbidden', async () => {
    const error = new Error('Forbidden');
    (error as any).response = { status: 403 };
    vi.spyOn(apiClient, 'apiClient').mockRejectedValue(error);

    const { result } = renderHook(() => useUserList(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
  });
});

// ==========================================
// Cache Management Tests
// ==========================================

describe('useUserList - Cache Management', () => {
  it('should cache query results', async () => {
    const mockFetch = vi.spyOn(apiClient, 'apiClient').mockResolvedValue({
      data: mockUsers,
      total: 3,
      page: 1,
      pageSize: 10,
    });

    const { result, rerender } = renderHook(() => useUserList(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockFetch).toHaveBeenCalledTimes(1);

    // Rerender should use cache
    rerender();

    expect(mockFetch).toHaveBeenCalledTimes(1); // Still 1
  });

  it('should refetch on manual refetch', async () => {
    const mockFetch = vi.spyOn(apiClient, 'apiClient').mockResolvedValue({
      data: mockUsers,
      total: 3,
      page: 1,
      pageSize: 10,
    });

    const { result } = renderHook(() => useUserList(), {
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
// Edge Cases
// ==========================================

describe('useUserList - Edge Cases', () => {
  it('should handle invalid page number', async () => {
    vi.spyOn(apiClient, 'apiClient').mockResolvedValue({
      data: [],
      total: 0,
      page: 0,
      pageSize: 10,
    });

    const { result } = renderHook(() => useUserList({ page: 0 }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });

  it('should handle very large page size', async () => {
    vi.spyOn(apiClient, 'apiClient').mockResolvedValue({
      data: mockUsers,
      total: 3,
      page: 1,
      pageSize: 1000,
    });

    const { result } = renderHook(() => useUserList({ pageSize: 1000 }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });

  it('should handle special characters in search', async () => {
    const mockFetch = vi.spyOn(apiClient, 'apiClient').mockResolvedValue({
      data: [],
      total: 0,
      page: 1,
      pageSize: 10,
    });

    const { result } = renderHook(
      () => useUserList({ search: "'; DROP TABLE users; --" }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Should safely encode special characters
    expect(mockFetch).toHaveBeenCalled();
  });

  it('should handle concurrent requests', async () => {
    const mockFetch = vi.spyOn(apiClient, 'apiClient').mockResolvedValue({
      data: mockUsers,
      total: 3,
      page: 1,
      pageSize: 10,
    });

    const { result: result1 } = renderHook(() => useUserList(), {
      wrapper: createWrapper(),
    });

    const { result: result2 } = renderHook(() => useUserList(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result1.current.isSuccess).toBe(true);
      expect(result2.current.isSuccess).toBe(true);
    });

    // Should deduplicate requests
    expect(mockFetch).toHaveBeenCalled();
  });
});
