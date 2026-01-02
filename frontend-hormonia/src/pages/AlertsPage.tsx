import React, { useState, useMemo, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { TriangleAlert as AlertTriangle, CircleCheck as CheckCircle, Clock, ListFilter as Filter, Search, X, Download, RefreshCw, CheckCheck } from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { AlertsSkeleton } from '@/features/alerts/AlertsSkeleton'
import { AlertCard } from '@/features/alerts/AlertCard'
import { useToast } from '@/components/ui/use-toast'
import { Checkbox } from '@/components/ui/checkbox'
import { createLogger } from '@/lib/logger'

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

const logger = createLogger('AlertsPage')

// Custom hook for debounced value
function useDebounce<T>(value: T, delay: number = 300): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value)

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value)
    }, delay)

    return () => {
      clearTimeout(handler)
    }
  }, [value, delay])

  return debouncedValue
}

export function AlertsPage() {
  const [currentPage, setCurrentPage] = useState(1)
  const [filters, setFilters] = useState({
    severity: 'all',
    acknowledged: 'all',
    type: 'all'
  })
  const [showFilters, setShowFilters] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedAlerts, setSelectedAlerts] = useState<Set<string>>(new Set())
  const [viewMode, setViewMode] = useState<'list' | 'compact'>('list')

  const { toast } = useToast()
  const queryClient = useQueryClient()

  // Debounce search query to avoid excessive API calls
  const debouncedSearchQuery = useDebounce(searchQuery, 300)

  const { data: alertsData, isLoading } = useQuery({
    queryKey: ['alerts', currentPage, filters, debouncedSearchQuery],
    queryFn: () => apiClient.alerts.list({
      page: currentPage,
      size: 20,
      ...(filters.severity !== 'all' && { severity: filters.severity as any }),
      ...(filters.acknowledged !== 'all' && { acknowledged: filters.acknowledged === 'true' }),
      ...(filters.type !== 'all' && { alert_type: filters.type })
    })
  })

  const acknowledgeMutation = useMutation({
    mutationFn: (alertId: string) => apiClient.alerts.acknowledge(alertId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
      toast({
        title: 'Alerta reconhecido',
        description: 'O alerta foi marcado como reconhecido.',
      })
    },
    onError: (error: unknown) => {
      logger.error('Acknowledge error', { error })
      const message = (error as { data?: { message?: string } }).data?.message || 'Ocorreu um erro inesperado.';
      toast({
        title: 'Erro ao reconhecer alerta',
        description: message,
        variant: 'destructive'
      })
    }
  })

  const resolveMutation = useMutation({
    mutationFn: (alertId: string) => apiClient.alerts.resolve(alertId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
      toast({
        title: 'Alerta resolvido',
        description: 'O alerta foi marcado como resolvido.',
      })
    },
    onError: (error: unknown) => {
      logger.error('Resolve error', { error })
      const message = (error as { data?: { message?: string } }).data?.message || 'Ocorreu um erro inesperado.';
      toast({
        title: 'Erro ao resolver alerta',
        description: message,
        variant: 'destructive'
      })
    }
  })

  const bulkAcknowledgeMutation = useMutation({
    mutationFn: async (alertIds: string[]) => {
      await Promise.all(alertIds.map(id => apiClient.alerts.acknowledge(id)))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
      setSelectedAlerts(new Set())
      toast({
        title: 'Alertas reconhecidos',
        description: `${selectedAlerts.size} alertas foram reconhecidos com sucesso.`,
      })
    },
    onError: (error: unknown) => {
      const message = (error as { message?: string }).message || 'Ocorreu um erro inesperado.';
      toast({
        title: 'Erro ao reconhecer alertas',
        description: message,
        variant: 'destructive'
      })
    }
  })

  const bulkResolveMutation = useMutation({
    mutationFn: async (alertIds: string[]) => {
      await Promise.all(alertIds.map(id => apiClient.alerts.resolve(id)))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
      setSelectedAlerts(new Set())
      toast({
        title: 'Alertas resolvidos',
        description: `${selectedAlerts.size} alertas foram resolvidos com sucesso.`,
      })
    },
    onError: (error: unknown) => {
      const message = (error as { message?: string }).message || 'Ocorreu um erro inesperado.';
      toast({
        title: 'Erro ao resolver alertas',
        description: message,
        variant: 'destructive'
      })
    }
  })

  const filteredAlerts = useMemo(() => {
    let alerts = alertsData?.items || []

    // Apply type filter (handled by backend now)
    // if (filters.type !== 'all') {
    //   alerts = alerts.filter((alert) => alert.type === filters.type)
    // }

    // Apply search filter (client-side)
    if (debouncedSearchQuery) {
      const query = debouncedSearchQuery.toLowerCase()
      alerts = alerts.filter((alert) =>
        alert.title?.toLowerCase().includes(query) ||
        alert.message?.toLowerCase().includes(query) ||
        alert.patient_name?.toLowerCase().includes(query)
      )
    }

    return alerts
  }, [alertsData?.items, filters.type, debouncedSearchQuery])

  const stats = useMemo(() => {
    const alerts = alertsData?.items || []
    return {
      total: alertsData?.total || 0,
      unacknowledged: alerts.filter((a) => !a.is_acknowledged).length,
      critical: alerts.filter((a) => a.severity === 'critical').length,
      high: alerts.filter((a) => a.severity === 'high').length
    }
  }, [alertsData])

  const hasActiveFilters = useMemo(
    () =>
      (['severity', 'acknowledged', 'type'] as const).some(
        (key) => filters[key] !== 'all'
      ),
    [filters]
  )

  const handleSelectAll = () => {
    if (selectedAlerts.size === filteredAlerts.length) {
      setSelectedAlerts(new Set())
    } else {
      setSelectedAlerts(new Set(filteredAlerts.map((a) => a.id)))
    }
  }

  const handleSelectAlert = (alertId: string) => {
    const newSelected = new Set(selectedAlerts)
    if (newSelected.has(alertId)) {
      newSelected.delete(alertId)
    } else {
      newSelected.add(alertId)
    }
    setSelectedAlerts(newSelected)
  }

  const handleBulkAcknowledge = () => {
    bulkAcknowledgeMutation.mutate(Array.from(selectedAlerts))
  }

  const handleBulkResolve = () => {
    bulkResolveMutation.mutate(Array.from(selectedAlerts))
  }

  const handleExportAlerts = () => {
    const csvData = filteredAlerts.map((alert) => ({
      'ID': alert.id,
      'Título': alert.title,
      'Mensagem': alert.message,
      'Severidade': alert.severity,
      'Tipo': alert.type,
      'Paciente': alert.patient_name || 'N/A',
      'Data': new Date(alert.created_at).toLocaleString('pt-BR')
    }))

    const headers: string[] = Object.keys(csvData[0] || {})
    const csvLines: string[] = [
      headers.join(','),
      ...csvData.map((row) => headers.map((h: string) => `"${String(row[h as keyof typeof row] ?? '')}"`).join(','))
    ]
    const csv = csvLines.join('\n')

    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `alertas-${new Date().toISOString().split('T')[0]}.csv`
    a.click()
    URL.revokeObjectURL(url)

    toast({
      title: 'Exportação concluída',
      description: 'Alertas exportados com sucesso.'
    })
  }

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['alerts'] })
    toast({
      title: 'Atualizado',
      description: 'Lista de alertas atualizada.'
    })
  }

  const handleClearFilters = () => {
    setFilters({ severity: 'all', acknowledged: 'all', type: 'all' })
    setSearchQuery('')
    toast({
      title: 'Filtros limpos',
      description: 'Todos os filtros foram removidos.'
    })
  }

  return (
    <div className="space-y-4 md:space-y-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-gray-900">Alertas</h1>
          <p className="text-sm md:text-base text-gray-600">
            Monitore e gerencie alertas do sistema em tempo real
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Button variant="outline" size="sm" onClick={handleRefresh}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Atualizar
          </Button>
          <Button variant="outline" size="sm" onClick={handleExportAlerts} disabled={filteredAlerts.length === 0}>
            <Download className="mr-2 h-4 w-4" />
            Exportar
          </Button>
          <Badge variant="outline" className="bg-red-50 text-red-700">
            {stats.unacknowledged} não reconhecidos
          </Badge>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Total de Alertas
            </CardTitle>
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
            <p className="text-xs text-muted-foreground">
              Alertas no sistema
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Não Reconhecidos
            </CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.unacknowledged}</div>
            <p className="text-xs text-muted-foreground">
              Requerem atenção
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Críticos
            </CardTitle>
            <AlertTriangle className="h-4 w-4 text-red-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.critical}</div>
            <p className="text-xs text-muted-foreground">
              Prioridade máxima
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Alta Prioridade
            </CardTitle>
            <AlertTriangle className="h-4 w-4 text-orange-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.high}</div>
            <p className="text-xs text-muted-foreground">
              Prioridade alta
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Filters and Search */}
      <Card>
        <CardContent className="pt-4 md:pt-6 px-4 md:px-6">
          <div className="space-y-4">
            <div className="flex flex-col lg:flex-row items-stretch lg:items-center gap-3">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  name="alertSearch"
                  placeholder="Buscar por título, mensagem ou paciente..."
                  className="pl-10 text-sm"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery('')}
                    className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowFilters(!showFilters)}
                  className={showFilters ? 'bg-blue-50' : ''}
                >
                  <Filter className="mr-2 h-4 w-4" />
                  Filtros
                  {hasActiveFilters && (
                    <Badge className="ml-2" variant="secondary">1</Badge>
                  )}
                </Button>
                {(hasActiveFilters || searchQuery) && (
                  <Button variant="ghost" size="sm" onClick={handleClearFilters}>
                    <X className="mr-2 h-4 w-4" />
                    Limpar
                  </Button>
                )}
              </div>
            </div>

            {showFilters && (
              <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4 p-4 bg-gray-50 rounded-lg">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Severidade</label>
                  <Select
                    name="severityFilter"
                    value={filters.severity}
                    onValueChange={(value: string) => setFilters({ ...filters, severity: value })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Todas" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Todas as severidades</SelectItem>
                      <SelectItem value="critical">Crítico</SelectItem>
                      <SelectItem value="high">Alto</SelectItem>
                      <SelectItem value="medium">Médio</SelectItem>
                      <SelectItem value="low">Baixo</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Status</label>
                  <Select
                    name="acknowledgedFilter"
                    value={filters.acknowledged}
                    onValueChange={(value: string) => setFilters({ ...filters, acknowledged: value })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Todos" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Todos os status</SelectItem>
                      <SelectItem value="false">Não reconhecidos</SelectItem>
                      <SelectItem value="true">Reconhecidos</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Tipo</label>
                  <Select
                    name="typeFilter"
                    value={filters.type}
                    onValueChange={(value: string) => setFilters({ ...filters, type: value })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Todos" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Todos os tipos</SelectItem>
                      <SelectItem value="medical">Médico</SelectItem>
                      <SelectItem value="engagement">Engajamento</SelectItem>
                      <SelectItem value="system">Sistema</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}

            {selectedAlerts.size > 0 && (
              <div className="flex items-center justify-between p-3 bg-blue-50 rounded-lg">
                <span className="text-sm font-medium text-blue-900">
                  {selectedAlerts.size} alerta{selectedAlerts.size > 1 ? 's' : ''} selecionado{selectedAlerts.size > 1 ? 's' : ''}
                </span>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleBulkAcknowledge}
                    disabled={bulkAcknowledgeMutation.isPending}
                  >
                    <CheckCircle className="mr-2 h-4 w-4" />
                    Reconhecer
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleBulkResolve}
                    disabled={bulkResolveMutation.isPending}
                  >
                    <CheckCheck className="mr-2 h-4 w-4" />
                    Resolver
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setSelectedAlerts(new Set())}
                  >
                    Cancelar
                  </Button>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Alerts List */}
      <div>
        {isLoading ? (
          <AlertsSkeleton />
        ) : filteredAlerts.length === 0 ? (
          <Card>
            <CardContent className="pt-6">
              <div className="text-center py-12">
                {searchQuery || hasActiveFilters ? (
                  <>
                    <AlertTriangle className="mx-auto h-12 w-12 text-gray-400 mb-4" />
                    <p className="text-lg font-medium text-gray-900 mb-2">Nenhum alerta encontrado</p>
                    <p className="text-sm text-gray-500 mb-4">
                      Tente ajustar os filtros ou termos de busca
                    </p>
                    <Button variant="outline" onClick={handleClearFilters}>
                      Limpar filtros
                    </Button>
                  </>
                ) : (
                  <>
                    <CheckCircle className="mx-auto h-12 w-12 text-green-500 mb-4" />
                    <p className="text-lg font-medium text-gray-900 mb-2">Tudo certo!</p>
                    <p className="text-sm text-gray-500">
                      Não há alertas pendentes no momento
                    </p>
                  </>
                )}
              </div>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {filteredAlerts.length > 0 && (
              <div className="flex items-center gap-3 px-2">
                <Checkbox
                  checked={selectedAlerts.size === filteredAlerts.length && filteredAlerts.length > 0}
                  onCheckedChange={handleSelectAll}
                />
                <span className="text-sm text-gray-600">
                  Selecionar todos ({filteredAlerts.length})
                </span>
              </div>
            )}
            {filteredAlerts.map((alert) => (
              <div key={alert.id} className="flex items-start gap-3">
                <div className="pt-6">
                  <Checkbox
                    checked={selectedAlerts.has(alert.id)}
                    onCheckedChange={() => handleSelectAlert(alert.id)}
                  />
                </div>
                <div className="flex-1">
                  <AlertCard
                    alert={alert}
                    onAcknowledge={(alertId) => acknowledgeMutation.mutate(alertId)}
                    onResolve={(alertId) => resolveMutation.mutate(alertId)}
                    isLoading={acknowledgeMutation.isPending || resolveMutation.isPending}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
