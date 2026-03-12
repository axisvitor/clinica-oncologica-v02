import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ApiError } from '@/lib/api-client/core'
import { usePasswordChange } from '@/hooks/useSettings'

const mockApiClient = vi.hoisted(() => ({
  request: vi.fn(),
  clearAuthToken: vi.fn(),
}))

const mockWsManager = vi.hoisted(() => ({
  disconnect: vi.fn(),
}))

const mockToast = vi.hoisted(() => vi.fn())

vi.mock('@/lib/api-client', () => ({
  apiClient: mockApiClient,
}))

vi.mock('@/lib/websocket', () => ({
  wsManager: mockWsManager,
}))

vi.mock('@/hooks/use-toast', () => ({
  toast: mockToast,
}))

const storageState = new Map<string, string>()
const localStorageMock = {
  getItem: vi.fn((key: string) => storageState.get(key) ?? null),
  setItem: vi.fn((key: string, value: string) => {
    storageState.set(key, value)
  }),
  removeItem: vi.fn((key: string) => {
    storageState.delete(key)
  }),
}

Object.defineProperty(globalThis, 'localStorage', {
  value: localStorageMock,
  configurable: true,
})

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

describe('usePasswordChange', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    storageState.clear()
  })

  it('submits the first-party password-change payload and clears local session artifacts on success', async () => {
    mockApiClient.request.mockResolvedValue({
      success: true,
      message: 'Password changed successfully',
    })
    localStorage.setItem('session_id', 'session-password-change-123')

    const { result } = renderHook(() => usePasswordChange(), {
      wrapper: createWrapper(),
    })

    await act(async () => {
      await result.current.changePassword({
        current_password: 'CurrentPass123!',
        new_password: 'NextPass123!',
        confirm_password: 'NextPass123!',
      })
    })

    expect(mockApiClient.request).toHaveBeenCalledWith('/api/v2/auth/password', {
      method: 'PUT',
      body: JSON.stringify({
        current_password: 'CurrentPass123!',
        new_password: 'NextPass123!',
      }),
    })
    expect(mockApiClient.clearAuthToken).toHaveBeenCalledTimes(1)
    expect(mockWsManager.disconnect).toHaveBeenCalledTimes(1)
    expect(localStorage.getItem('session_id')).toBeNull()
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Senha alterada',
        description: 'Sua senha foi alterada. Faça login novamente para continuar.',
      })
    )
  })

  it('surfaces stable backend diagnostics without clearing session state on failure', async () => {
    mockApiClient.request.mockRejectedValue(
      new ApiError(
        400,
        {
          error: 'AUTH_PASSWORD_CURRENT_PASSWORD_INVALID',
          message: 'Current password is incorrect.',
          request_id: 'req-password-400',
        },
        'Current password is incorrect.',
        'Current password is incorrect.'
      )
    )
    localStorage.setItem('session_id', 'session-still-valid')

    const { result } = renderHook(() => usePasswordChange(), {
      wrapper: createWrapper(),
    })

    await expect(
      act(async () => {
        await result.current.changePassword({
          current_password: 'WrongPass123!',
          new_password: 'NextPass123!',
          confirm_password: 'NextPass123!',
        })
      })
    ).rejects.toMatchObject({
      message: 'Current password is incorrect.',
    })

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Erro ao alterar senha',
          description: 'Current password is incorrect.',
          variant: 'destructive',
        })
      )
    })

    expect(mockApiClient.clearAuthToken).not.toHaveBeenCalled()
    expect(mockWsManager.disconnect).not.toHaveBeenCalled()
    expect(localStorage.getItem('session_id')).toBe('session-still-valid')
  })
})
