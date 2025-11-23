import React, { useState, useEffect } from 'react'
import { createLogger } from '@/lib/logger'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { apiClient } from '@/lib/api-client'
import { useConfig } from '@/lib/config-initializer'
import { Settings } from 'lucide-react'

const logger = createLogger('AdminSettingsTab')

interface SaveSettingsResponse {
  success: boolean
  message?: string
}

interface SettingsPayload {
  ai_enabled: boolean
  auto_reply: boolean
  maintenance_mode: boolean
  debug_mode: boolean
}

interface AdminSettingsTabProps {
  isLoading: boolean
  setIsLoading: (loading: boolean) => void
  setMessage: (message: { type: 'success' | 'error', text: string } | null) => void
}

/**
 * AdminSettingsTab - System configuration and integrations
 *
 * Manages:
 * - AI and automation settings
 * - System maintenance mode
 * - Debug mode
 * - External integrations (Evolution API, Gemini)
 */
export default function AdminSettingsTab({ isLoading, setIsLoading, setMessage }: AdminSettingsTabProps) {
  const { config } = useConfig()
  const [aiEnabled, setAiEnabled] = useState(true)
  const [autoReply, setAutoReply] = useState(true)
  const [maintenanceMode, setMaintenanceMode] = useState(false)
  const [debugMode, setDebugMode] = useState(false)

  // Load settings on mount - GET /admin/settings endpoint
  useEffect(() => {
    const loadSettings = async () => {
      setIsLoading(true)
      try {
        const response = await apiClient.request<{
          ai_enabled: boolean
          auto_reply: boolean
          maintenance_mode: boolean
          debug_mode: boolean
        }>('/admin/settings', {
          method: 'GET'
        })

        if (response && typeof response === 'object') {
          setAiEnabled(response.ai_enabled ?? true)
          setAutoReply(response.auto_reply ?? true)
          setMaintenanceMode(response.maintenance_mode ?? false)
          setDebugMode(response.debug_mode ?? false)
        }

        logger.debug('[AdminSettingsTab] Settings loaded successfully')
      } catch (error) {
        logger.warn('[AdminSettingsTab] Failed to load settings, using defaults:', error)
        // Use default values if API call fails
        setAiEnabled(true)
        setAutoReply(true)
        setMaintenanceMode(false)
        setDebugMode(false)
      } finally {
        setIsLoading(false)
      }
    }
    loadSettings()
  }, [setIsLoading])

  const handleSaveSettings = async () => {
    setIsLoading(true)
    try {
      const payload: SettingsPayload = {
        ai_enabled: aiEnabled,
        auto_reply: autoReply,
        maintenance_mode: maintenanceMode,
        debug_mode: debugMode
      }

      await apiClient.request<SaveSettingsResponse>('/admin/settings', {
        method: 'PUT',
        body: JSON.stringify(payload)
      })

      setMessage({ type: 'success', text: 'Configurações salvas com sucesso!' })
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Erro ao salvar configurações'
      setMessage({ type: 'error', text: errorMessage })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <Card className="shadow-sm">
        <CardHeader className="border-b">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-lg bg-blue-50">
              <Settings className="h-6 w-6 text-blue-600" />
            </div>
            <div>
              <CardTitle>Configurações do Sistema</CardTitle>
              <CardDescription>
                Ajuste o comportamento e funcionalidades do sistema
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-6 pt-6">
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
            <div className="space-y-1 flex-1">
              <div className="flex items-center gap-2">
                <Label htmlFor="ai-enabled" className="font-semibold">IA Habilitada</Label>
                {aiEnabled && <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">Ativo</span>}
              </div>
              <p className="text-sm text-gray-600">
                Ativa o processamento de IA para mensagens e respostas automáticas
              </p>
            </div>
            <Switch
              id="ai-enabled"
              checked={aiEnabled}
              onCheckedChange={setAiEnabled}
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="auto-reply">Resposta Automática</Label>
              <p className="text-sm text-gray-600">
                Responde automaticamente às mensagens dos pacientes
              </p>
            </div>
            <Switch
              id="auto-reply"
              checked={autoReply}
              onCheckedChange={setAutoReply}
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="maintenance">Modo de Manutenção</Label>
              <p className="text-sm text-gray-600">
                Desativa o sistema para manutenção
              </p>
            </div>
            <Switch
              id="maintenance"
              checked={maintenanceMode}
              onCheckedChange={setMaintenanceMode}
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="debug">Modo Debug</Label>
              <p className="text-sm text-gray-600">
                Ativa logs detalhados para debugging
              </p>
            </div>
            <Switch
              id="debug"
              checked={debugMode}
              onCheckedChange={setDebugMode}
            />
          </div>

          <Button
            onClick={handleSaveSettings}
            disabled={isLoading}
            className="w-full"
          >
            {isLoading ? 'Salvando...' : 'Salvar Configurações'}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Integrações</CardTitle>
          <CardDescription>
            Configure as integrações externas
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="evolution-url">Evolution API URL</Label>
            <Input
              id="evolution-url"
              placeholder="https://api.evolution.com"
              defaultValue={config?.VITE_EVOLUTION_API_URL || ''}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="gemini-key">Gemini API Key</Label>
            <Input
              id="gemini-key"
              type="password"
              placeholder="••••••••••••••••"
              defaultValue={config?.VITE_GEMINI_API_KEY ? config.VITE_GEMINI_API_KEY.substring(0, 8) + '...' : ''}
            />
          </div>

          <Button className="w-full">Atualizar Integrações</Button>
        </CardContent>
      </Card>
    </div>
  )
}
