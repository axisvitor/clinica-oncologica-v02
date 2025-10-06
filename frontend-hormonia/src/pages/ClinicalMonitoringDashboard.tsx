import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from 'recharts';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Activity,
  AlertTriangle,
  Heart,
  MessageSquare,
  TrendingUp,
  TrendingDown,
  Users,
  Brain,
  ClipboardCheck,
  Calendar,
  RefreshCw,
} from 'lucide-react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { format, subDays } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { createLogger } from '../lib/logger';
import { useClinicalMetrics } from '@/hooks/api/useClinicalMetrics';
import { useRiskPatients } from '@/hooks/api/useRiskPatients';
import { useAdherenceData } from '@/hooks/api/useAdherenceData';
import { useQueryClient } from '@tanstack/react-query';

const logger = createLogger('ClinicalMonitoringDashboard');

// Tipos para métricas clínicas
interface ClinicalMetrics {
  patientEngagement: number;
  quizCompletion: number;
  messageResponseRate: number;
  averageSentiment: number;
  riskPatients: number;
  totalPatients: number;
  activeFlows: number;
  completedFlows: number;
}

// Tipos para mensagens WebSocket
interface ClinicalWebSocketMessage {
  type: 'metrics_update' | 'risk_alert';
  data: {
    metrics?: ClinicalMetrics;
    alert?: any;
  };
  timestamp: string;
}

// Tipos para respostas da API
interface ApiResponse<T> {
  data: T;
  message?: string;
  timestamp: string;
}

interface PatientRisk {
  id: string;
  name: string;
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
  lastInteraction: string;
  sentiment: number;
  adherence: number;
  alerts: string[];
}

interface TreatmentAdherence {
  day: string;
  adherence: number;
  responses: number;
  sentiment: number;
}

const ClinicalMonitoringDashboard: React.FC = () => {
  const [selectedTimeRange, setSelectedTimeRange] = useState<'7d' | '30d' | '90d'>('7d');
  const [refreshing, setRefreshing] = useState(false);
  const queryClient = useQueryClient();

  // React Query hooks for data fetching
  const {
    data: metrics,
    isLoading: isLoadingMetrics,
    error: metricsError,
    refetch: refetchMetrics
  } = useClinicalMetrics({
    timeRange: selectedTimeRange,
    refetchInterval: 30000
  });

  const {
    data: riskPatients = [],
    isLoading: isLoadingRisk,
    refetch: refetchRisk
  } = useRiskPatients();

  const {
    data: adherenceData = [],
    isLoading: isLoadingAdherence,
    refetch: refetchAdherence
  } = useAdherenceData({
    days: parseInt(selectedTimeRange.replace('d', ''))
  });

  const isLoading = isLoadingMetrics || isLoadingRisk || isLoadingAdherence;

  // WebSocket para atualizações em tempo real
  const { lastMessage: wsData } = useWebSocket({ url: '/clinical-metrics' });

  // Atualizar com dados do WebSocket
  useEffect(() => {
    if (wsData?.type === 'metrics_update') {
      queryClient.invalidateQueries({ queryKey: ['clinical', 'metrics'] });
    }
    if (wsData?.type === 'risk_alert') {
      queryClient.invalidateQueries({ queryKey: ['clinical', 'risk-patients'] });
    }
  }, [wsData, queryClient]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await Promise.all([
      refetchMetrics(),
      refetchRisk(),
      refetchAdherence()
    ]);
    setRefreshing(false);
  };

  // Dados para gráficos (PLACEHOLDER - aguardando integração com API real)
  const sentimentDistribution = [
    { name: 'Positivo', value: 45, color: '#10b981' },
    { name: 'Neutro', value: 35, color: '#6b7280' },
    { name: 'Negativo', value: 20, color: '#ef4444' },
  ];

  const riskDistribution = [
    { name: 'Baixo', value: riskPatients.filter(p => p.riskLevel === 'low').length },
    { name: 'Médio', value: riskPatients.filter(p => p.riskLevel === 'medium').length },
    { name: 'Alto', value: riskPatients.filter(p => p.riskLevel === 'high').length },
    { name: 'Crítico', value: riskPatients.filter(p => p.riskLevel === 'critical').length },
  ];

  const getRiskColor = (level: string) => {
    switch (level) {
      case 'low': return '#10b981';
      case 'medium': return '#f59e0b';
      case 'high': return '#ef4444';
      case 'critical': return '#7c3aed';
      default: return '#6b7280';
    }
  };

  const formatPercentage = (value: number) => `${(value * 100).toFixed(1)}%`;

  // Loading state with skeleton
  if (isLoading && !metrics) {
    return (
      <div className="p-6 space-y-6">
        <Skeleton className="h-12 w-96" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-32" />)}
        </div>
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  // Error state
  if (metricsError) {
    return (
      <div className="p-6 space-y-6">
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Erro ao carregar métricas clínicas</AlertTitle>
          <AlertDescription>
            Não foi possível carregar as métricas. Tente novamente.
            <Button onClick={() => refetchMetrics()} variant="outline" size="sm" className="ml-2">
              Tentar novamente
            </Button>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  // Ensure metrics is defined before rendering
  if (!metrics) {
    return null;
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Monitoramento Clínico</h1>
          <p className="text-gray-500">Acompanhamento em tempo real do engajamento e bem-estar dos pacientes</p>
        </div>
        <div className="flex gap-2">
          <select
            className="px-4 py-2 border rounded-lg"
            value={selectedTimeRange}
            onChange={(e) => setSelectedTimeRange(e.target.value as '7d' | '30d' | '90d')}
          >
            <option value="7d">Últimos 7 dias</option>
            <option value="30d">Últimos 30 dias</option>
            <option value="90d">Últimos 90 dias</option>
          </select>
          <Button
            onClick={handleRefresh}
            disabled={refreshing}
            variant="outline"
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
            Atualizar
          </Button>
        </div>
      </div>

      {/* KPIs Principais */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Engajamento</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatPercentage(metrics.patientEngagement)}</div>
            <Progress value={metrics.patientEngagement * 100} className="mt-2" />
            <p className="text-xs text-muted-foreground mt-2">
              Meta: 60% • {metrics.patientEngagement >= 0.6 ? '✅ Atingida' : '⚠️ Abaixo'}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Quiz Mensal</CardTitle>
            <ClipboardCheck className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatPercentage(metrics.quizCompletion)}</div>
            <Progress value={metrics.quizCompletion * 100} className="mt-2" />
            <p className="text-xs text-muted-foreground mt-2">
              Meta: 70% • {metrics.quizCompletion >= 0.7 ? '✅ Atingida' : '⚠️ Melhorar'}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Sentimento Médio</CardTitle>
            <Brain className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold flex items-center">
              {metrics.averageSentiment.toFixed(2)}
              {metrics.averageSentiment > 0 ? (
                <TrendingUp className="h-4 w-4 ml-2 text-green-500" />
              ) : (
                <TrendingDown className="h-4 w-4 ml-2 text-red-500" />
              )}
            </div>
            <div className="mt-2">
              <Badge
                variant="outline"
                className={metrics.averageSentiment > 0.3 ? 'bg-green-100 text-green-800 border-green-300' : 'bg-yellow-100 text-yellow-800 border-yellow-300'}
              >
                {metrics.averageSentiment > 0.3 ? 'Positivo' : 'Atenção'}
              </Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Pacientes em Risco</CardTitle>
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.riskPatients}</div>
            <p className="text-xs text-muted-foreground mt-2">
              De {metrics.totalPatients} pacientes totais
            </p>
            {metrics.riskPatients > 0 && (
              <Badge variant="destructive" className="mt-2">
                Requer Atenção
              </Badge>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Tabs com Análises Detalhadas */}
      <Tabs defaultValue="adherence" className="space-y-4">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="adherence">Aderência</TabsTrigger>
          <TabsTrigger value="sentiment">Sentimento</TabsTrigger>
          <TabsTrigger value="risk">Risco</TabsTrigger>
          <TabsTrigger value="engagement">Engajamento</TabsTrigger>
        </TabsList>

        {/* Tab: Aderência ao Tratamento */}
        <TabsContent value="adherence">
          <Card>
            <CardHeader>
              <CardTitle>Aderência ao Tratamento</CardTitle>
              <CardDescription>
                Evolução da aderência e resposta dos pacientes ao longo do tempo
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={adherenceData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="day" />
                  <YAxis yAxisId="left" />
                  <YAxis yAxisId="right" orientation="right" />
                  <Tooltip />
                  <Legend />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="adherence"
                    stroke="#10b981"
                    name="Aderência (%)"
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="responses"
                    stroke="#3b82f6"
                    name="Respostas"
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab: Análise de Sentimento */}
        <TabsContent value="sentiment">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Distribuição de Sentimento</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={sentimentDistribution}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, value }) => `${name}: ${value}%`}
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {sentimentDistribution.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Tendência de Sentimento</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={adherenceData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="day" />
                    <YAxis />
                    <Tooltip />
                    <Line
                      type="monotone"
                      dataKey="sentiment"
                      stroke="#8b5cf6"
                      name="Sentimento"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Tab: Pacientes em Risco */}
        <TabsContent value="risk">
          <Card>
            <CardHeader>
              <CardTitle>Pacientes Requerendo Atenção</CardTitle>
              <CardDescription>
                Lista de pacientes com indicadores de risco elevado
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {riskPatients.map((patient) => (
                  <Alert key={patient.id} variant={patient.riskLevel === 'critical' ? 'destructive' : 'default'}>
                    <AlertTriangle className="h-4 w-4" />
                    <AlertTitle className="flex justify-between">
                      <span>{patient.name}</span>
                      <Badge style={{ backgroundColor: getRiskColor(patient.riskLevel) }}>
                        Risco {patient.riskLevel.toUpperCase()}
                      </Badge>
                    </AlertTitle>
                    <AlertDescription>
                      <div className="mt-2 space-y-1 text-sm">
                        <p>Última interação: {patient.lastInteraction}</p>
                        <p>Aderência: {formatPercentage(patient.adherence)}</p>
                        <p>Sentimento: {patient.sentiment.toFixed(2)}</p>
                        {patient.alerts.length > 0 && (
                          <div className="mt-2">
                            <p className="font-medium">Alertas:</p>
                            <ul className="list-disc list-inside">
                              {patient.alerts.map((alert, i) => (
                                <li key={i}>{alert}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                      <Button size="sm" className="mt-3">
                        <MessageSquare className="h-4 w-4 mr-2" />
                        Contactar Paciente
                      </Button>
                    </AlertDescription>
                  </Alert>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab: Engajamento Detalhado */}
        <TabsContent value="engagement">
          <Card>
            <CardHeader>
              <CardTitle>Métricas de Engajamento</CardTitle>
              <CardDescription>
                Análise detalhada do engajamento por tipo de interação
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={400}>
                {/* PLACEHOLDER - Aguardando integração com useAdherenceData */}
                <RadarChart data={[
                  { metric: 'Mensagens', value: 75 },
                  { metric: 'Quiz', value: 65 },
                  { metric: 'Check-ins', value: 80 },
                  { metric: 'Consultas', value: 90 },
                  { metric: 'Feedback', value: 55 },
                  { metric: 'App Usage', value: 70 },
                ]}>
                  <PolarGrid />
                  <PolarAngleAxis dataKey="metric" />
                  <PolarRadiusAxis angle={90} domain={[0, 100]} />
                  <Radar name="Engajamento" dataKey="value" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.6} />
                </RadarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Alertas e Recomendações */}
      <Card>
        <CardHeader>
          <CardTitle>Recomendações Clínicas</CardTitle>
          <CardDescription>
            Sugestões baseadas na análise dos dados
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {metrics.patientEngagement < 0.5 && (
              <Alert>
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Engajamento Baixo</AlertTitle>
                <AlertDescription>
                  Considere revisar o conteúdo das mensagens ou aumentar a frequência de check-ins motivacionais.
                </AlertDescription>
              </Alert>
            )}

            {metrics.quizCompletion < 0.6 && (
              <Alert>
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Baixa Conclusão de Questionários</AlertTitle>
                <AlertDescription>
                  Simplifique os questionários ou envie lembretes adicionais para aumentar a taxa de conclusão.
                </AlertDescription>
              </Alert>
            )}

            {metrics.riskPatients > 5 && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Múltiplos Pacientes em Risco</AlertTitle>
                <AlertDescription>
                  {metrics.riskPatients} pacientes requerem atenção imediata. Priorize contato direto.
                </AlertDescription>
              </Alert>
            )}

            {metrics.averageSentiment > 0.3 && (
              <Alert variant="default" className="border-green-500">
                <Heart className="h-4 w-4" />
                <AlertTitle>Sentimento Positivo</AlertTitle>
                <AlertDescription>
                  O sentimento geral está positivo. Continue com a estratégia atual de comunicação.
                </AlertDescription>
              </Alert>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default ClinicalMonitoringDashboard;