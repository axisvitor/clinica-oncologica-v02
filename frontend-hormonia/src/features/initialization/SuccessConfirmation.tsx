import React, { useState, useEffect } from 'react'
import {
  CheckCircle,
  Download,
  ExternalLink,
  Copy,
  PartyPopper,
  Users,
  Calendar,
  FileText,
  Activity,
  Shield,
  Settings,
  ArrowRight,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { Badge } from '@/components/ui/badge'
import { createLogger } from '@/lib/logger'
import { useToast } from '@/components/ui/use-toast'

const logger = createLogger('SuccessConfirmation')

interface SuccessConfirmationProps {
  onComplete: () => void
  setupData?: {
    adminUser?: {
      email: string
      name: string
      role: string
    }
    environment?: {
      databaseStatus: string
      servicesCount: number
    }
  }
}

export function SuccessConfirmation({ onComplete, setupData }: SuccessConfirmationProps) {
  const [isGeneratingReport, setIsGeneratingReport] = useState(false)
  const [showCredentials, setShowCredentials] = useState(false)
  const { toast } = useToast()

  useEffect(() => {
    // Celebrate successful setup
    logger.log('System initialization completed successfully')

    // Show success toast
    toast({
      title: '🎉 Sistema Configurado com Sucesso!',
      description: 'Sua clínica oncológica está pronta para uso.',
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- toast is stable and should only run on mount
  }, [])

  const handleGenerateReport = async () => {
    setIsGeneratingReport(true)

    try {
      // Generate setup report
      const report = {
        timestamp: new Date().toISOString(),
        setupData,
        systemStatus: 'ready',
        nextSteps: [
          'Fazer login com credenciais de administrador',
          'Configurar perfis de usuários adicionais',
          'Importar dados de pacientes (se necessário)',
          'Configurar preferências da clínica',
          'Testar funcionalidades principais',
        ],
      }

      // In production, this would generate a PDF or send via email
      const reportText = JSON.stringify(report, null, 2)

      // For now, copy to clipboard
      await navigator.clipboard.writeText(reportText)

      toast({
        title: 'Relatório Gerado',
        description: 'Relatório de configuração copiado para a área de transferência.',
      })
    } catch (error) {
      logger.error('Failed to generate report:', error)
      toast({
        title: 'Erro ao Gerar Relatório',
        description: 'Não foi possível gerar o relatório de configuração.',
        variant: 'destructive',
      })
    } finally {
      setIsGeneratingReport(false)
    }
  }

  const handleCopyCredentials = async () => {
    if (!setupData?.adminUser) return

    const credentials = `
Sistema Clínica Oncológica - Credenciais de Administrador

Email: ${setupData.adminUser.email}
Nome: ${setupData.adminUser.name}
Função: ${setupData.adminUser.role}
Data de Criação: ${new Date().toLocaleString('pt-BR')}

IMPORTANTE:
- Guarde estas credenciais em local seguro
- Altere a senha no primeiro acesso
- Configure autenticação de dois fatores quando disponível
    `.trim()

    try {
      await navigator.clipboard.writeText(credentials)
      toast({
        title: 'Credenciais Copiadas',
        description: 'Credenciais copiadas para a área de transferência.',
      })
    } catch {
      toast({
        title: 'Erro ao Copiar',
        description: 'Não foi possível copiar as credenciais.',
        variant: 'destructive',
      })
    }
  }

  const systemFeatures = [
    {
      icon: <Users className="w-5 h-5 text-blue-500" />,
      title: 'Gestão de Pacientes',
      description: 'Cadastro e acompanhamento completo',
    },
    {
      icon: <Calendar className="w-5 h-5 text-green-500" />,
      title: 'Agendamento',
      description: 'Sistema inteligente com notificações',
    },
    {
      icon: <FileText className="w-5 h-5 text-purple-500" />,
      title: 'Prontuários Digitais',
      description: 'Documentação médica eletrônica',
    },
    {
      icon: <Activity className="w-5 h-5 text-orange-500" />,
      title: 'Monitoramento',
      description: 'Acompanhamento em tempo real',
    },
    {
      icon: <Shield className="w-5 h-5 text-red-500" />,
      title: 'Segurança',
      description: 'Proteção de dados certificada',
    },
    {
      icon: <Settings className="w-5 h-5 text-gray-500" />,
      title: 'Administração',
      description: 'Controle total do sistema',
    },
  ]

  const nextSteps = [
    {
      title: 'Primeiro Acesso',
      description: 'Faça login com as credenciais de administrador criadas',
      action: 'Ir para Login',
      priority: 'high',
    },
    {
      title: 'Configurar Perfil',
      description: 'Complete seu perfil profissional e preferências',
      action: 'Configurar',
      priority: 'high',
    },
    {
      title: 'Adicionar Usuários',
      description: 'Convide sua equipe e configure permissões',
      action: 'Gerenciar Usuários',
      priority: 'medium',
    },
    {
      title: 'Importar Dados',
      description: 'Migre dados existentes de pacientes (opcional)',
      action: 'Importar',
      priority: 'low',
    },
    {
      title: 'Explorar Recursos',
      description: 'Conheça todas as funcionalidades disponíveis',
      action: 'Tour Guiado',
      priority: 'low',
    },
  ]

  return (
    <div className="space-y-6">
      {/* Main Success Message */}
      <Card className="border-green-200 bg-green-50">
        <CardContent className="pt-6">
          <div className="text-center space-y-4">
            <div className="w-20 h-20 mx-auto bg-gradient-to-br from-green-400 to-green-600 rounded-full flex items-center justify-center">
              <PartyPopper className="w-10 h-10 text-white" />
            </div>
            <div>
              <h2 className="text-3xl font-bold text-green-800 mb-2">
                🎉 Parabéns! Sistema Configurado
              </h2>
              <p className="text-green-700 text-lg">
                Sua clínica oncológica está pronta para revolucionar o atendimento aos pacientes
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Setup Summary */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <CheckCircle className="w-5 h-5 text-green-500" />
              <span>Resumo da Configuração</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {setupData?.adminUser && (
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <div className="font-medium">Administrador</div>
                  <div className="text-sm text-gray-600">
                    {setupData.adminUser.name} ({setupData.adminUser.email})
                  </div>
                </div>
                <Badge variant="default">Criado</Badge>
              </div>
            )}

            {setupData?.environment && (
              <>
                <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div>
                    <div className="font-medium">Banco de Dados</div>
                    <div className="text-sm text-gray-600">
                      Status: {setupData.environment.databaseStatus}
                    </div>
                  </div>
                  <Badge variant="default" className="bg-green-100 text-green-800">
                    Conectado
                  </Badge>
                </div>

                <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div>
                    <div className="font-medium">Serviços Externos</div>
                    <div className="text-sm text-gray-600">
                      {setupData.environment.servicesCount} serviços verificados
                    </div>
                  </div>
                  <Badge variant="default" className="bg-blue-100 text-blue-800">
                    Operacional
                  </Badge>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Shield className="w-5 h-5 text-blue-500" />
              <span>Credenciais de Acesso</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Alert className="bg-yellow-50 border-yellow-200">
              <Shield className="h-4 w-4 text-yellow-600" />
              <AlertDescription className="text-yellow-800">
                <strong>Importante:</strong> Guarde suas credenciais em local seguro. Estas
                informações são necessárias para o primeiro acesso.
              </AlertDescription>
            </Alert>

            <div className="space-y-2">
              <Button
                variant="outline"
                onClick={() => setShowCredentials(!showCredentials)}
                className="w-full"
              >
                {showCredentials ? 'Ocultar' : 'Mostrar'} Credenciais
              </Button>

              {showCredentials && setupData?.adminUser && (
                <div className="p-3 bg-gray-50 rounded-lg text-sm">
                  <div>
                    <strong>Email:</strong> {setupData.adminUser.email}
                  </div>
                  <div>
                    <strong>Nome:</strong> {setupData.adminUser.name}
                  </div>
                  <div>
                    <strong>Função:</strong> {setupData.adminUser.role}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleCopyCredentials}
                    className="mt-2 h-7"
                  >
                    <Copy className="w-3 h-3 mr-1" />
                    Copiar
                  </Button>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Available Features */}
      <Card>
        <CardHeader>
          <CardTitle>Recursos Disponíveis</CardTitle>
          <CardDescription>Explore as funcionalidades do seu novo sistema</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {systemFeatures.map((feature, index) => (
              <div
                key={index}
                className="flex items-start space-x-3 p-3 rounded-lg border hover:bg-gray-50 transition-colors"
              >
                <div className="flex-shrink-0 mt-1">{feature.icon}</div>
                <div className="flex-1 min-w-0">
                  <h4 className="font-medium text-sm">{feature.title}</h4>
                  <p className="text-xs text-gray-600 mt-1">{feature.description}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Next Steps */}
      <Card>
        <CardHeader>
          <CardTitle>Próximos Passos</CardTitle>
          <CardDescription>Recomendações para começar a usar o sistema</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {nextSteps.map((step, index) => (
              <div
                key={index}
                className={`flex items-center justify-between p-4 rounded-lg border-l-4 ${
                  step.priority === 'high'
                    ? 'border-l-red-400 bg-red-50'
                    : step.priority === 'medium'
                      ? 'border-l-yellow-400 bg-yellow-50'
                      : 'border-l-gray-400 bg-gray-50'
                }`}
              >
                <div className="flex-1">
                  <div className="flex items-center space-x-2 mb-1">
                    <h4 className="font-medium">{step.title}</h4>
                    <Badge
                      variant="outline"
                      className={`text-xs ${
                        step.priority === 'high'
                          ? 'border-red-300 text-red-700'
                          : step.priority === 'medium'
                            ? 'border-yellow-300 text-yellow-700'
                            : 'border-gray-300 text-gray-700'
                      }`}
                    >
                      {step.priority === 'high'
                        ? 'Prioritário'
                        : step.priority === 'medium'
                          ? 'Importante'
                          : 'Opcional'}
                    </Badge>
                  </div>
                  <p className="text-sm text-gray-600">{step.description}</p>
                </div>
                <Button variant="outline" size="sm">
                  {step.action}
                  <ArrowRight className="w-3 h-3 ml-1" />
                </Button>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Action Buttons */}
      <div className="flex flex-col sm:flex-row gap-4 pt-6">
        <Button
          onClick={handleGenerateReport}
          disabled={isGeneratingReport}
          variant="outline"
          className="flex-1"
        >
          {isGeneratingReport ? (
            <LoadingSpinner size="sm" />
          ) : (
            <>
              <Download className="w-4 h-4 mr-2" />
              Gerar Relatório
            </>
          )}
        </Button>

        <Button
          onClick={() => window.open('/docs', '_blank')}
          variant="outline"
          className="flex-1 sm:flex-none"
        >
          <ExternalLink className="w-4 h-4 mr-2" />
          Documentação
        </Button>

        <Button onClick={onComplete} className="flex-1" size="lg">
          <CheckCircle className="w-5 h-5 mr-2" />
          Começar a Usar Sistema
        </Button>
      </div>

      {/* Support Information */}
      <Alert className="bg-blue-50 border-blue-200">
        <Activity className="h-4 w-4 text-blue-600" />
        <AlertDescription className="text-blue-800">
          <strong>Precisa de Ajuda?</strong> Nossa equipe de suporte está disponível para auxiliar
          no treinamento e configurações adicionais. Entre em contato através do chat do sistema ou
          pelo email suporte@clinica-oncologica.com
        </AlertDescription>
      </Alert>
    </div>
  )
}
