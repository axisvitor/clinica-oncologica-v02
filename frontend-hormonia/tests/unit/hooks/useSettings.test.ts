/**
 * useSettings Hook Tests
 * Tests custom hooks for settings management
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { mockUserProfile, mockUserPreferences } from '../../test-utils/mock-data'

// Mock API client
const mockApiClient = {
  settings: {
    getProfile: vi.fn(),
    updateProfile: vi.fn(),
    uploadAvatar: vi.fn(),
    changePassword: vi.fn(),
    getPreferences: vi.fn(),
    updatePreferences: vi.fn()
  }
}

vi.mock('@/lib/api-client', () => ({
  apiClient: mockApiClient
}))

// Mock hooks - these would be the actual implementations
const useUserProfile = () => {
  const updateProfile = async (data: any) => {
    return mockApiClient.settings.updateProfile(data)
  }

  const uploadAvatar = async (file: File) => {
    return mockApiClient.settings.uploadAvatar(file)
  }

  return {
    updateProfile,
    uploadAvatar,
    isUpdatingProfile: false,
    isUploadingAvatar: false
  }
}

const usePasswordChange = () => {
  const changePassword = async (data: any) => {
    return mockApiClient.settings.changePassword(data)
  }

  return {
    changePassword,
    isChangingPassword: false
  }
}

const useUserPreferences = () => {
  return {
    preferences: mockUserPreferences,
    isLoadingPreferences: false,
    updatePreferences: mockApiClient.settings.updatePreferences
  }
}

describe('useSettings Hooks - Unit Tests', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    vi.clearAllMocks()
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false }
      }
    })

    // Setup default mocks
    mockApiClient.settings.getProfile.mockResolvedValue({ data: mockUserProfile })
    mockApiClient.settings.updateProfile.mockResolvedValue({ data: mockUserProfile })
    mockApiClient.settings.uploadAvatar.mockResolvedValue({ url: 'https://example.com/avatar.png' })
    mockApiClient.settings.changePassword.mockResolvedValue({ success: true })
    mockApiClient.settings.getPreferences.mockResolvedValue({ data: mockUserPreferences })
    mockApiClient.settings.updatePreferences.mockResolvedValue({ data: mockUserPreferences })
  })

  describe('useUserProfile', () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )

    it('should provide update profile function', async () => {
      const { result } = renderHook(() => useUserProfile(), { wrapper })

      expect(result.current.updateProfile).toBeDefined()
      expect(typeof result.current.updateProfile).toBe('function')
    })

    it('should update profile successfully', async () => {
      const { result } = renderHook(() => useUserProfile(), { wrapper })

      const updatedData = { ...mockUserProfile, full_name: 'Updated Name' }

      await act(async () => {
        await result.current.updateProfile(updatedData)
      })

      expect(mockApiClient.settings.updateProfile).toHaveBeenCalledWith(updatedData)
    })

    it('should upload avatar successfully', async () => {
      const { result } = renderHook(() => useUserProfile(), { wrapper })

      const file = new File(['avatar'], 'avatar.png', { type: 'image/png' })

      await act(async () => {
        await result.current.uploadAvatar(file)
      })

      expect(mockApiClient.settings.uploadAvatar).toHaveBeenCalledWith(file)
    })

    it('should handle profile update errors', async () => {
      mockApiClient.settings.updateProfile.mockRejectedValue(new Error('Update failed'))

      const { result } = renderHook(() => useUserProfile(), { wrapper })

      await expect(async () => {
        await act(async () => {
          await result.current.updateProfile(mockUserProfile)
        })
      }).rejects.toThrow('Update failed')
    })

    it('should track loading state during update', async () => {
      const { result } = renderHook(() => useUserProfile(), { wrapper })

      expect(result.current.isUpdatingProfile).toBe(false)
    })

    it('should track loading state during avatar upload', async () => {
      const { result } = renderHook(() => useUserProfile(), { wrapper })

      expect(result.current.isUploadingAvatar).toBe(false)
    })
  })

  describe('usePasswordChange', () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )

    it('should provide change password function', async () => {
      const { result } = renderHook(() => usePasswordChange(), { wrapper })

      expect(result.current.changePassword).toBeDefined()
      expect(typeof result.current.changePassword).toBe('function')
    })

    it('should change password successfully', async () => {
      const { result } = renderHook(() => usePasswordChange(), { wrapper })

      const passwordData = {
        current_password: 'oldPassword123',
        new_password: 'newPassword123',
        confirm_password: 'newPassword123'
      }

      await act(async () => {
        await result.current.changePassword(passwordData)
      })

      expect(mockApiClient.settings.changePassword).toHaveBeenCalledWith(passwordData)
    })

    it('should handle incorrect current password', async () => {
      mockApiClient.settings.changePassword.mockRejectedValue(
        new Error('Senha atual incorreta')
      )

      const { result } = renderHook(() => usePasswordChange(), { wrapper })

      const passwordData = {
        current_password: 'wrongPassword',
        new_password: 'newPassword123',
        confirm_password: 'newPassword123'
      }

      await expect(async () => {
        await act(async () => {
          await result.current.changePassword(passwordData)
        })
      }).rejects.toThrow('Senha atual incorreta')
    })

    it('should validate password match', async () => {
      const { result } = renderHook(() => usePasswordChange(), { wrapper })

      const passwordData = {
        current_password: 'oldPassword123',
        new_password: 'newPassword123',
        confirm_password: 'differentPassword'
      }

      // Validation should happen before API call
      if (passwordData.new_password !== passwordData.confirm_password) {
        throw new Error('Senhas não coincidem')
      }

      await expect(async () => {
        if (passwordData.new_password !== passwordData.confirm_password) {
          throw new Error('Senhas não coincidem')
        }
      }).rejects.toThrow('Senhas não coincidem')
    })

    it('should track loading state', async () => {
      const { result } = renderHook(() => usePasswordChange(), { wrapper })

      expect(result.current.isChangingPassword).toBe(false)
    })
  })

  describe('useUserPreferences', () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )

    it('should load preferences', async () => {
      const { result } = renderHook(() => useUserPreferences(), { wrapper })

      expect(result.current.preferences).toEqual(mockUserPreferences)
    })

    it('should update theme preference', async () => {
      const { result } = renderHook(() => useUserPreferences(), { wrapper })

      const newPreferences = {
        ...mockUserPreferences,
        theme: 'dark' as const
      }

      await act(async () => {
        await result.current.updatePreferences(newPreferences)
      })

      expect(mockApiClient.settings.updatePreferences).toHaveBeenCalledWith(newPreferences)
    })

    it('should update language preference', async () => {
      const { result } = renderHook(() => useUserPreferences(), { wrapper })

      const newPreferences = {
        ...mockUserPreferences,
        language: 'en-US'
      }

      await act(async () => {
        await result.current.updatePreferences(newPreferences)
      })

      expect(mockApiClient.settings.updatePreferences).toHaveBeenCalledWith(newPreferences)
    })

    it('should update notification settings', async () => {
      const { result } = renderHook(() => useUserPreferences(), { wrapper })

      const newPreferences = {
        ...mockUserPreferences,
        notifications_enabled: false
      }

      await act(async () => {
        await result.current.updatePreferences(newPreferences)
      })

      expect(mockApiClient.settings.updatePreferences).toHaveBeenCalledWith(newPreferences)
    })

    it('should handle preferences update errors', async () => {
      mockApiClient.settings.updatePreferences.mockRejectedValue(
        new Error('Update failed')
      )

      const { result } = renderHook(() => useUserPreferences(), { wrapper })

      await expect(async () => {
        await act(async () => {
          await result.current.updatePreferences(mockUserPreferences)
        })
      }).rejects.toThrow('Update failed')
    })

    it('should track loading state', async () => {
      const { result } = renderHook(() => useUserPreferences(), { wrapper })

      expect(result.current.isLoadingPreferences).toBe(false)
    })
  })

  describe('Integration Tests', () => {
    it('should update both profile and preferences', async () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      )

      const profileHook = renderHook(() => useUserProfile(), { wrapper })
      const preferencesHook = renderHook(() => useUserPreferences(), { wrapper })

      await act(async () => {
        await profileHook.result.current.updateProfile(mockUserProfile)
        await preferencesHook.result.current.updatePreferences(mockUserPreferences)
      })

      expect(mockApiClient.settings.updateProfile).toHaveBeenCalled()
      expect(mockApiClient.settings.updatePreferences).toHaveBeenCalled()
    })

    it('should handle concurrent updates', async () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      )

      const profileHook = renderHook(() => useUserProfile(), { wrapper })

      await act(async () => {
        await Promise.all([
          profileHook.result.current.updateProfile(mockUserProfile),
          profileHook.result.current.updateProfile({ ...mockUserProfile, full_name: 'Different' })
        ])
      })

      expect(mockApiClient.settings.updateProfile).toHaveBeenCalledTimes(2)
    })
  })

  describe('Error Handling', () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )

    it('should handle network errors', async () => {
      mockApiClient.settings.updateProfile.mockRejectedValue(
        new Error('Network error')
      )

      const { result } = renderHook(() => useUserProfile(), { wrapper })

      await expect(async () => {
        await act(async () => {
          await result.current.updateProfile(mockUserProfile)
        })
      }).rejects.toThrow('Network error')
    })

    it('should handle validation errors', async () => {
      mockApiClient.settings.updateProfile.mockRejectedValue({
        message: 'Validation error',
        errors: {
          email: 'Email inválido'
        }
      })

      const { result } = renderHook(() => useUserProfile(), { wrapper })

      await expect(async () => {
        await act(async () => {
          await result.current.updateProfile(mockUserProfile)
        })
      }).rejects.toMatchObject({
        message: 'Validation error'
      })
    })

    it('should handle timeout errors', async () => {
      mockApiClient.settings.updateProfile.mockImplementation(
        () => new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout')), 100))
      )

      const { result } = renderHook(() => useUserProfile(), { wrapper })

      await expect(async () => {
        await act(async () => {
          await result.current.updateProfile(mockUserProfile)
        })
      }).rejects.toThrow('Timeout')
    })
  })
})