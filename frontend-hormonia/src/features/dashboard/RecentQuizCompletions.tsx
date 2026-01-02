import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { FileText, CheckCircle, ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { apiClient } from '@/lib/api-client'
import type { QuizSession as BaseQuizSession } from '@/lib/api-client/types'

// Extend QuizSession with optional UI-specific enriched fields
interface QuizSession extends BaseQuizSession {
  patient_name?: string
  template_name?: string
}

export function RecentQuizCompletions() {
  // Fetch recent quiz sessions across all patients
  const { data: sessionsData, isLoading, error } = useQuery({
    queryKey: ['recent-quiz-sessions'],
    queryFn: async () => {
      // Get all quiz sessions
      const response = await apiClient.quiz.sessions({})
      return response
    },
    refetchInterval: 60000 // Refresh every minute
  })

  // Format date
  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return 'Agora mesmo'
    if (diffMins < 60) return `${diffMins}m atrás`
    if (diffHours < 24) return `${diffHours}h atrás`
    if (diffDays < 7) return `${diffDays}d atrás`
    
    return date.toLocaleDateString('pt-BR', {
      day: '2-digit',
      month: 'short'
    })
  }

  // Get status badge variant
  const getStatusBadgeVariant = (status: string): 'default' | 'secondary' | 'outline' => {
    switch (status) {
      case 'completed':
        return 'default'
      case 'started':
        return 'secondary'
      default:
        return 'outline'
    }
  }

  // Get recent completed sessions (last 5)
  const recentSessions = React.useMemo(() => {
    if (!sessionsData?.items) return []

    return sessionsData.items
      .filter((session: QuizSession) => session.status === 'completed')
      .sort((a: QuizSession, b: QuizSession) => {
        const dateA = a.completed_at || a.started_at
        const dateB = b.completed_at || b.started_at
        if (!dateA || !dateB) return 0
        return new Date(dateB).getTime() - new Date(dateA).getTime()
      })
      .slice(0, 5)
  }, [sessionsData])

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Quiz Recentes
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <LoadingSpinner size="md" />
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Quiz Recentes
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center text-red-600 py-4 text-sm">
            Erro ao carregar quiz recentes
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileText className="h-5 w-5" />
          Quiz Recentes
        </CardTitle>
        <CardDescription>
          Últimos questionários completados
        </CardDescription>
      </CardHeader>
      <CardContent>
        {recentSessions.length === 0 ? (
          <div className="text-center py-8">
            <FileText className="mx-auto h-12 w-12 text-gray-400 mb-4" />
            <p className="text-gray-500 text-sm">Nenhum quiz completado recentemente</p>
          </div>
        ) : (
          <div className="space-y-4">
            {recentSessions.map((session: QuizSession) => (
              <Link
                key={session.id}
                to={`/patients/${session.patient_id}?tab=quiz-responses`}
                className="block"
              >
                <div className="flex items-start gap-3 p-3 rounded-lg border hover:border-blue-300 hover:bg-blue-50 transition-all cursor-pointer">
                  <div className="flex-shrink-0 mt-1">
                    <CheckCircle className="h-5 w-5 text-green-600" />
                  </div>
                  
                  <div className="flex-1 min-w-0 space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {session.patient_name || `Paciente ${session.patient_id.slice(0, 8)}`}
                      </p>
                      <Badge variant={getStatusBadgeVariant(session.status)} className="flex-shrink-0">
                        {session.status}
                      </Badge>
                    </div>
                    
                    <p className="text-xs text-gray-600 truncate">
                      {session.template_name || 'Quiz'}
                    </p>
                    
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs text-gray-500">
                        {formatDate(session.completed_at || session.started_at || new Date().toISOString())}
                      </span>
                      {session.score !== undefined && session.score !== null && (
                        <span className="text-xs font-medium text-blue-600">
                          Score: {session.score}
                        </span>
                      )}
                    </div>
                  </div>
                  
                  <div className="flex-shrink-0">
                    <ArrowRight className="h-4 w-4 text-gray-400" />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

