import React, { useState } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { SystemStatus } from '@/components/monitoring/SystemStatus'
import { useAuth } from '@/contexts/AuthContext'
import { useConfig } from '@/lib/config-initializer'
import { apiClient } from '@/lib/api-client'
import { useSystemStats } from '@/hooks/api/useSystemStats'
import { Loader2, Settings, Users, Database, Shield, Activity, FileText, Download, Upload, RefreshCw, TriangleAlert as AlertTriangle, CircleCheck as CheckCircle, Search, ListFilter as ListFilter } from 'lucide-react'

interface BackupResponse {
  success: boolean
  message?: string
}

interface ClearCacheResponse {
  success: boolean
  message?: string
}

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

// Helper function to format uptime in human-readable format
function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)

  if (days > 0) {
    return `${days}d ${hours}h`
  } else if (hours > 0) {
    return `${hours}h ${minutes}m`
  } else {
    return `${minutes}m`
  }
}

export default function AdminPage() {
  const { user } = useAuth()
  const { config } = useConfig()
  const [isLoading, setIsLoading] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)
  const [searchUsers, setSearchUsers] = useState('')

  // Configuration states
  const [aiEnabled, setAiEnabled] = useState(true)
  const [autoReply, setAutoReply] = useState(true)
  const [maintenanceMode, setMaintenanceMode] = useState(false)
  const [debugMode, setDebugMode] = useState(false)

  // Fetch system stats with automatic refetching
  const { data: stats, isLoading: statsLoading, error: statsError, refetch: refetchStats } = useSystemStats({
    refetchInterval: 30000 // Refresh every 30s
  })

  // Check admin access
  if (!user || user['role'] !== 'admin') {
    return (
      <div className="container mx-auto p-6">
        <Alert className="bg-red-50">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Acesso Negado</AlertTitle>
          <AlertDescription>
            Você não tem permissão para acessar esta página.
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  const handleBackup = async () => {
    setIsLoading(true)
    try {
      // Use apiClient's baseURL and authToken for blob downloads
      const baseURL = apiClient.getBaseURL()
      const url = `${baseURL}/admin/backup`

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${(apiClient as any).authToken || ''}`
        }
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const blob = await response.blob()
      const downloadUrl = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = downloadUrl
      a.download = `backup-${new Date().toISOString()}.zip`
      a.click()
      window.URL.revokeObjectURL(downloadUrl)
      setMessage({ type: 'success', text: 'Backup realizado com sucesso!' })
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Erro ao realizar backup'
      setMessage({ type: 'error', text: errorMessage })
    } finally {
      setIsLoading(false)
    }
  }

  const handleClearCache = async () => {
    setIsLoading(true)
    try {
      await apiClient.request<ClearCacheResponse>('/admin/cache/clear', {
        method: 'POST'
      })

      setMessage({ type: 'success', text: 'Cache limpo com sucesso!' })
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Erro ao limpar cache'
      setMessage({ type: 'error', text: errorMessage })
    } finally {
      setIsLoading(false)
    }
  }

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
    <div className="container mx-auto p-6 max-w-7xl">
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Painel Administrativo</h1>
            <p className="text-gray-600 mt-1">Controle completo do sistema e monitoramento em tempo real</p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetchStats()}
              disabled={statsLoading}
            >
              <RefreshCw className={`mr-2 h-4 w-4 ${statsLoading ? 'animate-spin' : ''}`} />
              Atualizar
            </Button>
            <Button size="sm">
              <Download className="mr-2 h-4 w-4" />
              Relatório
            </Button>
          </div>
        </div>
      </div>

      {message && (
        <Alert className={`mb-6 ${message.type === 'success' ? 'bg-green-50' : 'bg-red-50'}`}>
          {message.type === 'success' ? (
            <CheckCircle className="h-4 w-4 text-green-600" />
          ) : (
            <AlertTriangle className="h-4 w-4 text-red-600" />
          )}
          <AlertDescription>{message.text}</AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="monitoring" className="space-y-6">
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

        <TabsContent value="monitoring" className="space-y-6">
          {/* Error Alert */}
          {statsError && (
            <Alert variant="destructive" className="mb-6">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Erro ao carregar estatísticas do sistema</AlertTitle>
              <AlertDescription className="flex items-center justify-between">
                <span>{statsError instanceof Error ? statsError.message : 'Erro desconhecido'}</span>
                <Button onClick={() => refetchStats()} variant="outline" size="sm" className="ml-4">
                  Tentar Novamente
                </Button>
              </AlertDescription>
            </Alert>
          )}

          {/* System Metrics Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* CPU Usage */}
            <Card className="hover:shadow-lg transition-shadow">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">CPU Usage</p>
                    {statsLoading ? (
                      <Skeleton className="h-10 w-20 mt-2" />
                    ) : (
                      <>
                        <p className={`text-3xl font-bold mt-2 ${stats && stats.system.cpu_percent > 80 ? 'text-red-600' : ''}`}>
                          {stats?.system.cpu_percent.toFixed(1)}%
                        </p>
                        <p className="text-xs text-gray-500 mt-1">
                          {stats && stats.system.cpu_percent > 80 ? 'Alta utilização' : 'Normal'}
                        </p>
                      </>
                    )}
                  </div>
                  <div className={`h-12 w-12 rounded-full flex items-center justify-center ${
                    stats && stats.system.cpu_percent > 80 ? 'bg-red-100' : 'bg-blue-100'
                  }`}>
                    <Activity className={`h-6 w-6 ${
                      stats && stats.system.cpu_percent > 80 ? 'text-red-600' : 'text-blue-600'
                    }`} />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Memory Usage */}
            <Card className="hover:shadow-lg transition-shadow">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Memory Usage</p>
                    {statsLoading ? (
                      <Skeleton className="h-10 w-20 mt-2" />
                    ) : (
                      <>
                        <p className={`text-3xl font-bold mt-2 ${stats && stats.system.memory_percent > 80 ? 'text-orange-600' : ''}`}>
                          {stats?.system.memory_percent.toFixed(1)}%
                        </p>
                        <p className="text-xs text-gray-500 mt-1">
                          {stats && stats.system.memory_percent > 80 ? 'Atenção' : 'Normal'}
                        </p>
                      </>
                    )}
                  </div>
                  <div className={`h-12 w-12 rounded-full flex items-center justify-center ${
                    stats && stats.system.memory_percent > 80 ? 'bg-orange-100' : 'bg-green-100'
                  }`}>
                    <Activity className={`h-6 w-6 ${
                      stats && stats.system.memory_percent > 80 ? 'text-orange-600' : 'text-green-600'
                    }`} />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Disk Usage */}
            <Card className="hover:shadow-lg transition-shadow">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Disk Usage</p>
                    {statsLoading ? (
                      <Skeleton className="h-10 w-20 mt-2" />
                    ) : (
                      <>
                        <p className="text-3xl font-bold mt-2">{stats?.system.disk_percent.toFixed(1)}%</p>
                        <p className="text-xs text-gray-500 mt-1">Armazenamento</p>
                      </>
                    )}
                  </div>
                  <div className="h-12 w-12 rounded-full bg-purple-100 flex items-center justify-center">
                    <Database className="h-6 w-6 text-purple-600" />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* System Uptime */}
            <Card className="hover:shadow-lg transition-shadow">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">System Uptime</p>
                    {statsLoading ? (
                      <Skeleton className="h-10 w-20 mt-2" />
                    ) : (
                      <>
                        <p className="text-3xl font-bold mt-2">{stats ? formatUptime(stats.system.uptime_seconds) : '0m'}</p>
                        <p className="text-xs text-green-600 mt-1">Online</p>
                      </>
                    )}
                  </div>
                  <div className="h-12 w-12 rounded-full bg-green-100 flex items-center justify-center">
                    <CheckCircle className="h-6 w-6 text-green-600" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* User Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card className="hover:shadow-lg transition-shadow">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Total Users</p>
                    {statsLoading ? (
                      <Skeleton className="h-10 w-16 mt-2" />
                    ) : (
                      <>
                        <p className="text-3xl font-bold mt-2">{stats?.users.total.toLocaleString()}</p>
                        <p className="text-xs text-gray-500 mt-1">Cadastrados</p>
                      </>
                    )}
                  </div>
                  <div className="h-12 w-12 rounded-full bg-blue-100 flex items-center justify-center">
                    <Users className="h-6 w-6 text-blue-600" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="hover:shadow-lg transition-shadow">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Active Users (24h)</p>
                    {statsLoading ? (
                      <Skeleton className="h-10 w-16 mt-2" />
                    ) : (
                      <>
                        <p className="text-3xl font-bold mt-2">{stats?.users.active_now.toLocaleString()}</p>
                        <p className="text-xs text-gray-500 mt-1">Últimas 24h</p>
                      </>
                    )}
                  </div>
                  <div className="h-12 w-12 rounded-full bg-green-100 flex items-center justify-center">
                    <Activity className="h-6 w-6 text-green-600" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="hover:shadow-lg transition-shadow">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Admins</p>
                    {statsLoading ? (
                      <Skeleton className="h-10 w-12 mt-2" />
                    ) : (
                      <>
                        <p className="text-3xl font-bold mt-2">{(stats?.users.by_role.admin ?? 0).toString()}</p>
                        <p className="text-xs text-gray-500 mt-1">
                          {(stats?.users.by_role.doctor ?? 0).toString()} médicos
                        </p>
                      </>
                    )}
                  </div>
                  <div className="h-12 w-12 rounded-full bg-orange-100 flex items-center justify-center">
                    <Shield className="h-6 w-6 text-orange-600" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Database Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card className="hover:shadow-lg transition-shadow">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Total Records</p>
                    {statsLoading ? (
                      <Skeleton className="h-10 w-16 mt-2" />
                    ) : (
                      <>
                        <p className="text-3xl font-bold mt-2">{stats?.database.total_records.toLocaleString()}</p>
                        <p className="text-xs text-gray-500 mt-1">Registros</p>
                      </>
                    )}
                  </div>
                  <div className="h-12 w-12 rounded-full bg-indigo-100 flex items-center justify-center">
                    <Database className="h-6 w-6 text-indigo-600" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="hover:shadow-lg transition-shadow">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Patients</p>
                    {statsLoading ? (
                      <Skeleton className="h-10 w-16 mt-2" />
                    ) : (
                      <>
                        <p className="text-3xl font-bold mt-2">{stats?.database.total_patients.toLocaleString()}</p>
                        <p className="text-xs text-gray-500 mt-1">Pacientes</p>
                      </>
                    )}
                  </div>
                  <div className="h-12 w-12 rounded-full bg-blue-100 flex items-center justify-center">
                    <Users className="h-6 w-6 text-blue-600" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="hover:shadow-lg transition-shadow">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">DB Users</p>
                    {statsLoading ? (
                      <Skeleton className="h-10 w-16 mt-2" />
                    ) : (
                      <>
                        <p className="text-3xl font-bold mt-2">{stats?.database.total_users.toLocaleString()}</p>
                        <p className="text-xs text-gray-500 mt-1">Usuários</p>
                      </>
                    )}
                  </div>
                  <div className="h-12 w-12 rounded-full bg-green-100 flex items-center justify-center">
                    <Users className="h-6 w-6 text-green-600" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="hover:shadow-lg transition-shadow">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">DB Connections</p>
                    {statsLoading ? (
                      <Skeleton className="h-10 w-12 mt-2" />
                    ) : (
                      <>
                        <p className="text-3xl font-bold mt-2">{stats?.database.connections.toString()}</p>
                        <p className="text-xs text-gray-500 mt-1">Ativas</p>
                      </>
                    )}
                  </div>
                  <div className="h-12 w-12 rounded-full bg-purple-100 flex items-center justify-center">
                    <Activity className="h-6 w-6 text-purple-600" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Timestamp */}
          {!statsLoading && stats && (
            <div className="flex justify-end">
              <p className="text-sm text-muted-foreground">
                Última atualização: {new Date(stats.timestamp).toLocaleString('pt-BR')}
              </p>
            </div>
          )}

          {/* System Status and Resources */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <SystemStatus />

            <Card>
              <CardHeader>
                <CardTitle>Uso de Recursos</CardTitle>
                <CardDescription>Monitoramento de CPU, memória e disco</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {statsLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
                  </div>
                ) : stats ? (
                  <>
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">CPU</span>
                        <span className="text-sm text-gray-600">{stats.system.cpu_percent.toFixed(1)}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full ${
                            stats.system.cpu_percent > 80 ? 'bg-red-600' :
                            stats.system.cpu_percent > 60 ? 'bg-orange-600' :
                            'bg-blue-600'
                          }`}
                          style={{ width: `${Math.min(stats.system.cpu_percent, 100)}%` }}
                        />
                      </div>
                    </div>

                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">Memória</span>
                        <span className="text-sm text-gray-600">{stats.system.memory_percent.toFixed(1)}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full ${
                            stats.system.memory_percent > 80 ? 'bg-red-600' :
                            stats.system.memory_percent > 60 ? 'bg-orange-600' :
                            'bg-green-600'
                          }`}
                          style={{ width: `${Math.min(stats.system.memory_percent, 100)}%` }}
                        />
                      </div>
                    </div>

                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">Disco</span>
                        <span className="text-sm text-gray-600">{stats.system.disk_percent.toFixed(1)}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full ${
                            stats.system.disk_percent > 80 ? 'bg-red-600' :
                            stats.system.disk_percent > 60 ? 'bg-orange-600' :
                            'bg-purple-600'
                          }`}
                          style={{ width: `${Math.min(stats.system.disk_percent, 100)}%` }}
                        />
                      </div>
                    </div>

                    <div className="pt-4 border-t">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-600">Última atualização</span>
                        <span className="font-medium">{new Date(stats.timestamp).toLocaleTimeString('pt-BR')}</span>
                      </div>
                    </div>
                  </>
                ) : null}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="settings" className="space-y-6">
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
        </TabsContent>

        <TabsContent value="users" className="space-y-6">
          <Card className="shadow-sm">
            <CardHeader className="border-b">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-3 rounded-lg bg-green-50">
                    <Users className="h-6 w-6 text-green-600" />
                  </div>
                  <div>
                    <CardTitle>Gestão de Usuários</CardTitle>
                    <CardDescription>
                      {statsLoading ? (
                        <Loader2 className="h-4 w-4 animate-spin inline" />
                      ) : (
                        `${stats?.users.total ?? 0} usuários cadastrados, ${stats?.users.active_now ?? 0} ativos`
                      )}
                    </CardDescription>
                  </div>
                </div>
                <Button>
                  <Users className="mr-2 h-4 w-4" />
                  Novo Usuário
                </Button>
              </div>
            </CardHeader>
            <CardContent className="pt-6">
              <div className="space-y-4">
                <div className="flex gap-3">
                  <div className="flex-1 relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                    <Input
                      placeholder="Buscar por nome, email ou função..."
                      className="pl-10"
                      value={searchUsers}
                      onChange={(e) => setSearchUsers(e.target.value)}
                    />
                  </div>
                  <Button variant="outline">
                    <ListFilter className="mr-2 h-4 w-4" />
                    Filtros
                  </Button>
                </div>

                <div className="border rounded-lg">
                  <div className="grid grid-cols-5 gap-4 p-4 bg-gray-50 font-medium text-sm text-gray-700 border-b">
                    <div>Usuário</div>
                    <div>Email</div>
                    <div>Função</div>
                    <div>Status</div>
                    <div className="text-right">Ações</div>
                  </div>
                  <div className="divide-y">
                    {[1, 2, 3, 4, 5].map((i) => (
                      <div key={i} className="grid grid-cols-5 gap-4 p-4 hover:bg-gray-50 transition-colors">
                        <div className="flex items-center gap-3">
                          <div className="h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center">
                            <span className="text-sm font-medium text-blue-700">U{i}</span>
                          </div>
                          <div>
                            <p className="font-medium text-sm">Usuário {i}</p>
                            <p className="text-xs text-gray-500">Último acesso há 2h</p>
                          </div>
                        </div>
                        <div className="flex items-center text-sm text-gray-600">
                          usuario{i}@email.com
                        </div>
                        <div className="flex items-center">
                          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full">
                            {i === 1 ? 'Admin' : 'Médico'}
                          </span>
                        </div>
                        <div className="flex items-center">
                          <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full">
                            Ativo
                          </span>
                        </div>
                        <div className="flex items-center justify-end gap-2">
                          <Button variant="ghost" size="sm">
                            Editar
                          </Button>
                          <Button variant="ghost" size="sm" className="text-red-600 hover:text-red-700">
                            Remover
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="database" className="space-y-6">
          <Card className="shadow-sm">
            <CardHeader className="border-b">
              <div className="flex items-center gap-3">
                <div className="p-3 rounded-lg bg-purple-50">
                  <Database className="h-6 w-6 text-purple-600" />
                </div>
                <div>
                  <CardTitle>Gestão de Dados</CardTitle>
                  <CardDescription>
                    Operações de backup, manutenção e otimização
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-6 pt-6">
              <div className="grid grid-cols-2 gap-4">
                <Button
                  onClick={handleBackup}
                  disabled={isLoading}
                  variant="outline"
                >
                  <Download className="mr-2 h-4 w-4" />
                  Fazer Backup
                </Button>

                <Button variant="outline" disabled>
                  <Upload className="mr-2 h-4 w-4" />
                  Restaurar Backup
                </Button>

                <Button
                  onClick={handleClearCache}
                  disabled={isLoading}
                  variant="outline"
                >
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Limpar Cache
                </Button>

                <Button variant="outline" disabled>
                  <Database className="mr-2 h-4 w-4" />
                  Otimizar DB
                </Button>
              </div>

              <Alert>
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Atenção</AlertTitle>
                <AlertDescription>
                  Operações de banco de dados podem afetar o desempenho do sistema.
                  Execute durante períodos de baixa atividade.
                </AlertDescription>
              </Alert>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Estatísticas do Banco</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center p-4 bg-gray-50 rounded">
                  <p className="text-2xl font-bold">1,234</p>
                  <p className="text-sm text-gray-600">Pacientes</p>
                </div>
                <div className="text-center p-4 bg-gray-50 rounded">
                  <p className="text-2xl font-bold">45,678</p>
                  <p className="text-sm text-gray-600">Mensagens</p>
                </div>
                <div className="text-center p-4 bg-gray-50 rounded">
                  <p className="text-2xl font-bold">2.3 GB</p>
                  <p className="text-sm text-gray-600">Tamanho</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="security" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Segurança</CardTitle>
              <CardDescription>
                Configurações de segurança e auditoria
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Alert>
                <Shield className="h-4 w-4" />
                <AlertTitle>Status de Segurança</AlertTitle>
                <AlertDescription>
                  Todos os sistemas de segurança estão operacionais.
                  Última verificação: há 5 minutos.
                </AlertDescription>
              </Alert>

              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 border rounded">
                  <div>
                    <p className="font-medium">Autenticação de 2 Fatores</p>
                    <p className="text-sm text-gray-600">Obrigatório para todos os usuários</p>
                  </div>
                  <Switch defaultChecked />
                </div>

                <div className="flex items-center justify-between p-4 border rounded">
                  <div>
                    <p className="font-medium">Rate Limiting</p>
                    <p className="text-sm text-gray-600">Limita requisições por IP</p>
                  </div>
                  <Switch defaultChecked />
                </div>

                <div className="flex items-center justify-between p-4 border rounded">
                  <div>
                    <p className="font-medium">Logs de Auditoria</p>
                    <p className="text-sm text-gray-600">Registra todas as ações do sistema</p>
                  </div>
                  <Switch defaultChecked />
                </div>
              </div>

              <Button className="w-full">
                <FileText className="mr-2 h-4 w-4" />
                Ver Logs de Auditoria
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
