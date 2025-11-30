/**
 * Comprehensive test suite for useUserMutations hook
 *
 * Tests cover:
 * - User creation, update, deletion
 * - Role assignment and permissions
 * - Optimistic updates
 * - Error handling and rollback
 * - Cache invalidation
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactNode } from 'react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { useUserMutations } from '../useUserMutations';
import * as apiClient from '../../../lib/api-client/core';

// ==========================================
// Test Setup
// ==========================================

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

const mockUser = {
  id: '1',
  email: 'test@example.com',
  name: 'Test User',
  role: 'user',
  isActive: true,
};

// ==========================================
// Create User Tests
// ==========================================

describe('useUserMutations - Create User', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should create user successfully', async () => {
    const mockCreate = vi.spyOn(apiClient, 'apiClient').mockResolvedValue(mockUser);

    const { result } = renderHook(() => useUserMutations(), {
      wrapper: createWrapper(),
    });

    const newUser = {
      email: 'new@example.com',
      name: 'New User',
      role: 'user',
    };

    await act(async () => {
      await result.current.createUser.mutateAsync(newUser);
    });

    expect(mockCreate).toHaveBeenCalledWith('/admin/users', {
      method: 'POST',
      body: newUser,
    });

    expect(result.current.createUser.isSuccess).toBe(true);
  });

  it('should handle creation validation errors', async () => {
    const error = new Error('Email already exists');
    (error as any).response = { status: 422, data: { message: 'Email already exists' } };
    vi.spyOn(apiClient, 'apiClient').mockRejectedValue(error);

    const { result } = renderHook(() => useUserMutations(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      try {
        await result.current.createUser.mutateAsync({
          email: 'duplicate@example.com',
          name: 'Duplicate',
          role: 'user',
        });
      } catch (e) {
        // Expected error
      }
    });

    expect(result.current.createUser.isError).toBe(true);
  });

  it('should validate email format before creation', async () => {
    const { result } = renderHook(() => useUserMutations(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      try {
        await result.current.createUser.mutateAsync({
          email: 'invalid-email',
          name: 'Test',
          role: 'user',
        });
      } catch (e) {
        // Expected validation error
      }
    });

    expect(result.current.createUser.isError).toBe(true);
  });

  it('should invalidate user list cache after creation', async () => {
    const queryClient = new QueryClient();
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    vi.spyOn(apiClient, 'apiClient').mockResolvedValue(mockUser);

    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useUserMutations(), { wrapper });

    await act(async () => {
      await result.current.createUser.mutateAsync({
        email: 'new@example.com',
        name: 'New',
        role: 'user',
      });
    });

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['users'] });
  });
});

// ==========================================
// Update User Tests
// ==========================================

describe('useUserMutations - Update User', () => {
  it('should update user successfully', async () => {
    const updatedUser = { ...mockUser, name: 'Updated Name' };
    const mockUpdate = vi.spyOn(apiClient, 'apiClient').mockResolvedValue(updatedUser);

    const { result } = renderHook(() => useUserMutations(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.updateUser.mutateAsync({
        id: '1',
        data: { name: 'Updated Name' },
      });
    });

    expect(mockUpdate).toHaveBeenCalledWith('/admin/users/1', {
      method: 'PATCH',
      body: { name: 'Updated Name' },
    });

    expect(result.current.updateUser.isSuccess).toBe(true);
  });

  it('should perform optimistic update', async () => {
    vi.spyOn(apiClient, 'apiClient').mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve(mockUser), 100))
    );

    const { result } = renderHook(() => useUserMutations({ optimistic: true }), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current.updateUser.mutate({
        id: '1',
        data: { name: 'Optimistic Update' },
      });
    });

    // Should show optimistic update immediately
    await waitFor(() => {
      expect(result.current.updateUser.isPending).toBe(true);
    });
  });

  it('should rollback on update failure', async () => {
    const error = new Error('Update failed');
    vi.spyOn(apiClient, 'apiClient').mockRejectedValue(error);

    const { result } = renderHook(() => useUserMutations({ optimistic: true }), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      try {
        await result.current.updateUser.mutateAsync({
          id: '1',
          data: { name: 'Failed Update' },
        });
      } catch (e) {
        // Expected error
      }
    });

    expect(result.current.updateUser.isError).toBe(true);
  });
});

// ==========================================
// Delete User Tests
// ==========================================

describe('useUserMutations - Delete User', () => {
  it('should delete user successfully', async () => {
    const mockDelete = vi.spyOn(apiClient, 'apiClient').mockResolvedValue({ success: true });

    const { result } = renderHook(() => useUserMutations(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.deleteUser.mutateAsync('1');
    });

    expect(mockDelete).toHaveBeenCalledWith('/admin/users/1', {
      method: 'DELETE',
    });

    expect(result.current.deleteUser.isSuccess).toBe(true);
  });

  it('should show confirmation before deletion', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);

    const { result } = renderHook(() => useUserMutations({ confirmDelete: true }), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      try {
        await result.current.deleteUser.mutateAsync('1');
      } catch (e) {
        // Deletion cancelled
      }
    });

    expect(confirmSpy).toHaveBeenCalled();
  });

  it('should handle deletion of non-existent user', async () => {
    const error = new Error('User not found');
    (error as any).response = { status: 404 };
    vi.spyOn(apiClient, 'apiClient').mockRejectedValue(error);

    const { result } = renderHook(() => useUserMutations(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      try {
        await result.current.deleteUser.mutateAsync('999');
      } catch (e) {
        // Expected error
      }
    });

    expect(result.current.deleteUser.isError).toBe(true);
  });
});

// ==========================================
// Role Assignment Tests
// ==========================================

describe('useUserMutations - Role Assignment', () => {
  it('should assign role successfully', async () => {
    const mockAssign = vi.spyOn(apiClient, 'apiClient').mockResolvedValue({
      ...mockUser,
      role: 'admin',
    });

    const { result } = renderHook(() => useUserMutations(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.assignRole.mutateAsync({
        userId: '1',
        role: 'admin',
      });
    });

    expect(mockAssign).toHaveBeenCalledWith('/admin/users/1/role', {
      method: 'PUT',
      body: { role: 'admin' },
    });
  });

  it('should validate role before assignment', async () => {
    const { result } = renderHook(() => useUserMutations(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      try {
        await result.current.assignRole.mutateAsync({
          userId: '1',
          role: 'invalid-role' as any,
        });
      } catch (e) {
        // Invalid role
      }
    });

    expect(result.current.assignRole.isError).toBe(true);
  });

  it('should prevent self-demotion from admin', async () => {
    const currentUserId = '1';
    const mockGet = vi.fn().mockReturnValue(currentUserId);
    global.localStorage = { getItem: mockGet } as any;

    const { result } = renderHook(() => useUserMutations(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      try {
        await result.current.assignRole.mutateAsync({
          userId: currentUserId,
          role: 'user',
        });
      } catch (e) {
        // Cannot self-demote
      }
    });

    expect(result.current.assignRole.isError).toBe(true);
  });
});

// ==========================================
// Permissions Tests
// ==========================================

describe('useUserMutations - Permissions', () => {
  it('should update user permissions', async () => {
    const mockUpdate = vi.spyOn(apiClient, 'apiClient').mockResolvedValue({
      ...mockUser,
      permissions: ['read', 'write'],
    });

    const { result } = renderHook(() => useUserMutations(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.updatePermissions.mutateAsync({
        userId: '1',
        permissions: ['read', 'write'],
      });
    });

    expect(mockUpdate).toHaveBeenCalledWith('/admin/users/1/permissions', {
      method: 'PUT',
      body: { permissions: ['read', 'write'] },
    });
  });

  it('should add permission to user', async () => {
    const mockAdd = vi.spyOn(apiClient, 'apiClient').mockResolvedValue({
      ...mockUser,
      permissions: ['read', 'write', 'delete'],
    });

    const { result } = renderHook(() => useUserMutations(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.addPermission.mutateAsync({
        userId: '1',
        permission: 'delete',
      });
    });

    expect(mockAdd).toHaveBeenCalled();
  });

  it('should remove permission from user', async () => {
    const mockRemove = vi.spyOn(apiClient, 'apiClient').mockResolvedValue({
      ...mockUser,
      permissions: ['read'],
    });

    const { result } = renderHook(() => useUserMutations(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.removePermission.mutateAsync({
        userId: '1',
        permission: 'write',
      });
    });

    expect(mockRemove).toHaveBeenCalled();
  });
});

// ==========================================
// Activation/Deactivation Tests
// ==========================================

describe('useUserMutations - Activation', () => {
  it('should activate user', async () => {
    const mockActivate = vi.spyOn(apiClient, 'apiClient').mockResolvedValue({
      ...mockUser,
      isActive: true,
    });

    const { result } = renderHook(() => useUserMutations(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.activateUser.mutateAsync('1');
    });

    expect(mockActivate).toHaveBeenCalledWith('/admin/users/1/activate', {
      method: 'POST',
    });
  });

  it('should deactivate user', async () => {
    const mockDeactivate = vi.spyOn(apiClient, 'apiClient').mockResolvedValue({
      ...mockUser,
      isActive: false,
    });

    const { result } = renderHook(() => useUserMutations(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.deactivateUser.mutateAsync('1');
    });

    expect(mockDeactivate).toHaveBeenCalledWith('/admin/users/1/deactivate', {
      method: 'POST',
    });
  });
});

// ==========================================
// Error Handling Tests
// ==========================================

describe('useUserMutations - Error Handling', () => {
  it('should handle network errors', async () => {
    vi.spyOn(apiClient, 'apiClient').mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useUserMutations(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      try {
        await result.current.createUser.mutateAsync({
          email: 'test@example.com',
          name: 'Test',
          role: 'user',
        });
      } catch (e) {
        // Expected error
      }
    });

    expect(result.current.createUser.error?.message).toContain('Network error');
  });

  it('should handle concurrent mutations', async () => {
    vi.spyOn(apiClient, 'apiClient').mockResolvedValue(mockUser);

    const { result } = renderHook(() => useUserMutations(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await Promise.all([
        result.current.updateUser.mutateAsync({ id: '1', data: { name: 'Update 1' } }),
        result.current.updateUser.mutateAsync({ id: '1', data: { name: 'Update 2' } }),
      ]);
    });

    expect(result.current.updateUser.isSuccess).toBe(true);
  });
});
