import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ChevronLeft, ChevronRight, FileText, Calendar } from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import { QuizAnalysisCard } from './QuizAnalysisCard'
import { QuizResponsePDFExport } from './QuizResponsePDFExport'
import type { PatientQuizResponsesResponse, QuizAnalysisResponse } from '@/types/quiz'

interface QuizResponseViewerProps {
  patientId: string
  patientName?: string
  className?: string
}

export function QuizResponseViewer({ patientId, patientName = 'Paciente', className }: QuizResponseViewerProps) {
  const [currentPage, setCurrentPage] = useState(1)
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const pageSize = 20

  // Fetch patient quiz responses
  const { data: responsesData, isLoading: responsesLoading, error: responsesError } = useQuery<PatientQuizResponsesResponse>({
    queryKey: ['patient-quiz-responses', patientId, currentPage],
    queryFn: () => apiClient.quiz.getPatientResponses(patientId, {
      page: currentPage,
      size: pageSize
    })
  })

  // Fetch analysis for selected session
  const { data: analysisData, isLoading: analysisLoading } = useQuery<QuizAnalysisResponse>({
    queryKey: ['quiz-session-analysis', selectedSessionId],
    queryFn: () => apiClient.quiz.getSessionAnalysis(selectedSessionId!),
    enabled: !!selectedSessionId
  })

  // Format date
  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleDateString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  // Get unique sessions from responses
  const sessions = React.useMemo(() => {
    if (!responsesData?.items) return []
    const sessionMap = new Map()
    responsesData.items.forEach(response => {
      if (response.quiz_session_id && !sessionMap.has(response.quiz_session_id)) {
        sessionMap.set(response.quiz_session_id, {
          id: response.quiz_session_id,
          template_name: response.template_name,
          template_version: response.template_version,
          status: response.session_status,
          date: response.responded_at
        })
      }
    })
    return Array.from(sessionMap.values())
  }, [responsesData])

  // Handle page change
  const handlePageChange = (newPage: number) => {
    setCurrentPage(newPage)
  }

  if (responsesLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (responsesError) {
    return (
      <Card className={className}>
        <CardContent className="pt-6">
          <div className="text-center text-red-600">
            Erro ao carregar respostas do quiz. Por favor, tente novamente.
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!responsesData || responsesData.items.length === 0) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>Respostas de Quiz</CardTitle>
          <CardDescription>Histórico de respostas do paciente</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center text-muted-foreground py-8">
            Nenhuma resposta de quiz encontrada para este paciente.
          </div>
        </CardContent>
      </Card>
    )
  }

  const totalPages = responsesData.pages || Math.ceil(responsesData.total / pageSize)

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Sessions Overview */}
      {sessions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calendar className="h-5 w-5" />
              Sessões de Quiz
            </CardTitle>
            <CardDescription>
              {sessions.length} {sessions.length === 1 ? 'sessão encontrada' : 'sessões encontradas'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {sessions.map((session) => (
                <div
                  key={session.id}
                  className={`p-4 border rounded-lg cursor-pointer transition-colors ${
                    selectedSessionId === session.id
                      ? 'border-blue-600 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                  onClick={() => setSelectedSessionId(session.id)}
                >
                  <div className="space-y-2">
                    <div className="font-medium text-sm">{session.template_name}</div>
                    <div className="text-xs text-muted-foreground">
                      Versão: {session.template_version}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {formatDate(session.date)}
                    </div>
                    {session.status && (
                      <Badge variant={session.status === 'completed' ? 'default' : 'secondary'}>
                        {session.status}
                      </Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* AI Analysis Card */}
      {selectedSessionId && analysisData && (
        <QuizAnalysisCard analysis={analysisData} />
      )}

      {selectedSessionId && analysisLoading && (
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-center">
              <LoadingSpinner size="md" />
              <span className="ml-2 text-sm text-muted-foreground">Carregando análise...</span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Responses Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Respostas do Quiz
              </CardTitle>
              <CardDescription>
                Mostrando {responsesData.items.length} de {responsesData.total} respostas
              </CardDescription>
            </div>
            <QuizResponsePDFExport
              responses={responsesData.items}
              analysis={analysisData}
              patientName={patientName}
            />
          </div>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Pergunta</TableHead>
                  <TableHead>Resposta</TableHead>
                  <TableHead>Tipo</TableHead>
                  <TableHead>Template</TableHead>
                  <TableHead>Data</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {responsesData.items.map((response) => (
                  <TableRow key={response.id}>
                    <TableCell className="font-medium max-w-xs">
                      <div className="truncate" title={response.question_text}>
                        {response.question_text}
                      </div>
                    </TableCell>
                    <TableCell className="max-w-xs">
                      <div className="truncate" title={response.response_value}>
                        {response.response_value}
                      </div>
                      {response.other_text && (
                        <div className="text-xs text-muted-foreground mt-1">
                          Outro: {response.other_text}
                        </div>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{response.response_type}</Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {response.template_name}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDate(response.responded_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <div className="text-sm text-muted-foreground">
                Página {currentPage} de {totalPages}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handlePageChange(currentPage - 1)}
                  disabled={currentPage === 1}
                >
                  <ChevronLeft className="h-4 w-4 mr-1" />
                  Anterior
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handlePageChange(currentPage + 1)}
                  disabled={currentPage === totalPages}
                >
                  Próxima
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

