import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { AlertTriangle, TrendingUp, Lightbulb, Brain } from 'lucide-react'
import type { QuizAnalysisResponse } from '@/types/quiz'

interface QuizAnalysisCardProps {
  analysis: QuizAnalysisResponse
  className?: string
}

export function QuizAnalysisCard({ analysis, className }: QuizAnalysisCardProps) {
  // Get risk level badge variant
  const getRiskBadgeVariant = (level?: string) => {
    switch (level) {
      case 'critical':
        return 'destructive'
      case 'high':
        return 'destructive'
      case 'medium':
        return 'default'
      case 'low':
        return 'secondary'
      default:
        return 'outline'
    }
  }

  // Get risk level color
  const getRiskColor = (level?: string) => {
    switch (level) {
      case 'critical':
        return 'text-red-600'
      case 'high':
        return 'text-orange-600'
      case 'medium':
        return 'text-yellow-600'
      case 'low':
        return 'text-green-600'
      default:
        return 'text-gray-600'
    }
  }

  // Get sentiment indicator
  const getSentimentIndicator = (score?: number) => {
    if (score === undefined || score === null) return { text: 'N/A', color: 'text-gray-500' }
    if (score > 0.3) return { text: 'Positivo', color: 'text-green-600' }
    if (score < -0.3) return { text: 'Negativo', color: 'text-red-600' }
    return { text: 'Neutro', color: 'text-gray-600' }
  }

  const sentiment = getSentimentIndicator(analysis.sentiment_score)

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Brain className="h-5 w-5" />
          Análise de IA
        </CardTitle>
        <CardDescription>
          {analysis.template_name} - {analysis.template_version}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Risk Score Section */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Nível de Risco</span>
            {analysis.risk_level && (
              <Badge variant={getRiskBadgeVariant(analysis.risk_level)}>
                {analysis.risk_level.toUpperCase()}
              </Badge>
            )}
          </div>
          {analysis.risk_score !== undefined && analysis.risk_score !== null && (
            <div className="space-y-1">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Pontuação</span>
                <span className={`font-semibold ${getRiskColor(analysis.risk_level)}`}>
                  {analysis.risk_score.toFixed(1)}/100
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${
                    analysis.risk_level === 'critical' || analysis.risk_level === 'high'
                      ? 'bg-red-600'
                      : analysis.risk_level === 'medium'
                      ? 'bg-yellow-600'
                      : 'bg-green-600'
                  }`}
                  style={{ width: `${analysis.risk_score}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Sentiment Section */}
        {analysis.sentiment_score !== undefined && analysis.sentiment_score !== null && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Sentimento</span>
              <span className={`text-sm font-semibold ${sentiment.color}`}>
                {sentiment.text}
              </span>
            </div>
            <div className="text-xs text-muted-foreground">
              Score: {analysis.sentiment_score.toFixed(2)}
            </div>
          </div>
        )}

        {/* Key Concerns Section */}
        {analysis.key_concerns && analysis.key_concerns.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium">
              <AlertTriangle className="h-4 w-4 text-orange-600" />
              Preocupações Identificadas
            </div>
            <ul className="space-y-1">
              {analysis.key_concerns.map((concern, index) => (
                <li key={index} className="text-sm text-muted-foreground flex items-start gap-2">
                  <span className="text-orange-600 mt-0.5">•</span>
                  <span>{concern}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Recommendations Section */}
        {analysis.recommendations && analysis.recommendations.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Lightbulb className="h-4 w-4 text-blue-600" />
              Recomendações
            </div>
            <ul className="space-y-1">
              {analysis.recommendations.map((recommendation, index) => (
                <li key={index} className="text-sm text-muted-foreground flex items-start gap-2">
                  <span className="text-blue-600 mt-0.5">•</span>
                  <span>{recommendation}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Response Summary */}
        <div className="pt-4 border-t space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Total de Respostas</span>
            <span className="font-semibold">{analysis.total_responses}</span>
          </div>
          {analysis.flagged_responses > 0 && (
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Respostas Sinalizadas</span>
              <Badge variant="destructive">{analysis.flagged_responses}</Badge>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

