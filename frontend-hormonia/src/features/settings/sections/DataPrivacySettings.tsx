import React from 'react'
import { useAuth } from '@/app/providers/AuthContext'
import { useUserPreferences } from '../../../hooks/useSettings'
import { SettingsSection } from '../SettingsSection'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Separator } from '@/components/ui/separator'
import { toast } from '../../../hooks/use-toast'
import { Database, RefreshCw } from 'lucide-react'

/**
 * Data and Privacy Settings Component
 * Manages data export, cache, offline mode, and account deletion
 */
export function DataPrivacySettings() {
  const { user } = useAuth()
  const { preferences } = useUserPreferences()

  const handleExportData = () => {
    toast({
      title: 'Exportação iniciada',
      description: 'Preparando seus dados para download...',
    })

    setTimeout(() => {
      const data = {
        user: user,
        preferences: preferences,
        exported_at: new Date().toISOString(),
      }
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: 'application/json',
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `dados-usuario-${new Date().toISOString().split('T')[0]}.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)

      toast({
        title: 'Download concluído',
        description: 'Seus dados foram exportados com sucesso.',
      })
    }, 2000)
  }

  const handleClearCache = () => {
    localStorage.clear()
    sessionStorage.clear()
    toast({
      title: 'Cache limpo',
      description: 'Todos os dados temporários foram removidos.',
    })
  }

  const handleDeleteAccount = () => {
    toast({
      title: 'Funcionalidade em desenvolvimento',
      description: 'A exclusão de conta será implementada em breve.',
      variant: 'destructive',
    })
  }

  return (
    <SettingsSection title="Dados & Privacidade" description="Gerenciar seus dados" icon={Database}>
      <div className="space-y-6">
        {/* Data Export */}
        <div>
          <h3 className="text-lg font-medium mb-4">Exportar Dados</h3>
          <p className="text-gray-600 mb-4">Baixe uma cópia dos seus dados em formato JSON</p>
          <Button variant="outline" onClick={handleExportData}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Exportar dados
          </Button>
        </div>

        <Separator />

        {/* Cache and Storage */}
        <div>
          <h3 className="text-lg font-medium mb-4">Cache e Armazenamento</h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Limpar cache local</p>
                <p className="text-sm text-gray-500">
                  Remove dados temporários armazenados no navegador
                </p>
              </div>
              <Button variant="outline" size="sm" onClick={handleClearCache}>
                Limpar
              </Button>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Dados offline</p>
                <p className="text-sm text-gray-500">Permite acesso limitado quando offline</p>
              </div>
              <Switch
                checked={localStorage.getItem('offline-enabled') === 'true'}
                onCheckedChange={(checked) => {
                  localStorage.setItem('offline-enabled', checked.toString())
                  toast({
                    title: checked ? 'Dados offline ativados' : 'Dados offline desativados',
                    description: checked
                      ? 'Dados serão armazenados localmente para acesso offline.'
                      : 'Dados offline foram desabilitados.',
                  })
                }}
              />
            </div>
          </div>
        </div>

        <Separator />

        {/* Danger Zone */}
        <div>
          <h3 className="text-lg font-medium mb-4 text-red-600">Zona de Perigo</h3>
          <div className="space-y-4">
            <div className="p-4 border border-red-200 rounded-lg bg-red-50">
              <h4 className="font-medium text-red-800 mb-2">Excluir conta</h4>
              <p className="text-sm text-red-600 mb-4">
                Esta ação é irreversível. Todos os seus dados serão permanentemente removidos.
              </p>
              <Button variant="destructive" size="sm" onClick={handleDeleteAccount}>
                Excluir conta
              </Button>
            </div>
          </div>
        </div>
      </div>
    </SettingsSection>
  )
}
