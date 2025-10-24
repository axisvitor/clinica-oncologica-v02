import React, { useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Phone, Mail, Calendar, Activity, Send, CheckCircle, TrendingUp, Brain, AlertTriangle, Lightbulb } from 'lucide-react'
import { Link } from 'react-router-dom'
import { apiClient } from '../lib/api-client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Progress } from '@/components/ui/progress'
import { LoadingSpinner } from '../components/ui/loading-spinner'
import { PatientTimeline } from '../components/patients/PatientTimeline'
import { FlowStatus } from '../components/patients/FlowStatus'
import { QuickActions } from '../components/patients/QuickActions'
import { QuizLinkStatus } from '@/components/quiz/QuizLinkStatus'
import { SendQuizLinkModal } from '@/components/quiz/SendQuizLinkModal'
import { AIChatInterface } from '@/components/ai/AIChatInterface'
import { AIAnalyticsDashboard } from '@/components/ai/AIAnalyticsDashboard'
import { QuizResponseViewer } from '../components/patients/QuizResponseViewer'
import { QuizResponseTimeline } from '../components/patients/QuizResponseTimeline'
import { useMonthlyQuizAdmin } from '@/hooks/useMonthlyQuizAdmin'
import { useAIInsights, useAIRecommendations } from '@/hooks/useAI'
import { useAuth } from '@/contexts/AuthContext'
import { FEATURES } from '@/config'
import type { QuizHistoryEntry } from '@/lib/api-client/monthly-quiz'

export function PatientDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const defaultTab = searchParams.get('tab') || 'overview'
  const [showSendQuizModal, setShowSendQuizModal] = useState(false)
  const { user, hasRole } = useAuth()
  const { useQuizLinkStatus, useQuizLinkHistory, resendQuizLink, cancelQuizLink } = useMonthlyQuizAdmin()

  // AI Hooks - Hooks will return mock data if AI is not configured
  const { data: aiInsights, isLoading: insightsLoading } = useAIInsights(id || '')
  const { data: aiRecommendations, isLoading: recommendationsLoading } = useAIRecommendations(id || '')

  const { data: patient, isLoading: patientLoading } = useQuery({
    queryKey: ['patient', id],
    queryFn: () => apiClient.patients.get(id!),
    enabled: !!id
  })

  const { data: timeline, isLoading: timelineLoading } = useQuery({
    queryKey: ['patient-timeline', id],
    queryFn: () => apiClient.patients.timeline(id!),
    enabled: !!id
  })

  const { data: flowState } = useQuery({
    queryKey: ['flow-state', id],
    queryFn: () => apiClient.flows.getState(id!),
    enabled: !!id
  })

  const { data: quizStatus, isLoading: quizStatusLoading } = useQuizLinkStatus(id!)
  const { data: quizHistory, isLoading: quizHistoryLoading } = useQuizLinkHistory(id!)

  if (patientLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (!patient) {
    return (
      <div className="text-center py-8">
        <h2 className="text-xl font-semibold text-gray-900 mb-2">
          Paciente não encontrado
        </h2>
        <p className="text-gray-600 mb-4">
          O paciente solicitado não foi encontrado ou você não tem permissão para visualizá-lo.
        </p>
        <Button asChild>
          <Link to="/patients">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Voltar para pacientes
          </Link>
        </Button>
      </div>
    )
  }

  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2)
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return <Badge className="bg-green-100 text-green-800">Ativo</Badge>
      case 'paused':
        return <Badge className="bg-yellow-100 text-yellow-800">Pausado</Badge>
      case 'completed':
        return <Badge className="bg-blue-100 text-blue-800">Concluído</Badge>
      case 'inactive':
        return <Badge variant="secondary">Inativo</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleDateString('pt-BR')
    } catch {
      return 'Data inválida'
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Button variant="outline" size="sm" asChild>
            <Link to="/patients">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Voltar
            </Link>
          </Button>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{patient.name}</h1>
            <p className="text-gray-600">Detalhes do paciente</p>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          {getStatusBadge(patient.status || 'inactive')}
        </div>
      </div>

      {/* Patient Overview */}
      <Card>
        <CardHeader>
          <CardTitle>Informações do Paciente</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-start space-x-6">
            <Avatar className="h-20 w-20">
              <AvatarImage src="" alt={patient.name} />
              <AvatarFallback className="bg-blue-600 text-white text-lg">
                {getInitials(patient.name)}
              </AvatarFallback>
            </Avatar>

            <div className="flex-1 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <Phone className="h-4 w-4 text-gray-400" />
                  <span className="text-sm text-gray-600">Telefone</span>
                </div>
                <p className="font-medium">{patient.phone}</p>
              </div>

              {patient.email && (
                <div className="space-y-3">
                  <div className="flex items-center space-x-2">
                    <Mail className="h-4 w-4 text-gray-400" />
                    <span className="text-sm text-gray-600">Email</span>
                  </div>
                  <p className="font-medium">{patient.email}</p>
                </div>
              )}

              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <Activity className="h-4 w-4 text-gray-400" />
                  <span className="text-sm text-gray-600">Tratamento</span>
                </div>
                <p className="font-medium">{patient.treatment_type}</p>
              </div>

              {patient.birth_date && (
                <div className="space-y-3">
                  <div className="flex items-center space-x-2">
                    <Calendar className="h-4 w-4 text-gray-400" />
                    <span className="text-sm text-gray-600">Data de nascimento</span>
                  </div>
                  <p className="font-medium">{formatDate(patient.birth_date)}</p>
                </div>
              )}

              {patient.treatment_start_date && (
                <div className="space-y-3">
                  <div className="flex items-center space-x-2">
                    <Calendar className="h-4 w-4 text-gray-400" />
                    <span className="text-sm text-gray-600">Início do tratamento</span>
                  </div>
                  <p className="font-medium">{formatDate(patient.treatment_start_date)}</p>
                </div>
              )}

              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <Activity className="h-4 w-4 text-gray-400" />
                  <span className="text-sm text-gray-600">Dia atual</span>
                </div>
                <p className="font-medium">{patient.current_day}</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Quiz Mensal Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Quiz Mensal</span>
            {quizStatus && (
              <QuizLinkStatus
                patientId={id!}
                {...(quizStatus.last_sent && { lastSent: new Date(quizStatus.last_sent) })}
                {...(quizStatus.access_date && { lastResponse: new Date(quizStatus.access_date) })}
                linkStatus={quizStatus.status}
                {...(quizStatus.expires_at && { expiresAt: new Date(quizStatus.expires_at) })}
              />
            )}
          </CardTitle>
          <CardDescription>
            Gerencie o questionário mensal de bem-estar
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Action Buttons */}
            <div className="flex items-center space-x-2">
              <Button
                onClick={() => setShowSendQuizModal(true)}
                disabled={quizStatus?.status === 'active'}
              >
                <Send className="mr-2 h-4 w-4" />
                {quizStatus?.status === 'active' ? 'Link Ativo' : 'Enviar Link'}
              </Button>
              {quizStatus?.status === 'active' && quizStatus?.session_id && (
                <>
                  <Button
                    variant="outline"
                    onClick={() => resendQuizLink(quizStatus.session_id)}
                  >
                    Reenviar
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => cancelQuizLink(quizStatus.session_id)}
                  >
                    Cancelar
                  </Button>
                </>
              )}
            </div>

            {/* Metrics */}
            {quizHistory && quizHistory.length > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
                <div className="p-4 border rounded-lg">
                  <div className="flex items-center space-x-2">
                    <Send className="h-5 w-5 text-blue-600" />
                    <span className="text-sm text-gray-600">Total Enviados</span>
                  </div>
                  <p className="text-2xl font-bold mt-2">{quizHistory.length}</p>
                </div>
                <div className="p-4 border rounded-lg">
                  <div className="flex items-center space-x-2">
                    <CheckCircle className="h-5 w-5 text-green-600" />
                    <span className="text-sm text-gray-600">Completados</span>
                  </div>
                  <p className="text-2xl font-bold mt-2">
                    {quizHistory.filter((h: any) => h.status === 'completed').length}
                  </p>
                </div>
                <div className="p-4 border rounded-lg">
                  <div className="flex items-center space-x-2">
                    <TrendingUp className="h-5 w-5 text-purple-600" />
                    <span className="text-sm text-gray-600">Taxa de Conclusão</span>
                  </div>
                  <p className="text-2xl font-bold mt-2">
                    {quizHistory.length > 0
                      ? Math.round((quizHistory.filter((h: unknown) => h.status === 'completed').length / quizHistory.length) * 100)
                      : 0}%
                  </p>
                </div>
              </div>
            )}

            {/* History */}
            {quizHistoryLoading ? (
              <div className="flex items-center justify-center py-4">
                <LoadingSpinner />
              </div>
            ) : quizHistory && quizHistory.length > 0 && (
              <div className="mt-4">
                <h4 className="text-sm font-semibold text-gray-900 mb-2">Histórico</h4>
                <div className="space-y-2">
                  {quizHistory.slice(0, 5).map((entry: QuizHistoryEntry) => (
                    <div key={entry.id} className="flex items-center justify-between p-2 border rounded">
                      <div>
                        <p className="text-sm font-medium">{entry.quiz_template_name}</p>
                        <p className="text-xs text-gray-500">
                          {entry.sent_at && new Date(entry.sent_at).toLocaleDateString('pt-BR')}
                        </p>
                      </div>
                      <QuizLinkStatus
                        patientId={id!}
                        {...(entry.sent_at && { lastSent: new Date(entry.sent_at) })}
                        {...(entry.accessed_at && { lastResponse: new Date(entry.accessed_at) })}
                        linkStatus={entry.status}
                        {...(entry.expires_at && { expiresAt: new Date(entry.expires_at) })}
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Main Content Tabs */}
      <Tabs defaultValue={defaultTab} className="space-y-6">
        <TabsList>
          <TabsTrigger value="overview">Visão Geral</TabsTrigger>
          <TabsTrigger value="timeline">Linha do Tempo</TabsTrigger>
          <TabsTrigger value="quiz-responses">Respostas de Quiz</TabsTrigger>
          {FEATURES.AI_CHAT && (hasRole('doctor') || hasRole('admin')) && (
            <>
              <TabsTrigger value="ai-insights">Insights de IA</TabsTrigger>
              <TabsTrigger value="ai-chat">Chat IA</TabsTrigger>
            </>
          )}
          <TabsTrigger value="messages">Mensagens</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Column - Timeline */}
            <div className="lg:col-span-2 space-y-6">
              <PatientTimeline
                timeline={timeline ? { events: timeline.events } : undefined}
                isLoading={timelineLoading}
              />
            </div>

            {/* Right Column - Flow Status and Actions */}
            <div className="space-y-6">
              <FlowStatus
                patientId={id!}
              />
              <QuickActions patientId={id!} />
            </div>
          </div>
        </TabsContent>

        <TabsContent value="timeline" className="space-y-6">
          <PatientTimeline
            timeline={timeline ? { events: timeline.events } : undefined}
            isLoading={timelineLoading}
          />
        </TabsContent>

        <TabsContent value="quiz-responses" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Column - Quiz Responses */}
            <div className="lg:col-span-2">
              <QuizResponseViewer patientId={id!} patientName={patient.name} />
            </div>

            {/* Right Column - Timeline and Actions */}
            <div className="space-y-6">
              <QuizResponseTimeline patientId={id!} />

              {/* Quick Actions for Quiz Responses */}
              <Card>
                <CardHeader>
                  <CardTitle>Ações Rápidas</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <Button className="w-full" variant="outline">
                    <Calendar className="mr-2 h-4 w-4" />
                    Agendar Consulta
                  </Button>
                  <Button className="w-full" variant="outline">
                    <Send className="mr-2 h-4 w-4" />
                    Enviar Mensagem
                  </Button>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        {FEATURES.AI_CHAT && (hasRole('doctor') || hasRole('admin')) && (
          <>
            <TabsContent value="ai-insights" className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Brain className="h-5 w-5" />
                    Análise de IA - {patient.name}
                  </CardTitle>
                  <CardDescription>
                    Insights, recomendações e análise de sentimento baseados em dados do paciente
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <AIAnalyticsDashboard
                    patientId={id!}
                    timeframe="week"
                    className="mt-4"
                  />
                </CardContent>
              </Card>

              {/* Legacy AI Insights - Keep for backward compatibility */}
              {(aiInsights || aiRecommendations) && (
                <Card>
                  <CardHeader>
                    <CardTitle>Resumo Rápido</CardTitle>
                    <CardDescription>Visão geral dos principais indicadores</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {/* Risk Assessment */}
                    {aiInsights?.risk_level && (
                      <div className={`border-l-4 p-4 rounded-r-lg ${aiInsights.risk_level === 'critical' ? 'border-red-500 bg-red-50' :
                        aiInsights.risk_level === 'high' ? 'border-orange-500 bg-orange-50' :
                          aiInsights.risk_level === 'medium' ? 'border-yellow-500 bg-yellow-50' :
                            'border-green-500 bg-green-50'
                        }`}>
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <AlertTriangle className="h-5 w-5" />
                            <span className="font-medium">Nível de Risco:</span>
                          </div>
                          <Badge className={`${aiInsights.risk_level === 'critical' ? 'bg-red-500' :
                            aiInsights.risk_level === 'high' ? 'bg-orange-500' :
                              aiInsights.risk_level === 'medium' ? 'bg-yellow-500' :
                                'bg-green-500'
                            } text-white`}>
                            {aiInsights.risk_level === 'critical' ? 'Crítico' :
                              aiInsights.risk_level === 'high' ? 'Alto' :
                                aiInsights.risk_level === 'medium' ? 'Médio' : 'Baixo'}
                          </Badge>
                        </div>
                        {aiInsights.risk_factors && aiInsights.risk_factors.length > 0 && (
                          <div className="mt-3">
                            <p className="text-sm font-medium mb-2">Fatores:</p>
                            <div className="flex flex-wrap gap-2">
                              {aiInsights.risk_factors.map((factor: string, idx: number) => (
                                <Badge key={idx} variant="outline">{factor}</Badge>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Sentiment Score */}
                    {aiInsights?.sentiment_score !== undefined && (
                      <div className="p-4 border rounded-lg">
                        <div className="flex items-center gap-2 mb-3">
                          <TrendingUp className="h-5 w-5" />
                          <span className="font-medium">Score de Sentimento</span>
                        </div>
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-sm text-muted-foreground">
                              {aiInsights.sentiment_score >= 0.7 ? 'Positivo' :
                                aiInsights.sentiment_score >= 0.4 ? 'Neutro' : 'Negativo'}
                            </span>
                            <span className="text-sm font-bold">{(aiInsights.sentiment_score * 100).toFixed(0)}%</span>
                          </div>
                          <Progress value={aiInsights.sentiment_score * 100} />
                        </div>
                      </div>
                    )}

                    {/* Top Recommendations */}
                    {aiRecommendations && aiRecommendations.length > 0 && (
                      <div className="p-4 border rounded-lg">
                        <div className="flex items-center gap-2 mb-3">
                          <Lightbulb className="h-5 w-5" />
                          <span className="font-medium">Principais Recomendações</span>
                        </div>
                        <div className="space-y-2">
                          {aiRecommendations.slice(0, 3).map((rec: { id: string; title: string; priority: string }) => (
                            <div key={rec.id} className="flex items-center justify-between text-sm">
                              <span className="text-muted-foreground">{rec.title}</span>
                              <Badge variant={rec.priority === 'high' ? 'destructive' : 'secondary'} className="text-xs">
                                {rec.priority}
                              </Badge>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            <TabsContent value="ai-chat" className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Brain className="h-5 w-5" />
                    Chat com IA - Contexto do Paciente
                  </CardTitle>
                  <CardDescription>
                    Tire dúvidas e obtenha insights sobre {patient.name}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <AIChatInterface patientId={id!} />
                </CardContent>
              </Card>
            </TabsContent>
          </>
        )}

        <TabsContent value="messages" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Mensagens</CardTitle>
              <CardDescription>Histórico de comunicação com o paciente</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground">Painel de mensagens será implementado aqui...</p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Send Quiz Modal */}
      <SendQuizLinkModal
        open={showSendQuizModal}
        onOpenChange={setShowSendQuizModal}
        patientId={id!}
        patientName={patient?.name || ''}
      />
    </div>
  )
}
