import React, { useState, useMemo, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Activity, TriangleAlert as AlertTriangle, TrendingUp, Users, Brain, MessageSquare, Calendar, Search, Download, ListFilter as Filter, RefreshCw, FileText, Lightbulb, Clock, X } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { PatientRiskCard } from '@/components/ai/PatientRiskCard'
import { AIAnalyticsDashboard } from '@/components/ai/AIAnalyticsDashboard'
import { apiClient } from '@/lib/api-client'
import { useAuth } from '@/contexts/AuthContext'
import { useDebounce } from '@/hooks/useDebounce'
import { FEATURES } from '@/config'
import type { AIInsight, AIRecommendation } from '@/lib/types/ai'
import { ChatRole } from '../../types/api'
import { createLogger } from '@/lib/logger'

const logger = createLogger('PhysicianDashboard')

interface DashboardMetrics {
  total_patients: number
  active_conversations: number
  high_risk_patients: number
  avg_sentiment: number
  pending_reviews: number
}

interface PatientWithRisk {
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

interface ChatMessage {
  id: string
  role: ChatRole
  content: string
  timestamp: string
}

export default function PhysicianDashboard() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user, hasRole } = useAuth()

  // Permission check
  const canAccessDashboard = hasRole('doctor') || hasRole('admin') || hasRole('superadmin')

  // State management
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedRiskLevel, setSelectedRiskLevel] = useState<string>('all')
  const [chatOpen, setChatOpen] = useState(false)
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [chatInput, setChatInput] = useState('')
  const [exportDialogOpen, setExportDialogOpen] = useState(false)
  const [selectedPatientForChat, setSelectedPatientForChat] = useState<string | null>(null)

  const debouncedSearch = useDebounce(searchQuery, 300)

  // Fetch dashboard metrics
  const { data: metrics, isLoading: metricsLoading } = useQuery<DashboardMetrics>({
    queryKey: ['physician-dashboard-metrics'],
    queryFn: async () => {
      const response = await apiClient.analytics.dashboard()
      return response
    },
    staleTime: 60000, // 1 minute
    refetchInterval: 120000 // 2 minutes
  })

  // Fetch patients with AI risk assessment
  const { data: patientsData, isLoading: patientsLoading, refetch: refetchPatients } = useQuery({
    queryKey: ['physician-patients', debouncedSearch, selectedRiskLevel],
    queryFn: async () => {
      const params: any = { page: 1, size: 50 }
      if (debouncedSearch) params.search = debouncedSearch
      if (selectedRiskLevel !== 'all') params.risk_level = selectedRiskLevel

      const response = await apiClient.patients.list(params)

      // Enrich with AI insights if available
      if (FEATURES.AI_INSIGHTS) {
        const patientsWithRisk = await Promise.all(
          response.items.map(async (patient: any) => {
            try {
              const insights = await apiClient.ai.insights(patient.id, 'week')
              return {
                id: patient.id,
                name: patient.full_name || `${patient.first_name} ${patient.last_name}`,
                phone: patient.phone,
                treatment_type: patient.treatment_type || 'N/A',
                risk_level: insights.risk_level || 'low',
                risk_factors: insights.risk_factors || [],
                last_interaction: insights.last_interaction || patient.updated_at,
                sentiment_score: insights.sentiment_score || 0.5,
                engagement_score: insights.engagement_score || 50,
                has_alerts: insights.has_alerts || false
              }
            } catch (error) {
              logger.warn('Failed to fetch AI insights for patient', { patientId: patient.id, error });
              return {
                id: patient.id,
                name: patient.full_name || `${patient.first_name} ${patient.last_name}`,
                phone: patient.phone,
                treatment_type: patient.treatment_type || 'N/A',
                risk_level: 'low',
                risk_factors: [],
                last_interaction: patient.updated_at,
                sentiment_score: 0.5,
                engagement_score: 50,
                has_alerts: false
              }
            }
          })
        )
        return { ...response, items: patientsWithRisk }
      }

      return response
    },
    enabled: canAccessDashboard,
    staleTime: 120000 // 2 minutes
  })

  // Fetch high-risk alerts
  const { data: alerts } = useQuery({
    queryKey: ['physician-alerts'],
    queryFn: async () => {
      return apiClient.alerts.list({
        severity: 'high',
        acknowledged: false,
        size: 10
      })
    },
    enabled: canAccessDashboard,
    staleTime: 60000
  })

  // Fetch AI summary insights for all patients
  const { data: summaryInsights, isLoading: insightsLoading } = useQuery({
    queryKey: ['physician-insights-summary'],
    queryFn: async () => {
      try {
        logger.info('Fetching summary AI insights');
        const response = await apiClient.ai.insights('all', 'week')
        logger.debug('Summary insights loaded', { insightsCount: response.insights?.length });
        return response
      } catch (error) {
        logger.error('Failed to fetch summary insights', { error });
        return { insights: [], recommendations: [] }
      }
    },
    enabled: canAccessDashboard && FEATURES.AI_INSIGHTS,
    staleTime: 300000, // 5 minutes
    refetchInterval: 600000 // 10 minutes
  })

  // AI Chat mutation
  const chatMutation = useMutation({
    mutationFn: async (message: string) => {
      const response = await apiClient.ai.chat(message, {
        role: 'physician',
        patient_id: selectedPatientForChat,
        context: 'clinical_guidance'
      })
      return response
    },
    onSuccess: (data) => {
      logger.info('AI chat response received');
      setChatMessages(prev => [
        ...prev,
        {
          id: Date.now().toString(),
          role: ChatRole.ASSISTANT,
          content: data.message || data.response,
          timestamp: new Date().toISOString()
        }
      ])
    },
    onError: (error) => {
      logger.error('Chat error', { error });
      setChatMessages(prev => [
        ...prev,
        {
          id: Date.now().toString(),
          role: ChatRole.ASSISTANT,
          content: 'Desculpe, ocorreu um erro ao processar sua mensagem. Tente novamente.',
          timestamp: new Date().toISOString()
        }
      ])
    }
  })

  // Export report mutation
  const exportMutation = useMutation({
    mutationFn: async (format: 'pdf' | 'excel') => {
      const reportData = {
        patients: filteredPatients,
        insights: summaryInsights,
        riskCounts,
        generatedAt: new Date().toISOString(),
        generatedBy: user?.full_name
      }

      // Generate report file
      const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `physician-report-${new Date().toISOString().slice(0, 10)}.json`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
    },
    onSuccess: () => {
      setExportDialogOpen(false)
    }
  })

  // Calculate risk counts
  const riskCounts = useMemo(() => {
    if (!patientsData?.items) return { critical: 0, high: 0, medium: 0, low: 0 }

    return (patientsData.items as unknown as PatientWithRisk[]).reduce((acc: Record<string, number>, patient: PatientWithRisk) => {
      acc[patient.risk_level] = (acc[patient.risk_level] || 0) + 1
      return acc
    }, { critical: 0, high: 0, medium: 0, low: 0 })
  }, [patientsData?.items])

  // Handlers
  const handlePatientClick = useCallback((patientId: string) => {
    navigate(`/physician/patients/${patientId}`)
  }, [navigate])

  const handleQuickAction = useCallback((patientId: string, action: string) => {
    switch (action) {
      case 'message':
        setSelectedPatientForChat(patientId)
        setChatOpen(true)
        break
      case 'schedule':
        navigate(`/physician/patients/${patientId}?tab=appointments`)
        break
      case 'review':
        navigate(`/physician/patients/${patientId}?tab=ai-insights`)
        break
    }
  }, [navigate])

  const handleSendChat = useCallback(() => {
    if (!chatInput.trim()) return

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: ChatRole.USER,
      content: chatInput,
      timestamp: new Date().toISOString()
    }

    setChatMessages(prev => [...prev, userMessage])
    chatMutation.mutate(chatInput)
    setChatInput('')
  }, [chatInput, chatMutation])

  const handleExport = useCallback((format: 'pdf' | 'excel') => {
    exportMutation.mutate(format)
  }, [exportMutation])

  const handleRefresh = useCallback(() => {
    refetchPatients()
    queryClient.invalidateQueries({ queryKey: ['physician-insights-summary'] })
    queryClient.invalidateQueries({ queryKey: ['physician-dashboard-metrics'] })
  }, [refetchPatients, queryClient])

  // Permission denied screen
  if (!canAccessDashboard) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Card className="w-96">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-red-500">
              <AlertTriangle className="h-6 w-6" />
              Acesso Negado
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">
              Você não tem permissão para acessar o Dashboard do Médico.
              Entre em contato com o administrador do sistema.
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (metricsLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  const filteredPatients = (patientsData?.items as unknown as PatientWithRisk[] || []).filter((p: PatientWithRisk) =>
    selectedRiskLevel === 'all' || p.risk_level === selectedRiskLevel
  )

  const highRiskPatients = filteredPatients.filter((p: PatientWithRisk) =>
    p.risk_level === 'critical' || p.risk_level === 'high'
  )

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Brain className="h-8 w-8 text-primary" />
            Dashboard do Médico
          </h1>
          <p className="text-muted-foreground mt-1">
            Insights de IA e análise de risco dos pacientes
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={handleRefresh}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Atualizar
          </Button>
          <Button onClick={() => setChatOpen(true)}>
            <MessageSquare className="h-4 w-4 mr-2" />
            Chat IA
          </Button>
          <Button onClick={() => setExportDialogOpen(true)}>
            <Download className="h-4 w-4 mr-2" />
            Exportar
          </Button>
        </div>
      </div>

      {/* Risk Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="border-l-4 border-l-red-500 dark:bg-red-950/20">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center justify-between">
              <span>Crítico</span>
              <AlertTriangle className="h-4 w-4 text-red-500" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{riskCounts['critical']}</p>
            <p className="text-xs text-muted-foreground mt-1">Requer atenção imediata</p>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-orange-500 dark:bg-orange-950/20">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center justify-between">
              <span>Alto</span>
              <TrendingUp className="h-4 w-4 text-orange-500" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{riskCounts['high']}</p>
            <p className="text-xs text-muted-foreground mt-1">Monitoramento próximo</p>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-yellow-500 dark:bg-yellow-950/20">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center justify-between">
              <span>Médio</span>
              <Activity className="h-4 w-4 text-yellow-500" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{riskCounts['medium']}</p>
            <p className="text-xs text-muted-foreground mt-1">Acompanhamento regular</p>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-green-500 dark:bg-green-950/20">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center justify-between">
              <span>Baixo</span>
              <Users className="h-4 w-4 text-green-500" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{riskCounts['low']}</p>
            <p className="text-xs text-muted-foreground mt-1">Estável</p>
          </CardContent>
        </Card>
      </div>

      {/* High-Risk Alerts */}
      {alerts && alerts.items && alerts.items.length > 0 && (
        <Card className="border-destructive">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-destructive" />
              Alertas Críticos
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {alerts.items.map((alert: any) => (
                <div
                  key={alert.id}
                  className="flex items-center justify-between p-3 bg-destructive/10 rounded-lg"
                >
                  <div className="flex-1">
                    <p className="font-medium">{alert.title}</p>
                    <p className="text-sm text-muted-foreground">{alert.message}</p>
                  </div>
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => alert.patient_id && handlePatientClick(alert.patient_id)}
                  >
                    Revisar
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Main Content */}
      <Tabs defaultValue="patients" className="space-y-4">
        <TabsList>
          <TabsTrigger value="patients">Pacientes</TabsTrigger>
          <TabsTrigger value="insights">Insights IA</TabsTrigger>
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
        </TabsList>

        <TabsContent value="patients" className="space-y-4">
          {/* Search and Filters */}
          <div className="flex items-center gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Buscar pacientes..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select value={selectedRiskLevel} onValueChange={setSelectedRiskLevel}>
              <SelectTrigger className="w-48">
                <Filter className="h-4 w-4 mr-2" />
                <SelectValue placeholder="Filtrar por risco" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos os Riscos</SelectItem>
                <SelectItem value="critical">Crítico</SelectItem>
                <SelectItem value="high">Alto</SelectItem>
                <SelectItem value="medium">Médio</SelectItem>
                <SelectItem value="low">Baixo</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Patients Grid */}
          {patientsLoading ? (
            <div className="flex items-center justify-center py-12">
              <LoadingSpinner size="lg" />
              <p className="ml-3 text-muted-foreground">Carregando pacientes...</p>
            </div>
          ) : filteredPatients.length === 0 ? (
            <Card>
              <CardContent className="pt-6">
                <div className="text-center text-muted-foreground">
                  <Users className="mx-auto h-8 w-8 mb-2" />
                  <p>Nenhum paciente encontrado</p>
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredPatients.map((patient: PatientWithRisk) => (
                <PatientRiskCard
                  key={patient.id}
                  patient={patient}
                  onPatientClick={handlePatientClick}
                  onQuickAction={handleQuickAction}
                />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="insights" className="space-y-4">
          {insightsLoading ? (
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-center">
                  <LoadingSpinner size="lg" />
                  <p className="ml-3 text-muted-foreground">Carregando insights...</p>
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {/* Key Insights */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Lightbulb className="h-5 w-5" />
                    Insights Principais
                  </CardTitle>
                  <CardDescription>
                    Padrões e recomendações detectadas pela IA
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {summaryInsights?.insights?.slice(0, 5).map((insight: AIInsight) => (
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
                  {summaryInsights?.recommendations?.slice(0, 5).map((rec: AIRecommendation) => (
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
          )}
        </TabsContent>

        <TabsContent value="analytics" className="space-y-4">
          <AIAnalyticsDashboard timeframe="week" />
        </TabsContent>
      </Tabs>

      {/* AI Chat Dialog */}
      <Dialog open={chatOpen} onOpenChange={setChatOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Brain className="h-5 w-5" />
              Chat com IA - Orientação Clínica
            </DialogTitle>
            <DialogDescription>
              Obtenha insights e orientações clínicas baseadas em IA
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col h-[60vh]">
            {/* Chat Messages */}
            <div className="flex-1 overflow-y-auto space-y-3 p-4 border rounded-md mb-4">
              {chatMessages.length === 0 ? (
                <div className="text-center text-muted-foreground py-8">
                  <MessageSquare className="mx-auto h-8 w-8 mb-2" />
                  <p>Inicie uma conversa com a IA</p>
                  <p className="text-xs mt-1">Faça perguntas sobre pacientes, tratamentos ou análises</p>
                </div>
              ) : (
                chatMessages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[80%] rounded-lg p-3 ${
                        msg.role === 'user'
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted'
                      }`}
                    >
                      <p className="text-sm">{msg.content}</p>
                      <p className="text-xs opacity-70 mt-1">
                        {new Date(msg.timestamp).toLocaleTimeString('pt-BR')}
                      </p>
                    </div>
                  </div>
                ))
              )}
              {chatMutation.isPending && (
                <div className="flex justify-start">
                  <div className="bg-muted rounded-lg p-3">
                    <LoadingSpinner size="sm" />
                  </div>
                </div>
              )}
            </div>

            {/* Chat Input */}
            <div className="flex gap-2">
              <Input
                placeholder="Digite sua pergunta..."
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSendChat()}
                disabled={chatMutation.isPending}
              />
              <Button
                onClick={handleSendChat}
                disabled={!chatInput.trim() || chatMutation.isPending}
              >
                <MessageSquare className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Export Dialog */}
      <Dialog open={exportDialogOpen} onOpenChange={setExportDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Exportar Relatório
            </DialogTitle>
            <DialogDescription>
              Escolha o formato do relatório para exportação
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              O relatório incluirá todos os pacientes filtrados, insights e recomendações de IA.
            </p>
            <div className="flex gap-3">
              <Button
                className="flex-1"
                variant="outline"
                onClick={() => handleExport('pdf')}
                disabled={exportMutation.isPending}
              >
                <FileText className="h-4 w-4 mr-2" />
                PDF
              </Button>
              <Button
                className="flex-1"
                variant="outline"
                onClick={() => handleExport('excel')}
                disabled={exportMutation.isPending}
              >
                <Download className="h-4 w-4 mr-2" />
                Excel
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}