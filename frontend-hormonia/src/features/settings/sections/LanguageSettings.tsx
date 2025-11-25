import React from 'react'
import { useUserPreferences } from '../../../hooks/useSettings'
import { SettingsSection } from '../SettingsSection'
import { Separator } from '@/components/ui/separator'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Globe } from 'lucide-react'

/**
 * Language and Region Settings Component
 * Manages language, timezone, and date format preferences
 */
export function LanguageSettings() {
  const { preferences, updatePreferences } = useUserPreferences()

  return (
    <SettingsSection
      title="Idioma & Região"
      description="Localização e formato"
      icon={Globe}
    >
      <div className="space-y-6">
        {/* Language Selection */}
        <div>
          <h3 className="text-lg font-medium mb-4">Idioma da Interface</h3>
          <Select
            value={preferences?.language || 'pt-BR'}
            onValueChange={(value) => updatePreferences({ language: value })}
          >
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder="Selecione um idioma" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="pt-BR">Português (Brasil)</SelectItem>
              <SelectItem value="en-US">English (US)</SelectItem>
              <SelectItem value="es-ES">Español</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Separator />

        {/* Timezone Selection */}
        <div>
          <h3 className="text-lg font-medium mb-4">Fuso Horário</h3>
          <Select
            value={preferences?.timezone || 'America/Sao_Paulo'}
            onValueChange={(value) => updatePreferences({ timezone: value })}
          >
            <SelectTrigger className="w-[300px]">
              <SelectValue placeholder="Selecione o fuso horário" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="America/Sao_Paulo">São Paulo (GMT-3)</SelectItem>
              <SelectItem value="America/New_York">New York (GMT-5)</SelectItem>
              <SelectItem value="Europe/London">London (GMT+0)</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Separator />

        {/* Date Format Selection */}
        <div>
          <h3 className="text-lg font-medium mb-4">Formato de Data</h3>
          <Select
            value={preferences?.date_format || 'dd/mm/yyyy'}
            onValueChange={(value) => updatePreferences({ date_format: value })}
          >
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder="Formato de data" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="dd/mm/yyyy">DD/MM/AAAA</SelectItem>
              <SelectItem value="mm/dd/yyyy">MM/DD/AAAA</SelectItem>
              <SelectItem value="yyyy-mm-dd">AAAA-MM-DD</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
    </SettingsSection>
  )
}
