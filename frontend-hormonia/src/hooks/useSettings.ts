import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../lib/api-client'
import { createLogger } from '../lib/logger'
import { toast } from './use-toast'

const logger = createLogger('useSettings')

// Types for settings
export interface UserProfile {
  id: string
  email: string
  full_name: string
  phone?: string
  specialty?: string
  avatar_url?: string
}

// Frontend preferences format (with nesting and UI-specific fields)
export interface UserPreferences {
  theme: 'light' | 'dark' | 'system'
  accent_color: 'blue' | 'green' | 'purple' | 'orange' | 'red'
  density: 'compact' | 'comfortable' | 'spacious'
  language: string
  timezone: string
  date_format: string
  notifications: {
    new_alerts: boolean
    patient_messages: boolean
    reports_completed: boolean
    quiz_completed: boolean
    browser_notifications: boolean
    email_notifications: boolean
  }
}

// Backend preferences format (flat structure)
// IMPORTANT: Only includes fields that backend actually supports
// See backend-hormonia/app/api/v2/auth.py UserPreferences model (lines 31-44)
export interface BackendUserPreferences {
  theme: 'light' | 'dark' | 'system'
  language: string
  timezone: string
  notification_email: boolean
  notification_sms: boolean
  notification_whatsapp: boolean
}

export interface PasswordChangeData {
  current_password: string
  new_password: string
  confirm_password: string
}

// Frontend-only preferences stored in localStorage
interface FrontendOnlyPreferences {
  accent_color: 'blue' | 'green' | 'purple' | 'orange' | 'red'
  density: 'compact' | 'comfortable' | 'spacious'
  date_format: string
  notification_new_alerts: boolean
  notification_patient_messages: boolean
  notification_reports_completed: boolean
  notification_quiz_completed: boolean
}

// Helper to load frontend-only preferences from localStorage
function loadFrontendOnlyPreferences(): Partial<FrontendOnlyPreferences> {
  try {
    const stored = localStorage.getItem('frontend_only_preferences')
    return stored ? JSON.parse(stored) : {}
  } catch {
    return {}
  }
}

// Helper to save frontend-only preferences to localStorage
function saveFrontendOnlyPreferences(prefs: Partial<FrontendOnlyPreferences>) {
  try {
    const current = loadFrontendOnlyPreferences()
    const updated = { ...current, ...prefs }
    localStorage.setItem('frontend_only_preferences', JSON.stringify(updated))
  } catch (error) {
    logger.error('Failed to save frontend-only preferences', { error })
  }
}

// Mapper functions to convert between frontend and backend formats
function mapBackendToFrontend(backend: BackendUserPreferences): UserPreferences {
  const frontendOnly = loadFrontendOnlyPreferences()

  return {
    theme: backend.theme,
    accent_color: frontendOnly.accent_color ?? 'blue',
    density: frontendOnly.density ?? 'comfortable',
    language: backend.language,
    timezone: backend.timezone,
    date_format: frontendOnly.date_format ?? 'DD/MM/YYYY',
    notifications: {
      new_alerts: frontendOnly.notification_new_alerts ?? false,
      patient_messages: frontendOnly.notification_patient_messages ?? false,
      reports_completed: frontendOnly.notification_reports_completed ?? false,
      quiz_completed: frontendOnly.notification_quiz_completed ?? false,
      browser_notifications: false, // Not supported by backend
      email_notifications: backend.notification_email ?? false,
    },
  }
}

function mapFrontendToBackend(frontend: Partial<UserPreferences>): Partial<BackendUserPreferences> {
  const backend: Partial<BackendUserPreferences> = {}

  // Map only supported backend fields
  if (frontend.theme !== undefined) backend.theme = frontend.theme
  if (frontend.language !== undefined) backend.language = frontend.language
  if (frontend.timezone !== undefined) backend.timezone = frontend.timezone

  // Map only supported notification fields
  if (frontend.notifications) {
    const notif = frontend.notifications
    if (notif.email_notifications !== undefined)
      backend.notification_email = notif.email_notifications
    // notification_sms and notification_whatsapp are not currently used in frontend
  }

  return backend
}

function extractFrontendOnlyPreferences(
  frontend: Partial<UserPreferences>
): Partial<FrontendOnlyPreferences> {
  const frontendOnly: Partial<FrontendOnlyPreferences> = {}

  // Extract UI-only fields
  if (frontend.accent_color !== undefined) frontendOnly.accent_color = frontend.accent_color
  if (frontend.density !== undefined) frontendOnly.density = frontend.density
  if (frontend.date_format !== undefined) frontendOnly.date_format = frontend.date_format

  // Extract frontend-only notification toggles
  if (frontend.notifications) {
    const notif = frontend.notifications
    if (notif.new_alerts !== undefined) frontendOnly.notification_new_alerts = notif.new_alerts
    if (notif.patient_messages !== undefined)
      frontendOnly.notification_patient_messages = notif.patient_messages
    if (notif.reports_completed !== undefined)
      frontendOnly.notification_reports_completed = notif.reports_completed
    if (notif.quiz_completed !== undefined)
      frontendOnly.notification_quiz_completed = notif.quiz_completed
  }

  return frontendOnly
}

// Extended API client with settings endpoints
const settingsApi = {
  // Profile endpoints
  updateProfile: async (data: Partial<UserProfile>) => {
    const response = await apiClient.request<UserProfile>('/api/v2/auth/profile', {
      method: 'PUT',
      body: JSON.stringify(data),
    })
    return response
  },

  // Password change endpoint - Backend only needs new_password
  // Firebase reauthentication should be done before calling this
  changePassword: async (data: PasswordChangeData) => {
    // Note: Backend expects only new_password and handles reauthentication via Firebase
    // The current_password should be used for Firebase reauthentication on the client side
    const response = await apiClient.request<{ message: string }>('/api/v2/auth/password', {
      method: 'PUT',
      body: JSON.stringify({
        new_password: data.new_password,
      }),
    })
    return response
  },

  // User preferences endpoints
  getPreferences: async (): Promise<UserPreferences> => {
    const response = await apiClient.request<{
      user_id: string
      preferences: BackendUserPreferences
      updated_at: string
    }>('/api/v2/users/preferences')
    // Backend returns { user_id, preferences, updated_at } - extract and map preferences
    return mapBackendToFrontend(response.preferences)
  },

  updatePreferences: async (data: Partial<UserPreferences>) => {
    // Extract and save frontend-only preferences to localStorage
    const frontendOnly = extractFrontendOnlyPreferences(data)
    if (Object.keys(frontendOnly).length > 0) {
      saveFrontendOnlyPreferences(frontendOnly)
    }

    // Convert frontend format to backend format
    const backendData = mapFrontendToBackend(data)

    // If there are no backend fields to update, skip the API call
    if (Object.keys(backendData).length === 0) {
      // Return current preferences (frontend-only update)
      const currentPrefs = await settingsApi.getPreferences()
      return currentPrefs
    }

    // Use PATCH for partial updates (backend supports this)
    const response = await apiClient.request<{
      user_id: string
      preferences: BackendUserPreferences
      updated_at: string
    }>('/api/v2/users/preferences', {
      method: 'PATCH',
      body: JSON.stringify(backendData),
    })
    // Backend returns { user_id, preferences, updated_at } - extract and map preferences
    return mapBackendToFrontend(response.preferences)
  },

  // Avatar upload endpoint
  uploadAvatar: async (file: File) => {
    const formData = new FormData()
    formData.append('file', file) // Backend expects 'file' parameter

    const response = await apiClient.request<{ avatar_url: string }>('/api/v2/auth/avatar', {
      method: 'POST',
      body: formData,
      // Don't set headers - browser will set correct multipart boundary
    })
    return response
  },
}

// Hook for user profile management
export function useUserProfile() {
  const queryClient = useQueryClient()

  const updateProfileMutation = useMutation({
    mutationFn: settingsApi.updateProfile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['auth', 'me'] })
      toast({
        title: 'Perfil atualizado',
        description: 'Suas informações foram atualizadas com sucesso.',
      })
    },
    onError: (error: unknown) => {
      const errorMessage =
        error instanceof Error ? error.message : 'Não foi possível atualizar suas informações.'
      toast({
        title: 'Erro ao atualizar perfil',
        description: errorMessage,
        variant: 'destructive',
      })
    },
  })

  const uploadAvatarMutation = useMutation({
    mutationFn: settingsApi.uploadAvatar,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['auth', 'me'] })
      toast({
        title: 'Avatar atualizado',
        description: 'Sua foto de perfil foi atualizada com sucesso.',
      })
    },
    onError: (error: unknown) => {
      const errorMessage =
        error instanceof Error ? error.message : 'Não foi possível fazer o upload da imagem.'
      toast({
        title: 'Erro ao fazer upload',
        description: errorMessage,
        variant: 'destructive',
      })
    },
  })

  return {
    updateProfile: updateProfileMutation.mutate,
    uploadAvatar: uploadAvatarMutation.mutate,
    isUpdatingProfile: updateProfileMutation.isPending,
    isUploadingAvatar: uploadAvatarMutation.isPending,
  }
}

// Hook for password management
export function usePasswordChange() {
  const changePasswordMutation = useMutation({
    mutationFn: settingsApi.changePassword,
    onSuccess: () => {
      toast({
        title: 'Senha alterada',
        description: 'Sua senha foi alterada com sucesso.',
      })
    },
    onError: (error: unknown) => {
      const errorMessage =
        error instanceof Error ? error.message : 'Não foi possível alterar sua senha.'
      toast({
        title: 'Erro ao alterar senha',
        description: errorMessage,
        variant: 'destructive',
      })
    },
  })

  return {
    changePassword: changePasswordMutation.mutate,
    isChangingPassword: changePasswordMutation.isPending,
  }
}

// Hook for user preferences
export function useUserPreferences() {
  const queryClient = useQueryClient()

  const preferencesQuery = useQuery({
    queryKey: ['user', 'preferences'],
    queryFn: settingsApi.getPreferences,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })

  const updatePreferencesMutation = useMutation({
    mutationFn: settingsApi.updatePreferences,
    onSuccess: (updatedData: UserPreferences) => {
      queryClient.setQueryData(['user', 'preferences'], updatedData)
      toast({
        title: 'Preferências salvas',
        description: 'Suas preferências foram salvas com sucesso.',
      })
    },
    onError: (error: unknown) => {
      const errorMessage =
        error instanceof Error ? error.message : 'Não foi possível salvar suas preferências.'
      toast({
        title: 'Erro ao salvar preferências',
        description: errorMessage,
        variant: 'destructive',
      })
    },
  })

  return {
    preferences: preferencesQuery.data,
    isLoadingPreferences: preferencesQuery.isLoading,
    updatePreferences: updatePreferencesMutation.mutate,
    isUpdatingPreferences: updatePreferencesMutation.isPending,
  }
}

// Hook for theme management (localStorage + preferences)
export function useTheme() {
  const { preferences, updatePreferences } = useUserPreferences()

  const setTheme = (theme: UserPreferences['theme']) => {
    // Update localStorage immediately for instant feedback
    localStorage.setItem('theme', theme)

    // Apply theme class to document
    const root = document.documentElement
    root.classList.remove('light', 'dark')

    if (theme === 'system') {
      const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light'
      root.classList.add(systemTheme)
    } else {
      root.classList.add(theme)
    }

    // Update preferences in backend
    updatePreferences({ theme })
  }

  const setAccentColor = (accent_color: UserPreferences['accent_color']) => {
    // Update localStorage immediately
    localStorage.setItem('accent-color', accent_color)

    // Apply CSS custom property
    document.documentElement.style.setProperty('--accent-color', accent_color)

    // Update preferences in backend
    updatePreferences({ accent_color })
  }

  return {
    theme: preferences?.theme || localStorage.getItem('theme') || 'light',
    accentColor: preferences?.accent_color || localStorage.getItem('accent-color') || 'blue',
    setTheme,
    setAccentColor,
  }
}

// Hook for notifications preferences
export function useNotificationPreferences() {
  const { preferences, updatePreferences } = useUserPreferences()

  const updateNotificationSetting = (
    key: keyof UserPreferences['notifications'],
    value: boolean
  ) => {
    const currentNotifications = preferences?.notifications || {
      new_alerts: true,
      patient_messages: true,
      reports_completed: true,
      quiz_completed: true,
      browser_notifications: true,
      email_notifications: false,
    }

    updatePreferences({
      notifications: {
        ...currentNotifications,
        [key]: value,
      },
    })
  }

  return {
    notifications: preferences?.notifications,
    updateNotificationSetting,
  }
}
