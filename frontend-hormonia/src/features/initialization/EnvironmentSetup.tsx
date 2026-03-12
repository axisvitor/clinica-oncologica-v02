import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  Settings,
  Cloud,
  Shield,
  RefreshCw,
  Eye,
  EyeOff,
} from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { toast } from '@/hooks/use-toast'
import { createLogger } from '@/lib/logger'
import { apiClient } from '@/lib/api-client'
import { loadConfig } from '@/config'

const logger = createLogger('EnvironmentSetup')

interface EnvironmentCheck {
  id: string
  name: string
  description: string
  status: 'pending' | 'checking' | 'success' | 'warning' | 'error'
  required: boolean
  value?: string | undefined
  error?: string | undefined
  category: 'api' | 'services' | 'security'
}

interface EnvironmentSetupProps {
  onComplete: () => void
  onError: (error: string) => void
}

const AUTH_MODE = 'first-party-session'

function hasValidCsrfToken(payload: unknown): boolean {
  if (!payload || typeof payload !== 'object') {
    return false
  }

  const csrfToken = (payload as { csrf_token?: unknown }).csrf_token
  if (typeof csrfToken === 'string') {
    return csrfToken.trim().length > 0
  }

  if (
    Array.isArray(csrfToken) &&
    csrfToken.length >= 2 &&
    typeof csrfToken[1] === 'string' &&
    csrfToken[1].trim().length > 0
  ) {
    return true
  }

  return false
}

export function EnvironmentSetup({ onComplete, onError }: EnvironmentSetupProps) {
  const [checks, setChecks] = useState<EnvironmentCheck[]>([
    {
      id: 'api_base_url',
      name: 'API Base URL',
      description: 'URL base para comunicação com o backend',
      status: 'pending',
      required: true,
      category: 'api',
    },
    {
      id: 'ws_url',
      name: 'WebSocket URL',
      description: 'URL para conexões WebSocket em tempo real',
      status: 'pending',
      required: false,
      category: 'api',
    },
    {
      id: 'session_auth',
      name: 'Autenticação por Sessão',
      description: 'Prontidão do login/restore via cookies HTTP + CSRF do backend',
      status: 'pending',
      required: true,
      category: 'security',
    },
    {
      id: 'whatsapp_instance',
      name: 'WhatsApp Instance',
      description: 'Instância do WhatsApp Business API',
      status: 'pending',
      required: false,
      category: 'services',
    },
    {
      id: 'sentry_dsn',
      name: 'Sentry DSN',
      description: 'Configuração de monitoramento de erros',
      status: 'pending',
      required: false,
      category: 'security',
    },
    {
      id: 'session_config',
      name: 'Política de Sessão',
      description: 'Timeout e limiar de renovação usados pela sessão própria',
      status: 'pending',
      required: true,
      category: 'security',
    },
  ])

  const [isChecking, setIsChecking] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [manualConfig, setManualConfig] = useState<Record<string, string>>({})
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({})

  const categoryIcons = {
    api: <Cloud className="w-5 h-5" />,
    services: <Settings className="w-5 h-5" />,
    security: <Shield className="w-5 h-5" />,
  }

  const categoryNames = {
    api: 'API & Comunicação',
    services: 'Serviços Externos',
    security: 'Segurança & Sessão',
  }

  useEffect(() => {
    handleCheckEnvironment()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- handleCheckEnvironment is intentionally only called on mount
  }, [])

  const updateCheckStatus = (
    id: string,
    status: EnvironmentCheck['status'],
    value?: string,
    error?: string
  ) => {
    setChecks((prev) =>
      prev.map((check) => (check.id === id ? { ...check, status, value, error } : check))
    )
  }

  const handleCheckEnvironment = async () => {
    setIsChecking(true)
    logger.log('Starting environment checks', { auth_mode: AUTH_MODE })

    const observedStatuses = new Map<string, EnvironmentCheck['status']>()
    const markCheck = (
      id: string,
      status: EnvironmentCheck['status'],
      value?: string,
      error?: string
    ) => {
      observedStatuses.set(id, status)
      updateCheckStatus(id, status, value, error)
    }

    try {
      const config = await loadConfig()

      setChecks((prev) =>
        prev.map((check) => ({
          ...check,
          status: 'pending' as const,
          value: undefined,
          error: undefined,
        }))
      )
      checks.forEach((check) => observedStatuses.set(check.id, 'pending'))

      if (config.API_BASE_URL) {
        apiClient.setBaseURL(config.API_BASE_URL)
      }

      markCheck('api_base_url', 'checking')
      if (config.API_BASE_URL) {
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), 5000)

        try {
          const response = await fetch(`${config.API_BASE_URL}/health`, {
            method: 'GET',
            signal: controller.signal,
          })

          if (response.ok) {
            markCheck('api_base_url', 'success', config.API_BASE_URL)
          } else {
            markCheck(
              'api_base_url',
              'warning',
              config.API_BASE_URL,
              `API retornou status ${response.status}`
            )
          }
        } catch (error) {
          const message =
            error instanceof Error && error.name === 'AbortError'
              ? 'Timeout ao conectar com a API'
              : 'Falha ao conectar com a API'
          markCheck('api_base_url', 'error', config.API_BASE_URL, message)
        } finally {
          clearTimeout(timeoutId)
        }
      } else {
        markCheck('api_base_url', 'error', '', 'URL da API não configurada')
      }

      markCheck('ws_url', 'checking')
      if (config.WS_BASE_URL) {
        markCheck('ws_url', 'success', config.WS_BASE_URL)
      } else {
        markCheck('ws_url', 'warning', '', 'WebSocket não configurado')
      }

      markCheck('session_auth', 'checking')
      if (config.API_BASE_URL) {
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), 5000)

        try {
          const response = await fetch(`${config.API_BASE_URL}/api/v2/auth/csrf-token`, {
            method: 'GET',
            credentials: 'include',
            headers: {
              Accept: 'application/json',
              ...apiClient.getSessionHeaders(),
            },
            signal: controller.signal,
          })

          if (!response.ok) {
            throw new Error(`Sessão HTTP retornou status ${response.status}`)
          }

          const data = await response.json()
          if (!hasValidCsrfToken(data)) {
            throw new Error('Resposta CSRF inválida para autenticação por sessão')
          }

          markCheck('session_auth', 'success', 'Cookie + CSRF prontos')
        } catch (error) {
          const message =
            error instanceof Error && error.name === 'AbortError'
              ? 'Timeout na preparação da sessão HTTP'
              : error instanceof Error
                ? error.message
                : 'Falha na preparação da sessão HTTP'

          markCheck('session_auth', 'error', '', message)
        } finally {
          clearTimeout(timeoutId)
        }
      } else {
        markCheck('session_auth', 'error', '', 'API não configurada para autenticação por sessão')
      }

      markCheck('whatsapp_instance', 'checking')
      if (config.WHATSAPP_INSTANCE_NAME) {
        markCheck('whatsapp_instance', 'success', config.WHATSAPP_INSTANCE_NAME)
      } else {
        markCheck('whatsapp_instance', 'warning', '', 'WhatsApp não configurado')
      }

      markCheck('sentry_dsn', 'checking')
      if (config.SENTRY_DSN) {
        markCheck('sentry_dsn', 'success', '****')
      } else {
        markCheck('sentry_dsn', 'warning', '', 'Sentry não configurado')
      }

      markCheck('session_config', 'checking')
      if (config.SESSION_TIMEOUT && config.TOKEN_REFRESH_THRESHOLD) {
        markCheck(
          'session_config',
          'success',
          `Timeout: ${config.SESSION_TIMEOUT}ms • refresh: ${config.TOKEN_REFRESH_THRESHOLD}ms`
        )
      } else {
        markCheck(
          'session_config',
          'warning',
          '',
          'Configurações de sessão usando padrões seguros'
        )
      }

      logger.log('Environment auth diagnostics', {
        auth_mode: AUTH_MODE,
        session_auth_status: observedStatuses.get('session_auth') ?? 'pending',
        websocket_status: observedStatuses.get('ws_url') ?? 'pending',
      })

      await new Promise((resolve) => setTimeout(resolve, 1000))

      const requiredChecks = checks.filter((check) => check.required)
      const failedRequired = requiredChecks.filter((check) => observedStatuses.get(check.id) === 'error')

      if (failedRequired.length > 0) {
        onError(
          `Configurações obrigatórias falharam: ${failedRequired.map((check) => check.name).join(', ')}`
        )
      } else {
        toast({
          title: 'Ambiente Verificado',
          description: 'Sessão própria, API e integrações essenciais estão prontas.',
        })
        onComplete()
      }
    } catch (error) {
      logger.error('Environment check failed:', error)
      onError('Falha na verificação do ambiente: ' + (error as Error).message)
    } finally {
      setIsChecking(false)
    }
  }

  const getStatusIcon = (status: EnvironmentCheck['status']) => {
    switch (status) {
      case 'success':
        return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'error':
        return <XCircle className="w-4 h-4 text-red-500" />
      case 'warning':
        return <AlertTriangle className="w-4 h-4 text-yellow-500" />
      case 'checking':
        return <RefreshCw className="w-4 h-4 text-blue-500 animate-spin" />
      default:
        return <div className="w-4 h-4 border border-gray-300 rounded-full" />
    }
  }

  const getStatusBadge = (status: EnvironmentCheck['status']) => {
    switch (status) {
      case 'success':
        return (
          <Badge variant="default" className="bg-green-100 text-green-800">
            OK
          </Badge>
        )
      case 'error':
        return <Badge variant="destructive">Erro</Badge>
      case 'warning':
        return (
          <Badge variant="secondary" className="bg-yellow-100 text-yellow-800">
            Aviso
          </Badge>
        )
      case 'checking':
        return <Badge variant="outline">Verificando...</Badge>
      default:
        return <Badge variant="outline">Pendente</Badge>
    }
  }

  const toggleSecret = (checkId: string) => {
    setShowSecrets((prev) => ({
      ...prev,
      [checkId]: !prev[checkId],
    }))
  }

  const categorizedChecks = checks.reduce(
    (acc, check) => {
      const category = check.category
      if (!acc[category]) {
        acc[category] = []
      }
      acc[category]?.push(check)
      return acc
    },
    {} as Record<EnvironmentCheck['category'], EnvironmentCheck[]>
  )

  const visibleCategories = (Object.keys(categoryNames) as EnvironmentCheck['category'][]).filter(
    (category) => (categorizedChecks[category]?.length || 0) > 0
  )

  const summaryStats = {
    total: checks.length,
    success: checks.filter((c) => c.status === 'success').length,
    error: checks.filter((c) => c.status === 'error').length,
    warning: checks.filter((c) => c.status === 'warning').length,
  }

  const manuallyConfigurableChecks = checks.filter((check) => check.id !== 'session_auth')

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="text-center">
          <CardContent className="pt-4">
            <div className="text-2xl font-bold text-green-600">{summaryStats.success}</div>
            <div className="text-sm text-gray-600">Sucessos</div>
          </CardContent>
        </Card>
        <Card className="text-center">
          <CardContent className="pt-4">
            <div className="text-2xl font-bold text-yellow-600">{summaryStats.warning}</div>
            <div className="text-sm text-gray-600">Avisos</div>
          </CardContent>
        </Card>
        <Card className="text-center">
          <CardContent className="pt-4">
            <div className="text-2xl font-bold text-red-600">{summaryStats.error}</div>
            <div className="text-sm text-gray-600">Erros</div>
          </CardContent>
        </Card>
        <Card className="text-center">
          <CardContent className="pt-4">
            <div className="text-2xl font-bold text-blue-600">{summaryStats.total}</div>
            <div className="text-sm text-gray-600">Total</div>
          </CardContent>
        </Card>
      </div>

      <Tabs
        defaultValue={visibleCategories.includes('security') ? 'security' : (visibleCategories[0] ?? 'api')}
        className="space-y-4"
      >
        <TabsList
          className="grid w-full"
          style={{ gridTemplateColumns: `repeat(${Math.max(visibleCategories.length, 1)}, minmax(0, 1fr))` }}
        >
          {visibleCategories.map((category) => (
            <TabsTrigger key={category} value={category} className="flex items-center space-x-2">
              {categoryIcons[category]}
              <span className="hidden sm:inline">{categoryNames[category]}</span>
            </TabsTrigger>
          ))}
        </TabsList>

        {visibleCategories.map((category) => (
          <TabsContent key={category} value={category}>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  {categoryIcons[category]}
                  <span>{categoryNames[category]}</span>
                </CardTitle>
                <CardDescription>
                  Verificação das configurações de {categoryNames[category].toLowerCase()}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {(categorizedChecks[category] || []).map((check) => (
                  <div key={check.id} className="flex items-center justify-between p-4 border rounded-lg">
                    <div className="flex items-start space-x-3 flex-1">
                      {getStatusIcon(check.status)}
                      <div className="flex-1">
                        <div className="flex items-center space-x-2">
                          <h4 className="font-medium">{check.name}</h4>
                          {check.required && (
                            <Badge variant="outline" className="text-xs">
                              Obrigatório
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm text-gray-600 mt-1">{check.description}</p>
                        {check.value && (
                          <div className="flex items-center space-x-2 mt-2">
                            <code className="text-xs bg-gray-100 px-2 py-1 rounded">
                              {check.id.includes('key') || check.id.includes('dsn')
                                ? showSecrets[check.id]
                                  ? check.value
                                  : '****'
                                : check.value}
                            </code>
                            {(check.id.includes('key') || check.id.includes('dsn')) && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => toggleSecret(check.id)}
                                className="h-6 w-6 p-0"
                              >
                                {showSecrets[check.id] ? (
                                  <EyeOff className="w-3 h-3" />
                                ) : (
                                  <Eye className="w-3 h-3" />
                                )}
                              </Button>
                            )}
                          </div>
                        )}
                        {check.error && (
                          <Alert className="mt-2" variant="destructive">
                            <AlertDescription className="text-xs">{check.error}</AlertDescription>
                          </Alert>
                        )}
                      </div>
                    </div>
                    <div className="flex-shrink-0">{getStatusBadge(check.status)}</div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </TabsContent>
        ))}
      </Tabs>

      <div className="flex flex-col sm:flex-row gap-4 pt-6">
        <Button onClick={handleCheckEnvironment} disabled={isChecking} className="flex-1">
          {isChecking ? (
            <>
              <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
              Verificando...
            </>
          ) : (
            <>
              <RefreshCw className="w-4 h-4 mr-2" />
              Verificar Novamente
            </>
          )}
        </Button>

        <Button
          variant="outline"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex-1 sm:flex-none"
        >
          <Settings className="w-4 h-4 mr-2" />
          Configuração Manual
        </Button>
      </div>

      {showAdvanced && (
        <Card>
          <CardHeader>
            <CardTitle>Configuração Manual</CardTitle>
            <CardDescription>
              Ajuste valores de ambiente do frontend quando necessário. O login da equipe usa
              sessão própria do backend e não depende de provedores externos no navegador.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                As configurações manuais são temporárias e não persistem após o reload. Para
                configuração permanente, defina as variáveis de ambiente no servidor.
              </AlertDescription>
            </Alert>

            {manuallyConfigurableChecks
              .filter((check) => check.status === 'error' || check.status === 'warning')
              .map((check) => (
                <div key={check.id} className="space-y-2">
                  <Label htmlFor={check.id}>{check.name}</Label>
                  <Input
                    id={check.id}
                    type={
                      check.id.includes('key') || check.id.includes('dsn') ? 'password' : 'text'
                    }
                    placeholder={`Digite ${check.name.toLowerCase()}`}
                    value={manualConfig[check.id] || ''}
                    onChange={(e) =>
                      setManualConfig((prev) => ({
                        ...prev,
                        [check.id]: e.target.value,
                      }))
                    }
                  />
                </div>
              ))}

            <Button
              onClick={() => {
                toast({
                  title: 'Configuração Aplicada',
                  description: 'Configurações manuais aplicadas. Verificando novamente...',
                })
                setTimeout(handleCheckEnvironment, 1000)
              }}
              className="w-full"
            >
              Aplicar Configurações
            </Button>
          </CardContent>
        </Card>
      )}

      {isChecking && (
        <div className="text-center py-8">
          <LoadingSpinner size="lg" text="Verificando configurações do ambiente..." />
        </div>
      )}
    </div>
  )
}
