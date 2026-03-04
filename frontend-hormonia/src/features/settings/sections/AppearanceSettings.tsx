import React from 'react'
import { useTheme, useUserPreferences } from '../../../hooks/useSettings'
import { SettingsSection } from '../SettingsSection'
import { Separator } from '@/components/ui/separator'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Palette } from 'lucide-react'

// Static color map to avoid dynamic class generation issues with Tailwind
const themeColors = {
  blue: 'bg-blue-600',
  green: 'bg-green-600',
  purple: 'bg-purple-600',
  orange: 'bg-orange-600',
  red: 'bg-red-600',
} as const

type _AccentColor = keyof typeof themeColors

/**
 * Appearance Settings Component
 * Manages theme, interface density, and accent color preferences
 */
export function AppearanceSettings() {
  const { theme, accentColor, setTheme, setAccentColor } = useTheme()
  const { preferences, updatePreferences } = useUserPreferences()

  return (
    <SettingsSection title="Aparência" description="Tema e interface" icon={Palette}>
      <div className="space-y-6">
        {/* Theme Selection */}
        <div>
          <h3 className="text-lg font-medium mb-4">Tema</h3>
          <Select value={theme} onValueChange={setTheme}>
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder="Selecione um tema" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="light">Claro</SelectItem>
              <SelectItem value="dark">Escuro</SelectItem>
              <SelectItem value="system">Sistema</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Separator />

        {/* Interface Density */}
        <div>
          <h3 className="text-lg font-medium mb-4">Densidade da Interface</h3>
          <Select
            value={preferences?.density || 'comfortable'}
            onValueChange={(value) =>
              updatePreferences({ density: value as 'compact' | 'comfortable' | 'spacious' })
            }
          >
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder="Selecione a densidade" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="compact">Compacta</SelectItem>
              <SelectItem value="comfortable">Confortável</SelectItem>
              <SelectItem value="spacious">Espaçosa</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Separator />

        {/* Accent Color */}
        <div>
          <h3 className="text-lg font-medium mb-4">Cor de Destaque</h3>
          <div className="flex space-x-2">
            {(['blue', 'green', 'purple', 'orange', 'red'] as const).map((color) => (
              <button
                key={color}
                onClick={() => setAccentColor(color)}
                className={`w-8 h-8 rounded-full ${themeColors[color]} border-2 transition-colors ${
                  accentColor === color
                    ? 'border-gray-900 ring-2 ring-gray-900 ring-offset-2'
                    : 'border-gray-300 hover:border-gray-400'
                }`}
                aria-label={`Definir cor de destaque como ${color}`}
              />
            ))}
          </div>
        </div>
      </div>
    </SettingsSection>
  )
}
