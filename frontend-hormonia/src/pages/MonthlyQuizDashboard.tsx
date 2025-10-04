import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Send, TrendingUp, CircleCheck as CheckCircle, Circle as XCircle, Clock } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { apiClient } from '@/lib/api-client'
import { useMonthlyQuizAdmin } from '@/hooks/useMonthlyQuizAdmin'
import { SendQuizLinkModal } from '@/components/quiz/SendQuizLinkModal'
import { QuizLinkStatus } from '@/components/quiz/QuizLinkStatus'
import { createLogger } from '../lib/logger'

const logger = createLogger('MonthlyQuizDashboard')
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'

export function MonthlyQuizDashboard() {
  const [selectedPatient, setSelectedPatient] = useState<{ id: string; name: string } | null>(null)
  const [showSendModal, setShowSendModal] = useState(false)

  const { data: stats, isLoading: isLoadingStats } = useQuery({
    queryKey: ['monthly-quiz-stats'],
    queryFn: () => apiClient.monthlyQuiz.getStats()
  })

  const { data: activeLinks, isLoading: isLoadingLinks } = useQuery({
    queryKey: ['monthly-quiz-active-links'],
    queryFn: () => apiClient.monthlyQuiz.getActiveLinks()
  })

  const { resendQuizLink } = useMonthlyQuizAdmin()

  const handleSendToPatient = (patient: { id: string; name: string }) => {
    setSelectedPatient(patient)
    setShowSendModal(true)
  }

  const handleResend = async (sessionId: string) => {
    try {
      await resendQuizLink(sessionId)
    } catch (error) {
      logger.error('Error resending quiz link', { sessionId, error })
    }
  }

  if (isLoadingStats) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  // Extract stats with fallbacks for backward compatibility
  const totalSent = stats?.total_sent ?? stats?.total_links_created ?? 0;
  const totalCompleted = stats?.total_completed ?? stats?.completed_quizzes ?? 0;
  const expiredLinks = stats?.total_expired ?? stats?.expired_links ?? 0;
  const activeLinksCount = stats?.total_active ?? stats?.active_links ?? 0;

  const metrics = [
    {
      title: 'Links Enviados',
      value: totalSent,
      icon: Send,
      color: 'text-blue-600',
      bgColor: 'bg-blue-100'
    },
    {
      title: 'Completados',
      value: totalCompleted,
      icon: CheckCircle,
      color: 'text-green-600',
      bgColor: 'bg-green-100'
    },
    {
      title: 'Expirados',
      value: expiredLinks,
      icon: XCircle,
      color: 'text-red-600',
      bgColor: 'bg-red-100'
    },
    {
      title: 'Ativos',
      value: activeLinksCount,
      icon: Clock,
      color: 'text-yellow-600',
      bgColor: 'bg-yellow-100'
    }
  ]

  const completionRate = stats?.completion_rate ??
    (totalSent > 0 ? ((totalCompleted / totalSent) * 100).toFixed(1) : '0')

  return (
    <div className="space-y-4 sm:space-y-6 px-3 sm:px-4 lg:px-6 py-4 sm:py-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Quiz Mensal</h1>
          <p className="text-sm sm:text-base text-gray-600 mt-1">Gerencie os questionários mensais dos pacientes</p>
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-6">
        {metrics.map((metric) => {
          const Icon = metric.icon
          return (
            <Card key={metric.title}>
              <CardContent className="p-4 sm:pt-6 sm:px-6">
                <div className="flex flex-col sm:flex-row items-start sm:items-center sm:justify-between gap-3">
                  <div className="flex-1">
                    <p className="text-xs sm:text-sm font-medium text-gray-600">{metric.title}</p>
                    <p className="text-2xl sm:text-3xl font-bold text-gray-900 mt-1 sm:mt-2">{metric.value}</p>
                  </div>
                  <div className={`p-2 sm:p-3 rounded-lg ${metric.bgColor}`}>
                    <Icon className={`h-5 w-5 sm:h-6 sm:w-6 ${metric.color}`} />
                  </div>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Completion Rate */}
      <Card>
        <CardHeader className="px-4 sm:px-6">
          <CardTitle className="flex items-center text-base sm:text-lg">
            <TrendingUp className="mr-2 h-4 w-4 sm:h-5 sm:w-5 text-blue-600" />
            Taxa de Conclusão
          </CardTitle>
        </CardHeader>
        <CardContent className="px-4 sm:px-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
            <div className="text-3xl sm:text-4xl font-bold text-blue-600">{completionRate}%</div>
            <div className="flex-1 w-full">
              <div className="h-3 sm:h-4 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-600 transition-all duration-500"
                  style={{ width: `${completionRate}%` }}
                />
              </div>
              <p className="text-xs sm:text-sm text-gray-600 mt-2">
                {totalCompleted} de {totalSent} links completados
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Active Links */}
      <Card>
        <CardHeader className="px-4 sm:px-6">
          <CardTitle className="text-base sm:text-lg">Links Ativos</CardTitle>
          <CardDescription className="text-sm">
            Questionários enviados e aguardando resposta
          </CardDescription>
        </CardHeader>
        <CardContent className="px-0 sm:px-6">
          {isLoadingLinks ? (
            <div className="flex items-center justify-center py-8">
              <LoadingSpinner size="lg" />
            </div>
          ) : !activeLinks || activeLinks.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-sm text-gray-500">Nenhum link ativo no momento</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="min-w-[150px]">Paciente</TableHead>
                    <TableHead className="hidden sm:table-cell min-w-[120px]">Template</TableHead>
                    <TableHead className="hidden md:table-cell">Enviado</TableHead>
                    <TableHead className="hidden lg:table-cell">Expira em</TableHead>
                    <TableHead className="min-w-[100px]">Status</TableHead>
                    <TableHead className="text-right">Ações</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {activeLinks.map((link: any) => {
                    // Fallback for sent_at field (backward compatibility)
                    const sentDate = link.sent_at ?? link.created_at;

                    return (
                      <TableRow key={link.id}>
                        <TableCell className="font-medium">
                          <div className="flex flex-col">
                            <span>{link.patient_name}</span>
                            <span className="sm:hidden text-xs text-gray-500 mt-1">
                              {link.template_name}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="hidden sm:table-cell">
                          <Badge variant="outline" className="text-xs">{link.template_name}</Badge>
                        </TableCell>
                        <TableCell className="hidden md:table-cell text-sm text-gray-600">
                          {sentDate ? new Date(sentDate).toLocaleDateString('pt-BR') : '-'}
                        </TableCell>
                        <TableCell className="hidden lg:table-cell text-sm text-gray-600">
                          {link.expires_at ? new Date(link.expires_at).toLocaleDateString('pt-BR') : '-'}
                        </TableCell>
                        <TableCell>
                          <QuizLinkStatus
                            patientId={link.patient_id}
                            lastSent={sentDate ? new Date(sentDate) : new Date()}
                            linkStatus={link.status}
                            expiresAt={link.expires_at ? new Date(link.expires_at) : new Date()}
                          />
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="outline"
                            size="sm"
                            className="text-xs"
                            onClick={() => handleResend(link.session_id || link.id)}
                          >
                            Reenviar
                          </Button>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Send Link Modal */}
      {selectedPatient && (
        <SendQuizLinkModal
          open={showSendModal}
          onOpenChange={setShowSendModal}
          patientId={selectedPatient.id}
          patientName={selectedPatient.name}
          onSuccess={() => {
            setSelectedPatient(null)
          }}
        />
      )}
    </div>
  )
}