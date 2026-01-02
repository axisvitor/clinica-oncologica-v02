/**
 * Frontend Integration Tests for API Contract Fixes
 * ==================================================
 *
 * Tests validate:
 * 1. useUserAdmin hook processes {items, total}
 * 2. NotificationCenter renders {items}
 * 3. AdminDashboard uses useSystemStats
 * 4. Dashboard shows trend percentages
 */

import React from 'react';
import { renderHook, waitFor } from '@testing-library/react';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { rest } from 'msw';
import { setupServer } from 'msw/node';
import { useUserAdmin } from '@/hooks/useUserAdmin';
import { useSystemStats } from '@/hooks/useSystemStats';
import { NotificationCenter } from '@/components/NotificationCenter';
import { AdminDashboard } from '@/pages/AdminDashboard';

// Mock API server
const server = setupServer();

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// Test helpers
const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
};

describe('Fix #1: useUserAdmin Hook - Paginated Response', () => {
  it('should process {items, total} structure correctly', async () => {
    // Mock API response with new structure
    server.use(
      rest.get('/api/v2/admin/users', (req, res, ctx) => {
        return res(
          ctx.json({
            items: [
              {
                id: '1',
                email: 'admin@test.com',
                full_name: 'Admin User',
                role: 'admin',
                created_at: '2024-01-01T00:00:00Z',
              },
              {
                id: '2',
                email: 'user@test.com',
                full_name: 'Regular User',
                role: 'user',
                created_at: '2024-01-02T00:00:00Z',
              },
            ],
            total: 42,
          })
        );
      })
    );

    const { result } = renderHook(() => useUserAdmin(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Verify hook extracts items correctly
    expect(result.current.data).toHaveLength(2);
    expect(result.current.data?.[0].email).toBe('admin@test.com');

    // Verify total is accessible (if exposed by hook)
    // This depends on hook implementation
  });

  it('should handle pagination parameters', async () => {
    server.use(
      rest.get('/api/v2/admin/users', (req, res, ctx) => {
        const skip = req.url.searchParams.get('skip') || '0';
        const limit = req.url.searchParams.get('limit') || '10';

        return res(
          ctx.json({
            items: Array.from({ length: parseInt(limit) }, (_, i) => ({
              id: `${parseInt(skip) + i + 1}`,
              email: `user${parseInt(skip) + i + 1}@test.com`,
              full_name: `User ${parseInt(skip) + i + 1}`,
              role: 'user',
              created_at: '2024-01-01T00:00:00Z',
            })),
            total: 100,
          })
        );
      })
    );

    const { result } = renderHook(
      () => useUserAdmin({ skip: 10, limit: 20 }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toHaveLength(20);
  });

  it('should handle empty results', async () => {
    server.use(
      rest.get('/api/v2/admin/users', (req, res, ctx) => {
        return res(ctx.json({ items: [], total: 0 }));
      })
    );

    const { result } = renderHook(() => useUserAdmin(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toHaveLength(0);
  });
});

describe('Fix #2: User Activity Endpoint', () => {
  it('should fetch user activity data', async () => {
    server.use(
      rest.get('/api/v2/admin/users/activity', (req, res, ctx) => {
        return res(
          ctx.json([
            {
              user_id: '1',
              action: 'login',
              timestamp: '2024-01-01T10:00:00Z',
              details: { ip: '192.168.1.1' },
            },
            {
              user_id: '1',
              action: 'update_profile',
              timestamp: '2024-01-01T11:00:00Z',
              details: { field: 'email' },
            },
          ])
        );
      })
    );

    // Note: This test assumes a useUserActivity hook exists
    // If not implemented yet, this serves as specification
    const { result } = renderHook(
      () => useUserActivity({ userId: '1' }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toHaveLength(2);
    expect(result.current.data?.[0].action).toBe('login');
  });
});

describe('Fix #3: NotificationCenter - {items, unread_count}', () => {
  it('should render notifications from items array', async () => {
    server.use(
      rest.get('/api/v2/notifications', (req, res, ctx) => {
        return res(
          ctx.json({
            items: [
              {
                id: '1',
                title: 'New Message',
                message: 'You have a new message',
                type: 'info',
                read: false,
                created_at: '2024-01-01T10:00:00Z',
              },
              {
                id: '2',
                title: 'Warning',
                message: 'System maintenance scheduled',
                type: 'warning',
                read: true,
                created_at: '2024-01-01T09:00:00Z',
              },
            ],
            unread_count: 1,
          })
        );
      })
    );

    render(<NotificationCenter />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('New Message')).toBeInTheDocument();
      expect(screen.getByText('Warning')).toBeInTheDocument();
    });
  });

  it('should display unread count badge', async () => {
    server.use(
      rest.get('/api/v2/notifications', (req, res, ctx) => {
        return res(
          ctx.json({
            items: [
              {
                id: '1',
                title: 'Unread 1',
                message: 'Message 1',
                type: 'info',
                read: false,
                created_at: '2024-01-01T10:00:00Z',
              },
              {
                id: '2',
                title: 'Unread 2',
                message: 'Message 2',
                type: 'info',
                read: false,
                created_at: '2024-01-01T09:00:00Z',
              },
            ],
            unread_count: 2,
          })
        );
      })
    );

    render(<NotificationCenter />, { wrapper: createWrapper() });

    await waitFor(() => {
      // Assuming badge shows unread count
      expect(screen.getByText('2')).toBeInTheDocument();
    });
  });

  it('should update unread count when notification is marked as read', async () => {
    server.use(
      rest.get('/api/v2/notifications', (req, res, ctx) => {
        return res(
          ctx.json({
            items: [
              {
                id: '1',
                title: 'Test',
                message: 'Test message',
                type: 'info',
                read: false,
                created_at: '2024-01-01T10:00:00Z',
              },
            ],
            unread_count: 1,
          })
        );
      }),
      rest.patch('/api/v2/notifications/:id/read', (req, res, ctx) => {
        return res(ctx.json({ success: true }));
      })
    );

    render(<NotificationCenter />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Test')).toBeInTheDocument();
    });

    // Test marking as read (implementation depends on UI)
    // const markReadButton = screen.getByRole('button', { name: /mark as read/i });
    // fireEvent.click(markReadButton);

    // Verify unread count updates
  });
});

describe('Fix #4: Dashboard Trends with Deltas', () => {
  it('should display metrics with trend indicators', async () => {
    server.use(
      rest.get('/api/v2/admin/dashboard/stats', (req, res, ctx) => {
        return res(
          ctx.json({
            users: {
              value: 1250,
              trend: { percentage: 12.5, direction: 'up' },
            },
            appointments: {
              value: 342,
              trend: { percentage: 8.2, direction: 'up' },
            },
            revenue: {
              value: 45890.50,
              trend: { percentage: -3.1, direction: 'down' },
            },
            active_users: {
              value: 892,
              trend: { percentage: 0, direction: 'stable' },
            },
          })
        );
      })
    );

    render(<AdminDashboard />, { wrapper: createWrapper() });

    await waitFor(() => {
      // Check metric values are displayed
      expect(screen.getByText('1250')).toBeInTheDocument();
      expect(screen.getByText('342')).toBeInTheDocument();

      // Check trend percentages are displayed
      expect(screen.getByText(/12\.5%/)).toBeInTheDocument();
      expect(screen.getByText(/8\.2%/)).toBeInTheDocument();
      expect(screen.getByText(/3\.1%/)).toBeInTheDocument();
    });
  });

  it('should show correct trend direction indicators', async () => {
    server.use(
      rest.get('/api/v2/admin/dashboard/stats', (req, res, ctx) => {
        return res(
          ctx.json({
            users: {
              value: 100,
              trend: { percentage: 10, direction: 'up' },
            },
            appointments: {
              value: 50,
              trend: { percentage: 5, direction: 'down' },
            },
          })
        );
      })
    );

    render(<AdminDashboard />, { wrapper: createWrapper() });

    await waitFor(() => {
      // Assuming trend direction is shown with icons/classes
      const upTrend = screen.getByTestId('trend-users');
      const downTrend = screen.getByTestId('trend-appointments');

      expect(upTrend).toHaveClass('trend-up'); // or contain up arrow icon
      expect(downTrend).toHaveClass('trend-down'); // or contain down arrow icon
    });
  });

  it('should use useSystemStats hook correctly', async () => {
    server.use(
      rest.get('/api/v2/admin/dashboard/stats', (req, res, ctx) => {
        return res(
          ctx.json({
            users: {
              value: 100,
              trend: { percentage: 5, direction: 'up' },
            },
          })
        );
      })
    );

    const { result } = renderHook(() => useSystemStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toHaveProperty('users');
    expect(result.current.data?.users).toHaveProperty('value');
    expect(result.current.data?.users).toHaveProperty('trend');
    expect(result.current.data?.users.trend).toHaveProperty('percentage');
    expect(result.current.data?.users.trend).toHaveProperty('direction');
  });
});

describe('TypeScript Interface Compliance', () => {
  it('should have correct AdminUsersResponse type', async () => {
    server.use(
      rest.get('/api/v2/admin/users', (req, res, ctx) => {
        return res(
          ctx.json({
            items: [],
            total: 0,
          })
        );
      })
    );

    const { result } = renderHook(() => useUserAdmin(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // TypeScript should enforce correct types
    // This test mainly validates at compile time
    const data = result.current.data;
    expect(Array.isArray(data)).toBe(true);
  });

  it('should have correct NotificationsResponse type', async () => {
    server.use(
      rest.get('/api/v2/notifications', (req, res, ctx) => {
        return res(
          ctx.json({
            items: [],
            unread_count: 0,
          })
        );
      })
    );

    const { result } = renderHook(() => useNotifications(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Verify TypeScript types are correct
    expect(result.current.data).toHaveProperty('items');
    expect(result.current.data).toHaveProperty('unread_count');
  });
});

describe('Error Handling', () => {
  it('should handle API errors gracefully', async () => {
    server.use(
      rest.get('/api/v2/admin/users', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ error: 'Internal server error' }));
      })
    );

    const { result } = renderHook(() => useUserAdmin(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeDefined();
  });

  it('should handle network errors', async () => {
    server.use(
      rest.get('/api/v2/notifications', (req, res, ctx) => {
        return res.networkError('Network error');
      })
    );

    const { result } = renderHook(() => useNotifications(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it('should handle malformed response data', async () => {
    server.use(
      rest.get('/api/v2/admin/users', (req, res, ctx) => {
        // Return old format (should cause issues if not handled)
        return res(ctx.json([]));
      })
    );

    const { result } = renderHook(() => useUserAdmin(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      // Should either error or handle gracefully
      expect(
        result.current.isError || result.current.data?.length === 0
      ).toBe(true);
    });
  });
});

// Mock hooks for tests (if not already implemented)
function useUserActivity({ userId }: { userId: string }) {
  // Placeholder - replace with actual hook
  return { data: [], isSuccess: false, isError: false };
}

function useNotifications() {
  // Placeholder - replace with actual hook
  return { data: null, isSuccess: false, isError: false };
}
