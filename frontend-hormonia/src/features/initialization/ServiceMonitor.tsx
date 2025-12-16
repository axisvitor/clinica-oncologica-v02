import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Wifi,
  MessageSquare,
  Shield,
  Activity,
  Clock,
  ExternalLink
} from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { LoadingSpinner } from './LoadingSpinner'
import { toast } from '@/hooks/use-toast'
import { createLogger } from '@/lib/logger'
import { loadConfig } from '@/config'

const logger = createLogger('ServiceMonitor')

interface ServiceDetails {
  configured?: boolean
  enabled?: boolean
  [key: string]: unknown
}

interface Service {
  id: string
  name: string
  description: string
  category: 'auth' | 'messaging' | 'monitoring' | 'ai' | 'websocket'
  status: 'pending' | 'checking' | 'healthy' | 'degraded' | 'unhealthy' | 'unknown'
  required: boolean
  url?: string | undefined
  responseTime?: number | undefined
  lastCheck?: Date | undefined
  error?: string | undefined
  details?: ServiceDetails
}

interface AppConfig {
  API_BASE_URL: string
  WS_BASE_URL?: string
  WHATSAPP_INSTANCE_NAME?: string
  SENTRY_DSN?: string
  AI_CHAT_ENABLED?: boolean
  AI_ANALYTICS_ENABLED?: boolean
  [key: string]: unknown
}

interface ServiceMonitorProps {
  onComplete: () => void
  onError: (error: string) => void
}

export function ServiceMonitor({ onComplete, onError }: ServiceMonitorProps) {
  const [services, setServices] = useState<Service[]>([
    {
      id: 'firebase-auth',
      name: 'Firebase Authentication',
      description: 'Serviço de autenticação de usuários',
      category: 'auth',
      status: 'pending',
      required: true
    },
    {
      id: 'websocket',
      name: 'WebSocket Server',
      description: 'Comunicação em tempo real',
      category: 'websocket',
      status: 'pending',
      required: false
    },
    {
      id: 'whatsapp',
      name: 'WhatsApp Business API',
      description: 'Integração com WhatsApp para notificações',
      category: 'messaging',
      status: 'pending',
      required: false
    },
    {
      id: 'sentry',
      name: 'Sentry Error Tracking',
      description: 'Monitoramento de erros em produção',
      category: 'monitoring',
      status: 'pending',
      required: false
    },
    {
      id: 'ai',
      name: 'Serviços de IA',
      description: 'Recursos de IA disponíveis no backend',
      category: 'ai',
      status: 'pending',
      required: false
    }
  ])

  const [isChecking, setIsChecking] = useState(false)
  const [currentServiceIndex, setCurrentServiceIndex] = useState(0)
  const [overallProgress, setOverallProgress] = useState(0)

  const categoryIcons = {
    auth: <Shield className="w-4 h-4" />,
    messaging: <MessageSquare className="w-4 h-4" />,
    monitoring: <Activity className="w-4 h-4" />,
    ai: <Wifi className="w-4 h-4" />,
    websocket: <Wifi className="w-4 h-4" />
  }

  const categoryNames = {
    auth: 'Autenticação',
    messaging: 'Mensagens',
    monitoring: 'Monitoramento',
    ai: 'Inteligência Artificial',
    websocket: 'Tempo Real'
  }

  useEffect(() => {
    // Auto-start service checks
    handleCheckServices()
  }, [])

  const updateServiceStatus = (
    id: string,
    status: Service['status'],
    responseTime?: number,
    error?: string,
    details?: any
  ) => {
    setServices(prev => prev.map(service =>
      service.id === id
        ? {
          ...service,
          status,
          responseTime,
          error,
          details,
          lastCheck: new Date()
        }
        : service
    ))
  }

  const handleCheckServices = async () => {
    setIsChecking(true)
    setCurrentServiceIndex(0)
    setOverallProgress(0)
    logger.log('Starting service checks')

    try {
      // Load configuration
      const config = await loadConfig()

      // Reset all services to pending
      setServices(prev => prev.map(service => ({ ...service, status: 'pending' as const })))

      for (let i = 0; i < services.length; i++) {
        const service = services[i]
        if (!service) continue

        setCurrentServiceIndex(i)
        updateServiceStatus(service.id, 'checking')

        const startTime = Date.now()

        try {
          await checkService(service, config)
          const responseTime = Date.now() - startTime
          updateServiceStatus(service.id, 'healthy', responseTime)
        } catch (error) {
          const responseTime = Date.now() - startTime
          const errorMessage = error instanceof Error ? error.message : 'Serviço indisponível'

          // Determine status based on error type
          const normalizedError = errorMessage.toLowerCase()
          const status = (
            normalizedError.includes('degraded') ||
            normalizedError.includes('não configur') ||
            normalizedError.includes('timeout') ||
            normalizedError.includes('network')
          )
            ? 'degraded'
            : 'unhealthy'

          updateServiceStatus(service.id, status, responseTime, errorMessage)
          logger.error(`Service '${service.id}' check failed:`, error)
        }

        // Update progress
        const progress = Math.round(((i + 1) / services.length) * 100)
        setOverallProgress(progress)

        // Small delay for visual feedback
        await new Promise(resolve => setTimeout(resolve, 300))
      }

      // Check results - only fail if required services are unhealthy
      const failedRequiredServices = services.filter(s =>
        s.required && s.status === 'unhealthy'
      )

      if (failedRequiredServices.length > 0) {
        onError(`Serviços críticos falharam: ${failedRequiredServices.map(s => s.name).join(', ')}`)
      } else {
        const degradedServices = services.filter(s => s.status === 'degraded').length
        const unhealthyServices = services.filter(s => s.status === 'unhealthy').length

        let message = 'Verificação de serviços concluída.'
        if (degradedServices > 0 || unhealthyServices > 0) {
          message += ` ${degradedServices + unhealthyServices} serviços com problemas.`
        }

        toast({
          title: 'Serviços Verificados',
          description: message,
          variant: failedRequiredServices.length > 0 ? 'destructive' : 'default'
        })
        onComplete()
      }

    } catch (error) {
      logger.error('Service monitoring failed:', error)
      onError('Falha na verificação dos serviços: ' + (error as Error).message)
    } finally {
      setIsChecking(false)
    }
  }

  const checkService = async (service: Service, config: AppConfig): Promise<void> => {
    switch (service.id) {
      case 'firebase-auth':
        await checkFirebaseAuth(config)
        break
      case 'websocket':
        await checkWebSocket(config)
        break
      case 'whatsapp':
        await checkWhatsApp(config)
        break
      case 'sentry':
        await checkSentry(config)
        break
      case 'ai':
        await checkAI(config)
        break
      default:
        throw new Error(`Unknown service: ${service.id}`)
    }
  }

  const checkFirebaseAuth = async (config: AppConfig) => {
    if (!config['FIREBASE_CONFIG']) {
      throw new Error('Firebase não configurado')
    }

    // Try to validate Firebase configuration
    try {
      const { firebaseAuthLazy } = await import('@/lib/firebase-lazy')
      if (!firebaseAuthLazy.isConfigured()) {
        throw new Error('Configuração Firebase inválida')
      }
      updateServiceStatus('firebase-auth', 'checking', undefined, undefined, {
        configured: true,
        projectId: (config['FIREBASE_CONFIG'] as { projectId?: string }).projectId || 'N/A'
      })
    } catch (error) {
      throw new Error('Falha na validação Firebase')
    }
  }

  const checkWebSocket = async (config: AppConfig) => {
    if (!config.WS_BASE_URL) {
      throw new Error('WebSocket não configurado')
    }

    // Try to create a test WebSocket connection
    return new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Timeout na conexão WebSocket'))
      }, 5000)

      try {
        const wsUrl = config.WS_BASE_URL!.replace(/^http/, 'ws')
        const ws = new WebSocket(wsUrl)

        ws.onopen = () => {
          clearTimeout(timeout)
          ws.close()
          updateServiceStatus('websocket', 'checking', undefined, undefined, {
            url: wsUrl,
            protocol: ws.protocol || 'default'
          })
          resolve()
        }

        ws.onerror = () => {
          clearTimeout(timeout)
          reject(new Error('Erro na conexão WebSocket'))
        }

        ws.onclose = (event) => {
          if (event.code !== 1000) {
            clearTimeout(timeout)
            reject(new Error(`WebSocket fechou com código: ${event.code}`))
          }
        }
      } catch (error) {
        clearTimeout(timeout)
        reject(error)
      }
    })
  }

  const checkWhatsApp = async (config: AppConfig) => {
    if (!config.WHATSAPP_INSTANCE_NAME) {
      throw new Error('WhatsApp não configurado')
    }

    // Mock check - in real implementation, ping WhatsApp API
    await new Promise(resolve => setTimeout(resolve, 1000))

    updateServiceStatus('whatsapp', 'checking', undefined, undefined, {
      instance: config.WHATSAPP_INSTANCE_NAME,
      status: 'mock_healthy'
    })
  }

  const checkSentry = async (config: AppConfig) => {
    if (!config.SENTRY_DSN) {
      throw new Error('Sentry não configurado')
    }

    // Validate Sentry DSN format
    const sentryDsnRegex = /^https:\/\/[a-f0-9]+@[a-z0-9]+\.ingest\.sentry\.io\/[0-9]+$/
    if (!sentryDsnRegex.test(config.SENTRY_DSN)) {
      throw new Error('DSN Sentry inválido')
    }

    updateServiceStatus('sentry', 'checking', undefined, undefined, {
      configured: true,
      environment: config['ENVIRONMENT'] as string || 'development'
    })
  }

  const checkAI = async (config: AppConfig) => {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 5000)

    try {
      const response = await fetch(`${config.API_BASE_URL}/api/v2/ai/health`, {
        method: 'GET',
        credentials: 'include',
        headers: {
          'Accept': 'application/json'
        },
        signal: controller.signal
      })

      if (!response.ok) {
        throw new Error(`Healthcheck IA retornou status ${response.status}`)
      }

      const data = await response.json() as any
      const backendStatus = (data?.status as string | undefined) || 'unknown'
      const geminiStatus = (data?.gemini_api?.status as string | undefined) || 'unknown'
      const geminiEnabled = data?.gemini_api?.enabled === true

      if (backendStatus === 'unhealthy') {
        throw new Error('IA indisponível')
      }

      if (backendStatus === 'degraded' || !geminiEnabled) {
        throw new Error(`degraded: IA ${geminiEnabled ? 'degradada' : 'não configurada'} (${geminiStatus})`)
      }

      updateServiceStatus('ai', 'checking', undefined, undefined, {
        backendStatus,
        geminiStatus,
        geminiEnabled,
      })
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        throw new Error('timeout na verificação de IA')
      }
      throw error
    } finally {
      clearTimeout(timeoutId)
    }
  }

  const getStatusIcon = (status: Service['status']) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="w-5 h-5 text-green-500" />
      case 'degraded':
        return <AlertTriangle className="w-5 h-5 text-yellow-500" />
      case 'unhealthy':
        return <XCircle className="w-5 h-5 text-red-500" />
      case 'checking':
        return <RefreshCw className="w-5 h-5 text-blue-500 animate-spin" />
      default:
        return <div className="w-5 h-5 border-2 border-gray-300 rounded-full" />
    }
  }

  const getStatusBadge = (status: Service['status']) => {
    switch (status) {
      case 'healthy':
        return <Badge variant="default" className="bg-green-100 text-green-800">Saudável</Badge>
      case 'degraded':
        return <Badge variant="secondary" className="bg-yellow-100 text-yellow-800">Degradado</Badge>
      case 'unhealthy':
        return <Badge variant="destructive">Indisponível</Badge>
      case 'checking':
        return <Badge variant="outline" className="bg-blue-100 text-blue-800">Verificando</Badge>
      default:
        return <Badge variant="outline">Pendente</Badge>
    }
  }

  const formatResponseTime = (ms?: number) => {
    if (!ms) return ''
    if (ms < 1000) return `${ms}ms`
    return `${(ms / 1000).toFixed(1)}s`
  }

  const servicesByCategory = services.reduce((acc, service) => {
    const category = service.category
    if (!acc[category]) {
      acc[category] = []
    }
    acc[category]?.push(service)
    return acc
  }, {} as Record<string, Service[]>)

  const summaryStats = {
    total: services.length,
    healthy: services.filter(s => s.status === 'healthy').length,
    degraded: services.filter(s => s.status === 'degraded').length,
    unhealthy: services.filter(s => s.status === 'unhealthy').length
  }

  return (
    <div className="space-y-6">
      {/* Progress Overview */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center space-x-2">
                <Activity className="w-5 h-5" />
                <span>Monitoramento de Serviços</span>
              </CardTitle>
              <CardDescription>
                Verificando conectividade e saúde dos serviços externos
              </CardDescription>
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold text-blue-600">{overallProgress}%</div>
              <div className="text-sm text-gray-600">Progresso</div>
            </div>
          </div>
          {isChecking && (
            <div className="mt-4">
              <Progress value={overallProgress} />
              <div className="text-sm text-gray-600 mt-2">
                Verificando: {services[currentServiceIndex]?.name}
              </div>
            </div>
          )}
        </CardHeader>
      </Card>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="text-center">
          <CardContent className="pt-4">
            <div className="text-2xl font-bold text-green-600">{summaryStats.healthy}</div>
            <div className="text-sm text-gray-600">Saudáveis</div>
          </CardContent>
        </Card>
        <Card className="text-center">
          <CardContent className="pt-4">
            <div className="text-2xl font-bold text-yellow-600">{summaryStats.degraded}</div>
            <div className="text-sm text-gray-600">Degradados</div>
          </CardContent>
        </Card>
        <Card className="text-center">
          <CardContent className="pt-4">
            <div className="text-2xl font-bold text-red-600">{summaryStats.unhealthy}</div>
            <div className="text-sm text-gray-600">Indisponíveis</div>
          </CardContent>
        </Card>
        <Card className="text-center">
          <CardContent className="pt-4">
            <div className="text-2xl font-bold text-blue-600">{summaryStats.total}</div>
            <div className="text-sm text-gray-600">Total</div>
          </CardContent>
        </Card>
      </div>

      {/* Services by Category */}
      {Object.entries(servicesByCategory).map(([category, categoryServices]) => (
        <Card key={category}>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              {categoryIcons[category as keyof typeof categoryIcons]}
              <span>{categoryNames[category as keyof typeof categoryNames]}</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {categoryServices.map((service, index) => (
              <div
                key={service.id}
                className={`flex items-center justify-between p-4 border rounded-lg transition-colors ${index === currentServiceIndex && isChecking
                    ? 'bg-blue-50 border-blue-200'
                    : ''
                  }`}
              >
                <div className="flex items-start space-x-3 flex-1">
                  {getStatusIcon(service.status)}
                  <div className="flex-1">
                    <div className="flex items-center space-x-2">
                      <h4 className="font-medium">{service.name}</h4>
                      {service.required && (
                        <Badge variant="outline" className="text-xs">Obrigatório</Badge>
                      )}
                      {service.responseTime && (
                        <span className="text-xs text-gray-500 flex items-center">
                          <Clock className="w-3 h-3 mr-1" />
                          {formatResponseTime(service.responseTime)}
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-600 mt-1">{service.description}</p>
                    {service.lastCheck && (
                      <div className="text-xs text-gray-500 mt-1">
                        Última verificação: {service.lastCheck.toLocaleTimeString()}
                      </div>
                    )}
                    {service.details && (
                      <div className="mt-2 text-xs text-gray-500">
                        {Object.entries(service.details).map(([key, value]) => (
                          <span key={key} className="mr-4">
                            {key}: {String(value)}
                          </span>
                        ))}
                      </div>
                    )}
                    {service.error && (
                      <Alert className="mt-2" variant="destructive">
                        <AlertDescription className="text-xs">{service.error}</AlertDescription>
                      </Alert>
                    )}
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  {getStatusBadge(service.status)}
                  {service.url && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => window.open(service.url, '_blank')}
                      className="h-6 w-6 p-0"
                    >
                      <ExternalLink className="w-3 h-3" />
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      ))}

      {/* Action Buttons */}
      <div className="flex flex-col sm:flex-row gap-4">
        <Button
          onClick={handleCheckServices}
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
          onClick={() => {
            toast({
              title: 'Relatório de Serviços',
              description: 'Funcionalidade em desenvolvimento.',
            })
          }}
          className="flex-1 sm:flex-none"
        >
          <Activity className="w-4 h-4 mr-2" />
          Gerar Relatório
        </Button>
      </div>

      {isChecking && (
        <div className="text-center py-8">
          <LoadingSpinner
            size="lg"
            text={`Verificando: ${services[currentServiceIndex]?.name}...`}
            showProgress
            progress={overallProgress}
          />
        </div>
      )}
    </div>
  )
}