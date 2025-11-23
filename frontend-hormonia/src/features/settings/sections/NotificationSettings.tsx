import React from 'react'
import { useUserPreferences, useNotificationPreferences } from '../../../hooks/useSettings'
import { SettingsSection } from '../SettingsSection'
import { Switch } from '@/components/ui/switch'
import { Separator } from '@/components/ui/separator'
import { Bell, Loader2 } from 'lucide-react'

/**
 * Notification Settings Component
 * Manages user notification preferences including alerts, messages, and delivery methods
 */
export function NotificationSettings() {
  const { isLoadingPreferences } = useUserPreferences()
  const { notifications, updateNotificationSetting } = useNotificationPreferences()

  if (isLoadingPreferences) {
    return (
      <SettingsSection
        title="Notificações"
        description="Preferências de alerta"
        icon={Bell}
      >
        <div className="flex items-center justify-center p-6">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
      </SettingsSection>
    )
  }

  return (
    <SettingsSection
      title="Notificações"
      description="Preferências de alerta"
      icon={Bell}
    >
      <div className="space-y-6">
        {/* Notification Types */}
        <div>
          <h3 className="text-lg font-medium mb-4">Preferências de Notificação</h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Novos alertas</p>
                <p className="text-sm text-gray-500">
                  Receber notificações quando novos alertas forem gerados
                </p>
              </div>
              <Switch
                checked={notifications?.new_alerts ?? true}
                onCheckedChange={(checked) => updateNotificationSetting('new_alerts', checked)}
              />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Mensagens de pacientes</p>
                <p className="text-sm text-gray-500">
                  Notificações quando pacientes enviarem mensagens
                </p>
              </div>
              <Switch
                checked={notifications?.patient_messages ?? true}
                onCheckedChange={(checked) => updateNotificationSetting('patient_messages', checked)}
              />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Relatórios concluídos</p>
                <p className="text-sm text-gray-500">
                  Avisar quando relatórios estiverem prontos
                </p>
              </div>
              <Switch
                checked={notifications?.reports_completed ?? true}
                onCheckedChange={(checked) => updateNotificationSetting('reports_completed', checked)}
              />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Questionários completados</p>
                <p className="text-sm text-gray-500">
                  Notificar quando pacientes completarem questionários
                </p>
              </div>
              <Switch
                checked={notifications?.quiz_completed ?? true}
                onCheckedChange={(checked) => updateNotificationSetting('quiz_completed', checked)}
              />
            </div>
          </div>
        </div>

        <Separator />

        {/* Notification Methods */}
        <div>
          <h3 className="text-lg font-medium mb-4">Métodos de Notificação</h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Notificações no navegador</p>
                <p className="text-sm text-gray-500">
                  Mostrar notificações push no navegador
                </p>
              </div>
              <Switch
                checked={notifications?.browser_notifications ?? true}
                onCheckedChange={(checked) => updateNotificationSetting('browser_notifications', checked)}
              />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Notificações por email</p>
                <p className="text-sm text-gray-500">
                  Enviar resumos por email
                </p>
              </div>
              <Switch
                checked={notifications?.email_notifications ?? false}
                onCheckedChange={(checked) => updateNotificationSetting('email_notifications', checked)}
              />
            </div>
          </div>
        </div>
      </div>
    </SettingsSection>
  )
}
