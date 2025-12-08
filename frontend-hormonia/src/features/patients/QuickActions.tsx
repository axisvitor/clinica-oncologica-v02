import React from 'react'
import { MessageSquare, FileText, AlertTriangle, Activity } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

interface QuickActionsProps {
  patientId: string
}

export function QuickActions({ patientId }: QuickActionsProps) {
  const navigate = useNavigate()

  const handleStartQuiz = () => {
    navigate(`/quiz?patient=${patientId}`)
  }

  const handleViewAnalytics = () => {
    navigate(`/patients/${patientId}/analytics`)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Ações Rápidas</CardTitle>
        <CardDescription>
          Ações comuns para este paciente
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Button 
          variant="outline" 
          className="w-full justify-start"
          asChild
        >
          <Link to={`/messages?patient=${patientId}`}>
            <MessageSquare className="mr-2 h-4 w-4" />
            Enviar Mensagem
          </Link>
        </Button>

        <Button
          variant="outline"
          className="w-full justify-start"
          onClick={handleStartQuiz}
        >
          <FileText className="mr-2 h-4 w-4" />
          Iniciar Questionário
        </Button>

        <Button 
          variant="outline" 
          className="w-full justify-start"
          asChild
        >
          <Link to={`/reports?patient=${patientId}`}>
            <FileText className="mr-2 h-4 w-4" />
            Gerar Relatório
          </Link>
        </Button>

        <Button 
          variant="outline" 
          className="w-full justify-start"
          asChild
        >
          <Link to={`/alerts?patient=${patientId}`}>
            <AlertTriangle className="mr-2 h-4 w-4" />
            Ver Alertas
          </Link>
        </Button>

        <Button
          variant="outline"
          className="w-full justify-start"
          onClick={handleViewAnalytics}
        >
          <Activity className="mr-2 h-4 w-4" />
          Ver Analytics
        </Button>
      </CardContent>
    </Card>
  )
}
