import React from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Card, CardContent } from '@/components/ui/card'
import { User, Bell, Palette, Globe, Shield, Database, LucideIcon } from 'lucide-react'

interface SettingsTab {
  id: string
  label: string
  icon: LucideIcon
  description: string
  path: string
}

const settingsTabs: SettingsTab[] = [
  {
    id: 'profile',
    label: 'Perfil',
    icon: User,
    description: 'Suas informações pessoais',
    path: '/settings/profile',
  },
  {
    id: 'notifications',
    label: 'Notificações',
    icon: Bell,
    description: 'Preferências de alerta',
    path: '/settings/notifications',
  },
  {
    id: 'appearance',
    label: 'Aparência',
    icon: Palette,
    description: 'Tema e interface',
    path: '/settings/appearance',
  },
  {
    id: 'language',
    label: 'Idioma & Região',
    icon: Globe,
    description: 'Localização e formato',
    path: '/settings/language',
  },
  {
    id: 'security',
    label: 'Segurança',
    icon: Shield,
    description: 'Senha e autenticação',
    path: '/settings/security',
  },
  {
    id: 'data',
    label: 'Dados & Privacidade',
    icon: Database,
    description: 'Gerenciar seus dados',
    path: '/settings/data',
  },
]

/**
 * Settings sidebar navigation component
 * Provides navigation between different settings sections with visual indicators
 */
export function SettingsSidebar() {
  const navigate = useNavigate()
  const location = useLocation()

  // Determine active tab from current path
  const getActiveTab = () => {
    const path = location.pathname
    const activeTab = settingsTabs.find((tab) => path.includes(tab.id))
    return activeTab?.id || 'profile'
  }

  const activeTab = getActiveTab()

  const handleTabClick = (tab: SettingsTab) => {
    navigate(tab.path)
  }

  return (
    <Card className="sticky top-6">
      <CardContent className="p-2">
        <nav className="space-y-1">
          {settingsTabs.map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id

            return (
              <button
                key={tab.id}
                onClick={() => handleTabClick(tab)}
                className={`w-full flex items-start gap-3 px-3 py-3 text-sm font-medium text-left transition-[background-color,color,box-shadow] rounded-lg ${
                  isActive ? 'bg-blue-50 text-blue-700 shadow-sm' : 'text-gray-700 hover:bg-gray-50'
                }`}
              >
                <div className={`p-2 rounded-lg ${isActive ? 'bg-blue-100' : 'bg-gray-100'}`}>
                  <Icon className="h-4 w-4" />
                </div>
                <div className="flex-1 text-left">
                  <div className="font-medium">{tab.label}</div>
                  <div className="text-xs text-gray-500 mt-0.5">{tab.description}</div>
                </div>
              </button>
            )
          })}
        </nav>
      </CardContent>
    </Card>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export { settingsTabs }
export type { SettingsTab }
