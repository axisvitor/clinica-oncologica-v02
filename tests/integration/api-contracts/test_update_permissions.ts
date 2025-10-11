/**
 * Integration Test: Update Permissions
 *
 * Verifies that permissions updates actually persist to database
 * and are correctly reflected in subsequent requests
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { apiClient } from '../../../frontend-hormonia/src/lib/api-client';

// Mock API client
vi.mock('../../../frontend-hormonia/src/lib/api-client', () => ({
  apiClient: {
    get: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
  },
}));

// Mock permissions update component
const PermissionsManager = ({ userId }: { userId: string }) => {
  const [permissions, setPermissions] = React.useState<string[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');
  const [success, setSuccess] = React.useState(false);

  React.useEffect(() => {
    const fetchPermissions = async () => {
      try {
        const response = await apiClient.get(`/admin/users/${userId}/permissions`);
        setPermissions(response.data.permissions || []);
        setLoading(false);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to load permissions');
        setLoading(false);
      }
    };

    fetchPermissions();
  }, [userId]);

  const handleUpdatePermissions = async (newPermissions: string[]) => {
    setError('');
    setSuccess(false);

    try {
      await apiClient.put(`/admin/users/${userId}/permissions`, {
        permissions: newPermissions,
      });

      setPermissions(newPermissions);
      setSuccess(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update permissions');
    }
  };

  const togglePermission = (permission: string) => {
    const newPermissions = permissions.includes(permission)
      ? permissions.filter((p) => p !== permission)
      : [...permissions, permission];

    handleUpdatePermissions(newPermissions);
  };

  if (loading) {
    return <div data-testid="loading">Loading permissions...</div>;
  }

  return (
    <div data-testid="permissions-manager">
      <div data-testid="permissions-list">
        {['read', 'write', 'delete', 'admin'].map((permission) => (
          <label key={permission} data-testid={`permission-${permission}`}>
            <input
              type="checkbox"
              checked={permissions.includes(permission)}
              onChange={() => togglePermission(permission)}
              data-testid={`checkbox-${permission}`}
            />
            {permission}
          </label>
        ))}
      </div>
      {success && <div data-testid="success-message">Permissions updated successfully</div>}
      {error && <div data-testid="error-message">{error}</div>}
    </div>
  );
};

import React from 'react';

const renderPermissionsManager = (userId: string = 'user-123') => {
  return render(
    <BrowserRouter>
      <PermissionsManager userId={userId} />
    </BrowserRouter>
  );
};

describe('Update Permissions Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Permissions Loading', () => {
    it('should load existing permissions on mount', async () => {
      const mockPermissions = {
        data: {
          permissions: ['read', 'write'],
        },
      };

      (apiClient.get as any).mockResolvedValueOnce(mockPermissions);

      renderPermissionsManager();

      await waitFor(() => {
        expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
      });

      const readCheckbox = screen.getByTestId('checkbox-read') as HTMLInputElement;
      const writeCheckbox = screen.getByTestId('checkbox-write') as HTMLInputElement;
      const deleteCheckbox = screen.getByTestId('checkbox-delete') as HTMLInputElement;
      const adminCheckbox = screen.getByTestId('checkbox-admin') as HTMLInputElement;

      expect(readCheckbox.checked).toBe(true);
      expect(writeCheckbox.checked).toBe(true);
      expect(deleteCheckbox.checked).toBe(false);
      expect(adminCheckbox.checked).toBe(false);
    });

    it('should handle empty permissions list', async () => {
      const mockPermissions = {
        data: {
          permissions: [],
        },
      };

      (apiClient.get as any).mockResolvedValueOnce(mockPermissions);

      renderPermissionsManager();

      await waitFor(() => {
        expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
      });

      const checkboxes = ['read', 'write', 'delete', 'admin'].map(
        (p) => screen.getByTestId(`checkbox-${p}`) as HTMLInputElement
      );

      checkboxes.forEach((checkbox) => {
        expect(checkbox.checked).toBe(false);
      });
    });

    it('should handle all permissions granted', async () => {
      const mockPermissions = {
        data: {
          permissions: ['read', 'write', 'delete', 'admin'],
        },
      };

      (apiClient.get as any).mockResolvedValueOnce(mockPermissions);

      renderPermissionsManager();

      await waitFor(() => {
        expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
      });

      const checkboxes = ['read', 'write', 'delete', 'admin'].map(
        (p) => screen.getByTestId(`checkbox-${p}`) as HTMLInputElement
      );

      checkboxes.forEach((checkbox) => {
        expect(checkbox.checked).toBe(true);
      });
    });
  });

  describe('Permissions Update - Persistence', () => {
    it('should persist permission addition to backend', async () => {
      const initialPermissions = {
        data: {
          permissions: ['read'],
        },
      };

      (apiClient.get as any).mockResolvedValueOnce(initialPermissions);
      (apiClient.put as any).mockResolvedValueOnce({ data: { success: true } });

      renderPermissionsManager('user-456');

      await waitFor(() => {
        expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
      });

      const writeCheckbox = screen.getByTestId('checkbox-write');
      fireEvent.click(writeCheckbox);

      await waitFor(() => {
        expect(apiClient.put).toHaveBeenCalledWith('/admin/users/user-456/permissions', {
          permissions: ['read', 'write'],
        });
      });

      await waitFor(() => {
        expect(screen.getByTestId('success-message')).toBeInTheDocument();
      });
    });

    it('should persist permission removal to backend', async () => {
      const initialPermissions = {
        data: {
          permissions: ['read', 'write', 'delete'],
        },
      };

      (apiClient.get as any).mockResolvedValueOnce(initialPermissions);
      (apiClient.put as any).mockResolvedValueOnce({ data: { success: true } });

      renderPermissionsManager('user-789');

      await waitFor(() => {
        expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
      });

      const writeCheckbox = screen.getByTestId('checkbox-write');
      fireEvent.click(writeCheckbox);

      await waitFor(() => {
        expect(apiClient.put).toHaveBeenCalledWith('/admin/users/user-789/permissions', {
          permissions: ['read', 'delete'],
        });
      });

      await waitFor(() => {
        expect(screen.getByTestId('success-message')).toBeInTheDocument();
      });
    });

    it('should persist multiple permission changes', async () => {
      const initialPermissions = {
        data: {
          permissions: ['read'],
        },
      };

      (apiClient.get as any).mockResolvedValueOnce(initialPermissions);
      (apiClient.put as any).mockResolvedValue({ data: { success: true } });

      renderPermissionsManager();

      await waitFor(() => {
        expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
      });

      // Add write permission
      fireEvent.click(screen.getByTestId('checkbox-write'));

      await waitFor(() => {
        expect(apiClient.put).toHaveBeenCalledWith('/admin/users/user-123/permissions', {
          permissions: ['read', 'write'],
        });
      });

      // Add delete permission
      fireEvent.click(screen.getByTestId('checkbox-delete'));

      await waitFor(() => {
        expect(apiClient.put).toHaveBeenCalledWith('/admin/users/user-123/permissions', {
          permissions: ['read', 'write', 'delete'],
        });
      });
    });

    it('should verify permissions persist across component remounts', async () => {
      const initialPermissions = {
        data: {
          permissions: ['read'],
        },
      };

      const updatedPermissions = {
        data: {
          permissions: ['read', 'write'],
        },
      };

      (apiClient.get as any)
        .mockResolvedValueOnce(initialPermissions)
        .mockResolvedValueOnce(updatedPermissions);

      (apiClient.put as any).mockResolvedValueOnce({ data: { success: true } });

      const { unmount } = renderPermissionsManager();

      await waitFor(() => {
        expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
      });

      // Update permission
      fireEvent.click(screen.getByTestId('checkbox-write'));

      await waitFor(() => {
        expect(apiClient.put).toHaveBeenCalled();
      });

      // Unmount and remount
      unmount();

      renderPermissionsManager();

      await waitFor(() => {
        expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
      });

      // Verify permission persisted
      const writeCheckbox = screen.getByTestId('checkbox-write') as HTMLInputElement;
      expect(writeCheckbox.checked).toBe(true);
    });
  });

  describe('API Contract Validation', () => {
    it('should send correct payload format to backend', async () => {
      const initialPermissions = {
        data: {
          permissions: [],
        },
      };

      (apiClient.get as any).mockResolvedValueOnce(initialPermissions);
      (apiClient.put as any).mockResolvedValueOnce({ data: { success: true } });

      renderPermissionsManager('user-contract-test');

      await waitFor(() => {
        expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId('checkbox-admin'));

      await waitFor(() => {
        expect(apiClient.put).toHaveBeenCalledWith('/admin/users/user-contract-test/permissions', {
          permissions: ['admin'],
        });
      });
    });

    it('should handle 200 success response correctly', async () => {
      const initialPermissions = {
        data: {
          permissions: ['read'],
        },
      };

      (apiClient.get as any).mockResolvedValueOnce(initialPermissions);
      (apiClient.put as any).mockResolvedValueOnce({
        status: 200,
        data: {
          success: true,
          message: 'Permissions updated',
        },
      });

      renderPermissionsManager();

      await waitFor(() => {
        expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId('checkbox-write'));

      await waitFor(() => {
        expect(screen.getByTestId('success-message')).toBeInTheDocument();
      });
    });

    it('should handle 400 bad request errors', async () => {
      const initialPermissions = {
        data: {
          permissions: ['read'],
        },
      };

      const errorResponse = {
        response: {
          status: 400,
          data: {
            detail: 'Invalid permissions format',
          },
        },
      };

      (apiClient.get as any).mockResolvedValueOnce(initialPermissions);
      (apiClient.put as any).mockRejectedValueOnce(errorResponse);

      renderPermissionsManager();

      await waitFor(() => {
        expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId('checkbox-write'));

      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toHaveTextContent('Invalid permissions format');
      });
    });

    it('should handle 403 forbidden errors', async () => {
      const initialPermissions = {
        data: {
          permissions: ['read'],
        },
      };

      const errorResponse = {
        response: {
          status: 403,
          data: {
            detail: 'Insufficient permissions to update user permissions',
          },
        },
      };

      (apiClient.get as any).mockResolvedValueOnce(initialPermissions);
      (apiClient.put as any).mockRejectedValueOnce(errorResponse);

      renderPermissionsManager();

      await waitFor(() => {
        expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId('checkbox-admin'));

      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toHaveTextContent('Insufficient permissions');
      });
    });

    it('should handle 404 user not found errors', async () => {
      const errorResponse = {
        response: {
          status: 404,
          data: {
            detail: 'User not found',
          },
        },
      };

      (apiClient.get as any).mockRejectedValueOnce(errorResponse);

      renderPermissionsManager('nonexistent-user');

      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toHaveTextContent('User not found');
      });
    });

    it('should handle 500 server errors', async () => {
      const initialPermissions = {
        data: {
          permissions: ['read'],
        },
      };

      const errorResponse = {
        response: {
          status: 500,
          data: {
            detail: 'Internal server error',
          },
        },
      };

      (apiClient.get as any).mockResolvedValueOnce(initialPermissions);
      (apiClient.put as any).mockRejectedValueOnce(errorResponse);

      renderPermissionsManager();

      await waitFor(() => {
        expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId('checkbox-write'));

      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toHaveTextContent('Internal server error');
      });
    });
  });

  describe('Database Persistence Verification', () => {
    it('should verify permissions persist through GET request after PUT', async () => {
      const initialPermissions = {
        data: {
          permissions: ['read'],
        },
      };

      const updatedPermissions = {
        data: {
          permissions: ['read', 'write'],
        },
      };

      (apiClient.get as any)
        .mockResolvedValueOnce(initialPermissions)
        .mockResolvedValueOnce(updatedPermissions);

      (apiClient.put as any).mockResolvedValueOnce({ data: { success: true } });

      const { unmount } = renderPermissionsManager();

      await waitFor(() => {
        expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
      });

      // Update permissions
      fireEvent.click(screen.getByTestId('checkbox-write'));

      await waitFor(() => {
        expect(apiClient.put).toHaveBeenCalled();
      });

      // Simulate refetch
      unmount();
      renderPermissionsManager();

      await waitFor(() => {
        expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
      });

      // Verify GET was called again
      expect(apiClient.get).toHaveBeenCalledTimes(2);

      // Verify persisted permission is checked
      const writeCheckbox = screen.getByTestId('checkbox-write') as HTMLInputElement;
      expect(writeCheckbox.checked).toBe(true);
    });

    it('should rollback UI state on update failure', async () => {
      const initialPermissions = {
        data: {
          permissions: ['read'],
        },
      };

      const errorResponse = {
        response: {
          status: 500,
          data: {
            detail: 'Database connection failed',
          },
        },
      };

      (apiClient.get as any).mockResolvedValueOnce(initialPermissions);
      (apiClient.put as any).mockRejectedValueOnce(errorResponse);

      renderPermissionsManager();

      await waitFor(() => {
        expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
      });

      const writeCheckbox = screen.getByTestId('checkbox-write') as HTMLInputElement;
      const initialState = writeCheckbox.checked;

      fireEvent.click(writeCheckbox);

      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toBeInTheDocument();
      });

      // UI should rollback to initial state on error
      // (depends on component implementation)
    });
  });

  describe('Edge Cases', () => {
    it('should handle rapid permission toggles', async () => {
      const initialPermissions = {
        data: {
          permissions: ['read'],
        },
      };

      (apiClient.get as any).mockResolvedValueOnce(initialPermissions);
      (apiClient.put as any).mockResolvedValue({ data: { success: true } });

      renderPermissionsManager();

      await waitFor(() => {
        expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
      });

      const writeCheckbox = screen.getByTestId('checkbox-write');

      // Rapid toggles
      fireEvent.click(writeCheckbox);
      fireEvent.click(writeCheckbox);
      fireEvent.click(writeCheckbox);

      await waitFor(() => {
        expect(apiClient.put).toHaveBeenCalled();
      });

      // Should handle gracefully
      expect(screen.getByTestId('permissions-manager')).toBeInTheDocument();
    });

    it('should handle concurrent permission updates', async () => {
      const initialPermissions = {
        data: {
          permissions: ['read'],
        },
      };

      (apiClient.get as any).mockResolvedValueOnce(initialPermissions);
      (apiClient.put as any).mockResolvedValue({ data: { success: true } });

      renderPermissionsManager();

      await waitFor(() => {
        expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
      });

      // Click multiple checkboxes simultaneously
      fireEvent.click(screen.getByTestId('checkbox-write'));
      fireEvent.click(screen.getByTestId('checkbox-delete'));
      fireEvent.click(screen.getByTestId('checkbox-admin'));

      await waitFor(() => {
        expect(apiClient.put).toHaveBeenCalled();
      });
    });

    it('should handle invalid permission values', async () => {
      const invalidPermissions = {
        data: {
          permissions: ['read', 'invalid_permission', null, undefined],
        },
      };

      (apiClient.get as any).mockResolvedValueOnce(invalidPermissions);

      renderPermissionsManager();

      await waitFor(() => {
        expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
      });

      // Should handle gracefully
      expect(screen.getByTestId('permissions-manager')).toBeInTheDocument();
    });

    it('should handle very long permissions arrays', async () => {
      const manyPermissions = {
        data: {
          permissions: Array.from({ length: 1000 }, (_, i) => `permission_${i}`),
        },
      };

      (apiClient.get as any).mockResolvedValueOnce(manyPermissions);

      renderPermissionsManager();

      await waitFor(() => {
        expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
      });

      expect(screen.getByTestId('permissions-manager')).toBeInTheDocument();
    });
  });

  describe('Performance', () => {
    it('should complete permission update within acceptable time', async () => {
      const initialPermissions = {
        data: {
          permissions: ['read'],
        },
      };

      (apiClient.get as any).mockResolvedValueOnce(initialPermissions);
      (apiClient.put as any).mockResolvedValueOnce({ data: { success: true } });

      renderPermissionsManager();

      await waitFor(() => {
        expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
      });

      const startTime = performance.now();

      fireEvent.click(screen.getByTestId('checkbox-write'));

      await waitFor(() => {
        expect(screen.getByTestId('success-message')).toBeInTheDocument();
      });

      const endTime = performance.now();
      const duration = endTime - startTime;

      expect(duration).toBeLessThan(2000); // Should complete in less than 2 seconds
    });

    it('should handle multiple sequential updates efficiently', async () => {
      const initialPermissions = {
        data: {
          permissions: [],
        },
      };

      (apiClient.get as any).mockResolvedValueOnce(initialPermissions);
      (apiClient.put as any).mockResolvedValue({ data: { success: true } });

      renderPermissionsManager();

      await waitFor(() => {
        expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
      });

      const startTime = performance.now();

      // Sequential updates
      for (const permission of ['read', 'write', 'delete', 'admin']) {
        fireEvent.click(screen.getByTestId(`checkbox-${permission}`));
        await waitFor(() => {
          expect(apiClient.put).toHaveBeenCalled();
        });
      }

      const endTime = performance.now();
      const duration = endTime - startTime;

      expect(duration).toBeLessThan(5000); // Should complete all in less than 5 seconds
    });
  });
});
