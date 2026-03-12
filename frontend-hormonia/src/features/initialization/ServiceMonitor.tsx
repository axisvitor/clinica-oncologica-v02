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
  ExternalLink,
} from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { toast } from '@/hooks/use-toast'
import { createLogger } from '@/lib/logger'
import { loadConfig } from '@/config'
import { apiClient } from '@/lib/api-client'

const logger = createLogger('ServiceMonitor')
const AUTH_MODE = 'first-party-session'

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

export function ServiceMonitor({ onComplete, onError }: ServiceMonitorProps) {
  const [services, setServices] = useState<Service[]>([
    {
      id: 'session-auth',
      name: 'Sessão do Backend',
      description: 'Prontidão do login e restore via cookies HTTP + CSRF próprio',
      category: 'auth',
      status: 'pending',
      required: true,
    },
    {
      id: 'websocket',
      name: 'WebSocket de Sessão',
      description: 'Conectividade em tempo real alinhada ao contrato de sessão',
      category: 'websocket',
      status: 'pending',
      required: false,
    },
    {
      id: 'whatsapp',
      name: 'WhatsApp Business API',
      description: 'Integração com WhatsApp para notificações',
      category: 'messaging',
      status: 'pending',
      required: false,
    },
    {
      id: 'sentry',
      name: 'Sentry Error Tracking',
      description: 'Monitoramento de erros em produção',
      category: 'monitoring',
      status: 'pending',
      required: false,
    },
    {
      id: 'ai',
      name: 'Serviços de IA',
      description: 'Recursos de IA disponíveis no backend',
      category: 'ai',
      status: 'pending',
      required: false,
    },
  ])

  const [isChecking, setIsChecking] = useState(false)
  const [currentServiceIndex, setCurrentServiceIndex] = useState(0)
  const [overallProgress, setOverallProgress] = useState(0)

  const categoryIcons = {
    auth: <Shield className="w-4 h-4" />,
    messaging: <MessageSquare className="w-4 h-4" />,
    monitoring: <Activity className="w-4 h-4" />,
    ai: <Wifi className="w-4 h-4" />,
    websocket: <Wifi className="w-4 h-4" />,
  }

  const categoryNames = {
    auth: 'Autenticação',
    messaging: 'Mensagens',
    monitoring: 'Monitoramento',
    ai: 'Inteligência Artificial',
    websocket: 'Tempo Real',
  }

  useEffect(() => {
    handleCheckServices()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- handleCheckServices is intentionally only called on mount
  }, [])

  const updateServiceStatus = (
    id: string,
    status: Service['status'],
    responseTime?: number,
    error?: string,
    details?: Record<string, unknown>
  ) => {
    setServices((prev) =>
      prev.map((service) =>
        service.id === id
          ? {
              ...service,
              status,
              responseTime,
              error,
              details,
              lastCheck: new Date(),
            }
          : service
      )
    )
  }

  const handleCheckServices = async () => {
    setIsChecking(true)
    setCurrentServiceIndex(0)
    setOverallProgress(0)
    logger.log('Starting service checks', { auth_mode: AUTH_MODE })

    const observedStatuses = new Map<string, Service['status']>()
    const markService = (
      id: string,
      status: Service['status'],
      responseTime?: number,
      error?: string,
      details?: Record<string, unknown>
    ) => {
      observedStatuses.set(id, status)
      updateServiceStatus(id, status, responseTime, error, details)
    }

    try {
      const config = await loadConfig()

      if (config.API_BASE_URL) {
        apiClient.setBaseURL(config.API_BASE_URL)
      }

      setServices((prev) =>
        prev.map((service) => ({
          ...service,
          status: 'pending' as const,
          error: undefined,
          details: undefined,
          responseTime: undefined,
        }))
      )

      const servicesToCheck = services.map((service) => ({ ...service }))
      servicesToCheck.forEach((service) => observedStatuses.set(service.id, 'pending'))

      for (let i = 0; i < servicesToCheck.length; i++) {
        const service = servicesToCheck[i]
        if (!service) continue

        setCurrentServiceIndex(i)
        markService(service.id, 'checking')

        const startTime = Date.now()

        try {
          const details = await checkService(service, config)
          const responseTime = Date.now() - startTime
          markService(service.id, 'healthy', responseTime, undefined, details)
        } catch (error) {
          const responseTime = Date.now() - startTime
          const errorMessage = error instanceof Error ? error.message : 'Serviço indisponível'
          const normalizedError = errorMessage.toLowerCase()
          const status: Service['status'] =
            normalizedError.includes('degraded') ||
            normalizedError.includes('não configur') ||
            normalizedError.includes('timeout') ||
            normalizedError.includes('network')
              ? 'degraded'
              : 'unhealthy'

          markService(service.id, status, responseTime, errorMessage)
          logger.error(`Service '${service.id}' check failed:`, error)
        }

        const progress = Math.round(((i + 1) / servicesToCheck.length) * 100)
        setOverallProgress(progress)
        await new Promise((resolve) => setTimeout(resolve, 300))
      }

      logger.log('Service auth diagnostics', {
        auth_mode: AUTH_MODE,
        session_auth_status: observedStatuses.get('session-auth') ?? 'pending',
        websocket_status: observedStatuses.get('websocket') ?? 'pending',
      })

      const failedRequiredServices = servicesToCheck.filter(
        (service) => service.required && observedStatuses.get(service.id) === 'unhealthy'
      )

      if (failedRequiredServices.length > 0) {
        onError(
          `Serviços críticos falharam: ${failedRequiredServices.map((service) => service.name).join(', ')}`
        )
      } else {
        const degradedServices = servicesToCheck.filter(
          (service) => observedStatuses.get(service.id) === 'degraded'
        ).length
        const unhealthyServices = servicesToCheck.filter(
          (service) => observedStatuses.get(service.id) === 'unhealthy'
        ).length

        let message = 'Verificação de serviços concluída.'
        if (degradedServices > 0 || unhealthyServices > 0) {
          message += ` ${degradedServices + unhealthyServices} serviços com problemas.`
        }

        toast({
          title: 'Serviços Verificados',
          description: message,
          variant: failedRequiredServices.length > 0 ? 'destructive' : 'default',
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

  const checkService = async (
    service: Service,
    config: AppConfig
  ): Promise<Record<string, unknown> | undefined> => {
    switch (service.id) {
      case 'session-auth':
        return checkSessionAuth(config)
      case 'websocket':
        return checkWebSocket(config)
      case 'whatsapp':
        return checkWhatsApp(config)
      case 'sentry':
        return checkSentry(config)
      case 'ai':
        return checkAI(config)
      default:
        throw new Error(`Unknown service: ${service.id}`)
    }
  }

  const checkSessionAuth = async (config: AppConfig): Promise<Record<string, unknown>> => {
    if (!config.API_BASE_URL) {
      throw new Error('API não configurada para autenticação por sessão')
    }

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
        throw new Error('Sessão HTTP sem token CSRF válido')
      }

      return {
        auth_mode: AUTH_MODE,
        csrf_ready: true,
        endpoint: `${config.API_BASE_URL}/api/v2/auth/csrf-token`,
      }
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        throw new Error('timeout na preparação da sessão HTTP')
      }
      throw error
    } finally {
      clearTimeout(timeoutId)
    }
  }

  const checkWebSocket = async (config: AppConfig): Promise<Record<string, unknown>> => {
    if (!config.WS_BASE_URL) {
      throw new Error('degraded: WebSocket não configurado')
    }

    return new Promise<Record<string, unknown>>((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Timeout na conexão WebSocket'))
      }, 5000)

      try {
        const wsUrl = config.WS_BASE_URL!.replace(/^http/, 'ws')
        const ws = new WebSocket(wsUrl)

        ws.onopen = () => {
          clearTimeout(timeout)
          ws.close()
          resolve({
            url: wsUrl,
            protocol: ws.protocol || 'default',
            auth_mode: AUTH_MODE,
          })
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

  const checkWhatsApp = async (config: AppConfig): Promise<Record<string, unknown>> => {
    if (!config.WHATSAPP_INSTANCE_NAME) {
      throw new Error('WhatsApp não configurado')
    }

    await new Promise((resolve) => setTimeout(resolve, 1000))

    return {
      instance: config.WHATSAPP_INSTANCE_NAME,
      status: 'mock_healthy',
    }
  }

  const checkSentry = async (config: AppConfig): Promise<Record<string, unknown>> => {
    if (!config.SENTRY_DSN) {
      throw new Error('Sentry não configurado')
    }

    const sentryDsnRegex = /^https:\/\/[a-f0-9]+@[a-z0-9]+\.ingest\.sentry\.io\/[0-9]+$/
    if (!sentryDsnRegex.test(config.SENTRY_DSN)) {
      throw new Error('DSN Sentry inválido')
    }

    return {
      configured: true,
      environment: (config['ENVIRONMENT'] as string) || 'development',
    }
  }

  const checkAI = async (config: AppConfig): Promise<Record<string, unknown>> => {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 5000)

    try {
      const response = await fetch(`${config.API_BASE_URL}/api/v2/ai/health`, {
        method: 'GET',
        credentials: 'include',
        headers: {
          Accept: 'application/json',
          ...apiClient.getSessionHeaders(),
        },
        signal: controller.signal,
      })

      if (!response.ok) {
        throw new Error(`Healthcheck IA retornou status ${response.status}`)
      }

      const data = (await response.json()) as {
        status?: string
        gemini_api?: { status?: string; enabled?: boolean }
      }
      const backendStatus = (data?.status as string | undefined) || 'unknown'
      const geminiStatus = (data?.gemini_api?.status as string | undefined) || 'unknown'
      const geminiEnabled = data?.gemini_api?.enabled === true

      if (backendStatus === 'unhealthy') {
        throw new Error('IA indisponível')
      }

      if (backendStatus === 'degraded' || !geminiEnabled) {
        throw new Error(
          `degraded: IA ${geminiEnabled ? 'degradada' : 'não configurada'} (${geminiStatus})`
        )
      }

      return {
        backendStatus,
        geminiStatus,
        geminiEnabled,
      }
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
        return (
          <Badge variant="default" className="bg-green-100 text-green-800">
            Saudável
          </Badge>
        )
      case 'degraded':
        return (
          <Badge variant="secondary" className="bg-yellow-100 text-yellow-800">
            Degradado
          </Badge>
        )
      case 'unhealthy':
        return <Badge variant="destructive">Indisponível</Badge>
      case 'checking':
        return (
          <Badge variant="outline" className="bg-blue-100 text-blue-800">
            Verificando
          </Badge>
        )
      default:
        return <Badge variant="outline">Pendente</Badge>
    }
  }

  const formatResponseTime = (ms?: number) => {
    if (!ms) return ''
    if (ms < 1000) return `${ms}ms`
    return `${(ms / 1000).toFixed(1)}s`
  }

  const servicesByCategory = services.reduce(
    (acc, service) => {
      const category = service.category
      if (!acc[category]) {
        acc[category] = []
      }
      acc[category]?.push(service)
      return acc
    },
    {} as Record<string, Service[]>
  )

  const summaryStats = {
    total: services.length,
    healthy: services.filter((s) => s.status === 'healthy').length,
    degraded: services.filter((s) => s.status === 'degraded').length,
    unhealthy: services.filter((s) => s.status === 'unhealthy').length,
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center space-x-2">
                <Activity className="w-5 h-5" />
                <span>Monitoramento de Serviços</span>
              </CardTitle>
              <CardDescription>
                Verificando sessão própria, tempo real e integrações externas
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
                className={`flex items-center justify-between p-4 border rounded-lg transition-colors ${
                  index === currentServiceIndex && isChecking ? 'bg-blue-50 border-blue-200' : ''
                }`}
              >
                <div className="flex items-start space-x-3 flex-1">
                  {getStatusIcon(service.status)}
                  <div className="flex-1">
                    <div className="flex items-center space-x-2">
                      <h4 className="font-medium">{service.name}</h4>
                      {service.required && (
                        <Badge variant="outline" className="text-xs">
                          Obrigatório
                        </Badge>
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

      <div className="flex flex-col sm:flex-row gap-4">
        <Button onClick={handleCheckServices} disabled={isChecking} className="flex-1">
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
