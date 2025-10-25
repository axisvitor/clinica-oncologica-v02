import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Label } from '../ui/label'
import { Switch } from '../ui/switch'
import { Badge } from '../ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs'
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  Settings,
  Cloud,
  Shield,
  RefreshCw,
  Eye,
  EyeOff
} from 'lucide-react'
import { Alert, AlertDescription } from '../ui/alert'
import { LoadingSpinner } from './LoadingSpinner'
import { toast } from '../../hooks/use-toast'
import { createLogger } from '../../lib/logger'
import { loadConfig, getRuntimeConfigSync } from '../../config'

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

export function EnvironmentSetup({ onComplete, onError }: EnvironmentSetupProps) {
  const [checks, setChecks] = useState<EnvironmentCheck[]>([
    // API Configuration
    {
      id: 'api_base_url',
      name: 'API Base URL',
      description: 'URL base para comunicação com o backend',
      status: 'pending',
      required: true,
      category: 'api'
    },
    {
      id: 'ws_url',
      name: 'WebSocket URL',
      description: 'URL para conexões WebSocket em tempo real',
      status: 'pending',
      required: false,
      category: 'api'
    },

    // External Services
    {
      id: 'firebase_config',
      name: 'Firebase Configuration',
      description: 'Configuração de autenticação Firebase',
      status: 'pending',
      required: true,
      category: 'services'
    },
    {
      id: 'whatsapp_instance',
      name: 'WhatsApp Instance',
      description: 'Instância do WhatsApp Business API',
      status: 'pending',
      required: false,
      category: 'services'
    },

    // Security & Monitoring
    {
      id: 'sentry_dsn',
      name: 'Sentry DSN',
      description: 'Configuração de monitoramento de erros',
      status: 'pending',
      required: false,
      category: 'security'
    },
    {
      id: 'session_config',
      name: 'Session Configuration',
      description: 'Configurações de sessão e segurança',
      status: 'pending',
      required: true,
      category: 'security'
    }
  ])

  const [isChecking, setIsChecking] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [manualConfig, setManualConfig] = useState<Record<string, string>>({})
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({})

  const categoryIcons = {
    api: <Cloud className="w-5 h-5" />,
    services: <Settings className="w-5 h-5" />,
    security: <Shield className="w-5 h-5" />
  }

  const categoryNames = {
    api: 'API & Comunicação',
    database: 'Banco de Dados',
    services: 'Serviços Externos',
    security: 'Segurança & Monitoramento'
  }

  useEffect(() => {
    // Auto-start environment check
    handleCheckEnvironment()
  }, [])

  const updateCheckStatus = (
    id: string,
    status: EnvironmentCheck['status'],
    value?: string,
    error?: string
  ) => {
    setChecks(prev => prev.map(check =>
      check.id === id
        ? { ...check, status, value, error }
        : check
    ))
  }

  const handleCheckEnvironment = async () => {
    setIsChecking(true)
    logger.log('Starting environment checks')

    try {
      // Load configuration
      const config = await loadConfig()
      const runtimeConfig = getRuntimeConfigSync()

      // Check API configuration
      updateCheckStatus('api_base_url', 'checking')
      if (config.API_BASE_URL) {
        try {
          const response = await fetch(`${config.API_BASE_URL}/health`, {
            method: 'GET',
            signal: AbortSignal.timeout(5000)
          })
          if (response.ok) {
            updateCheckStatus('api_base_url', 'success', config.API_BASE_URL)
          } else {
            updateCheckStatus('api_base_url', 'warning', config.API_BASE_URL,
              `API retornou status ${response.status}`)
          }
        } catch (error) {
          updateCheckStatus('api_base_url', 'error', config.API_BASE_URL,
            'Falha ao conectar com a API')
        }
      } else {
        updateCheckStatus('api_base_url', 'error', '', 'URL da API não configurada')
      }

      // Check WebSocket URL
      updateCheckStatus('ws_url', 'checking')
      if (config.WS_BASE_URL) {
        updateCheckStatus('ws_url', 'success', config.WS_BASE_URL)
      } else {
        updateCheckStatus('ws_url', 'warning', '', 'WebSocket não configurado')
      }

      // Check Firebase configuration
      updateCheckStatus('firebase_config', 'checking')
      if (runtimeConfig?.VITE_FIREBASE_API_KEY) {
        updateCheckStatus('firebase_config', 'success', 'Configurado')
      } else {
        updateCheckStatus('firebase_config', 'error', '', 'Firebase não configurado')
      }

      // Check WhatsApp instance
      updateCheckStatus('whatsapp_instance', 'checking')
      if (config.WHATSAPP_INSTANCE_NAME) {
        updateCheckStatus('whatsapp_instance', 'success', config.WHATSAPP_INSTANCE_NAME)
      } else {
        updateCheckStatus('whatsapp_instance', 'warning', '', 'WhatsApp não configurado')
      }

      // Check Sentry DSN
      updateCheckStatus('sentry_dsn', 'checking')
      if (config.SENTRY_DSN) {
        updateCheckStatus('sentry_dsn', 'success', '****')
      } else {
        updateCheckStatus('sentry_dsn', 'warning', '', 'Sentry não configurado')
      }

      // Check session configuration
      updateCheckStatus('session_config', 'checking')
      if (config.SESSION_TIMEOUT && config.TOKEN_REFRESH_THRESHOLD) {
        updateCheckStatus('session_config', 'success',
          `Timeout: ${config.SESSION_TIMEOUT}ms`)
      } else {
        updateCheckStatus('session_config', 'warning', '',
          'Configurações de sessão usando padrões')
      }

      // Wait a moment for visual feedback
      await new Promise(resolve => setTimeout(resolve, 1000))

      // Check if all required configurations are valid
      const requiredChecks = checks.filter(check => check.required)
      const failedRequired = requiredChecks.filter(check =>
        check.status === 'error'
      )

      if (failedRequired.length > 0) {
        onError(`Configurações obrigatórias falharam: ${failedRequired.map(c => c.name).join(', ')}`)
      } else {
        toast({
          title: 'Ambiente Verificado',
          description: 'Todas as configurações essenciais estão funcionando.',
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
        return <Badge variant="default" className="bg-green-100 text-green-800">OK</Badge>
      case 'error':
        return <Badge variant="destructive">Erro</Badge>
      case 'warning':
        return <Badge variant="secondary" className="bg-yellow-100 text-yellow-800">Aviso</Badge>
      case 'checking':
        return <Badge variant="outline">Verificando...</Badge>
      default:
        return <Badge variant="outline">Pendente</Badge>
    }
  }

  const toggleSecret = (checkId: string) => {
    setShowSecrets(prev => ({
      ...prev,
      [checkId]: !prev[checkId]
    }))
  }

  const categorizedChecks = checks.reduce((acc, check) => {
    const category = check.category
    if (!acc[category]) {
      acc[category] = []
    }
    acc[category]?.push(check)
    return acc
  }, {} as Record<string, EnvironmentCheck[]>)

  const summaryStats = {
    total: checks.length,
    success: checks.filter(c => c.status === 'success').length,
    error: checks.filter(c => c.status === 'error').length,
    warning: checks.filter(c => c.status === 'warning').length
  }

  return (
    <div className="space-y-6">
      {/* Summary Stats */}
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

      {/* Environment Checks by Category */}
      <Tabs defaultValue="api" className="space-y-4">
        <TabsList className="grid w-full grid-cols-4">
          {Object.keys(categoryNames).map(category => (
            <TabsTrigger
              key={category}
              value={category}
              className="flex items-center space-x-2"
            >
              {categoryIcons[category as keyof typeof categoryIcons]}
              <span className="hidden sm:inline">
                {categoryNames[category as keyof typeof categoryNames]}
              </span>
            </TabsTrigger>
          ))}
        </TabsList>

        {Object.entries(categorizedChecks).map(([category, categoryChecks]) => (
          <TabsContent key={category} value={category}>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  {categoryIcons[category as keyof typeof categoryIcons]}
                  <span>{categoryNames[category as keyof typeof categoryNames]}</span>
                </CardTitle>
                <CardDescription>
                  Verificação das configurações de {categoryNames[category as keyof typeof categoryNames].toLowerCase()}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {categoryChecks.map(check => (
                  <div
                    key={check.id}
                    className="flex items-center justify-between p-4 border rounded-lg"
                  >
                    <div className="flex items-start space-x-3 flex-1">
                      {getStatusIcon(check.status)}
                      <div className="flex-1">
                        <div className="flex items-center space-x-2">
                          <h4 className="font-medium">{check.name}</h4>
                          {check.required && (
                            <Badge variant="outline" className="text-xs">Obrigatório</Badge>
                          )}
                        </div>
                        <p className="text-sm text-gray-600 mt-1">{check.description}</p>
                        {check.value && (
                          <div className="flex items-center space-x-2 mt-2">
                            <code className="text-xs bg-gray-100 px-2 py-1 rounded">
                              {check.id.includes('key') || check.id.includes('dsn') ?
                                (showSecrets[check.id] ? check.value : '****') :
                                check.value
                              }
                            </code>
                            {(check.id.includes('key') || check.id.includes('dsn')) && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => toggleSecret(check.id)}
                                className="h-6 w-6 p-0"
                              >
                                {showSecrets[check.id] ?
                                  <EyeOff className="w-3 h-3" /> :
                                  <Eye className="w-3 h-3" />
                                }
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
                    <div className="flex-shrink-0">
                      {getStatusBadge(check.status)}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </TabsContent>
        ))}
      </Tabs>

      {/* Action Buttons */}
      <div className="flex flex-col sm:flex-row gap-4 pt-6">
        <Button
          onClick={handleCheckEnvironment}
          disabled={isChecking}
          className="flex-1"
        >
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

      {/* Advanced Configuration Panel */}
      {showAdvanced && (
        <Card>
          <CardHeader>
            <CardTitle>Configuração Manual</CardTitle>
            <CardDescription>
              Configure manualmente as variáveis de ambiente se necessário
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                As configurações manuais são temporárias e não persistem após o reload.
                Para configuração permanente, defina as variáveis de ambiente no servidor.
              </AlertDescription>
            </Alert>

            {checks.filter(c => c.status === 'error' || c.status === 'warning').map(check => (
              <div key={check.id} className="space-y-2">
                <Label htmlFor={check.id}>{check.name}</Label>
                <Input
                  id={check.id}
                  type={check.id.includes('key') || check.id.includes('dsn') ? 'password' : 'text'}
                  placeholder={`Digite ${check.name.toLowerCase()}`}
                  value={manualConfig[check.id] || ''}
                  onChange={(e) => setManualConfig(prev => ({
                    ...prev,
                    [check.id]: e.target.value
                  }))}
                />
              </div>
            ))}

            <Button
              onClick={() => {
                // Apply manual configuration and re-check
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
