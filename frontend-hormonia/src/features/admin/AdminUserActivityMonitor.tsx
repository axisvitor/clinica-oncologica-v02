import React, { useState, useEffect, useCallback } from 'react'
import { format } from 'date-fns'
import {
  Eye,
  Lock,
  UserX,
  Shield,
  RefreshCw,
  Download,
  Search,
  CheckCircle,
  XCircle,
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { AdminUserActivity, AdminActivityFilter } from '@/types/admin'
import { apiClient } from '@/lib/api-client'
import { createLogger } from '@/lib/logger'

const logger = createLogger('AdminUserActivityMonitor')

interface AdminUserActivityMonitorProps {
  className?: string
}

// Mock data for demonstration
const mockActivityData: AdminUserActivity[] = [
  {
    id: '1',
    user_id: 'user1',
    user_email: 'admin@example.com',
    action: 'login',
    resource: 'admin_panel',
    details: {
      ip: '192.168.1.100',
      browser: 'Chrome 120.0',
      location: 'São Paulo, BR',
    },
    timestamp: '2024-01-15T14:30:00-03:00',
    ip_address: '192.168.1.100',
    user_agent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    session_id: 'sess1',
  },
  {
    id: '2',
    user_id: 'user2',
    user_email: 'doctor@example.com',
    action: 'password_reset',
    resource: 'user_account',
    details: {
      target_user: 'patient123',
      reason: 'Forgot password',
      ip: '192.168.1.101',
    },
    timestamp: '2024-01-15T14:25:00-03:00',
    ip_address: '192.168.1.101',
    user_agent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
    session_id: 'sess2',
  },
  {
    id: '3',
    user_id: 'user1',
    user_email: 'admin@example.com',
    action: 'user_view',
    resource: 'patient_record',
    details: {
      patient_id: 'pt456',
      view_type: 'medical_history',
      duration: 120,
    },
    timestamp: '2024-01-15T14:20:00-03:00',
    ip_address: '192.168.1.100',
    user_agent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    session_id: 'sess1',
  },
  {
    id: '4',
    user_id: 'user3',
    user_email: 'nurse@example.com',
    action: 'failed_login',
    resource: 'admin_panel',
    details: {
      failure_reason: 'Invalid password',
      attempt_number: 3,
      ip: '203.0.113.45',
    },
    timestamp: '2024-01-15T14:15:00-03:00',
    ip_address: '203.0.113.45',
    user_agent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
    session_id: 'failed_sess',
  },
  {
    id: '5',
    user_id: 'user2',
    user_email: 'doctor@example.com',
    action: 'settings_update',
    resource: 'system_settings',
    details: {
      setting: 'session_timeout',
      old_value: '30',
      new_value: '60',
    },
    timestamp: '2024-01-15T14:10:00-03:00',
    ip_address: '192.168.1.101',
    user_agent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
    session_id: 'sess2',
  },
]

const FALLBACK_ICON = { icon: CheckCircle, color: 'text-gray-600', bgColor: 'bg-gray-100' }

const actionIcons: Record<string, typeof FALLBACK_ICON> = {
  login: { icon: Eye, color: 'text-green-600', bgColor: 'bg-green-100' },
  logout: { icon: UserX, color: 'text-gray-600', bgColor: 'bg-gray-100' },
  failed_login: { icon: XCircle, color: 'text-red-600', bgColor: 'bg-red-100' },
  password_reset: { icon: Lock, color: 'text-yellow-600', bgColor: 'bg-yellow-100' },
  user_view: { icon: Eye, color: 'text-blue-600', bgColor: 'bg-blue-100' },
  settings_update: { icon: Shield, color: 'text-purple-600', bgColor: 'bg-purple-100' },
  data_export: { icon: Download, color: 'text-indigo-600', bgColor: 'bg-indigo-100' },
}

export const AdminUserActivityMonitor: React.FC<AdminUserActivityMonitorProps> = ({
  className,
}) => {
  const [activities, setActivities] = useState<AdminUserActivity[]>(mockActivityData)
  const [filteredActivities, setFilteredActivities] =
    useState<AdminUserActivity[]>(mockActivityData)
  const [filters, setFilters] = useState<AdminActivityFilter>({})
  const [searchQuery, setSearchQuery] = useState('')
  const [_selectedActivity, setSelectedActivity] = useState<AdminUserActivity | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const [itemsPerPage] = useState(10)
  const [dateRange, setDateRange] = useState<{ from?: Date; to?: Date }>({})

  // Load activities from API
  const loadActivities = useCallback(async () => {
    setIsLoading(true)
    try {
      // Using any cast here because the API response type might not match exactly what we expect yet
      // In a real scenario, we should define a proper response type
      const response = await apiClient.request<{
        items?: AdminUserActivity[]
        data?: AdminUserActivity[]
        total: number
      }>('/admin/audit-logs', {
        method: 'GET',
        params: {
          page: currentPage,
          size: itemsPerPage,
          ...(dateRange.from && { start_date: dateRange.from.toISOString() }),
          ...(dateRange.to && { end_date: dateRange.to.toISOString() }),
        },
      })

      if (response && response.items) {
        setActivities(response.items)
      } else if (response && response.data) {
        setActivities(response.data)
      } else {
        // Fallback to mock data if API fails
        logger.warn('API returned no data, using mock data')
        setActivities(mockActivityData)
      }
    } catch (error) {
      logger.error('Failed to load activities, using mock data', { error })
      // Fallback to mock data on error
      setActivities(mockActivityData)
    } finally {
      setIsLoading(false)
    }
  }, [currentPage, itemsPerPage, dateRange])

  // Apply filters to activities
  useEffect(() => {
    let filtered = [...activities]

    // Text search
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      filtered = filtered.filter(
        (activity) =>
          activity.action.toLowerCase().includes(query) ||
          activity.resource.toLowerCase().includes(query) ||
          activity.ip_address.includes(query) ||
          activity.user_id.toLowerCase().includes(query) ||
          JSON.stringify(activity.details).toLowerCase().includes(query)
      )
    }

    // Filter by user ID
    if (filters.userId) {
      filtered = filtered.filter((activity) => activity.user_id === filters.userId)
    }

    // Filter by action
    if (filters.action) {
      filtered = filtered.filter((activity) => activity.action === filters.action)
    }

    // Filter by resource
    if (filters.resource) {
      filtered = filtered.filter((activity) => activity.resource === filters.resource)
    }

    // Filter by IP address
    if (filters.ipAddress) {
      filtered = filtered.filter((activity) => activity.ip_address.includes(filters.ipAddress!))
    }

    // Filter by date range
    if (dateRange.from || dateRange.to) {
      filtered = filtered.filter((activity) => {
        const activityDate = new Date(activity.timestamp)
        if (dateRange.from && activityDate < dateRange.from) return false
        if (dateRange.to && activityDate > dateRange.to) return false
        return true
      })
    }

    setFilteredActivities(filtered)
    setCurrentPage(1)
  }, [activities, filters, searchQuery, dateRange])

  // Get paginated activities
  const paginatedActivities = filteredActivities.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  )

  const totalPages = Math.ceil(filteredActivities.length / itemsPerPage)

  // Export activities to CSV
  const exportToCSV = () => {
    const headers = ['Timestamp', 'User ID', 'Action', 'Resource', 'IP Address', 'Details']

    const csvContent = [
      headers.join(','),
      ...filteredActivities.map((activity) =>
        [
          activity.timestamp,
          activity.user_id,
          activity.action,
          activity.resource,
          activity.ip_address,
          `"${JSON.stringify(activity.details).replace(/"/g, '""')}"`,
        ].join(',')
      ),
    ].join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    if (link.download !== undefined) {
      const url = URL.createObjectURL(blob)
      link.setAttribute('href', url)
      link.setAttribute('download', `activity_log_${format(new Date(), 'yyyy-MM-dd')}.csv`)
      link.style.visibility = 'hidden'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    }
  }

  const getActionIcon = (action: string) => {
    return actionIcons[action] || FALLBACK_ICON
  }

  return (
    <Card className={`w-full ${className}`}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Monitor de Atividade</CardTitle>
            <CardDescription>
              Rastreamento em tempo real de ações de usuários e segurança
            </CardDescription>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={loadActivities} disabled={isLoading}>
              <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
              Atualizar
            </Button>
            <Button variant="outline" size="sm" onClick={exportToCSV}>
              <Download className="mr-2 h-4 w-4" />
              Exportar
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* Filters */}
        <div className="mb-6 flex flex-wrap gap-4">
          <div className="flex-1 min-w-[200px]">
            <div className="relative">
              <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Buscar atividades..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8"
              />
            </div>
          </div>

          <Select
            value={filters.action}
            onValueChange={(value) => setFilters({ ...filters, action: value || undefined })}
          >
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Tipo de Ação" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas as Ações</SelectItem>
              <SelectItem value="login">Login</SelectItem>
              <SelectItem value="logout">Logout</SelectItem>
              <SelectItem value="failed_login">Falha de Login</SelectItem>
              <SelectItem value="user_view">Visualização</SelectItem>
              <SelectItem value="settings_update">Configuração</SelectItem>
            </SelectContent>
          </Select>

          <div className="flex items-center gap-2">
            {/* Date picker placeholder - using simple inputs for now to avoid complex dependency */}
            <Input
              type="date"
              className="w-[150px]"
              onChange={(e) =>
                setDateRange((prev) => ({
                  ...prev,
                  from: e.target.value ? new Date(e.target.value) : undefined,
                }))
              }
            />
            <span className="text-muted-foreground">-</span>
            <Input
              type="date"
              className="w-[150px]"
              onChange={(e) =>
                setDateRange((prev) => ({
                  ...prev,
                  to: e.target.value ? new Date(e.target.value) : undefined,
                }))
              }
            />
          </div>
        </div>

        {/* Activity Table */}
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Usuário</TableHead>
                <TableHead>Ação</TableHead>
                <TableHead>Recurso</TableHead>
                <TableHead>IP / Local</TableHead>
                <TableHead>Data/Hora</TableHead>
                <TableHead className="text-right">Detalhes</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {paginatedActivities.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="h-24 text-center">
                    Nenhuma atividade encontrada.
                  </TableCell>
                </TableRow>
              ) : (
                paginatedActivities.map((activity) => {
                  const { icon: Icon, color, bgColor } = getActionIcon(activity.action)
                  return (
                    <TableRow key={activity.id}>
                      <TableCell>
                        <div className="flex flex-col">
                          <span className="font-medium">{activity.user_email}</span>
                          <span className="text-xs text-muted-foreground">{activity.user_id}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <div className={`p-1 rounded-full ${bgColor}`}>
                            <Icon className={`h-4 w-4 ${color}`} />
                          </div>
                          <span className="capitalize">{activity.action.replace('_', ' ')}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="font-mono text-xs">
                          {activity.resource}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col text-xs">
                          <span>{activity.ip_address}</span>
                          <span className="text-muted-foreground">
                            {String(activity.details['location'] || 'Unknown')}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col text-sm">
                          <span className="font-medium">
                            {format(new Date(activity.timestamp), 'dd/MM/yyyy')}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {format(new Date(activity.timestamp), 'HH:mm:ss')}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <Dialog>
                          <DialogTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setSelectedActivity(activity)}
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                          </DialogTrigger>
                          <DialogContent>
                            <DialogHeader>
                              <DialogTitle>Detalhes da Atividade</DialogTitle>
                              <DialogDescription>
                                ID da Sessão: {activity.session_id}
                              </DialogDescription>
                            </DialogHeader>
                            <div className="grid gap-4 py-4">
                              <div className="grid grid-cols-2 gap-4">
                                <div>
                                  <Label>Usuário</Label>
                                  <div className="text-sm font-medium">{activity.user_email}</div>
                                </div>
                                <div>
                                  <Label>Ação</Label>
                                  <div className="text-sm font-medium">{activity.action}</div>
                                </div>
                                <div>
                                  <Label>IP</Label>
                                  <div className="text-sm font-medium">{activity.ip_address}</div>
                                </div>
                                <div>
                                  <Label>Navegador</Label>
                                  <div className="text-sm font-medium">{activity.user_agent}</div>
                                </div>
                              </div>
                              <div>
                                <Label>Dados Completos (JSON)</Label>
                                <pre className="mt-2 w-full rounded-md bg-slate-950 p-4 overflow-auto text-xs text-slate-50">
                                  {JSON.stringify(activity.details, null, 2)}
                                </pre>
                              </div>
                            </div>
                          </DialogContent>
                        </Dialog>
                      </TableCell>
                    </TableRow>
                  )
                })
              )}
            </TableBody>
          </Table>
        </div>

        {/* Pagination */}
        <div className="mt-4 flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            Mostrando {(currentPage - 1) * itemsPerPage + 1} a{' '}
            {Math.min(currentPage * itemsPerPage, filteredActivities.length)} de{' '}
            {filteredActivities.length} resultados
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
            >
              Anterior
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
            >
              Próxima
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
