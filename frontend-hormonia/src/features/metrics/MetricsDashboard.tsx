/**
 * Real-time Metrics Dashboard for Hormonia Healthcare System
 *
 * Provides comprehensive healthcare KPI monitoring including:
 * - Patient engagement rates
 * - Quiz completion analytics
 * - AI personalization impact
 * - System performance metrics
 * - Real-time alerts and notifications
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Activity, Users, Brain, Clock, AlertTriangle, CheckCircle,
  TrendingUp, TrendingDown, Heart, MessageSquare, Target, Cpu
} from 'lucide-react';

import { EngagementChart } from './charts/EngagementChart';
import { QuizCompletionChart } from './charts/QuizCompletionChart';
import { AIPersonalizationChart } from './charts/AIPersonalizationChart';
import { SystemHealthChart } from './charts/SystemHealthChart';
import { AlertsPanel } from './AlertsPanel';
import { MetricsWebSocket } from './MetricsWebSocket';
import { createLogger } from '../../lib/logger';

import type {
  MetricsSummary,
  RealTimeMetrics,
  MetricsAlert as AlertType
} from '@/types/metrics';

const logger = createLogger('metrics:dashboard');

interface MetricsDashboardProps {
  userRole: 'doctor' | 'admin';
  refreshInterval?: number;
}

export const MetricsDashboard: React.FC<MetricsDashboardProps> = ({
  userRole,
  refreshInterval = 5000
}) => {
  const [summary, setSummary] = useState<MetricsSummary | null>(null);
  const [realTimeMetrics, setRealTimeMetrics] = useState<RealTimeMetrics | null>(null);
  const [alerts, setAlerts] = useState<AlertType[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedTab, setSelectedTab] = useState('overview');

  // WebSocket for real-time updates
  const {
    isConnected,
    lastMessage,
    connect,
    disconnect
  } = MetricsWebSocket({
    onMessage: (data: unknown) => {
      if (data && typeof data === 'object' && 'engagement' in data) {
        setRealTimeMetrics(prev => prev ? { ...prev, ...(data as Record<string, unknown>) } : null);
      }
    }
  });

  // Fetch initial data
  const fetchSummary = useCallback(async () => {
    try {
      const response = await fetch('/api/v2/metrics/summary', {
        credentials: 'include' // Use httpOnly cookies
      });

      if (!response.ok) {
        throw new Error('Failed to fetch metrics summary');
      }

      const data = await response.json();
      setSummary(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error occurred');
    }
  }, []);

  const fetchRealTimeMetrics = useCallback(async () => {
    try {
      const response = await fetch('/api/v2/metrics/realtime', {
        credentials: 'include' // Use httpOnly cookies
      });

      if (!response.ok) {
        throw new Error('Failed to fetch real-time metrics');
      }

      const data = await response.json();
      setRealTimeMetrics(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error occurred');
    }
  }, []);

  const fetchAlerts = useCallback(async () => {
    try {
      const response = await fetch('/api/v2/metrics/alerts', {
        credentials: 'include' // Use httpOnly cookies
      });

      if (!response.ok) {
        throw new Error('Failed to fetch alerts');
      }

      const data = await response.json();
      setAlerts(data.alerts || []);
    } catch (err) {
      logger.error('Failed to fetch alerts', { error: err });
    }
  }, []);

  // Initialize dashboard
  useEffect(() => {
    const initializeDashboard = async () => {
      setIsLoading(true);
      try {
        await Promise.all([
          fetchSummary(),
          fetchRealTimeMetrics(),
          fetchAlerts()
        ]);
      } finally {
        setIsLoading(false);
      }
    };

    initializeDashboard();

    // Set up periodic refresh for non-WebSocket data
    const interval = setInterval(() => {
      fetchSummary();
      fetchAlerts();
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [fetchSummary, fetchRealTimeMetrics, fetchAlerts, refreshInterval]);

  // Connect to WebSocket for real-time updates
  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  const acknowledgeAlert = async (alertId: string) => {
    try {
      const response = await fetch(`/api/v2/metrics/alerts/${alertId}/acknowledge`, {
        method: 'POST',
        credentials: 'include', // Use httpOnly cookies
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        setAlerts(prev => prev.filter(alert => alert.id !== alertId));
      }
    } catch (err) {
      logger.error('Failed to acknowledge alert', { alertId, error: err });
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'bg-red-100 text-red-800';
      case 'high': return 'bg-orange-100 text-orange-800';
      case 'medium': return 'bg-yellow-100 text-yellow-800';
      case 'low': return 'bg-blue-100 text-blue-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const formatValue = (value: number, type: 'percentage' | 'number' | 'time' = 'number') => {
    switch (type) {
      case 'percentage':
        return `${value.toFixed(1)}%`;
      case 'time':
        return `${value.toFixed(1)}h`;
      default:
        return value.toLocaleString();
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex items-center space-x-2">
          <Activity className="w-5 h-5 animate-spin" />
          <span>Carregando métricas...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>
          Erro ao carregar métricas: {error}
          <Button
            variant="outline"
            size="sm"
            className="ml-2"
            onClick={() => window.location.reload()}
          >
            Tentar Novamente
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard de Métricas</h1>
          <p className="text-muted-foreground">
            Monitoramento em tempo real do sistema Hormonia
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <Badge
            variant={isConnected ? 'default' : 'destructive'}
            className={isConnected ? 'bg-green-100 text-green-800 border-green-300' : ''}
          >
            {isConnected ? 'Conectado' : 'Desconectado'}
          </Badge>
          {summary && (
            <Badge variant="outline">
              Atualizado: {new Date(summary.timestamp).toLocaleTimeString()}
            </Badge>
          )}
        </div>
      </div>

      {/* Critical Alerts */}
      {alerts.filter(alert => alert.severity === 'critical').length > 0 && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            {alerts.filter(alert => alert.severity === 'critical').length} alertas críticos
            requerem atenção imediata
          </AlertDescription>
        </Alert>
      )}

      {/* Key Performance Indicators */}
      {summary && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Taxa de Engajamento</CardTitle>
              <Heart className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">
                {formatValue(summary.engagement_rate, 'percentage')}
              </div>
              <p className="text-xs text-muted-foreground">
                {summary.active_patients} pacientes ativos
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Conclusão de Quizzes</CardTitle>
              <Target className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-blue-600">
                {formatValue(summary.quiz_completion_rate, 'percentage')}
              </div>
              <p className="text-xs text-muted-foreground">
                Últimos 30 dias
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">IA Personalizada</CardTitle>
              <Brain className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-purple-600">
                {formatValue(summary.ai_personalization_impact, 'percentage')}
              </div>
              <p className="text-xs text-muted-foreground">
                Impacto na comunicação
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Saúde do Sistema</CardTitle>
              <Cpu className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-emerald-600">
                {formatValue(summary.system_health_score, 'percentage')}
              </div>
              <p className="text-xs text-muted-foreground">
                {summary.daily_messages} mensagens hoje
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Detailed Metrics Tabs */}
      <Tabs value={selectedTab} onValueChange={setSelectedTab} className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Visão Geral</TabsTrigger>
          <TabsTrigger value="engagement">Engajamento</TabsTrigger>
          <TabsTrigger value="quizzes">Quizzes</TabsTrigger>
          <TabsTrigger value="ai">IA & Personalização</TabsTrigger>
          <TabsTrigger value="system">Sistema</TabsTrigger>
          <TabsTrigger value="alerts">
            Alertas
            {alerts.length > 0 && (
              <Badge variant="destructive" className="ml-2">
                {alerts.length}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            {realTimeMetrics && (
              <>
                <Card>
                  <CardHeader>
                    <CardTitle>Engajamento dos Pacientes</CardTitle>
                    <CardDescription>Atividade e resposta dos pacientes</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <EngagementChart data={realTimeMetrics.engagement} />
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Performance dos Quizzes</CardTitle>
                    <CardDescription>Taxa de conclusão e tempo médio</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <QuizCompletionChart data={realTimeMetrics.quiz} />
                  </CardContent>
                </Card>
              </>
            )}
          </div>
        </TabsContent>

        <TabsContent value="engagement" className="space-y-4">
          {realTimeMetrics && (
            <Card>
              <CardHeader>
                <CardTitle>Análise Detalhada de Engajamento</CardTitle>
                <CardDescription>
                  Métricas completas de engajamento dos pacientes
                </CardDescription>
              </CardHeader>
              <CardContent>
                <EngagementChart
                  data={realTimeMetrics.engagement}
                  detailed={true}
                />

                <div className="mt-6 grid gap-4 md:grid-cols-3">
                  <div className="bg-blue-50 p-4 rounded-lg">
                    <div className="text-2xl font-bold text-blue-600">
                      {realTimeMetrics.engagement.daily_active_users}
                    </div>
                    <div className="text-sm text-blue-800">Usuários Ativos Hoje</div>
                  </div>

                  <div className="bg-green-50 p-4 rounded-lg">
                    <div className="text-2xl font-bold text-green-600">
                      {formatValue(realTimeMetrics.engagement.response_rate, 'percentage')}
                    </div>
                    <div className="text-sm text-green-800">Taxa de Resposta</div>
                  </div>

                  <div className="bg-purple-50 p-4 rounded-lg">
                    <div className="text-2xl font-bold text-purple-600">
                      {formatValue(realTimeMetrics.engagement.avg_response_time_hours, 'time')}
                    </div>
                    <div className="text-sm text-purple-800">Tempo Médio de Resposta</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="quizzes" className="space-y-4">
          {realTimeMetrics && (
            <Card>
              <CardHeader>
                <CardTitle>Análise de Quizzes</CardTitle>
                <CardDescription>
                  Performance detalhada dos questionários
                </CardDescription>
              </CardHeader>
              <CardContent>
                <QuizCompletionChart
                  data={realTimeMetrics.quiz}
                  detailed={true}
                />
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="ai" className="space-y-4">
          {realTimeMetrics && (
            <Card>
              <CardHeader>
                <CardTitle>IA e Personalização</CardTitle>
                <CardDescription>
                  Impacto da inteligência artificial na comunicação
                </CardDescription>
              </CardHeader>
              <CardContent>
                <AIPersonalizationChart
                  data={realTimeMetrics.ai_personalization}
                />

                <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                  <div className="bg-indigo-50 p-4 rounded-lg">
                    <div className="text-2xl font-bold text-indigo-600">
                      {formatValue(realTimeMetrics.ai_personalization.personalization_rate, 'percentage')}
                    </div>
                    <div className="text-sm text-indigo-800">Taxa de Personalização</div>
                  </div>

                  <div className="bg-emerald-50 p-4 rounded-lg">
                    <div className="text-2xl font-bold text-emerald-600">
                      {formatValue(realTimeMetrics.ai_personalization.response_quality_score)}
                    </div>
                    <div className="text-sm text-emerald-800">Score de Qualidade</div>
                  </div>

                  <div className="bg-orange-50 p-4 rounded-lg">
                    <div className="text-2xl font-bold text-orange-600">
                      {realTimeMetrics.ai_personalization.safety_interventions}
                    </div>
                    <div className="text-sm text-orange-800">Intervenções de Segurança</div>
                  </div>

                  <div className="bg-red-50 p-4 rounded-lg">
                    <div className="text-2xl font-bold text-red-600">
                      {formatValue(realTimeMetrics.ai_personalization.fallback_rate, 'percentage')}
                    </div>
                    <div className="text-sm text-red-800">Taxa de Fallback</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="system" className="space-y-4">
          {realTimeMetrics && userRole === 'admin' && (
            <Card>
              <CardHeader>
                <CardTitle>Saúde do Sistema</CardTitle>
                <CardDescription>
                  Métricas de performance e infraestrutura
                </CardDescription>
              </CardHeader>
              <CardContent>
                <SystemHealthChart data={realTimeMetrics.system_performance} />
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="alerts" className="space-y-4">
          <AlertsPanel
            alerts={alerts}
            onAcknowledge={acknowledgeAlert}
            userRole={userRole}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
};
