import React from 'react'
import { TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Activity, Settings, Users, Database, Shield } from 'lucide-react'

/**
 * AdminTabNavigation - Tab navigation component for admin panel
 *
 * Provides consistent tab navigation with icons and labels
 * for all admin panel sections
 *
 * Responsive behavior:
 * - Mobile (< 640px): 2 columns, icon-only on first row
 * - Tablet (640px - 1024px): 3 columns
 * - Desktop (>= 1024px): 5 columns, full labels
 */
export default function AdminTabNavigation() {
  return (
    <TabsList className="grid w-full grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 h-auto p-1 gap-1">
      <TabsTrigger value="monitoring" className="flex flex-col items-center gap-1 py-2 sm:py-3">
        <Activity className="h-4 w-4 sm:h-5 sm:w-5" />
        <span className="text-[10px] sm:text-xs leading-tight text-center">
          Monitoramento
        </span>
      </TabsTrigger>
      <TabsTrigger value="settings" className="flex flex-col items-center gap-1 py-2 sm:py-3">
        <Settings className="h-4 w-4 sm:h-5 sm:w-5" />
        <span className="text-[10px] sm:text-xs leading-tight text-center">
          Configurações
        </span>
      </TabsTrigger>
      <TabsTrigger value="users" className="flex flex-col items-center gap-1 py-2 sm:py-3">
        <Users className="h-4 w-4 sm:h-5 sm:w-5" />
        <span className="text-[10px] sm:text-xs leading-tight text-center">
          Usuários
        </span>
      </TabsTrigger>
      <TabsTrigger value="database" className="flex flex-col items-center gap-1 py-2 sm:py-3">
        <Database className="h-4 w-4 sm:h-5 sm:w-5" />
        <span className="text-[10px] sm:text-xs leading-tight text-center">
          Dados
        </span>
      </TabsTrigger>
      <TabsTrigger value="security" className="flex flex-col items-center gap-1 py-2 sm:py-3">
        <Shield className="h-4 w-4 sm:h-5 sm:w-5" />
        <span className="text-[10px] sm:text-xs leading-tight text-center">
          Segurança
        </span>
      </TabsTrigger>
    </TabsList>
  )
}
