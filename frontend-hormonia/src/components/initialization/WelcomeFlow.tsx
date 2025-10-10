import React, { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { Button } from '../ui/button'
import { Badge } from '../ui/badge'
import {
  Heart,
  Users,
  Calendar,
  FileText,
  Activity,
  Shield,
  Zap,
  ArrowRight,
  CheckCircle,
  Star
} from 'lucide-react'
import { Alert, AlertDescription } from '../ui/alert'

interface WelcomeFlowProps {
  onComplete: () => void
  onError: (error: string) => void
}

export function WelcomeFlow({ onComplete }: WelcomeFlowProps) {
  const [currentStep, setCurrentStep] = useState(0)

  const welcomeSteps = [
    {
      id: 'introduction',
      title: 'Bem-vindo ao Sistema Clínica Oncológica',
      subtitle: 'Transformando o cuidado oncológico com tecnologia avançada',
      content: (
        <div className="space-y-6 text-center">
          <div className="w-24 h-24 mx-auto bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center">
            <Heart className="w-12 h-12 text-white" />
          </div>
          <div>
            <h3 className="text-2xl font-bold text-gray-900 mb-2">
              Sistema Completo de Gestão Oncológica
            </h3>
            <p className="text-gray-600 max-w-2xl mx-auto">
              Uma plataforma integrada desenvolvida especificamente para clínicas oncológicas,
              oferecendo gestão completa de pacientes, tratamentos e acompanhamento médico.
            </p>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-8">
            <div className="text-center">
              <Users className="w-8 h-8 text-blue-500 mx-auto mb-2" />
              <div className="text-sm font-medium">Gestão de Pacientes</div>
            </div>
            <div className="text-center">
              <Calendar className="w-8 h-8 text-green-500 mx-auto mb-2" />
              <div className="text-sm font-medium">Agendamento</div>
            </div>
            <div className="text-center">
              <FileText className="w-8 h-8 text-purple-500 mx-auto mb-2" />
              <div className="text-sm font-medium">Prontuários</div>
            </div>
            <div className="text-center">
              <Activity className="w-8 h-8 text-orange-500 mx-auto mb-2" />
              <div className="text-sm font-medium">Monitoramento</div>
            </div>
          </div>
        </div>
      )
    },
    {
      id: 'features',
      title: 'Principais Recursos',
      subtitle: 'Conheça as funcionalidades que irão revolucionar sua prática médica',
      content: (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card className="border-2 border-blue-100">
              <CardContent className="pt-6">
                <div className="flex items-center space-x-3 mb-3">
                  <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                    <Users className="w-5 h-5 text-blue-600" />
                  </div>
                  <h4 className="font-semibold">Gestão Completa de Pacientes</h4>
                </div>
                <p className="text-sm text-gray-600 mb-3">
                  Cadastro completo, histórico médico, documentos e acompanhamento personalizado.
                </p>
                <div className="flex flex-wrap gap-1">
                  <Badge variant="secondary" className="text-xs">Prontuários Digitais</Badge>
                  <Badge variant="secondary" className="text-xs">Histórico Médico</Badge>
                  <Badge variant="secondary" className="text-xs">Documentos</Badge>
                </div>
              </CardContent>
            </Card>

            <Card className="border-2 border-green-100">
              <CardContent className="pt-6">
                <div className="flex items-center space-x-3 mb-3">
                  <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                    <Calendar className="w-5 h-5 text-green-600" />
                  </div>
                  <h4 className="font-semibold">Agendamento Inteligente</h4>
                </div>
                <p className="text-sm text-gray-600 mb-3">
                  Sistema avançado de agendamento com lembretes automáticos e otimização de agenda.
                </p>
                <div className="flex flex-wrap gap-1">
                  <Badge variant="secondary" className="text-xs">Lembretes</Badge>
                  <Badge variant="secondary" className="text-xs">WhatsApp</Badge>
                  <Badge variant="secondary" className="text-xs">Otimização</Badge>
                </div>
              </CardContent>
            </Card>

            <Card className="border-2 border-purple-100">
              <CardContent className="pt-6">
                <div className="flex items-center space-x-3 mb-3">
                  <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                    <Activity className="w-5 h-5 text-purple-600" />
                  </div>
                  <h4 className="font-semibold">Monitoramento em Tempo Real</h4>
                </div>
                <p className="text-sm text-gray-600 mb-3">
                  Acompanhamento contínuo de tratamentos, efeitos colaterais e evolução clínica.
                </p>
                <div className="flex flex-wrap gap-1">
                  <Badge variant="secondary" className="text-xs">Tempo Real</Badge>
                  <Badge variant="secondary" className="text-xs">Alertas</Badge>
                  <Badge variant="secondary" className="text-xs">Relatórios</Badge>
                </div>
              </CardContent>
            </Card>

            <Card className="border-2 border-orange-100">
              <CardContent className="pt-6">
                <div className="flex items-center space-x-3 mb-3">
                  <div className="w-10 h-10 bg-orange-100 rounded-lg flex items-center justify-center">
                    <Shield className="w-5 h-5 text-orange-600" />
                  </div>
                  <h4 className="font-semibold">Segurança e Compliance</h4>
                </div>
                <p className="text-sm text-gray-600 mb-3">
                  Proteção total de dados seguindo LGPD e padrões internacionais de segurança.
                </p>
                <div className="flex flex-wrap gap-1">
                  <Badge variant="secondary" className="text-xs">LGPD</Badge>
                  <Badge variant="secondary" className="text-xs">Criptografia</Badge>
                  <Badge variant="secondary" className="text-xs">Auditoria</Badge>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )
    },
    {
      id: 'benefits',
      title: 'Benefícios Imediatos',
      subtitle: 'Veja como o sistema irá transformar sua prática médica',
      content: (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="text-center">
              <div className="w-16 h-16 bg-gradient-to-br from-green-400 to-green-600 rounded-full flex items-center justify-center mx-auto mb-4">
                <Zap className="w-8 h-8 text-white" />
              </div>
              <h4 className="font-semibold text-lg mb-2">+70% Eficiência</h4>
              <p className="text-gray-600 text-sm">
                Automatização de processos administrativos e redução significativa de tempo gasto em tarefas manuais.
              </p>
            </div>
            <div className="text-center">
              <div className="w-16 h-16 bg-gradient-to-br from-blue-400 to-blue-600 rounded-full flex items-center justify-center mx-auto mb-4">
                <Heart className="w-8 h-8 text-white" />
              </div>
              <h4 className="font-semibold text-lg mb-2">Melhor Cuidado</h4>
              <p className="text-gray-600 text-sm">
                Acompanhamento mais próximo dos pacientes com alertas inteligentes e protocolos personalizados.
              </p>
            </div>
            <div className="text-center">
              <div className="w-16 h-16 bg-gradient-to-br from-purple-400 to-purple-600 rounded-full flex items-center justify-center mx-auto mb-4">
                <Star className="w-8 h-8 text-white" />
              </div>
              <h4 className="font-semibold text-lg mb-2">Experiência Premium</h4>
              <p className="text-gray-600 text-sm">
                Interface moderna e intuitiva que facilita o trabalho da equipe médica e administrativa.
              </p>
            </div>
          </div>

          <Alert className="bg-blue-50 border-blue-200">
            <CheckCircle className="h-4 w-4 text-blue-600" />
            <AlertDescription className="text-blue-800">
              <strong>Implementação Gradual:</strong> O sistema será configurado passo a passo,
              garantindo uma transição suave e treinamento adequado para toda a equipe.
            </AlertDescription>
          </Alert>
        </div>
      )
    },
    {
      id: 'ready',
      title: 'Pronto para Começar?',
      subtitle: 'Vamos configurar seu sistema e começar a transformar sua clínica',
      content: (
        <div className="space-y-6 text-center">
          <div className="w-24 h-24 mx-auto bg-gradient-to-br from-green-500 to-blue-600 rounded-full flex items-center justify-center">
            <CheckCircle className="w-12 h-12 text-white" />
          </div>
          <div>
            <h3 className="text-2xl font-bold text-gray-900 mb-4">
              Tudo Pronto para Configuração!
            </h3>
            <p className="text-gray-600 max-w-2xl mx-auto mb-6">
              Agora vamos verificar as configurações do sistema, testar as conexões
              necessárias e criar seu primeiro usuário administrador.
            </p>
            <div className="bg-gray-50 rounded-lg p-6 max-w-md mx-auto">
              <h4 className="font-semibold mb-3">Próximos Passos:</h4>
              <div className="space-y-2 text-sm text-left">
                <div className="flex items-center space-x-2">
                  <CheckCircle className="w-4 h-4 text-green-500" />
                  <span>Verificar configurações do ambiente</span>
                </div>
                <div className="flex items-center space-x-2">
                  <CheckCircle className="w-4 h-4 text-green-500" />
                  <span>Testar conexão com banco de dados</span>
                </div>
                <div className="flex items-center space-x-2">
                  <CheckCircle className="w-4 h-4 text-green-500" />
                  <span>Verificar serviços externos</span>
                </div>
                <div className="flex items-center space-x-2">
                  <CheckCircle className="w-4 h-4 text-green-500" />
                  <span>Criar usuário administrador</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )
    }
  ]

  const currentStepData = welcomeSteps[currentStep]
  if (!currentStepData) {
    onComplete()
    return null
  }

  const isLastStep = currentStep === welcomeSteps.length - 1

  const handleNext = () => {
    if (isLastStep) {
      onComplete()
    } else {
      setCurrentStep(prev => prev + 1)
    }
  }

  const handlePrevious = () => {
    if (currentStep > 0) {
      setCurrentStep(prev => prev - 1)
    }
  }

  const handleSkip = () => {
    onComplete()
  }

  return (
    <div className="space-y-6">
      {/* Progress Indicators */}
      <div className="flex items-center justify-center space-x-2 mb-8">
        {welcomeSteps.map((_, index) => (
          <div
            key={index}
            className={`w-3 h-3 rounded-full transition-colors ${
              index === currentStep
                ? 'bg-blue-600'
                : index < currentStep
                ? 'bg-green-500'
                : 'bg-gray-300'
            }`}
          />
        ))}
      </div>

      {/* Main Content */}
      <Card className="min-h-[500px]">
        <CardHeader className="text-center pb-6">
          <CardTitle className="text-2xl md:text-3xl font-bold text-gray-900">
            {currentStepData.title}
          </CardTitle>
          <CardDescription className="text-lg text-gray-600 mt-2">
            {currentStepData.subtitle}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {currentStepData.content}
        </CardContent>
      </Card>

      {/* Navigation */}
      <div className="flex items-center justify-between pt-6">
        <div className="flex space-x-2">
          <Button
            variant="outline"
            onClick={handlePrevious}
            disabled={currentStep === 0}
            className="px-6"
          >
            Anterior
          </Button>
          {currentStep > 0 && (
            <Button
              variant="ghost"
              onClick={handleSkip}
              className="text-gray-600 hover:text-gray-800"
            >
              Pular Apresentação
            </Button>
          )}
        </div>

        <div className="flex items-center space-x-2">
          <span className="text-sm text-gray-500">
            {currentStep + 1} de {welcomeSteps.length}
          </span>
          <Button
            onClick={handleNext}
            className="px-6"
            size="default"
          >
            {isLastStep ? (
              <>
                Iniciar Configuração
                <ArrowRight className="w-4 h-4 ml-2" />
              </>
            ) : (
              <>
                Próximo
                <ArrowRight className="w-4 h-4 ml-2" />
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}