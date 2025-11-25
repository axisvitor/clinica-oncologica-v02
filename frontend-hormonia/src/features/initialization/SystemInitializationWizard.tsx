import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { CheckCircle2, XCircle, Loader2, AlertTriangle, ArrowRight, RefreshCcw, Play } from 'lucide-react'
import { LoadingSpinner } from './LoadingSpinner'
import { EnvironmentSetup } from './EnvironmentSetup'
import { DatabaseChecker } from './DatabaseChecker'
import { ServiceMonitor } from './ServiceMonitor'
import { WelcomeFlow } from './WelcomeFlow'
import { InitialUserSetup } from './InitialUserSetup'
import { ErrorBoundary } from '@/components/common/ErrorBoundary'
import { useToast } from '@/components/ui/use-toast'
import { createLogger } from '@/lib/logger'

const logger = createLogger('SystemInitializationWizard')

interface InitializationStep {
  id: string
  title: string
  description: string
  component: React.ComponentType<{ onComplete: () => void; onError: (error: string) => void }>
  required: boolean
  status: 'pending' | 'running' | 'completed' | 'error' | 'skipped'
  error?: string
}

interface SystemInitializationWizardProps {
  onComplete: () => void
  autoStart?: boolean
  skipWelcome?: boolean
}

export function SystemInitializationWizard({
  onComplete,
  autoStart = false,
  skipWelcome = false
}: SystemInitializationWizardProps) {
  const { toast } = useToast()
  const [currentStep, setCurrentStep] = useState(0)
  const [isInitializing, setIsInitializing] = useState(false)
  const [hasStarted, setHasStarted] = useState(autoStart)
  const [initializationSteps, setInitializationSteps] = useState<InitializationStep[]>([
    {
      id: 'welcome',
      title: 'Bem-vindo',
      description: 'Configuração inicial do sistema',
      component: WelcomeFlow,
      required: !skipWelcome,
      status: 'pending'
    },
    {
      id: 'environment',
      title: 'Ambiente',
      description: 'Verificação das configurações do ambiente',
      component: EnvironmentSetup,
      required: true,
      status: 'pending'
    },
    {
      id: 'database',
      title: 'Banco de Dados',
      description: 'Conexão e verificação do banco de dados',
      component: DatabaseChecker,
      required: true,
      status: 'pending'
    },
    {
      id: 'services',
      title: 'Serviços',
      description: 'Verificação dos serviços externos',
      component: ServiceMonitor,
      required: false,
      status: 'pending'
    },
    {
      id: 'user-setup',
      title: 'Usuário Inicial',
      description: 'Configuração do primeiro usuário administrador',
      component: InitialUserSetup,
      required: true,
      status: 'pending'
    }
  ])

  const totalSteps = initializationSteps.filter(step => step.required || !skipWelcome).length
  const completedSteps = initializationSteps.filter(step => step.status === 'completed').length
  const progress = Math.round((completedSteps / totalSteps) * 100)

  useEffect(() => {
    if (autoStart && !hasStarted) {
      handleStart()
    }
  }, [autoStart, hasStarted])

  const handleStart = () => {
    logger.log('Starting system initialization')
    setHasStarted(true)
    setIsInitializing(true)

    // Skip welcome step if requested
    if (skipWelcome) {
      setCurrentStep(1)
      updateStepStatus('welcome', 'skipped')
    }

    toast({
      title: 'Inicializando Sistema',
      description: 'Verificando configurações e conectando serviços...',
    })
  }

  const updateStepStatus = (stepId: string, status: InitializationStep['status'], error?: string) => {
    setInitializationSteps(prev =>
      prev.map(step =>
        step.id === stepId
          ? { ...step, status, error }
          : step
      )
    )
  }

  const handleStepComplete = () => {
    const currentStepData = initializationSteps[currentStep]
    if (!currentStepData) return

    updateStepStatus(currentStepData.id, 'completed')

    logger.log(`Step '${currentStepData.id}' completed`)

    // Move to next step
    const nextStepIndex = currentStep + 1
    if (nextStepIndex < initializationSteps.length) {
      setCurrentStep(nextStepIndex)
      const nextStep = initializationSteps[nextStepIndex]
      if (nextStep) {
        updateStepStatus(nextStep.id, 'running')
      }
    } else {
      // All steps completed
      handleInitializationComplete()
    }
  }

  const handleStepError = (error: string) => {
    const currentStepData = initializationSteps[currentStep]
    if (!currentStepData) return

    updateStepStatus(currentStepData.id, 'error', error)

    logger.error(`Step '${currentStepData.id}' failed:`, error)

    toast({
      title: 'Erro na Inicialização',
      description: `Falha na etapa: ${currentStepData.title}`,
      variant: 'destructive'
    })
  }

  const handleSkipStep = () => {
    const currentStepData = initializationSteps[currentStep]
    if (!currentStepData) return

    if (!currentStepData.required) {
      updateStepStatus(currentStepData.id, 'skipped')
      handleStepComplete()
    }
  }

  const handleRetryStep = () => {
    const currentStepData = initializationSteps[currentStep]
    if (!currentStepData) return

    updateStepStatus(currentStepData.id, 'running')
    logger.log(`Retrying step '${currentStepData.id}'`)
  }

  const handleInitializationComplete = () => {
    setIsInitializing(false)
    logger.log('System initialization completed successfully')

    toast({
      title: 'Inicialização Concluída',
      description: 'Sistema configurado com sucesso!',
      variant: 'default'
    })

    onComplete()
  }

  const getStatusIcon = (status: InitializationStep['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="w-5 h-5 text-green-500" />
      case 'error':
        return <XCircle className="w-5 h-5 text-red-500" />
      case 'running':
        return <RefreshCcw className="w-5 h-5 text-blue-500 animate-spin" />
      case 'skipped':
        return <AlertTriangle className="w-5 h-5 text-yellow-500" />
      default:
        return <div className="w-5 h-5 border-2 border-gray-300 rounded-full" />
    }
  }

  const getStatusBadge = (status: InitializationStep['status']) => {
    switch (status) {
      case 'completed':
        return <Badge variant="default" className="bg-green-100 text-green-800">Concluído</Badge>
      case 'error':
        return <Badge variant="destructive">Erro</Badge>
      case 'running':
        return <Badge variant="default" className="bg-blue-100 text-blue-800">Em Execução</Badge>
      case 'skipped':
        return <Badge variant="secondary">Ignorado</Badge>
      default:
        return <Badge variant="outline">Pendente</Badge>
    }
  }

  if (!hasStarted) {
    return (
      <ErrorBoundary>
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
          <Card className="w-full max-w-2xl mx-4">
            <CardHeader className="text-center">
              <CardTitle className="text-3xl font-bold text-gray-900">
                Sistema Clínica Oncológica
              </CardTitle>
              <CardDescription className="text-lg text-gray-600 mt-2">
                Bem-vindo! Vamos configurar seu sistema de gestão médica.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="text-center">
                <Play className="w-16 h-16 mx-auto text-blue-500 mb-4" />
                <p className="text-gray-600 mb-6">
                  O assistente de configuração irá verificar as conexões necessárias
                  e configurar o sistema automaticamente.
                </p>
                <Button
                  onClick={handleStart}
                  size="lg"
                  className="w-full sm:w-auto px-8"
                >
                  Iniciar Configuração
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </ErrorBoundary>
    )
  }

  const currentStepData = initializationSteps[currentStep]
  const CurrentStepComponent = currentStepData?.component

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 py-8">
        <div className="container mx-auto px-4">
          {/* Progress Header */}
          <Card className="mb-8">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Configuração do Sistema</CardTitle>
                  <CardDescription>
                    Etapa {currentStep + 1} de {totalSteps}
                  </CardDescription>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-blue-600">{progress}%</div>
                  <div className="text-sm text-gray-600">Concluído</div>
                </div>
              </div>
              <Progress value={progress} className="mt-4" />
            </CardHeader>
          </Card>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Steps Sidebar */}
            <div className="lg:col-span-1">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Etapas</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {initializationSteps.map((step, index) => (
                    <div
                      key={step.id}
                      className={`flex items-start space-x-3 p-3 rounded-lg transition-colors ${index === currentStep
                        ? 'bg-blue-50 border border-blue-200'
                        : 'hover:bg-gray-50'
                        }`}
                    >
                      <div className="flex-shrink-0 mt-0.5">
                        {getStatusIcon(step.status)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <h4 className="text-sm font-medium text-gray-900 truncate">
                            {step.title}
                          </h4>
                          {getStatusBadge(step.status)}
                        </div>
                        <p className="text-xs text-gray-600 mt-1">
                          {step.description}
                        </p>
                        {step.error && (
                          <p className="text-xs text-red-600 mt-1">
                            {step.error}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </div>

            {/* Main Content */}
            <div className="lg:col-span-2">
              <Card className="min-h-[500px]">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="flex items-center space-x-2">
                        {getStatusIcon(currentStepData?.status || 'pending')}
                        <span>{currentStepData?.title}</span>
                      </CardTitle>
                      <CardDescription>{currentStepData?.description}</CardDescription>
                    </div>
                    {currentStepData?.status === 'error' && (
                      <Button onClick={handleRetryStep} variant="outline" size="sm">
                        <RefreshCcw className="w-4 h-4 mr-2" />
                        Tentar Novamente
                      </Button>
                    )}
                  </div>
                </CardHeader>
                <CardContent>
                  {currentStepData?.status === 'error' && currentStepData.error && (
                    <Alert className="mb-6" variant="destructive">
                      <XCircle className="h-4 w-4" />
                      <AlertDescription>{currentStepData.error}</AlertDescription>
                    </Alert>
                  )}

                  {CurrentStepComponent && (
                    <CurrentStepComponent
                      onComplete={handleStepComplete}
                      onError={handleStepError}
                    />
                  )}

                  {!currentStepData?.required && currentStepData?.status !== 'completed' && (
                    <div className="mt-6 pt-6 border-t">
                      <Button
                        onClick={handleSkipStep}
                        variant="outline"
                        className="w-full sm:w-auto"
                      >
                        Pular Esta Etapa
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </div>
    </ErrorBoundary>
  )
}