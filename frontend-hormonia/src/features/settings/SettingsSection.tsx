import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Save, Loader2 } from 'lucide-react'

/**
 * Reusable settings section wrapper component
 * Provides consistent layout and save functionality across all settings sections
 */
interface SettingsSectionProps {
  /** Section title */
  title: string
  /** Section description */
  description?: string
  /** Section icon component */
  icon?: React.ComponentType<{ className?: string }>
  /** Section content */
  children: React.ReactNode
  /** Save handler */
  onSave?: () => void
  /** Loading state for save operation */
  isLoading?: boolean
  /** Whether the form has unsaved changes */
  isDirty?: boolean
  /** Show save button */
  showSaveButton?: boolean
  /** Custom footer content */
  footer?: React.ReactNode
}

export function SettingsSection({
  title,
  description,
  icon: Icon,
  children,
  onSave,
  isLoading = false,
  isDirty = false,
  showSaveButton = false,
  footer,
}: SettingsSectionProps) {
  return (
    <Card className="shadow-sm">
      <CardHeader className="border-b">
        <div className="flex items-center gap-3">
          {Icon && (
            <div className="p-3 rounded-lg bg-blue-50">
              <Icon className="h-6 w-6 text-blue-600" />
            </div>
          )}
          <div>
            <CardTitle className="text-xl">{title}</CardTitle>
            {description && (
              <CardDescription className="mt-1">{description}</CardDescription>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-6">
        {children}

        {(showSaveButton || footer) && (
          <div className="mt-6 pt-6 border-t">
            {footer || (
              <div className="flex justify-end">
                <Button
                  type="submit"
                  disabled={isLoading || !isDirty}
                  onClick={onSave}
                >
                  {isLoading ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Save className="mr-2 h-4 w-4" />
                  )}
                  Salvar alterações
                </Button>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
