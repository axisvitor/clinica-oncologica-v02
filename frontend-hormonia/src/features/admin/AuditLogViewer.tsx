import React, { useState, useMemo, memo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import {
  Search,
  Filter,
  Download,
  RefreshCw,
  Calendar,
  User,
  Shield,
  AlertTriangle,
  Info,
  CheckCircle,
  XCircle,
  Eye,
  FileText,
  Clock,
  ExternalLink
} from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import { AuditLogEntry } from '@/types/admin'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { DateRangePicker } from '@/components/ui/date-range-picker'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Pagination } from '@/components/ui/pagination'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { PermissionGuard } from './PermissionGuard'
import { FixedSizeList } from 'react-window'
import AutoSizer from 'react-virtualized-auto-sizer'
import { cn } from '@/lib/utils'

interface AuditLogFilters {
  search: string
  action: string
  resource: string
  severity: string
  userId: string
  dateRange: {
    from: Date | null
    to: Date | null
  }
  page: number
  size: number
}

interface AuditLogViewerProps {
  userId?: string // If provided, show logs for specific user only
  compact?: boolean
  maxHeight?: string
}

interface RowData {
  items: AuditLogEntry[]
  compact: boolean
  gridCols: string
}

const getActionIcon = (action: string) => {
  switch (action.toLowerCase()) {
    case 'login': return <CheckCircle className="h-4 w-4 text-green-600" />
    case 'logout': return <XCircle className="h-4 w-4 text-gray-600" />
    case 'failed_login': return <AlertTriangle className="h-4 w-4 text-red-600" />
    case 'create_user':
    case 'create_patient': return <User className="h-4 w-4 text-green-600" />
    case 'update_user':
    case 'update_patient': return <FileText className="h-4 w-4 text-blue-600" />
    case 'delete_user':
    case 'delete_patient': return <AlertTriangle className="h-4 w-4 text-red-600" />
    case 'view_patient':
    case 'access_data': return <Eye className="h-4 w-4 text-gray-600" />
    case 'permission_change':
    case 'role_change': return <Shield className="h-4 w-4 text-purple-600" />
    default: return <Info className="h-4 w-4 text-blue-600" />
  }
}

const getSeverityLevel = (action: string) => {
  switch (action.toLowerCase()) {
    case 'failed_login':
    case 'delete_user':
    case 'delete_patient':
    case 'permission_change': return 'high'
    case 'create_user':
    case 'create_patient':
    case 'update_user':
    case 'update_patient':
    case 'role_change': return 'medium'
    default: return 'low'
  }
}

const getSeverityBadge = (severity: string) => {
  switch (severity) {
    case 'high': return <Badge variant="destructive">Alto</Badge>
    case 'medium': return <Badge variant="default">Médio</Badge>
    default: return <Badge variant="secondary">Baixo</Badge>
  }
}

const formatRelativeTime = (timestamp: string) => {
  try {
    return formatDistanceToNow(new Date(timestamp), { addSuffix: true, locale: ptBR })
  } catch {
    return 'Data inválida'
  }
}

const formatFullTime = (timestamp: string) => {
  try {
    return new Date(timestamp).toLocaleString('pt-BR')
  } catch {
    return 'Data inválida'
  }
}

const getActionDescription = (log: AuditLogEntry) => {
  switch (log.action.toLowerCase()) {
    case 'login': return 'Realizou login no sistema'
    case 'logout': return 'Realizou logout do sistema'
    case 'failed_login': return 'Tentativa de login falhada'
    case 'create_user': return 'Criou um novo usuário'
    case 'create_patient': return 'Criou um novo paciente'
    case 'update_user': return 'Atualizou informações de usuário'
    case 'update_patient': return 'Atualizou informações de paciente'
    case 'delete_user': return 'Excluiu um usuário'
    case 'delete_patient': return 'Excluiu um paciente'
    case 'view_patient': return 'Visualizou dados de paciente'
    case 'permission_change': return 'Alterou permissões de usuário'
    case 'role_change': return 'Alterou função de usuário'
    default: return log.action.replace('_', ' ')
  }
}

const AuditLogRow = memo(({ style, index, items, compact, gridCols }: any) => {
  const log = items[index]

  return (
    <div
      style={style}
      className={cn(
        "grid items-center gap-4 px-4 py-2 border-b hover:bg-muted/50 transition-colors text-sm",
        gridCols
      )}
    >
      <div className="flex items-center gap-2 min-w-0">
        {getActionIcon(log.action)}
        <span className="font-medium truncate">{getActionDescription(log)}</span>
      </div>
      <div className="flex items-center gap-2 min-w-0">
        <User className="h-4 w-4 text-gray-500 flex-shrink-0" />
        <span className="text-sm truncate">{log.user_email}</span>
      </div>
      <div className="min-w-0 space-y-1">
        <p className="font-medium truncate">{log.resource}</p>
        {log.resource_id && (
          <p className="text-xs text-gray-500 truncate">{log.resource_id}</p>
        )}
      </div>
      <div>{getSeverityBadge(getSeverityLevel(log.action))}</div>
      <div className="min-w-0 space-y-1">
        <p className="text-sm truncate" title={formatFullTime(log.timestamp)}>
          {formatRelativeTime(log.timestamp)}
        </p>
        <p className="text-xs text-gray-500 truncate">
          {formatFullTime(log.timestamp)}
        </p>
      </div>
      <div className="min-w-0">
        <span className="text-sm font-mono truncate block">{log.ip_address}</span>
      </div>
      {!compact && (
        <div className="min-w-0">
          {log.details && Object.keys(log.details).length > 0 && (
            <details>
              <summary className="text-xs text-blue-600 cursor-pointer">
                Ver detalhes
              </summary>
              <div className="mt-2 p-2 bg-gray-50 rounded text-xs overflow-x-auto">
                <pre>{JSON.stringify(log.details, null, 2)}</pre>
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  )
})

const AuditLogTimelineItem = memo(({ style, index, items }: any) => {
  const log = items[index]

  return (
    <div style={style} className="px-4 py-2">
      <div className="flex items-start space-x-3 p-4 border rounded-lg h-full">
        <div className="mt-1 flex-shrink-0">
          {getActionIcon(log.action)}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2 min-w-0">
              <p className="text-sm font-medium truncate">{getActionDescription(log)}</p>
              {getSeverityBadge(getSeverityLevel(log.action))}
            </div>
            <p className="text-xs text-gray-500 flex-shrink-0" title={formatFullTime(log.timestamp)}>
              {formatRelativeTime(log.timestamp)}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-4 text-xs text-gray-600">
            <span className="flex items-center gap-1">
              <User className="h-3 w-3" />
              {log.user_email}
            </span>
            <span>{log.resource}</span>
            {log.resource_id && <span>ID: {log.resource_id}</span>}
            <span>IP: {log.ip_address}</span>
          </div>
          {log.details && Object.keys(log.details).length > 0 && (
            <details className="mt-2">
              <summary className="text-xs text-blue-600 cursor-pointer">
                Ver detalhes
              </summary>
              <div className="mt-1 p-2 bg-gray-50 rounded text-xs overflow-x-auto">
                <pre>{JSON.stringify(log.details, null, 2)}</pre>
              </div>
            </details>
          )}
        </div>
      </div>
    </div>
  )
})

export function AuditLogViewer({
  userId,
  compact = false,
  maxHeight = "600px"
}: AuditLogViewerProps) {
  const [filters, setFilters] = useState<AuditLogFilters>({
    search: '',
    action: 'all',
    resource: 'all',
    severity: 'all',
    userId: userId || '',
    dateRange: { from: null, to: null },
    page: 1,
    size: compact ? 5 : 20
  })

  const [viewMode, setViewMode] = useState<'table' | 'timeline'>('table')

  // Mock data - replace with actual API call
  const {
    data: auditLogs,
    isLoading,
    error,
    refetch
  } = useQuery({
    queryKey: ['audit-logs', filters],
    queryFn: async () => {
      // Mock implementation - replace with actual API call
      const mockLogs: AuditLogEntry[] = [
        {
          id: '1',
          user_id: 'user1',
          user_email: 'admin@clinic.com',
          action: 'login',
          resource: 'auth',
          resource_id: 'session-123',
          details: { ip_address: '192.168.1.100', user_agent: 'Chrome 120.0' },
          ip_address: '192.168.1.100',
          user_agent: 'Chrome 120.0',
          timestamp: new Date(Date.now() - 1000 * 60 * 10).toISOString() // 10 minutes ago
        },
        {
          id: '2',
          user_id: 'user1',
          user_email: 'admin@clinic.com',
          action: 'create_patient',
          resource: 'patients',
          resource_id: 'patient-456',
          details: { patient_name: 'João Silva', created_fields: ['name', 'email', 'phone'] },
          ip_address: '192.168.1.100',
          user_agent: 'Chrome 120.0',
          timestamp: new Date(Date.now() - 1000 * 60 * 30).toISOString() // 30 minutes ago
        },
        {
          id: '3',
          user_id: 'user2',
          user_email: 'doctor@clinic.com',
          action: 'view_patient',
          resource: 'patients',
          resource_id: 'patient-456',
          details: { patient_name: 'João Silva', sections_accessed: ['medical_history', 'medications'] },
          ip_address: '192.168.1.105',
          user_agent: 'Firefox 119.0',
          timestamp: new Date(Date.now() - 1000 * 60 * 60).toISOString() // 1 hour ago
        },
        {
          id: '4',
          user_id: 'user1',
          user_email: 'admin@clinic.com',
          action: 'failed_login',
          resource: 'auth',
          details: { reason: 'invalid_password', attempts: 3 },
          ip_address: '192.168.1.200',
          user_agent: 'Chrome 120.0',
          timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString() // 2 hours ago
        },
        {
          id: '5',
          user_id: 'user3',
          user_email: 'doctor@clinic.com',
          action: 'update_patient',
          resource: 'patients',
          resource_id: 'patient-789',
          details: { patient_name: 'Maria Santos', updated_fields: ['medications', 'notes'] },
          ip_address: '192.168.1.110',
          user_agent: 'Safari 17.0',
          timestamp: new Date(Date.now() - 1000 * 60 * 60 * 3).toISOString() // 3 hours ago
        }
      ]

      return {
        items: mockLogs.filter(log => {
          if (filters.userId && log.user_id !== filters.userId) return false
          if (filters.search) {
            const searchLower = filters.search.toLowerCase()
            const matchesSearch = 
              log.action.toLowerCase().includes(searchLower) ||
              log.resource.toLowerCase().includes(searchLower) ||
              log.user_email.toLowerCase().includes(searchLower) ||
              (log.resource_id && log.resource_id.toLowerCase().includes(searchLower))
            if (!matchesSearch) return false
          }
          if (filters.action !== 'all' && log.action !== filters.action) return false
          if (filters.resource !== 'all' && log.resource !== filters.resource) return false
          return true
        }),
        total: mockLogs.length,
        page: filters.page,
        size: filters.size,
        pages: Math.ceil(mockLogs.length / filters.size)
      }
    },
    refetchInterval: 30000 // Refresh every 30 seconds
  })

  const exportLogs = () => {
    if (!auditLogs?.items) return

    const csvContent = [
      ['Data/Hora', 'Usuário', 'Ação', 'Recurso', 'Severidade', 'IP', 'Detalhes'],
      ...auditLogs.items.map(log => [
        formatFullTime(log.timestamp),
        log.user_email,
        getActionDescription(log),
        log.resource + (log.resource_id ? ` (${log.resource_id})` : ''),
        getSeverityLevel(log.action),
        log.ip_address,
        JSON.stringify(log.details)
      ])
    ].map(row => row.map(cell => `"${cell}"`).join(',')).join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `audit-logs-${new Date().toISOString().split('T')[0]}.csv`
    link.click()
  }

  const stats = useMemo(() => {
    if (!auditLogs?.items) return { total: 0, high: 0, medium: 0, low: 0 }

    return auditLogs.items.reduce((acc, log) => {
      const severity = getSeverityLevel(log.action)
      acc.total++
      acc[severity as 'high' | 'medium' | 'low']++
      return acc
    }, { total: 0, high: 0, medium: 0, low: 0 })
  }, [auditLogs])

  if (isLoading && !auditLogs) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-center h-64">
            <LoadingSpinner size="lg" />
          </div>
        </CardContent>
      </Card>
    )
  }

  const gridCols = compact
    ? "grid-cols-[1.5fr_1.5fr_1fr_0.8fr_1.2fr_0.8fr]"
    : "grid-cols-[1.5fr_1.5fr_1fr_0.8fr_1.2fr_0.8fr_1fr]"

  const itemData: RowData = {
    items: auditLogs?.items || [],
    compact,
    gridCols
  }

  return (
    <div className="space-y-6">
      {!compact && (
        <>
          {/* Header */}
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-2xl font-bold tracking-tight">Logs de Auditoria</h2>
              <p className="text-muted-foreground">
                Histórico completo de ações realizadas no sistema
              </p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => refetch()}>
                <RefreshCw className="h-4 w-4 mr-2" />
                Atualizar
              </Button>
              <PermissionGuard permissions={['admin.audit.export']}>
                <Button variant="outline" onClick={exportLogs}>
                  <Download className="h-4 w-4 mr-2" />
                  Exportar
                </Button>
              </PermissionGuard>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Total de Eventos</p>
                    <p className="text-2xl font-bold">{stats.total}</p>
                  </div>
                  <FileText className="h-8 w-8 text-blue-600" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Severidade Alta</p>
                    <p className="text-2xl font-bold text-red-600">{stats.high}</p>
                  </div>
                  <AlertTriangle className="h-8 w-8 text-red-600" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Severidade Média</p>
                    <p className="text-2xl font-bold text-orange-600">{stats.medium}</p>
                  </div>
                  <Shield className="h-8 w-8 text-orange-600" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Severidade Baixa</p>
                    <p className="text-2xl font-bold text-green-600">{stats.low}</p>
                  </div>
                  <CheckCircle className="h-8 w-8 text-green-600" />
                </div>
              </CardContent>
            </Card>
          </div>
        </>
      )}

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col md:flex-row gap-4">
            {/* Search */}
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
                <Input
                  placeholder="Buscar por ação, recurso ou usuário..."
                  value={filters.search}
                  onChange={(e) => setFilters(prev => ({ ...prev, search: e.target.value, page: 1 }))}
                  className="pl-10"
                />
              </div>
            </div>

            {/* Action Filter */}
            <Select
              value={filters.action}
              onValueChange={(value) => setFilters(prev => ({ ...prev, action: value, page: 1 }))}
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Filtrar por ação" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas as ações</SelectItem>
                <SelectItem value="login">Login</SelectItem>
                <SelectItem value="logout">Logout</SelectItem>
                <SelectItem value="failed_login">Login Falhado</SelectItem>
                <SelectItem value="create_user">Criar Usuário</SelectItem>
                <SelectItem value="update_user">Atualizar Usuário</SelectItem>
                <SelectItem value="delete_user">Excluir Usuário</SelectItem>
                <SelectItem value="create_patient">Criar Paciente</SelectItem>
                <SelectItem value="update_patient">Atualizar Paciente</SelectItem>
                <SelectItem value="view_patient">Visualizar Paciente</SelectItem>
              </SelectContent>
            </Select>

            {/* Resource Filter */}
            <Select
              value={filters.resource}
              onValueChange={(value) => setFilters(prev => ({ ...prev, resource: value, page: 1 }))}
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Filtrar por recurso" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos os recursos</SelectItem>
                <SelectItem value="auth">Autenticação</SelectItem>
                <SelectItem value="users">Usuários</SelectItem>
                <SelectItem value="patients">Pacientes</SelectItem>
                <SelectItem value="flows">Fluxos</SelectItem>
                <SelectItem value="settings">Configurações</SelectItem>
              </SelectContent>
            </Select>

            {/* Severity Filter */}
            <Select
              value={filters.severity}
              onValueChange={(value) => setFilters(prev => ({ ...prev, severity: value, page: 1 }))}
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Filtrar por severidade" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas as severidades</SelectItem>
                <SelectItem value="high">Alta</SelectItem>
                <SelectItem value="medium">Média</SelectItem>
                <SelectItem value="low">Baixa</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Content */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Registros de Auditoria</CardTitle>
              <CardDescription>
                {auditLogs?.total || 0} evento(s) encontrado(s)
              </CardDescription>
            </div>
            {!compact && (
              <Tabs value={viewMode} onValueChange={(value) => setViewMode(value as 'table' | 'timeline')}>
                <TabsList>
                  <TabsTrigger value="table">Tabela</TabsTrigger>
                  <TabsTrigger value="timeline">Timeline</TabsTrigger>
                </TabsList>
              </Tabs>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div style={{ height: maxHeight, minHeight: 400 }} className="flex flex-col">
            {viewMode === 'table' ? (
              <div className="flex-1 flex flex-col overflow-hidden">
                <div className={cn("grid bg-muted/50 font-medium text-sm border-b p-2", gridCols)}>
                  <div className="px-2">Ação</div>
                  <div className="px-2">Usuário</div>
                  <div className="px-2">Recurso</div>
                  <div className="px-2">Severidade</div>
                  <div className="px-2">Data/Hora</div>
                  <div className="px-2">IP</div>
                  {!compact && <div className="px-2">Detalhes</div>}
                </div>
                <div className="flex-1">
                   <AutoSizer>
                      {({ height, width }) => (
                        <FixedSizeList
                          height={height}
                          width={width}
                          itemCount={auditLogs?.items.length || 0}
                          itemSize={compact ? 50 : 60}
                          itemData={itemData}
                        >
                          {AuditLogRow as any}
                        </FixedSizeList>
                      )}
                   </AutoSizer>
                </div>
              </div>
            ) : (
               <div className="flex-1">
                  <AutoSizer>
                    {({ height, width }) => (
                      <FixedSizeList
                        height={height}
                        width={width}
                        itemCount={auditLogs?.items.length || 0}
                        itemSize={120}
                        itemData={itemData}
                      >
                        {AuditLogTimelineItem as any}
                      </FixedSizeList>
                    )}
                  </AutoSizer>
               </div>
            )}
            
            {(!auditLogs?.items || auditLogs.items.length === 0) && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-white bg-opacity-80 z-10">
                <FileText className="h-12 w-12 text-gray-400 mb-4" />
                <p className="text-gray-500">Nenhum log de auditoria encontrado</p>
              </div>
            )}
          </div>

          {auditLogs && auditLogs.pages > 1 && (
            <div className="mt-4">
              <Pagination
                currentPage={auditLogs.page}
                totalPages={auditLogs.pages}
                onPageChange={(page) => setFilters(prev => ({ ...prev, page }))}
              />
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}