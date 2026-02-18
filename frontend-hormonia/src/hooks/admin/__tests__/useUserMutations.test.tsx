import { act, renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useUserMutations } from '../useUserMutations';
import { apiClient } from '@/lib/api-client';

const toastMock = vi.fn();

vi.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

vi.mock('@/lib/utils/security/password-generator', () => ({
  generateTemporaryPassword: vi.fn(() => 'Temp1234!'),
}));

vi.mock('@/lib/api-client', () => ({
  apiClient: {
    adminUsers: {
      create: vi.fn(),
      update: vi.fn(),
      delete: vi.fn(),
      activate: vi.fn(),
      deactivate: vi.fn(),
      updatePermissions: vi.fn(),
      resetPassword: vi.fn(),
    },
  },
}));

function createWrapper(queryClient: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useUserMutations', () => {
  const mockAdminUsers = apiClient.adminUsers;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('creates user and invalidates caches', async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        mutations: { retry: false },
      },
    });
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    vi.mocked(mockAdminUsers.create).mockResolvedValue({
      id: 'u1',
      full_name: 'Ana Silva',
      email: 'ana@example.com',
    } as any);

    const { result } = renderHook(() => useUserMutations(), {
      wrapper: createWrapper(queryClient),
    });

    await act(async () => {
      await result.current.createUserAsync({
        full_name: 'Ana Silva',
        email: 'ana@example.com',
        role: 'admin',
      });
    });

    expect(mockAdminUsers.create).toHaveBeenCalledWith(
      expect.objectContaining({ email: 'ana@example.com' })
    );
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['admin-users'] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['admin-stats'] });
    expect(toastMock).toHaveBeenCalled();
  });

  it('updates and deletes user through canonical API', async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        mutations: { retry: false },
      },
    });

    vi.mocked(mockAdminUsers.update).mockResolvedValue({ id: 'u1' } as any);
    vi.mocked(mockAdminUsers.delete).mockResolvedValue({ message: 'ok' } as any);

    const { result } = renderHook(() => useUserMutations(), {
      wrapper: createWrapper(queryClient),
    });

    await act(async () => {
      await result.current.updateUserAsync({
        id: 'u1',
        userData: { full_name: 'Ana Souza' },
      });
    });

    await act(async () => {
      await result.current.deleteUserAsync('u1');
    });

    expect(mockAdminUsers.update).toHaveBeenCalledWith('u1', {
      full_name: 'Ana Souza',
    });
    expect(mockAdminUsers.delete).toHaveBeenCalledWith('u1');
  });

  it('resets password and returns generated temporary password', async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        mutations: { retry: false },
      },
    });

    vi.mocked(mockAdminUsers.resetPassword).mockResolvedValue({
      message: 'ok',
    } as any);

    const { result } = renderHook(() => useUserMutations(), {
      wrapper: createWrapper(queryClient),
    });

    let response: { temporary_password: string } | undefined;

    await act(async () => {
      response = await result.current.resetPasswordAsync('u1');
    });

    expect(mockAdminUsers.resetPassword).toHaveBeenCalledWith('u1', {
      new_password: 'Temp1234!',
      force_change: true,
    });
    expect(response).toEqual({ temporary_password: 'Temp1234!' });
  });
});
