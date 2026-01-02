import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { FileText, CheckCircle, Clock, AlertCircle } from 'lucide-react'
import { apiClient } from '@/lib/api-client'
interface QuizResponseTimelineProps {
  patientId: string
  onSessionClick?: (sessionId: string) => void
  className?: string
}

interface _TimelineSession {
  id: string
  template_name: string
  template_version: string
  status: string
  date: string
  responseCount: number
}

export function QuizResponseTimeline({ patientId, onSessionClick, className }: QuizResponseTimelineProps) {
  // Fetch patient quiz sessions
  const { data: sessionsData, isLoading, error } = useQuery({
    queryKey: ['patient-quiz-sessions-timeline', patientId],
    queryFn: async () => {
      const result = await apiClient.quiz.getPatientResponses(patientId, {
        page: 1,
        size: 100 // Get more sessions for timeline
      })
      return result
    }
  })

  // Convert sessions to timeline format
  const sessions = React.useMemo(() => {
    if (!sessionsData?.sessions) return []

    return sessionsData.sessions.map(session => ({
      id: session.id,
      template_name: 'Quiz', // Default name, could be enhanced with template lookup
      template_version: '1.0',
      status: session.status,
      date: session.created_at,
      responseCount: 0 // This could be fetched separately if needed
    })).sort((a, b) =>
      new Date(b.date).getTime() - new Date(a.date).getTime()
    )
  }, [sessionsData])

  // Format date
  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleDateString('pt-BR', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  // Get status icon
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return CheckCircle
      case 'started':
        return Clock
      case 'cancelled':
        return AlertCircle
      default:
        return FileText
    }
  }

  // Get status color
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'text-green-600 bg-green-100'
      case 'started':
        return 'text-blue-600 bg-blue-100'
      case 'cancelled':
        return 'text-red-600 bg-red-100'
      default:
        return 'text-gray-600 bg-gray-100'
    }
  }

  // Get status badge variant
  const getStatusBadgeVariant = (status: string): 'default' | 'secondary' | 'destructive' | 'outline' => {
    switch (status) {
      case 'completed':
        return 'default'
      case 'started':
        return 'secondary'
      case 'cancelled':
        return 'destructive'
      default:
        return 'outline'
    }
  }

  if (isLoading) {
    return (
      <Card className={className}>
        <CardContent className="pt-6">
          <div className="flex items-center justify-center py-8">
            <LoadingSpinner size="md" />
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card className={className}>
        <CardContent className="pt-6">
          <div className="text-center text-red-600 py-8">
            Erro ao carregar timeline de quiz. Por favor, tente novamente.
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Timeline de Quiz</CardTitle>
        <CardDescription>
          {sessions.length === 0 
            ? 'Nenhuma sessão de quiz encontrada'
            : `${sessions.length} ${sessions.length === 1 ? 'sessão' : 'sessões'} de quiz`
          }
        </CardDescription>
      </CardHeader>
      <CardContent>
        {sessions.length === 0 ? (
          <div className="text-center py-8">
            <FileText className="mx-auto h-12 w-12 text-gray-400 mb-4" />
            <p className="text-gray-500">Nenhuma sessão de quiz registrada</p>
            <p className="text-sm text-gray-400">
              As sessões de quiz aparecerão aqui quando o paciente completar questionários
            </p>
          </div>
        ) : (
          <ScrollArea className="h-[400px]">
            <div className="space-y-4">
              {sessions.map((session, index) => {
                const Icon = getStatusIcon(session.status)
                const colorClass = getStatusColor(session.status)
                
                return (
                  <div
                    key={session.id}
                    className={`relative flex gap-4 pb-4 ${
                      index !== sessions.length - 1 ? 'border-l-2 border-gray-200 ml-4' : ''
                    }`}
                  >
                    {/* Timeline dot */}
                    <div className={`absolute -left-[9px] top-0 w-4 h-4 rounded-full ${colorClass} flex items-center justify-center`}>
                      <div className="w-2 h-2 rounded-full bg-white" />
                    </div>
                    
                    {/* Content */}
                    <div 
                      className={`flex-1 ml-8 p-4 rounded-lg border bg-white ${
                        onSessionClick ? 'cursor-pointer hover:border-blue-300 hover:shadow-sm transition-all' : ''
                      }`}
                      onClick={() => onSessionClick?.(session.id)}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 space-y-2">
                          <div className="flex items-center gap-2">
                            <Icon className={`h-4 w-4 ${colorClass.split(' ')[0]}`} />
                            <span className="font-medium text-sm">{session.template_name}</span>
                          </div>
                          
                          <div className="text-xs text-muted-foreground space-y-1">
                            <div>Versão: {session.template_version}</div>
                            <div>{formatDate(session.date)}</div>
                            <div>{session.responseCount} {session.responseCount === 1 ? 'resposta' : 'respostas'}</div>
                          </div>
                        </div>
                        
                        <Badge variant={getStatusBadgeVariant(session.status)}>
                          {session.status}
                        </Badge>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  )
}

