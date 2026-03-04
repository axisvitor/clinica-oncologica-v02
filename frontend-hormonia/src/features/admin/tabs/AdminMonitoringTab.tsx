import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { SystemStatus } from '@/features/monitoring/SystemStatus'
import { useSystemStats } from '@/hooks/api/useSystemStats'
import {
  Activity,
  Database,
  Users,
  Shield,
  TriangleAlert as AlertTriangle,
  CircleCheck as CheckCircle,
  Loader2,
} from 'lucide-react'

/**
 * Helper function to format uptime in human-readable format
 */
function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)

  if (days > 0) {
    return `${days}d ${hours}h`
  } else if (hours > 0) {
    return `${hours}h ${minutes}m`
  } else {
    return `${minutes}m`
  }
}

interface AdminMonitoringTabProps {
  refetchStats: () => void
}

/**
 * AdminMonitoringTab - System monitoring and metrics
 *
 * Displays real-time system metrics including:
 * - CPU, Memory, and Disk usage
 * - User statistics and activity
 * - Database metrics and connections
 * - System uptime and status
 */
export default function AdminMonitoringTab({ refetchStats }: AdminMonitoringTabProps) {
  const {
    data: stats,
    isLoading: statsLoading,
    error: statsError,
  } = useSystemStats({
    refetchInterval: 30000, // Refresh every 30s
  })

  return (
    <div className="space-y-6">
      {/* Error Alert */}
      {statsError && (
        <Alert variant="destructive" className="mb-6">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Erro ao carregar estatísticas do sistema</AlertTitle>
          <AlertDescription className="flex items-center justify-between">
            <span>{statsError instanceof Error ? statsError.message : 'Erro desconhecido'}</span>
            <Button onClick={refetchStats} variant="outline" size="sm" className="ml-4">
              Tentar Novamente
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* System Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* CPU Usage */}
        <Card className="hover:shadow-lg transition-shadow">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Uso de CPU</p>
                {statsLoading ? (
                  <Skeleton className="h-10 w-20 mt-2" />
                ) : (
                  <>
                    <p
                      className={`text-3xl font-bold mt-2 ${stats && stats.system.cpu_percent > 80 ? 'text-red-600' : ''}`}
                    >
                      {stats?.system.cpu_percent.toFixed(1)}%
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      {stats && stats.system.cpu_percent > 80 ? 'Alta utilização' : 'Normal'}
                    </p>
                  </>
                )}
              </div>
              <div
                className={`h-12 w-12 rounded-full flex items-center justify-center ${
                  stats && stats.system.cpu_percent > 80 ? 'bg-red-100' : 'bg-blue-100'
                }`}
              >
                <Activity
                  className={`h-6 w-6 ${
                    stats && stats.system.cpu_percent > 80 ? 'text-red-600' : 'text-blue-600'
                  }`}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Memory Usage */}
        <Card className="hover:shadow-lg transition-shadow">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Uso de Memória</p>
                {statsLoading ? (
                  <Skeleton className="h-10 w-20 mt-2" />
                ) : (
                  <>
                    <p
                      className={`text-3xl font-bold mt-2 ${stats && stats.system.memory_percent > 80 ? 'text-orange-600' : ''}`}
                    >
                      {stats?.system.memory_percent.toFixed(1)}%
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      {stats && stats.system.memory_percent > 80 ? 'Atenção' : 'Normal'}
                    </p>
                  </>
                )}
              </div>
              <div
                className={`h-12 w-12 rounded-full flex items-center justify-center ${
                  stats && stats.system.memory_percent > 80 ? 'bg-orange-100' : 'bg-green-100'
                }`}
              >
                <Activity
                  className={`h-6 w-6 ${
                    stats && stats.system.memory_percent > 80 ? 'text-orange-600' : 'text-green-600'
                  }`}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Disk Usage */}
        <Card className="hover:shadow-lg transition-shadow">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Uso de Disco</p>
                {statsLoading ? (
                  <Skeleton className="h-10 w-20 mt-2" />
                ) : (
                  <>
                    <p className="text-3xl font-bold mt-2">
                      {stats?.system.disk_percent.toFixed(1)}%
                    </p>
                    <p className="text-xs text-gray-500 mt-1">Armazenamento</p>
                  </>
                )}
              </div>
              <div className="h-12 w-12 rounded-full bg-purple-100 flex items-center justify-center">
                <Database className="h-6 w-6 text-purple-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* System Uptime */}
        <Card className="hover:shadow-lg transition-shadow">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Tempo de Atividade</p>
                {statsLoading ? (
                  <Skeleton className="h-10 w-20 mt-2" />
                ) : (
                  <>
                    <p className="text-3xl font-bold mt-2">
                      {stats ? formatUptime(stats.system.uptime_seconds) : '0m'}
                    </p>
                    <p className="text-xs text-green-600 mt-1">Online</p>
                  </>
                )}
              </div>
              <div className="h-12 w-12 rounded-full bg-green-100 flex items-center justify-center">
                <CheckCircle className="h-6 w-6 text-green-600" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* User Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="hover:shadow-lg transition-shadow">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Total de Usuários</p>
                {statsLoading ? (
                  <Skeleton className="h-10 w-16 mt-2" />
                ) : (
                  <>
                    <p className="text-3xl font-bold mt-2">{stats?.users.total.toLocaleString()}</p>
                    <p className="text-xs text-gray-500 mt-1">Cadastrados</p>
                  </>
                )}
              </div>
              <div className="h-12 w-12 rounded-full bg-blue-100 flex items-center justify-center">
                <Users className="h-6 w-6 text-blue-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="hover:shadow-lg transition-shadow">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Usuários Ativos (24h)</p>
                {statsLoading ? (
                  <Skeleton className="h-10 w-16 mt-2" />
                ) : (
                  <>
                    <p className="text-3xl font-bold mt-2">
                      {stats?.users.active_now.toLocaleString()}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">Últimas 24h</p>
                  </>
                )}
              </div>
              <div className="h-12 w-12 rounded-full bg-green-100 flex items-center justify-center">
                <Activity className="h-6 w-6 text-green-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="hover:shadow-lg transition-shadow">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Administradores</p>
                {statsLoading ? (
                  <Skeleton className="h-10 w-12 mt-2" />
                ) : (
                  <>
                    <p className="text-3xl font-bold mt-2">
                      {(stats?.users.by_role.admin ?? 0).toString()}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      {(stats?.users.by_role.doctor ?? 0).toString()} médicos
                    </p>
                  </>
                )}
              </div>
              <div className="h-12 w-12 rounded-full bg-orange-100 flex items-center justify-center">
                <Shield className="h-6 w-6 text-orange-600" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Database Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="hover:shadow-lg transition-shadow">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Total de Registros</p>
                {statsLoading ? (
                  <Skeleton className="h-10 w-16 mt-2" />
                ) : (
                  <>
                    <p className="text-3xl font-bold mt-2">
                      {stats?.database.total_records.toLocaleString()}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">Registros</p>
                  </>
                )}
              </div>
              <div className="h-12 w-12 rounded-full bg-indigo-100 flex items-center justify-center">
                <Database className="h-6 w-6 text-indigo-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="hover:shadow-lg transition-shadow">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Pacientes</p>
                {statsLoading ? (
                  <Skeleton className="h-10 w-16 mt-2" />
                ) : (
                  <>
                    <p className="text-3xl font-bold mt-2">
                      {stats?.database.total_patients.toLocaleString()}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">Pacientes</p>
                  </>
                )}
              </div>
              <div className="h-12 w-12 rounded-full bg-blue-100 flex items-center justify-center">
                <Users className="h-6 w-6 text-blue-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="hover:shadow-lg transition-shadow">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Usuários no BD</p>
                {statsLoading ? (
                  <Skeleton className="h-10 w-16 mt-2" />
                ) : (
                  <>
                    <p className="text-3xl font-bold mt-2">
                      {stats?.database.total_users.toLocaleString()}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">Usuários</p>
                  </>
                )}
              </div>
              <div className="h-12 w-12 rounded-full bg-green-100 flex items-center justify-center">
                <Users className="h-6 w-6 text-green-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="hover:shadow-lg transition-shadow">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Conexões do BD</p>
                {statsLoading ? (
                  <Skeleton className="h-10 w-12 mt-2" />
                ) : (
                  <>
                    <p className="text-3xl font-bold mt-2">
                      {stats?.database.connections.toString()}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">Ativas</p>
                  </>
                )}
              </div>
              <div className="h-12 w-12 rounded-full bg-purple-100 flex items-center justify-center">
                <Activity className="h-6 w-6 text-purple-600" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Timestamp */}
      {!statsLoading && stats && (
        <div className="flex justify-end">
          <p className="text-sm text-muted-foreground">
            Última atualização: {new Date(stats.timestamp).toLocaleString('pt-BR')}
          </p>
        </div>
      )}

      {/* System Status and Resources */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SystemStatus />

        <Card>
          <CardHeader>
            <CardTitle>Uso de Recursos</CardTitle>
            <CardDescription>Monitoramento de CPU, memória e disco</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {statsLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
              </div>
            ) : stats ? (
              <>
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">CPU</span>
                    <span className="text-sm text-gray-600">
                      {stats.system.cpu_percent.toFixed(1)}%
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full ${
                        stats.system.cpu_percent > 80
                          ? 'bg-red-600'
                          : stats.system.cpu_percent > 60
                            ? 'bg-orange-600'
                            : 'bg-blue-600'
                      }`}
                      style={{ width: `${Math.min(stats.system.cpu_percent, 100)}%` }}
                    />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">Memória</span>
                    <span className="text-sm text-gray-600">
                      {stats.system.memory_percent.toFixed(1)}%
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full ${
                        stats.system.memory_percent > 80
                          ? 'bg-red-600'
                          : stats.system.memory_percent > 60
                            ? 'bg-orange-600'
                            : 'bg-green-600'
                      }`}
                      style={{ width: `${Math.min(stats.system.memory_percent, 100)}%` }}
                    />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">Disco</span>
                    <span className="text-sm text-gray-600">
                      {stats.system.disk_percent.toFixed(1)}%
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full ${
                        stats.system.disk_percent > 80
                          ? 'bg-red-600'
                          : stats.system.disk_percent > 60
                            ? 'bg-orange-600'
                            : 'bg-purple-600'
                      }`}
                      style={{ width: `${Math.min(stats.system.disk_percent, 100)}%` }}
                    />
                  </div>
                </div>

                <div className="pt-4 border-t">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">Última atualização</span>
                    <span className="font-medium">
                      {new Date(stats.timestamp).toLocaleTimeString('pt-BR')}
                    </span>
                  </div>
                </div>
              </>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
