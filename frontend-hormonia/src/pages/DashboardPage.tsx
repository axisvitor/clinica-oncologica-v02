import React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Users,
  MessageSquare,
  TrendingUp,
  TriangleAlert as AlertTriangle,
  Activity,
  Clock,
  CircleCheck as CheckCircle,
  Circle as XCircle,
  Calendar,
  FileText,
  Shield,
  Settings,
} from "lucide-react";
import { apiClient } from "../lib/api-client";
import { useAuth } from "@/app/providers/AuthContext";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DashboardSkeleton } from "@/features/dashboard/DashboardSkeleton";
import { MetricCard } from "@/features/dashboard/MetricCard";
import { RecentActivity } from "@/features/dashboard/RecentActivity";
import { AlertsPanel } from "@/features/dashboard/AlertsPanel";
import { EngagementChart } from "@/features/dashboard/EngagementChart";
import QuickStats from "@/features/dashboard/QuickStats";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useRoleGuard, PermissionGate } from "@/features/auth/ProtectedRoute";
import { getRoleLabel } from "@/types/shared";
import { Link } from "react-router-dom";

export function DashboardPage() {
  const { user, isInitializing: authLoading } = useAuth();
  const { permissions, userRole, isAdmin, isDoctor } = useRoleGuard();

  // Wait for authentication to be ready before making API calls
  const {
    data: metrics,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["dashboard-metrics"],
    queryFn: () => apiClient.dashboard.getMain({ time_range: 'week' }),
    enabled: !!user && !authLoading, // Only run when authenticated
    refetchInterval: 60000, // Refresh every 60 seconds (optimized from 30s)
    staleTime: 30000, // Consider data fresh for 30 seconds
  });

  // Show skeleton while loading - UI appears immediately!
  if (isLoading) {
    return <DashboardSkeleton />;
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6">
            <div className="text-center">
              <XCircle className="mx-auto h-12 w-12 text-red-500 mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">Erro ao carregar dashboard</h3>
              <p className="text-gray-500 mb-4">
                Não foi possível carregar as métricas do dashboard.
              </p>
              <Button onClick={() => window.location.reload()}>Tentar novamente</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4 md:space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl md:text-3xl font-bold font-heading text-gray-900">Dashboard</h1>
            <Badge variant={isAdmin ? "default" : "secondary"} className="hidden sm:inline-flex">
              {getRoleLabel(userRole)}
            </Badge>
          </div>
          <p className="text-sm md:text-base text-gray-600 mt-1 font-body">
            {isAdmin ? "Visão administrativa completa" : "Visão geral do sistema"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="bg-green-50 text-green-700">
            Sistema Online
          </Badge>
          <PermissionGate permission="canAccessAdmin">
            <Button variant="outline" size="sm" asChild className="hidden sm:flex">
              <Link to="/admin">
                <Shield className="mr-2 h-4 w-4" />
                Admin
              </Link>
            </Button>
          </PermissionGate>
          <Button variant="outline" size="sm" className="hidden sm:flex">
            <Calendar className="mr-2 h-4 w-4" />
            Hoje
          </Button>
        </div>
      </div>

      {/* Admin Quick Actions */}
      <PermissionGate permission="canAccessAdmin">
        <Card className="bg-gradient-to-r from-purple-50 to-blue-50 border-purple-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <Shield className="h-5 w-5 text-purple-600" />
              Ações Administrativas
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" asChild>
                <Link to="/admin/users">
                  <Users className="mr-2 h-4 w-4" />
                  Gerenciar Usuários
                </Link>
              </Button>
              <Button variant="outline" size="sm" asChild>
                <Link to="/settings">
                  <Settings className="mr-2 h-4 w-4" />
                  Configurações
                </Link>
              </Button>
              <Button variant="outline" size="sm" asChild>
                <Link to="/flows">
                  <Activity className="mr-2 h-4 w-4" />
                  Configurar Flows
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </PermissionGate>

      {/* Doctor Info Card */}
      <PermissionGate permission="canManagePatients" fallback={null}>
        {isDoctor && (
          <Card className="bg-gradient-to-r from-green-50 to-teal-50 border-green-200">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg">👨‍⚕️ Painel Médico</CardTitle>
              <CardDescription>Acesso às suas responsabilidades clínicas</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-gray-600">Pacientes</p>
                  <p className="font-semibold text-green-700">✓ Gerenciar</p>
                </div>
                <div>
                  <p className="text-gray-600">Relatórios</p>
                  <p className="font-semibold text-green-700">✓ Visualizar</p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </PermissionGate>

      {/* Quick Stats */}
      <QuickStats />

      {/* Main Content Tabs */}
      <Tabs defaultValue="overview" className="space-y-4 md:space-y-6">
        <TabsList className="flex overflow-x-auto md:grid md:grid-cols-4 gap-1 scrollbar-hide">
          <TabsTrigger value="overview" className="text-xs sm:text-sm">
            Visão Geral
          </TabsTrigger>
          <TabsTrigger value="patients" className="text-xs sm:text-sm">
            Pacientes
          </TabsTrigger>
          <TabsTrigger value="engagement" className="text-xs sm:text-sm">
            Engajamento
          </TabsTrigger>
          <TabsTrigger value="alerts" className="text-xs sm:text-sm">
            Alertas
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4 md:space-y-6">
          {/* Metrics Grid - responsive from mobile to ultra-wide */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-4 2xl:grid-cols-4 gap-4 md:gap-6 xl:gap-8">
            <MetricCard
              title="Total de Pacientes"
              value={metrics?.total_patients || 0}
              change={metrics?.patients_change || 0}
              icon={Users}
              trend="up"
            />
            <MetricCard
              title="Mensagens Enviadas"
              value={metrics?.messages_sent || 0}
              change={metrics?.messages_change || 0}
              icon={MessageSquare}
              trend="up"
            />
            <MetricCard
              title="Taxa de Resposta"
              value={`${metrics?.response_rate || 0}%`}
              change={metrics?.response_rate_change || 0}
              icon={TrendingUp}
              trend="up"
            />
            <MetricCard
              title="Alertas Ativos"
              value={metrics?.alerts_pending || 0}
              change={metrics?.alerts_change || 0}
              icon={AlertTriangle}
              trend="down"
              variant="warning"
            />
          </div>

          {/* Charts and Activity - side by side on large screens */}
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-2 2xl:grid-cols-2 gap-4 md:gap-6 xl:gap-8">
            <EngagementChart data={metrics?.engagement_chart || []} />
            <RecentActivity activities={metrics?.recent_activity || []} />
          </div>
        </TabsContent>

        <TabsContent value="patients" className="space-y-4 md:space-y-6 xl:space-y-8">
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-3 2xl:grid-cols-4 gap-4 md:gap-6 xl:gap-8">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Pacientes Ativos</CardTitle>
                <Activity className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold font-mono tabular-nums">
                  {metrics?.active_patients || 0}
                </div>
                <p className="text-xs text-muted-foreground font-body">
                  {metrics?.active_patients_percentage || 0}% do total
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Questionários Completados</CardTitle>
                <CheckCircle className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold font-mono tabular-nums">
                  {metrics?.completed_quizzes || 0}
                </div>
                <p className="text-xs text-muted-foreground font-body">
                  +{metrics?.quizzes_change || 0} esta semana
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Tempo Médio de Resposta</CardTitle>
                <Clock className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold font-mono tabular-nums">
                  {metrics?.avg_response_time || 0}min
                </div>
                <p className="text-xs text-muted-foreground font-body">Média dos últimos 7 dias</p>
              </CardContent>
            </Card>
          </div>

          {/* Patient Status Distribution */}
          <Card>
            <CardHeader>
              <CardTitle>Distribuição de Status dos Pacientes</CardTitle>
              <CardDescription>Visão geral do status atual dos pacientes</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-4 gap-4 xl:gap-6">
                <div className="text-center p-4 border rounded-lg">
                  <div className="text-2xl font-bold font-mono tabular-nums text-green-600">
                    {metrics?.flow_breakdown?.active || 0}
                  </div>
                  <p className="text-sm text-gray-600 font-body">Ativos</p>
                </div>
                <div className="text-center p-4 border rounded-lg">
                  <div className="text-2xl font-bold font-mono tabular-nums text-yellow-600">
                    {metrics?.flow_breakdown?.paused || 0}
                  </div>
                  <p className="text-sm text-gray-600 font-body">Pausados</p>
                </div>
                <div className="text-center p-4 border rounded-lg">
                  <div className="text-2xl font-bold font-mono tabular-nums text-blue-600">
                    {metrics?.flow_breakdown?.completed || 0}
                  </div>
                  <p className="text-sm text-gray-600 font-body">Concluídos</p>
                </div>
                <div className="text-center p-4 border rounded-lg">
                  <div className="text-2xl font-bold font-mono tabular-nums text-gray-600">
                    {(metrics?.total_patients || 0) - (metrics?.flow_breakdown?.active || 0) - (metrics?.flow_breakdown?.paused || 0) - (metrics?.flow_breakdown?.completed || 0)}
                  </div>
                  <p className="text-sm text-gray-600 font-body">Inativos</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="engagement" className="space-y-6 xl:space-y-8">
          <EngagementChart data={metrics?.engagement_chart || []} />

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-2 gap-6 xl:gap-8">
            <Card>
              <CardHeader>
                <CardTitle>Métricas de Engajamento</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600 font-body">Taxa de resposta média</span>
                  <span className="font-medium font-mono tabular-nums">
                    {metrics?.response_rate || 0}%
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600 font-body">Mensagens enviadas (7d)</span>
                  <span className="font-medium font-mono tabular-nums">
                    {metrics?.messages_sent || 0}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600 font-body">Tempo médio de resposta</span>
                  <span className="font-medium font-mono tabular-nums">
                    {metrics?.avg_response_time || 0}min
                  </span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Questionários</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600 font-body">Completados esta semana</span>
                  <span className="font-medium font-mono tabular-nums">
                    {metrics?.completed_quizzes || 0}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600 font-body">Em andamento</span>
                  <span className="font-medium font-mono tabular-nums">5</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600 font-body">Taxa de conclusão</span>
                  <span className="font-medium font-mono tabular-nums">85%</span>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="alerts" className="space-y-6 xl:space-y-8">
          <AlertsPanel alerts={metrics?.recent_alerts || []} />

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-3 gap-6 xl:gap-8">
            <Card>
              <CardHeader>
                <CardTitle>Alertas por Severidade</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Críticos</span>
                  <Badge variant="destructive">{metrics?.alert_breakdown?.critical || 0}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Altos</span>
                  <Badge className="bg-orange-100 text-orange-800">{metrics?.alert_breakdown?.high || 0}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Médios</span>
                  <Badge className="bg-yellow-100 text-yellow-800">{metrics?.alert_breakdown?.medium || 0}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Baixos</span>
                  <Badge className="bg-blue-100 text-blue-800">{metrics?.alert_breakdown?.low || 0}</Badge>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Alertas por Tipo</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Médicos</span>
                  <span className="font-medium">15</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Engajamento</span>
                  <span className="font-medium">8</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Sistema</span>
                  <span className="font-medium">4</span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Performance</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600 font-body">Tempo médio de resolução</span>
                  <span className="font-medium font-mono tabular-nums">2.5h</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600 font-body">Taxa de resolução</span>
                  <span className="font-medium font-mono tabular-nums">92%</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600 font-body">Alertas resolvidos hoje</span>
                  <span className="font-medium font-mono tabular-nums">18</span>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
