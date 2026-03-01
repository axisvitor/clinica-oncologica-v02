import React, { useState, useMemo } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Calendar, Send, MessageSquare } from 'lucide-react'
import { Link } from 'react-router-dom'
import { apiClient } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { PatientDetailSkeleton } from '@/features/patients/PatientDetailSkeleton'
import { PatientTimeline } from '@/features/patients/PatientTimeline'
import { FlowStatus } from '@/features/patients/FlowStatus'
import { MessagesList } from '@/features/messages/MessagesList'
import { MessageComposer } from '@/features/messages/MessageComposer'
import { QuickActions } from '@/features/patients/QuickActions'
import { SendQuizLinkModal } from '@/features/quiz/SendQuizLinkModal'
import { PatientAISummary } from '@/features/ai/PatientAISummary'
import { QuizResponseViewer } from '@/features/patients/QuizResponseViewer'
import { QuizResponseTimeline } from '@/features/patients/QuizResponseTimeline'
import { useMonthlyQuizAdmin } from '@/hooks/useMonthlyQuizAdmin'
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
  const canAccessAiSummary = FEATURES.AI_SUMMARY && (hasRole('doctor') || hasRole('admin'))
  const canAccessAiChat = FEATURES.AI_CHAT && (hasRole('doctor') || hasRole('admin'))

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

  // Fetch patient messages
  const { data: messagesData, isLoading: messagesLoading } = useQuery({
    queryKey: ['messages', { patient_id: id }],
    queryFn: () => {
      if (!id) throw new Error('Patient ID is required')
      return apiClient.messages.list({ patient_id: id })
    },
    enabled: !!id
  })

  const totalQuizzes = quizHistory?.length ?? 0
  const completedQuizCount = useMemo(() => quizHistory
    ? quizHistory.filter((entry: QuizHistoryEntry) => entry.status === 'completed').length
    : 0, [quizHistory])

  const quizCompletionRate = useMemo(() => totalQuizzes > 0
    ? Math.round((completedQuizCount / totalQuizzes) * 100)
    : 0, [totalQuizzes, completedQuizCount])

  if (patientLoading) {
    return <PatientDetailSkeleton />
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
          {canAccessAiSummary && (
            <TabsTrigger value="ai-summary">Resumo IA</TabsTrigger>
          )}
          {canAccessAiChat && (
            <TabsTrigger value="ai-chat">Chat IA</TabsTrigger>
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

        {canAccessAiSummary && (
          <TabsContent value="ai-summary" className="space-y-6">
            {id && patient && (
              <PatientAISummary patientId={id} patientName={patient.name} />
            )}
          </TabsContent>
        )}
        {canAccessAiChat && (
          <PatientAIAnalysis
            patientId={id || ''}
            patientName={patient.name}
            showChat={canAccessAiChat}
          />
        )}

        <TabsContent value="messages" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MessageSquare className="h-5 w-5" />
                Mensagens
              </CardTitle>
              <CardDescription>Histórico de comunicação com o paciente via WhatsApp</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {id && patient && (
                <>
                  <MessagesList
                    messages={messagesData?.items || messagesData?.data || []}
                    isLoading={messagesLoading}
                    patientName={patient.name}
                  />
                  <div className="border-t pt-4">
                    <MessageComposer
                      patientId={id}
                      patientName={patient.name}
                      onMessageSent={() => { }}
                    />
                  </div>
                </>
              )}
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
