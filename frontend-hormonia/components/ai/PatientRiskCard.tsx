import React from 'react'
import {
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  MessageSquare,
  Calendar,
  Clock,
  Activity
} from 'lucide-react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'

interface PatientRiskCardProps {
  patient: {
    id: string
    name: string
    phone: string
    treatment_type: string
    risk_level: 'critical' | 'high' | 'medium' | 'low'
    risk_factors: string[]
    last_interaction: string
    sentiment_score: number
    engagement_score: number
    has_alerts: boolean
  }
  onPatientClick: (patientId: string) => void
  onQuickAction: (patientId: string, action: string) => void
}

export function PatientRiskCard({ patient, onPatientClick, onQuickAction }: PatientRiskCardProps) {
  const getRiskColor = (level: string) => {
    switch (level) {
      case 'critical':
        return 'bg-red-500 text-white'
      case 'high':
        return 'bg-orange-500 text-white'
      case 'medium':
        return 'bg-yellow-500 text-white'
      case 'low':
        return 'bg-green-500 text-white'
      default:
        return 'bg-gray-500 text-white'
    }
  }

  const getRiskBorderColor = (level: string) => {
    switch (level) {
      case 'critical':
        return 'border-red-500'
      case 'high':
        return 'border-orange-500'
      case 'medium':
        return 'border-yellow-500'
      case 'low':
        return 'border-green-500'
      default:
        return 'border-gray-500'
    }
  }

  const getRiskLabel = (level: string) => {
    switch (level) {
      case 'critical':
        return 'Crítico'
      case 'high':
        return 'Alto'
      case 'medium':
        return 'Médio'
      case 'low':
        return 'Baixo'
      default:
        return level
    }
  }

  const getSentimentIcon = (score: number) => {
    if (score >= 0.7) return <TrendingUp className="h-4 w-4 text-green-500" />
    if (score <= 0.3) return <TrendingDown className="h-4 w-4 text-red-500" />
    return <Activity className="h-4 w-4 text-yellow-500" />
  }

  const formatLastInteraction = (timestamp: string) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

    if (diffHours < 1) return 'Há menos de 1 hora'
    if (diffHours < 24) return `Há ${diffHours}h`
    if (diffDays === 1) return 'Há 1 dia'
    if (diffDays < 7) return `Há ${diffDays} dias`
    return date.toLocaleDateString('pt-BR')
  }

  return (
    <Card
      className={`cursor-pointer hover:shadow-lg transition-shadow border-l-4 ${getRiskBorderColor(
        patient.risk_level
      )}`}
      onClick={() => onPatientClick(patient.id)}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <h3 className="font-semibold text-lg">{patient.name}</h3>
            <p className="text-sm text-muted-foreground">{patient.phone}</p>
          </div>
          <div className="flex flex-col items-end gap-1">
            <Badge className={getRiskColor(patient.risk_level)}>
              {getRiskLabel(patient.risk_level)}
            </Badge>
            {patient.has_alerts && (
              <Badge variant="destructive" className="text-xs">
                <AlertTriangle className="h-3 w-3 mr-1" />
                Alerta
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Treatment Type */}
        <div>
          <p className="text-xs text-muted-foreground mb-1">Tipo de Tratamento</p>
          <Badge variant="outline">{patient.treatment_type}</Badge>
        </div>

        {/* Risk Factors */}
        {patient.risk_factors && patient.risk_factors.length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-2">Fatores de Risco</p>
            <div className="flex flex-wrap gap-1">
              {patient.risk_factors.slice(0, 3).map((factor, index) => (
                <Badge key={index} variant="secondary" className="text-xs">
                  {factor}
                </Badge>
              ))}
              {patient.risk_factors.length > 3 && (
                <Badge variant="secondary" className="text-xs">
                  +{patient.risk_factors.length - 3}
                </Badge>
              )}
            </div>
          </div>
        )}

        {/* Sentiment Score */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <p className="text-xs text-muted-foreground flex items-center gap-1">
              {getSentimentIcon(patient.sentiment_score)}
              Sentimento
            </p>
            <span className="text-xs font-medium">
              {(patient.sentiment_score * 100).toFixed(0)}%
            </span>
          </div>
          <Progress value={patient.sentiment_score * 100} className="h-2" />
        </div>

        {/* Engagement Score */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <p className="text-xs text-muted-foreground">Engajamento</p>
            <span className="text-xs font-medium">{patient.engagement_score}/100</span>
          </div>
          <Progress value={patient.engagement_score} className="h-2" />
        </div>

        {/* Last Interaction */}
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Clock className="h-3 w-3" />
          <span>{formatLastInteraction(patient.last_interaction)}</span>
        </div>

        {/* Quick Actions */}
        <div className="flex gap-2 pt-2 border-t">
          <Button
            size="sm"
            variant="outline"
            className="flex-1"
            onClick={(e) => {
              e.stopPropagation()
              onQuickAction(patient.id, 'message')
            }}
          >
            <MessageSquare className="h-3 w-3 mr-1" />
            Msg
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="flex-1"
            onClick={(e) => {
              e.stopPropagation()
              onQuickAction(patient.id, 'schedule')
            }}
          >
            <Calendar className="h-3 w-3 mr-1" />
            Agendar
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="flex-1"
            onClick={(e) => {
              e.stopPropagation()
              onQuickAction(patient.id, 'review')
            }}
          >
            <Activity className="h-3 w-3 mr-1" />
            Revisar
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}