import React from 'react'
import { TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Activity, Settings, Users, Database, Shield } from 'lucide-react'

/**
 * AdminTabNavigation - Tab navigation component for admin panel
 *
 * Provides consistent tab navigation with icons and labels
 * for all admin panel sections
 */
export default function AdminTabNavigation() {
  return (
    <TabsList className="grid w-full grid-cols-5 h-auto p-1">
      <TabsTrigger value="monitoring" className="flex flex-col items-center gap-1 py-3">
        <Activity className="h-5 w-5" />
        <span className="text-xs">Monitoramento</span>
      </TabsTrigger>
      <TabsTrigger value="settings" className="flex flex-col items-center gap-1 py-3">
        <Settings className="h-5 w-5" />
        <span className="text-xs">Configurações</span>
      </TabsTrigger>
      <TabsTrigger value="users" className="flex flex-col items-center gap-1 py-3">
        <Users className="h-5 w-5" />
        <span className="text-xs">Usuários</span>
      </TabsTrigger>
      <TabsTrigger value="database" className="flex flex-col items-center gap-1 py-3">
        <Database className="h-5 w-5" />
        <span className="text-xs">Dados</span>
      </TabsTrigger>
      <TabsTrigger value="security" className="flex flex-col items-center gap-1 py-3">
        <Shield className="h-5 w-5" />
        <span className="text-xs">Segurança</span>
      </TabsTrigger>
    </TabsList>
  )
}
