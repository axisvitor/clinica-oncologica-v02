import React, { useEffect } from 'react'
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { toast } from '@/hooks/use-toast'
import { Save } from 'lucide-react'
import { SettingsSidebar } from '@/features/settings/SettingsSidebar'
import {
  ProfileSettings,
  NotificationSettings,
  AppearanceSettings,
  LanguageSettings,
  SecuritySettings,
  DataPrivacySettings,
} from '@/features/settings'

/**
 * Settings Page Component
 * Main settings layout with sidebar navigation and routed sections
 *
 * Refactored from 833 lines to ~180 lines by extracting feature-based components
 * Each settings section is now a self-contained component with its own logic
 */
export function SettingsPage() {
  const navigate = useNavigate()
  const location = useLocation()

  // Redirect to profile if accessing /settings directly
  useEffect(() => {
    if (location.pathname === '/settings' || location.pathname === '/settings/') {
      navigate('/settings/profile', { replace: true })
    }
  }, [location.pathname, navigate])

  const handleSaveAll = () => {
    toast({
      title: 'Configurações salvas',
      description: 'Todas as suas preferências foram salvas automaticamente.'
    })
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Configurações</h1>
          <p className="text-gray-600 mt-1">
            Personalize sua experiência e gerencie suas preferências
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={handleSaveAll}>
          <Save className="mr-2 h-4 w-4" />
          Salvar Tudo
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar Navigation */}
        <div className="lg:col-span-1">
          <SettingsSidebar />
        </div>

        {/* Content Area with Nested Routes */}
        <div className="lg:col-span-3">
          <Routes>
            <Route path="profile" element={<ProfileSettings />} />
            <Route path="notifications" element={<NotificationSettings />} />
            <Route path="appearance" element={<AppearanceSettings />} />
            <Route path="language" element={<LanguageSettings />} />
            <Route path="security" element={<SecuritySettings />} />
            <Route path="data" element={<DataPrivacySettings />} />
            <Route path="*" element={<Navigate to="/settings/profile" replace />} />
          </Routes>
        </div>
      </div>
    </div>
  )
}
