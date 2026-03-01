import React from 'react'
import { Lightbulb, Brain, Clock } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import type { AIInsight } from '@/types/api'

interface Recommendation {
  id: string
  title: string
  description: string
  priority?: string
  type?: string
  rationale?: string
}

interface PhysicianInsightsPanelProps {
  isLoading: boolean
  insights: AIInsight[] | undefined
  recommendations: Recommendation[] | undefined
}

export function PhysicianInsightsPanel({ isLoading, insights, recommendations }: PhysicianInsightsPanelProps) {
  if (isLoading) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-center">
            <LoadingSpinner size="lg" />
            <p className="ml-3 text-muted-foreground">Carregando análises...</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  if ((!insights || insights.length === 0) && (!recommendations || recommendations.length === 0)) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="text-center text-muted-foreground">
            <Lightbulb className="mx-auto h-8 w-8 mb-2" />
            <p>Análises automatizadas disponíveis apenas no contexto do paciente.</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {/* Key Insights */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lightbulb className="h-5 w-5" />
            Análises principais
          </CardTitle>
          <CardDescription>
            Padrões e recomendações detectadas automaticamente
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {insights?.slice(0, 5).map((insight) => (
            <div key={insight.id} className="border rounded-lg p-4 space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="font-medium">{insight.title}</h4>
                <Badge variant={insight.priority === 'high' || insight.priority === 'critical' ? 'destructive' : 'default'}>
                  {insight.priority}
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground">{insight.description}</p>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Clock className="h-3 w-3" />
                {new Date(insight.created_at).toLocaleString('pt-BR')}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Recommendations */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Brain className="h-5 w-5" />
            Recomendações IA
          </CardTitle>
          <CardDescription>
            Ações sugeridas baseadas em análise de dados
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {recommendations?.slice(0, 5).map((rec) => (
            <div key={rec.id} className="border rounded-lg p-4 space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="font-medium">{rec.title}</h4>
                <Badge>{rec.type}</Badge>
              </div>
              <p className="text-sm text-muted-foreground">{rec.description}</p>
              <p className="text-xs italic text-muted-foreground">{rec.rationale}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
