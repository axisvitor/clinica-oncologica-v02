import React, { useState, useMemo } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Phone, Mail, Calendar, Activity, Send, CheckCircle, TrendingUp, Brain, AlertTriangle, Lightbulb } from 'lucide-react'
import { Link } from 'react-router-dom'
import { apiClient } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Progress } from '@/components/ui/progress'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { PatientTimeline } from '@/features/patients/PatientTimeline'
import { FlowStatus } from '@/features/patients/FlowStatus'
import { QuickActions } from '@/features/patients/QuickActions'
import { QuizLinkStatus } from '@/features/quiz/QuizLinkStatus'
import { SendQuizLinkModal } from '@/features/quiz/SendQuizLinkModal'
import { AIChatInterface } from '@/features/ai/AIChatInterface'
import { AIAnalyticsDashboard } from '@/features/ai/AIAnalyticsDashboard'
import { PatientAISummary } from '@/features/ai/PatientAISummary'
import { QuizResponseViewer } from '@/features/patients/QuizResponseViewer'
import { QuizResponseTimeline } from '@/features/patients/QuizResponseTimeline'
import { useMonthlyQuizAdmin } from '@/hooks/useMonthlyQuizAdmin'
import { useAIInsights, useAIRecommendations } from '@/hooks/useAI'
import { useAuth } from '@/app/providers/AuthContext'
import { FEATURES } from '@/config'
import { PatientDetailHeader } from '@/features/patients/components/PatientDetailHeader'
import { PatientOverviewCard } from '@/features/patients/components/PatientOverviewCard'
import { PatientQuizSection } from '@/features/patients/components/PatientQuizSection'
import { PatientAIAnalysis } from '@/features/patients/components/PatientAIAnalysis'
import type { QuizHistoryEntry } from '@/lib/api-client/monthly-quiz'

export function PatientDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const defaultTab = searchParams.get('tab') || 'overview'
  const [showSendQuizModal, setShowSendQuizModal] = useState(false)
  const { hasRole } = useAuth()
  const { useQuizLinkStatus, useQuizLinkHistory, resendQuizLink, cancelQuizLink } = useMonthlyQuizAdmin()

  // AI Hooks - Hooks will return mock data if AI is not configured
  const { data: aiInsights } = useAIInsights(id || '')
  const { data: aiRecommendations } = useAIRecommendations(id || '')

  const { data: patient, isLoading: patientLoading } = useQuery({
    queryKey: ['patient', id],
    queryFn: () => {
      if (!id) throw new Error('Patient ID is required')
      return apiClient.patients.get(id)
    },
    enabled: !!id
  })

  const { data: timeline, isLoading: timelineLoading } = useQuery({
    queryKey: ['patient-timeline', id],
    queryFn: () => {
      if (!id) throw new Error('Patient ID is required')
      return apiClient.patients.timeline(id)
    },
    enabled: !!id
  })

  const { data: quizStatus } = useQuizLinkStatus(id || '')
  const { data: quizHistory, isLoading: quizHistoryLoading } = useQuizLinkHistory(id || '')

  // Type guard to check if AI insights is an object (not an array)
  const isAIInsightsObject = (data: typeof aiInsights): data is import('@/lib/api-client/types').AIInsights => {
    return data != null && typeof data === 'object' && !Array.isArray(data) && 'patient_id' in data
  }

  const aiInsightsData = useMemo(() => isAIInsightsObject(aiInsights) ? aiInsights : undefined, [aiInsights])

  const totalQuizzes = quizHistory?.length ?? 0
  const completedQuizCount = useMemo(() => quizHistory
    ? quizHistory.filter((entry: QuizHistoryEntry) => entry.status === 'completed').length
    : 0, [quizHistory])

  const quizCompletionRate = useMemo(() => totalQuizzes > 0
    ? Math.round((completedQuizCount / totalQuizzes) * 100)
    : 0, [totalQuizzes, completedQuizCount])

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

  return (
    <div className="space-y-6">
      {/* Header */}
      <PatientDetailHeader patientName={patient.name} status={patient.status || 'inactive'} />

      {/* Patient Overview */}
      <PatientOverviewCard patient={patient} />

      {/* Quiz Mensal Section */}
      <PatientQuizSection
        patientId={id || ''}
        quizStatus={quizStatus}
        quizHistory={quizHistory || []}
        quizHistoryLoading={quizHistoryLoading}
        completedQuizCount={completedQuizCount}
        quizCompletionRate={quizCompletionRate}
        onSendQuiz={() => setShowSendQuizModal(true)}
        onResendQuiz={resendQuizLink}
        onCancelQuiz={cancelQuizLink}
      />

      {/* Main Content Tabs */}
      <Tabs defaultValue={defaultTab} className="space-y-6">
        <TabsList>
          <TabsTrigger value="overview">Visão Geral</TabsTrigger>
          <TabsTrigger value="timeline">Linha do Tempo</TabsTrigger>
          <TabsTrigger value="quiz-responses">Respostas de Quiz</TabsTrigger>
          {FEATURES.AI_CHAT && (hasRole('doctor') || hasRole('admin')) && (
            <>
              <TabsTrigger value="ai-summary">Resumo IA</TabsTrigger>
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
              {id && (
                <>
                  <FlowStatus patientId={id} />
                  <QuickActions patientId={id} />
                </>
              )}
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
              {id && patient && (
                <QuizResponseViewer patientId={id} patientName={patient.name} />
              )}
            </div>

            {/* Right Column - Timeline and Actions */}
            <div className="space-y-6">
              {id && <QuizResponseTimeline patientId={id} />}

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
            <TabsContent value="ai-summary" className="space-y-6">
              {id && patient && (
                <PatientAISummary patientId={id} patientName={patient.name} />
              )}
            </TabsContent>
            <PatientAIAnalysis
              patientId={id || ''}
              patientName={patient.name}
              aiInsightsData={aiInsightsData}
              aiRecommendations={aiRecommendations}
            />
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
      {id && (
        <SendQuizLinkModal
          open={showSendQuizModal}
          onOpenChange={setShowSendQuizModal}
          patientId={id}
          patientName={patient?.name || ''}
        />
      )}
    </div>
  )
}
