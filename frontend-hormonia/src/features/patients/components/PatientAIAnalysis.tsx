import React from 'react'
import { Brain, AlertTriangle, TrendingUp, Lightbulb } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { AIAnalyticsDashboard } from '@/features/ai/AIAnalyticsDashboard'
import { AIChatInterface } from '@/features/ai/AIChatInterface'
import { Tabs, TabsContent } from '@/components/ui/tabs'

interface PatientAIAnalysisProps {
  patientId: string
  patientName: string
  aiInsightsData: any
  aiRecommendations: any
}

export function PatientAIAnalysis({
  patientId,
  patientName,
  aiInsightsData,
  aiRecommendations
}: PatientAIAnalysisProps) {
  return (
    <>
      <TabsContent value="ai-insights" className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Brain className="h-5 w-5" />
              Análise de IA - {patientName}
            </CardTitle>
            <CardDescription>
              Insights, recomendações e análise de sentimento baseados em dados do paciente
            </CardDescription>
          </CardHeader>
          <CardContent>
            {patientId && (
              <AIAnalyticsDashboard
                patientId={patientId}
                timeframe="week"
                className="mt-4"
              />
            )}
          </CardContent>
        </Card>

        {/* Legacy AI Insights */}
        {(aiInsightsData || aiRecommendations) && (
          <Card>
            <CardHeader>
              <CardTitle>Resumo Rápido</CardTitle>
              <CardDescription>Visão geral dos principais indicadores</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Risk Assessment */}
              {aiInsightsData?.risk_level && (
                <div className={`border-l-4 p-4 rounded-r-lg ${aiInsightsData.risk_level === 'critical' ? 'border-red-500 bg-red-50' :
                  aiInsightsData.risk_level === 'high' ? 'border-orange-500 bg-orange-50' :
                    aiInsightsData.risk_level === 'medium' ? 'border-yellow-500 bg-yellow-50' :
                      'border-green-500 bg-green-50'
                  }`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="h-5 w-5" />
                      <span className="font-medium">Nível de Risco:</span>
                    </div>
                    <Badge className={`${aiInsightsData.risk_level === 'critical' ? 'bg-red-500' :
                      aiInsightsData.risk_level === 'high' ? 'bg-orange-500' :
                        aiInsightsData.risk_level === 'medium' ? 'bg-yellow-500' :
                          'bg-green-500'
                      } text-white`}>
                      {aiInsightsData.risk_level === 'critical' ? 'Crítico' :
                        aiInsightsData.risk_level === 'high' ? 'Alto' :
                          aiInsightsData.risk_level === 'medium' ? 'Médio' : 'Baixo'}
                    </Badge>
                  </div>
                  {aiInsightsData.risk_factors && aiInsightsData.risk_factors.length > 0 && (
                    <div className="mt-3">
                      <p className="text-sm font-medium mb-2">Fatores:</p>
                      <div className="flex flex-wrap gap-2">
                        {aiInsightsData.risk_factors.map((factor: string, idx: number) => (
                          <Badge key={idx} variant="outline">{factor}</Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Sentiment Score */}
              {aiInsightsData?.sentiment_score !== undefined && (
                <div className="p-4 border rounded-lg">
                  <div className="flex items-center gap-2 mb-3">
                    <TrendingUp className="h-5 w-5" />
                    <span className="font-medium">Score de Sentimento</span>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">
                        {aiInsightsData.sentiment_score >= 0.7 ? 'Positivo' :
                          aiInsightsData.sentiment_score >= 0.4 ? 'Neutro' : 'Negativo'}
                      </span>
                      <span className="text-sm font-bold">{(aiInsightsData.sentiment_score * 100).toFixed(0)}%</span>
                    </div>
                    <Progress value={aiInsightsData.sentiment_score * 100} />
                  </div>
                </div>
              )}

              {/* Top Recommendations */}
              {(aiRecommendations?.length ?? 0) > 0 && (
                <div className="p-4 border rounded-lg">
                  <div className="flex items-center gap-2 mb-3">
                    <Lightbulb className="h-5 w-5" />
                    <span className="font-medium">Principais Recomendações</span>
                  </div>
                  <div className="space-y-2">
                    {(Array.isArray(aiRecommendations) ? aiRecommendations : aiRecommendations?.recommendations || []).slice(0, 3).map((rec: { id?: string; title?: string; description?: string; priority: string }) => (
                      <div key={rec.id} className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">{rec.title}</span>
                        <Badge variant={rec.priority === 'high' ? 'destructive' : 'secondary'} className="text-xs">
                          {rec.priority}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </TabsContent>

      <TabsContent value="ai-chat" className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Brain className="h-5 w-5" />
              Chat com IA - Contexto do Paciente
            </CardTitle>
            <CardDescription>
              Tire dúvidas e obtenha insights sobre {patientName}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {patientId && <AIChatInterface patientId={patientId} />}
          </CardContent>
        </Card>
      </TabsContent>
    </>
  )
}
