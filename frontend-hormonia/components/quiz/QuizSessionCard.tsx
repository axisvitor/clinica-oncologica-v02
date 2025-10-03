import React from 'react'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { FileText, Play, CheckCircle, Clock, User } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'

interface QuizSession {
  id: string
  patient_id: string
  patient_name?: string
  template_id: string
  template_name?: string
  status: 'pending' | 'started' | 'completed'
  responses: Record<string, any>
  score?: number
  started_at?: string
  completed_at?: string
  created_at: string
}

interface QuizSessionCardProps {
  session: QuizSession
  onContinue?: (sessionId: string) => void
  onView?: (sessionId: string) => void
}

export function QuizSessionCard({ session, onContinue, onView }: QuizSessionCardProps) {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return CheckCircle
      case 'started':
        return Play
      case 'pending':
        return Clock
      default:
        return FileText
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <Badge className="bg-green-100 text-green-800">Completado</Badge>
      case 'started':
        return <Badge className="bg-blue-100 text-blue-800">Em andamento</Badge>
      case 'pending':
        return <Badge className="bg-yellow-100 text-yellow-800">Pendente</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'completed':
        return 'Completado'
      case 'started':
        return 'Em andamento'
      case 'pending':
        return 'Pendente'
      default:
        return status
    }
  }

  const StatusIcon = getStatusIcon(session.status)
  
  // Calculate progress for started sessions
  const totalQuestions = Object.keys(session.responses || {}).length
  const answeredQuestions = Object.values(session.responses || {}).filter(
    answer => answer !== null && answer !== '' && answer !== undefined
  ).length
  const progressPercentage = totalQuestions > 0 ? (answeredQuestions / totalQuestions) * 100 : 0

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-3">
            <div className="flex items-center justify-center w-10 h-10 bg-blue-100 rounded-lg">
              <StatusIcon className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <CardTitle className="text-lg">
                {session.template_name || 'Questionário'}
              </CardTitle>
              <CardDescription className="flex items-center space-x-2">
                <User className="h-3 w-3" />
                <span>{session.patient_name || 'Paciente não encontrado'}</span>
              </CardDescription>
            </div>
          </div>
          {getStatusBadge(session.status)}
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Progress for started sessions */}
          {session.status === 'started' && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-600">Progresso</span>
                <span className="font-medium">{Math.round(progressPercentage)}%</span>
              </div>
              <Progress value={progressPercentage} className="w-full" />
            </div>
          )}

          {/* Score for completed sessions */}
          {session.status === 'completed' && session.score !== undefined && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Pontuação</span>
              <span className="font-medium text-lg">{Math.round(session.score)}%</span>
            </div>
          )}

          {/* Timestamps */}
          <div className="space-y-2 text-sm text-gray-600">
            <div className="flex items-center justify-between">
              <span>Criado</span>
              <span>
                {formatDistanceToNow(new Date(session.created_at), {
                  addSuffix: true,
                  locale: ptBR
                })}
              </span>
            </div>
            
            {session.started_at && (
              <div className="flex items-center justify-between">
                <span>Iniciado</span>
                <span>
                  {formatDistanceToNow(new Date(session.started_at), {
                    addSuffix: true,
                    locale: ptBR
                  })}
                </span>
              </div>
            )}
            
            {session.completed_at && (
              <div className="flex items-center justify-between">
                <span>Completado</span>
                <span>
                  {formatDistanceToNow(new Date(session.completed_at), {
                    addSuffix: true,
                    locale: ptBR
                  })}
                </span>
              </div>
            )}
          </div>
          
          {/* Actions */}
          <div className="flex space-x-2">
            {session.status === 'started' ? (
              <Button
                size="sm"
                onClick={() => onContinue?.(session.id)}
                className="flex-1"
              >
                <Play className="mr-2 h-4 w-4" />
                Continuar
              </Button>
            ) : session.status === 'completed' ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onView?.(session.id)}
                className="flex-1"
              >
                <CheckCircle className="mr-2 h-4 w-4" />
                Visualizar
              </Button>
            ) : (
              <Button
                size="sm"
                onClick={() => onContinue?.(session.id)}
                className="flex-1"
              >
                <Play className="mr-2 h-4 w-4" />
                Iniciar
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
